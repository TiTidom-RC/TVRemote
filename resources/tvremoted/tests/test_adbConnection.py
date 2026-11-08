""" Appareils ADB : connexion unique partagée par la boucle et les commandes, boucle qui ne s'arrête que sur annulation,
retrait pendant une tentative de connexion, appairage (statut changé seulement sur un résultat certain, clé relue).
Fausse connexion ADB (FakeAdb), aucun réseau.
Lancement depuis resources/tvremoted :  python -m unittest discover -s tests -t . """

import asyncio
import unittest
from unittest import mock

from adb_shell.exceptions import DeviceAuthError, TcpTimeoutException

import tvremoted
from config import Config
from tests.helpers import API_KEY, FakePublisher, newConfig, waitUntil

MAC = 'AA:BB:CC:DD:EE:FF'
HOST = '192.168.1.10'


class FakeAdb:
    """ Remplace adb_shell AdbDeviceTcpAsync. Chaque connect() consomme le résultat suivant de `connectResults`, commun à toutes les
    instances : une exception à lever, un asyncio.Event à attendre avant de réussir, ou None ; liste vide : connexion réussie """
    connectResults: list = []
    instances: list = []
    shellError = None  # exception levée par le prochain shell()

    def __init__(self, host, port, default_transport_timeout_s=None):
        self.host = host
        self.connectCalls = 0
        self.signers = []
        self.commands = []
        self.connected = False
        FakeAdb.instances.append(self)

    @classmethod
    def reset(cls, results=None):
        cls.connectResults = list(results or [])
        cls.instances = []
        cls.shellError = None

    @classmethod
    def totalConnectCalls(cls):
        return sum(adb.connectCalls for adb in cls.instances)

    async def connect(self, rsa_keys=None, transport_timeout_s=None, auth_timeout_s=None):
        self.connectCalls += 1
        self.signers.append(rsa_keys[0] if rsa_keys else None)
        if FakeAdb.connectResults:
            result = FakeAdb.connectResults.pop(0)
            if isinstance(result, asyncio.Event):
                await result.wait()
            elif result is not None:
                raise result
        self.connected = True
        return True

    async def shell(self, command, transport_timeout_s=None):
        if FakeAdb.shellError is not None:
            error, FakeAdb.shellError = FakeAdb.shellError, None
            raise error
        self.commands.append(command)
        return 'ok'

    async def close(self):
        self.connected = False


def addAdbMessage(persistent=0, paired=1, host=HOST):
    return {'apikey': API_KEY, 'cmd': 'addtvremote_adb', 'mac': MAC, 'host': host, 'friendly_name': 'Salon',
            'adb_paired': paired, 'adb_persistent_connection': persistent, 'adb_idle_timeout': 5}


class AdbTestCase(unittest.IsolatedAsyncioTestCase):
    heartbeatInterval = 3600

    async def asyncSetUp(self):
        FakeAdb.reset()
        self.signers = iter(f'key{i}' for i in range(1, 100))
        quick = 0.01
        for patcher in (
            mock.patch.object(tvremoted, 'AdbDeviceTcpAsync', FakeAdb),
            mock.patch.object(tvremoted, 'load_adb_signer', lambda config: next(self.signers)),
            mock.patch.object(tvremoted.TVRemoted, 'ensure_adb_keys', mock.AsyncMock(return_value=False)),
            mock.patch.object(Config, 'adb_key_file', new_callable=mock.PropertyMock, return_value=__file__),  # fichier existant
            mock.patch.object(Config, 'adb_start_delay', new_callable=mock.PropertyMock, return_value=0),
            mock.patch.object(Config, 'adb_loop_interval', new_callable=mock.PropertyMock, return_value=quick),
            mock.patch.object(Config, 'reconnect_delay_min', new_callable=mock.PropertyMock, return_value=quick),
            mock.patch.object(Config, 'reconnect_delay_max', new_callable=mock.PropertyMock, return_value=quick),
            mock.patch.object(Config, 'adb_heartbeat_interval', new_callable=mock.PropertyMock, return_value=self.heartbeatInterval),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.config = newConfig()
        self.daemon = tvremoted.TVRemoted(self.config)
        self.publisher = FakePublisher()
        self.daemon._jeedom_publisher = self.publisher

    async def asyncTearDown(self):
        for mac in list(self.config.remote_devices_adb):
            await self.daemon._remove_remote_adb(mac)

    def device(self):
        return self.config.remote_devices_adb.get(MAC)

    async def addAdb(self, **kwargs):
        await self.daemon._on_socket_message(addAdbMessage(**kwargs))
        return self.device()

    def commandErrors(self):
        return [sent for sent in self.publisher.sent if 'adb_shell_error' in sent]


class ConnectionTest(AdbTestCase):
    async def testPersistentDeviceConnects(self):
        device = await self.addAdb(persistent=1)
        self.assertTrue(await waitUntil(lambda: device._connected))
        self.assertIn(1, [change.get('adb_connected') for change in self.publisher.changesFor(MAC)])

    async def testRemovalDuringAConnectionAttemptCompletes(self):
        """ Annulation de la boucle pendant une tentative : elle ne doit pas être absorbée (retrait qui ne finirait jamais,
        en bloquant tous les ajouts et retraits suivants) """
        FakeAdb.reset([asyncio.Event()])  # tentative qui ne se termine pas d'elle-même
        device = await self.addAdb(persistent=1)
        self.assertTrue(await waitUntil(lambda: FakeAdb.totalConnectCalls() == 1))
        removal = {'apikey': API_KEY, 'cmd': 'removetvremote_adb', 'mac': MAC, 'host': HOST, 'friendly_name': 'Salon'}
        await asyncio.wait_for(self.daemon._on_socket_message(removal), timeout=2)
        self.assertIsNone(self.device())
        self.assertFalse(device.is_running)

    async def testOnDemandFailureKeepsTheLoopRunning(self):
        """ Échec d'une connexion à la demande (TV éteinte) : erreur rendue à la commande, la boucle continue sans retenter
        en arrière-plan (aucune commande n'attend), la commande suivante se reconnecte """
        FakeAdb.reset([OSError('unreachable')])
        device = await self.addAdb(persistent=0)
        await device.send_command('shell', 'ls', '12')
        self.assertEqual(self.commandErrors(), [{'adb_shell_output_mac': MAC, 'adb_shell_output_cmd_id': '12', 'adb_shell_error': 'Failed to connect'}])
        await asyncio.sleep(0.1)  # plusieurs tours de boucle
        self.assertTrue(device.is_running)
        self.assertEqual(FakeAdb.totalConnectCalls(), 1)
        await device.send_command('shell', 'ls', '13')
        self.assertTrue(device._connected)
        self.assertEqual(FakeAdb.instances[0].commands, ['ls'])

    async def testUnansweredTvIsAWarningNotAnError(self):
        """ TV éteinte qui ignore les paquets : délai TCP dépassé (TcpTimeoutException d'adb_shell), traité comme une TV injoignable.
        Une erreur à chaque tentative déclencherait les alertes Jeedom pour une situation normale """
        FakeAdb.reset([TcpTimeoutException('Connecting to 192.168.1.10:5555 timed out (20 seconds)')] * 2)
        with self.assertLogs(tvremoted.__name__, 'DEBUG') as logs:
            device = await self.addAdb(persistent=1)
            self.assertTrue(await waitUntil(lambda: device._connected))
        self.assertEqual(len([line for line in logs.output if line.startswith('WARNING') and 'Device unreachable' in line]), 2)
        self.assertFalse([line for line in logs.output if line.startswith('ERROR')])

    async def testAdbFailureNeverReportsTheTvOffline(self):
        """ Un échec ADB ne prouve pas que la TV est hors ligne (ports ADB fermés, débogage désactivé) : seul « Connexion ADB » passe à 0 ;
        une connexion ADB réussie, elle, prouve que la TV est joignable """
        FakeAdb.reset([ConnectionRefusedError('refused')])
        device = await self.addAdb(persistent=1)
        self.assertTrue(await waitUntil(lambda: device._connected))
        changes = self.publisher.changesFor(MAC)
        self.assertNotIn(0, [change.get('online') for change in changes])
        self.assertEqual([change['adb_connected'] for change in changes], [0, 0, 1])
        self.assertEqual(changes[-1].get('online'), 1)

    async def testCommandSharesTheConnectionInProgress(self):
        """ Commande à la demande et boucle : une seule tentative de connexion, attendue par les deux """
        gate = asyncio.Event()
        FakeAdb.reset([gate])
        device = await self.addAdb(persistent=0)
        command = asyncio.create_task(device.send_command('shell', 'echo hello', None))
        await asyncio.sleep(0.1)  # plusieurs tours de boucle pendant la tentative
        gate.set()
        await asyncio.wait_for(command, timeout=2)
        self.assertEqual(FakeAdb.totalConnectCalls(), 1)
        self.assertIn('echo hello', FakeAdb.instances[0].commands)
        self.assertEqual(self.commandErrors(), [])

    async def testCommandDuringTheStartDelayUsesTheDeviceConnection(self):
        """ Commande reçue pendant la pause de démarrage : sa connexion (clé chargée pour elle) est gardée par la boucle """
        with mock.patch.object(Config, 'adb_start_delay', new_callable=mock.PropertyMock, return_value=0.2):
            device = await self.addAdb(persistent=0)
            await device.send_command('shell', 'echo first', '1')
            self.assertTrue(await waitUntil(lambda: FakeAdb.totalConnectCalls() == 1 and device._signer is not None))
            await asyncio.sleep(0.3)  # fin de la pause : la boucle démarre
            await device.send_command('shell', 'echo second', '2')
        self.assertEqual(len(FakeAdb.instances), 1)
        self.assertEqual(FakeAdb.instances[0].commands, ['echo first', 'echo second'])
        self.assertEqual(FakeAdb.instances[0].signers, ['key1'])
        self.assertEqual(self.commandErrors(), [])

    async def testCommandWhenNotConnectedInPersistentMode(self):
        FakeAdb.reset([asyncio.Event()])
        device = await self.addAdb(persistent=1)
        self.assertTrue(await waitUntil(lambda: FakeAdb.totalConnectCalls() == 1))
        await device.send_command('shell', 'ls', '7')
        self.assertEqual(self.commandErrors()[0]['adb_shell_error'], 'Device not connected (ADB)')


class UnexpectedErrorTest(AdbTestCase):
    heartbeatInterval = 0  # heartbeat à chaque tour

    async def testUnexpectedErrorKeepsTheLoopRunning(self):
        device = await self.addAdb(persistent=1)
        self.assertTrue(await waitUntil(lambda: device._connected))
        with self.assertLogs(tvremoted.__name__, 'ERROR') as logs:
            FakeAdb.shellError = RuntimeError('unexpected')
            self.assertTrue(await waitUntil(lambda: FakeAdb.totalConnectCalls() >= 2 and device._connected))
        self.assertTrue([line for line in logs.output if 'Unexpected exception' in line])
        self.assertTrue(device.is_running)


class PairingTest(AdbTestCase):
    def pairingMessages(self):
        return [sent for sent in self.publisher.sent if 'adb_paired' in sent or 'adb_pairing_failed' in sent]

    async def testSuccessRestartsTheDeviceWithTheCurrentKey(self):
        """ La clé a pu être régénérée pour l'appairage : l'appareil est recréé et relit la clé, réglages repris """
        old = await self.addAdb(persistent=1, paired=0)
        self.assertTrue(await waitUntil(lambda: old._signer is not None))
        await self.daemon._pairing_adb(MAC, HOST)
        new = self.device()
        self.assertIsNot(new, old)
        self.assertFalse(old.is_running)
        self.assertEqual((new._adb_paired, new._persistent_connection), (1, True))
        self.assertTrue(await waitUntil(lambda: new._connected))
        self.assertEqual(new._signer, 'key3')  # key1 : ancien appareil, key2 : appairage, key3 : appareil recréé
        self.assertEqual(self.pairingMessages(), [{'mac': MAC, 'adb_paired': 1, 'message': 'ADB pairing successful'}])

    async def testPairingAlreadyInProgressKeepsTheStatus(self):
        device = await self.addAdb(paired=1)
        device.set_pairing_mode(True)
        await self.daemon._pairing_adb(MAC, HOST)
        self.assertEqual(self.pairingMessages(), [{'mac': MAC, 'adb_pairing_failed': 1, 'message': 'Pairing already in progress'}])
        self.assertIs(self.device(), device)
        self.assertEqual(device._adb_paired, 1)

    async def testUnreachableTvKeepsThePairingStatus(self):
        """ TV injoignable pendant l'appairage : aucune conclusion sur l'appairage, la clé reste autorisée sur la TV """
        device = await self.addAdb(persistent=0, paired=1)  # à la demande, sans activité : la boucle ne se connecte pas
        FakeAdb.reset([OSError('unreachable')])
        await self.daemon._pairing_adb(MAC, HOST)
        messages = self.pairingMessages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['adb_pairing_failed'], 1)
        self.assertNotIn('adb_paired', messages[0])
        self.assertIs(self.device(), device)
        self.assertEqual(device._adb_paired, 1)
        self.assertFalse(device._pairing_mode)

    async def testRefusalOnTheTvResetsThePairingStatus(self):
        await self.addAdb(persistent=0, paired=1)
        FakeAdb.reset([DeviceAuthError('refused')])
        await self.daemon._pairing_adb(MAC, HOST)
        self.assertEqual([message['adb_paired'] for message in self.pairingMessages()], [0])
        self.assertFalse(self.device()._pairing_mode)

    async def testPairingCancelsTheConnectionInProgress(self):
        """ Une tentative de la boucle en cours est annulée par l'appairage, sans être signalée comme une erreur de connexion """
        FakeAdb.reset([asyncio.Event()])
        device = await self.addAdb(persistent=1, paired=1)
        self.assertTrue(await waitUntil(lambda: FakeAdb.totalConnectCalls() == 1))
        with self.assertNoLogs(tvremoted.__name__, 'WARNING'):
            await self.daemon._pairing_adb(MAC, HOST)
        self.assertIsNot(self.device(), device)
        self.assertEqual(self.pairingMessages(), [{'mac': MAC, 'adb_paired': 1, 'message': 'ADB pairing successful'}])


if __name__ == '__main__':
    unittest.main()
