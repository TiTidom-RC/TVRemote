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

  var selCmdType = '<select style="width:120px;" class="cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="cmdType">'
  selCmdType += '<option value="adb-shell">{{ADB Shell}}</option>'
  selCmdType += '<option value="refresh-cmd">{{Refresh Cmd}}</option>'
  selCmdType += '</select>'

  var tr = '<tr class="cmd" data-cmd_id="' + init(_cmd.id) + '">'
  tr += '<td class="hidden-xs">'
  tr += '<span class="cmdAttr" data-l1key="id"></span>'
  tr += '</td>'
  tr += '<td>'
  tr += '<div class="input-group">'
  tr += '<input class="cmdAttr form-control input-sm roundedLeft" data-l1key="name" placeholder="{{Nom de la commande}}">'
  tr += '<span class="input-group-btn"><a class="cmdAction btn btn-sm btn-default" data-l1key="chooseIcon" title="{{Choisir une icône}}"><i class="fas fa-icons"></i></a></span>'
  tr += '<span class="cmdAttr input-group-addon roundedRight" data-l1key="display" data-l2key="icon" style="font-size:19px;padding:0 5px 0 0!important;"></span>'
  tr += '</div>'
  tr += '<select class="cmdAttr form-control input-sm" data-l1key="value" style="display:none;margin-top:5px;" title="{{Commande info liée}}">'
  tr += '<option value="">{{Aucune}}</option>'
  tr += '</select>'
  tr += '</td>'
  
  // Calculate all display conditions once (like SSH-Manager)
  var isGlobalRefresh = init(_cmd.logicalId) === 'refresh'
  var isNewCmd = !isset(_cmd.id) || _cmd.id === ''
  var hasCmdType = isset(_cmd.configuration.cmdType) && _cmd.configuration.cmdType !== ''
  var isRefreshCmd = isset(_cmd.configuration.cmdType) && _cmd.configuration.cmdType === 'refresh-cmd'
  var isAdbShellCmd = isset(_cmd.configuration.cmdType) && _cmd.configuration.cmdType === 'adb-shell'
  var hasAdbCmd = isset(_cmd.configuration['adb-shell-command']) && _cmd.configuration['adb-shell-command'] !== ''
  
  // Type Cmd column - show for new commands or commands with cmdType, but hide for global refresh
  var displayCmdType = isGlobalRefresh ? 'none' : ((isNewCmd || hasCmdType) ? 'block' : 'none')
  
  // Type/SubType should be hidden for refresh-cmd commands and global refresh command
  var displayTypeSubType = (isGlobalRefresh || isRefreshCmd) ? 'none' : 'block'
  
  // Textarea ADB Shell - show ONLY for adb-shell commands
  // For existing commands: show if cmdType is adb-shell OR if has adb-shell-command (will be auto-detected as adb-shell)
  // For new commands: hide (will be shown when user selects adb-shell in dropdown)
  var displayAdbCmd = (isGlobalRefresh || isRefreshCmd) ? 'none' : 
                      (isAdbShellCmd ? 'block' : 
                      (hasAdbCmd && !isNewCmd ? 'block' : 'none'))
  
  tr += '<td>'
  tr += '<span class="cmdType" style="display:' + displayCmdType + ';" type="' + init(_cmd.configuration.cmdType) + '">' + selCmdType + '</span>'
  tr += '</td>'
  tr += '<td>'
  tr += '<span class="type" style="display:' + displayTypeSubType + ';" type="' + init(_cmd.type) + '">' + jeedom.cmd.availableType() + '</span>'
  tr += '<span class="subType" style="display:' + displayTypeSubType + ';" subType="' + init(_cmd.subType) + '"></span>'
  tr += '</td>'
  
  // Cmd ADB Shell / Refresh column
  tr += '<td>'
  tr += '<textarea rows="2" class="cmdAttr form-control input-sm adb-shell-cmd" data-l1key="configuration" data-l2key="adb-shell-command" placeholder="{{Commande ADB Shell}}" style="display:' + displayAdbCmd + ';"></textarea>'
  tr += '<select class="cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="cmdToRefresh" style="display:none;margin-top:5px;" title="{{Commande info à rafraîchir}}">'
  tr += '<option value="">{{Aucune}}</option>'
  tr += '</select>'
  tr += '</td>'
  tr += '<td>'
  tr += '<div class="cmdOptionAutoRefresh">'
  tr += '<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isVisible" checked/>{{Afficher}}</label> '
  tr += '<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isHistorized" checked/>{{Historiser}}</label> '
  tr += '<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="display" data-l2key="invertBinary"/>{{Inverser}}</label> '
  tr += '<div style="margin-top:7px;">'
  tr += '<input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="minValue" placeholder="{{Min}}" title="{{Min}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">'
  tr += '<input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="maxValue" placeholder="{{Max}}" title="{{Max}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">'
  tr += '<input class="tooltips cmdAttr form-control input-sm" data-l1key="unite" placeholder="Unité" title="{{Unité}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">'
  tr += '</div>'
  tr += '</div>'
  tr += '</td>'
  tr += '<td>';
  tr += '<span class="cmdAttr" data-l1key="htmlstate"></span>';
  tr += '</td>';
  tr += '<td>'
  if (is_numeric(_cmd.id)) {
    tr += '<a class="btn btn-default btn-xs cmdAction" data-action="configure"><i class="fas fa-cogs"></i></a> '
    tr += '<a class="btn btn-default btn-xs cmdAction" data-action="test"><i class="fas fa-rss"></i> {{Tester}}</a>'
  }
  tr += '<i class="fas fa-minus-circle pull-right cmdAction cursor" data-action="remove" title="{{Supprimer la commande}}"></i></td>'
  tr += '</tr>'
  $('#table_cmd tbody').append(tr)
  var tr = $('#table_cmd tbody tr').last()
  jeedom.eqLogic.buildSelectCmd({
    id: $('.eqLogicAttr[data-l1key=id]').value(),
    filter: { type: 'info' },
    error: function (error) {
      $('#div_alert').showAlert({ message: error.message, level: 'danger' })
    },
    success: function (result) {
      tr.find('.cmdAttr[data-l1key=value]').append(result)
      tr.find('.cmdAttr[data-l2key=cmdToRefresh]').append(result)
      tr.setValues(_cmd, '.cmdAttr')
      jeedom.cmd.changeType(tr, init(_cmd.subType))
      
      // Check if this is the global refresh command
      var isGlobalRefresh = init(_cmd.logicalId) === 'refresh'
      if (isGlobalRefresh) {
        // Hide Type Cmd, Type and SubType for global refresh command
        tr.find('.cmdType').hide()
        tr.find('.type').hide()
        tr.find('.subType').hide()
      }
      
      // Auto-detect cmdType based on configuration (but not for global refresh)
      if (!isGlobalRefresh && (!isset(_cmd.configuration.cmdType) || _cmd.configuration.cmdType === '')) {
        if (isset(_cmd.configuration['adb-shell-command']) && _cmd.configuration['adb-shell-command'] !== '') {
          tr.find('.cmdAttr[data-l2key=cmdType]').val('adb-shell')
          tr.find('.cmdType').show()
          tr.find('.adb-shell-cmd').show()
        } else if (isset(_cmd.configuration.cmdToRefresh) && _cmd.configuration.cmdToRefresh !== '') {
          tr.find('.cmdAttr[data-l2key=cmdType]').val('refresh-cmd')
          tr.find('.cmdType').show()
        }
      }
      
      // Trigger cmdType change event if cmdType is set
      var cmdType = tr.find('.cmdAttr[data-l2key=cmdType]').val()
      if (isset(cmdType) && cmdType !== '') {
        tr.find('.cmdAttr[data-l2key=cmdType]').trigger('change')
      } else {
        // For standard commands without cmdType, show/hide auto-refresh based on type
        updateAutoRefreshVisibility(tr)
      }
    }
  })
}

// Helper function to update auto-refresh visibility
function updateAutoRefreshVisibility(tr) {
  var type = tr.find('.cmdAttr[data-l1key=type]').val()
  var cmdType = tr.find('.cmdAttr[data-l2key=cmdType]').val()
  
  if (type === 'info' && cmdType !== 'refresh-cmd') {
    tr.find('.cmdOptionAutoRefresh').show()
  } else {
    tr.find('.cmdOptionAutoRefresh').hide()
  }
}

// Handle cmdType change
$('#table_cmd').on('change', '.cmdAttr[data-l2key=cmdType]', function() {
  var tr = $(this).closest('tr')
  var cmdType = $(this).val()
  
  if (cmdType === 'refresh-cmd') {
    // Refresh mode: force action/other type, hide type/subtype, show cmdToRefresh select, hide adb command
    tr.find('.cmdAttr[data-l1key=type]').val('action')
    tr.find('.cmdAttr[data-l1key=subType]').val('other')
    jeedom.cmd.changeType(tr, 'other')
    tr.find('.type').hide()
    tr.find('.subType').hide()
    tr.find('.adb-shell-cmd').hide()
    tr.find('.cmdAttr[data-l2key=cmdToRefresh]').show()
    tr.find('.cmdOptionAutoRefresh').hide()
  } else if (cmdType === 'adb-shell') {
    // ADB Shell mode: show type/subtype, show adb command, hide cmdToRefresh
    tr.find('.type').show()
    tr.find('.subType').show()
    tr.find('.adb-shell-cmd').show()
    tr.find('.cmdAttr[data-l2key=cmdToRefresh]').hide()
    updateAutoRefreshVisibility(tr)
  } else {
    // Standard mode: show type/subtype, hide both adb command and cmdToRefresh
    tr.find('.type').show()
    tr.find('.subType').show()
    tr.find('.adb-shell-cmd').hide()
    tr.find('.cmdAttr[data-l2key=cmdToRefresh]').hide()
    updateAutoRefreshVisibility(tr)
  }
})

// Handle type change to show/hide auto-refresh option
$('#table_cmd').on('change', '.cmdAttr[data-l1key=type]', function() {
  updateAutoRefreshVisibility($(this).closest('tr'))
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