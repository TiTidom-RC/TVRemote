""" Code PHP du plugin exécuté sans Jeedom, avec des classes du Core simulées (scripts de tests/php).
Ignorés si php n'est pas installé.
Lancement depuis resources/tvremoted :  python -m unittest discover -s tests -t . """

import os
import shutil
import subprocess
import unittest

PHP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'php')


@unittest.skipUnless(shutil.which('php'), 'php non installé')
class PhpChecksTest(unittest.TestCase):
    def assertScriptPasses(self, name):
        result = subprocess.run(['php', os.path.join(PHP_DIR, name)], capture_output=True, text=True, timeout=30, check=False)
        self.assertEqual((result.returncode, result.stdout.strip()), (0, 'OK'), result.stdout + result.stderr)

    def testCustomCommandDecoding(self):
        self.assertScriptPasses('check_custom_cmd.php')


if __name__ == '__main__':
    unittest.main()
