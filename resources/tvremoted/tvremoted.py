import logging
import argparse
import random
import sys
import os
import signal
import asyncio
import functools

from config import Config
from jeedom.utils import Utils
from jeedom.aio_connector import Listener, Publisher

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
        # self._search_task = None

    async def main(self):
        """
        The is the entry point of your daemon.
        You should start the asyncio loop with this function like this: `asyncio.run(daemon.main())`
        """
        self._jeedom_publisher = Publisher(self._config.callback_url, self._config.api_key, self._config.cycle)
        if not await self._jeedom_publisher.test_callback():
            return

        # _listen_task & _send_task are 2 background tasks handling communication with the daemon
        self._listen_task = Listener.create_listen_task(self._config.socket_host, self._config.socket_port, self._on_socket_message)
        self._send_task = self._jeedom_publisher.create_send_task()  # Not needed if you don't need to send change to Jeedom in cycle but only immediately

        # create your own background tasks if needed.
        # `_search_task` is here to demo usage of background task in a daemon
        # self._search_task = asyncio.create_task(self._search_animals())

        # register signal handler
        await self.__add_signal_handler()
        await asyncio.sleep(1)  # allow all tasks to start

        self._logger.info("Ready")
        # ensure that the loop continues to run until all tasks are completed or canceled, you must list here all tasks previously created
        #  await asyncio.gather(self._search_task, self._listen_task, self._send_task)
        await asyncio.gather(self._listen_task, self._send_task)

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
            self._logger.error('Invalid apikey from socket : %s', message)
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
        await self._jeedom_publisher.send_to_jeedom({'alert':f"'{message}' was an interesting information, thanks for the nap"})

    async def _search_animals(self):
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
        self._logger.info("Signal %i caught, exiting...", sig)
        self.close()

    def close(self):
        """
        This function can be called from outside to stop the daemon if needed`
        You need to close your remote connexions and cancel background tasks if any here.
        """
        self._logger.debug('Cancel all tasks')
        # self._search_task.cancel()  # don't forget to cancel your background task
        self._listen_task.cancel()
        self._send_task.cancel()


# ----------------------------------------------------------------------------

def get_args():
    parser = argparse.ArgumentParser(description='TVRemote Daemon for Jeedom plugin')
    parser.add_argument("--loglevel", help="Log Level for the daemon", type=str)
    parser.add_argument("--socketport", help="Socket Port", type=int)
    parser.add_argument("--cycle", help="cycle", type=float)
    parser.add_argument("--callback", help="Jeedom callback url", type=str)
    parser.add_argument("--apikey", help="Plugin API Key", type=str)
    parser.add_argument("--pid", help="daemon pid", type=str)

    return parser.parse_args()

def shutdown():
    _LOGGER.info("Shuting down")

    _LOGGER.debug("Removing PID file %s", config.pid_filename)
    os.remove(config.pid_filename)

    _LOGGER.debug("Exit 0")
    sys.stdout.flush()
    os._exit(0)

# ----------------------------------------------------------------------------

args = get_args()
config = Config(**vars(args))

Utils.init_logger(config.log_level)
_LOGGER = logging.getLogger(__name__)
logging.getLogger('asyncio').setLevel(logging.WARNING)

try:
    _LOGGER.info('Starting daemon')
    _LOGGER.info('Log level: %s', config.log_level)
    Utils.write_pid(str(config.pid_filename))

    daemon = TVRemoted(config)
    asyncio.run(daemon.main())
except Exception as e:
    exception_type, exception_object, exception_traceback = sys.exc_info()
    filename = exception_traceback.tb_frame.f_code.co_filename
    line_number = exception_traceback.tb_lineno
    _LOGGER.error('Fatal error: %s(%s) in %s on line %s', e, exception_type, filename, line_number)
shutdown()
