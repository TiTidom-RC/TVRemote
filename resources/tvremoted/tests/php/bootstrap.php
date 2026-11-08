<?php
// Classes du Core Jeedom simulées, puis chargement de la vraie classe du plugin (core/class/tvremote.class.php) sans Jeedom.
// Inclus par les scripts check_*.php, lancés par tests/test_phpChecks.py.

function __($text, $file = '') {
    return $text;
}

class log {
    public static $lines = [];
    public static function add($log, $level, $message, $logicalId = '') {
        self::$lines[] = [$level, $message];
    }
    public static function linesOf($level) {
        return array_values(array_map(fn($line) => $line[1], array_filter(self::$lines, fn($line) => $line[0] === $level)));
    }
}

class config {
    public static $values = [];
    public static function byKey($key, $plugin = 'core', $default = '') {
        return self::$values[$plugin][$key] ?? $default;
    }
    public static function save($key, $value, $plugin = 'core') {
        self::$values[$plugin][$key] = $value;
    }
}

class event {
    public static $events = [];
    public static function add($name, $data = []) {
        self::$events[] = [$name, $data];
    }
}

class eqLogic {}
class cmd {}

function loadPluginClass() {
    $source = file_get_contents(__DIR__ . '/../../../../core/class/tvremote.class.php');
    $source = preg_replace('/^<\?php/', '', $source);
    $source = preg_replace('/^require_once .*$/m', '', $source);
    eval($source);
}

function check(bool $ok, string $label) {
    if (!$ok) {
        echo "KO $label" . PHP_EOL;
        exit(1);
    }
}

loadPluginClass();
