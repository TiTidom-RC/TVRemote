""" Utilitaires communs aux tests du démon : configuration de test et faux canal vers Jeedom. Aucune TV ni aucun Jeedom nécessaire. """

from config import Config

API_KEY = 'testApiKey'


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
