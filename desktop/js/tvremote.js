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

/* Permet la réorganisation des commandes dans l'équipement */
$("#table_cmd").sortable({
  axis: "y",
  cursor: "move",
  items: ".cmd",
  placeholder: "ui-state-highlight",
  tolerance: "intersect",
  forcePlaceholderSize: true
})

/* Fonction permettant l'affichage des commandes dans l'équipement */
function addCmdToTable(_cmd) {
  if (!isset(_cmd)) {
    var _cmd = { configuration: {} }
  }
  if (!isset(_cmd.configuration)) {
    _cmd.configuration = {}
  }

  // Build HTML using array for better performance
  var html = [];
  html.push('<select style="width:120px;" class="cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="cmdType">');
  html.push('<option value="adb-shell" selected>{{ADB Shell}}</option>');
  html.push('<option value="refresh-cmd">{{Refresh Cmd}}</option>');
  html.push('<option value="plugin" style="display:none;">{{Plugin}}</option>');
  html.push('</select>');
  var selCmdType = html.join('');

  html = [];
  html.push('<tr class="cmd" data-cmd_id="' + init(_cmd.id) + '">');
  html.push('<td class="hidden-xs"><span class="cmdAttr" data-l1key="id"></span></td>');
  html.push('<td>');
  html.push('<div class="input-group">');
  html.push('<input class="cmdAttr form-control input-sm roundedLeft" data-l1key="name" placeholder="{{Nom de la commande}}">');
  html.push('<span class="input-group-btn"><a class="cmdAction btn btn-sm btn-default" data-l1key="chooseIcon" title="{{Choisir une icône}}"><i class="fas fa-icons"></i></a></span>');
  html.push('<span class="cmdAttr input-group-addon roundedRight" data-l1key="display" data-l2key="icon" style="font-size:19px;padding:0 5px 0 0!important;"></span>');
  html.push('</div>');
  html.push('<select class="cmdAttr form-control input-sm" data-l1key="value" style="display:none;margin-top:5px;" title="{{Commande info liée}}">');
  html.push('<option value="">{{Aucune}}</option>');
  html.push('</select>');
  html.push('</td>');
  
  // Calculate initial display conditions
  var isGlobalRefresh = init(_cmd.logicalId) === 'refresh'
  var isNewCmd = !isset(_cmd.id) || _cmd.id === ''
  var cmdType = init(_cmd.configuration.cmdType)
  var isRefreshCmd = cmdType === 'refresh-cmd'
  var isAdbShellCmd = cmdType === 'adb-shell'
  var isPluginCmd = cmdType === 'plugin'
  
  // Type Cmd column - show for new commands or custom commands, hide for plugin/global refresh
  var displayCmdType = (isGlobalRefresh || isPluginCmd) ? 'none' : ((isNewCmd || isAdbShellCmd || isRefreshCmd) ? 'block' : 'none')
  
  // Type/SubType - hidden for refresh-cmd and global refresh
  var displayTypeSubType = (isGlobalRefresh || isRefreshCmd) ? 'none' : 'block'
  
  // ADB Shell textarea - show ONLY for adb-shell commands
  var displayAdbCmd = isAdbShellCmd ? 'block' : 'none';
  
  // Continue building HTML with array
  html.push('<td><span class="cmdType" style="display:' + displayCmdType + ';" type="' + cmdType + '">' + selCmdType + '</span></td>');
  html.push('<td>');
  html.push('<span class="type" style="display:' + displayTypeSubType + ';" type="' + init(_cmd.type) + '">' + jeedom.cmd.availableType() + '</span>');
  html.push('<span class="subType" style="display:' + displayTypeSubType + ';" subType="' + init(_cmd.subType) + '"></span>');
  html.push('</td>');
  
  // Cmd ADB Shell / Refresh column
  html.push('<td>');
  html.push('<textarea rows="2" class="cmdAttr form-control input-sm adb-shell-cmd" data-l1key="configuration" data-l2key="adb-shell-command" placeholder="{{Commande ADB Shell}}" style="display:' + displayAdbCmd + ';"></textarea>');
  html.push('<select class="cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="cmdToRefresh" style="display:none;margin-top:5px;" title="{{Commande info à rafraîchir}}">');
  html.push('<option value="">{{Aucune}}</option>');
  html.push('</select>');
  html.push('</td>');
  html.push('<td><div class="cmdInfoOptions">');
  html.push('<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isVisible"/>{{Afficher}}</label> ');
  html.push('<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isHistorized"/>{{Historiser}}</label> ');
  html.push('<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="display" data-l2key="invertBinary"/>{{Inverser}}</label> ');
  html.push('<div style="margin-top:7px;">');
  html.push('<input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="minValue" placeholder="{{Min}}" title="{{Min}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">');
  html.push('<input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="maxValue" placeholder="{{Max}}" title="{{Max}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">');
  html.push('<input class="tooltips cmdAttr form-control input-sm" data-l1key="unite" placeholder="Unité" title="{{Unité}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">');
  html.push('</div></div></td>');
  html.push('<td><span class="cmdAttr" data-l1key="htmlstate"></span></td>');
  html.push('<td>');
  if (is_numeric(_cmd.id)) {
    html.push('<a class="btn btn-default btn-xs cmdAction" data-action="configure"><i class="fas fa-cogs"></i></a> ');
    html.push('<a class="btn btn-default btn-xs cmdAction" data-action="test"><i class="fas fa-rss"></i> {{Tester}}</a>');
  }
  html.push('<i class="fas fa-minus-circle pull-right cmdAction cursor" data-action="remove" title="{{Supprimer la commande}}"></i></td>');
  html.push('</tr>');
  
  $('#table_cmd tbody').append(html.join(''));
  var $tr = $('#table_cmd tbody tr').last();
  jeedom.eqLogic.buildSelectCmd({
    id: $('.eqLogicAttr[data-l1key=id]').value(),
    filter: { type: 'info' },
    error: function (error) {
      $('#div_alert').showAlert({ message: error.message, level: 'danger' })
    },
    success: function (result) {
      var $cmdValue = $tr.find('.cmdAttr[data-l1key=value]');
      var $cmdToRefresh = $tr.find('.cmdAttr[data-l2key=cmdToRefresh]');
      var $cmdTypeSelect = $tr.find('.cmdAttr[data-l2key=cmdType]');
      
      $cmdValue.append(result);
      $cmdToRefresh.append(result);
      $tr.setValues(_cmd, '.cmdAttr');
      jeedom.cmd.changeType($tr, init(_cmd.subType));
      
      // Global refresh command: hide all custom fields
      var isGlobalRefresh = init(_cmd.logicalId) === 'refresh';
      if (isGlobalRefresh) {
        $tr.find('.cmdType, .type, .subType, .cmdAttr[data-l1key=value], .adb-shell-cmd').hide();
        $cmdToRefresh.hide();
        return;
      }
      
      // Auto-detect cmdType for existing commands without explicit configuration
      var isNewCmd = !isset(_cmd.id) || _cmd.id === '';
      if (!isset(_cmd.configuration.cmdType) || _cmd.configuration.cmdType === '') {
        if (isset(_cmd.configuration['adb-shell-command']) && _cmd.configuration['adb-shell-command'] !== '') {
          $cmdTypeSelect.val('adb-shell');
        } else if (isset(_cmd.configuration.cmdToRefresh) && _cmd.configuration.cmdToRefresh !== '') {
          $cmdTypeSelect.val('refresh-cmd');
        } else if (!isNewCmd) {
          // Native plugin command: hide custom fields
          $tr.find('.cmdType, .adb-shell-cmd').hide();
        }
      }
      
      // Trigger change event for detected custom commands
      var detectedCmdType = $cmdTypeSelect.val();
      if (detectedCmdType && detectedCmdType !== 'plugin') {
        $cmdTypeSelect.trigger('change');
      } else {
        // Standard/native commands: update info options visibility
        updateInfoOptionsVisibility($tr);
      }
    }
  })
}

// Helper function to update info options visibility
function updateInfoOptionsVisibility($tr) {
  var type = $tr.find('.cmdAttr[data-l1key=type]').val();
  var cmdType = $tr.find('.cmdAttr[data-l2key=cmdType]').val();
  
  if (type === 'info' && cmdType !== 'refresh-cmd') {
    $tr.find('.cmdInfoOptions').show();
  } else {
    $tr.find('.cmdInfoOptions').hide();
  }
}

// Handle cmdType change
$('#table_cmd').on('change', '.cmdAttr[data-l2key=cmdType]', function() {
  var $tr = $(this).closest('tr');
  var cmdType = $(this).val();
  var $type = $tr.find('.type');
  var $subType = $tr.find('.subType');
  var $adbShellCmd = $tr.find('.adb-shell-cmd');
  var $cmdToRefresh = $tr.find('.cmdAttr[data-l2key=cmdToRefresh]');
  var $cmdInfoOptions = $tr.find('.cmdInfoOptions');
  
  if (cmdType === 'refresh-cmd') {
    // Refresh mode: force action/other type, hide type/subtype, show cmdToRefresh select
    $tr.find('.cmdAttr[data-l1key=type]').val('action');
    $tr.find('.cmdAttr[data-l1key=subType]').val('other');
    jeedom.cmd.changeType($tr, 'other');
    $type.add($subType).add($adbShellCmd).add($cmdInfoOptions).hide();
    $cmdToRefresh.show();
  } else if (cmdType === 'adb-shell') {
    // ADB Shell mode: set action/other for new commands, keep existing type otherwise
    var isNewCommand = !$tr.attr('data-cmd_id') || $tr.attr('data-cmd_id') === '';
    if (isNewCommand) {
      $tr.find('.cmdAttr[data-l1key=type]').val('action');
      $tr.find('.cmdAttr[data-l1key=subType]').val('other');
      jeedom.cmd.changeType($tr, 'other');
    } else {
      jeedom.cmd.changeType($tr, $tr.find('.cmdAttr[data-l1key=subType]').val());
    }
    $type.add($subType).add($adbShellCmd).show();
    $cmdToRefresh.hide();
    updateInfoOptionsVisibility($tr);
  } else {
    // Plugin/Standard mode: show type/subtype, hide custom fields
    $type.add($subType).show();
    $adbShellCmd.add($cmdToRefresh).hide();
    updateInfoOptionsVisibility($tr);
  }
});

// Handle type change to show/hide info options
$('#table_cmd').on('change', '.cmdAttr[data-l1key=type]', function() {
  updateInfoOptionsVisibility($(this).closest('tr'))
})

function printEqLogic(_eqLogic) {
  // Si la configuration use_adb n'existe pas encore (nouvel équipement), on force le décochage
  if (typeof _eqLogic.configuration.use_adb === 'undefined') {
    $('.eqLogicAttr[data-l2key="use_adb"]').prop('checked', false);
  }
}

$('.pluginAction[data-action=openLocation]').on('click', function () {
	window.open($(this).attr("data-location"), "_blank", null);
});

$('.customclass-beginpairing').on('click', function () {
  var _hostAddr = $('#hostAddr').val()
  var _macAddr = $('#macAddr').val()
  var _portNum = $('#portNum').val()
  $.ajax({
      type: "POST",
      url: "plugins/tvremote/core/ajax/tvremote.ajax.php",
      data: {
          action: "beginPairing",
          mac: _macAddr,
          host: _hostAddr,
          port: _portNum,
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
          $('#div_alert').showAlert({ message: '{{Lancement Appairage (Actif pendant 5min)}} :: ' + data.result, level: 'warning' });
      }
  });
});

$('.customclass-sendpaircode').on('click', function () {
  var _pairCode = $('#pairCode').val()
  var _hostAddr = $('#hostAddr').val()
  var _macAddr = $('#macAddr').val()
  var _portNum = $('#portNum').val()
  $.ajax({
      type: "POST",
      url: "plugins/tvremote/core/ajax/tvremote.ajax.php",
      data: {
          action: "sendPairCode",
          mac: _macAddr,
          host: _hostAddr,
          port: _portNum,
          paircode: _pairCode
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
          $('#div_alert').showAlert({ message: '{{Envoi Code Appairage}} :: ' + data.result, level: 'success' });
      }
  });
});

$('.customclass-beginpairingadb').on('click', function () {
  var _hostAddr = $('#hostAddr').val()
  var _macAddr = $('#macAddr').val()
  $.ajax({
      type: "POST",
      url: "plugins/tvremote/core/ajax/tvremote.ajax.php",
      data: {
          action: "beginPairingAdb",
          mac: _macAddr,
          host: _hostAddr
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
          $('#div_alert').showAlert({ message: '{{Appairage ADB lancé. Veuillez vérifier votre TV et ACCEPTER la demande d\'autorisation ADB qui s\'affiche à l\'écran.}}', level: 'warning' });
      }
  });
});

$('.customclass-scanState').on('click', function () {
	var scanState = $(this).attr('data-scanState');
	changeScanState(scanState);
});

function changeScanState(_scanState) {
  $.ajax({
    type: "POST",
      url: "plugins/tvremote/core/ajax/tvremote.ajax.php",
      data: {
          action: "changeScanState",
          scanState: _scanState,
      },
      dataType: 'json',
      error: function (request, status, error) {
          handleAjaxError(request, status, error);
      },
      success: function (data) {
          if (data.state != 'ok') {
              $('#div_alert').showAlert({message: data.result, level: 'danger'});
              return;
          }
      }
  });
}

$('body').on('tvremote::scanResult', function (_event, _option) {
  if (_option && _option['friendly_name'] && _option['isNew'] === 1) {
    $('#div_alert').showAlert({message: "[SCAN] TVRemote AJOUTE :: " + _option['friendly_name'], level: 'success'});
  } else if (_option && _option['friendly_name'] && _option['isNew'] === 0) {
    $('#div_alert').showAlert({message: "[SCAN] TVRemote MAJ :: " + _option['friendly_name'], level: 'warning'});
  }
});

$('body').on('tvremote::adbPairingResult', function (_event, _option) {
  if (_option && _option['adb_paired'] === 1) {
    var deviceName = _option['friendly_name'] || _option['mac'];
    // Only show alert if it's not an auto-detection
    if (!_option['auto_detected']) {
      $('#div_alert').showAlert({message: '{{Appairage ADB réussi pour}} ' + deviceName, level: 'success'});
    }
    // Update status indicator
    $('#adb-pairing-status').removeClass('label-danger').addClass('label-success');
    $('#adb-pairing-status').html('<i class="fas fa-check-circle"></i> {{Appairé}}');
  } else if (_option && _option['adb_paired'] === 0) {
    var deviceName = _option['friendly_name'] || _option['mac'];
    $('#div_alert').showAlert({message: '{{Échec de l\'appairage ADB pour}} ' + deviceName + ' : ' + (_option['message'] || '{{Erreur inconnue}}'), level: 'danger'});
    // Update status indicator
    $('#adb-pairing-status').removeClass('label-success').addClass('label-danger');
    $('#adb-pairing-status').html('<i class="fas fa-times-circle"></i> {{Non appairé}}');
  }
});

$('body').on('tvremote::tvremotePairingResult', function (_event, _option) {
  if (_option && _option['tvremote_paired'] === 1) {
    var deviceName = _option['friendly_name'] || _option['mac'];
    // Only show alert if it's not an auto-detection
    if (!_option['auto_detected']) {
      $('#div_alert').showAlert({message: '{{Appairage TVRemote réussi pour}} ' + deviceName, level: 'success'});
    }
    // Update status indicator
    $('#tvremote-pairing-status').removeClass('label-danger').addClass('label-success');
    $('#tvremote-pairing-status').html('<i class="fas fa-check-circle"></i> {{Appairé}}');
  } else if (_option && _option['tvremote_paired'] === 0) {
    var deviceName = _option['friendly_name'] || _option['mac'];
    $('#div_alert').showAlert({message: '{{Échec de l\'appairage TVRemote pour}} ' + deviceName + ' : ' + (_option['message'] || '{{Erreur inconnue}}'), level: 'danger'});
    // Update status indicator
    $('#tvremote-pairing-status').removeClass('label-success').addClass('label-danger');
    $('#tvremote-pairing-status').html('<i class="fas fa-times-circle"></i> {{Non appairé}}');
  }
});

$('body').on('tvremote::scanState', function (_event, _options) {
  // console.log('[TVRemote] scanState event received:', _options);
  
  if (_options['scanState'] === "scanOn") {
    // console.log('[TVRemote] Activating scan mode');
    $.hideAlert();
    $('.customclass-scanState').attr('data-scanState', 'scanOff');
    $('.customclass-scanState').removeClass('logoPrimary').addClass('logoSecondary');
    $('.customicon-scanState').addClass('icon_red');
    $('.customtext-scanState').text('{{Stop Scan}}');
    $('#div_alert').showAlert({message: '{{Mode SCAN actif pendant 60 secondes. (Cliquez sur STOP SCAN pour arrêter la découverte des équipements)}}', level: 'warning'});
  } else if (_options['scanState'] === "scanOff") {
    // console.log('[TVRemote] Deactivating scan mode');
    $.hideAlert();
    $('.customclass-scanState').attr('data-scanState', 'scanOn');
    $('.customclass-scanState').removeClass('logoSecondary').addClass('logoPrimary');
    $('.customicon-scanState').removeClass('icon_red');
    $('.customtext-scanState').text('{{Scan}}');
    window.location.reload();
  }
});

// Update pairing status badges when configuration changes
$('.eqLogicAttr[data-l2key="tvremote_paired_status"]').on('change', function() {
  var status = $(this).val();
  if (status == 1) {
    $('#tvremote-pairing-status').removeClass('label-danger').addClass('label-success');
    $('#tvremote-pairing-status').html('<i class="fas fa-check-circle"></i> {{Appairé}}');
  } else {
    $('#tvremote-pairing-status').removeClass('label-success').addClass('label-danger');
    $('#tvremote-pairing-status').html('<i class="fas fa-times-circle"></i> {{Non appairé}}');
  }
  $('#tvremote-pairing-status').show();
});

$('.eqLogicAttr[data-l2key="adb_paired_status"]').on('change', function() {
  var status = $(this).val();
  if (status == 1) {
    $('#adb-pairing-status').removeClass('label-danger').addClass('label-success');
    $('#adb-pairing-status').html('<i class="fas fa-check-circle"></i> {{Appairé}}');
  } else {
    $('#adb-pairing-status').removeClass('label-success').addClass('label-danger');
    $('#adb-pairing-status').html('<i class="fas fa-times-circle"></i> {{Non appairé}}');
  }
  $('#adb-pairing-status').show();
});