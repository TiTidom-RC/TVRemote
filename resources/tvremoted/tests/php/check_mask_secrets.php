<?php
// Vrai tvremote::maskSecrets, sur les exemples de mask_secrets_cases.json, partagés avec le test Python de maskSecrets.
// Lancé par test_phpChecks.py.
require __DIR__ . '/bootstrap.php';

$cases = json_decode(file_get_contents(__DIR__ . '/../mask_secrets_cases.json'), true);
check(is_array($cases) && count($cases['masked']) > 0, 'exemples lus');
foreach ($cases['masked'] as [$input, $expected]) {
    check(tvremote::maskSecrets($input) === $expected, 'masqué : ' . $input . ' => ' . tvremote::maskSecrets($input));
}
foreach ($cases['unchanged'] as $line) {
    check(tvremote::maskSecrets($line) === $line, 'inchangé : ' . $line . ' => ' . tvremote::maskSecrets($line));
}
echo 'OK' . PHP_EOL;
