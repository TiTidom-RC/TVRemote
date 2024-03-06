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
            tvremote::sendOnStartCastToDaemon();

        }
    } elseif (isset($result['heartbeat'])) {
        if ($result['heartbeat'] == 1) {
            log::add('tvremote','info','[CALLBACK] tvremote Daemon Heartbeat (600s)');
        }
    } elseif (isset($result['daemonStarted'])) {
        if ($result['daemonStarted'] == '1') {
            log::add('tvremote', 'info', '[CALLBACK] Daemon Started');
            tvremote::sendOnStartCastToDaemon();
        }
    } elseif (isset($result['actionReturn'])) {
        log::add('tvremote','debug','[CALLBACK] tvremote ActionReturn :: ' . json_encode($result));
        if ($result['actionReturn'] == "setvolume" || $result['actionReturn'] == "volumeup" || $result['actionReturn'] == "volumedown") {
            if (!isset($result['uuid']) || !isset($result['volumelevel'])) {
                log::add('tvremote','debug','[CALLBACK] Action Return Volume :: UUID et/ou VolumeLevel non défini(s) !');
            } else {
                log::add('tvremote','debug','[CALLBACK] Action Return Volume :: Les paramètres sont bien définis...');
                $tvremote = tvremote::byLogicalId($result['uuid'], 'tvremote');
                if (is_object($tvremote)) { 
                    log::add('tvremote','debug','[CALLBACK] Action Return Volume :: Le Cast a été trouvé...');
                    $cmd = $tvremote->getCmd('info', 'volumelevel');
                    if (is_object($cmd)) {
                        log::add('tvremote','debug','[CALLBACK] Action Return Volume :: SetVolume in Config :: ' . $result['volumelevel']);
                        $cmd->event($result['volumelevel']);
                    }
                }
            }
        } else {
            log::add('tvremote','debug','[CALLBACK] Action Return :: ERROR SetVolume Return...');
        }
        
            
    } elseif (isset($result['devices'])) {
        log::add('tvremote','debug','[CALLBACK] tvremote Devices Discovery');
        foreach ($result['devices'] as $key => $data) {
            if (!isset($data['uuid'])) {
                log::add('tvremote','debug','[CALLBACK] tvremote Device :: UUID non défini !');
                continue;
            }
            log::add('tvremote','debug','[CALLBACK] tvremote Device :: ' . $data['uuid']);
            if ($data['scanmode'] != 1) {
                log::add('tvremote','debug','[CALLBACK] tvremote Device :: NoScanMode');
                continue;
            }
            $tvremote = tvremote::byLogicalId($data['uuid'], 'tvremote');
            if (!is_object($tvremote)) {    
                log::add('tvremote','debug','[CALLBACK] NEW tvremote détecté :: ' . $data['friendly_name'] . ' (' . $data['uuid'] . ')');
                /* event::add('tvremote::newdevice', array(
                    'friendly_name' => $data['friendly_name'],
                    'newone' => '1'
                )); */
                $newtvremote = tvremote::createAndUpdCastFromScan($data);
            }
            else {
                log::add('tvremote','debug','[CALLBACK] tvremote Update :: ' . $data['friendly_name'] . ' (' . $data['uuid'] . ')');
                /* event::add('tvremote::newdevice', array(
                    'friendly_name' => $data['friendly_name'],
                    'newone' => '0'
                )); */
                $updtvremote = tvremote::createAndUpdCastFromScan($data);
            }
        }
    } elseif (isset($result['casts'])) {
        log::add('tvremote','debug','[CALLBACK] tvremote Schedule');
        foreach ($result['casts'] as $key => $data) {
            if (!isset($data['uuid'])) {
                log::add('tvremote','debug','[CALLBACK] tvremote Schedule :: UUID non défini !');
                continue;
            }
            log::add('tvremote','debug','[CALLBACK] tvremote Schedule :: ' . $data['uuid']);
            if ($data['schedule'] != 1) {
                # log::add('tvremote','debug','[CALLBACK] tvremote Schedule :: NoScheduleMode');
                continue;
            }
            # log::add('tvremote','debug','[CALLBACK] tvremote Schedule Volume :: ' . $data['uuid'] . ' = ' . $data['volume_level']);

            $tvremote = tvremote::byLogicalId($data['uuid'], 'tvremote');
            if (!is_object($tvremote)) {    
                # log::add('tvremote','debug','[CALLBACK] tvremote Schedule NON EXIST :: ' . $data['uuid']);
                continue;
            }
            else {
                $updtvremote = tvremote::scheduleUpdateCast($data);
            }
        }
    } elseif (isset($result['castsRT'])) {
        log::add('tvremote','debug','[CALLBACK] tvremote RealTime');
        foreach ($result['castsRT'] as $key => $data) {
            if (!isset($data['uuid'])) {
                log::add('tvremote','debug','[CALLBACK] tvremote RealTime :: UUID non défini !');
                continue;
            }
            log::add('tvremote','debug','[CALLBACK] tvremote RealTime :: ' . $data['uuid']);
            if ($data['realtime'] != 1) {
                # log::add('tvremote','debug','[CALLBACK] tvremote RealTime :: NoRealTimeMode');
                continue;
            }
            $tvremote = tvremote::byLogicalId($data['uuid'], 'tvremote');
            if (!is_object($tvremote)) {    
                # log::add('tvremote','debug','[CALLBACK] tvremote RealTime NON EXIST :: ' . $data['uuid']);
                continue;
            }
            else {
                $rtcast = tvremote::realtimeUpdateCast($data);
            }
        }
    } else {
        log::add('tvremote', 'error', '[CALLBACK] unknown message received from daemon'); 
    }
} catch (Exception $e) {
    log::add('tvremote', 'error', displayException($e));
}
