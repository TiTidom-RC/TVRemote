""" Power On/Off et Mute On/Off : la touche bascule l'état, elle n'est donc pas envoyée quand la TV est déjà dans l'état demandé.
État connu par la connexion Google TV (seulement si elle est établie) ; en ADB, Power est décidé par la TV elle-même.
Fausses TV (FakeRemote, FakeAdb), aucun réseau.
Lancement depuis resources/tvremoted :  python -m unittest discover -s tests -t . """

import asyncio
import unittest
from unittest import mock

import tvremoted
from config import Config
from tests.helpers import API_KEY, FakeAdb, FakePublisher, FakeRemote, newConfig, waitUntil

MAC = 'AA:BB:CC:DD:EE:FF'
HOST = '192.168.1.10'


def action(name, protocol=None, value=None):
    return {'apikey': API_KEY, 'cmd': 'action', 'cmd_action': name, 'mac': MAC, 'value': value,
            'options': f'"protocol":"{protocol}"' if protocol else None}


class PowerMuteTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        FakeRemote.reset()
        FakeAdb.reset()
        quick = 0.01
        for patcher in (
            mock.patch.object(tvremoted, 'AndroidTVRemote', FakeRemote),
            mock.patch.object(tvremoted, 'AdbDeviceTcpAsync', FakeAdb),
            mock.patch.object(tvremoted, 'load_adb_signer', lambda config: 'key'),
            mock.patch.object(tvremoted.TVRemoted, 'ensure_adb_keys', mock.AsyncMock(return_value=False)),
            mock.patch.object(Config, 'adb_key_file', new_callable=mock.PropertyMock, return_value=__file__),  # fichier existant
            mock.patch.object(Config, 'adb_start_delay', new_callable=mock.PropertyMock, return_value=0),
            mock.patch.object(Config, 'adb_loop_interval', new_callable=mock.PropertyMock, return_value=quick),
            mock.patch.object(Config, 'reconnect_delay_min', new_callable=mock.PropertyMock, return_value=quick),
            mock.patch.object(Config, 'reconnect_delay_max', new_callable=mock.PropertyMock, return_value=quick),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.config = newConfig()
        self.daemon = tvremoted.TVRemoted(self.config)
        self.daemon._jeedom_publisher = FakePublisher()

    async def asyncTearDown(self):
        for mac in list(self.config.remote_devices):
            await self.daemon._remove_remote(mac)
        for mac in list(self.config.remote_devices_adb):
            await self.daemon._remove_remote_adb(mac)

    async def send(self, message):
        await self.daemon._on_socket_message(message)

    async def addGoogleTv(self, is_on=None, volume_info=None):
        """ Appareil Google TV connecté, dans l'état donné (None : inconnu) """
        await self.send({'apikey': API_KEY, 'cmd': 'addtvremote', 'mac': MAC, 'host': HOST, 'port': 6466, 'friendly_name': 'Salon'})
        self.assertTrue(await waitUntil(lambda: self.config.remote_devices[MAC]._remote is not None and self.config.remote_devices[MAC]._remote.connected))
        remote = self.config.remote_devices[MAC]._remote
        remote.is_on = is_on
        remote.volume_info = volume_info
        return remote

    async def addAdb(self):
        await self.send({'apikey': API_KEY, 'cmd': 'addtvremote_adb', 'mac': MAC, 'host': HOST, 'friendly_name': 'Salon',
                         'adb_paired': 1, 'adb_persistent_connection': 0, 'adb_idle_timeout': 5})


class GoogleTvPowerTest(PowerMuteTestCase):
    async def testPowerOnIgnoredWhenTheTvIsOn(self):
        remote = await self.addGoogleTv(is_on=True)
        with self.assertLogs(tvremoted.__name__, 'INFO') as logs:
            await self.send(action('power_on'))
        self.assertEqual(remote.keys, [])
        self.assertTrue([line for line in logs.output if 'already in the requested state' in line])

    async def testPowerOffSentWhenTheTvIsOn(self):
        remote = await self.addGoogleTv(is_on=True)
        await self.send(action('power_off'))
        self.assertEqual(remote.keys, ['KEYCODE_POWER'])

    async def testPowerOnSentWhenTheTvIsOff(self):
        remote = await self.addGoogleTv(is_on=False)
        await self.send(action('power_on'))
        self.assertEqual(remote.keys, ['KEYCODE_POWER'])

    async def testPowerOffIgnoredWhenTheTvIsOff(self):
        remote = await self.addGoogleTv(is_on=False)
        await self.send(action('power_off'))
        self.assertEqual(remote.keys, [])

    async def testUnknownStateSendsTheKey(self):
        remote = await self.addGoogleTv(is_on=None)
        await self.send(action('power_on'))
        self.assertEqual(remote.keys, ['KEYCODE_POWER'])

    async def testStateIsNotTrustedWhileTheConnectionIsLost(self):
        """ Connexion perdue : l'état n'est plus poussé par la TV, il peut être périmé ; la touche est envoyée comme avant """
        remote = await self.addGoogleTv(is_on=True)
        remote.callbacks['is_available'](False)
        await self.send(action('power_on'))
        self.assertEqual(remote.keys, ['KEYCODE_POWER'])
        remote.callbacks['is_available'](True)
        await self.send(action('power_on'))
        self.assertEqual(remote.keys, ['KEYCODE_POWER'])  # connexion revenue : état de nouveau utilisé

    async def testRawPowerKeyIsAlwaysSent(self):
        """ La commande Key Code reste une bascule brute """
        remote = await self.addGoogleTv(is_on=True)
        await self.send(action('keycode', value='KEYCODE_POWER'))
        self.assertEqual(remote.keys, ['KEYCODE_POWER'])

    async def testOtherKeysAreNotConcerned(self):
        remote = await self.addGoogleTv(is_on=True)
        await self.send(action('volumeup'))
        self.assertEqual(remote.keys, ['KEYCODE_VOLUME_UP'])


class GoogleTvMuteTest(PowerMuteTestCase):
    async def testMuteOnIgnoredWhenAlreadyMuted(self):
        remote = await self.addGoogleTv(is_on=True, volume_info={'level': 5, 'max': 100, 'muted': True})
        await self.send(action('mute_on'))
        self.assertEqual(remote.keys, [])

    async def testMuteOffSentWhenMuted(self):
        remote = await self.addGoogleTv(is_on=True, volume_info={'level': 5, 'max': 100, 'muted': True})
        await self.send(action('mute_off'))
        self.assertEqual(remote.keys, ['KEYCODE_VOLUME_MUTE'])

    async def testUnknownMuteStateSendsTheKey(self):
        remote = await self.addGoogleTv(is_on=True, volume_info=None)
        await self.send(action('mute_on'))
        self.assertEqual(remote.keys, ['KEYCODE_VOLUME_MUTE'])


class AdbPowerMuteTest(PowerMuteTestCase):
    async def runAdb(self, message):
        await self.send(message)
        await asyncio.sleep(0.05)
        return FakeAdb.allCommands()

    async def testAdbPowerLetsTheTvDecide(self):
        """ Sans état Google TV connu : la TV vérifie son écran au moment de la commande """
        await self.addAdb()
        self.assertEqual(await self.runAdb(action('power_on', 'adb')), [tvremoted.ADB_POWER_COMMANDS['power_on']])
        self.assertEqual((await self.runAdb(action('power_off', 'adb')))[-1:], [tvremoted.ADB_POWER_COMMANDS['power_off']])
        self.assertIn(" || input keyevent KEYCODE_POWER", tvremoted.ADB_POWER_COMMANDS['power_on'])
        self.assertIn(" && input keyevent KEYCODE_POWER", tvremoted.ADB_POWER_COMMANDS['power_off'])

    async def testAdbPowerIgnoredWhenGoogleTvKnowsTheState(self):
        await self.addGoogleTv(is_on=True)
        await self.addAdb()
        self.assertEqual(await self.runAdb(action('power_on', 'adb')), [])

    async def testAdbMuteUsesTheGoogleTvState(self):
        await self.addGoogleTv(is_on=True, volume_info={'level': 5, 'max': 100, 'muted': True})
        await self.addAdb()
        self.assertEqual(await self.runAdb(action('mute_on', 'adb')), [])
        self.assertEqual(await self.runAdb(action('mute_off', 'adb')), ['input keyevent KEYCODE_VOLUME_MUTE'])

    async def testAdbMuteWithoutGoogleTvTogglesAsBefore(self):
        await self.addAdb()
        self.assertEqual(await self.runAdb(action('mute_on', 'adb')), ['input keyevent KEYCODE_VOLUME_MUTE'])


if __name__ == '__main__':
    unittest.main()
