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

from urllib.parse import urljoin, urlencode, urlparse

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
        self._tvhosts_task = None
        # self._search_task = None

    async def main(self):
        """
        The is the entry point of your daemon.
        You should start the asyncio loop with this function like this: `asyncio.run(daemon.main())`
        """
        self._jeedom_publisher = Publisher(self._config.callback_url, self._config.api_key, self._config.cycle_factor * self._config.cycle_comm)
        if not await self._jeedom_publisher.test_callback():
            self._logger.info("[CALLBACK] Test :: OK")
            return

        # _listen_task & _send_task are 2 background tasks handling communication with the daemon
        self._listen_task = Listener.create_listen_task(self._config.socket_host, self._config.socket_port, self._on_socket_message)
        self._send_task = self._jeedom_publisher.create_send_task()  # Not needed if you don't need to send change to Jeedom in cycle but only immediately

        # create your own background tasks here.
        # self._search_task = asyncio.create_task(self._search_animals())
        self._main_task = asyncio.create_task(self._mainLoop(self._config.cycle_main))
        self._tvhosts_task = asyncio.create_task(self._tvhosts_from_zeroconf(timeout=30))
        
        # register signal handler
        await self.__add_signal_handler()
        await asyncio.sleep(1)  # allow all tasks to start

        self._logger.info("[MAIN] Ready")
        # ensure that the loop continues to run until all tasks are completed or canceled, you must list here all tasks previously created
        #  await asyncio.gather(self._search_task, self._listen_task, self._send_task)
        await asyncio.gather(self._tvhosts_task, self._main_task, self._listen_task, self._send_task)

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
            """ if message['action'] == 'think':
                await self._think(message['message'])
            elif message['action'] == 'ping':
                for i in range(1, 4):
                    await self._jeedom_publisher.send_to_jeedom({'pingpong' : f'ping {i}'})
                    await asyncio.sleep(2)
                    await self._jeedom_publisher.send_to_jeedom({'pingpong' : f'pong {i}'})
                    await asyncio.sleep(2)
            else:
                self._logger.warning('Unknown action: %s', message['action']) """
        except Exception as message_e:
            self._logger.error('Send command to daemon error: %s', message_e)

    """ async def _think(self, message):
        # this is a demo implementation of a single function, this function will be invoked once the corresponding call is received from Jeedom
        random_int = random.randint(3, 15)
        self._logger.info("==> think on received '%s' during %is", message, random_int)
        await self._jeedom_publisher.send_to_jeedom({'alert':f"Let me think about '{message}' during {random_int}s"})
        await asyncio.sleep(random_int)
        self._logger.info("==> '%s' was an interesting information, thanks for the nap", message)
        await self._jeedom_publisher.send_to_jeedom({'alert':f"'{message}' was an interesting information, thanks for the nap"}) """

    async def _tvhosts_from_zeroconf(self, timeout: float = 30.0) -> None:
        """ Function to detect TV hosts from ZeroConf Instance """
        
        def _async_on_service_state_change(zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
            if state_change is not ServiceStateChange.Added:
                return
            _ = asyncio.ensure_future(async_display_service_info(zeroconf, service_type, name))

        async def async_display_service_info(zeroconf: Zeroconf, service_type: str, name: str) -> None:
            info = AsyncServiceInfo(service_type, name)
            await info.async_request(zeroconf, 3000)
            if info:
                self._logger.info("[TVHOSTS][%s] Name :: %s", info.get_name(), name)
                self._logger.info("[TVHOSTS][%s] Type :: %s", info.get_name(), info.type)
                for addr in info.parsed_scoped_addresses():
                    if (await self._is_ipv4(addr)):
                        self._logger.info("[TVHOSTS][%s] Addr:Port (IPv4) :: %s:%s", info.get_name(), addr, str(info.port))
                    # else:
                        # self._logger.info("[TVHOSTS][%s] Addr (IPv6) :: %s (port=%s)", name, addr, str(info.port))
                
                if info.decoded_properties:
                    for key, value in info.decoded_properties.items():
                        self._logger.info("[TVHOSTS][%s] Properties :: %s = %s", info.get_name(), key, value)
                else:
                    self._logger.warning("[TVHOSTS][%s] Properties :: NO", info.get_name())
            else:
                self._logger.warning("[TVHOSTS][%s] Info :: NO", name)

        zc = AsyncZeroconf()
        services = ["_androidtvremote2._tcp.local."]
        self._logger.info("[TVHOSTS] TV Browser (for %s seconds) :: START", timeout)
        browser = AsyncServiceBrowser(zc.zeroconf, services, handlers=[_async_on_service_state_change])
        await asyncio.sleep(timeout)

        await browser.async_cancel()
        await zc.async_close()
        self._logger.info("[TVHOSTS] TV Browser :: STOP")

    async def _mainLoop(self, cycle=2.0):
        # Main Loop for Daemon
        self._logger.debug("[MAINLOOP] Start MainLoop")
        try:
            while True:
                try:
                    
                    # *** Actions de la MainLoop ***
                    currentTime = int(time.time())
                    
                    # Arrêt du ScanMode au bout de 60 secondes
                    
                    # Heartbeat du démon
                    # self._logger.debug("[MAINLOOP] Check Heartbeat")
                    if ((self._config.heartbeat_lasttime + self._config.heartbeat_frequency) <= currentTime):
                        self._logger.info('[MAINLOOP] Heartbeat = 1')
                        await self._jeedom_publisher.send_to_jeedom({'heartbeat': '1'})
                        self._config.heartbeat_lasttime = currentTime
                        await self._getResourcesUsage()
                    # Scan New TVRemote
                        
                except Exception as e:
                    self._logger.error("[MAINLOOP] Exception :: %s", e)
                    self._logger.info(traceback.format_exc())
                
                # Pause Cycle
                await asyncio.sleep(cycle)
                
        except asyncio.CancelledError:
            self._logger.debug("[MAINLOOP] Stop MainLoop")
            
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
    
    """ async def _search_animals(self):
        # this is a demo implementation of a backgroudn task, you must have a try ... except asyncio.CancelledError: ... that will intercept the cancel request from the loop
        self._logger.info("Start searching animals")

        animals = {
            0: 'Cat',
            1: 'Dog',
            2: 'Duck',
            3: 'Sheep',
            4: 'Horse',
            5: 'Cow',
            6: 'Goat',
            7: 'Rabbit'
        }

        try:
            max_int = len(animals) - 1
            while True:
                animal = animals[random.randint(0, max_int)]
                nbr = random.randint(0, 97)
                self._logger.info("I found %i %s(s)", nbr, animal.lower())
                await self._jeedom_publisher.add_change(animal, nbr)
                await asyncio.sleep(random.randint(0, 2))
        except asyncio.CancelledError:
            self._logger.info("Stop searching animals") """
            
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
        self._logger.debug('[ASKEXIT] Cancel all tasks')
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
    parser.add_argument("--callback", help="Jeedom callback url", type=str)
    parser.add_argument("--apikey", help="Plugin API Key", type=str)
    parser.add_argument("--pid", help="daemon pid", type=str)

    return parser.parse_args()

def shutdown():
    _LOGGER.info("[SHUTDOWN] Shuting down")

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
    _LOGGER.info('[DAEMON] Config Path: %s', config.config_fullpath)
    
    Utils.write_pid(str(config.pid_filename))

    daemon = TVRemoted(config)
    asyncio.run(daemon.main())
except Exception as e:
    exception_type, exception_object, exception_traceback = sys.exc_info()
    filename = exception_traceback.tb_frame.f_code.co_filename
    line_number = exception_traceback.tb_lineno
    _LOGGER.error('[DAEMON] Fatal error: %s(%s) in %s on line %s', e, exception_type, filename, line_number)
shutdown()
