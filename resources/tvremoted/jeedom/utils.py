import logging
import os
import re

SECRET_MASK = 'sEcReT'

# Règles de masquage des secrets, uniques côté Python (miroir de tvremote::maskSecrets côté PHP) : toute nouvelle donnée
# sensible est ajoutée ici, des deux côtés, plutôt que masquée au cas par cas.
_SECRET_RULES = [
    # Identifiants dans une URL, y compris échappée en JSON : l'URL reste lisible et lançable (avant la règle des mots-clés)
    (re.compile(r'''(\b[a-z][a-z0-9+.-]*:(?:\\?/){2})[^\s/?#"'@:\\]+:[^\s/?#"']*@''', re.IGNORECASE), r'\1uSeR:' + SECRET_MASK + '@'),
    (re.compile(r'''(\b[a-z][a-z0-9+.-]*:(?:\\?/){2})[^\s/?#"':\\]+@''', re.IGNORECASE), r'\1uSeR@'),
    (re.compile(r'''(\bbearer\s+)[^\s"']+''', re.IGNORECASE), r'\1' + SECRET_MASK),
    # Argument de la ligne de commande du démon
    (re.compile(r'(--apikey\s+)\S+'), r'\1' + SECRET_MASK),
    # Clé API, token ou mot de passe dans un message (JSON, dict Python, paramètre d'URL, texte saisi : commande ADB Shell,
    # commande personnalisée, lien d'appli), avec ou sans guillemets
    (re.compile(r'''(["']?\b(?:apikey|api_key|token|access_token|refresh_token|accessToken|refreshToken|client_secret|clientSecret|password|passwd|pass|pwd)\b["']?\s*[:=]\s*["']?)[^"'&\s,}]+''', re.IGNORECASE), r'\1' + SECRET_MASK),
]


def maskSecrets(text: str) -> str:
    """Texte avec les secrets masqués (clé API, tokens, mots de passe, identifiants d'URL) : pour un log, ou tout texte qui peut en contenir"""
    for pattern, repl in _SECRET_RULES:
        text = pattern.sub(repl, text)
    return text


class SecretMaskFilter(logging.Filter):
    """Masque en direct, avec maskSecrets(), les secrets pouvant apparaître dans les logs du démon ou de bibliothèques
    tierces : les logs sont lisibles par d'autres (support, agents IA)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True  # Message mal formé : laissé au handler, qui signale l'erreur de formatage
        redacted = maskSecrets(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        if record.exc_info:
            # Le texte de l'exception n'est produit qu'au formatage, après les filtres : il est généré ici pour être masqué
            # (le Formatter réutilise exc_text s'il est déjà renseigné)
            if not record.exc_text:
                record.exc_text = logging.Formatter().formatException(record.exc_info)
            record.exc_text = maskSecrets(record.exc_text)
        if record.stack_info:
            record.stack_info = maskSecrets(record.stack_info)
        return True


class Utils():

    @staticmethod
    def convert_log_level(level='error'):
        """Niveau Jeedom vers niveau Python ; « Aucun » (none) et niveau inconnu : critical"""
        LEVELS = {'debug': logging.DEBUG,
                  'info': logging.INFO,
                  'notice': logging.WARNING,
                  'warning': logging.WARNING,
                  'error': logging.ERROR,
                  'critical': logging.CRITICAL,
                  'none': logging.CRITICAL}
        return LEVELS.get(level, logging.CRITICAL)

    @staticmethod
    def init_logger(level='error'):
        FORMAT = '[%(asctime)-15s][%(levelname)s] : %(message)s'
        logging.basicConfig(level=Utils.convert_log_level(level), format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
        # Installé avec le logger, avant toute ligne de log, toujours actif (indépendant des filtres de logs configurables)
        secretFilter = SecretMaskFilter()
        for logHandler in logging.root.handlers:
            logHandler.addFilter(secretFilter)

    @staticmethod
    def write_pid(path):
        pid = str(os.getpid())
        logging.debug("[PID] Writing PID %s to %s", pid, path)
        open(path, 'w').write("%s\n" % pid)
