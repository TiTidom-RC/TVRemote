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

// Protect against multiple script loads (Jeedom SPA navigation, cache, etc.)
(function() {
'use strict'

// Constants for better maintainability and performance
const AJAX_URL = 'plugins/tvremote/core/ajax/tvremote.ajax.php'

// DOM Selectors constants (better minification + no string repetition + immutable)
const SELECTORS = Object.freeze({
  TABLE_CMD: '#table_cmd',
  EQ_ID: '.eqLogicAttr[data-l1key=id]',
  SCAN_BUTTONS: '.customclass-scanState',
  SCAN_ICONS: '.customicon-scanState',
  SCAN_TEXTS: '.customtext-scanState',
  CMD_TYPE_SELECT: '.cmdAttr[data-l2key=cmdType]',
  VALUE_SELECT: '.cmdAttr[data-l1key=value]',
  REFRESH_SELECT: '.cmdAttr[data-l2key=cmdToRefresh]'
})

// Bridge jQuery events to native CustomEvents (unidirectional: jQuery → CustomEvents)
if (typeof jQuery !== 'undefined' && !window.tvremoteBridgeAttached) {
  window.tvremoteBridgeAttached = true
  
  const eventsToBridge = [
    'tvremote::scanState',
    'tvremote::scanResult',
    'tvremote::adbPairingResult',
    'tvremote::tvremotePairingResult'
  ]
  
  eventsToBridge.forEach(eventName => {
    // jQuery → CustomEvents
    $('body').on(eventName, function(event, data) {
      if (event.originalEvent?.__bridged) return  // Prevent infinite loop
      
      const customEvent = new CustomEvent(eventName, {
        detail: data
      })
      customEvent.__bridged = true
      document.body.dispatchEvent(customEvent)
    })
    
  })
}

/* Fonction permettant l'affichage des commandes dans l'équipement */
function addCmdToTable(_cmd) {
  if (!isset(_cmd)) {
    _cmd = { configuration: {} }
  }
  if (!isset(_cmd.configuration)) {
    _cmd.configuration = {}
  }

  // Calculate initial display conditions first (before building HTML)
  const cmdType = init(_cmd.configuration.cmdType)
  const isGlobalRefresh = init(_cmd.logicalId) === 'refresh'
  const isNewCmd = !isset(_cmd.id) || _cmd.id === ''
  
  // For existing commands without cmdType, default to 'plugin' (native commands)
  const effectiveCmdType = cmdType || (isNewCmd ? 'adb-shell' : 'plugin')
  const isRefreshCmd = effectiveCmdType === 'refresh-cmd'
  const isAdbShellCmd = effectiveCmdType === 'adb-shell'
  const isPluginCmd = effectiveCmdType === 'plugin'
  
  // Display conditions
  const displayCmdType = (isGlobalRefresh || isPluginCmd) ? 'none' : ((isNewCmd || isAdbShellCmd || isRefreshCmd) ? 'block' : 'none')
  const displayTypeSubType = (isGlobalRefresh || isRefreshCmd) ? 'none' : 'block'
  const displayAdbCmd = isAdbShellCmd ? 'block' : 'none'
  const displayRefreshCmd = isRefreshCmd ? 'block' : 'none'
  
  // Build cmdType selector with dynamic selection
  const selCmdType = `<select style="width:120px;" class="cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="cmdType">
    <option value="adb-shell"${isAdbShellCmd ? ' selected' : ''}>{{ADB Shell}}</option>
    <option value="refresh-cmd"${isRefreshCmd ? ' selected' : ''}>{{Refresh Cmd}}</option>
    <option value="plugin" style="display:none;"${isPluginCmd ? ' selected' : ''}>{{Plugin}}</option>
  </select>`

  // Build complete row HTML with template literals (optimal V8 performance)
  const testButtons = is_numeric(_cmd.id) 
    ? '<a class="btn btn-default btn-xs cmdAction" data-action="configure"><i class="fas fa-cogs"></i></a> <a class="btn btn-default btn-xs cmdAction" data-action="test"><i class="fas fa-rss"></i> {{Tester}}</a>'
    : ''
  
  const rowHtml = `
    <td class="hidden-xs"><span class="cmdAttr" data-l1key="id"></span></td>
    <td>
      <div class="input-group">
        <input class="cmdAttr form-control input-sm roundedLeft" data-l1key="name" placeholder="{{Nom de la commande}}">
        <span class="input-group-btn"><a class="cmdAction btn btn-sm btn-default" data-l1key="chooseIcon" title="{{Choisir une icône}}"><i class="fas fa-icons"></i></a></span>
        <span class="cmdAttr input-group-addon roundedRight" data-l1key="display" data-l2key="icon" style="font-size:19px;padding:0 5px 0 0!important;"></span>
      </div>
      <select class="cmdAttr form-control input-sm" data-l1key="value" style="display:none;margin-top:5px;" title="{{Commande info liée}}">
        <option value="">{{Aucune}}</option>
      </select>
    </td>
    <td><span class="cmdType" style="display:${displayCmdType};" type="${init(cmdType)}">${selCmdType}</span></td>
    <td>
      <span class="type" style="display:${displayTypeSubType};" type="${init(_cmd.type)}">${jeedom.cmd.availableType()}</span>
      <span class="subType" style="display:${displayTypeSubType};" subType="${init(_cmd.subType)}"></span>
    </td>
    <td>
      <textarea rows="2" class="cmdAttr form-control input-sm adb-shell-cmd" data-l1key="configuration" data-l2key="adb-shell-command" placeholder="{{Commande ADB Shell}}" style="display:${displayAdbCmd};"></textarea>
      <select class="cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="cmdToRefresh" style="display:${displayRefreshCmd};margin-top:5px;" title="{{Commande info à rafraîchir}}">
        <option value="">{{Aucune}}</option>
      </select>
    </td>
    <td>
      <label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isVisible"/>{{Afficher}}</label> 
      <label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="isHistorized"/>{{Historiser}}</label> 
      <label class="checkbox-inline"><input type="checkbox" class="cmdAttr" data-l1key="display" data-l2key="invertBinary"/>{{Inverser}}</label> 
      <div style="margin-top:7px;">
        <input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="minValue" placeholder="{{Min}}" title="{{Min}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">
        <input class="tooltips cmdAttr form-control input-sm" data-l1key="configuration" data-l2key="maxValue" placeholder="{{Max}}" title="{{Max}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">
        <input class="tooltips cmdAttr form-control input-sm" data-l1key="unite" placeholder="Unité" title="{{Unité}}" style="width:30%;max-width:80px;display:inline-block;margin-right:2px;">
      </div>
    </td>
    <td><span class="cmdAttr" data-l1key="htmlstate"></span></td>
    <td>
      ${testButtons}
      <i class="fas fa-minus-circle pull-right cmdAction cursor" data-action="remove" title="{{Supprimer la commande}}"></i>
    </td>`
  
  // Create and configure row element (optimal: Object.assign for batch properties)
  const newRow = Object.assign(document.createElement('tr'), {
    className: 'cmd',
    innerHTML: rowHtml
  })
  newRow.setAttribute('data-cmd_id', init(_cmd.id))
  
  // Cache table body for performance (with optional chaining)
  const tableBody = document.querySelector(`${SELECTORS.TABLE_CMD} tbody`)
  if (!tableBody) return console.error('Table body not found')
  
  tableBody.appendChild(newRow)
  
  // Cache eqLogic ID to avoid multiple DOM queries
  const eqLogicIdElement = document.querySelector(SELECTORS.EQ_ID)
  if (!eqLogicIdElement) return console.error('Equipment ID element not found')
  
  const eqLogicId = eqLogicIdElement.jeeValue()
  
  // Single optimized call to get all commands
  jeedom.eqLogic.getCmd({
    id: eqLogicId,
    error: (error) => {
      jeedomUtils.showAlert({ message: error.message, level: 'danger' })
    },
    success: (cmds) => {
      // Filter info commands once
      const infoCmds = cmds.filter(cmd => cmd.type === 'info')
      
      // Cache selects to avoid multiple queries (using constants)
      const valueSelect = newRow.querySelector(SELECTORS.VALUE_SELECT)
      const refreshSelect = newRow.querySelector(SELECTORS.REFRESH_SELECT)
      
      // Build options HTML (map().join() is clearer than reduce for simple cases)
      if (valueSelect) {
        const allInfoOptions = infoCmds
          .map(cmd => `<option value="${init(cmd.id)}">${init(cmd.name)}</option>`)
          .join('')
        valueSelect.insertAdjacentHTML('beforeend', allInfoOptions)
      }
      
      if (refreshSelect) {
        // Filter and map for better readability
        const adbShellOptions = infoCmds
          .filter(cmd => {
            const cfg = cmd.configuration
            return cfg?.cmdType === 'adb-shell' || cfg?.['adb-shell-command']
          })
          .map(cmd => `<option value="${init(cmd.id)}">${init(cmd.name)}</option>`)
          .join('')
        refreshSelect.insertAdjacentHTML('beforeend', adbShellOptions)
      }
      
      // Set values and update display after both selects are populated
      newRow.setJeeValues(_cmd, '.cmdAttr')
      jeedom.cmd.changeType(newRow, init(_cmd.subType))
      
      // Global refresh command: already handled in initial display, just exit
      if (isGlobalRefresh) {
        return
      }
      
      // Auto-detect cmdType for existing commands without explicit configuration
      const cmdTypeSelect = newRow.querySelector(SELECTORS.CMD_TYPE_SELECT)
      if (cmdTypeSelect && (!_cmd.configuration.cmdType || _cmd.configuration.cmdType === '')) {
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



// Handle cmdType change with event delegation (optimal)
(() => {
  const { TABLE_CMD, CMD_TYPE_SELECT } = SELECTORS
  const tableCmdElement = document.querySelector(TABLE_CMD)
  if (tableCmdElement && !tableCmdElement._cmdTypeListenerAttached) {
    tableCmdElement.addEventListener('change', (event) => {
      if (!event.target.matches(CMD_TYPE_SELECT)) return
      
      const tr = event.target.closest('tr')
      const cmdType = event.target.value
      
      // Cache all DOM elements once
      const elements = {
        type: tr.querySelector('.type'),
        subType: tr.querySelector('.subType'),
        adbShellCmd: tr.querySelector('.adb-shell-cmd'),
        cmdToRefresh: tr.querySelector('.cmdAttr[data-l2key=cmdToRefresh]'),
        typeInput: tr.querySelector('.cmdAttr[data-l1key=type]'),
        subTypeInput: tr.querySelector('.cmdAttr[data-l1key=subType]')
      }
      
      if (cmdType === 'refresh-cmd') {
        // Refresh mode: force action/other type, hide type/subtype, show cmdToRefresh select
        if (elements.typeInput) elements.typeInput.value = 'action'
        if (elements.subTypeInput) elements.subTypeInput.value = 'other'
        jeedom.cmd.changeType(tr, 'other')
        if (elements.type) elements.type.unseen()
        if (elements.subType) elements.subType.unseen()
        if (elements.adbShellCmd) elements.adbShellCmd.unseen()
        if (elements.cmdToRefresh) elements.cmdToRefresh.seen()
      } else if (cmdType === 'adb-shell') {
        // ADB Shell mode: set action/other for new commands, keep existing type otherwise
        const cmdId = tr.getAttribute('data-cmd_id')
        const isNewCommand = !cmdId || cmdId === '' || cmdId === 'null' || cmdId === 'undefined'
        if (isNewCommand) {
          if (elements.typeInput) elements.typeInput.value = 'action'
          if (elements.subTypeInput) elements.subTypeInput.value = 'other'
          jeedom.cmd.changeType(tr, 'other')
        } else {
          jeedom.cmd.changeType(tr, elements.subTypeInput?.value)
        }
        if (elements.type) elements.type.seen()
        if (elements.subType) elements.subType.seen()
        if (elements.adbShellCmd) elements.adbShellCmd.seen()
        if (elements.cmdToRefresh) elements.cmdToRefresh.unseen()
      } else {
        // Plugin/Standard mode: show type/subtype, hide custom fields
        if (elements.type) elements.type.seen()
        if (elements.subType) elements.subType.seen()
        if (elements.adbShellCmd) elements.adbShellCmd.unseen()
        if (elements.cmdToRefresh) elements.cmdToRefresh.unseen()
      }
    })
    tableCmdElement._cmdTypeListenerAttached = true
  }
})()

// Helper function to update pairing status badge
const updatePairingStatusBadge = (statusElement, isPaired) => {
  if (isPaired) {
    statusElement.removeClass('label-danger').addClass('label-success')
    statusElement.innerHTML = '<i class="fas fa-check-circle"></i> {{Appairé}}'
  } else {
    statusElement.removeClass('label-success').addClass('label-danger')
    statusElement.innerHTML = '<i class="fas fa-times-circle"></i> {{Non appairé}}'
  }
  statusElement.seen()
}

const printEqLogic = (_eqLogic) => {
  // Si la configuration use_adb n'existe pas encore (nouvel équipement), on force le décochage
  if (_eqLogic?.configuration?.use_adb === undefined) {
    document.querySelector('.eqLogicAttr[data-l2key="use_adb"]')?.jeeValue(0)
  }
  
  // Update pairing status badges based on configuration
  const adbPairedStatus = _eqLogic?.configuration?.adb_paired_status
  const tvremotePairedStatus = _eqLogic?.configuration?.tvremote_paired_status
  
  // Update ADB pairing status badge
  const adbStatusElement = document.getElementById('adb-pairing-status')
  if (adbStatusElement && adbPairedStatus !== undefined) {
    updatePairingStatusBadge(adbStatusElement, parseInt(adbPairedStatus, 10) === 1)
  }
  
  // Update TVRemote pairing status badge
  const tvremoteStatusElement = document.getElementById('tvremote-pairing-status')
  if (tvremoteStatusElement && tvremotePairedStatus !== undefined) {
    updatePairingStatusBadge(tvremoteStatusElement, parseInt(tvremotePairedStatus, 10) === 1)
  }
}

// Expose functions globally for Jeedom to call them
window.addCmdToTable = addCmdToTable
window.printEqLogic = printEqLogic

// DOM cache to avoid multiple getElementById calls
const DOM_CACHE = {
  hostAddr: null,
  macAddr: null,
  portNum: null,
  pairCode: null,
  get: function(id) {
    if (!this[id]) this[id] = document.getElementById(id)
    return this[id]
  }
}

// Event delegation: single listener instead of multiple (optimal)
for (const element of document.querySelectorAll('.pluginAction[data-action=openLocation]')) {
  element.addEventListener('click', (event) => {
    window.open(event.currentTarget.getAttribute('data-location'), '_blank', null)
  })
}

for (const element of document.querySelectorAll('.customclass-beginpairing')) {
  element.addEventListener('click', () => {
    domUtils.ajax({
      type: 'POST',
      url: AJAX_URL,
      data: {
        action: 'beginPairing',
        mac: DOM_CACHE.get('macAddr')?.value,
        host: DOM_CACHE.get('hostAddr')?.value,
        port: DOM_CACHE.get('portNum')?.value
      },
      dataType: 'json',
      error: (request, status, error) => handleAjaxError(request, status, error),
      success: (data) => {
        if (data.state !== 'ok') {
          jeedomUtils.showAlert({ message: data.result, level: 'danger' })
          return
        }
        jeedomUtils.showAlert({ message: `{{Lancement Appairage (Actif pendant 5min)}} :: ${data.result}`, level: 'warning' })
      }
    })
  })
}

for (const element of document.querySelectorAll('.customclass-sendpaircode')) {
  element.addEventListener('click', () => {
    domUtils.ajax({
      type: 'POST',
      url: AJAX_URL,
      data: {
        action: 'sendPairCode',
        mac: DOM_CACHE.get('macAddr')?.value,
        host: DOM_CACHE.get('hostAddr')?.value,
        port: DOM_CACHE.get('portNum')?.value,
        paircode: DOM_CACHE.get('pairCode')?.value
      },
      dataType: 'json',
      error: (request, status, error) => handleAjaxError(request, status, error),
      success: (data) => {
        if (data.state !== 'ok') {
          jeedomUtils.showAlert({ message: data.result, level: 'danger' })
          return
        }
        jeedomUtils.showAlert({ message: `{{Envoi Code Appairage}} :: ${data.result}`, level: 'success' })
      }
    })
  })
}

for (const element of document.querySelectorAll('.customclass-beginpairingadb')) {
  element.addEventListener('click', () => {
    domUtils.ajax({
      type: 'POST',
      url: AJAX_URL,
      data: {
        action: 'beginPairingAdb',
        mac: DOM_CACHE.get('macAddr')?.value,
        host: DOM_CACHE.get('hostAddr')?.value
      },
      dataType: 'json',
      error: (request, status, error) => handleAjaxError(request, status, error),
      success: (data) => {
        if (data.state !== 'ok') {
          jeedomUtils.showAlert({ message: data.result, level: 'danger' })
          return
        }
        jeedomUtils.showAlert({ message: '{{Appairage ADB lancé. Veuillez vérifier votre TV et ACCEPTER la demande d\'autorisation ADB qui s\'affiche à l\'écran.}}', level: 'warning' })
      }
    })
  })
}

for (const element of document.querySelectorAll(SELECTORS.SCAN_BUTTONS)) {
  element.addEventListener('click', (event) => {
    changeScanState(event.currentTarget.getAttribute('data-scanState'))
  })
}

const changeScanState = (_scanState) => {
  domUtils.ajax({
    type: 'POST',
    url: AJAX_URL,
    data: {
      action: 'changeScanState',
      scanState: _scanState
    },
    dataType: 'json',
    error: (request, status, error) => handleAjaxError(request, status, error),
    success: (data) => {
      if (data.state !== 'ok') {
        jeedomUtils.showAlert({ message: data.result, level: 'danger' })
      }
    }
  })
}

// Store handlers globally to ensure they persist across script reloads
window.tvremoteEventHandlers = window.tvremoteEventHandlers || {}

// Define handlers only if not already defined
if (!window.tvremoteEventHandlers.adbPairing) {
  window.tvremoteEventHandlers.adbPairing = function(event) {
    const _option = event.detail
    console.log('[DEBUG] adbPairingResult event received:', _option)
    if (!_option) {
      console.log('[DEBUG] adbPairingResult: _option is null or undefined')
      return
    }
    
    const { friendly_name, mac, adb_paired, message: errorMsg, auto_detected } = _option
    const deviceName = friendly_name || mac
    const adbStatus = document.getElementById('adb-pairing-status')
    
    console.log('[DEBUG] adbPairingResult:', { mac, adb_paired, deviceName, auto_detected, adbStatus })
    
    if (adb_paired === 1) {
      if (!auto_detected) {
        console.log('[DEBUG] Showing success alert for', deviceName)
        jeedomUtils.showAlert({ message: `{{Appairage ADB réussi pour}} ${deviceName}`, level: 'success' })
      } else {
        console.log('[DEBUG] Success alert suppressed (auto_detected=true)')
      }
      if (adbStatus) {
        console.log('[DEBUG] Updating badge to success')
        updatePairingStatusBadge(adbStatus, true)
      } else {
        console.log('[DEBUG] Badge element not found')
      }
    } else if (adb_paired === 0) {
      const finalErrorMsg = errorMsg || '{{Erreur inconnue}}'
      console.log('[DEBUG] Showing error alert:', finalErrorMsg)
      jeedomUtils.showAlert({ message: `{{Échec de l'appairage ADB pour}} ${deviceName} : ${finalErrorMsg}`, level: 'danger' })
      if (adbStatus) {
        updatePairingStatusBadge(adbStatus, false)
      }
    }
  }
}

if (!window.tvremoteEventHandlers.tvremotePairing) {
  window.tvremoteEventHandlers.tvremotePairing = function(event) {
    const _option = event.detail
    if (!_option) return
    
    const { friendly_name, mac, tvremote_paired, message: errorMsg, auto_detected } = _option
    const deviceName = friendly_name || mac
    const tvremoteStatus = document.getElementById('tvremote-pairing-status')
    
    if (tvremote_paired === 1) {
      if (!auto_detected) {
        jeedomUtils.showAlert({ message: `{{Appairage TVRemote réussi pour}} ${deviceName}`, level: 'success' })
      }
      if (tvremoteStatus) {
        updatePairingStatusBadge(tvremoteStatus, true)
      }
    } else if (tvremote_paired === 0) {
      const finalErrorMsg = errorMsg || '{{Erreur inconnue}}'
      jeedomUtils.showAlert({ message: `{{Échec de l'appairage TVRemote pour}} ${deviceName} : ${finalErrorMsg}`, level: 'danger' })
      if (tvremoteStatus) {
        updatePairingStatusBadge(tvremoteStatus, false)
      }
    }
  }
}

if (!window.tvremoteEventHandlers.scanResult) {
  window.tvremoteEventHandlers.scanResult = function(event) {
    const _option = event.detail
    if (_option?.friendly_name) {
      if (_option.isNew === 1) {
        jeedomUtils.showAlert({ message: `[SCAN] TVRemote AJOUTE :: ${_option.friendly_name}`, level: 'success' })
      } else if (_option.isNew === 0) {
        jeedomUtils.showAlert({ message: `[SCAN] TVRemote MAJ :: ${_option.friendly_name}`, level: 'warning' })
      }
    }
  }
}

// Remove old listeners if they exist
document.body.removeEventListener('tvremote::adbPairingResult', window.tvremoteEventHandlers.adbPairing)
document.body.removeEventListener('tvremote::tvremotePairingResult', window.tvremoteEventHandlers.tvremotePairing)
document.body.removeEventListener('tvremote::scanResult', window.tvremoteEventHandlers.scanResult)

// Add listeners using global references
document.body.addEventListener('tvremote::adbPairingResult', window.tvremoteEventHandlers.adbPairing)
document.body.addEventListener('tvremote::tvremotePairingResult', window.tvremoteEventHandlers.tvremotePairing)
document.body.addEventListener('tvremote::scanResult', window.tvremoteEventHandlers.scanResult)

document.body.addEventListener('tvremote::scanState', (event) => {
  const scanState = event.detail?.scanState
  
  const scanButtons = document.querySelectorAll(SELECTORS.SCAN_BUTTONS)
  const scanIcons = document.querySelectorAll(SELECTORS.SCAN_ICONS)
  const scanTexts = document.querySelectorAll(SELECTORS.SCAN_TEXTS)
  
  jeedomUtils.hideAlert()
  
  const isScanOn = scanState === 'scanOn'
  
  // Batch DOM updates with for...of (faster than forEach)
  for (const el of scanButtons) {
    el.setAttribute('data-scanState', isScanOn ? 'scanOff' : 'scanOn')
    el.removeClass(isScanOn ? 'logoPrimary' : 'logoSecondary')
      .addClass(isScanOn ? 'logoSecondary' : 'logoPrimary')
  }
  
  for (const el of scanIcons) {
    if (isScanOn) {
      el.addClass('icon_red')
    } else {
      el.removeClass('icon_red')
    }
  }
  
  for (const el of scanTexts) {
    el.textContent = isScanOn ? '{{Stop Scan}}' : '{{Scan}}'
  }
  
  if (isScanOn) {
    jeedomUtils.showAlert({ message: '{{Mode SCAN actif pendant 60 secondes. (Cliquez sur STOP SCAN pour arrêter la découverte des équipements)}}', level: 'warning' })
  } else {
    window.location.reload()
  }
})

// Update pairing status badges when configuration changes (for...of optimization)
for (const element of document.querySelectorAll('.eqLogicAttr[data-l2key="tvremote_paired_status"]')) {
  element.addEventListener('change', (event) => {
    const statusElement = document.getElementById('tvremote-pairing-status')
    if (statusElement) {
      updatePairingStatusBadge(statusElement, parseInt(event.target.value, 10) === 1)
    }
  })
}

for (const element of document.querySelectorAll('.eqLogicAttr[data-l2key="adb_paired_status"]')) {
  element.addEventListener('change', (event) => {
    const statusElement = document.getElementById('adb-pairing-status')
    if (statusElement) {
      updatePairingStatusBadge(statusElement, parseInt(event.target.value, 10) === 1)
    }
  })
}

})() // End IIFE protection
