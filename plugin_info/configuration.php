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
include_file('core', 'authentification', 'php');
if (!isConnect()) {
    include_file('desktop', '404', 'php');
    die();
}
?>
<form class="form-horizontal">
    <fieldset>
        <div>
            <legend><i class="fas fa-info"></i> {{Plugin}}</legend>
            <div class="form-group">
                <label class="col-lg-3 control-label">{{Version Plugin}}
                    <sup><i class="fas fa-question-circle tooltips" title="{{Version du Plugin (A indiquer sur Community)}}"></i></sup>
                </label>
                <div class="col-lg-1">
                    <input class="configKey form-control" data-l1key="pluginVersion" readonly />
                </div>
            </div>
            <div class="form-group">
                <label class="col-lg-3 control-label">{{Version PyEnv}}
                    <sup><i class="fas fa-question-circle tooltips" title="{{Version de PyEnv utilisée par le Plugin (A indiquer sur Community)}}"></i></sup>
                </label>
                <div class="col-lg-1">
                    <input class="configKey form-control" data-l1key="pyenvVersion" readonly />
                </div>
            </div>
            <div class="form-group">
                <label class="col-lg-3 control-label">{{Version Python}}
                    <sup><i class="fas fa-question-circle tooltips" title="{{Version de Python utilisée par le Plugin (A indiquer sur Community)}}"></i></sup>
                </label>
                <div class="col-lg-1">
                    <input class="configKey form-control" data-l1key="pythonVersion" readonly />
                </div>
            </div>
            <legend><i class="fas fa-code"></i> {{Dépendances}}</legend>
            <div class="form-group">
                <label class="col-lg-3 control-label">{{Force les mises à jour Systèmes}}
                    <sup><i class="fas fa-ban tooltips" style="color:var(--al-danger-color)!important;" title="{{Les dépendances devront être relancées après la sauvegarde de ce paramètre}}"></i></sup>    
                    <sup><i class="fas fa-question-circle tooltips" title="{{Permet de forcer l'installation des mises à jour systèmes}}"></i></sup>
                </label>
                <div class="col-lg-2">
                    <input type="checkbox" class="configKey" data-l1key="debugInstallUpdates" />
                </div>
            </div>
            <div class="form-group">
                <label class="col-lg-3 control-label">{{Force la réinitialisation de PyEnv}}
                    <sup><i class="fas fa-ban tooltips" style="color:var(--al-danger-color)!important;" title="{{Les dépendances devront être relancées après la sauvegarde de ce paramètre}}"></i></sup>    
                    <sup><i class="fas fa-question-circle tooltips" title="{{Permet de forcer la réinitilsation de l'environnement Python utilisé par le plugin}}"></i></sup>
                </label>
                <div class="col-lg-2">
                    <input type="checkbox" class="configKey" data-l1key="debugRestorePyEnv" />
                </div>
            </div>
            <div class="form-group">
                <label class="col-lg-3 control-label">{{Force la réinitialisation de Venv}}
                    <sup><i class="fas fa-ban tooltips" style="color:var(--al-danger-color)!important;" title="{{Les dépendances devront être relancées après la sauvegarde de ce paramètre}}"></i></sup>    
                    <sup><i class="fas fa-question-circle tooltips" title="{{Permet de forcer la réinitilsation de l'environnement Venv utilisé par le plugin}}"></i></sup>
                </label>
                <div class="col-lg-2">
                    <input type="checkbox" class="configKey" data-l1key="debugRestoreVenv" />
                </div>
            </div>
            <legend><i class="fas fa-university"></i> {{Démon}}</legend>
            <div class="form-group">
                <label class="col-lg-3 control-label">{{Port Socket Interne}}
                    <sup><i class="fas fa-exclamation-triangle tooltips" style="color:var(--al-warning-color)!important;" title="{{Le démon devra être redémarré après la modification de ce paramètre}}"></i></sup>    
                    <sup><i class="fas fa-question-circle tooltips" title="{{[ATTENTION] Ne changez ce paramètre qu'en cas de nécessité. (Défaut = 55112)}}"></i></sup>
                </label>
                <div class="col-lg-1">
                    <input class="configKey form-control" data-l1key="socketport" placeholder="55112" />
                </div>
            </div>
            <div class="form-group">
	            <label class="col-lg-3 control-label">{{Fréquence des cycles}}
                    <sup><i class="fas fa-exclamation-triangle tooltips" style="color:var(--al-warning-color)!important;" title="{{Le démon devra être redémarré après la modification de ce paramètre}}"></i></sup>    
                    <sup><i class="fas fa-question-circle tooltips" title="{{Facteur multiplicateur des cycles du démon (Défaut = x1)}}"></i></sup>
                </label>
	            <div class="col-lg-2">
			        <select class="configKey form-control" data-l1key="cyclefactor">
                        <option value="0.1">{{Rapide +++ (x0.1)}}</option>
                        <option value="0.25">{{Rapide ++ (x0.25)}}</option>
                        <option value="0.5">{{Rapide + (x0.5)}}</option>
			            <option value="1.0" selected>{{Normal (x1)}}</option>
			            <option value="1.5">{{Lent - (x1.5)}}</option>
                        <option value="2.0">{{Lent -- (x2)}}</option>
			            <option value="3.0">{{Lent --- (x3)}}</option>
			        </select>
	            </div>
            </div>        
            <legend><i class="fas fa-tv"></i> {{Remote TV (Télécommande)}}</legend>
            <div class="form-group">
                <label class="col-lg-3 control-label">{{Effacer le Certificat / Clé}}
                    <sup><i class="fas fa-exclamation-triangle tooltips" style="color:var(--al-warning-color)!important;" title="{{Le démon devra être redémarré après la modification de ce paramètre}}"></i></sup>    
                    <sup><i class="fas fa-question-circle tooltips" title="{{Effacer le certificat et la clé générés au premier appairage à un équipement}}"></i></sup>
                </label>
                <div class="col-lg-1">
                    <a class="btn btn-danger customclass-resettvcertkey"><i class="fas fa-trash-alt"></i> {{Effacer Cert/Key}}</a>
                </div>
            </div>
        </div>
    </fieldset>
</form>

<script>
    $('.customclass-resettvcertkey').on('click', function () {
        $.ajax({
            type: "POST",
            url: "plugins/tvremote/core/ajax/tvremote.ajax.php",
            data: {
                action: "resetTVCertKey"
            },
            dataType: 'json',
            error: function (request, status, error) {
                handleAjaxError(request, status, error);
            },
            success: function (data) {
                if (data.state != 'ok') {
                    $('#div_alert').showAlert({ message: data.result, level: 'danger' });
                    return;
                }
                $('#div_alert').showAlert({ message: '{{Reset TV Cert (OK)}} :: ' + data.result, level: 'success' });
            }
        });
    });
</script>
