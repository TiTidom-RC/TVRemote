<?php
/* This file is part of Jeedom.
*
* Jeedom is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* Jeedom is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with Jeedom. If not, see <http://www.gnu.org/licenses/>.
*/

/* * ***************************Includes********************************* */
require_once __DIR__  . '/../../../../core/php/core.inc.php';

class tvremote extends eqLogic {
    /* ************************** Variables Globales ****************************** */

    const PYTHON3_PATH = __DIR__ . '/../../resources/venv/bin/python3';
    const PYENV_PATH = '/opt/pyenv/bin/pyenv';

    /*
     * Permet de définir les possibilités de personnalisation du widget (en cas d'utilisation de la fonction 'toHtml' par exemple)
     * Tableau multidimensionnel - exemple: array('custom' => true, 'custom::layout' => false) */
    public static $_widgetPossibility = array('custom' => true);

    /*
     * Permet de crypter/décrypter automatiquement des champs de configuration du plugin
     * Exemple : "param1" & "param2" seront cryptés mais pas "param3"
     */
    // public static $_encryptConfigKey = array('voiceRSSAPIKey');

    /* ************************ Methodes statiques : Démon & Dépendances *************************** */

    public static function backupExclude() {
		return [
			'resources/venv'
		];
	}

    public static function dependancy_install() {
        log::remove(__CLASS__ . '_update');
        
        // debug options for install script
        $script_sysUpdates = 0;
        $script_restorePyEnv = 0;
        $script_restoreVenv = 0;

        if (config::byKey('debugInstallUpdates', 'tvremote') == '1') {
            $script_sysUpdates = 1;
            config::save('debugInstallUpdates', '0', 'tvremote');
        }
        if (config::byKey('debugRestorePyEnv', 'tvremote') == '1') {
            $script_restorePyEnv = 1;
            config::save('debugRestorePyEnv', '0', 'tvremote');
        }
        if (config::byKey('debugRestoreVenv', 'tvremote') == '1') {
            $script_restoreVenv = 1;
            config::save('debugRestoreVenv', '0', 'tvremote');
        }
        
        return array('script' => __DIR__ . '/../../resources/install_#stype#.sh ' . jeedom::getTmpFolder(__CLASS__) . '/dependency' . ' ' . $script_sysUpdates . ' ' . $script_restorePyEnv . ' ' . $script_restoreVenv, 'log' => log::getPathToLog(__CLASS__ . '_update'));
    }

    public static function dependancy_info() {
        $return = array();
        $return['log'] = log::getPathToLog(__CLASS__ . '_update');
        $return['progress_file'] = jeedom::getTmpFolder(__CLASS__) . '/dependency';
        if (file_exists(jeedom::getTmpFolder(__CLASS__) . '/dependency')) {
            $return['state'] = 'in_progress';
        } else {
            if (exec(system::getCmdSudo() . system::get('cmd_check') . '-Ec "python3\-requests|python3\-setuptools|python3\-dev|python3\-venv"') < 4) {
                $return['state'] = 'nok';
            } elseif (!file_exists(self::PYTHON3_PATH)) {
                $return['state'] = 'nok';
            } elseif (exec(system::getCmdSudo() . self::PYTHON3_PATH . ' -m pip freeze | grep -Ewc "' . config::byKey('pythonDepString', 'tvremote', '', true) . '"') < config::byKey('pythonDepNum', 'tvremote', 0, true)) {
                $return['state'] = 'nok';
            } else {
                $return['state'] = 'ok';
            }
        }
        return $return;
    }

    public static function deamon_info() {
        $return = array();
        $return['log'] = __CLASS__;
        $return['state'] = 'nok';
        $pid_file = jeedom::getTmpFolder(__CLASS__) . '/deamon.pid';
        if (file_exists($pid_file)) {
            if (@posix_getsid(trim(file_get_contents($pid_file)))) {
                $return['state'] = 'ok';
            } else {
                shell_exec(system::getCmdSudo() . 'rm -rf ' . $pid_file . ' 2>&1 > /dev/null');
            }
        }
        $return['launchable'] = 'ok';
        return $return;
    }

    public static function deamon_start() {
        self::deamon_stop();
        $deamon_info = self::deamon_info();
        if ($deamon_info['launchable'] != 'ok') {
            throw new Exception(__('Veuillez vérifier la configuration', __FILE__));
        }

        try {
            self::getPyEnvVersion();
            self::getPythonVersion();
        }
        catch (Exception $e) {
            log::add('tvremote', 'error', '[DAEMON][START][PyVersions] Exception :: ' . $e->getMessage());
        }

        $path = realpath(__DIR__ . '/../../resources/tvremoted');
        $cmd = self::PYTHON3_PATH . " {$path}/tvremoted.py";
        $cmd .= ' --loglevel ' . log::convertLogLevel(log::getLogLevel(__CLASS__));
        $cmd .= ' --pluginversion ' . config::byKey('pluginVersion', __CLASS__, '0.0.0');
        $cmd .= ' --socketport ' . config::byKey('socketport', __CLASS__, '55112');
        $cmd .= ' --cyclefactor ' . config::byKey('cyclefactor', __CLASS__, '1.0');
        $cmd .= ' --jeedomname ' . preg_replace('/\s+/', '', config::byKey('name', 'core', 'Jeedom'));
        $cmd .= ' --callback ' . network::getNetworkAccess('internal', 'http:127.0.0.1:port:comp') . '/plugins/tvremote/core/php/jeetvremote.php'; // chemin du callback
        log::add(__CLASS__, 'debug', 'Daemon Cmd (w/o APIKey) :: ' . $cmd);
        $cmd .= ' --apikey ' . jeedom::getApiKey(__CLASS__);
        $cmd .= ' --pid ' . jeedom::getTmpFolder(__CLASS__) . '/deamon.pid'; // ne PAS modifier
        log::add(__CLASS__, 'info', 'Lancement du démon');
        $result = exec($cmd . ' >> ' . log::getPathToLog('tvremote_daemon') . ' 2>&1 &');
        $i = 0;
        while ($i < 20) {
            $deamon_info = self::deamon_info();
            if ($deamon_info['state'] == 'ok') {
                break;
            }
            sleep(1);
            $i++;
        }
        if ($i >= 20) {
            log::add(__CLASS__, 'error', __('Impossible de lancer le démon, vérifiez le log', __FILE__), 'unableStartDeamon');
            return false;
        }
        message::removeAll(__CLASS__, 'unableStartDeamon');
        config::save('scanState', '0', 'tvremote');
        return true;
    }

    public static function deamon_stop() {
        $pid_file = jeedom::getTmpFolder(__CLASS__) . '/deamon.pid'; // Ne PAS modifier
        if (file_exists($pid_file)) {
            $pid = intval(trim(file_get_contents($pid_file)));
            system::kill($pid);
        }
        system::kill('tvremoted.py');
        system::fuserk(config::byKey('socketport', __CLASS__, '55112'));
        sleep(1);
    }

    public static function sendToDaemon($params) {
        try {
            $deamon_info = self::deamon_info();
            if ($deamon_info['state'] != 'ok') {
                event::add('jeedom::alert', array(
                    'level' => 'danger',
                    'page' => 'tvremote',
                    'message' => __('[KO] Communication impossible avec le démon car il n\'est pas démarré !', __FILE__),
                ));
                throw new Exception("Communication impossible avec le démon car il n'est pas démarré !");
            }
            $params['apikey'] = jeedom::getApiKey(__CLASS__);
            $payLoad = json_encode($params);
            $socket = socket_create(AF_INET, SOCK_STREAM, SOL_TCP);
            socket_connect($socket, '127.0.0.1', config::byKey('socketport', __CLASS__, '55112'));
            socket_write($socket, $payLoad, strlen($payLoad));
            socket_close($socket);
        } catch (Exception $e) {
            log::add('tvremote', 'error', '[SOCKET][SendToDaemon] Exception :: ' . $e->getMessage());
            return false;
        }
    }

    /* ************************ Methodes static : PLUGIN *************************** */

    public static function getPluginVersion() {
        $pluginVersion = '0.0.0';
        try {
            if (!file_exists(dirname(__FILE__) . '/../../plugin_info/info.json')) {
                log::add('tvremote', 'warning', '[Plugin-Version] fichier info.json manquant');
                return $pluginVersion;
            }
            $data = json_decode(file_get_contents(dirname(__FILE__) . '/../../plugin_info/info.json'), true);
            if (!is_array($data)) {
                log::add('tvremote', 'warning', '[Plugin-Version] Impossible de décoder le fichier info.json');
                return $pluginVersion;
            }
            try {
                $pluginVersion = $data['pluginVersion'];
                // $pluginVersion .= " (" . update::byLogicalId('tvremote')->getLocalVersion() . ")";
            } catch (\Exception $e) {
                log::add('tvremote', 'warning', '[Plugin-Version] Impossible de récupérer la version du plugin');
            }
        }
        catch (\Exception $e) {
            log::add('tvremote', 'debug', '[Plugin-Version] Get ERROR :: ' . $e->getMessage());
        }
        log::add('tvremote', 'info', '[Plugin-Version] PluginVersion :: ' . $pluginVersion);
        return $pluginVersion;
    }

    public static function getPythonDepFromRequirements() {
        $pythonDepString = '';
        $pythonDepNum = 0;
        try {
            if (!file_exists(dirname(__FILE__) . '/../../resources/requirements.txt')) {
                log::add('tvremote', 'error', '[Python-Dep] Fichier requirements.txt manquant');
                config::save('pythonDepString', $pythonDepString, 'tvremote');
                config::save('pythonDepNum', $pythonDepNum, 'tvremote');
                return false;
            }
            $data = file_get_contents(dirname(__FILE__) . '/../../resources/requirements.txt');
            if (!is_string($data)) {
                log::add('tvremote', 'error', '[Python-Dep] Impossible de lire le fichier requirements.txt');
                config::save('pythonDepString', $pythonDepString, 'tvremote');
                config::save('pythonDepNum', $pythonDepNum, 'tvremote');
                return false;
            }
            $lines = explode("\n", $data);
            $nonEmptyLines = array_filter($lines, function($line) {
                return trim($line) !== '';
            });
            $pythonDepString = join("|", $nonEmptyLines);
            $pythonDepNum = count($nonEmptyLines);
        }
        catch (\Exception $e) {
            log::add('tvremote', 'debug', '[Python-Dep] Get requirements.txt ERROR :: ' . $e->getMessage());
        }
        log::add('tvremote', 'debug', '[Python-Dep] PythonDepString / PythonDepNum :: ' . $pythonDepString . " / " . $pythonDepNum);
        config::save('pythonDepString', $pythonDepString, 'tvremote');
        config::save('pythonDepNum', $pythonDepNum, 'tvremote');
        return true;
    }

    public static function getPythonVersion() {
        $pythonVersion = '0.0.0';
        try {
            if (file_exists(self::PYTHON3_PATH)) {
               $pythonVersion = exec(system::getCmdSudo() . self::PYTHON3_PATH . " --version | awk '{ print $2 }'");
               config::save('pythonVersion', $pythonVersion, 'tvremote');
            }
            else {
                log::add('tvremote', 'error', '[Python-Version] Python File :: KO');
            }
        }
        catch (\Exception $e) {
            log::add('tvremote', 'error', '[Python-Version] Exception :: ' . $e->getMessage());
        }
        log::add('tvremote', 'info', '[Python-Version] PythonVersion :: ' . $pythonVersion);
        return $pythonVersion;
    }

    public static function getPyEnvVersion() {
        $pyenvVersion = '0.0.0';
        try {
            if (file_exists(self::PYENV_PATH)) {
                $pyenvVersion = exec(system::getCmdSudo() . self::PYENV_PATH . " --version | awk '{ print $2 }'");
                config::save('pyenvVersion', $pyenvVersion, 'tvremote');
            } 
            elseif (file_exists(self::PYTHON3_PATH)) {
                $pythonPyEnvInUse = (exec(system::getCmdSudo() . 'dirname $(readlink ' . self::PYTHON3_PATH . ') | grep -Ewc "opt/pyenv"') == 1) ? true : false;
                if (!$pythonPyEnvInUse) {
                    $pyenvVersion = "-";
                    config::save('pyenvVersion', $pyenvVersion, 'tvremote');
                }
            } 
            else {
                log::add('tvremote', 'error', '[PyEnv-Version] PyEnv File :: KO');
            }
        }
        catch (\Exception $e) {
            log::add('tvremote', 'error', '[PyEnv-Version] Exception :: ' . $e->getMessage());
        }
        log::add('tvremote', 'info', '[PyEnv-Version] PyEnvVersion :: ' . $pyenvVersion);
        return $pyenvVersion;
    }

    public static function changeScanState($_scanState)
    {
        if ($_scanState == "scanOn") {
            $value = array('cmd' => 'scanOn');
            self::sendToDaemon($value);
        } else {
            $value = array('cmd' => 'scanOff');
            self::sendToDaemon($value);
        }
    }

    public static function sendBeginPairing($_mac=null, $_host=null, $_port=null)
    {
        if (!is_null($_mac)) {
            $value = array(
                'cmd' => 'sendBeginPairing',
                'mac' => $_mac,
                'host' => $_host,
                'port' => $_port
            );
            self::sendToDaemon($value);
            return 'OK';
        } else {
            log::add('tvremote', 'debug', '[sendBeginPairing] MAC is missing :: KO');
            return 'MAC is missing (KO)';
        }
    }

    public static function sendPairCode($_mac=null, $_host=null, $_port=null, $_paircode=null)
    {
        if (!is_null($_mac)) {
            $value = array(
                'cmd' => 'sendPairCode',
                'mac' => $_mac,
                'host' => $_host,
                'port' => $_port,
                'paircode' => $_paircode
            );
            self::sendToDaemon($value);
            return 'OK';
        } else {
            log::add('tvremote', 'debug', '[sendPairCode] MAC is missing :: KO');
            return 'MAC is missing (KO)';
        }
    }

    public static function createAndUpdTVRemoteFromScan($_data)
    {
        if (!isset($_data['mac'])) {
            event::add('jeedom::alert', array(
                'level' => 'danger',
                'page' => 'tvremote',
                'message' => __('[KO] Information manquante (MAC) pour créer l\'équipement', __FILE__),
            ));
            log::add('tvremote', 'error', '[FROM_SCAN] Information manquante (MAC) pour créer l\'équipement');
            return false;
        }
        
        $newtvremote = tvremote::byLogicalId($_data['mac'], 'tvremote');
        if (!is_object($newtvremote)) {
            log::add('tvremote', 'debug', '[FROM_SCAN] Objet non existant :: ' . $_data['friendly_name']);
            $eqLogic = new tvremote();
            $eqLogic->setLogicalId($_data['mac']);
            $eqLogic->setIsEnable(1);
            $eqLogic->setIsVisible(1);
            $eqLogic->setName($_data['friendly_name']);
            $eqLogic->setEqType_name('tvremote');
            $eqLogic->setCategory('multimedia','1');
            $eqLogic->setConfiguration('name', $_data['name']);
            $eqLogic->setConfiguration('family', $_data['family']);
            $eqLogic->setConfiguration('friendly_name', $_data['friendly_name']);
            $eqLogic->setConfiguration('type', $_data['type']);
            $eqLogic->setConfiguration('host', $_data['host']);
            $eqLogic->setConfiguration('port', $_data['port']);
            $eqLogic->setConfiguration('lastscan', $_data['lastscan']);
            $eqLogic->save();

            event::add('jeedom::alert', array(
                'level' => 'success',
                'page' => 'tvremote',
                'message' => __('[FROM_SCAN] TVRemote AJOUTE :: ', __FILE__) . $_data['friendly_name'],
            ));
            log::add('tvremote', 'info', '[FROM_SCAN] TVRemote AJOUTE :: ' . $_data['friendly_name']);
            return $eqLogic;
        }
        else {
            log::add('tvremote', 'debug', '[FROM_SCAN] Objet déjà existant :: ' . $_data['friendly_name']);
            $newtvremote->setConfiguration('name', $_data['name']);
            $newtvremote->setConfiguration('family', $_data['family']);
            $newtvremote->setConfiguration('friendly_name', $_data['friendly_name']);
            $newtvremote->setConfiguration('type', $_data['type']);
            $newtvremote->setConfiguration('host', $_data['host']);
            $newtvremote->setConfiguration('port', $_data['port']);
            $newtvremote->setConfiguration('lastscan', $_data['lastscan']);
            $newtvremote->save();

            event::add('jeedom::alert', array(
                'level' => 'warning',
                'page' => 'tvremote',
                'message' => __('[FROM_SCAN] TVRemote MAJ :: ', __FILE__) . $_data['friendly_name'],
            ));
            log::add('tvremote', 'info', '[FROM_SCAN] TVRemote MAJ :: ' . $_data['friendly_name']);
            return $newtvremote;
        }
    }

    public static function sendOnStartTVRemoteToDaemon()
    {
        log::add('tvremote', 'info', '[SendOnStart] Envoi Equipements TVRemote Actifs');
        $i = 0;
        while ($i < 10) {
            $deamon_info = self::deamon_info();
            if ($deamon_info['state'] == 'ok') {
                break;
            }
            sleep(1);
            $i++;
        }
        if ($i >= 10) {
            log::add('tvremote', 'error', '[SendOnStart] Démon non lancé (>10s) :: KO');
            return false;
        }
        foreach(self::byType('tvremote') as $eqLogic) {
            if ($eqLogic->getIsEnable()) {
                $eqLogic->enableTVRemoteToDaemon();
            }
            else {
                $eqLogic->disableTVRemoteToDaemon();
            }   
        }
    }

    public function enableTVRemoteToDaemon()
    {
        if ($this->getLogicalId() != '') {
            $value = array(
                'cmd' => 'addtvremote',
                'mac' => $this->getLogicalId(),
                'host' => $this->getConfiguration('host'),
                'port' => $this->getConfiguration('port'),
                'friendly_name' => $this->getConfiguration('friendly_name')
            );
            self::sendToDaemon($value);
        }

    }

    public function disableTVRemoteToDaemon()
    {
        if ($this->getLogicalId() != '') {
            $value = array(
                'cmd' => 'removetvremote',
                'mac' => $this->getLogicalId(),
                'host' => $this->getConfiguration('host'),
                'port' => $this->getConfiguration('port'),
                'friendly_name' => $this->getConfiguration('friendly_name')
            );
            self::sendToDaemon($value);
        }
    }

    public static function pairingException($_data)
    {
        if (!isset($_data['pairing_mac'])) {
            log::add('tvremote', 'error', '[PAIRING][EXCEPTION] Information manquante (MAC) pour mettre à jour l\'équipement');
            return false;
        }
        $pairingExc = tvremote::byLogicalId($_data['pairing_mac'], 'tvremote');
        if (!is_object($pairingExc)) {
            $mac_addr = $_data['pairing_mac'];
            log::add('tvremote', 'error', '[PAIRING][EXCEPTION] Device (' . $mac_addr . ') non existant dans Jeedom');
            return false;
        }
        else {
            $friendly_name = $pairingExc->getConfiguration('friendly_name');
            $device_mac = $_data['pairing_mac'];
            $device_host = $_data['pairing_host'];
            $pairing_exc = $_data['PairingExc'];
            
            event::add('jeedom::alert', array(
                'level' => 'warning',
                'page' => 'tvremote',
                'message' => __('TV :: ' . $friendly_name .  ' (' . $device_mac . ' / ' . $device_host . ') :: ' . $pairing_exc, __FILE__),
            ));

            log::add('tvremote', 'error', 'TV :: ' . $friendly_name .  ' (' . $device_mac . ' / ' . $device_host . ') :: ' . $pairing_exc, 'pairingExc' . $pairingExc->getId());
            # message::add('tvremote', 'TV :: ' . $friendly_name .  ' (' . $device_mac . ' / ' . $device_host . ') :: ' . $pairing_exc, '', 'pairingExc' . $pairingExc->getId());
            # $pairingExc->setConfiguration('pairingState', $_data['pairing_value']);
            # $pairingExc->save();

        }
    }

    public static function realtimeUpdateDevice($_data)
    {
        if (!isset($_data['mac'])) {
            log::add('tvremote', 'error', '[REALTIME][REMOTE] Information manquante (MAC) pour mettre à jour l\'équipement');
            return false;
        }
        $rtdevice = tvremote::byLogicalId($_data['mac'], 'tvremote');
        if (!is_object($rtdevice)) {
            log::add('tvremote', 'error', '[REALTIME][REMOTE] Device non existant dans Jeedom');
            return false;
        }
        else {
            foreach($rtdevice->getCmd('info') as $cmd) {
                $logicalId = $cmd->getLogicalId();
                if (key_exists($logicalId, $_data)) {
                    log::add('tvremote', 'debug', '[REALTIME][REMOTE] Device cmd event :: ' . $logicalId . ' = ' . $_data[$logicalId]);
                    $cmd->event($_data[$logicalId]);
                } else {
                    log::add('tvremote', 'debug', '[REALTIME][REMOTE] Device cmd NON EXIST :: ' . $logicalId);
                    continue;
                }
            }
        }
    }

    public static function actionTVRemote($mac=null, $action=null, $message=null) {
        log::add('tvremote', 'debug', '[ActionTVRemote] Infos :: ' . $mac . ' / ' . $action . " / " . $message);
        $value = array(
            'cmd' => 'action', 
            'cmd_action' => $action, 
            'value' => $message, 
            'mac' => $mac
        );
        log::add('tvremote', 'debug', '[ActionTVRemote] ArrayToSend :: ' . json_encode($value));
        self::sendToDaemon($value);
    }

    /* ************************ Methodes static : JEEDOM *************************** */

    /*
     * Fonction exécutée automatiquement toutes les minutes par Jeedom
    public static function cron() {

    }
    */

    
    /* Fonction exécutée automatiquement toutes les 5 minutes par Jeedom
    public static function cron5() {

    } 
    */
    

    /*
     * Fonction exécutée automatiquement toutes les 10 minutes par Jeedom
    public static function cron10() {

    }
    */

    /*
     * Fonction exécutée automatiquement toutes les 15 minutes par Jeedom
    public static function cron15() {

    }
    */

    /*
     * Fonction exécutée automatiquement toutes les 30 minutes par Jeedom
    public static function cron30() {

    }
    */

    /*
     * Fonction exécutée automatiquement toutes les heures par Jeedom
    public static function cronHourly() {

    }
    */

    /* Fonction exécutée automatiquement tous les jours par Jeedom
    public static function cronDaily() {
        
    }
    */

    // Fonction exécutée automatiquement après la sauvegarde (création ou mise à jour) de l'équipement
    public function postSave() {
        $orderCmd = 1;

        $cmd = $this->getCmd(null, 'refresh');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Rafraîchir', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('refresh');
            $cmd->setType('action');
            $cmd->setSubType('other');    
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }
        
        $cmd = $this->getCmd(null, 'online');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('En Ligne', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('online');
            $cmd->setType('info');
            $cmd->setSubType('binary');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'is_on');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Power', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('is_on');
            $cmd->setType('info');
            $cmd->setSubType('binary');
	        $cmd->setIsVisible(0);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }
        $power_cmd_id = $cmd->getId();
        
        $cmd = $this->getCmd(null, 'power_on');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Power On', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('power_on');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-volume-mute"></i>');
            $cmd->setValue($power_cmd_id);
	        $cmd->setIsVisible(1);
            $cmd->setTemplate('dashboard', 'core::binaryDefault');
            $cmd->setTemplate('mobile', 'core::binaryDefault');
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'power_off');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Power Off', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('power_off');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-volume-off"></i>');
            $cmd->setValue($power_cmd_id);
	        $cmd->setIsVisible(1);
            $cmd->setTemplate('dashboard', 'core::binaryDefault');
            $cmd->setTemplate('mobile', 'core::binaryDefault');
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'volume_level');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Volume', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('volume_level');
            $cmd->setType('info');
            $cmd->setSubType('numeric');
            $cmd->setUnite('%');
            $cmd->setConfiguration('minValue', 0);
            $cmd->setConfiguration('maxValue', 100);
            $cmd->setTemplate('dashboard', 'core::tile');
            $cmd->setTemplate('mobile', 'core::tile');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'volume_muted');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Mute', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('volume_muted');
            $cmd->setType('info');
            $cmd->setSubType('binary');
	        $cmd->setIsVisible(0);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }
        $mute_cmd_id = $cmd->getId();

        $cmd = $this->getCmd(null, 'mute_on');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Mute On', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('mute_on');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-volume-mute"></i>');
            $cmd->setValue($mute_cmd_id);
	        $cmd->setIsVisible(1);
            $cmd->setTemplate('dashboard', 'core::toggle');
            $cmd->setTemplate('mobile', 'core::toggle');
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'mute_off');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Mute Off', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('mute_off');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-volume-off"></i>');
            $cmd->setValue($mute_cmd_id);
	        $cmd->setIsVisible(1);
            $cmd->setTemplate('dashboard', 'core::toggle');
            $cmd->setTemplate('mobile', 'core::toggle');
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'menu');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Menu', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('menu');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-bars"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'volumedown');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Volume Down', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('volumedown');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-volume-down icon_blue"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'volumeup');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Volume Up', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('volumeup');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-volume-up icon_blue"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'tv');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('TV', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('tv');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-tv"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'info');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Info', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('info');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-info-circle"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'up');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Up', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('up');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-arrow-circle-up icon_blue"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'settings');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Settings', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('settings');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-cogs"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'left');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Left', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('left');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-arrow-circle-left icon_blue"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'center');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Center', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('center');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-dot-circle"></i>');
            $cmd->setDisplay('icon', '<i class="fas fa-check-circle"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'right');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Right', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('right');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-arrow-circle-right icon_blue"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'back');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Back', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('back');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'down');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Down', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('down');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-arrow-circle-down icon_blue"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'home');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Home', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('home');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-home"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }
       
        $cmd = $this->getCmd(null, 'one');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('1', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('one');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'two');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('2', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('two');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'three');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('3', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('three');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'four');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('4', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('four');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'five');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('5', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('five');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'six');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('6', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('six');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'seven');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('7', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('seven');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'eight');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('8', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('eight');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'nine');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('9', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('nine');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'channel_down');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Channel -', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('channel_down');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-minus-square icon_blue"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'zero');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('0', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('zero');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'channel_up');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Channel +', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('channel_up');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-plus-square icon_blue"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }


        $cmd = $this->getCmd(null, 'input');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Input', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('input');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'hdmi_1');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('HDMI 1', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('hdmi_1');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'hdmi_2');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('HDMI 2', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('hdmi_2');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'hdmi_3');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('HDMI 3', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('hdmi_3');
            $cmd->setType('action');
            $cmd->setSubType('other');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'hdmi_4');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('HDMI 4', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('hdmi_4');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            # $cmd->setDisplay('icon', '<i class="fas fa-reply"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'media_previous');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Previous', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_previous');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-step-backward"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'media_rewind');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Rewind', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_rewind');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-backward"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'media_play');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Play', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_play');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-play"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'media_pause');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Pause', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_pause');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-pause"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'media_stop');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Stop', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_stop');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-stop"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'media_forward');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Forward', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_forward');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-forward"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'media_next');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Next', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_next');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-step-forward"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        /* $cmd = $this->getCmd(null, 'media_eject');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Eject', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_eject');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            $cmd->setDisplay('icon', '<i class="fas fa-eject"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        } */

        $cmd = $this->getCmd(null, 'oqee');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Free', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('oqee');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('type', 'application');
            $cmd->setConfiguration('image', 'oqee.png');
            $cmd->setTemplate('dashboard', 'tvremote::tvremote-app');
            $cmd->setTemplate('mobile', 'tvremote::tvremote-app');
            $cmd->setDisplay('forceReturnLineBefore', '1');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'youtube');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('YouTube', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('youtube');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('type', 'application');
            $cmd->setConfiguration('image', 'youtube.png');
            $cmd->setTemplate('dashboard', 'tvremote::tvremote-app');
            $cmd->setTemplate('mobile', 'tvremote::tvremote-app');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'netflix');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Netflix', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('netflix');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('type', 'application');
            $cmd->setConfiguration('image', 'netflix.png');
            $cmd->setTemplate('dashboard', 'tvremote::tvremote-app');
            $cmd->setTemplate('mobile', 'tvremote::tvremote-app');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'primevideo');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Prime Video', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('primevideo');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('type', 'application');
            $cmd->setConfiguration('image', 'primevideo.png');
            $cmd->setTemplate('dashboard', 'tvremote::tvremote-app');
            $cmd->setTemplate('mobile', 'tvremote::tvremote-app');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'disneyplus');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Disney+', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('disneyplus');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('type', 'application');
            $cmd->setConfiguration('image', 'disneyplus.png');
            $cmd->setTemplate('dashboard', 'tvremote::tvremote-app');
            $cmd->setTemplate('mobile', 'tvremote::tvremote-app');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'mycanal');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('My Canal', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('mycanal');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('type', 'application');
            $cmd->setConfiguration('image', 'mycanal.png');
            $cmd->setTemplate('dashboard', 'tvremote::tvremote-app');
            $cmd->setTemplate('mobile', 'tvremote::tvremote-app');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'plex');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Plex', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('plex');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('type', 'application');
            $cmd->setConfiguration('image', 'plex.png');
            $cmd->setTemplate('dashboard', 'tvremote::tvremote-app');
            $cmd->setTemplate('mobile', 'tvremote::tvremote-app');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'appletv');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Apple TV', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('appletv');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('type', 'application');
            $cmd->setConfiguration('image', 'appletv.png');
            $cmd->setTemplate('dashboard', 'tvremote::tvremote-app');
            $cmd->setTemplate('mobile', 'tvremote::tvremote-app');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'molotov');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Molotov TV', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('molotov');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setConfiguration('type', 'application');
            $cmd->setConfiguration('image', 'molotov.png');
            $cmd->setTemplate('dashboard', 'tvremote::tvremote-app');
            $cmd->setTemplate('mobile', 'tvremote::tvremote-app');
            $cmd->setDisplay('forceReturnLineAfter', '1');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'current_app');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Current App', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('current_app');
            $cmd->setType('info');
            $cmd->setSubType('string');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setDisplay('forceReturnLineAfter', '1');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'updatelasttime');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Update LastTime', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('updatelasttime');
            $cmd->setType('info');
            $cmd->setSubType('string');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setDisplay('forceReturnLineAfter', '1');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'updatelasttimets');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Update LastTime (TS)', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('updatelasttimets');
            $cmd->setType('info');
            $cmd->setSubType('string');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setDisplay('forceReturnLineAfter', '1');
	        $cmd->setIsVisible(0);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'customcmd');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Custom Cmd', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('customcmd');
            $cmd->setType('action');
            $cmd->setSubType('message');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setDisplay('forceReturnLineAfter', '1');
	        $cmd->setIsVisible(0);
            $cmd->setDisplay('parameters', array("title_disable" => "1", "title_placeholder" => "Options", "message_placeholder" => "Custom Cmd"));
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'keycode');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Key Code', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('keycode');
            $cmd->setType('action');
            $cmd->setSubType('message');
            $cmd->setDisplay('forceReturnLineBefore', '1');
            $cmd->setIsVisible(0);
            $cmd->setDisplay('parameters', array("title_disable" => "1", "title_placeholder" => "Options", "message_placeholder" => "Key Code"));
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'appcode');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('App Code', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('appcode');
            $cmd->setType('action');
            $cmd->setSubType('message');
            $cmd->setDisplay('forceReturnLineAfter', '1');
            $cmd->setIsVisible(0);
            $cmd->setDisplay('parameters', array("title_disable" => "1", "title_placeholder" => "Options", "message_placeholder" => "App Code"));
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        if ($this->getIsEnable()) {
            $this->enableTVRemoteToDaemon();
        } else {
            $this->disableTVRemoteToDaemon();
        }
    }

    // Fonction exécutée automatiquement avant la suppression de l'équipement
    public function preRemove() {
        $this->disableTVRemoteToDaemon();
    }
}

class tvremoteCmd extends cmd {

    /* **************************Attributs****************************** */

    public static $_widgetPossibility = array('custom' => true);


    // Exécution d'une commande
    public function execute($_options = array()) {
        $eqLogic = $this->getEqLogic();
        $logicalId = $this->getLogicalId();
        
        log::add('tvremote', 'debug', '[CMD] LogicalId :: ' . $logicalId);

        if ( $this->getType() == "action" ) {
            if (in_array($logicalId, ["keycode", "appcode"])) {
                log::add('tvremote', 'debug', '[CMD] ' . $logicalId . ' :: ' . json_encode($_options));
                $deviceMAC = $eqLogic->getLogicalId();
                if (isset($deviceMAC) && isset($_options['message'])) {
                    tvremote::actionTVRemote($deviceMAC, $logicalId, $_options['message']);
                }
                else {
                    log::add('tvremote', 'debug', '[CMD - Key/App Code] Il manque un paramètre pour lancer la commande '. $logicalId);
                }                
            } elseif (in_array($logicalId, ["volumedown", "volumeup", "power_on", "power_off", "up", "down", "left", "right", "center", "mute_on", "mute_off", "back", "home", "menu", "tv", "channel_up", "channel_down", "info", "settings", "input", "hdmi_1", "hdmi_2", "hdmi_3", "hdmi_4", "oqee", "youtube", "netflix", "primevideo", "disneyplus", "mycanal", "plex", "appletv", "molotov", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "zero", "media_next", "media_stop", "media_pause", "media_play", "media_rewind", "media_forward", "media_previous"])) {
                log::add('tvremote', 'debug', '[CMD] ' . $logicalId . ' :: ' . json_encode($_options));
                $deviceMAC = $eqLogic->getLogicalId();
                if (isset($deviceMAC)) {
                    tvremote::actionTVRemote($deviceMAC, $logicalId);
                }
            } elseif (in_array($logicalId, ["refresh"])) {
                log::add('tvremote', 'debug', '[CMD] ' . $logicalId . ' :: ' . json_encode($_options));
            }
            else {
                throw new Exception(__('Commande Action non implémentée actuellement', __FILE__));    
            }
		} else {
			throw new Exception(__('Commande non implémentée actuellement', __FILE__));
		}
		return true;
    }
}
