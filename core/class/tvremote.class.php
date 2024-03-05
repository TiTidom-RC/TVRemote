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
    public static function deamon_info() {
        $return = array();
        $return['log'] = __CLASS__;
        $return['launchable'] = 'ok';
        $return['state'] = 'nok';
        $pid_file = jeedom::getTmpFolder(__CLASS__) . '/daemon.pid';
        if (file_exists($pid_file)) {
            if (@posix_getsid(trim(file_get_contents($pid_file)))) {
                $return['state'] = 'ok';
            } else {
                shell_exec(system::getCmdSudo() . 'rm -rf ' . $pid_file . ' 2>&1 > /dev/null');
            }
        }
        return $return;
    }

    public static function deamon_start() {
        self::deamon_stop();
        $deamon_info = self::deamon_info();
        if ($deamon_info['launchable'] != 'ok') {
            throw new Exception(__('Veuillez vérifier la configuration', __FILE__));
        }

        config::remove('discovered_data_topics', __CLASS__);

        $path = realpath(dirname(__FILE__) . '/../../resources/tvremoted');
        $cmd = "python3 {$path}/tvremoted.py";
        $cmd .= ' --loglevel ' . log::convertLogLevel(log::getLogLevel(__CLASS__));
        $cmd .= ' --socketport ' . 55009;
        $cmd .= ' --cycle ' . config::byKey('cycle', __CLASS__, 2);
        $cmd .= ' --callback ' . network::getNetworkAccess('internal', 'proto:127.0.0.1:port:comp') . '/plugins/tvremote/core/php/jeetvremote.php';
        $cmd .= ' --apikey ' . jeedom::getApiKey(__CLASS__);
        $cmd .= ' --pid ' . jeedom::getTmpFolder(__CLASS__) . '/daemon.pid';
        log::add(__CLASS__, 'info', 'Lancement démon');
        $result = exec($cmd . ' >> ' . log::getPathToLog(__CLASS__ . '_daemon') . ' 2>&1 &');
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
            log::add(__CLASS__, 'error', __('Impossible de lancer le démon', __FILE__), 'unableStartDeamon');
            return false;
        }
        message::removeAll(__CLASS__, 'unableStartDeamon');

        return true;
    }

    public static function deamon_stop() {
        $pid_file = jeedom::getTmpFolder(__CLASS__) . '/daemon.pid';
        if (file_exists($pid_file)) {
            $pid = intval(trim(file_get_contents($pid_file)));
            system::kill($pid);
        }
        sleep(1);
        system::kill('tvremoted.py');
        // system::fuserk(config::byKey('socketport', __CLASS__));
        sleep(1);
    }

    public static function handleFeedback($message) {
        log::add(__CLASS__, 'debug', 'new feedback:' . json_encode($message));

        $eqLogic = eqLogic::byLogicalId('tvremote', __CLASS__);
        if (!is_object($eqLogic)) {
            $eqLogic = new self();
            $eqLogic->setLogicalId('tvremote');
            $eqLogic->setEqType_name(__CLASS__);
            $eqLogic->setIsEnable(1);
            $eqLogic->setIsVisible(1);
            $eqLogic->setName('tvremote');
            $eqLogic->save();
        }

        foreach ($message as $key => $value) {
            if ($key == 'alert') {
                event::add('jeedom::alert', array(
                    'level' => 'success',
                    'page' => 'tvremote',
                    'message' => $value
                ));
            }
            $eqLogic->checkAndUpdateCmd($key, $value);
        }
    }

    public function postInsert() {
        $info = ['pingpong', 'Cat', 'Dog', 'Duck', 'Sheep', 'Horse', 'Cow', 'Goat', 'Rabbit'];
        foreach ($info as $id) {
            $cmd = $this->getCmd('info', $id);
            if (!is_object($cmd)) {
                $cmd = new tvremoteCmd();
                $cmd->setLogicalId($id);
                $cmd->setEqLogic_id($this->getId());
                $cmd->setName($id);
                $cmd->setType('info');
                $cmd->setSubType('string');
                $cmd->save();
            }
        }

        $cmd = $this->getCmd('action', 'ping');
        if (!is_object($cmd)) {
            $cmd = new tvremoteCmd();
            $cmd->setLogicalId('ping');
            $cmd->setEqLogic_id($this->getId());
            $cmd->setName('ping');
            $cmd->setType('action');
            $cmd->setSubType('other');
            $cmd->save();
        }

        $cmd = $this->getCmd('action', 'think');
        if (!is_object($cmd)) {
            $cmd = new tvremoteCmd();
            $cmd->setLogicalId('think');
            $cmd->setEqLogic_id($this->getId());
            $cmd->setName('think');
            $cmd->setType('action');
            $cmd->setSubType('message');
            $cmd->save();
        }
    }

    public static function sendToDaemon($params) {
        log::add(__CLASS__, 'debug', 'params to send to daemon:' . json_encode($params));
        $params['apikey'] = jeedom::getApiKey(__CLASS__);
        $payLoad = json_encode($params);
        $socket = socket_create(AF_INET, SOCK_STREAM, SOL_TCP);
        socket_connect($socket, '127.0.0.1', 55009);
        socket_write($socket, $payLoad, strlen($payLoad));
        socket_close($socket);
    }
}

class tvremoteCmd extends cmd {
    // Exécution d'une commande
    public function execute($_options = array()) {
        $params = [
            'action' => $this->getLogicalId()
        ];
        switch ($this->getSubType()) {
            case 'message':
                $params['message'] = !empty($_options['message']) ? $_options['message'] : "Async IO is amazing";
                break;
        }
        tvremote::sendToDaemon($params);
    }
}
