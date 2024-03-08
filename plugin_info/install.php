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
    message::add('tvremote', 'Installation du plugin TTS Cast (Version : ' . $pluginVersion . ')', null, null);

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
    if (config::byKey('ttsEngine', 'tvremote') == '') {
        config::save('ttsEngine', 'jeedomtts', 'tvremote');
    }
    if (config::byKey('ttsLang', 'tvremote') == '') {
        config::save('ttsLang', 'fr-FR', 'tvremote');
    }
    if (config::byKey('gCloudTTSSpeed', 'tvremote') == '') {
        config::save('gCloudTTSSpeed', '1.0', 'tvremote');
    }
    if (config::byKey('gCloudTTSVoice', 'tvremote') == '') {
        config::save('gCloudTTSVoice', 'fr-FR-Standard-A', 'tvremote');
    }
    if (config::byKey('ttsPurgeCacheDays', 'tvremote') == '') {
        config::save('ttsPurgeCacheDays', '10', 'tvremote');
    }
    if (config::byKey('appDisableDing', 'tvremote') == '') {
        config::save('appDisableDing', '0', 'tvremote');
    }
    if (config::byKey('remoteTV', 'tvremote') == '') {
        config::save('remoteTV', '1', 'tvremote');
    }

    $dependencyInfo = tvremote::dependancy_info();
    if (!isset($dependencyInfo['state'])) {
        message::add('tvremote', __('Veuillez vérifier les dépendances', __FILE__));
    } elseif ($dependencyInfo['state'] == 'nok') {
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

    message::removeAll('tvremote');
    message::add('tvremote', 'Mise à jour du plugin TTS Cast (Version : ' . $pluginVersion . ')', null, null);

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
    if (config::byKey('ttsEngine', 'tvremote') == '') {
        config::save('ttsEngine', 'jeedomtts', 'tvremote');
    }
    if (config::byKey('ttsLang', 'tvremote') == '') {
        config::save('ttsLang', 'fr-FR', 'tvremote');
    }
    if (config::byKey('gCloudTTSSpeed', 'tvremote') == '') {
        config::save('gCloudTTSSpeed', '1.0', 'tvremote');
    }
    if (config::byKey('gCloudTTSVoice', 'tvremote') == '') {
        config::save('gCloudTTSVoice', 'fr-FR-Standard-A', 'tvremote');
    }
    if (config::byKey('ttsPurgeCacheDays', 'tvremote') == '') {
        config::save('ttsPurgeCacheDays', '10', 'tvremote');
    }
    if (config::byKey('appDisableDing', 'tvremote') == '') {
        config::save('appDisableDing', '0', 'tvremote');
    }
    if (config::byKey('remoteTV', 'tvremote') == '') {
        config::save('remoteTV', '1', 'tvremote');
    }

    $dependencyInfo = tvremote::dependancy_info();
    if (!isset($dependencyInfo['state'])) {
        message::add('tvremote', __('Veuillez vérifier les dépendances', __FILE__));
    } elseif ($dependencyInfo['state'] == 'nok') {
        try {
            $plugin = plugin::byId('tvremote');
            $plugin->dependancy_install();
        } catch (\Throwable $th) {
            message::add('tvremote', __('Une erreur est survenue à la mise à jour automatique des dépendances. Vérifiez les logs et relancez les dépendances manuellement', __FILE__));
        }
    }
}

// Fonction exécutée automatiquement après la suppression du plugin
function tvremote_remove() {

}
