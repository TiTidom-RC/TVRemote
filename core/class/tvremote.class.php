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
        return array('script' => __DIR__ . '/../../resources/install_#stype#.sh ' . jeedom::getTmpFolder(__CLASS__) . '/dependency', 'log' => log::getPathToLog(__CLASS__ . '_update'));
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
                log::add(__CLASS__, 'debug', 'Python3 file check failed !');
                $return['state'] = 'nok';
            } elseif (exec(system::getCmdSudo() . self::PYTHON3_PATH . ' -m pip freeze | grep -Ewc "zeroconf==0.131.0|aiohttp==3.9.3|androidtvremote2==0.0.14"') < 3) {
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
        $cmd .= ' --callback ' . network::getNetworkAccess('internal', 'http:127.0.0.1:port:comp') . '/plugins/tvremote/core/php/jeetvremote.php'; // chemin du callback
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
                throw new Exception("Le Démon n'est pas démarré !");
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

    public static function getPluginVersion() {
        $pluginVersion = '0.0.0';
        try {
            if (!file_exists(dirname(__FILE__) . '/../../plugin_info/info.json')) {
                log::add('tvremote', 'warning', '[Plugin-Version] fichier info.json manquant');
            }
            $data = json_decode(file_get_contents(dirname(__FILE__) . '/../../plugin_info/info.json'), true);
            if (!is_array($data)) {
                log::add('tvremote', 'warning', '[Plugin-Version] Impossible de décoder le fichier info.json');
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

    public static function createAndUpdCastFromScan($_data)
    {
        if (!isset($_data['name'])) {
            log::add('tvremote', 'error', '[CREATEFROMSCAN] Information manquante (Name) pour créer l\'équipement');
            event::add('jeedom::alert', array(
                'level' => 'danger',
                'page' => 'tvremote',
                'message' => __('[KO] Information manquante (Name) pour créer l\'équipement', __FILE__),
            ));
            return false;
        }
        
        $newtvremote = tvremote::byLogicalId($_data['name'], 'tvremote');
        if (!is_object($newtvremote)) {
            $eqLogic = new tvremote();
            $eqLogic->setLogicalId($_data['name']);
            $eqLogic->setIsEnable(1);
            $eqLogic->setIsVisible(1);
            $eqLogic->setName($_data['friendly_name']);
            $eqLogic->setEqType_name('tvremote');
            $eqLogic->setCategory('multimedia','1');
            $eqLogic->setConfiguration('friendly_name', $_data['friendly_name']);
            $eqLogic->setConfiguration('type', $_data['type']);
            $eqLogic->setConfiguration('host', $_data['host']);
            $eqLogic->setConfiguration('port', $_data['port']);
            $eqLogic->setConfiguration('lastscan', $_data['lastscan']);
            $eqLogic->save();

            event::add('jeedom::alert', array(
                'level' => 'success',
                'page' => 'tvremote',
                'message' => __('[SCAN] TVRemote AJOUTE :: ' .$_data['friendly_name'], __FILE__),
            ));
            return $eqLogic;
        }
        else {
            $newtvremote->setConfiguration('friendly_name', $_data['friendly_name']);
            $newtvremote->setConfiguration('type', $_data['type']);
            $newtvremote->setConfiguration('host', $_data['host']);
            $newtvremote->setConfiguration('port', $_data['port']);
            $newtvremote->setConfiguration('lastscan', $_data['lastscan']);
            $newtvremote->save();

            event::add('jeedom::alert', array(
                'level' => 'success',
                'page' => 'tvremote',
                'message' => __('[SCAN] TVRemote MAJ :: ' .$_data['friendly_name'], __FILE__),
            ));
            return $newtvremote;
        }
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
        $volumeLevelId = $cmd->getId();

        $cmd = $this->getCmd(null, 'volumeset');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Volume Set', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('volumeset');
            $cmd->setType('action');
            $cmd->setSubType('slider');
	        $cmd->setIsVisible(1);
            $cmd->setTemplate('dashboard', 'core::value');
            $cmd->setTemplate('mobile', 'core::value');
            $cmd->setValue($volumeLevelId);
            $cmd->setConfiguration('minValue', 0);
            $cmd->setConfiguration('maxValue', 100);
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
            $cmd->setTemplate('dashboard', 'template::toggle');
            $cmd->setTemplate('mobile', 'template::toggle');
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
            $cmd->setTemplate('dashboard', 'template::toggle');
            $cmd->setTemplate('mobile', 'template::toggle');
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
            $cmd->setDisplay('icon', '<i class="fas fa-volume-down"></i>');
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
            $cmd->setDisplay('icon', '<i class="fas fa-volume-up"></i>');
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

        $cmd = $this->getCmd(null, 'display_name');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Cast App Name', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('display_name');
            $cmd->setType('info');
            $cmd->setSubType('string');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'app_id');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Cast App Id', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('app_id');
            $cmd->setType('info');
            $cmd->setSubType('string');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'last_updated');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Cast Media Updated', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('last_updated');
            $cmd->setType('info');
            $cmd->setSubType('string');
	        $cmd->setIsVisible(1);
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
	        $cmd->setIsVisible(0);
            $cmd->setDisplay('parameters', array("title_disable" => "1", "title_placeholder" => "Options", "message_placeholder" => "Custom Cmd"));
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        if ($this->getIsEnable()) {
            # $this->enableTVRemoteToDaemon();
        } else {
            # $this->disableTVRemoteToDaemon();
        }
    }

    // Fonction exécutée automatiquement avant la suppression de l'équipement
    public function preRemove() {
        # $this->disableTVRemoteToDaemon();
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
            if ($logicalId == "volumeset") {
                log::add('tvremote', 'debug', '[CMD] VolumeSet Keys :: ' . json_encode($_options));
                $googleUUID = $eqLogic->getLogicalId();
                if (isset($googleUUID) && isset($_options['slider'])) {
                    log::add('tvremote', 'debug', '[CMD] VolumeSet :: ' . $_options['slider'] . ' / ' . $googleUUID);
                    # tvremote::actionGCast($googleUUID, "volumeset", $_options['slider']);
                } else {
                    log::add('tvremote', 'debug', '[CMD] VolumeSet :: ERROR = Mauvais paramètre');
                }
            } elseif (in_array($logicalId, ["volumedown", "volumeup", "media_pause", "media_play", "media_stop", "media_previous", "media_next", "media_quit", "media_rewind", "mute_on", "mute_off"])) {
                log::add('tvremote', 'debug', '[CMD] ' . $logicalId . ' :: ' . json_encode($_options));
                $googleUUID = $eqLogic->getLogicalId();
                if (isset($googleUUID)) {
                    # tvremote::actionGCast($googleUUID, $logicalId);
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
