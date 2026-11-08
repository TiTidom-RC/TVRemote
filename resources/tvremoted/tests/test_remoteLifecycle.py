""" Cycle de vie des appareils dans le démon : ajout, modification (IP, IME), retrait, TV non appairée ou injoignable,
volume inconnu, appairage. Fausse TV (FakeRemote), aucun réseau.
Lancement depuis resources/tvremoted :  python -m unittest discover -s tests -t . """

import asyncio
import unittest
from unittest import mock

from androidtvremote2 import CannotConnect, InvalidAuth

import tvremoted
from config import Config
from tests.helpers import API_KEY, FakePublisher, FakeRemote, newConfig, waitUntil

MAC = 'AA:BB:CC:DD:EE:FF'


def addMessage(host='192.168.1.10', enable_ime=1):
    return {'apikey': API_KEY, 'cmd': 'addtvremote', 'mac': MAC, 'host': host, 'port': 6466, 'friendly_name': 'Salon', 'enable_ime': enable_ime}


def addAdbMessage(host='192.168.1.10', paired=1):
    return {'apikey': API_KEY, 'cmd': 'addtvremote_adb', 'mac': MAC, 'host': host, 'friendly_name': 'Salon', 'adb_paired': paired, 'adb_persistent_connection': 0, 'adb_idle_timeout': 5}


class DaemonTestCase(unittest.IsolatedAsyncioTestCase):
    reconnectDelay = 0.01

    async def asyncSetUp(self):
        FakeRemote.reset()
        for patcher in (
            mock.patch.object(tvremoted, 'AndroidTVRemote', FakeRemote),
            mock.patch.object(Config, 'reconnect_delay_min', new_callable=mock.PropertyMock, return_value=self.reconnectDelay),
            mock.patch.object(Config, 'reconnect_delay_max', new_callable=mock.PropertyMock, return_value=self.reconnectDelay),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.config = newConfig()
        self.daemon = tvremoted.TVRemoted(self.config)
        self.publisher = FakePublisher()
        self.daemon._jeedom_publisher = self.publisher

    async def asyncTearDown(self):
        for mac in list(self.config.remote_devices):
            await self.daemon._remove_remote(mac)
        for mac in list(self.config.remote_devices_adb):
            await self.daemon._remove_remote_adb(mac)

    async def send(self, message):
        await self.daemon._on_socket_message(message)

    def device(self):
        return self.config.remote_devices.get(MAC)

    async def addConnected(self, **kwargs):
        await self.send(addMessage(**kwargs))
        self.assertTrue(await waitUntil(lambda: self.device()._remote is not None and self.device()._remote.connected))
        return self.device()


class AddChangeRemoveTest(DaemonTestCase):
    async def testAddCreatesAndConnects(self):
        device = await self.addConnected()
        self.assertEqual(device._remote.host, '192.168.1.10')

    async def testAddUnchangedKeepsTheConnection(self):
        """ Chaque enregistrement de l'équipement renvoie l'ajout : la connexion en place ne doit pas être coupée """
        device = await self.addConnected()
        await self.send(addMessage())
        self.assertIs(self.device(), device)
        self.assertEqual(len(FakeRemote.instances), 1)
        self.assertFalse(device._remote.disconnected)

    async def testHostChangeRestartsTheDevice(self):
        old = await self.addConnected()
        oldRemote = old._remote
        new = await self.addConnected(host='192.168.1.20')
        self.assertIsNot(new, old)
        self.assertTrue(oldRemote.disconnected)
        self.assertEqual(new._remote.host, '192.168.1.20')

    async def testImeChangeRestartsTheDevice(self):
        old = await self.addConnected()
        oldRemote = old._remote
        new = await self.addConnected(enable_ime=0)
        self.assertTrue(oldRemote.disconnected)
        self.assertFalse(new._remote.enable_ime)

    async def testRemoveDisconnects(self):
        device = await self.addConnected()
        remote = device._remote
        await self.send({'apikey': API_KEY, 'cmd': 'removetvremote', 'mac': MAC, 'host': '192.168.1.10', 'port': 6466, 'friendly_name': 'Salon'})
        self.assertIsNone(self.device())
        self.assertTrue(remote.disconnected)
        self.assertTrue(device._main_task is None or device._main_task.done())

    async def testRemoveWhileRetryingStopsTheAttempts(self):
        FakeRemote.reset([CannotConnect()] * 1000)
        await self.send(addMessage())
        remote = await waitUntil(lambda: FakeRemote.instances and FakeRemote.instances[0].connectCalls >= 2) and FakeRemote.instances[0]
        self.assertTrue(remote)
        await self.daemon._remove_remote(MAC)
        calls = remote.connectCalls
        await asyncio.sleep(0.1)
        self.assertEqual(remote.connectCalls, calls)
        self.assertTrue(remote.disconnected)


class ConnectionFailureTest(DaemonTestCase):
    async def testNotPairedIsReportedOnce(self):
        FakeRemote.reset([InvalidAuth()] * 3)
        with self.assertLogs(tvremoted.__name__, 'DEBUG') as logs:
            await self.addConnected()
        self.assertEqual(len([sent for sent in self.publisher.sent if 'PairingExc' in sent]), 1)
        warnings = [line for line in logs.output if line.startswith('WARNING') and 'Not Paired' in line]
        self.assertEqual(len(warnings), 1)
        self.assertFalse([line for line in logs.output if line.startswith('ERROR')])

    async def testUnreachableTvIsReportedOfflineOnce(self):
        FakeRemote.reset([CannotConnect()] * 3)
        await self.addConnected()
        self.assertTrue(await waitUntil(lambda: len(self.publisher.changesFor(MAC)) >= 2))
        onlineValues = [change['online'] for change in self.publisher.changesFor(MAC) if 'online' in change]
        self.assertEqual(onlineValues, [0, 1])

    async def testNotificationsStartAgainAfterAConnection(self):
        FakeRemote.reset([CannotConnect()])
        device = await self.addConnected()
        self.assertFalse(device._unreachableNotified)
        self.assertFalse(device._notPairedNotified)


class RobustnessTest(DaemonTestCase):
    def pairingReports(self):
        return [sent for sent in self.publisher.sent if 'PairingExc' in sent]

    async def testJeedomUnreachableDoesNotStopTheDevice(self):
        """ L'envoi de l'état « non appairée » échoue (Jeedom injoignable) : l'appareil continue, et l'envoi est retenté """
        self.publisher.failures = 1
        FakeRemote.reset([InvalidAuth()] * 2)
        device = await self.addConnected()
        self.assertTrue(device.is_running)
        self.assertEqual(len(self.pairingReports()), 1)

    async def testPairingLostWhileConnectedIsReportedAndRetried(self):
        """ Reconnexion de la bibliothèque refusée faute d'appairage (elle ne réessaie plus) : signalé à Jeedom, et la boucle du plugin reprend """
        device = await self.addConnected()
        remote = device._remote
        remote.losePairing([InvalidAuth()])
        self.assertTrue(await waitUntil(lambda: remote.connected and remote.connectCalls == 3))
        self.assertEqual(len(self.pairingReports()), 1)
        self.assertTrue(device.is_running)

    async def testStoppedDeviceIsRestartedOnTheNextAdd(self):
        FakeRemote.certError = RuntimeError('certificate error')
        await self.send(addMessage())
        self.assertTrue(await waitUntil(lambda: not self.device().is_running))
        FakeRemote.certError = None
        device = await self.addConnected()
        self.assertTrue(device.is_running)
        self.assertEqual(len(FakeRemote.instances), 2)

    async def testSimultaneousAddsKeepASingleDevice(self):
        await self.addConnected()
        await asyncio.gather(self.send(addMessage(host='192.168.1.20')), self.send(addMessage(host='192.168.1.20')))
        self.assertTrue(await waitUntil(lambda: self.device()._remote is not None and self.device()._remote.connected))
        self.assertEqual([remote.host for remote in FakeRemote.running()], ['192.168.1.20'])

    async def testWakeUpDuringAConnectionDoesNotShortenALaterWaiting(self):
        FakeRemote.connectGate = asyncio.Event()
        await self.send(addMessage())
        self.assertTrue(await waitUntil(lambda: FakeRemote.instances and FakeRemote.instances[0].connectCalls == 1))
        self.device().wake_up()
        FakeRemote.connectGate.set()
        self.assertTrue(await waitUntil(lambda: FakeRemote.instances[0].connected))
        self.assertFalse(self.device()._wakeup.is_set())

    async def testDaemonCancellationIsNotSwallowedWhileStoppingADevice(self):
        device = await self.addConnected()
        stopping = asyncio.create_task(self.daemon._stop_device_task(device))
        await asyncio.sleep(0)
        stopping.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await stopping

    async def testInvalidImeValueUsesTheDefault(self):
        with self.assertLogs(tvremoted.__name__, 'WARNING') as logs:
            device = await self.addConnected(enable_ime='')
        self.assertTrue(device.enable_ime)
        self.assertTrue([line for line in logs.output if 'enable_ime' in line])


class VolumeTest(DaemonTestCase):
    async def testUnknownVolumeIsNotSent(self):
        """ TV en veille à la connexion : pas d'infos de volume, la dernière valeur connue dans Jeedom ne doit pas être écrasée par 0 """
        await self.addConnected()
        self.assertTrue(await waitUntil(lambda: self.publisher.changesFor(MAC)))
        first = self.publisher.changesFor(MAC)[0]
        self.assertEqual(first['online'], 1)
        self.assertFalse({'volume_level', 'volume_muted', 'volume_max'} & set(first))

    async def testKnownVolumeIsSent(self):
        FakeRemote.initialVolume = {'level': 12, 'muted': True, 'max': 100}
        await self.addConnected()
        self.assertTrue(await waitUntil(lambda: self.publisher.changesFor(MAC)))
        first = self.publisher.changesFor(MAC)[0]
        self.assertEqual((first['volume_level'], first['volume_muted'], first['volume_max']), (12, 1, 100))

    async def testIncompleteVolumeNotificationIsIgnored(self):
        device = await self.addConnected()
        self.assertTrue(await waitUntil(lambda: self.publisher.changesFor(MAC)))
        count = len(self.publisher.changesFor(MAC))
        device._remote.callbacks['volume_info']({'level': 5})
        await asyncio.sleep(0.05)
        self.assertEqual(len(self.publisher.changesFor(MAC)), count)


class PairingTest(DaemonTestCase):
    reconnectDelay = 30  # une attente de reconnexion qui ne finirait pas pendant le test

    async def testWakeUpInterruptsTheWaiting(self):
        FakeRemote.reset([InvalidAuth()])
        await self.send(addMessage())
        self.assertTrue(await waitUntil(lambda: FakeRemote.instances and FakeRemote.instances[0].connectCalls == 1))
        self.device().wake_up()
        self.assertTrue(await waitUntil(lambda: FakeRemote.instances[0].connected, timeout=1))

    async def testSuccessfulPairingIsReportedAndConnectsTheDevice(self):
        """ async_finish_pairing ne renvoie rien : une fin sans exception est un succès """
        FakeRemote.reset([InvalidAuth()])
        await self.send(addMessage())
        self.assertTrue(await waitUntil(lambda: FakeRemote.instances and FakeRemote.instances[0].connectCalls == 1))
        self.config.pairing_code = None
        pairing = asyncio.create_task(self.daemon._pairing(MAC, '192.168.1.10', 6466))
        await asyncio.sleep(0.05)
        self.config.pairing_code = '1234'
        await asyncio.wait_for(pairing, timeout=3)
        self.assertIn({'mac': MAC, 'tvremote_paired': 1, 'message': 'TVRemote pairing successful'}, self.publisher.sent)
        self.assertEqual(FakeRemote.instances[-1].pairingCodes, ['1234'])
        self.assertTrue(await waitUntil(lambda: FakeRemote.instances[0].connected, timeout=1))


class AdbAddChangeTest(DaemonTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()

        self.runningAdb = set()

        async def idleMain(device):
            self.runningAdb.add(device)
            try:
                await asyncio.Event().wait()
            finally:
                self.runningAdb.discard(device)
        for patcher in (
            mock.patch.object(tvremoted.EQRemoteADB, 'main', idleMain),
            mock.patch.object(tvremoted.TVRemoted, 'ensure_adb_keys', mock.AsyncMock(return_value=False)),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def adbDevice(self):
        return self.config.remote_devices_adb.get(MAC)

    async def testUnchangedHostUpdatesInPlace(self):
        await self.send(addAdbMessage(paired=0))
        device = self.adbDevice()
        await self.send(addAdbMessage(paired=1))
        self.assertIs(self.adbDevice(), device)
        self.assertEqual(device._adb_paired, 1)

    async def testEmptyIdleTimeoutUsesTheDefault(self):
        """ Champ « délai d'inactivité » vidé dans l'équipement : l'appareil est quand même ajouté, avec le délai par défaut """
        message = addAdbMessage()
        message['adb_idle_timeout'] = ''
        await self.send(message)
        self.assertEqual(self.adbDevice()._idle_timeout_minutes, self.config.adb_idle_timeout_default)

    async def testStoppedDeviceIsRestartedOnTheNextAdd(self):
        await self.send(addAdbMessage())
        old = self.adbDevice()
        old._main_task.cancel()
        self.assertTrue(await waitUntil(lambda: not old.is_running))
        await self.send(addAdbMessage())
        self.assertIsNot(self.adbDevice(), old)
        self.assertTrue(self.adbDevice().is_running)

    async def testSimultaneousAddsKeepASingleDevice(self):
        """ Le retrait ADB attend aussi la fermeture de la connexion : un second ajout pendant cette attente ne doit pas laisser d'appareil orphelin """
        await self.send(addAdbMessage())
        self.assertTrue(await waitUntil(lambda: len(self.runningAdb) == 1))
        await asyncio.gather(self.send(addAdbMessage(host='192.168.1.20')), self.send(addAdbMessage(host='192.168.1.20')))
        self.assertTrue(await waitUntil(lambda: len(self.runningAdb) == 1 and next(iter(self.runningAdb)).host == '192.168.1.20'))
        self.assertIs(next(iter(self.runningAdb)), self.adbDevice())

    async def testHostChangeRestartsTheDevice(self):
        await self.send(addAdbMessage())
        old = self.adbDevice()
        await self.send(addAdbMessage(host='192.168.1.20'))
        new = self.adbDevice()
        self.assertIsNot(new, old)
        self.assertEqual(new.host, '192.168.1.20')
        self.assertTrue(old._main_task is None or old._main_task.done())
        self.assertEqual(new._adb_paired, 1)


if __name__ == '__main__':
    unittest.main()
