<?php
// Vrai tvremote::onDaemonMessage (callback jeetvremote.php) avec des équipements simulés. Lancé par test_phpChecks.py.
require __DIR__ . '/bootstrap.php';

const MAC = 'AA:BB:CC:DD:EE:FF';

function newSalon($config = []) {
    $salon = new fakeTv('Salon', $config + ['friendly_name' => 'Salon', 'host' => '192.168.1.10', 'tvremote_paired_status' => 1, 'adb_paired_status' => 1]);
    foreach (['online', 'is_on', 'adb_shell_output'] as $logicalId) {
        $salon->cmds[$logicalId] = new fakeCmd($logicalId);
    }
    eqLogic::$byLogicalId[MAC] = $salon;
    return $salon;
}

// Découverte (devices) et temps réel (devicesRT) dans le même envoi groupé : les deux sont traités
resetCore();
$salon = newSalon();
tvremote::onDaemonMessage([
    'devices' => ['Salon._androidtvremote2._tcp.local.' => ['name' => 'Salon._androidtvremote2._tcp.local.', 'family' => 'Sony', 'mac' => MAC,
        'friendly_name' => 'Salon', 'lastscan' => '08/11/2026 - 12:00:00', 'type' => '_androidtvremote2._tcp.local.', 'host' => '192.168.1.20', 'port' => 6466, 'scanmode' => 1]],
    'devicesRT' => [MAC => ['mac' => MAC, 'online' => 1, 'is_on' => 1, 'realtime' => 1]],
]);
check($salon->config['host'] === '192.168.1.20', 'devices traité');
check($salon->cmds['is_on']->events === [1], 'devicesRT traité dans le même envoi');
check(log::linesOf('error') === [], 'aucune erreur (devices + devicesRT)');

// Une erreur sur un équipement temps réel ne concerne que lui
class brokenTv extends fakeTv {
    public function getCmd($type = null, $logicalId = null) { throw new Exception('broken'); }
}
resetCore();
$salon = newSalon();
eqLogic::$byLogicalId['11:22:33:44:55:66'] = new brokenTv('Chambre');
tvremote::onDaemonMessage(['devicesRT' => [
    '11:22:33:44:55:66' => ['mac' => '11:22:33:44:55:66', 'online' => 1, 'realtime' => 1],
    MAC => ['mac' => MAC, 'online' => 1, 'realtime' => 1],
]]);
check($salon->cmds['online']->events === [1], 'équipement suivant traité malgré l\'erreur');
check(count(log::linesOf('error')) === 1 && strpos(log::linesOf('error')[0], '11:22:33:44:55:66') !== false, 'erreur journalisée pour son seul équipement');

// TV non appairée : statut remis à 0, warning (pas d'erreur), alerte et badge (sans seconde alerte)
resetCore();
$salon = newSalon();
tvremote::onDaemonMessage(['PairingExc' => 'Need to pair', 'pairing_mac' => MAC, 'pairing_host' => '192.168.1.10', 'pairing_value' => 0]);
check($salon->config['tvremote_paired_status'] === 0 && $salon->saved === 1, 'statut d\'appairage remis à 0');
check(log::linesOf('error') === [] && count(log::linesOf('warning')) === 1, 'warning, pas d\'erreur');
check(count(eventsNamed('jeedom::alert')) === 1, 'une alerte');
$badge = eventsNamed('tvremote::tvremotePairingResult');
check(count($badge) === 1 && $badge[0]['tvremote_paired'] === 0 && $badge[0]['auto_detected'] === true, 'badge mis à jour, sans seconde alerte');

// Déjà à 0 : pas de nouvel enregistrement
resetCore();
$salon = newSalon(['tvremote_paired_status' => 0]);
tvremote::onDaemonMessage(['PairingExc' => 'Need to pair', 'pairing_mac' => MAC, 'pairing_host' => '192.168.1.10', 'pairing_value' => 0]);
check($salon->saved === 0, 'statut déjà à 0 : pas d\'enregistrement');

// Appairage ADB sans conclusion : statut inchangé, échec affiché
resetCore();
$salon = newSalon();
tvremote::onDaemonMessage(['mac' => MAC, 'adb_pairing_failed' => 1, 'message' => 'Connection error: unreachable']);
check($salon->config['adb_paired_status'] === 1 && $salon->saved === 0, 'statut ADB inchangé');
$adb = eventsNamed('tvremote::adbPairingResult');
check(count($adb) === 1 && $adb[0]['adb_paired'] === null, 'échec affiché sans statut');
check(log::linesOf('error') === [] && count(log::linesOf('warning')) === 1, 'échec ADB en warning');

// Appairage ADB refusé sur la TV : statut à 0
resetCore();
$salon = newSalon();
tvremote::onDaemonMessage(['mac' => MAC, 'adb_paired' => 0, 'message' => 'Device not authorized.']);
check($salon->config['adb_paired_status'] === 0 && $salon->saved === 1, 'refus ADB : statut à 0');

// Erreur d'une commande ADB Shell (TV éteinte…) : warning, valeur inchangée
resetCore();
$salon = newSalon();
tvremote::onDaemonMessage(['adb_shell_output_mac' => MAC, 'adb_shell_error' => 'Failed to connect']);
check(log::linesOf('error') === [] && count(log::linesOf('warning')) === 1, 'erreur ADB Shell en warning');
check($salon->cmds['adb_shell_output']->events === [], 'valeur inchangée');

// Sortie ADB Shell : secrets masqués dans les logs, valeur intacte dans la commande
resetCore();
$salon = newSalon();
tvremote::onDaemonMessage(['adb_shell_output_mac' => MAC, 'adb_shell_output_value' => 'login password=Secret42']);
check($salon->cmds['adb_shell_output']->events === ['login password=Secret42'], 'valeur intacte');
$logged = implode("\n", array_map(fn($line) => $line[1], log::$lines));
check(strpos($logged, 'Secret42') === false && strpos($logged, 'password=sEcReT') !== false, 'secret masqué dans les logs');

// Message inconnu
resetCore();
tvremote::onDaemonMessage(['something' => 1]);
check(count(log::linesOf('error')) === 1 && strpos(log::linesOf('error')[0], 'unknown message') !== false, 'message inconnu signalé');

echo 'OK' . PHP_EOL;
