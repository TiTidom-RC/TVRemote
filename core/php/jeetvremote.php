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
    if (init('test') !== '') {
        echo 'OK';
        die();
    }
    $result = json_decode(file_get_contents("php://input"), true);
    
    // Gestion des erreurs JSON (important pour PHP 8.4+)
    if (json_last_error() !== JSON_ERROR_NONE) {
        log::add('tvremote', 'error', '[CALLBACK] JSON decode error: ' . json_last_error_msg());
        die();
    }
    
    if (!is_array($result)) {
        log::add('tvremote', 'error', '[CALLBACK] Result is not an array');
        die();
    }
    
    // Log du contenu reçu pour debug
    log::add('tvremote', 'debug', '[CALLBACK] Received data: ' . json_encode($result));

    if (isset($result['scanState'])) {
        if ($result['scanState'] === "scanOn") {
            log::add('tvremote', 'debug', '[CALLBACK] scanState = scanOn'); 
            config::save('scanState', 'scanOn', 'tvremote');
            event::add('tvremote::scanState', array(
                'scanState' => 'scanOn')
            );
            log::add('tvremote', 'debug', '[CALLBACK] event::add tvremote::scanState scanOn sent');
        } else {
            log::add('tvremote', 'debug', '[CALLBACK] scanState = scanOff'); 
            config::save('scanState', 'scanOff', 'tvremote');
            event::add('tvremote::scanState', array(
                'scanState' => 'scanOff')
            );
            log::add('tvremote', 'debug', '[CALLBACK] event::add tvremote::scanState scanOff sent');
            tvremote::sendOnStartTVRemoteToDaemon();
        }
    } elseif (isset($result['heartbeat'])) {
        if ($result['heartbeat'] === 1) {
            log::add('tvremote','info','[CALLBACK] tvremote Daemon Heartbeat (600s)');
        }
    } elseif (isset($result['daemonStarted'])) {
        if ($result['daemonStarted'] === 1) {
            log::add('tvremote', 'info', '[CALLBACK] Daemon Started');
            tvremote::sendOnStartTVRemoteToDaemon();
        }
    } elseif (isset($result['devices'])) {
        log::add('tvremote','debug','[CALLBACK][Discovery] TVRemote Devices');
        foreach ($result['devices'] as $key => $data) {
            if (!isset($data['mac'])) {
                log::add('tvremote','debug','[CALLBACK][Discovery] TVRemote Device :: [MAC] non défini !');
                continue;
            }
            if ($data['scanmode'] !== 1) {
                log::add('tvremote','debug','[CALLBACK][Discovery] TVRemote Device :: NoScanMode');
                continue;
            }
            log::add('tvremote','debug','[CALLBACK][Discovery] TVRemote Device :: ' . $data['friendly_name']);
            $tv_remote = tvremote::byLogicalId($data['mac'], 'tvremote');
            if (!is_object($tv_remote)) {    
                log::add('tvremote','debug','[CALLBACK][Discovery] TVRemote NEW détecté :: ' . $data['friendly_name'] . ' (' . $data['mac'] . ')');
                $scannewtvremote = tvremote::createAndUpdTVRemoteFromScan($data);
            }
            else {
                log::add('tvremote','debug','[CALLBACK][Discovery] TVRemote UPDATE détecté :: ' . $data['friendly_name'] . ' (' . $data['mac'] . ')');
                $scanupdtvremote = tvremote::createAndUpdTVRemoteFromScan($data);
            }
        }
    } elseif (isset($result['adb_shell_output_mac']) && isset($result['adb_shell_output_value'])) {
        log::add('tvremote', 'debug', '[CALLBACK][ADB Shell Output] MAC :: ' . $result['adb_shell_output_mac']);
        $tv_remote = tvremote::byLogicalId($result['adb_shell_output_mac'], 'tvremote');
        if (is_object($tv_remote)) {
            // Check if a specific cmd_id is provided (for custom ADB Shell info commands)
            if (isset($result['adb_shell_output_cmd_id'])) {
                $cmd = cmd::byId($result['adb_shell_output_cmd_id']);
                if (is_object($cmd)) {
                    $tv_remote->checkAndUpdateCmd($cmd, $result['adb_shell_output_value']);
                    log::add('tvremote', 'info', '[CALLBACK][ADB Shell Output] Updated cmd #' . $result['adb_shell_output_cmd_id'] . ' for ' . $tv_remote->getName() . ' [:100] :: ' . substr($result['adb_shell_output_value'], 0, 100));
                } else {
                    log::add('tvremote', 'warning', '[CALLBACK][ADB Shell Output] Command not found :: cmd_id=' . $result['adb_shell_output_cmd_id']);
                }
            } else {
                // Fallback to default adb_shell_output command
                $cmd = $tv_remote->getCmd('info', 'adb_shell_output');
                if (is_object($cmd)) {
                    $cmd->event($result['adb_shell_output_value']);
                    log::add('tvremote', 'info', '[CALLBACK][ADB Shell Output] Updated for ' . $tv_remote->getName() . ' [:100] :: ' . substr($result['adb_shell_output_value'], 0, 100));
                }
            }
        }
    } elseif (isset($result['devicesRT'])) {
        log::add('tvremote','debug','[CALLBACK] TVRemote Devices RealTime');
        foreach ($result['devicesRT'] as $key => $data) {
            if (!isset($data['mac'])) {
                log::add('tvremote','debug','[CALLBACK] TVRemote RealTime :: [MAC] non défini !');
                continue;
            }
            log::add('tvremote','debug','[CALLBACK] TVRemote RealTime :: ' . $data['mac']);
            if ($data['realtime'] !== 1) {
                continue;
            }
            $tv_remote = tvremote::byLogicalId($data['mac'], 'tvremote');
            if (!is_object($tv_remote)) {    
                continue;
            }
            else {
                $rtDevice = tvremote::realtimeUpdateDevice($data);
            }
        }
    } elseif (isset($result['PairingExc'])) {
        log::add('tvremote','debug','[CALLBACK] TVRemote Pairing Exception');
        
            if (!isset($result['pairing_mac'])) {
                log::add('tvremote','debug','[CALLBACK] TVRemote Pairing Exception :: [MAC] non défini !');
                return;
            }
            log::add('tvremote','debug','[CALLBACK] TVRemote Pairing Exception :: ' . $result['pairing_mac']);
            $tv_remote = tvremote::byLogicalId($result['pairing_mac'], 'tvremote');
            if (!is_object($tv_remote)) {    
                return;
            }
            else {
                $pairingExc = tvremote::pairingException($result);
            }
    } elseif (isset($result['adb_paired'])) {
        log::add('tvremote', 'debug', '[CALLBACK] ADB Pairing Result');
        
        if (!isset($result['mac'])) {
            log::add('tvremote', 'debug', '[CALLBACK] ADB Pairing Result :: [MAC] non défini !');
            return;
        }
        
        log::add('tvremote', 'debug', '[CALLBACK] ADB Pairing Result :: ' . $result['mac'] . ' :: ' . ($result['adb_paired'] === 1 ? 'SUCCESS' : 'FAILED'));
        
        // Update equipment configuration with pairing status
        $tv_remote = tvremote::byLogicalId($result['mac'], 'tvremote');
        if (is_object($tv_remote)) {
            $tv_remote->setConfiguration('adb_paired_status', $result['adb_paired']);
            $tv_remote->save();
            log::add('tvremote', 'debug', '[CALLBACK] ADB Pairing Status saved :: ' . $result['mac'] . ' :: ' . $result['adb_paired']);
            
            // Get friendly name for user-friendly message
            $friendlyName = $tv_remote->getConfiguration('friendly_name', $tv_remote->getName());
            
            // Send event to JavaScript only if equipment exists
            event::add('tvremote::adbPairingResult', array(
                'mac' => $result['mac'],
                'friendly_name' => $friendlyName,
                'adb_paired' => $result['adb_paired'],
                'message' => isset($result['message']) ? $result['message'] : ''
            ));
            
            // Log the message if present
            if (isset($result['message'])) {
                if ($result['adb_paired'] === 1) {
                    log::add('tvremote', 'info', '[CALLBACK] ADB Pairing :: ' . $friendlyName . ' :: ' . $result['message']);
                } else {
                    log::add('tvremote', 'warning', '[CALLBACK] ADB Pairing :: ' . $friendlyName . ' :: ' . $result['message']);
                }
            }
        } else {
            log::add('tvremote', 'debug', '[CALLBACK] ADB Pairing :: Equipment not found in Jeedom :: ' . $result['mac']);
        }
    } elseif (isset($result['adb_auth_revoked'])) {
        log::add('tvremote', 'warning', '[CALLBACK] ADB Authorization Revoked');
        
        if (!isset($result['mac'])) {
            log::add('tvremote', 'debug', '[CALLBACK] ADB Auth Revoked :: [MAC] non défini !');
            return;
        }
        
        log::add('tvremote', 'warning', '[CALLBACK] ADB Authorization Revoked :: ' . $result['mac']);
        
        // Reset pairing status - authorization has been revoked from TV
        $tv_remote = tvremote::byLogicalId($result['mac'], 'tvremote');
        if (is_object($tv_remote)) {
            $tv_remote->setConfiguration('adb_paired_status', 0);
            $tv_remote->save();
            log::add('tvremote', 'warning', '[CALLBACK] ADB Pairing Status reset due to revocation :: ' . $result['mac']);
            
            // Get friendly name for user-friendly message
            $friendlyName = $tv_remote->getConfiguration('friendly_name', $tv_remote->getName());
            
            // Send event to JavaScript only if equipment exists
            event::add('tvremote::adbPairingResult', array(
                'mac' => $result['mac'],
                'friendly_name' => $friendlyName,
                'adb_paired' => 0,
                'message' => 'Authorization revoked from TV. Please pair again.'
            ));
        } else {
            log::add('tvremote', 'debug', '[CALLBACK] ADB Auth Revoked :: Equipment not found in Jeedom :: ' . $result['mac']);
        }
    } elseif (isset($result['pairing_value'])) {
        log::add('tvremote', 'debug', '[CALLBACK] TVRemote Pairing Error');
        
        if (!isset($result['pairing_mac'])) {
            log::add('tvremote', 'debug', '[CALLBACK] TVRemote Pairing Error :: [MAC] non défini !');
            return;
        }
        
        log::add('tvremote', 'warning', '[CALLBACK] TVRemote Not Paired :: ' . $result['pairing_mac'] . ' :: ' . (isset($result['PairingExc']) ? $result['PairingExc'] : 'Unknown error'));
        
        // Update equipment configuration with pairing status
        $tv_remote = tvremote::byLogicalId($result['pairing_mac'], 'tvremote');
        if (is_object($tv_remote)) {
            $tv_remote->setConfiguration('tvremote_paired_status', $result['pairing_value']);
            $tv_remote->save();
            log::add('tvremote', 'debug', '[CALLBACK] TVRemote Pairing Status saved :: ' . $result['pairing_mac'] . ' :: ' . $result['pairing_value']);
            
            // Get friendly name for user-friendly message
            $friendlyName = $tv_remote->getConfiguration('friendly_name', $tv_remote->getName());
            
            // Send event to JavaScript only if equipment exists
            event::add('tvremote::tvremotePairingResult', array(
                'mac' => $result['pairing_mac'],
                'friendly_name' => $friendlyName,
                'tvremote_paired' => $result['pairing_value'],
                'message' => isset($result['PairingExc']) ? $result['PairingExc'] : 'Device not paired. Please start pairing procedure.'
            ));
        } else {
            log::add('tvremote', 'debug', '[CALLBACK] TVRemote Pairing Error :: Equipment not found in Jeedom :: ' . $result['pairing_mac']);
        }
    } elseif (isset($result['tvremote_paired'])) {
        log::add('tvremote', 'debug', '[CALLBACK] TVRemote Pairing Result');
        
        if (!isset($result['mac'])) {
            log::add('tvremote', 'debug', '[CALLBACK] TVRemote Pairing Result :: [MAC] non défini !');
            return;
        }
        
        log::add('tvremote', 'debug', '[CALLBACK] TVRemote Pairing Result :: ' . $result['mac'] . ' :: ' . ($result['tvremote_paired'] === 1 ? 'SUCCESS' : 'FAILED'));
        
        // Update equipment configuration with pairing status
        $tv_remote = tvremote::byLogicalId($result['mac'], 'tvremote');
        if (is_object($tv_remote)) {
            $tv_remote->setConfiguration('tvremote_paired_status', $result['tvremote_paired']);
            $tv_remote->save();
            log::add('tvremote', 'debug', '[CALLBACK] TVRemote Pairing Status saved :: ' . $result['mac'] . ' :: ' . $result['tvremote_paired']);
            
            // Get friendly name for user-friendly message
            $friendlyName = $tv_remote->getConfiguration('friendly_name', $tv_remote->getName());
            
            // Send event to JavaScript only if equipment exists
            event::add('tvremote::tvremotePairingResult', array(
                'mac' => $result['mac'],
                'friendly_name' => $friendlyName,
                'tvremote_paired' => $result['tvremote_paired'],
                'message' => isset($result['message']) ? $result['message'] : ''
            ));
            
            // Log the message if present
            if (isset($result['message'])) {
                if ($result['tvremote_paired'] === 1) {
                    log::add('tvremote', 'info', '[CALLBACK] TVRemote Pairing :: ' . $friendlyName . ' :: ' . $result['message']);
                } else {
                    log::add('tvremote', 'warning', '[CALLBACK] TVRemote Pairing :: ' . $friendlyName . ' :: ' . $result['message']);
                }
            }
        } else {
            log::add('tvremote', 'debug', '[CALLBACK] TVRemote Pairing :: Equipment not found in Jeedom :: ' . $result['mac']);
        }
    } else {
        log::add('tvremote', 'error', '[CALLBACK] unknown message received from daemon'); 
    }
} catch (Exception $e) {
    log::add('tvremote', 'error', displayException($e));
}
