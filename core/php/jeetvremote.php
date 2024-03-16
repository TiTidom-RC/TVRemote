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
            # tvremote::sendOnStartCastToDaemon();

        }
    } elseif (isset($result['heartbeat'])) {
        if ($result['heartbeat'] == 1) {
            log::add('tvremote','info','[CALLBACK] tvremote Daemon Heartbeat (600s)');
        }
    } elseif (isset($result['daemonStarted'])) {
        if ($result['daemonStarted'] == '1') {
            log::add('tvremote', 'info', '[CALLBACK] Daemon Started');
            # tvremote::sendOnStartCastToDaemon();
        }
    } else {
        log::add('tvremote', 'error', '[CALLBACK] unknown message received from daemon'); 
    }
} catch (Exception $e) {
    log::add('tvremote', 'error', displayException($e));
}
