import datetime
import logging
import argparse
import resource
import sys
import os
import signal
import asyncio
import functools
import time
import traceback
import ipaddress

from config import Config
from jeedom.utils import Utils
from jeedom.aio_connector import Listener, Publisher

# from urllib.parse import urljoin, urlencode, urlparse

# Import pour ZeroConf
try:
    from zeroconf import ServiceStateChange, Zeroconf
    from zeroconf.asyncio import AsyncServiceBrowser, AsyncServiceInfo, AsyncZeroconf
except ImportError as e: 
    print("[DAEMON][IMPORT] Exception Error: importing module ZeroConf ::", e)
    sys.exit(1)

# Import pour AndroidTVRemote2
try:
    from androidtvremote2 import AndroidTVRemote, CannotConnect, ConnectionClosed, InvalidAuth
except ImportError as e: 
    print("[DAEMON][IMPORT] Exception Error: importing module AndroidTVRemote2 ::", e)
    sys.exit(1)
          
class EQRemote(object):
    """This is the Remote Device class"""

    def __init__(self, _mac, _host, _config: Config, _jeedom_publisher) -> None:
        # Standard Init of class
        self._config = _config
        self._remote = None
        self._macAddr = _mac
        self._host = _host
        self._logger = logging.getLogger(__name__)
        self._jeedom_publisher = _jeedom_publisher
        self._loop = asyncio.get_running_loop()

    async def main(self):
        """
        The is the entry point of your class EQRemote.
        You should start the asyncio task with this function like this: `asyncio.createtask(myEQRemote.main())`
        """
        try:
            self._logger.debug("[EQRemote][MAIN][%s] Starting Main for Host :: %s", self._macAddr, self._host)
            
            self._remote = AndroidTVRemote(self._config.client_name, self._config.cert_file, self._config.key_file, self._host)
            
            if self._remote is None:
                self._logger.error("[EQRemote][Remote] Object Creation Failed :: Object is None !")
                return
            
            if await self._remote.async_generate_cert_if_missing():
                self._logger.info("[EQRemote][CERT][%s] Generated New Cert/Key Files :: %s | %s", self._macAddr, self._config.cert_file, self._config.key_file)
            
            while not self._config.is_ending:
                try:
                    await self._remote.async_connect()
                    break
                except InvalidAuth as exc:
                    self._logger.error("[EQRemote][MAIN][%s] Not Paired. Exception :: %s", self._macAddr, exc)
                    
                    # Envoi des logs vers Jeedom
                    data = {
                        'PairingExc': str(exc),
                        'pairing_mac': self._macAddr,
                        'pairing_host': self._host,
                        'pairing_value': 0
                    }
                    await self._jeedom_publisher.send_to_jeedom(data)
                    await asyncio.sleep(60)
                    continue
                except (CannotConnect, ConnectionClosed) as exc:
                    self._logger.error("[EQRemote][MAIN][%s] Cannot connect. Exception :: %s", self._macAddr, exc)
                    await asyncio.sleep(60)
                    continue
                except Exception as e:
                    self._logger.error("[EQRemote][Connect][%s] Exception :: %s", self._macAddr, e)
                    self._logger.debug(traceback.format_exc())
                    await asyncio.sleep(60)
                    continue
                    
            self._remote.keep_reconnecting()
            
            try:
                self._logger.info("[EQRemote][MAIN][%s] Device_Info :: %s", self._macAddr, self._remote.device_info)
                self._logger.info("[EQRemote][MAIN][%s] Is_On :: %s", self._macAddr, self._remote.is_on)
                self._logger.info("[EQRemote][MAIN][%s] Current_App :: %s", self._macAddr, self._remote.current_app)
                self._logger.info("[EQRemote][MAIN][%s] Volume_Info :: %s", self._macAddr, self._remote.volume_info)
            
                # UpdateLastTime
                currentTime = int(time.time())
                currentTimeStr = datetime.datetime.fromtimestamp(currentTime).strftime("%d/%m/%Y - %H:%M:%S")    
                
                _isOn = 1 if self._remote.is_on else 0
                if all(keys in self._remote.volume_info for keys in ('level', 'muted', 'max')):
                    _volume_level = self._remote.volume_info['level']
                    _volume_muted = 1 if self._remote.volume_info['muted'] else 0
                    _volume_max = self._remote.volume_info['max']
                else:
                    _volume_level = 0
                    _volume_muted = 0
                    _volume_max = 0
                
                data = {
                    'mac': self._macAddr,
                    'online': 1,
                    'is_on': _isOn,
                    'current_app': self._remote.current_app,
                    'volume_level': _volume_level,
                    'volume_muted': _volume_muted,
                    'volume_max': _volume_max,
                    'updatelasttime': currentTimeStr,
                    'updatelasttimets': currentTime,
                    'realtime': 1
                }
                # Envoi vers Jeedom
                self._loop.create_task(self._jeedom_publisher.add_change('devicesRT::' + data['mac'], data))
            except Exception as e:
                self._logger.error('[EQRemote][MAIN-Publisher][%s] Exception :: %s', self._macAddr, e)
                self._logger.debug(traceback.format_exc())

            def is_available_updated(is_available: bool) -> None:
                self._logger.info("[EQRemote][Is_Available][%s] Notification :: %s", self._macAddr, is_available)
                try:
                    # UpdateLastTime
                    currentTime = int(time.time())
                    currentTimeStr = datetime.datetime.fromtimestamp(currentTime).strftime("%d/%m/%Y - %H:%M:%S")
                    
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
                self._logger.info("[EQRemote][Is_On][%s] Notification :: %s", self._macAddr, is_on)
                try:
                    # UpdateLastTime
                    currentTime = int(time.time())
                    currentTimeStr = datetime.datetime.fromtimestamp(currentTime).strftime("%d/%m/%Y - %H:%M:%S")
                    
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
                self._logger.info("[EQRemote][Current_App][%s] Notification :: %s", self._macAddr, current_app)
                try:
                    # UpdateLastTime
                    currentTime = int(time.time())
                    currentTimeStr = datetime.datetime.fromtimestamp(currentTime).strftime("%d/%m/%Y - %H:%M:%S")
                    
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

            def volume_info_updated(volume_info: dict[str, str | bool]) -> None:
                self._logger.info("[EQRemote][Volume_Info][%s] Notification :: %s", self._macAddr, volume_info)
                try:
                    # UpdateLastTime
                    currentTime = int(time.time())
                    currentTimeStr = datetime.datetime.fromtimestamp(currentTime).strftime("%d/%m/%Y - %H:%M:%S")
                    
                    _volume_level = volume_info['level']
                    _volume_muted = 1 if volume_info['muted'] else 0
                    _volume_max = volume_info['max']
                    
                    data = {
                        'mac': self._macAddr,
                        'volume_level': _volume_level,
                        'volume_muted': _volume_muted,
                        'volume_max': _volume_max,
                        'updatelasttime': currentTimeStr,
                        'updatelasttimets': currentTime,
                        'realtime': 1
                    }
                    # Envoi vers Jeedom
                    self._loop.create_task(self._jeedom_publisher.add_change('devicesRT::' + data['mac'], data))
                except Exception as e:
                    self._logger.error('[EQRemote][Volume_Info] Exception :: %s', e)
                    self._logger.debug(traceback.format_exc())

            self._remote.add_is_available_updated_callback(is_available_updated)
            self._remote.add_is_on_updated_callback(is_on_updated)
            self._remote.add_current_app_updated_callback(current_app_updated)
            self._remote.add_volume_info_updated_callback(volume_info_updated)
        
        except asyncio.CancelledError:
            self._logger.debug("[EQRemote] Stop Main")
        except Exception as e: 
            self._logger.error("[EQRemote][MAIN] Exception :: %s", e)
            self._logger.debug(traceback.format_exc())
        
    async def remove(self):
        """Call it to disconnect from a EQRemote"""
        self._remote.disconnect()
        await asyncio.sleep(1)
        self._remote = None
    
    async def send_command(self, action: str = None, value: str = None) -> None:
        """Call it to send command to EQRemote"""
        try:
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
            self._logger.error("[EQRemote][SendCommand] Exception (ConnectionError) :: %s", e)
            self._logger.debug(traceback.format_exc())
        except Exception as e:
            self._logger.error("[EQRemote][SendCommand] Exception :: %s", e)
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
        # self._tvhosts_task = None
        # self._search_task = None

    async def main(self):
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
        await self._jeedom_publisher.send_to_jeedom({'daemonStarted': '1'})
        self._logger.info("[MAINLOOP] DaemonStarted Info :: OK")
        
        # ensure that the loop continues to run until all tasks are completed or canceled, you must list here all tasks previously created
        self._config.tasks = [self._listen_task, self._send_task, self._main_task]
        await asyncio.gather(*self._config.tasks)
        
    async def __add_signal_handler(self):
        """
        This function register signal handler to interupt the loop in case of process kill is received from Jeedom. You don't need to change anything here
        """
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGINT, functools.partial(self._ask_exit, signal.SIGINT))
        loop.add_signal_handler(signal.SIGTERM, functools.partial(self._ask_exit, signal.SIGTERM))

    async def _on_socket_message(self, message: list):
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
                    if (message['cmd_action'] in ('volumeup', 'volumedown', 'up', 'down', 'left', 'right', 'center', 'mute_on', 'mute_off', 'power_on', 'power_off', 'back', 'home', 'menu', 'tv', 'channel_up', 'channel_down', 'info', 'settings', 'input', 'hdmi_1', 'hdmi_2', 'hdmi_3', 'hdmi_4', 'oqee', 'youtube', 'netflix', 'primevideo', 'disneyplus', 'mycanal', 'plex', 'appletv', 'orangetv', 'molotov', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'zero', 'keycode', 'appcode', 'media_next', 'media_stop', 'media_pause', 'media_play', 'media_rewind', 'media_previous', 'media_forward') and 'mac' in message):
                        self._logger.debug('[DAEMON][SOCKET] Action :: %s @ %s (%s)', message['cmd_action'], message['mac'], message['value'])
                        if message['mac'] in self._config.remote_mac:
                            await self._config.remote_devices[message['mac']].send_command(message['cmd_action'], message['value'])
                    else:
                        self._logger.warning('[DAEMON][SOCKET] Unknown Action :: %s', message['cmd_action'])
            elif message['cmd'] == "scanOn":
                self._logger.debug('[DAEMON][SOCKET] ScanState = scanOn') 
                self._config.scanmode = True
                self._config.scanmode_start = int(time.time())
                await self._jeedom_publisher.send_to_jeedom({'scanState': 'scanOn'})
            elif message['cmd'] == "scanOff":
                self._logger.debug('[DAEMON][SOCKET] ScanState = scanOff')
                self._config.scanmode = False
                await self._jeedom_publisher.send_to_jeedom({'scanState': 'scanOff'})
            elif message['cmd'] == "sendBeginPairing":
                self._logger.debug('[DAEMON][SOCKET] Begin Pairing for (Mac :: %s) :: %s:%s / %s', message['mac'], message['host'], message['port'])
                await self._pairing(message['mac'], message['host'], message['port'])
            elif message['cmd'] == "sendPairCode":
                self._logger.debug('[DAEMON][SOCKET] Received Pairing Code (Mac :: %s) :: %s', message['mac'], message['paircode'])
                self._config.pairing_code = message['paircode']
            elif message['cmd'] == "addtvremote":
                if all(keys in message for keys in ('mac', 'host', 'port', 'friendly_name')):
                    self._logger.debug('[DAEMON][SOCKET] Add TVRemote Device (Mac :: %s) :: %s:%s', message['mac'], message['host'], message['port'])
                    if message['host'] not in self._config.known_hosts:
                        self._config.known_hosts.append(message['host'])
                        self._logger.debug('[DAEMON][SOCKET] Add TVRemote to KNOWN Devices :: %s', str(self._config.known_hosts))
                    if message['friendly_name'] not in self._config.remote_names:
                        self._config.remote_names.append(message['friendly_name'])
                        self._logger.debug('[DAEMON][SOCKET] Add TVRemote to Remote Names :: %s', str(self._config.remote_names))
                    if message['mac'] not in self._config.remote_mac:
                        self._config.remote_mac.append(message['mac'])
                        self._logger.debug('[DAEMON][SOCKET] Add TVRemote to Remote MAC :: %s', str(self._config.remote_mac))
                        self._config.remote_devices[message['mac']] = EQRemote(message['mac'], message['host'], self._config, self._jeedom_publisher)
                        await self._config.remote_devices[message['mac']].main()
            elif message['cmd'] == "removetvremote":
                if all(keys in message for keys in ('mac', 'host', 'port', 'friendly_name')):
                    self._logger.debug('[DAEMON][SOCKET] Remove TVRemote (Mac :: %s) :: %s:%s', message['mac'], message['host'], message['port'])
                    if message['host'] in self._config.known_hosts:
                        self._config.known_hosts.remove(message['host'])
                        self._logger.debug('[DAEMON][SOCKET] Remove TVRemote from KNOWN Devices :: %s', str(self._config.known_hosts))
                    if message['friendly_name'] in self._config.remote_names:
                        self._config.remote_names.remove(message['friendly_name'])
                        self._logger.debug('[DAEMON][SOCKET] Remove TVRemote from Remote Names :: %s', str(self._config.remote_names))
                    if message['mac'] in self._config.remote_mac:
                        self._config.remote_mac.remove(message['mac'])
                        self._logger.debug('[DAEMON][SOCKET] Remove TVRemote from KNOWN Devices :: %s', str(self._config.remote_mac))
                        await self._config.remote_devices[message['mac']].remove()
                        del self._config.remote_devices[message['mac']]
                        
            else:
                self._logger.warning('[DAEMON][SOCKET] Unknown Cmd :: %s', message['cmd'])
                
        except Exception as message_e:
            self._logger.error('[MAIN][SOCKET] Exception :: %s', message_e)
            self._logger.debug(traceback.format_exc())
            
    async def _pairing(self, _mac=None, _host=None, _port=None) -> None:
        """ Function to pair Plugin with TV """
        
        if self._config.scanmode:
            self._logger.error("[PAIRING] TV ScanMode in Progress. Stop Scan before trying to Pair.")
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
                self._logger.debug("[PAIRING][START][%s] Start Pairing...", _mac)
                await remote.async_start_pairing()
            except (CannotConnect, ConnectionClosed) as e:
                self._logger.error("[PAIRING][START][%s] Exception :: %s", _mac, e)
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
                    return await remote.async_finish_pairing(self._config.pairing_code)
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
                currentTimeStr = datetime.datetime.fromtimestamp(currentTime).strftime("%d/%m/%Y - %H:%M:%S")
                
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

    async def _mainLoop(self, cycle=2.0):
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
                        await self._jeedom_publisher.send_to_jeedom({'scanState': 'scanOff'})                    
                    # Heartbeat du démon
                    if ((self._config.heartbeat_lasttime + self._config.heartbeat_frequency) <= currentTime):
                        self._logger.info('[MAINLOOP] Heartbeat = 1')
                        await self._jeedom_publisher.send_to_jeedom({'heartbeat': '1'})
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
            
    async def _getResourcesUsage(self):
        if (self._logger.isEnabledFor(logging.INFO)):
            resourcesUse = resource.getrusage(resource.RUSAGE_SELF)
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
    
    async def _is_ipv4(self, ip: str):
        try:
            ipaddress.IPv4Address(ip)
            return True
        except ValueError:
            return False
            
    def _ask_exit(self, sig):
        """
        This function will be called in case a signal is received, see `__add_signal_handler`. You don't need to change anything here
        """
        self._logger.info("[ASKEXIT] Signal %i caught, exiting...", sig)
        self.close()

    def close(self):
        """
        This function can be called from outside to stop the daemon if needed`
        You need to close your remote connexions and cancel background tasks if any here.
        """
        self._logger.debug('[CLOSE] Cancel all tasks')
        # self._search_task.cancel()  # don't forget to cancel your background task
        self._main_task.cancel()
        self._listen_task.cancel()
        self._send_task.cancel()

# ----------------------------------------------------------------------------

def get_args():
    parser = argparse.ArgumentParser(description='TVRemote Daemon for Jeedom plugin')
    parser.add_argument("--loglevel", help="Log Level for the daemon", type=str)
    parser.add_argument("--pluginversion", help="Plugin Version", type=str)
    parser.add_argument("--socketport", help="Port for TVRemote server", type=str)
    parser.add_argument("--cyclefactor", help="Cycle Factor", type=str)
    parser.add_argument("--jeedomname", help="Jeedom Name", type=str)
    parser.add_argument("--callback", help="Jeedom callback url", type=str)
    parser.add_argument("--apikey", help="Plugin API Key", type=str)
    parser.add_argument("--pid", help="daemon pid", type=str)

    return parser.parse_args()

def shutdown():
    _LOGGER.info("[SHUTDOWN] Shuting down")
    config.is_ending = True

    _LOGGER.debug("[SHUTDOWN] Removing PID file %s", config.pid_filename)
    os.remove(config.pid_filename)

    _LOGGER.debug("[SHUTDOWN] Exit 0")
    sys.stdout.flush()
    os._exit(0)

# ----------------------------------------------------------------------------

args = get_args()
config = Config(**vars(args))

Utils.init_logger(config.log_level)
_LOGGER = logging.getLogger(__name__)
logging.getLogger('asyncio').setLevel(logging.WARNING)

try:
    _LOGGER.info('[DAEMON] Starting Daemon')
    _LOGGER.info('[DAEMON] Plugin Version: %s', config.plugin_version)
    _LOGGER.info('[DAEMON] Pairing Name: %s', config.client_name)
    _LOGGER.info('[DAEMON] Log Level: %s', config.log_level)
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
    filename = exception_traceback.tb_frame.f_code.co_filename
    line_number = exception_traceback.tb_lineno
    _LOGGER.error('[DAEMON] Fatal error: %s(%s) in %s on line %s', e, exception_type, filename, line_number)
    _LOGGER.debug(traceback.format_exc())
shutdown()
