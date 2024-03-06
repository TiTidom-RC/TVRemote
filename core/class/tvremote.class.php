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
    const PYENV_PATH = __DIR__ . '/../../resources/pyenv/bin/pyenv';

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
			'resources/venv', 
            'resources/pyenv'
		];
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
        if (config::byKey('ttsUseExtAddr', 'tvremote') == 1) {
            $cmd .= ' --ttsweb ' . network::getNetworkAccess('external');
        } else {
            $cmd .= ' --ttsweb ' . network::getNetworkAccess('internal');
        }
        $cmd .= ' --apikey ' . jeedom::getApiKey(__CLASS__);
        $cmd .= ' --apittskey ' . jeedom::getApiKey("apitts");
        $cmd .= ' --gcloudapikey ' . config::byKey('gCloudAPIKey', __CLASS__, 'noKey');
        $cmd .= ' --voicerssapikey ' . config::byKey('voiceRSSAPIKey', __CLASS__, 'noKey');
        $cmd .= ' --appdisableding ' . config::byKey('appDisableDing', __CLASS__, '0');
        $cmd .= ' --remotetv ' . config::byKey('remoteTV', __CLASS__, '0');
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
            /* event::add('jeedom::alert', array(
                'level' => 'warning',
                'page' => 'tvremote',
                'message' => __('[sendToDaemon] Exception :: ' . $e->getMessage(), __FILE__),
            )); */
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

    public function enableTVRemoteToDaemon()
    {
        if ($this->getLogicalId() != '') {
            $value = array(
                'cmd' => 'addcast',
                'uuid' => $this->getLogicalId(),
                'host' => $this->getConfiguration('host'),
                'friendly_name' => $this->getConfiguration('friendly_name')
            );
            self::sendToDaemon($value);
        }

    }

    public function disableTVRemoteToDaemon()
    {
        if ($this->getLogicalId() != '') {
            $value = array(
                'cmd' => 'removecast',
                'uuid' => $this->getLogicalId(),
                'host' => $this->getConfiguration('host'),
                'friendly_name' => $this->getConfiguration('friendly_name')
            );
            self::sendToDaemon($value);
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

        $cmd = $this->getCmd(null, 'media_previous');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Previous', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_previous');
            $cmd->setType('action');
            $cmd->setSubType('other');
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

        $cmd = $this->getCmd(null, 'media_next');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Next', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_next');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-step-forward"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'media_quit');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Media Quit', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('media_quit');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->setDisplay('icon', '<i class="fas fa-eject"></i>');
	        $cmd->setIsVisible(1);
            $cmd->setOrder($orderCmd++);
            $cmd->save();
        } else {
            $orderCmd++;
        }

        $cmd = $this->getCmd(null, 'player_state');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Cast Media State', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('player_state');
            $cmd->setType('info');
            $cmd->setSubType('string');
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

        $cmd = $this->getCmd(null, 'status_text');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Cast Status Text', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('status_text');
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

        $cmd = $this->getCmd(null, 'image');
        if (!is_object($cmd)) {
	        $cmd = new tvremoteCmd();
            $cmd->setName(__('Cast Media Image', __FILE__));
            $cmd->setEqLogic_id($this->getId());
	        $cmd->setLogicalId('image');
            $cmd->setType('info');
            $cmd->setSubType('string');
            $cmd->setTemplate('dashboard', 'tvremote::cast-image');
            $cmd->setTemplate('mobile', 'tvremote::cast-image');
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
			if (in_array($logicalId, ["customcmd"])) {
                if (isset($_options['message'])) {
                    log::add('tvremote', 'debug', '[CMD] ' . $logicalId . ' :: ' . json_encode($_options));
                    [$logicalId, $_options] = tvremote::customCmdDecoder($_options['message']);
                    log::add('tvremote', 'debug', '[CMD] ' . $logicalId . ' (Custom Decoded Message) :: ' . json_encode($_options));
                }
                else {
                    log::add('tvremote', 'debug', '[CMD] Il manque un paramètre pour lancer la commande '. $logicalId);
                }                
            }
            
            if ($logicalId == "volumeset") {
                log::add('tvremote', 'debug', '[CMD] VolumeSet Keys :: ' . json_encode($_options));
                $googleUUID = $eqLogic->getLogicalId();
                if (isset($googleUUID) && isset($_options['slider'])) {
                    log::add('tvremote', 'debug', '[CMD] VolumeSet :: ' . $_options['slider'] . ' / ' . $googleUUID);
                    tvremote::actionGCast($googleUUID, "volumeset", $_options['slider']);
                } else {
                    log::add('tvremote', 'debug', '[CMD] VolumeSet :: ERROR = Mauvais paramètre');
                }
            } elseif (in_array($logicalId, ["volumedown", "volumeup", "media_pause", "media_play", "media_stop", "media_previous", "media_next", "media_quit", "media_rewind", "mute_on", "mute_off"])) {
                log::add('tvremote', 'debug', '[CMD] ' . $logicalId . ' :: ' . json_encode($_options));
                $googleUUID = $eqLogic->getLogicalId();
                if (isset($googleUUID)) {
                    tvremote::actionGCast($googleUUID, $logicalId);
                }
            } elseif (in_array($logicalId, ["youtube", "dashcast", "media"])) {
                log::add('tvremote', 'debug', '[CMD] ' . $logicalId . ' :: ' . json_encode($_options));
                $googleUUID = $eqLogic->getLogicalId();
                if (isset($googleUUID) && isset($_options['message'])) {
                    log::add('tvremote', 'debug', '[CMD] ' . $logicalId . ' (Message / GoogleUUID) :: ' . $_options['message'] . " / " . $googleUUID);
                    tvremote::mediaGCast($googleUUID, $logicalId, $_options['message'], $_options['title']);
                }
                else {
                    log::add('tvremote', 'debug', '[CMD] Il manque un paramètre pour lancer la commande '. $logicalId);
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
