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

require_once dirname(__FILE__) . '/../../../core/php/core.inc.php';

// Fonction exécutée automatiquement après l'installation du plugin
function tvremote_install() {
    $pluginVersion = tvremote::getPluginVersion();
    config::save('pluginVersion', $pluginVersion, 'tvremote');

    message::removeAll('tvremote');
    message::add('tvremote', 'Installation du plugin TV Remote (Version : ' . $pluginVersion . ')', null, null);

    tvremote::getPythonDepFromRequirements();

    if (config::byKey('pythonVersion', 'tvremote') == '') {
        config::save('pythonVersion', '?.?.?', 'tvremote');
    }
    if (config::byKey('pyenvVersion', 'tvremote') == '') {
        config::save('pyenvVersion', '?.?.?', 'tvremote');
    }
    if (config::byKey('socketport', 'tvremote') == '') {
        config::save('socketport', '55112', 'tvremote');
    }
    if (config::byKey('cyclefactor', 'tvremote') == '') {
        config::save('cyclefactor', '1.0', 'tvremote');
    }
    if (config::byKey('debugInstallUpdates', 'tvremote') == '') {
        config::save('debugInstallUpdates', '0', 'tvremote');
    }
    if (config::byKey('debugRestorePyEnv', 'tvremote') == '') {
        config::save('debugRestorePyEnv', '0', 'tvremote');
    }
    if (config::byKey('debugRestoreVenv', 'tvremote') == '') {
        config::save('debugRestoreVenv', '0', 'tvremote');
    }
    if (config::byKey('disableUpdateMsg', 'tvremote') == '') {
        config::save('disableUpdateMsg', '0', 'tvremote');
    }

    $dependencyInfo = tvremote::dependancy_info();
    if (!isset($dependencyInfo['state'])) {
        message::add('tvremote', __('Veuillez vérifier les dépendances', __FILE__));
    } elseif ($dependencyInfo['state'] === 'nok') {
        try {
            $plugin = plugin::byId('tvremote');
            $plugin->dependancy_install();
        } catch (\Throwable $th) {
            message::add('tvremote', __('Une erreur est survenue à la mise à jour automatique des dépendances. Vérifiez les logs et relancez les dépendances manuellement', __FILE__));
        }
    }
}

// Fonction exécutée automatiquement après la mise à jour du plugin
function tvremote_update() {
    $pluginVersion = tvremote::getPluginVersion();
    config::save('pluginVersion', $pluginVersion, 'tvremote');

    if (config::byKey('disableUpdateMsg', 'tvremote', '0') === '0') {
        message::removeAll('tvremote');
        message::add('tvremote', 'Mise à jour du plugin TV Remote (Version : ' . $pluginVersion . ')', null, null);
    }

    tvremote::getPythonDepFromRequirements();

    if (config::byKey('pythonVersion', 'tvremote') == '') {
        config::save('pythonVersion', '?.?.?', 'tvremote');
    }
    if (config::byKey('pyenvVersion', 'tvremote') == '') {
        config::save('pyenvVersion', '?.?.?', 'tvremote');
    }
    if (config::byKey('socketport', 'tvremote') == '') {
        config::save('socketport', '55112', 'tvremote');
    }
    if (config::byKey('cyclefactor', 'tvremote') == '') {
        config::save('cyclefactor', '1.0', 'tvremote');
    }
    if (config::byKey('debugInstallUpdates', 'tvremote') == '') {
        config::save('debugInstallUpdates', '0', 'tvremote');
    }
    if (config::byKey('debugRestorePyEnv', 'tvremote') == '') {
        config::save('debugRestorePyEnv', '0', 'tvremote');
    }
    if (config::byKey('debugRestoreVenv', 'tvremote') == '') {
        config::save('debugRestoreVenv', '0', 'tvremote');
    }
    if (config::byKey('disableUpdateMsg', 'tvremote') == '') {
        config::save('disableUpdateMsg', '0', 'tvremote');
    }

    $dependencyInfo = tvremote::dependancy_info();
    if (!isset($dependencyInfo['state'])) {
        message::add('tvremote', __('Veuillez vérifier les dépendances', __FILE__));
    } elseif ($dependencyInfo['state'] === 'nok') {
        try {
            $plugin = plugin::byId('tvremote');
            $plugin->dependancy_install();
        } catch (\Throwable $th) {
            message::add('tvremote', __('Une erreur est survenue à la mise à jour automatique des dépendances. Vérifiez les logs et relancez les dépendances manuellement', __FILE__));
        }
    }

    // Nettoyage des anciens fichiers et répertoires obsolètes
    $pluginDir = dirname(__DIR__);
    try {
        $pathsToRemove = array(
            // Accepte fichiers ET répertoires (rm -rf) — ajouter ici les chemins à supprimer à chaque mise à jour
            $pluginDir . '/core/php/.htaccess',
        );
        $cleanupRemoved = 0;
        $cleanupErrors = 0;
        foreach ($pathsToRemove as $path) {
            if (file_exists($path)) {
                $output = array();
                $returnVar = 0;
                exec('rm -rf ' . escapeshellarg($path) . ' 2>&1', $output, $returnVar);
                if ($returnVar !== 0) {
                    $cleanupErrors++;
                    log::add('tvremote', 'warning', '[CLEANUP_KO] Echec suppression "' . $path . '" (Code: ' . $returnVar . ') : ' . implode(' ', $output));
                } else {
                    $cleanupRemoved++;
                    log::add('tvremote', 'info', '[CLEANUP_OK] Chemin supprimé : ' . $path);
                }
            }
        }
        $cleanupSummary = count($pathsToRemove) . ' chemin(s) vérifié(s), ' . $cleanupRemoved . ' supprimé(s)';
        if ($cleanupErrors > 0) {
            $cleanupSummary .= ', ' . $cleanupErrors . ' erreur(s)';
        }
        log::add('tvremote', 'debug', '[CLEANUP] ' . $cleanupSummary);
    } catch (Exception $e) {
        log::add('tvremote', 'warning', '[CLEANUP_KO] Erreur lors du nettoyage : ' . $e->getMessage());
    }
}

// Fonction exécutée automatiquement après la suppression du plugin
function tvremote_remove() {

}
