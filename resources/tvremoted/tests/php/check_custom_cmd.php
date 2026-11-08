<?php
// Vrai tvremote::customCmdDecoder : action, valeur et options d'une commande personnalisée. Lancé par test_phpChecks.py.
require __DIR__ . '/bootstrap.php';

check(tvremote::customCmdDecoder('"action":"keycode","value":"KEYCODE_HOME"') === ['keycode', ['message' => 'KEYCODE_HOME']], 'action et valeur');
check(tvremote::customCmdDecoder('"action":"home"') === ['home', []], 'action sans valeur');
check(tvremote::customCmdDecoder('"action":"shell","value":"ls","protocol":"adb"') === ['shell', ['message' => 'ls', 'title' => '"protocol":"adb"']], 'protocole passé en option');

// Saisie invalide : refusée (warning), sans erreur fatale
log::$lines = [];
check(tvremote::customCmdDecoder('action:keycode') === null, 'JSON invalide refusé');
check(log::linesOf('error') === [] && count(log::linesOf('warning')) === 1, 'refus en warning');
check(tvremote::customCmdDecoder('"action":"keycode",') === null, 'JSON incomplet refusé');
echo 'OK' . PHP_EOL;
