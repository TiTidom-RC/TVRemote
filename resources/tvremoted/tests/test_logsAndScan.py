""" Logs : niveau « Aucun », clé API jamais écrite (messages du socket, filtre de masquage), message invalide sur le socket.
Scan : une TV en erreur n'interrompt pas le scan et n'est signalée qu'en warning, interrogations suivies jusqu'à la fin du scan.
Faux zeroconf et fausse TV, aucun réseau.
Lancement depuis resources/tvremoted :  python -m unittest discover -s tests -t . """

import asyncio
import json
import logging
import os
import sys
import unittest
from unittest import mock

from androidtvremote2 import CannotConnect
from zeroconf import ServiceStateChange

import tvremoted
from jeedom.aio_connector import Listener
from jeedom.utils import SECRET_MASK, SecretMaskFilter, Utils, maskSecrets
from tests.helpers import API_KEY, FakePublisher, FakeRemote, newConfig

SERVICE = '_androidtvremote2._tcp.local.'


class LogLevelTest(unittest.TestCase):
    def testNoneAndUnknownLevelsWriteNoDebug(self):
        """ « Aucun » dans Jeedom et niveau inconnu : critical seulement """
        for level in ('none', 'default', 'anything'):
            self.assertEqual(Utils.convert_log_level(level), logging.CRITICAL, level)

    def testJeedomLevels(self):
        self.assertEqual([Utils.convert_log_level(level) for level in ('debug', 'info', 'warning', 'error')],
                         [logging.DEBUG, logging.INFO, logging.WARNING, logging.ERROR])


class SecretMaskTest(unittest.TestCase):
    """ Exemples partagés avec le contrôle PHP de tvremote::maskSecrets (tests/php/check_mask_secrets.php) """

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mask_secrets_cases.json'), encoding='utf-8') as file:
            cls.cases = json.load(file)

    def record(self, message, args=()):
        return logging.LogRecord('tests.secrets', logging.INFO, __file__, 0, message, args, None)

    def testSharedCases(self):
        for text, expected in self.cases['masked']:
            self.assertEqual(maskSecrets(text), expected)
        for text in self.cases['unchanged']:
            self.assertEqual(maskSecrets(text), text)

    def testFilterMasksTheMessageAndItsArguments(self):
        record = self.record('Callback %s?apikey=%s', ('http://127.0.0.1/cb', API_KEY))
        self.assertTrue(SecretMaskFilter().filter(record))
        self.assertEqual(record.getMessage(), 'Callback http://127.0.0.1/cb?apikey=' + SECRET_MASK)

    def testFilterMasksTheExceptionText(self):
        try:
            raise OSError(f'GET http://127.0.0.1/cb?apikey={API_KEY} failed')
        except OSError:
            record = logging.LogRecord('tests.secrets', logging.ERROR, __file__, 0, 'Callback error', (), sys.exc_info())
        SecretMaskFilter().filter(record)
        self.assertNotIn(API_KEY, logging.Formatter().format(record))

    def testFilterLeavesOtherMessagesUnchanged(self):
        record = self.record('Heartbeat = %s', (1,))
        SecretMaskFilter().filter(record)
        self.assertEqual((record.msg, record.args), ('Heartbeat = %s', (1,)))

    def testMalformedMessageIsLeftToTheHandler(self):
        record = self.record('%s %s', (1,))
        self.assertTrue(SecretMaskFilter().filter(record))

    def testLoggerIsCreatedWithTheFilter(self):
        root = logging.getLogger()
        level = root.level
        self.addCleanup(root.setLevel, level)
        Utils.init_logger('error')
        filters = [f for handler in root.handlers for f in handler.filters if isinstance(f, SecretMaskFilter)]
        for handler in root.handlers:
            self.addCleanup(lambda h=handler: [h.removeFilter(f) for f in list(h.filters) if isinstance(f, SecretMaskFilter)])
        self.assertTrue(filters)


class FakeReader:
    def __init__(self, data: bytes):
        self.data = data

    async def read(self):
        return self.data


class FakeWriter:
    def get_extra_info(self, name):
        return ('127.0.0.1', 50000)

    def close(self):
        pass

    async def wait_closed(self):
        pass


class SocketMessageTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.received = []

        async def onMessage(message):
            self.received.append(message)
        self.listener = Listener('127.0.0.1', 0, onMessage)

    async def receive(self, data: bytes):
        await self.listener._handle_read(FakeReader(data), FakeWriter())

    async def testApiKeyIsNeverLogged(self):
        with self.assertLogs('jeedom.aio_connector', 'DEBUG') as logs:
            await self.receive(b'{"apikey": "' + API_KEY.encode() + b'", "cmd": "scanOn"}')
        self.assertEqual(self.received, [{'apikey': API_KEY, 'cmd': 'scanOn'}])
        self.assertFalse([line for line in logs.output if API_KEY in line])
        self.assertTrue([line for line in logs.output if 'scanOn' in line])

    async def testInvalidJsonIsAWarning(self):
        with self.assertLogs('jeedom.aio_connector', 'WARNING'):
            await self.receive(b'not json')
        self.assertEqual(self.received, [])

    async def testNonObjectJsonIsRejected(self):
        with self.assertLogs('jeedom.aio_connector', 'WARNING'):
            await self.receive(b'[1, 2]')
        self.assertEqual(self.received, [])

    async def testWrongApiKeyIsRejectedWithoutCopyingTheMessage(self):
        daemon = tvremoted.TVRemoted(newConfig())
        with self.assertLogs(tvremoted.__name__, 'ERROR') as logs:
            await daemon._on_socket_message({'apikey': 'wrongKey', 'cmd': 'scanOn'})
            await daemon._on_socket_message({'cmd': 'scanOn'})  # sans clé : refusé, sans exception
        self.assertEqual(len(logs.output), 2)
        self.assertFalse([line for line in logs.output if 'wrongKey' in line])
        self.assertFalse(daemon._config.scanmode)

    async def testNonAsciiApiKeyIsRejectedWithoutError(self):
        daemon = tvremoted.TVRemoted(newConfig())
        with self.assertLogs(tvremoted.__name__, 'ERROR') as logs:
            await daemon._on_socket_message({'apikey': 'clé-é', 'cmd': 'scanOn'})
        self.assertEqual(len(logs.output), 1)
        self.assertIn('Invalid apikey', logs.output[0])


class FakeServiceInfo:
    """ Remplace zeroconf AsyncServiceInfo : réponses par nom de service (dict `answers`, réglé par chaque test) """
    answers: dict = {}

    def __init__(self, service_type, name):
        self.type = service_type
        self.name = name
        self.answer = FakeServiceInfo.answers.get(name, {})
        self.port = 6466
        self.decoded_properties = {'bt': 'AA:BB'}

    async def async_request(self, zeroconf, timeout):
        found = self.answer.get('found', True)
        if isinstance(found, asyncio.Event):
            await found.wait()
            return True
        return found

    def get_name(self):
        return self.name.split('.')[0]

    def parsed_scoped_addresses(self):
        return self.answer.get('addresses', ['fe80::1', '192.168.1.10'])


class FakeZeroconf:
    def __init__(self):
        self.zeroconf = object()
        self.closed = False

    async def async_close(self):
        self.closed = True


class ScanTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        FakeRemote.reset()
        FakeServiceInfo.answers = {}
        self.found = []  # noms des TV annoncées par le faux navigateur zeroconf
        self.zeroconf = FakeZeroconf()
        found = self.found

        class FakeBrowser:
            def __init__(self, zeroconf, services, handlers):
                for name in found:
                    for handler in handlers:
                        handler(zeroconf=zeroconf, service_type=SERVICE, name=name, state_change=ServiceStateChange.Added)

            async def async_cancel(self):
                pass

        for patcher in (
            mock.patch.object(tvremoted, 'AndroidTVRemote', FakeRemote),
            mock.patch.object(tvremoted, 'AsyncServiceInfo', FakeServiceInfo),
            mock.patch.object(tvremoted, 'AsyncZeroconf', lambda: self.zeroconf),
            mock.patch.object(tvremoted, 'AsyncServiceBrowser', FakeBrowser),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.config = newConfig()
        self.config.scanmode = False  # le scan s'arrête aussitôt : seules les TV déjà annoncées sont interrogées
        self.daemon = tvremoted.TVRemoted(self.config)
        self.publisher = FakePublisher()
        self.daemon._jeedom_publisher = self.publisher

    def reported(self):
        return [value for key, value in self.publisher.changes if key.startswith('devices::')]

    async def testFoundTvIsReported(self):
        self.found.append('Salon.' + SERVICE)
        await self.daemon._tvhosts_from_zeroconf(timeout=1)
        reported = self.reported()
        self.assertEqual(len(reported), 1)
        self.assertEqual((reported[0]['host'], reported[0]['mac'], reported[0]['friendly_name']), ('192.168.1.10', FakeRemote.MAC, 'Salon'))
        self.assertTrue(self.zeroconf.closed)

    async def testUnreachableTvIsAWarningAndOtherTvsAreReported(self):
        """ Une TV qui ne répond pas ne concerne qu'elle : warning (pas d'exception perdue d'asyncio), les autres sont signalées """
        self.found.extend(['Chambre.' + SERVICE, 'Salon.' + SERVICE])
        FakeRemote.nameAndMacErrors = {'192.168.1.20': CannotConnect('unreachable')}
        FakeServiceInfo.answers = {'Chambre.' + SERVICE: {'addresses': ['192.168.1.20']}}
        with self.assertLogs(tvremoted.__name__, 'DEBUG') as logs:
            await self.daemon._tvhosts_from_zeroconf(timeout=1)
        self.assertEqual([tv['friendly_name'] for tv in self.reported()], ['Salon'])
        self.assertTrue([line for line in logs.output if line.startswith('WARNING') and 'Chambre' in line])
        self.assertFalse([line for line in logs.output if line.startswith('ERROR')])

    async def testTvWithoutIpv4IsIgnored(self):
        self.found.append('Salon.' + SERVICE)
        FakeServiceInfo.answers = {'Salon.' + SERVICE: {'addresses': ['fe80::1']}}
        with self.assertLogs(tvremoted.__name__, 'WARNING'):
            await self.daemon._tvhosts_from_zeroconf(timeout=1)
        self.assertEqual(self.reported(), [])
        self.assertEqual(FakeRemote.instances, [])  # aucune connexion vers 0.0.0.0

    async def testUnansweredServiceIsIgnored(self):
        self.found.append('Salon.' + SERVICE)
        FakeServiceInfo.answers = {'Salon.' + SERVICE: {'found': False}}
        await self.daemon._tvhosts_from_zeroconf(timeout=1)
        self.assertEqual(self.reported(), [])

    async def testDaemonStopDuringAScanDoesNotWaitForPendingReadings(self):
        """ Arrêt du démon pendant un scan : les interrogations en cours sont abandonnées tout de suite (Jeedom n'attend que 3 s) """
        self.config.scanmode = True
        self.found.append('Salon.' + SERVICE)
        FakeServiceInfo.answers = {'Salon.' + SERVICE: {'found': asyncio.Event()}}  # ne répond jamais
        scan = asyncio.create_task(self.daemon._tvhosts_from_zeroconf(timeout=60))
        await asyncio.sleep(0.05)
        scan.cancel()
        loop = asyncio.get_running_loop()
        start = loop.time()
        with self.assertRaises(asyncio.CancelledError):
            await scan
        self.assertLess(loop.time() - start, 1)
        self.assertTrue(self.zeroconf.closed)

    async def testReadingStillInProgressIsStoppedAtTheEndOfTheScan(self):
        self.found.append('Salon.' + SERVICE)
        FakeServiceInfo.answers = {'Salon.' + SERVICE: {'found': asyncio.Event()}}  # ne répond jamais
        with mock.patch.object(tvremoted.TVRemoted, 'SCAN_PENDING_TIMEOUT', 0.05):
            await asyncio.wait_for(self.daemon._tvhosts_from_zeroconf(timeout=1), timeout=2)
        self.assertEqual(self.reported(), [])
        self.assertTrue(self.zeroconf.closed)


if __name__ == '__main__':
    unittest.main()
