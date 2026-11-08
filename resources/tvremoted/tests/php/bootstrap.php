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

class eqLogic {
    public static $byLogicalId = [];
    public static function byLogicalId($logicalId, $type, $multiple = false) {
        return self::$byLogicalId[$logicalId] ?? null;
    }
}

class cmd {
    public static $byId = [];
    public static function byId($id) {
        return self::$byId[$id] ?? null;
    }
}

// Équipement TV : configuration, commandes info, enregistrements
class fakeTv {
    public $config;
    public $cmds = [];
    public $saved = 0;
    public $updated = [];
    private $name;
    public function __construct($name, $config = []) {
        $this->name = $name;
        $this->config = $config;
    }
    public function getName() { return $this->name; }
    public function getId() { return 1; }
    public function getConfiguration($key, $default = '') { return $this->config[$key] ?? $default; }
    public function setConfiguration($key, $value) { $this->config[$key] = $value; }
    public function save() { $this->saved++; }
    public function getCmd($type = null, $logicalId = null) {
        return ($logicalId === null) ? array_values($this->cmds) : ($this->cmds[$logicalId] ?? null);
    }
    public function checkAndUpdateCmd($cmd, $value) { $this->updated[] = [$cmd, $value]; }
}

class fakeCmd {
    public $events = [];
    private $logicalId;
    public function __construct($logicalId) { $this->logicalId = $logicalId; }
    public function getLogicalId() { return $this->logicalId; }
    public function event($value) { $this->events[] = $value; }
}

function resetCore() {
    log::$lines = [];
    event::$events = [];
    eqLogic::$byLogicalId = [];
    cmd::$byId = [];
}

function eventsNamed($name) {
    return array_values(array_map(fn($event) => $event[1], array_filter(event::$events, fn($event) => $event[0] === $name)));
}

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
