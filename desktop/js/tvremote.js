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

/* Fonction permettant l'affichage des commandes dans l'équipement */
function addCmdToTable(_cmd) {
  if (!isset(_cmd)) {
    _cmd = { configuration: {} }
  }
  if (!isset(_cmd.configuration)) {
    _cmd.configuration = {}
  }

  // Build HTML using array for better performance
  let html = [];
  html.push('<select style="width:120px;" class="cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="cmdType">');
  html.push('<option value="adb-shell" selected>{{ADB Shell}}</option>');
  html.push('<option value="refresh-cmd">{{Refresh Cmd}}</option>');
  html.push('<option value="plugin" style="display:none;">{{Plugin}}</option>');
  html.push('</select>');
  const selCmdType = html.join('');

  html = [];
  html.push(`<tr class="cmd" data-cmd_id="${init(_cmd.id)}">`);
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
  const cmdType = init(_cmd.configuration.cmdType)
  const isGlobalRefresh = init(_cmd.logicalId) === 'refresh'
  const isNewCmd = !isset(_cmd.id) || _cmd.id === ''
  const isRefreshCmd = cmdType === 'refresh-cmd'
  const isAdbShellCmd = cmdType === 'adb-shell'
  const isPluginCmd = cmdType === 'plugin'
  
  // Type Cmd column - show for new commands or custom commands, hide for plugin/global refresh
  const displayCmdType = (isGlobalRefresh || isPluginCmd) ? 'none' : ((isNewCmd || isAdbShellCmd || isRefreshCmd) ? 'block' : 'none')
  
  // Type/SubType - hidden for refresh-cmd and global refresh
  const displayTypeSubType = (isGlobalRefresh || isRefreshCmd) ? 'none' : 'block'
  
  // ADB Shell textarea - show ONLY for adb-shell commands
  const displayAdbCmd = isAdbShellCmd ? 'block' : 'none'
  
  // Refresh select - show ONLY for refresh-cmd commands
  const displayRefreshCmd = isRefreshCmd ? 'block' : 'none'
  
  // Continue building HTML with array
  html.push(`<td><span class="cmdType" style="display:${displayCmdType};" type="${init(cmdType)}">${selCmdType}</span></td>`);
  html.push('<td>');
  html.push(`<span class="type" style="display:${displayTypeSubType};" type="${init(_cmd.type)}">${jeedom.cmd.availableType()}</span>`);
  html.push(`<span class="subType" style="display:${displayTypeSubType};" subType="${init(_cmd.subType)}"></span>`);
  html.push('</td>');
  
  // Cmd ADB Shell / Refresh column
  html.push('<td>');
  html.push(`<textarea rows="2" class="cmdAttr form-control input-sm adb-shell-cmd" data-l1key="configuration" data-l2key="adb-shell-command" placeholder="{{Commande ADB Shell}}" style="display:${displayAdbCmd};"></textarea>`);
  html.push(`<select class="cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="cmdToRefresh" style="display:${displayRefreshCmd};margin-top:5px;" title="{{Commande info à rafraîchir}}">`);
  html.push('<option value="">{{Aucune}}</option>');
  html.push('</select>');
  html.push('</td>');
  html.push('<td>');
  html.push('<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isVisible"/>{{Afficher}}</label> ');
  html.push('<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isHistorized"/>{{Historiser}}</label> ');
  html.push('<label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="display" data-l2key="invertBinary"/>{{Inverser}}</label> ');
  html.push('<div style="margin-top:7px;">');
  html.push('<input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="minValue" placeholder="{{Min}}" title="{{Min}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">');
  html.push('<input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="maxValue" placeholder="{{Max}}" title="{{Max}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">');
  html.push('<input class="tooltips cmdAttr form-control input-sm" data-l1key="unite" placeholder="Unité" title="{{Unité}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">');
  html.push('</div></td>');
  html.push('<td><span class="cmdAttr" data-l1key="htmlstate"></span></td>');
  html.push('<td>');
  if (is_numeric(_cmd.id)) {
    html.push('<a class="btn btn-default btn-xs cmdAction" data-action="configure"><i class="fas fa-cogs"></i></a> ');
    html.push('<a class="btn btn-default btn-xs cmdAction" data-action="test"><i class="fas fa-rss"></i> {{Tester}}</a>');
  }
  html.push('<i class="fas fa-minus-circle pull-right cmdAction cursor" data-action="remove" title="{{Supprimer la commande}}"></i></td>');
  html.push('</tr>');
  
  const newRow = document.createElement('tr')
  newRow.innerHTML = html.join('')
  newRow.classList.add('cmd')
  newRow.setAttribute('data-cmd_id', init(_cmd.id))
  document.getElementById('table_cmd').querySelector('tbody').appendChild(newRow)
  
  // Cache eqLogic ID to avoid multiple DOM queries
  const eqLogicId = document.querySelector('.eqLogicAttr[data-l1key=id]').jeeValue()
  
  // Single optimized call to get all commands
  jeedom.eqLogic.getCmd({
    id: eqLogicId,
    error: (error) => {
      jeedomUtils.showAlert({ message: error.message, level: 'danger' })
    },
    success: (cmds) => {
      // Filter info commands once
      const infoCmds = cmds.filter(cmd => cmd.type === 'info')
      
      // Build select for "value" field (all info commands)
      const allInfoOptions = infoCmds.map(cmd => 
        `<option value="${init(cmd.id)}">${init(cmd.name)}</option>`
      ).join('')
      
      const valueSelect = newRow.querySelector('.cmdAttr[data-l1key=value]')
      if (valueSelect) valueSelect.insertAdjacentHTML('beforeend', allInfoOptions)
      
      // Build select for "cmdToRefresh" field (only ADB shell info commands)
      const adbShellOptions = infoCmds
        .filter(cmd => 
          cmd.configuration && 
          (cmd.configuration.cmdType === 'adb-shell' || 
           (cmd.configuration['adb-shell-command'] && cmd.configuration['adb-shell-command'] !== ''))
        )
        .map(cmd => 
          `<option value="${init(cmd.id)}">${init(cmd.name)}</option>`
        )
        .join('')
      
      const refreshSelect = newRow.querySelector('.cmdAttr[data-l2key=cmdToRefresh]')
      if (refreshSelect) refreshSelect.insertAdjacentHTML('beforeend', adbShellOptions)
      
      // Set values and update display after both selects are populated
      newRow.setJeeValues(_cmd, '.cmdAttr')
      jeedom.cmd.changeType(newRow, init(_cmd.subType))
      
      // Global refresh command: already handled in initial display, just exit
      if (isGlobalRefresh) {
        return
      }
      
      // Auto-detect cmdType for existing commands without explicit configuration
      const cmdTypeSelect = newRow.querySelector('.cmdAttr[data-l2key=cmdType]')
      if (cmdTypeSelect && (!isset(_cmd.configuration.cmdType) || _cmd.configuration.cmdType === '')) {
        if (isset(_cmd.configuration['adb-shell-command']) && _cmd.configuration['adb-shell-command'] !== '') {
          cmdTypeSelect.value = 'adb-shell'
        } else if (isset(_cmd.configuration.cmdToRefresh) && _cmd.configuration.cmdToRefresh !== '') {
          cmdTypeSelect.value = 'refresh-cmd'
        } else if (!isNewCmd) {
          // Native plugin command: hide custom fields
          newRow.querySelectorAll('.cmdType, .adb-shell-cmd').unseen()
        }
      }
      
      // Trigger change event for detected custom commands
      if (cmdTypeSelect) {
        const detectedCmdType = cmdTypeSelect.value
        if (detectedCmdType && detectedCmdType !== 'plugin') {
          cmdTypeSelect.triggerEvent('change')
        }
      }
    }
  })
}



// Handle cmdType change with event delegation (only attach once)
(() => {
  const tableCmdElement = document.getElementById('table_cmd')
  if (tableCmdElement && !tableCmdElement._cmdTypeListenerAttached) {
    tableCmdElement.addEventListener('change', (event) => {
      if (!event.target.matches('.cmdAttr[data-l2key=cmdType]')) return
      
      const tr = event.target.closest('tr')
      const cmdType = event.target.value
      const type = tr.querySelector('.type')
      const subType = tr.querySelector('.subType')
      const adbShellCmd = tr.querySelector('.adb-shell-cmd')
      const cmdToRefresh = tr.querySelector('.cmdAttr[data-l2key=cmdToRefresh]')
      
      if (cmdType === 'refresh-cmd') {
        // Refresh mode: force action/other type, hide type/subtype, show cmdToRefresh select
        tr.querySelector('.cmdAttr[data-l1key=type]').value = 'action'
        tr.querySelector('.cmdAttr[data-l1key=subType]').value = 'other'
        jeedom.cmd.changeType(tr, 'other')
        ;[type, subType, adbShellCmd].forEach(el => el?.unseen())
        cmdToRefresh?.seen()
      } else if (cmdType === 'adb-shell') {
        // ADB Shell mode: set action/other for new commands, keep existing type otherwise
        const cmdId = tr.getAttribute('data-cmd_id')
        const isNewCommand = !cmdId || cmdId === '' || cmdId === 'null' || cmdId === 'undefined'
        if (isNewCommand) {
          tr.querySelector('.cmdAttr[data-l1key=type]').value = 'action'
          tr.querySelector('.cmdAttr[data-l1key=subType]').value = 'other'
          jeedom.cmd.changeType(tr, 'other')
        } else {
          jeedom.cmd.changeType(tr, tr.querySelector('.cmdAttr[data-l1key=subType]').value)
        }
        ;[type, subType, adbShellCmd].forEach(el => el?.seen())
        cmdToRefresh?.unseen()
      } else {
        // Plugin/Standard mode: show type/subtype, hide custom fields
        ;[type, subType].forEach(el => el?.seen())
        ;[adbShellCmd, cmdToRefresh].forEach(el => el?.unseen())
      }
    })
    tableCmdElement._cmdTypeListenerAttached = true
  }
})()


function printEqLogic(_eqLogic) {
  // Si la configuration use_adb n'existe pas encore (nouvel équipement), on force le décochage
  if (typeof _eqLogic.configuration.use_adb === 'undefined') {
    var useAdbCheckbox = document.querySelector('.eqLogicAttr[data-l2key="use_adb"]')
    if (useAdbCheckbox) useAdbCheckbox.checked = false
  }
}

document.querySelectorAll('.pluginAction[data-action=openLocation]').forEach(function(element) {
  element.addEventListener('click', function() {
    window.open(this.getAttribute('data-location'), '_blank', null)
  })
})

document.querySelectorAll('.customclass-beginpairing').forEach(function(element) {
  element.addEventListener('click', function() {
    var hostAddr = document.getElementById('hostAddr').value
    var macAddr = document.getElementById('macAddr').value
    var portNum = document.getElementById('portNum').value
    domUtils.ajax({
      type: 'POST',
      url: 'plugins/tvremote/core/ajax/tvremote.ajax.php',
      data: {
        action: 'beginPairing',
        mac: macAddr,
        host: hostAddr,
        port: portNum
      },
      dataType: 'json',
      error: function(request, status, error) {
        handleAjaxError(request, status, error)
      },
      success: function(data) {
        if (data.state != 'ok') {
          jeedomUtils.showAlert({ message: data.result, level: 'danger' })
          return
        }
        jeedomUtils.showAlert({ message: '{{Lancement Appairage (Actif pendant 5min)}} :: ' + data.result, level: 'warning' })
      }
    })
  })
})

document.querySelectorAll('.customclass-sendpaircode').forEach(function(element) {
  element.addEventListener('click', function() {
    var pairCode = document.getElementById('pairCode').value
    var hostAddr = document.getElementById('hostAddr').value
    var macAddr = document.getElementById('macAddr').value
    var portNum = document.getElementById('portNum').value
    domUtils.ajax({
      type: 'POST',
      url: 'plugins/tvremote/core/ajax/tvremote.ajax.php',
      data: {
        action: 'sendPairCode',
        mac: macAddr,
        host: hostAddr,
        port: portNum,
        paircode: pairCode
      },
      dataType: 'json',
      error: function(request, status, error) {
        handleAjaxError(request, status, error)
      },
      success: function(data) {
        if (data.state != 'ok') {
          jeedomUtils.showAlert({ message: data.result, level: 'danger' })
          return
        }
        jeedomUtils.showAlert({ message: '{{Envoi Code Appairage}} :: ' + data.result, level: 'success' })
      }
    })
  })
})

document.querySelectorAll('.customclass-beginpairingadb').forEach(function(element) {
  element.addEventListener('click', function() {
    var hostAddr = document.getElementById('hostAddr').value
    var macAddr = document.getElementById('macAddr').value
    domUtils.ajax({
      type: 'POST',
      url: 'plugins/tvremote/core/ajax/tvremote.ajax.php',
      data: {
        action: 'beginPairingAdb',
        mac: macAddr,
        host: hostAddr
      },
      dataType: 'json',
      error: function(request, status, error) {
        handleAjaxError(request, status, error)
      },
      success: function(data) {
        if (data.state != 'ok') {
          jeedomUtils.showAlert({ message: data.result, level: 'danger' })
          return
        }
        jeedomUtils.showAlert({ message: '{{Appairage ADB lancé. Veuillez vérifier votre TV et ACCEPTER la demande d\'autorisation ADB qui s\'affiche à l\'écran.}}', level: 'warning' })
      }
    })
  })
})

document.querySelectorAll('.customclass-scanState').forEach(function(element) {
  element.addEventListener('click', function() {
    var scanState = this.getAttribute('data-scanState')
    changeScanState(scanState)
  })
})

function changeScanState(_scanState) {
  domUtils.ajax({
    type: 'POST',
    url: 'plugins/tvremote/core/ajax/tvremote.ajax.php',
    data: {
      action: 'changeScanState',
      scanState: _scanState
    },
    dataType: 'json',
    error: function(request, status, error) {
      handleAjaxError(request, status, error)
    },
    success: function(data) {
      if (data.state != 'ok') {
        jeedomUtils.showAlert({ message: data.result, level: 'danger' })
        return
      }
    }
  })
}

document.body.addEventListener('tvremote::scanResult', function(event) {
  var _option = event.detail || event._option
  if (_option && _option['friendly_name'] && _option['isNew'] === 1) {
    jeedomUtils.showAlert({ message: '[SCAN] TVRemote AJOUTE :: ' + _option['friendly_name'], level: 'success' })
  } else if (_option && _option['friendly_name'] && _option['isNew'] === 0) {
    jeedomUtils.showAlert({ message: '[SCAN] TVRemote MAJ :: ' + _option['friendly_name'], level: 'warning' })
  }
})

document.body.addEventListener('tvremote::adbPairingResult', function(event) {
  var _option = event.detail || event._option
  if (_option && _option['adb_paired'] === 1) {
    var deviceName = _option['friendly_name'] || _option['mac']
    // Only show alert if it's not an auto-detection
    if (!_option['auto_detected']) {
      jeedomUtils.showAlert({ message: '{{Appairage ADB réussi pour}} ' + deviceName, level: 'success' })
    }
    // Update status indicator
    var adbStatus = document.getElementById('adb-pairing-status')
    if (adbStatus) {
      adbStatus.removeClass('label-danger').addClass('label-success')
      adbStatus.innerHTML = '<i class="fas fa-check-circle"></i> {{Appairé}}'
    }
  } else if (_option && _option['adb_paired'] === 0) {
    var deviceName = _option['friendly_name'] || _option['mac']
    jeedomUtils.showAlert({ message: '{{Échec de l\'appairage ADB pour}} ' + deviceName + ' : ' + (_option['message'] || '{{Erreur inconnue}}'), level: 'danger' })
    // Update status indicator
    var adbStatus = document.getElementById('adb-pairing-status')
    if (adbStatus) {
      adbStatus.removeClass('label-success').addClass('label-danger')
      adbStatus.innerHTML = '<i class="fas fa-times-circle"></i> {{Non appairé}}'
    }
  }
})

document.body.addEventListener('tvremote::tvremotePairingResult', function(event) {
  var _option = event.detail || event._option
  if (_option && _option['tvremote_paired'] === 1) {
    var deviceName = _option['friendly_name'] || _option['mac']
    // Only show alert if it's not an auto-detection
    if (!_option['auto_detected']) {
      jeedomUtils.showAlert({ message: '{{Appairage TVRemote réussi pour}} ' + deviceName, level: 'success' })
    }
    // Update status indicator
    var tvremoteStatus = document.getElementById('tvremote-pairing-status')
    if (tvremoteStatus) {
      tvremoteStatus.removeClass('label-danger').addClass('label-success')
      tvremoteStatus.innerHTML = '<i class="fas fa-check-circle"></i> {{Appairé}}'
    }
  } else if (_option && _option['tvremote_paired'] === 0) {
    var deviceName = _option['friendly_name'] || _option['mac']
    jeedomUtils.showAlert({ message: '{{Échec de l\'appairage TVRemote pour}} ' + deviceName + ' : ' + (_option['message'] || '{{Erreur inconnue}}'), level: 'danger' })
    // Update status indicator
    var tvremoteStatus = document.getElementById('tvremote-pairing-status')
    if (tvremoteStatus) {
      tvremoteStatus.removeClass('label-success').addClass('label-danger')
      tvremoteStatus.innerHTML = '<i class="fas fa-times-circle"></i> {{Non appairé}}'
    }
  }
})

document.body.addEventListener('tvremote::scanState', function(event) {
  var _options = event.detail || event._options
  
  if (_options['scanState'] === 'scanOn') {
    jeedomUtils.hideAlert()
    document.querySelectorAll('.customclass-scanState').forEach(el => {
      el.setAttribute('data-scanState', 'scanOff')
      el.removeClass('logoPrimary').addClass('logoSecondary')
    })
    document.querySelectorAll('.customicon-scanState').addClass('icon_red')
    document.querySelectorAll('.customtext-scanState').forEach(el => el.textContent = '{{Stop Scan}}')
    jeedomUtils.showAlert({ message: '{{Mode SCAN actif pendant 60 secondes. (Cliquez sur STOP SCAN pour arrêter la découverte des équipements)}}', level: 'warning' })
  } else if (_options['scanState'] === 'scanOff') {
    jeedomUtils.hideAlert()
    document.querySelectorAll('.customclass-scanState').forEach(el => {
      el.setAttribute('data-scanState', 'scanOn')
      el.removeClass('logoSecondary').addClass('logoPrimary')
    })
    document.querySelectorAll('.customicon-scanState').removeClass('icon_red')
    document.querySelectorAll('.customtext-scanState').forEach(el => el.textContent = '{{Scan}}')
    window.location.reload()
  }
})

// Update pairing status badges when configuration changes
document.querySelectorAll('.eqLogicAttr[data-l2key="tvremote_paired_status"]').forEach(function(element) {
  element.addEventListener('change', function() {
    var status = this.value
    var statusElement = document.getElementById('tvremote-pairing-status')
    if (statusElement) {
      if (status == 1) {
        statusElement.removeClass('label-danger').addClass('label-success')
        statusElement.innerHTML = '<i class="fas fa-check-circle"></i> {{Appairé}}'
      } else {
        statusElement.removeClass('label-success').addClass('label-danger')
        statusElement.innerHTML = '<i class="fas fa-times-circle"></i> {{Non appairé}}'
      }
      statusElement.seen()
    }
  })
})

document.querySelectorAll('.eqLogicAttr[data-l2key="adb_paired_status"]').forEach(function(element) {
  element.addEventListener('change', function() {
    var status = this.value
    var statusElement = document.getElementById('adb-pairing-status')
    if (statusElement) {
      if (status == 1) {
        statusElement.removeClass('label-danger').addClass('label-success')
        statusElement.innerHTML = '<i class="fas fa-check-circle"></i> {{Appairé}}'
      } else {
        statusElement.removeClass('label-success').addClass('label-danger')
        statusElement.innerHTML = '<i class="fas fa-times-circle"></i> {{Non appairé}}'
      }
      statusElement.seen()
    }
  })
})