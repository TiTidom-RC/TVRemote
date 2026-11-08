""" Socle du démon : module importable sans démarrer, nom d'appairage, filtres de logs.
Lancement depuis resources/tvremoted :  python -m unittest discover -s tests -t . """

import logging
import unittest

import tvremoted
from tests.helpers import newConfig


class DaemonImportTest(unittest.TestCase):
    def testImportDoesNotStartTheDaemon(self):
        """ Importé, le module ne lit pas la ligne de commande et ne crée ni configuration ni démon """
        self.assertFalse(hasattr(tvremoted, 'config'))
        self.assertFalse(hasattr(tvremoted, 'daemon'))


class ClientNameTest(unittest.TestCase):
    def testAccentsAndSpacesAreReplaced(self):
        self.assertEqual(newConfig(jeedomname='Maison Élodie').client_name, 'Plugin TVRemote :: Maison_Elodie')

    def testEmptyNameFallsBackToJeedom(self):
        self.assertEqual(newConfig(jeedomname='  ').client_name, 'Plugin TVRemote :: Jeedom')


class PatternRemapFilterTest(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger('tests.remap')
        self.logger.setLevel(logging.INFO)
        self.addCleanup(self.logger.setLevel, logging.NOTSET)

    def record(self, message, level=logging.WARNING):
        return self.logger.makeRecord(self.logger.name, level, __file__, 0, message, (), None)

    def testDropRuleHidesTheMessage(self):
        remap = tvremoted.PatternRemapFilter([{'pattern': 'offline', 'level': 'drop'}])
        self.assertFalse(remap.filter(self.record('Cannot connect (device may be offline)')))

    def testMessageLoweredUnderTheLoggerLevelIsHidden(self):
        remap = tvremoted.PatternRemapFilter([{'pattern': 'offline', 'level': 'debug'}])
        self.assertFalse(remap.filter(self.record('Cannot connect (device may be offline)')))

    def testMessageRaisedIsKeptWithItsNewLevel(self):
        remap = tvremoted.PatternRemapFilter([{'pattern': 'Heartbeat', 'level': 'warning'}])
        record = self.record('[MAINLOOP] Heartbeat = 1', logging.INFO)
        self.assertTrue(remap.filter(record))
        self.assertEqual(record.levelname, 'WARNING')

    def testDisabledRuleIsIgnored(self):
        remap = tvremoted.PatternRemapFilter([{'pattern': 'offline', 'level': 'drop', 'enabled': False}])
        self.assertTrue(remap.filter(self.record('Cannot connect (device may be offline)')))


if __name__ == '__main__':
    unittest.main()
