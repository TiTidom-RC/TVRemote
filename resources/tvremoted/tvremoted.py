import datetime
import logging
import argparse
import json
try:
    import resource
    HAS_RESOURCE = True
except ImportError:
    HAS_RESOURCE = False
import sys
import os
import signal
import asyncio
import time
import traceback
import ipaddress

from config import Config
from jeedom.utils import Utils
from jeedom.aio_connector import Listener, Publisher

# Import pour ZeroConf
try:
    from zeroconf import ServiceStateChange, Zeroconf
    from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf
except ImportError as e: 
    print("[DAEMON][IMPORT] Exception Error: importing module ZeroConf ::", e)
    sys.exit(1)

# Import pour AndroidTVRemote2
try:
    from androidtvremote2 import AndroidTVRemote, CannotConnect, ConnectionClosed, InvalidAuth, VolumeInfo
except ImportError as e: 
    print("[DAEMON][IMPORT] Exception Error: importing module AndroidTVRemote2 ::", e)
    sys.exit(1)

# Import pour ADB Shell
try:
    from adb_shell.adb_device_async import AdbDeviceTcpAsync
    from adb_shell.auth.sign_pythonrsa import PythonRSASigner
    from adb_shell.auth.keygen import keygen
    from adb_shell.exceptions import TcpTimeoutException, InvalidResponseError, DeviceAuthError
except ImportError as e: 
    print("[DAEMON][IMPORT] Exception Error: importing module adb_shell ::", e)
    sys.exit(1)


# Écran allumé ? Commande de python-androidtv (CMD_SCREEN_ON), utilisée par l'intégration ADB de Home Assistant
ADB_SCREEN_ON = "(dumpsys power | grep 'Display Power' | grep -q 'state=ON' || dumpsys power | grep -q 'mScreenOn=true' || dumpsys display | grep -q 'mScreenState=ON')"
# Power On / Power Off en ADB : la touche Power (qui bascule) n'est envoyée que si l'écran n'est pas déjà dans l'état demandé
ADB_POWER_COMMANDS = {
    'power_on': ADB_SCREEN_ON + ' || input keyevent KEYCODE_POWER',
    'power_off': ADB_SCREEN_ON + ' && input keyevent KEYCODE_POWER',
}


def load_adb_signer(config: Config) -> PythonRSASigner:
    """Clé ADB du plugin (commune à tous les appareils), lue sur le disque à chaque appel : une clé régénérée est prise en compte"""
    with open(config.adb_key_file, 'r') as f:
        priv = f.read()
    with open(config.adb_pub_file, 'r') as f:
        pub = f.read()
    return PythonRSASigner(pub, priv)

          
class EQRemote(object):
    """This is the Remote Device class"""

    def __init__(self, _mac, _host, _config: Config, _jeedom_publisher, _enable_ime: bool = True) -> None:
        # Standard Init of class
        self._config = _config
        self._remote = None
        self._macAddr = _mac
        self._host = _host
        self._enable_ime = _enable_ime
        self._logger = logging.getLogger(__name__)
        self._jeedom_publisher = _jeedom_publisher
        self._loop = asyncio.get_running_loop()
        self._main_task: asyncio.Task | None = None  # Reference to the main loop task
        # Exponential backoff for reconnection attempts
        self._reconnect_delay = self._config.reconnect_delay_min
        self._pairingLost = asyncio.Event()  # Reconnexion de la bibliothèque refusée faute d'appairage
        self._available = False  # Connexion Google TV établie : l'état de la TV (allumée, mute) est alors poussé par elle à chaque changement
        # Jeedom n'est prévenu qu'au premier échec d'une série de tentatives (remis à zéro à la connexion)
        self._notPairedNotified = False
        self._unreachableNotified = False

    @property
    def host(self) -> str:
        return self._host

    @property
    def enable_ime(self) -> bool:
        return self._enable_ime

    # Commandes à état (même touche pour les deux sens : elle bascule) -> (état concerné, valeur demandée)
    STATEFUL_ACTIONS = {'power_on': ('is_on', True), 'power_off': ('is_on', False), 'mute_on': ('muted', True), 'mute_off': ('muted', False)}

    def is_already(self, action: str) -> bool:
        """La TV est-elle déjà dans l'état demandé par Power On/Off ou Mute On/Off ? Seulement si la connexion Google TV est établie
        (état poussé par la TV) et l'état connu ; sinon False : la touche est envoyée comme avant"""
        target = self.STATEFUL_ACTIONS.get(action)
        if target is None or self._remote is None or not self._available:
            return False
        state, wanted = target
        if state == 'is_on':
            current = self._remote.is_on
        else:
            volume_info = self._remote.volume_info
            current = volume_info.get('muted') if volume_info else None
        return current is not None and bool(current) == wanted

    @staticmethod
    def _format_timestamp(timestamp: int) -> str:
        """Format Unix timestamp to readable string"""
        return datetime.datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y - %H:%M:%S")

    @staticmethod
    def _volume_fields(volume_info: VolumeInfo | None) -> dict:
        """Champs de volume à envoyer à Jeedom, vide si la TV ne les a pas donnés (une valeur inconnue n'écrase pas la dernière connue)"""
        if volume_info is None or not all(key in volume_info for key in ('level', 'muted', 'max')):
            return {}
        return {
            'volume_level': volume_info['level'],
            'volume_muted': 1 if volume_info['muted'] else 0,
            'volume_max': volume_info['max']
        }

    async def _apply_backoff_delay(self) -> None:
        """Apply exponential backoff delay before next reconnection attempt"""
        self._logger.debug("[EQRemote][MAIN][%s] Waiting %ds before reconnection attempt (exponential backoff)", self._macAddr, self._reconnect_delay)
        await asyncio.sleep(self._reconnect_delay)
        self._reconnect_delay = min(self._reconnect_delay * 2, self._config.reconnect_delay_max)

    async def _notify_unreachable(self) -> None:
        """Premier échec de connexion d'une série : la TV est signalée hors ligne"""
        if self._unreachableNotified:
            return
        self._unreachableNotified = True
        currentTime = int(time.time())
        data = {
            'mac': self._macAddr,
            'online': 0,
            'updatelasttime': self._format_timestamp(currentTime),
            'updatelasttimets': currentTime,
            'realtime': 1
        }
        await self._jeedom_publisher.add_change('devicesRT::' + data['mac'], data)

    @property
    def is_running(self) -> bool:
        """Boucle de l'appareil en cours (False si elle s'est arrêtée, y compris sur une erreur)"""
        return self._main_task is not None and not self._main_task.done()

    def _on_pairing_lost(self) -> None:
        """Appelé par la bibliothèque quand une reconnexion est refusée faute d'appairage : elle ne réessaie plus, la boucle du plugin reprend la main"""
        self._logger.info("[EQRemote][MAIN][%s] Pairing lost while reconnecting :: back to the connection loop", self._macAddr)
        self._pairingLost.set()

    async def _wait_for_pairing_lost(self) -> None:
        """Garde la tâche en vie (notifications de la bibliothèque) jusqu'à la perte de l'appairage ou l'arrêt du démon"""
        while not self._config.is_ending:
            try:
                await asyncio.wait_for(self._pairingLost.wait(), timeout=60)
            except asyncio.TimeoutError:
                continue
            self._pairingLost.clear()
            return

    async def _notify_not_paired(self, exc: Exception) -> None:
        """TV pas (ou plus) appairée : état d'attente, Jeedom n'est prévenu qu'une fois par série de tentatives (une fois l'envoi réussi)"""
        if self._notPairedNotified:
            self._logger.debug("[EQRemote][MAIN][%s] Not Paired (still waiting for pairing) :: %s", self._macAddr, exc)
            return
        self._logger.warning("[EQRemote][MAIN][%s] Not Paired. Exception :: %s", self._macAddr, exc)
        data = {
            'PairingExc': str(exc),
            'pairing_mac': self._macAddr,
            'pairing_host': self._host,
            'pairing_value': 0
        }
        try:
            self._notPairedNotified = await self._jeedom_publisher.send_to_jeedom(data)
        except Exception as e:
            self._logger.warning("[EQRemote][MAIN][%s] Cannot send the pairing state to Jeedom (will retry) :: %s", self._macAddr, e)

    async def _connect_until_success(self) -> bool:
        """Tente la connexion jusqu'à ce qu'elle réussisse ; False si le démon s'arrête avant"""
        assert self._remote is not None
        while not self._config.is_ending:
            try:
                await self._remote.async_connect()
            except InvalidAuth as exc:
                await self._notify_not_paired(exc)
            except CannotConnect as exc:
                self._logger.warning("[EQRemote][MAIN][%s] Cannot connect (device may be offline) :: %s", self._macAddr, exc)
                await self._notify_unreachable()
            except ConnectionClosed as exc:
                self._logger.error("[EQRemote][MAIN][%s] Connection closed unexpectedly. Exception :: %s", self._macAddr, exc)
                await self._notify_unreachable()
            except Exception as e:
                self._logger.error("[EQRemote][Connect][%s] Exception :: %s", self._macAddr, e)
                self._logger.debug(traceback.format_exc())
                await self._notify_unreachable()
            else:
                # Reset reconnection delay and failure notifications on successful connection
                self._reconnect_delay = self._config.reconnect_delay_min
                self._notPairedNotified = False
                self._unreachableNotified = False
                self._available = True
                return True
            # Exponential backoff: wait before retry and increase delay
            await self._apply_backoff_delay()
        return False

    def _send_initial_state(self) -> None:
        """État complet de la TV, envoyé à Jeedom à chaque connexion réussie"""
        assert self._remote is not None
        try:
            self._logger.info("[EQRemote][MAIN][%s] Device_Info :: %s | Is_On :: %s | Current_App :: %s | Volume_Info :: %s", self._macAddr, self._remote.device_info, self._remote.is_on, self._remote.current_app, self._remote.volume_info)
            currentTime = int(time.time())
            data = {
                'mac': self._macAddr,
                'online': 1,
                'is_on': 1 if self._remote.is_on else 0,
                'current_app': self._remote.current_app,
                **self._volume_fields(self._remote.volume_info),
                'updatelasttime': self._format_timestamp(currentTime),
                'updatelasttimets': currentTime,
                'realtime': 1
            }
            self._loop.create_task(self._jeedom_publisher.add_change('devicesRT::' + data['mac'], data))
        except Exception as e:
            self._logger.error('[EQRemote][MAIN-Publisher][%s] Exception :: %s', self._macAddr, e)
            self._logger.debug(traceback.format_exc())

    async def main(self) -> None:
        """
        The is the entry point of your class EQRemote.
        You should start the asyncio task with this function like this: `asyncio.createtask(myEQRemote.main())`
        """
        try:
            self._logger.info("[EQRemote][MAIN][%s] Starting Main for Host :: %s", self._macAddr, self._host)

            self._remote = AndroidTVRemote(self._config.client_name, self._config.cert_file, self._config.key_file, self._host, enable_ime=self._enable_ime)

            if self._remote is None:
                self._logger.error("[EQRemote][Remote] Object Creation Failed :: Object is None !")
                return

            if await self._remote.async_generate_cert_if_missing():
                self._logger.info("[EQRemote][CERT][%s] Generated New Cert/Key Files :: %s | %s", self._macAddr, self._config.cert_file, self._config.key_file)

            def is_available_updated(is_available: bool) -> None:
                self._logger.debug("[EQRemote][Is_Available][%s] Notification :: %s", self._macAddr, is_available)
                self._available = is_available
                try:
                    # UpdateLastTime
                    currentTime = int(time.time())
                    currentTimeStr = self._format_timestamp(currentTime)
                    
                    _is_available = 1 if is_available else 0
                    
                    data = {
                        'mac': self._macAddr,
                        'online': _is_available,
                        'updatelasttime': currentTimeStr,
                        'updatelasttimets': currentTime,
                        'realtime': 1
                    }
                    # Envoi vers Jeedom
                    self._loop.create_task(self._jeedom_publisher.add_change('devicesRT::' + data['mac'], data))
                except Exception as e:
                    self._logger.error('[EQRemote][Is_Available] Exception :: %s', e)
                    self._logger.debug(traceback.format_exc())

            def is_on_updated(is_on: bool) -> None:
                self._logger.debug("[EQRemote][Is_On][%s] Notification :: %s", self._macAddr, is_on)
                try:
                    # UpdateLastTime
                    currentTime = int(time.time())
                    currentTimeStr = self._format_timestamp(currentTime)
                    
                    _isOn = 1 if is_on else 0
                    data = {
                        'mac': self._macAddr,
                        'online': 1,
                        'is_on': _isOn,
                        'updatelasttime': currentTimeStr,
                        'updatelasttimets': currentTime,
                        'realtime': 1
                    }
                    # Envoi vers Jeedom
                    self._loop.create_task(self._jeedom_publisher.add_change('devicesRT::' + data['mac'], data))
                except Exception as e:
                    self._logger.error('[EQRemote][Is_On] Exception :: %s', e)
                    self._logger.debug(traceback.format_exc())
                
            def current_app_updated(current_app: str) -> None:
                self._logger.debug("[EQRemote][Current_App][%s] Notification :: %s", self._macAddr, current_app)
                try:
                    # UpdateLastTime
                    currentTime = int(time.time())
                    currentTimeStr = self._format_timestamp(currentTime)
                    
                    data = {
                        'mac': self._macAddr,
                        'online': 1,
                        'current_app': current_app,
                        'updatelasttime': currentTimeStr,
                        'updatelasttimets': currentTime,
                        'realtime': 1
                    }
                    # Envoi vers Jeedom
                    self._loop.create_task(self._jeedom_publisher.add_change('devicesRT::' + data['mac'], data))
                except Exception as e:
                    self._logger.error('[EQRemote][Current_App] Exception :: %s', e)
                    self._logger.debug(traceback.format_exc())

            def volume_info_updated(volume_info: VolumeInfo) -> None:
                self._logger.debug("[EQRemote][Volume_Info][%s] Notification :: %s", self._macAddr, volume_info)
                try:
                    # UpdateLastTime
                    currentTime = int(time.time())
                    currentTimeStr = self._format_timestamp(currentTime)
                    
                    volumeFields = self._volume_fields(volume_info)
                    if not volumeFields:
                        return

                    data = {
                        'mac': self._macAddr,
                        **volumeFields,
                        'updatelasttime': currentTimeStr,
                        'updatelasttimets': currentTime,
                        'realtime': 1
                    }
                    # Envoi vers Jeedom
                    self._loop.create_task(self._jeedom_publisher.add_change('devicesRT::' + data['mac'], data))
                except Exception as e:
                    self._logger.error('[EQRemote][Volume_Info] Exception :: %s', e)
                    self._logger.debug(traceback.format_exc())

            # Connexion, état initial, puis attente des notifications ; la bibliothèque gère les reconnexions (keep_reconnecting),
            # sauf quand la TV les refuse faute d'appairage : retour à la boucle de connexion, qui le signale à Jeedom
            callbacksAdded = False
            while not self._config.is_ending:
                if not await self._connect_until_success():
                    break
                if not callbacksAdded:
                    # Branchés après la première connexion : son état (remote_start) est envoyé par _send_initial_state(), pas en double
                    self._remote.add_is_available_updated_callback(is_available_updated)
                    self._remote.add_is_on_updated_callback(is_on_updated)
                    self._remote.add_current_app_updated_callback(current_app_updated)
                    self._remote.add_volume_info_updated_callback(volume_info_updated)
                    callbacksAdded = True
                self._remote.keep_reconnecting(self._on_pairing_lost)
                self._send_initial_state()
                await self._wait_for_pairing_lost()

        except asyncio.CancelledError:
            self._logger.debug("[EQRemote] Stop Main for device %s (%s)", self._macAddr, self._host)
        except Exception as e:
            self._logger.error("[EQRemote][MAIN] Exception :: %s", e)
            self._logger.debug(traceback.format_exc())
        finally:
            # Cleanup resources
            self._available = False
            if self._remote is not None:
                try:
                    self._remote.disconnect()
                except Exception as e:
                    self._logger.debug("[EQRemote][MAIN][%s] Error during disconnect cleanup :: %s", self._macAddr, e)
            self._main_task = None
            self._logger.debug("[EQRemote][MAIN][%s] Main loop stopped", self._macAddr)
        
    async def remove(self) -> None:
        """Call it to disconnect from a EQRemote"""
        self._logger.debug("[EQRemote] Removing device %s (%s)", self._macAddr, self._host)
        # Disconnect is already handled in main() finally block
        # Just ensure the reference is cleared
        self._remote = None
    
    async def send_command(self, action: str | None = None, value: str | None = None) -> None:
        """Call it to send command to EQRemote"""
        try:
            if self._remote is None:
                self._logger.error("[EQRemote][SendCommand] Remote is None")
                return
            if action in ('keycode', 'appcode'):
                self._logger.debug("[EQRemote][SendCmd - Key/App Code] %s :: %s", action, value)
                if value is not None:
                    if action == 'keycode':
                        self._remote.send_key_command(value)
                    elif action == 'appcode':
                        self._remote.send_launch_app_command(value)
            elif action in self._config.key_mapping:
                self._logger.debug("[EQRemote][SendCommand] %s :: %s", action, self._config.key_mapping[action])
                if action in ('oqee', 'youtube', 'netflix', 'primevideo', 'disneyplus', 'mycanal', 'plex', 'appletv', 'orangetv', 'molotov'):
                    self._remote.send_launch_app_command(self._config.key_mapping[action])
                else:
                    self._remote.send_key_command(self._config.key_mapping[action])
            else:
                self._logger.error("[EQRemote][SendCommand] Command Mapping :: %s :: Unknown Key !", action)
        except ValueError as e:
            self._logger.error("[EQRemote][SendCommand] Exception (ValueError) :: %s", e)
            self._logger.debug(traceback.format_exc())
        except ConnectionClosed as e:
            self._logger.warning("[EQRemote][SendCommand] Connection closed (device may be offline) :: %s", e)
        except Exception as e:
            self._logger.error("[EQRemote][SendCommand] Exception :: %s", e)
            self._logger.debug(traceback.format_exc())

class EQRemoteADB(object):
    """This is the Remote Device class using ADB"""

    def __init__(self, _mac, _host, _config: Config, _jeedom_publisher) -> None:
        # Standard Init of class
        self._config = _config
        self._adb = None
        self._macAddr = _mac
        self._host = _host
        self._port = 5555
        self._logger = logging.getLogger(__name__)
        self._jeedom_publisher = _jeedom_publisher
        self._loop = asyncio.get_running_loop()
        self._signer = None
        self._connected = False
        self._connection_task: asyncio.Task | None = None  # Track ongoing connection attempt
        self._pairing_mode = False  # Flag to indicate pairing is in progress
        self._main_task: asyncio.Task | None = None  # Reference to the main loop task
        self._adb_paired = 0  # Pairing status (0=not paired, 1=paired)
        # Exponential backoff for reconnection attempts
        self._reconnect_delay = self._config.reconnect_delay_min
        self._last_heartbeat = 0  # Timestamp of last heartbeat check
        # Connection mode and idle timeout management
        self._persistent_connection = False  # True = permanent, False = on-demand
        self._idle_timeout_minutes = self._config.adb_idle_timeout_default
        self._last_activity = 0  # Timestamp of last activity (command or heartbeat)

    @property
    def host(self) -> str:
        return self._host

    @property
    def is_running(self) -> bool:
        """Boucle de l'appareil en cours (False si elle s'est arrêtée, y compris sur une erreur)"""
        return self._main_task is not None and not self._main_task.done()

    async def _load_signer(self) -> bool:
        """Load the ADB signer from key file"""
        try:
            if os.path.exists(self._config.adb_key_file):
                self._signer = load_adb_signer(self._config)
                self._logger.debug("[EQRemoteADB][%s] ADB signer loaded", self._macAddr)
                return True
            else:
                self._logger.error("[EQRemoteADB][%s] ADB key file not found :: %s", self._macAddr, self._config.adb_key_file)
                return False
        except Exception as e:
            self._logger.error("[EQRemoteADB][%s] Error loading ADB signer :: %s", self._macAddr, e)
            self._logger.debug(traceback.format_exc())
            return False

    def _reset_state(self, clear_activity: bool = False) -> None:
        """Reset connection state

        Args:
            clear_activity: If True, clears _last_activity (voluntary disconnect).
                          If False, preserves it to allow reconnection within idle period.
        """
        self._connection_task = None
        self._connected = False
        self._last_heartbeat = 0  # Reset heartbeat timer
        if clear_activity:
            self._last_activity = 0  # Clear activity timer (voluntary disconnect)

    def _can_connect(self) -> bool:
        """Check if we can attempt a new connection
        In persistent mode: always try to reconnect when disconnected
        In on-demand mode: reconnect if still within idle timeout period (involuntary disconnect)
        """
        if not self._connected and not self._pairing_mode:
            if self._persistent_connection:
                return True
            # On-demand mode: reconnect if we're still within the idle timeout period
            if self._last_activity > 0:
                time_since_activity = time.time() - self._last_activity
                if time_since_activity < self._idle_timeout_minutes * 60:
                    return True  # Involuntary disconnect during idle period, reconnect
        return False

    def _is_connecting(self) -> bool:
        """Check if a connection is in progress"""
        return self._connection_task is not None and not self._connection_task.done()

    async def _notify_adb_status(self, connected: bool) -> None:
        """Statut de la connexion ADB vers Jeedom. 'online' n'est envoyé qu'à 1 (connexion ADB réussie : la TV est joignable) ;
        un échec ou une déconnexion ADB ne prouve pas que la TV est hors ligne (ports ADB fermés, débogage désactivé…),
        c'est la connexion Google TV qui le met à 0"""
        currentTime = int(time.time())
        data = {
            'mac': self._macAddr,
            'adb_connected': 1 if connected else 0,
            'updatelasttime': EQRemote._format_timestamp(currentTime),
            'updatelasttimets': currentTime,
            'realtime': 1
        }
        if connected:
            data['online'] = 1
        await self._jeedom_publisher.add_change('devicesRT::' + data['mac'], data)

    async def _close_after_failure(self) -> None:
        """Ferme la connexion après un échec ou une perte, sans effacer l'activité (reconnexion possible pendant la période d'inactivité)"""
        if self._adb is not None:
            try:
                await self._adb.close()
            except Exception:
                pass  # Ignore errors during cleanup
        self._reset_state(clear_activity=False)

    def _forget_on_demand_activity(self) -> None:
        """Mode à la demande, tentative de connexion ratée : plus de tentative en arrière-plan (aucune commande n'attend, la suivante
        réessaiera). Effacé avant toute attente, pour que l'autre appelant d'une tentative partagée ne relance pas entre-temps.
        Une connexion établie puis perdue garde son activité : elle est retentée (une fois, si cette tentative échoue)"""
        if not self._persistent_connection:
            self._last_activity = 0

    async def _connect(self) -> None:
        """Connexion ADB, seul chemin utilisé par la boucle et par les commandes : une tentative en cours est attendue, jamais doublée.
        Lève l'erreur de la tentative (connexion déjà refermée), ConnectionAbortedError si elle a été annulée (appairage)"""
        if self._connected:
            return
        if self._signer is None and not await self._load_signer():
            raise ConnectionError('ADB key not available')
        if self._adb is None:
            self._adb = AdbDeviceTcpAsync(self._host, self._port, default_transport_timeout_s=self._config.adb_timeout)
        # Tentative existante toujours réutilisée, même déjà terminée : tant qu'un appelant ne l'a pas close (_connection_task remis
        # à None après un succès ou un échec), son résultat vaut pour tous ; en lancer une autre doublerait la tentative
        if self._connection_task is None:
            self._logger.debug("[EQRemoteADB][CONNECT][%s] Connecting to ADB...", self._macAddr)
            self._connection_task = asyncio.create_task(
                self._adb.connect(
                    rsa_keys=[self._signer],
                    transport_timeout_s=self._config.adb_timeout,  # Explicit TCP connection timeout
                    auth_timeout_s=self._config.adb_auth_timeout_connect
                )
            )
        task = self._connection_task
        assert task is not None
        # Use auth timeout + 5s margin to allow for network delays
        connection_timeout = self._config.adb_auth_timeout_connect + 5
        try:
            # shield : la tentative est partagée ; l'annulation d'un appelant ne doit pas l'interrompre pour l'autre
            await asyncio.wait_for(asyncio.shield(task), timeout=connection_timeout)
        except asyncio.CancelledError:
            current = asyncio.current_task()
            if current is not None and current.cancelling():
                raise  # annulation de l'appelant (retrait de l'appareil, arrêt du démon) : jamais absorbée
            self._forget_on_demand_activity()
            await self._close_after_failure()
            raise ConnectionAbortedError('ADB connection attempt cancelled')
        except asyncio.TimeoutError:
            task.cancel()
            self._forget_on_demand_activity()
            await self._close_after_failure()
            raise
        except Exception:
            self._forget_on_demand_activity()
            await self._close_after_failure()
            raise
        if not self._connected:  # les deux appelants d'une même tentative reprennent ici : un seul enregistre la connexion
            self._connected = True
            self._connection_task = None
            self._last_heartbeat = time.time()  # Initialize heartbeat timer
            self._last_activity = time.time()   # Initialize activity timer for on-demand mode
            self._reconnect_delay = self._config.reconnect_delay_min  # Reset backoff on successful connection
            mode_str = "permanent" if self._persistent_connection else "on-demand"
            self._logger.info("[EQRemoteADB][MAIN][%s] Connected to ADB (mode: %s)", self._macAddr, mode_str)
            await self._notify_adb_status(True)

    async def _on_connection_error(self, e: BaseException) -> None:
        """Échec de connexion ou connexion perdue dans la boucle : statut envoyé à Jeedom, puis attente avant la tentative suivante"""
        await self._close_after_failure()
        # If pairing is in progress, don't process errors (pairing handles its own connection)
        if self._pairing_mode:
            self._logger.debug("[EQRemoteADB][MAIN][%s] Connection error during pairing mode (expected, ignored) :: %s", self._macAddr, e)
            return
        if isinstance(e, asyncio.TimeoutError):
            # TV joignable, autorisation ADB non validée à temps : à régler sur la TV, pas une panne
            self._logger.warning("[EQRemoteADB][MAIN][%s] Connection timeout after %ds", self._macAddr, self._config.adb_auth_timeout_connect + 5)
            return
        if isinstance(e, (OSError, ConnectionError, TcpTimeoutException)):
            # Network errors (device offline, unreachable, etc.) - use WARNING instead of ERROR
            # TcpTimeoutException : connexion TCP sans réponse dans le délai (TV éteinte qui ignore les paquets)
            self._logger.warning("[EQRemoteADB][MAIN][%s] Device unreachable :: %s", self._macAddr, e)
        else:
            self._logger.error("[EQRemoteADB][MAIN][%s] Connection error :: %s", self._macAddr, e)
        await self._notify_adb_status(False)
        # Apply backoff only when we will attempt reconnection
        if self._can_connect():
            self._logger.debug("[EQRemoteADB][MAIN][%s] Waiting %ds before reconnection attempt", self._macAddr, self._reconnect_delay)
            await asyncio.sleep(self._reconnect_delay)
            self._reconnect_delay = min(self._reconnect_delay * 2, self._config.reconnect_delay_max)

    async def _loop_iteration(self) -> None:
        """Un tour de boucle : connexion si nécessaire, déconnexion après inactivité, heartbeat"""
        # Skip connection if not paired or pairing in progress
        if self._adb_paired != 1 or self._pairing_mode:
            return

        if self._can_connect():
            await self._connect()

        # Heartbeat: Check connection health when connected
        if not self._connected or self._pairing_mode:
            return
        assert self._adb is not None  # Guaranteed: _connected implies _adb exists
        current_time = time.time()

        # Mode non-persistent : déconnecter après inactivité
        if not self._persistent_connection and current_time - self._last_activity >= self._idle_timeout_minutes * 60:
            self._logger.info("[EQRemoteADB][IDLE][%s] Disconnecting after %d minutes of inactivity", self._macAddr, self._idle_timeout_minutes)
            try:
                await self._adb.close()
                self._logger.info("[EQRemoteADB][IDLE][%s] ADB connection closed", self._macAddr)
            except Exception as e:
                self._logger.debug("[EQRemoteADB][IDLE][%s] Error closing ADB :: %s", self._macAddr, e)
            self._reset_state(clear_activity=True)  # Voluntary disconnect
            await self._notify_adb_status(False)
            return

        # Heartbeat check (in both modes to prevent TV from auto-closing the connection)
        # Does NOT update _last_activity, so idle timeout is still enforced in on-demand mode
        if current_time - self._last_heartbeat >= self._config.adb_heartbeat_interval:
            self._last_heartbeat = current_time
            try:
                # Send keepalive with no-op shell command
                await asyncio.wait_for(self._adb.shell(":", transport_timeout_s=5), timeout=5)
                mode_type = "permanent" if self._persistent_connection else "on-demand"
                self._logger.debug("[EQRemoteADB][HEARTBEAT][%s] Connection verified (mode: %s)", self._macAddr, mode_type)
            except (asyncio.TimeoutError, TcpTimeoutException, InvalidResponseError, OSError, ConnectionError, AttributeError) as e:
                self._logger.warning("[EQRemoteADB][HEARTBEAT][%s] Device disconnected :: %s", self._macAddr, e)
                await self._close_after_failure()  # Involuntary disconnect, preserve activity for reconnection
                await self._notify_adb_status(False)

    async def main(self) -> None:
        """
        The is the entry point of your class EQRemoteADB.
        You should start the asyncio task with this function like this: `asyncio.create_task(myEQRemoteADB.main())`
        """
        try:
            self._logger.info("[EQRemoteADB][MAIN][%s] Starting Main for Host :: %s", self._macAddr, self._host)

            # Small initial delay to let the network and device stabilize after daemon start
            await asyncio.sleep(self._config.adb_start_delay)

            # Keys are managed globally by TVRemoted (they must already exist). Clé et objet ADB déjà créés si une commande
            # est arrivée pendant la pause de démarrage : réutilisés (un second objet ferait perdre la connexion de la commande)
            if self._signer is None and not await self._load_signer():
                self._logger.error("[EQRemoteADB][MAIN][%s] Failed to load ADB signer", self._macAddr)
                return

            if self._adb is None:
                self._adb = AdbDeviceTcpAsync(self._host, self._port, default_transport_timeout_s=self._config.adb_timeout)

            # Send initial ADB status: not connected at startup (will connect on-demand or in persistent mode)
            # Don't send 'online' as we don't know TVRemote connection state here
            await self._notify_adb_status(False)
            self._logger.debug("[EQRemoteADB][MAIN][%s] Sending initial status: ADB not connected", self._macAddr)

            while not self._config.is_ending:
                try:
                    await self._loop_iteration()
                except (asyncio.TimeoutError, TcpTimeoutException, InvalidResponseError, DeviceAuthError, OSError, ConnectionError) as e:
                    # Handle connection errors gracefully (device offline, network issue, etc.)
                    await self._on_connection_error(e)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    # Erreur imprévue : journalisée, la boucle continue (elle ne s'arrête que sur annulation)
                    self._logger.error("[EQRemoteADB][MAIN][%s] Unexpected exception :: %s", self._macAddr, e)
                    self._logger.debug(traceback.format_exc())
                    await self._close_after_failure()
                    await asyncio.sleep(self._reconnect_delay)
                    self._reconnect_delay = min(self._reconnect_delay * 2, self._config.reconnect_delay_max)

                await asyncio.sleep(self._config.adb_loop_interval)

        except asyncio.CancelledError:
            self._logger.debug("[EQRemoteADB] Stop Main for device %s (%s)", self._macAddr, self._host)
            # Clean up connection task on cancellation
            if self._connection_task is not None:
                self._connection_task.cancel()
        except Exception as e:
            self._logger.error("[EQRemoteADB][MAIN] Unexpected exception :: %s", e)
            self._logger.debug(traceback.format_exc())
        finally:
            # Cleanup resources (connection state kept: remove() notifies Jeedom that ADB is disconnected)
            if self._connected and self._adb is not None:
                try:
                    await self._adb.close()
                    self._logger.debug("[EQRemoteADB][MAIN][%s] ADB connection closed", self._macAddr)
                except Exception as e:
                    self._logger.debug("[EQRemoteADB][MAIN][%s] Error during ADB close cleanup :: %s", self._macAddr, e)
            self._main_task = None
            self._logger.debug("[EQRemoteADB][MAIN][%s] Main loop stopped", self._macAddr)

    async def cancel_connection_attempt(self) -> None:
        """Cancel any ongoing connection attempt and close existing connection

        Can be called in different states:
        - Connected: will close connection and notify Jeedom
        - Connecting: will cancel task without notification (not yet connected)
        - Disconnected: no-op, just resets state
        """
        if self._is_connecting():
            assert self._connection_task is not None  # Guaranteed by _is_connecting()
            self._logger.debug("[EQRemoteADB][%s] Cancelling ongoing connection attempt", self._macAddr)
            task = self._connection_task
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise
                self._logger.debug("[EQRemoteADB][%s] Connection attempt cancelled successfully", self._macAddr)
            except Exception as e:
                self._logger.debug("[EQRemoteADB][%s] Error during connection cancellation :: %s", self._macAddr, e)

        # Also close any existing connection
        if self._connected:
            assert self._adb is not None  # Guaranteed: _connected implies _adb exists
            try:
                await self._adb.close()
                self._logger.debug("[EQRemoteADB][%s] Existing connection closed", self._macAddr)
            except Exception as e:
                self._logger.debug("[EQRemoteADB][%s] Error closing connection :: %s", self._macAddr, e)

        # Capture state before reset to know if we need to notify
        was_connected = self._connected

        # Reset all connection state consistently
        self._reset_state(clear_activity=True)  # Voluntary user action

        # Notify Jeedom only if we were connected (state changed)
        if was_connected:
            await self._notify_adb_status(False)

    def set_pairing_mode(self, pairing: bool) -> None:
        """Set pairing mode to prevent background connection attempts"""
        self._pairing_mode = pairing
        self._logger.debug("[EQRemoteADB][%s] Pairing mode set to %s", self._macAddr, pairing)

    async def remove(self) -> None:
        """Call it to disconnect from a EQRemoteADB"""
        self._logger.debug("[EQRemoteADB] Removing device %s (%s)", self._macAddr, self._host)
        try:
            # Cancel any ongoing connection and close existing one
            await self.cancel_connection_attempt()

            # Log removal at INFO level for coherence with connection log
            self._logger.info("[EQRemoteADB][MAIN][%s] Device removed (ADB disconnected)", self._macAddr)

            # Reset pairing mode and clear ADB reference
            self._pairing_mode = False
            self._adb = None
        except Exception as e:
            self._logger.error("[EQRemoteADB][REMOVE] Exception :: %s", e)
            self._logger.debug(traceback.format_exc())

    async def send_command(self, action: str | None = None, value: str | None = None, cmd_id: str | None = None) -> None:
        """Call it to send ADB command to EQRemoteADB"""
        try:
            # Don't send commands during pairing
            if self._pairing_mode:
                self._logger.debug("[EQRemoteADB][SendCommand] Pairing in progress, command ignored")
                if cmd_id:
                    error_data = {
                        'adb_shell_output_mac': self._macAddr,
                        'adb_shell_output_cmd_id': cmd_id,
                        'adb_shell_error': 'Pairing in progress'
                    }
                    await self._jeedom_publisher.send_to_jeedom(error_data)
                return
            
            # Update activity timestamp for on-demand mode
            # If connection or command fails, _reset_state() will reset this timestamp
            if not self._persistent_connection:
                self._last_activity = time.time()
            
            # Connect on-demand if not already connected (same connection path as the main loop: an attempt in progress is awaited, never doubled)
            if not self._persistent_connection and not self._connected:
                self._logger.debug("[EQRemoteADB][SendCommand] On-demand mode: connecting...")
                try:
                    await self._connect()
                except (asyncio.TimeoutError, TcpTimeoutException, InvalidResponseError, DeviceAuthError, OSError, ConnectionError) as e:
                    # TV éteinte ou injoignable : situation attendue, pas une panne (la commande suivante réessaiera)
                    self._logger.warning("[EQRemoteADB][SendCommand] Failed to connect :: %s", e)
                    if cmd_id:
                        error_data = {
                            'adb_shell_output_mac': self._macAddr,
                            'adb_shell_output_cmd_id': cmd_id,
                            'adb_shell_error': 'Failed to connect'
                        }
                        await self._jeedom_publisher.send_to_jeedom(error_data)
                    return
            
            if self._adb is None or not self._connected:
                self._logger.warning("[EQRemoteADB][SendCommand] ADB not connected")
                # Send error to Jeedom if cmd_id is provided
                if cmd_id:
                    error_data = {
                        'adb_shell_output_mac': self._macAddr,
                        'adb_shell_output_cmd_id': cmd_id,
                        'adb_shell_error': 'Device not connected (ADB)'
                    }
                    await self._jeedom_publisher.send_to_jeedom(error_data)
                return
            
            if action == 'shell':
                # Execute shell command with timeout
                if value is not None:
                    self._logger.debug("[EQRemoteADB][SendCmd - Shell] %s", value)
                    
                    try:
                        # Use configured ADB timeout for both asyncio and transport layer
                        result = await asyncio.wait_for(
                            self._adb.shell(value, transport_timeout_s=self._config.adb_timeout), 
                            timeout=self._config.adb_timeout
                        )
                        # Clean whitespace and newlines from shell output
                        result = result.strip()
                        
                        if len(result) > 500:
                            self._logger.debug("[EQRemoteADB][SendCmd - Shell Result] (%d chars) :: %s", len(result), result)
                        else:
                            self._logger.debug("[EQRemoteADB][SendCmd - Shell Result] %s", result)
                        # Envoyer le résultat à Jeedom avec cmd_id si fourni
                        data = {
                            'adb_shell_output_mac': self._macAddr,
                            'adb_shell_output_value': result
                        }
                        if cmd_id:
                            data['adb_shell_output_cmd_id'] = cmd_id
                            self._logger.debug("[EQRemoteADB][SendCmd - Shell] Sending result for cmd_id %s", cmd_id)
                        await self._jeedom_publisher.send_to_jeedom(data)
                    except (asyncio.TimeoutError, TcpTimeoutException) as e:
                        self._logger.warning("[EQRemoteADB][SendCmd - Shell] Timeout (%ds) waiting for command response :: %s", self._config.adb_timeout, str(e))
                        # Send error to Jeedom if cmd_id is provided
                        if cmd_id:
                            error_data = {
                                'adb_shell_output_mac': self._macAddr,
                                'adb_shell_output_cmd_id': cmd_id,
                                'adb_shell_error': 'Command timeout'
                            }
                            await self._jeedom_publisher.send_to_jeedom(error_data)
                    except (OSError, ConnectionError, InvalidResponseError) as e:
                        self._logger.warning("[EQRemoteADB][SendCmd - Shell] Connection lost during command execution :: %s", str(e))
                        # Close ADB connection properly and mark as disconnected
                        assert self._adb is not None  # Guaranteed: checked at entry of send_command
                        try:
                            await self._adb.close()
                        except Exception:
                            pass  # Ignore errors during cleanup
                        self._reset_state(clear_activity=False)  # Involuntary disconnect during command
                        # Notify Jeedom that ADB is now disconnected
                        await self._notify_adb_status(False)
                        # Send error to Jeedom if cmd_id is provided
                        if cmd_id:
                            error_data = {
                                'adb_shell_output_mac': self._macAddr,
                                'adb_shell_output_cmd_id': cmd_id,
                                'adb_shell_error': 'Connection lost'
                            }
                            await self._jeedom_publisher.send_to_jeedom(error_data)
            elif action == 'keycode':
                # Send keycode via ADB
                if value is not None:
                    self._logger.debug("[EQRemoteADB][SendCmd - Keycode] %s", value)
                    await self._adb.shell(f"input keyevent {value}")
            elif action == 'appcode':
                # Launch app via ADB
                if value is not None:
                    self._logger.debug("[EQRemoteADB][SendCmd - Launch App] %s", value)
                    await self._adb.shell(f"monkey -p {value} 1")
            elif action in ADB_POWER_COMMANDS:
                # La TV vérifie elle-même son écran au moment de la commande : aucun état mémorisé qui pourrait être périmé
                self._logger.debug("[EQRemoteADB][SendCommand] %s :: %s", action, ADB_POWER_COMMANDS[action])
                await self._adb.shell(ADB_POWER_COMMANDS[action])
            elif action in self._config.key_mapping:
                self._logger.debug("[EQRemoteADB][SendCommand] %s :: %s", action, self._config.key_mapping[action])
                keycode = self._config.key_mapping[action]
                if action in ('oqee', 'youtube', 'netflix', 'primevideo', 'disneyplus', 'mycanal', 'plex', 'appletv', 'orangetv', 'molotov'):
                    # Launch app
                    await self._adb.shell(f"monkey -p {keycode} 1")
                else:
                    # Send keycode
                    await self._adb.shell(f"input keyevent {keycode}")
            else:
                self._logger.error("[EQRemoteADB][SendCommand] Command Mapping :: %s :: Unknown Key !", action)
        except (TcpTimeoutException, InvalidResponseError, OSError, ConnectionError) as e:
            # Connexion perdue pendant la commande (TV éteinte entre-temps…) : situation attendue, pas une panne
            self._logger.warning("[EQRemoteADB][SendCommand] Connection error :: %s", e)
            # Close ADB connection properly before resetting state
            # At this point _adb is guaranteed non-null (checked at entry of send_command)
            assert self._adb is not None
            try:
                await self._adb.close()
            except Exception:
                pass  # Ignore errors during cleanup
            self._reset_state(clear_activity=False)  # Involuntary disconnect
            # Notify Jeedom that ADB is now disconnected
            await self._notify_adb_status(False)
            self._logger.debug(traceback.format_exc())
        except Exception as e:
            self._logger.error("[EQRemoteADB][SendCommand] Exception :: %s", e)
            self._logger.debug(traceback.format_exc())
            
class TVRemoted:
    """This is the main class of you daemon"""

    def __init__(self, config_: Config) -> None:
        # Standard initialisation
        self._config = config_
        self._listen_task = None
        self._send_task = None  # Not needed if you don't need to send change to Jeedom in cycle
        self._jeedom_publisher = None
        self._logger = logging.getLogger(__name__)

        # Below you can init your own variables if needed
        self._main_task = None
        # Ajouts et retraits d'appareils un par un : chaque message du socket est traité dans sa propre tâche, et un ajout
        # qui recrée un appareil attend l'arrêt de l'ancien (un second ajout pendant cette attente créerait un doublon)
        self._devices_lock = asyncio.Lock()
        # self._tvhosts_task = None
        # self._search_task = None

    async def main(self) -> None:
        """
        The is the entry point of your daemon.
        You should start the asyncio loop with this function like this: `asyncio.run(daemon.main())`
        """
        self._jeedom_publisher = Publisher(self._config.callback_url, self._config.api_key, self._config.cycle_factor * self._config.cycle_comm)
        if not await self._jeedom_publisher.test_callback():
            self._logger.info("[CALLBACK] Test :: KO")
            return
        else:
            self._logger.info("[CALLBACK] Test :: OK")

        # _listen_task & _send_task are 2 background tasks handling communication with the daemon
        self._listen_task = Listener.create_listen_task(self._config.socket_host, self._config.socket_port, self._on_socket_message)
        self._send_task = self._jeedom_publisher.create_send_task()  # Not needed if you don't need to send change to Jeedom in cycle but only immediately

        # create your own background tasks here.
        # self._search_task = asyncio.create_task(self._search_animals())
        self._main_task = asyncio.create_task(self._mainLoop(self._config.cycle_main))
        # self._tvhosts_task = asyncio.create_task(self._tvhosts_from_zeroconf(timeout=60))
        
        # register signal handler
        await self.__add_signal_handler()
        await asyncio.sleep(1)  # allow all tasks to start

        self._logger.info("[MAIN] Ready")
        
        # Informer Jeedom que le démon est démarré
        await self._jeedom_publisher.send_to_jeedom({'daemonStarted': 1})
        self._logger.info("[MAINLOOP] DaemonStarted Info :: OK")
        
        # ensure that the loop continues to run until all tasks are completed or canceled, you must list here all tasks previously created
        self._config.tasks = [self._listen_task, self._send_task, self._main_task]
        await asyncio.gather(*self._config.tasks)
        
    async def __add_signal_handler(self) -> None:
        """
        This function register signal handler to interrupt the loop in case of process kill is received from Jeedom. You don't need to change anything here
        """
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, lambda: self._ask_exit(signal.SIGINT))
        loop.add_signal_handler(signal.SIGTERM, lambda: self._ask_exit(signal.SIGTERM))

    async def _on_socket_message(self, message: dict) -> None:
        """
        This function will be called by the "listen task" once a message is received from Jeedom.
        You must implement the different actions that your daemon can handle.
        """
        if message['apikey'] != self._config.api_key:
            self._logger.error('[MAIN][SOCKET] Invalid apikey from socket : %s', message)
            return
        try:
            if message['cmd'] == "action":
                # Gestion des actions
                self._logger.debug('[DAEMON][SOCKET] Action')
                if 'cmd_action' in message:
                    # Traitement des actions (inclus les CustomCmd)
                    if (message['cmd_action'] in ('volumeup', 'volumedown', 'up', 'down', 'left', 'right', 'center', 'mute_on', 'mute_off', 'power_on', 'power_off', 'back', 'home', 'menu', 'tv', 'channel_up', 'channel_down', 'info', 'settings', 'input', 'hdmi_1', 'hdmi_2', 'hdmi_3', 'hdmi_4', 'oqee', 'youtube', 'netflix', 'primevideo', 'disneyplus', 'mycanal', 'plex', 'appletv', 'orangetv', 'molotov', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'zero', 'keycode', 'appcode', 'shell', 'media_next', 'media_stop', 'media_pause', 'media_play', 'media_rewind', 'media_previous', 'media_forward') and 'mac' in message):
                        self._logger.debug('[DAEMON][SOCKET] Action :: %s @ %s (%s)', message['cmd_action'], message['mac'], message['value'])
                        
                        # Parse options field if present (format: "key1":"value1","key2":"value2")
                        protocol = None
                        if 'options' in message and message['options'] is not None:
                            try:
                                options_json = json.loads("{" + message['options'] + "}")
                                protocol = options_json.get('protocol', None)
                                cmd_id = options_json.get('cmd_id', None)
                                if protocol:
                                    protocol = protocol.lower()
                                self._logger.debug('[DAEMON][SOCKET] Options parsed :: %s', str(options_json))
                            except (ValueError, json.JSONDecodeError) as e:
                                self._logger.warning('[DAEMON][SOCKET] Options mal formatées (Json KO) :: %s', e)

                        # Power On/Off, Mute On/Off : rien n'est envoyé si la TV est déjà dans l'état demandé (la touche bascule)
                        if self._already_in_requested_state(message['mac'], message['cmd_action']):
                            return

                        # Check if protocol is explicitly specified via options
                        if protocol:
                            if protocol == 'adb':
                                device = self._config.remote_devices_adb.get(message['mac'])
                                if device:
                                    await device.send_command(message['cmd_action'], message['value'], cmd_id)
                                else:
                                    self._logger.warning('[DAEMON][SOCKET] ADB device not found :: %s', message['mac'])
                            elif protocol == 'tvremote':
                                device = self._config.remote_devices.get(message['mac'])
                                if device:
                                    await device.send_command(message['cmd_action'], message['value'])
                                else:
                                    self._logger.warning('[DAEMON][SOCKET] TVRemote device not found :: %s', message['mac'])
                            else:
                                self._logger.error('[DAEMON][SOCKET] Unknown protocol :: %s', protocol)
                        else:
                            # Protocol not specified, use default logic (priority to AndroidTVRemote2)
                            device = self._config.remote_devices.get(message['mac'])
                            if device:
                                await device.send_command(message['cmd_action'], message['value'])
                            else:
                                device_adb = self._config.remote_devices_adb.get(message['mac'])
                                if device_adb:
                                    await device_adb.send_command(message['cmd_action'], message['value'])
                                else:
                                    self._logger.warning('[DAEMON][SOCKET] Device not found :: %s', message['mac'])
                    else:
                        self._logger.warning('[DAEMON][SOCKET] Unknown Action :: %s', message['cmd_action'])
            elif message['cmd'] == "scanOn":
                self._logger.info('[DAEMON][SOCKET] ScanState = scanOn') 
                self._config.scanmode = True
                self._config.scanmode_start = int(time.time())
                if self._jeedom_publisher is not None:
                    await self._jeedom_publisher.send_to_jeedom({'scanState': 'scanOn'})
            elif message['cmd'] == "scanOff":
                self._logger.info('[DAEMON][SOCKET] ScanState = scanOff')
                self._config.scanmode = False
                if self._jeedom_publisher is not None:
                    await self._jeedom_publisher.send_to_jeedom({'scanState': 'scanOff'})
            elif message['cmd'] == "sendBeginPairing":
                self._logger.info('[DAEMON][SOCKET] Begin Pairing for (Mac :: %s) :: %s:%s', message['mac'], message['host'], message['port'])
                await self._pairing(message['mac'], message['host'], message['port'])
            elif message['cmd'] == "sendBeginPairingAdb":
                self._logger.info('[DAEMON][SOCKET] Begin ADB Pairing for (Mac :: %s) :: %s', message['mac'], message['host'])
                await self._pairing_adb(message['mac'], message['host'])
            elif message['cmd'] == "sendPairCode":
                self._logger.debug('[DAEMON][SOCKET] Received Pairing Code (Mac :: %s) :: %s', message['mac'], message['paircode'])
                self._config.pairing_code = message['paircode']
            elif message['cmd'] == "addtvremote":
                if all(keys in message for keys in ('mac', 'host', 'port', 'friendly_name')):
                    self._logger.info('[DAEMON][SOCKET] Add TVRemote Device (Mac :: %s) :: %s:%s', message['mac'], message['host'], message['port'])
                    async with self._devices_lock:
                        await self._add_remote(message)
            elif message['cmd'] == "removetvremote":
                if 'mac' in message:
                    self._logger.info('[DAEMON][SOCKET] Remove TVRemote (Mac :: %s) :: %s:%s', message['mac'], message.get('host'), message.get('port'))
                    async with self._devices_lock:
                        await self._remove_remote(message['mac'])
            elif message['cmd'] == "addtvremote_adb":
                if all(keys in message for keys in ('mac', 'host', 'friendly_name')):
                    self._logger.info('[DAEMON][SOCKET] Add ADB Device (Mac :: %s) :: %s', message['mac'], message['host'])
                    async with self._devices_lock:
                        await self._add_remote_adb(message)
            elif message['cmd'] == "removetvremote_adb":
                if 'mac' in message:
                    self._logger.info('[DAEMON][SOCKET] Remove ADB Device (Mac :: %s) :: %s', message['mac'], message.get('host'))
                    async with self._devices_lock:
                        await self._remove_remote_adb(message['mac'])
            else:
                self._logger.warning('[DAEMON][SOCKET] Unknown Cmd :: %s', message['cmd'])
                
        except Exception as message_e:
            self._logger.error('[MAIN][SOCKET] Exception :: %s', message_e)
            self._logger.debug(traceback.format_exc())

    def _already_in_requested_state(self, mac: str, action: str) -> bool:
        """État connu par la connexion Google TV de l'appareil, quel que soit le protocole utilisé pour la commande"""
        device = self._config.remote_devices.get(mac)
        if device is None or not device.is_already(action):
            return False
        self._logger.info('[DAEMON][SOCKET] Action %s ignored (Mac :: %s) :: TV already in the requested state', action, mac)
        return True

    async def _stop_device_task(self, device) -> None:
        """Arrête la boucle d'un appareil et attend sa fin (fermeture de la connexion comprise)"""
        task = device._main_task
        if task is not None and not task.done():
            task.cancel()
            try:
                # shield : une annulation de la tâche en cours (arrêt du démon) ne doit pas atteindre la boucle de l'appareil,
                # qui la rattraperait en s'arrêtant normalement (annulation perdue) ; elle remonte ici, l'appareil finit de s'arrêter
                await asyncio.shield(task)
            except asyncio.CancelledError:
                # Annulation de la boucle de l'appareil : attendue. Celle de la tâche en cours doit continuer
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise

    def _int_option(self, message: dict, key: str, default: int) -> int:
        """Valeur entière d'un réglage envoyé par Jeedom ; absente ou illisible (champ vidé…) : valeur par défaut, l'appareil est quand même ajouté"""
        value = message.get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            self._logger.warning('[DAEMON][SOCKET] Invalid value for %s (Mac :: %s) :: %r, using %s', key, message.get('mac'), value, default)
            return default

    async def _add_remote(self, message: dict) -> None:
        """Ajoute l'appareil Google TV, ou le recrée si son IP ou son option IME a changé, ou si sa boucle s'est arrêtée
        (sinon rien ne change : les enregistrements fréquents de l'équipement ne coupent pas la connexion)"""
        mac = message['mac']
        enable_ime = self._int_option(message, 'enable_ime', 1) != 0
        device = self._config.remote_devices.get(mac)
        if device is not None:
            if not device.is_running:
                self._logger.info('[DAEMON][SOCKET] TVRemote %s was stopped :: restarting device', mac)
            elif device.host == message['host'] and device.enable_ime == enable_ime:
                self._logger.debug('[DAEMON][SOCKET] TVRemote device %s already exists (unchanged)', mac)
                return
            else:
                self._logger.info('[DAEMON][SOCKET] TVRemote %s changed (host %s -> %s, IME %s -> %s) :: restarting device', mac, device.host, message['host'], device.enable_ime, enable_ime)
            await self._remove_remote(mac)
        self._logger.debug('[DAEMON][SOCKET] TVRemote %s (%s) :: IME (virtual keyboard) %s', message['friendly_name'], mac, 'enabled' if enable_ime else 'disabled')
        self._create_remote(mac, message['host'], enable_ime)

    def _create_remote(self, mac: str, host: str, enable_ime: bool) -> None:
        device = EQRemote(mac, host, self._config, self._jeedom_publisher, enable_ime)
        self._config.remote_devices[mac] = device
        device._main_task = asyncio.create_task(device.main())
        self._logger.debug('[DAEMON][SOCKET] Main loop task created for TVRemote %s | TVRemote devices (%d)', mac, len(self._config.remote_devices))

    async def _restart_remote(self, mac: str) -> None:
        """Recrée l'appareil avec les mêmes réglages : nouvelle connexion immédiate, certificat relu
        (la bibliothèque garde en mémoire celui chargé à la première connexion)"""
        device = self._config.remote_devices.get(mac)
        if device is None:
            return
        await self._remove_remote(mac)
        self._create_remote(mac, device.host, device.enable_ime)

    async def _remove_remote(self, mac: str) -> None:
        device = self._config.remote_devices.pop(mac, None)
        if device is None:
            return
        await self._stop_device_task(device)
        await device.remove()
        self._logger.debug('[DAEMON][SOCKET] TVRemote %s removed | TVRemote devices (%d)', mac, len(self._config.remote_devices))

    async def _add_remote_adb(self, message: dict) -> None:
        """Ajoute l'appareil ADB, ou le recrée si son IP a changé ; sinon met à jour l'appairage et le mode de connexion sans couper la connexion"""
        mac = message['mac']
        paired = self._int_option(message, 'adb_paired', 0)
        persistent = self._int_option(message, 'adb_persistent_connection', 0) != 0
        idle_timeout = self._int_option(message, 'adb_idle_timeout', self._config.adb_idle_timeout_default)
        if idle_timeout < 1:
            self._logger.warning('[DAEMON][SOCKET] Invalid value for adb_idle_timeout (Mac :: %s) :: %s, using %s', mac, idle_timeout, self._config.adb_idle_timeout_default)
            idle_timeout = self._config.adb_idle_timeout_default
        device = self._config.remote_devices_adb.get(mac)
        if device is not None and (device.host != message['host'] or not device.is_running):
            if device.is_running:
                self._logger.info('[DAEMON][SOCKET] ADB %s changed (host %s -> %s) :: restarting device', mac, device.host, message['host'])
            else:
                self._logger.info('[DAEMON][SOCKET] ADB %s was stopped :: restarting device', mac)
            await self._remove_remote_adb(mac)
            device = None
        if device is not None:
            device._adb_paired = paired
            device._persistent_connection = persistent
            device._idle_timeout_minutes = idle_timeout
            # In on-demand mode with active connection, reset activity timestamp to avoid immediate disconnect
            if not device._persistent_connection and device._connected:
                device._last_activity = time.time()
            self._logger.debug('[DAEMON][SOCKET] Device %s already exists, updated paired=%s, persistent=%s', mac, device._adb_paired, device._persistent_connection)
            return
        # Ensure ADB keys exist before adding device
        await self.ensure_adb_keys(notify_jeedom=False)
        self._create_remote_adb(mac, message['host'], paired, persistent, idle_timeout)

    def _create_remote_adb(self, mac: str, host: str, paired: int, persistent: bool, idle_timeout: int) -> None:
        device = EQRemoteADB(mac, host, self._config, self._jeedom_publisher)
        device._adb_paired = paired
        device._persistent_connection = persistent
        device._idle_timeout_minutes = idle_timeout
        self._config.remote_devices_adb[mac] = device
        self._logger.debug('[DAEMON][SOCKET] Persistent connection: %s, Idle timeout: %d min', device._persistent_connection, device._idle_timeout_minutes)
        # Always start main loop as async task (it will handle pairing logic internally)
        device._main_task = asyncio.create_task(device.main())
        self._logger.debug('[DAEMON][SOCKET] Main loop task created for %s (paired=%s) | ADB devices (%d)', mac, device._adb_paired, len(self._config.remote_devices_adb))

    async def _restart_remote_adb(self, mac: str, paired: int) -> None:
        """Recrée l'appareil ADB avec les mêmes réglages : la clé est relue (elle a pu être régénérée pour l'appairage)"""
        device = self._config.remote_devices_adb.get(mac)
        if device is None:
            return
        host, persistent, idle_timeout = device.host, device._persistent_connection, device._idle_timeout_minutes
        await self._remove_remote_adb(mac)
        self._create_remote_adb(mac, host, paired, persistent, idle_timeout)

    async def _remove_remote_adb(self, mac: str) -> None:
        device = self._config.remote_devices_adb.pop(mac, None)
        if device is None:
            return
        await self._stop_device_task(device)
        await device.remove()
        self._logger.debug('[DAEMON][SOCKET] ADB %s removed | ADB devices (%d)', mac, len(self._config.remote_devices_adb))

    async def _pairing(self, _mac=None, _host=None, _port=None) -> None:
        """ Function to pair Plugin with TV """
        
        if self._config.scanmode:
            self._logger.error("[PAIRING] TV ScanMode in Progress. Stop Scan before trying to Pair.")
            return
        
        if _host is None:
            self._logger.error("[PAIRING] Host is None")
            return
        
        self._config.pairing_code = None
        remote = AndroidTVRemote(self._config.client_name, self._config.cert_file, self._config.key_file, _host)
        if remote is None:
            self._logger.error("[PAIRING][%s] TVRemote Object is None !", _mac)
            return
        
        if await remote.async_generate_cert_if_missing():
            self._logger.info("[PAIRING][%s] Generated New Cert/Key Files :: %s | %s", _mac, self._config.cert_file, self._config.key_file)
        
        pairing_starttime = int(time.time())
        currentTime = int(time.time())
        
        try:
            try:
                self._logger.info("[PAIRING][START][%s] Start Pairing...", _mac)
                await remote.async_start_pairing()
            except CannotConnect as e:
                self._logger.warning("[PAIRING][START][%s] Cannot connect (device may be offline) :: %s", _mac, e)
                return
            except ConnectionClosed as e:
                self._logger.error("[PAIRING][START][%s] Connection closed :: %s", _mac, e)
                return
            
            while not self._config.is_ending and (pairing_starttime + self._config.pairing_timeout) > currentTime :
                while not self._config.is_ending and self._config.pairing_code is None :
                    await asyncio.sleep(1)
                    currentTime = int(time.time())
                    if (pairing_starttime + self._config.pairing_timeout) <= currentTime:
                        self._logger.error("[PAIRING][%s] Pairing Code not received in the last 5min :: KO", _mac)
                        remote = None
                        return
                try:
                    self._logger.debug("[PAIRING][%s] Trying to Pair with Code :: %s", _mac, str(self._config.pairing_code))
                    if self._config.pairing_code is not None:
                        # Ne renvoie rien : sans exception (InvalidAuth, ConnectionClosed), l'appairage a réussi
                        await remote.async_finish_pairing(self._config.pairing_code)
                        self._logger.info("[PAIRING][%s] Pairing successful", _mac)
                        # Appareil recréé : connexion immédiate (sans attendre son délai de reconnexion), avec le certificat
                        # utilisé pour l'appairage (régénéré si les fichiers avaient été supprimés)
                        async with self._devices_lock:
                            await self._restart_remote(_mac)
                        # Inform Jeedom about successful pairing
                        if self._jeedom_publisher is not None:
                            data = {
                                'mac': _mac,
                                'tvremote_paired': 1,
                                'message': 'TVRemote pairing successful'
                            }
                            await self._jeedom_publisher.send_to_jeedom(data)
                        return
                except InvalidAuth as exc:
                    self._logger.error("[PAIRING][%s] Invalid Pairing Code. Try to send another one. Error :: %s", _mac, exc)
                    # TODO : Informer le Plugin du mauvais code de Pairing
                    self._config.pairing_code = None
                    await asyncio.sleep(1)
                    continue
                except ConnectionClosed as exc:
                    self._logger.error("[PAIRING][%s] Initialize Pairing Again. Error :: %s", _mac, exc)
                    await asyncio.sleep(1)
                    return await self._pairing(_mac, _host, _port)
        except Exception as e:
            self._logger.error("[PAIRING][%s] Exception :: %s", _mac, e)
            self._logger.debug(traceback.format_exc())
            
        self._logger.debug("[PAIRING][%s] End Function...", _mac)
        # Libération de la mémoire
        remote = None

    async def ensure_adb_keys(self, notify_jeedom: bool = True) -> bool:
        """Ensure ADB keys exist, generate them if missing (shared method for all devices)
        
        Args:
            notify_jeedom: Whether to send notification to Jeedom
            
        Returns:
            True if keys were generated, False if they already existed
        """
        try:
            if not os.path.exists(self._config.adb_key_file):
                self._logger.info("[ADB] Generating ADB keys...")
                keygen(self._config.adb_key_file)
                self._logger.info("[ADB] ADB keys generated :: %s", self._config.adb_key_file)
                
                # Inform Jeedom that keys were generated
                if notify_jeedom and self._jeedom_publisher is not None:
                    data = {
                        'adb_keys_generated': 1,
                        'adb_key_file': self._config.adb_key_file,
                        'adb_pub_file': self._config.adb_pub_file
                    }
                    await self._jeedom_publisher.send_to_jeedom(data)
                return True
            else:
                self._logger.debug("[ADB] ADB keys already exist :: %s", self._config.adb_key_file)
                # Inform Jeedom only if explicitly requested
                if notify_jeedom and self._jeedom_publisher is not None:
                    data = {
                        'adb_keys_exist': 1,
                        'adb_key_file': self._config.adb_key_file,
                        'adb_pub_file': self._config.adb_pub_file
                    }
                    await self._jeedom_publisher.send_to_jeedom(data)
                return False
        except Exception as e:
            self._logger.error("[ADB] Error generating ADB keys :: %s", e)
            self._logger.debug(traceback.format_exc())
            if notify_jeedom and self._jeedom_publisher is not None:
                await self._jeedom_publisher.send_to_jeedom({'adb_keys_error': str(e)})
            return False

    async def _send_adb_pairing_result(self, data: dict) -> None:
        """Résultat de l'appairage ADB vers Jeedom ; un échec d'envoi est journalisé, sans interrompre l'appairage"""
        if self._jeedom_publisher is None:
            return
        try:
            await self._jeedom_publisher.send_to_jeedom(data)
        except Exception as e:
            self._logger.warning("[PAIRING_ADB][%s] Cannot send the pairing result to Jeedom :: %s", data.get('mac'), e)

    async def _send_adb_pairing_failed(self, mac, message: str) -> None:
        """Échec sans conclusion sur l'appairage (TV injoignable, appairage déjà en cours…) : affiché à l'utilisateur, statut d'appairage inchangé"""
        await self._send_adb_pairing_result({'mac': mac, 'adb_pairing_failed': 1, 'message': message})

    async def _pairing_adb(self, _mac=None, _host=None) -> None:
        """Function to pair with TV using ADB.
        Le statut d'appairage envoyé à Jeedom (adb_paired) ne change que sur un résultat certain : succès (1) ou refus sur la TV (0)"""

        if self._config.scanmode:
            self._logger.error("[PAIRING_ADB] TV ScanMode in Progress. Stop Scan before trying to Pair.")
            return

        if _host is None:
            self._logger.error("[PAIRING_ADB] Host is None")
            return

        # Check if pairing is already in progress for this device
        device = self._config.remote_devices_adb.get(_mac)
        if device is not None and device._pairing_mode:
            self._logger.warning("[PAIRING_ADB][%s] Pairing already in progress, ignoring new request", _mac)
            await self._send_adb_pairing_failed(_mac, 'Pairing already in progress')
            return

        adb = None
        try:
            # Ensure keys exist (shared across all devices)
            await self.ensure_adb_keys(notify_jeedom=False)
            signer = load_adb_signer(self._config)
            adb = AdbDeviceTcpAsync(_host, 5555, default_transport_timeout_s=self._config.adb_timeout)

            self._logger.debug("[PAIRING_ADB][START][%s] Start ADB Pairing...", _mac)

            # If device already exists, cancel any ongoing connection and enable pairing mode
            if device is not None:
                self._logger.debug("[PAIRING_ADB][%s] Cancelling background connections and enabling pairing mode", _mac)
                device.set_pairing_mode(True)
                await device.cancel_connection_attempt()

            # Longer authentication timeout for manual pairing, to give the user time to accept on the TV
            await adb.connect(
                rsa_keys=[signer],
                transport_timeout_s=self._config.adb_timeout,  # Explicit TCP connection timeout
                auth_timeout_s=self._config.adb_auth_timeout_pairing
            )
            self._logger.info("[PAIRING_ADB][%s] ADB connection successful", _mac)
            try:
                await adb.close()
            except Exception as close_error:
                self._logger.debug("[PAIRING_ADB][%s] Error closing connection (ignored) :: %s", _mac, close_error)

            # Appareil recréé : il relit la clé (régénérée si elle avait été supprimée) et se connecte avec l'appairage à jour
            async with self._devices_lock:
                await self._restart_remote_adb(_mac, paired=1)
            if _mac in self._config.remote_devices_adb:
                self._logger.info("[PAIRING_ADB][%s] Device paired, restarted to connect now", _mac)
            await self._send_adb_pairing_result({'mac': _mac, 'adb_paired': 1, 'message': 'ADB pairing successful'})

        except DeviceAuthError as e:
            # Refus sur la TV (ou demande non acceptée à temps) : la clé n'est pas autorisée, résultat certain
            self._logger.warning("[PAIRING_ADB][%s] Device not authorized. Please check TV screen for authorization prompt :: %s", _mac, e)
            await self._send_adb_pairing_result({'mac': _mac, 'adb_paired': 0, 'message': 'Device not authorized. Please check TV screen for authorization prompt.'})
        except (TcpTimeoutException, InvalidResponseError, OSError, ConnectionError) as e:
            # Distinguer les erreurs de connexion normales (device offline, délai TCP dépassé) des erreurs critiques
            if isinstance(e, (OSError, ConnectionError, TcpTimeoutException)):
                self._logger.warning("[PAIRING_ADB][%s] Cannot connect (device may be offline) :: %s", _mac, e)
            else:
                self._logger.error("[PAIRING_ADB][%s] Connection error :: %s", _mac, e)
            await self._send_adb_pairing_failed(_mac, f'Connection error: {str(e)}')
        except Exception as e:
            self._logger.error("[PAIRING_ADB][%s] Exception :: %s", _mac, e)
            self._logger.debug(traceback.format_exc())
            await self._send_adb_pairing_failed(_mac, f'Error: {str(e)}')
        finally:
            if adb is not None:
                try:
                    await adb.close()
                except Exception:
                    pass  # Ignore errors during cleanup
            # Fin du mode appairage (appareil inchangé ; un appareil recréé démarre sans)
            device = self._config.remote_devices_adb.get(_mac)
            if device is not None and device._pairing_mode:
                device.set_pairing_mode(False)

    async def _tvhosts_from_zeroconf(self, timeout: float = 30.0) -> None:
        """ Function to detect TV hosts from ZeroConf Instance """
        
        def _async_on_service_state_change(zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
            if state_change is not ServiceStateChange.Added:
                return
            _ = asyncio.ensure_future(async_get_service_info(zeroconf, service_type, name))

        async def async_get_service_info(zeroconf: Zeroconf, service_type: str, name: str) -> None:
            info = AsyncServiceInfo(service_type, name)
            await info.async_request(zeroconf, 3000)
            if info:
                currentTime = int(time.time())
                currentTimeStr = EQRemote._format_timestamp(currentTime)
                
                _friendly_name = info.get_name()
                _type = info.type
                
                self._logger.info("[TVHOSTS][%s] Name :: %s", _friendly_name, name)
                self._logger.info("[TVHOSTS][%s] Type :: %s", _friendly_name, _type)
                
                _ip_addr_v4 = "0.0.0.0"
                _port = info.port
                for addr in info.parsed_scoped_addresses():
                    if (await self._is_ipv4(addr)):
                        _ip_addr_v4 = addr
                        self._logger.info("[TVHOSTS][%s] Addr:Port (IPv4) :: %s:%s", _friendly_name, addr, str(_port))
                        break
                    # else:
                        # self._logger.info("[TVHOSTS][%s] Addr (IPv6) :: %s (port=%s)", name, addr, str(info.port))
                
                if info.decoded_properties:
                    for key, value in info.decoded_properties.items():
                        self._logger.info("[TVHOSTS][%s] Properties :: %s = %s", _friendly_name, key, value)
                else:
                    self._logger.warning("[TVHOSTS][%s] Properties :: NONE", _friendly_name)
                
                # Connect to Remote and get name and mac address
                remote = AndroidTVRemote(self._config.client_name, self._config.cert_file, self._config.key_file, _ip_addr_v4)
                if await remote.async_generate_cert_if_missing():
                    self._logger.info("[TVHOSTS][%s] Generated New Cert/Key Files :: %s | %s", _friendly_name, self._config.cert_file, self._config.key_file)
                
                remote_name, remote_mac = await remote.async_get_name_and_mac()
                
                self._logger.info("[TVHOSTS][%s] Name:Mac :: %s | %s", _friendly_name, remote_name, remote_mac)
                
                data = {
                    'name': name,
                    'family': remote_name,
                    'mac': remote_mac,
                    'friendly_name': _friendly_name,
                    'lastscan': currentTimeStr,
                    'type': _type,
                    'host': _ip_addr_v4,
                    'port': info.port,
                    'scanmode': 1
                }
                # Envoi vers Jeedom
                if self._jeedom_publisher is not None:
                    await self._jeedom_publisher.add_change('devices::' + data['name'], data)
                
                # Libération de la mémoire
                remote = None
                remote_name = None
                remote_mac = None
                
            else:
                self._logger.warning("[TVHOSTS][%s] Info :: NO", name)

        zc = AsyncZeroconf()
        services = ["_androidtvremote2._tcp.local."]
        self._logger.info("[TVHOSTS] TV Browser (for %s seconds) :: START", timeout)
        browser = AsyncServiceBrowser(zc.zeroconf, services, handlers=[_async_on_service_state_change])
        t = 0
        while not self._config.is_ending and (t < timeout) and self._config.scanmode:
            t += 0.5
            await asyncio.sleep(0.5)

        await browser.async_cancel()
        await zc.async_close()
        self._logger.info("[TVHOSTS] TV Browser :: STOP")

    async def _mainLoop(self, cycle: float = 2.0) -> None:
        # Main Loop for Daemon
        self._logger.debug("[MAINLOOP] Start MainLoop")
        try:
            while not self._config.is_ending:
                try:
                    # *** Actions de la MainLoop ***
                    currentTime = int(time.time())
                    
                    # Arrêt du ScanMode au bout de 60 secondes
                    if (self._config.scanmode and (self._config.scanmode_start + self._config.scanmode_timeout) <= currentTime):
                        self._config.scanmode = False
                        self._logger.info('[MAINLOOP] ScanMode :: END')
                        if self._jeedom_publisher is not None:
                            await self._jeedom_publisher.send_to_jeedom({'scanState': 'scanOff'})                    
                    # Heartbeat du démon
                    if ((self._config.heartbeat_lasttime + self._config.heartbeat_frequency) <= currentTime):
                        self._logger.info('[MAINLOOP] Heartbeat = 1')
                        if self._jeedom_publisher is not None:
                            await self._jeedom_publisher.send_to_jeedom({'heartbeat': 1})
                        self._config.heartbeat_lasttime = currentTime
                        await self._getResourcesUsage()
                    # Scan New TVRemote
                    if not self._config.scan_pending:
                        if self._config.scanmode and (self._config.scan_lasttime < self._config.scanmode_start):
                            self._logger.debug('[SCANNER] Scan TVRemote :: ScanMode')
                            await self._tvhosts_from_zeroconf(timeout=60)
                        elif (self._config.scan_lasttime + self._config.scan_schedule <= currentTime):
                            # self._logger.debug('[SCANNER] Scan TVRemote :: ScheduleMode')
                            # Scan Schedule
                            self._config.scan_pending = True
                            self._config.scan_lasttime = int(time.time())
                            # TODO Ajouter la fonction Scan Schedule
                            self._config.scan_pending = False
                    else:
                        self._logger.debug('[MAINLOOP] ScanMode : SCAN PENDING !')                        
                        
                except Exception as e:
                    self._logger.error("[MAINLOOP] Exception :: %s", e)
                    self._logger.debug(traceback.format_exc())
                
                # Pause Cycle
                await asyncio.sleep(cycle)
                
        except asyncio.CancelledError:
            self._logger.warning("[MAINLOOP] Stop MainLoop")
        except Exception as e:
            self._logger.error("[MAINLOOP] Exception :: %s", e)
            self._logger.debug(traceback.format_exc())
            
    async def _getResourcesUsage(self) -> None:
        if not HAS_RESOURCE:
            return
        if (self._logger.isEnabledFor(logging.INFO)):
            resourcesUse = resource.getrusage(resource.RUSAGE_SELF)  # type: ignore[attr-defined]
            try:
                uTime = getattr(resourcesUse, 'ru_utime')
                sTime = getattr(resourcesUse, 'ru_stime')
                maxRSS = getattr(resourcesUse, 'ru_maxrss')
                totalTime = uTime + sTime
                currentTime = int(time.time())
                timeDiff = currentTime - self._config.resources_lasttime
                timeDiffTotal = currentTime - self._config.resources_firsttime
                self._logger.info('[RESOURCES] Total CPU Time used : %.3fs (%.2f%%) | Last %i sec : %.3fs (%.2f%%) | Memory : %s Mo', totalTime, totalTime / timeDiffTotal * 100, timeDiff, totalTime - self._config.resources_lastused, (totalTime - self._config.resources_lastused) / timeDiff * 100, int(round(maxRSS / 1024)))
                self._config.resources_lastused = totalTime
                self._config.resources_lasttime = currentTime
            except Exception:
                pass
    
    async def _is_ipv4(self, ip: str) -> bool:
        try:
            ipaddress.IPv4Address(ip)
            return True
        except ValueError:
            return False
            
    def _ask_exit(self, sig: int) -> None:
        """
        This function will be called in case a signal is received, see `__add_signal_handler`. You don't need to change anything here
        """
        self._logger.info("[ASKEXIT] Signal %i caught, exiting...", sig)
        self.close()

    def close(self) -> None:
        """
        This function can be called from outside to stop the daemon if needed`
        You need to close your remote connexions and cancel background tasks if any here.
        """
        self._logger.info('[CLOSE] Cancelling all tasks')
        
        # Collect all tasks to cancel
        tasks_to_cancel = []
        
        # Cancel all device main loop tasks
        for mac, device in self._config.remote_devices.items():
            if device._main_task is not None and not device._main_task.done():
                self._logger.debug('[CLOSE] Cancelling main loop task for TVRemote device %s', mac)
                device._main_task.cancel()
                tasks_to_cancel.append(device._main_task)
        
        for mac, device in self._config.remote_devices_adb.items():
            if device._main_task is not None and not device._main_task.done():
                self._logger.debug('[CLOSE] Cancelling main loop task for ADB device %s', mac)
                device._main_task.cancel()
                tasks_to_cancel.append(device._main_task)
        
        # Cancel daemon tasks
        if self._main_task is not None and not self._main_task.done():
            self._main_task.cancel()
            tasks_to_cancel.append(self._main_task)
        if self._listen_task is not None and not self._listen_task.done():
            self._listen_task.cancel()
            tasks_to_cancel.append(self._listen_task)
        if self._send_task is not None and not self._send_task.done():
            self._send_task.cancel()
            tasks_to_cancel.append(self._send_task)
        
        # Wait for all cancelled tasks to complete to avoid warnings
        if tasks_to_cancel:
            self._logger.debug('[CLOSE] Waiting for %d tasks to finish cancellation', len(tasks_to_cancel))
            # Note: This is a sync method but called from signal handler
            # Tasks will complete their cancellation in the event loop

# ----------------------------------------------------------------------------

class PatternRemapFilter(logging.Filter):
    """Remappe le niveau de log des records dont le message contient un pattern configuré."""

    _LEVEL_MAP = {
        'DEBUG':   logging.DEBUG,
        'INFO':    logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR':   logging.ERROR,
    }

    def __init__(self, entries: list) -> None:
        super().__init__()
        self._rules = [
            (e['pattern'], e['level'].upper())
            for e in entries
            if e.get('enabled', True) and e.get('pattern', '').strip()
        ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        for pattern, level in self._rules:
            if pattern in msg:
                if level == 'DROP':
                    return False
                target = self._LEVEL_MAP.get(level)
                if target is not None:
                    record.levelno = target
                    record.levelname = level
                    # Le seuil du logger a été contrôlé avant ce filtre, sur le niveau d'origine : on le réapplique au nouveau niveau,
                    # sinon un message abaissé sous ce seuil resterait affiché (simplement réétiqueté) au lieu d'être masqué
                    return target >= logging.getLogger(record.name).getEffectiveLevel()
                return True
        return True

# ----------------------------------------------------------------------------

def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='TVRemote Daemon for Jeedom plugin')
    parser.add_argument("--loglevel", help="Log Level for the daemon", type=str)
    parser.add_argument("--tvloglevel", help="Log Level for TV libraries (zeroconf, androidtvremote2, adb_shell)", type=str, default='daemon')
    parser.add_argument("--logfiltersenabled", help="Enable log filters", type=str, default='0')
    parser.add_argument("--pluginversion", help="Plugin Version", type=str)
    parser.add_argument("--socketport", help="Port for TVRemote server", type=str)
    parser.add_argument("--cyclefactor", help="Cycle Factor", type=str)
    parser.add_argument("--jeedomname", help="Jeedom Name", type=str)
    parser.add_argument("--callback", help="Jeedom callback url", type=str)
    parser.add_argument("--apikey", help="Plugin API Key", type=str)
    parser.add_argument("--pid", help="daemon pid", type=str)

    return parser.parse_args()

def shutdown() -> None:
    _LOGGER.info("[SHUTDOWN] Shuting down")
    config.is_ending = True

    _LOGGER.debug("[SHUTDOWN] Removing PID file %s", config.pid_filename)
    try:
        os.remove(config.pid_filename)
    except FileNotFoundError:
        _LOGGER.debug("[SHUTDOWN] PID file already removed or does not exist")
    except Exception as e:
        _LOGGER.error("[SHUTDOWN] Error removing PID file: %s", e)

    _LOGGER.debug("[SHUTDOWN] Exit 0")
    sys.stdout.flush()
    os._exit(0)

# ----------------------------------------------------------------------------

_LOGGER = logging.getLogger(__name__)

# Démarrage du démon seulement quand le fichier est lancé : importé (tests), il ne lit pas d'arguments et ne démarre rien
if __name__ == '__main__':
    args = get_args()
    config = Config(**vars(args))

    Utils.init_logger(config.log_level)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    if config.tv_log_level != 'daemon':
        _tv_level = Utils.convert_log_level(config.tv_log_level)
        logging.getLogger('zeroconf').setLevel(_tv_level)
        logging.getLogger('androidtvremote2').setLevel(_tv_level)
        logging.getLogger('adb_shell').setLevel(_tv_level)

    if config.log_filters_enabled_arg != '0':
        config.log_filters_enabled = True

    if config.log_filters_enabled:
        try:
            with open(config.log_filters_file_path, 'r', encoding='utf-8') as _f:
                config.log_filters = json.load(_f)
        except FileNotFoundError:
            logging.warning('[DAEMON][LOGFILTERS] Fichier introuvable : %s', config.log_filters_file_path)
        except Exception as _e:
            logging.warning('[DAEMON][LOGFILTERS] Erreur lecture filtres : %s', _e)

    if config.log_filters_enabled and config.log_filters:
        _remap_filter = PatternRemapFilter(config.log_filters)
        for _handler in logging.root.handlers:
            _handler.addFilter(_remap_filter)
        _active_count = sum(1 for r in config.log_filters if r.get('enabled', True))
        logging.info('[DAEMON][LOGFILTERS] %d filtre(s) actif(s) sur %d', _active_count, len(config.log_filters))

    try:
        _LOGGER.info('[DAEMON] Starting Daemon')
        _LOGGER.info('[DAEMON] Plugin Version: %s', config.plugin_version)
        _LOGGER.info('[DAEMON] Pairing Name: %s', config.client_name)
        _LOGGER.info('[DAEMON] Log Level: %s', config.log_level)
        _LOGGER.info('[DAEMON] TV Log Level: %s', config.tv_log_level)
        _LOGGER.info('[DAEMON] Log Filters Enabled: %s | rules: %d', config.log_filters_enabled, len(config.log_filters))
        _LOGGER.info('[DAEMON] Socket Port: %s', config.socket_port)
        _LOGGER.info('[DAEMON] Socket Host: %s', config.socket_host)
        _LOGGER.info('[DAEMON] Cycle Factor: %s', config.cycle_factor)
        # TODO protéger les valeurs de cyclefactor

        _LOGGER.info('[DAEMON] Cycle Main: %s', config.cycle_main)
        _LOGGER.info('[DAEMON] Cycle Comm: %s', config.cycle_comm)
        _LOGGER.info('[DAEMON] Cycle Event: %s', config.cycle_event)
        _LOGGER.info('[DAEMON] PID File: %s', config.pid_filename)
        _LOGGER.info('[DAEMON] Api Key: %s', "***")
        _LOGGER.info('[DAEMON] CallBack: %s', config.callback_url)
        _LOGGER.info('[DAEMON] Cert/Key Files: %s :: %s', config.cert_file, config.key_file)

        Utils.write_pid(str(config.pid_filename))

        daemon = TVRemoted(config)
        asyncio.run(daemon.main())
    except Exception as e:
        exception_type, exception_object, exception_traceback = sys.exc_info()
        if exception_traceback is not None:
            filename = exception_traceback.tb_frame.f_code.co_filename
            line_number = exception_traceback.tb_lineno
            _LOGGER.error('[DAEMON] Fatal error: %s(%s) in %s on line %s', e, exception_type, filename, line_number)
        else:
            _LOGGER.error('[DAEMON] Fatal error: %s(%s)', e, exception_type)
        _LOGGER.debug(traceback.format_exc())
    shutdown()
