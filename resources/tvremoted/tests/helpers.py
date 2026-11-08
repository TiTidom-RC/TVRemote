""" Utilitaires communs aux tests du démon : configuration de test, faux canal vers Jeedom, fausse TV Google TV. Aucune TV ni aucun Jeedom nécessaire. """

import asyncio
import time

from config import Config

API_KEY = 'testApiKey'


async def waitUntil(condition, timeout: float = 2.0) -> bool:
    """ Attend qu'une condition devienne vraie en laissant tourner la boucle asyncio (tâches des appareils) """
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        await asyncio.sleep(0.01)
    return condition()


class FakeAdb:
    """ Remplace adb_shell AdbDeviceTcpAsync. Chaque connect() consomme le résultat suivant de `connectResults`, commun à toutes les
    instances : une exception à lever, un asyncio.Event à attendre avant de réussir, ou None ; liste vide : connexion réussie """
    connectResults: list = []
    instances: list = []
    shellError = None  # exception levée par le prochain shell()

    def __init__(self, host, port, default_transport_timeout_s=None):
        self.host = host
        self.connectCalls = 0
        self.signers = []
        self.commands = []
        self.connected = False
        FakeAdb.instances.append(self)

    @classmethod
    def reset(cls, results=None):
        cls.connectResults = list(results or [])
        cls.instances = []
        cls.shellError = None

    @classmethod
    def totalConnectCalls(cls):
        return sum(adb.connectCalls for adb in cls.instances)

    @classmethod
    def allCommands(cls):
        return [command for adb in cls.instances for command in adb.commands]

    async def connect(self, rsa_keys=None, transport_timeout_s=None, auth_timeout_s=None):
        self.connectCalls += 1
        self.signers.append(rsa_keys[0] if rsa_keys else None)
        if FakeAdb.connectResults:
            result = FakeAdb.connectResults.pop(0)
            if isinstance(result, asyncio.Event):
                await result.wait()
            elif result is not None:
                raise result
        self.connected = True
        return True

    async def shell(self, command, transport_timeout_s=None):
        if FakeAdb.shellError is not None:
            error, FakeAdb.shellError = FakeAdb.shellError, None
            raise error
        self.commands.append(command)
        return 'ok'

    async def close(self):
        self.connected = False


class FakeRemote:
    """ Remplace androidtvremote2.AndroidTVRemote. Chaque appel à async_connect consomme le résultat suivant de `script`
    (une exception à lever, ou None pour une connexion réussie) ; script vide : connexion réussie """
    script: list = []
    instances: list = []
    initialVolume = None  # volume_info des prochaines instances
    certError = None  # exception levée par async_generate_cert_if_missing des prochaines instances
    MAC = '11:22:33:44:55:66'  # renvoyée par async_get_name_and_mac (scan)
    nameAndMacErrors: dict = {}  # par hôte : exception levée par async_get_name_and_mac

    def __init__(self, client_name, certfile, keyfile, host, enable_ime=True, **kwargs):
        self.host = host
        self.enable_ime = enable_ime
        self.results = list(FakeRemote.script)
        self.certError = FakeRemote.certError
        self.connectCalls = 0
        self.connected = False
        self.disconnected = False
        self.keys = []
        self.callbacks = {}
        self.invalidAuthCallback = None
        self.is_on = False
        self.current_app = ''
        self.volume_info = FakeRemote.initialVolume
        self.device_info = {}
        self.pairingCodes = []
        FakeRemote.instances.append(self)

    @classmethod
    def reset(cls, script=None):
        cls.script = list(script or [])
        cls.instances = []
        cls.initialVolume = None
        cls.certError = None
        cls.nameAndMacErrors = {}

    @classmethod
    def running(cls):
        """ Instances dont la connexion n'a pas été fermée """
        return [remote for remote in cls.instances if not remote.disconnected]

    async def async_generate_cert_if_missing(self):
        if self.certError is not None:
            raise self.certError
        return False

    def losePairing(self, script=None):
        """ Simule une reconnexion de la bibliothèque refusée faute d'appairage : elle appelle le rappel et ne réessaie plus """
        self.connected = False
        self.results = list(script or [])
        self.invalidAuthCallback()

    async def async_connect(self):
        self.connectCalls += 1
        if self.results:
            result = self.results.pop(0)
            if result is not None:
                raise result
        self.connected = True
        # Comme la bibliothèque : le message remote_start de la connexion notifie l'état allumé/éteint
        if 'is_on' in self.callbacks:
            self.callbacks['is_on'](self.is_on)

    def keep_reconnecting(self, invalid_auth_callback=None):
        self.invalidAuthCallback = invalid_auth_callback

    def disconnect(self):
        self.disconnected = True
        self.connected = False

    def add_is_available_updated_callback(self, callback):
        self.callbacks['is_available'] = callback

    def add_is_on_updated_callback(self, callback):
        self.callbacks['is_on'] = callback

    def add_current_app_updated_callback(self, callback):
        self.callbacks['current_app'] = callback

    def add_volume_info_updated_callback(self, callback):
        self.callbacks['volume_info'] = callback

    def send_key_command(self, key_code, direction='SHORT'):
        self.keys.append(key_code)

    def send_launch_app_command(self, app_link):
        self.keys.append(('app', app_link))

    async def async_get_name_and_mac(self):
        error = FakeRemote.nameAndMacErrors.get(self.host)
        if error is not None:
            raise error
        return 'Sony', FakeRemote.MAC

    async def async_start_pairing(self):
        pass

    async def async_finish_pairing(self, pairing_code):
        self.pairingCodes.append(pairing_code)


def newConfig(**kwargs) -> Config:
    """ Configuration du démon telle que construite à partir des arguments de la ligne de commande """
    args = {'apikey': API_KEY, 'loglevel': 'debug', 'jeedomname': 'Jeedom'}
    args.update(kwargs)
    return Config(**args)


class FakePublisher:
    """ Remplace jeedom.aio_connector.Publisher : mémorise les envois vers Jeedom (cycle et immédiat) """
    def __init__(self):
        self.changes = []
        self.sent = []
        self.failures = 0  # nombre de prochains envois immédiats en échec (Jeedom injoignable)

    async def add_change(self, key, value):
        self.changes.append((key, dict(value)))

    async def send_to_jeedom(self, payload):
        if self.failures > 0:
            self.failures -= 1
            raise OSError('Jeedom unreachable')
        self.sent.append(dict(payload))
        return True

    def changesFor(self, mac):
        """ Valeurs envoyées en temps réel pour un appareil, dans l'ordre """
        return [value for key, value in self.changes if key == 'devicesRT::' + mac]
