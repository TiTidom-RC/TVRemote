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

try {
    require_once dirname(__FILE__) . "/../../../../core/php/core.inc.php";

    if (!jeedom::apiAccess(init('apikey'), 'tvremote')) { 
        echo __('Vous n\'etes pas autorisé à effectuer cette action', __FILE__);
        die();
    }
    if (init('test') != '') {
        echo 'OK';
        die();
    }
    $result = json_decode(file_get_contents("php://input"), true);
    if (!is_array($result)) {
        die();
    }

    if (isset($result['scanState'])) {
        if ($result['scanState'] == "scanOn") {
            log::add('tvremote', 'debug', '[CALLBACK] scanState = scanOn'); 
            config::save('scanState', 'scanOn', 'tvremote');
            event::add('tvremote::scanState', array(
                'scanState' => 'scanOn')
            );
        } else {
            log::add('tvremote', 'debug', '[CALLBACK] scanState = scanOff'); 
            config::save('scanState', 'scanOff', 'tvremote');
            event::add('tvremote::scanState', array(
                'scanState' => 'scanOff')
            );
            tvremote::sendOnStartTVRemoteToDaemon();
        }
    } elseif (isset($result['heartbeat'])) {
        if ($result['heartbeat'] == 1) {
            log::add('tvremote','info','[CALLBACK] tvremote Daemon Heartbeat (600s)');
        }
    } elseif (isset($result['daemonStarted'])) {
        if ($result['daemonStarted'] == '1') {
            log::add('tvremote', 'info', '[CALLBACK] Daemon Started');
            tvremote::sendOnStartTVRemoteToDaemon();
        }
    } elseif (isset($result['devices'])) {
        log::add('tvremote','debug','[CALLBACK] TVRemote Devices Discovery');
        foreach ($result['devices'] as $key => $data) {
            if (!isset($data['mac'])) {
                log::add('tvremote','debug','[CALLBACK] TVRemote Device :: [MAC] non défini !');
                continue;
            }
            log::add('tvremote','debug','[CALLBACK] TVRemote Device :: ' . $data['friendly_name']);
            if ($data['scanmode'] != 1) {
                log::add('tvremote','debug','[CALLBACK] TVRemote Device :: NoScanMode');
                continue;
            }
            $tv_remote = tvremote::byLogicalId($data['mac'], 'tvremote');
            if (!is_object($tv_remote)) {    
                log::add('tvremote','debug','[CALLBACK] NEW TVRemote détecté :: ' . $data['friendly_name'] . ' (' . $data['mac'] . ')');
                $newtvremote = tvremote::createAndUpdTVRemoteFromScan($data);
            }
            else {
                log::add('tvremote','debug','[CALLBACK] TVRemote Update :: ' . $data['friendly_name'] . ' (' . $data['mac'] . ')');
                $updtvremote = tvremote::createAndUpdTVRemoteFromScan($data);
            }
        }
    } else {
        log::add('tvremote', 'error', '[CALLBACK] unknown message received from daemon'); 
    }
} catch (Exception $e) {
    log::add('tvremote', 'error', displayException($e));
}
