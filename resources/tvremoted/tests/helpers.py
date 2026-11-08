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


class FakeRemote:
    """ Remplace androidtvremote2.AndroidTVRemote. Chaque appel à async_connect consomme le résultat suivant de `script`
    (une exception à lever, ou None pour une connexion réussie) ; script vide : connexion réussie """
    script: list = []
    instances: list = []

    def __init__(self, client_name, certfile, keyfile, host, enable_ime=True, **kwargs):
        self.host = host
        self.enable_ime = enable_ime
        self.results = list(FakeRemote.script)
        self.connectCalls = 0
        self.connected = False
        self.disconnected = False
        self.keys = []
        self.callbacks = {}
        self.is_on = False
        self.current_app = ''
        self.volume_info = None
        self.device_info = {}
        self.pairingCodes = []
        FakeRemote.instances.append(self)

    @classmethod
    def reset(cls, script=None):
        cls.script = list(script or [])
        cls.instances = []

    async def async_generate_cert_if_missing(self):
        return False

    async def async_connect(self):
        self.connectCalls += 1
        if self.results:
            result = self.results.pop(0)
            if result is not None:
                raise result
        self.connected = True

    def keep_reconnecting(self, invalid_auth_callback=None):
        pass

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

    async def add_change(self, key, value):
        self.changes.append((key, dict(value)))

    async def send_to_jeedom(self, payload):
        self.sent.append(dict(payload))
        return True

    def changesFor(self, mac):
        """ Valeurs envoyées en temps réel pour un appareil, dans l'ordre """
        return [value for key, value in self.changes if key == 'devicesRT::' + mac]
