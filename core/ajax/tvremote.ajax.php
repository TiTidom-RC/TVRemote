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
    require_once dirname(__FILE__) . '/../../../../core/php/core.inc.php';
    include_file('core', 'authentification', 'php');

    if (!isConnect('admin')) {
        throw new Exception(__('401 - Accès non autorisé', __FILE__));
    }

    /* Fonction permettant l'envoi de l'entête 'Content-Type: application/json'
     En V3 : indiquer l'argument 'true' pour contrôler le token d'accès Jeedom
     En V4 : autoriser l'exécution d'une méthode 'action' en GET en indiquant le(s) nom(s) de(s) action(s) dans un tableau en argument
    */
    ajax::init(array());

    if (init('action') == 'resetTVCertKey') {
        $certfilepath = __DIR__ . "/../../data/config/tvremote_cert.pem";
        $keyfilepath = __DIR__ . "/../../data/config/tvremote_key.pem";
        if (!file_exists($certfilepath) || !file_exists($keyfilepath)) {
            throw new Exception('[RESET][TVCertKey] Fichier(s) introuvable(s) ::<br />' . $certfilepath . '<br />' . $keyfilepath);
        }
        log::add('tvremote', 'debug', "[RESET][TVCertKey] Cert / Key filepath :: {$certfilepath} / {$keyfilepath}");
        unlink($certfilepath);
        unlink($keyfilepath);
        ajax::success("{$certfilepath}<br />{$keyfilepath}");
    }
    elseif (init('action') == 'changeScanState') {
        tvremote::changeScanState(init('scanState'));
        ajax::success();
    }
    elseif (init('action') == 'beginPairing') {
        ajax::success(tvremote::sendBeginPairing(init('mac'), init('host'), init('port')));
    }
    elseif (init('action') == 'sendPairCode') {
        ajax::success(tvremote::sendPairCode(init('mac'), init('host'), init('port'), init('paircode')));
    }

    throw new Exception(__('Aucune méthode correspondante à', __FILE__) . ' : ' . init('action'));
    /*     * *********Catch exeption*************** */
} catch (Exception $e) {
    ajax::error(displayException($e), $e->getCode());
}
