import os
import re
import time
import unicodedata


class Config(object):
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        
        self.is_ending = False
        
        self.heartbeat_lasttime = int(time.time())
        
        self.scanmode = False
        self.scanmode_start = int(time.time())
        self.scan_pending = False
        self.scan_lasttime = int(time.time())
        
        self.resources_lastused = 0
        self.resources_lasttime = int(time.time())
        self.resources_firsttime = int(time.time())
        
        self.tasks = []
        self.known_hosts = []  # Hosts for AndroidTVRemote2
        self.known_hosts_adb = []  # Hosts for ADB
        self.remote_mac = []  # MAC addresses for AndroidTVRemote2
        self.remote_mac_adb = []  # MAC addresses for ADB
        self.remote_names = []  # Names for AndroidTVRemote2
        self.remote_names_adb = []  # Names for ADB
        
        self.remote_devices = {}  # Devices using AndroidTVRemote2 - key is MAC
        self.remote_devices_adb = {}  # Devices using ADB - key is MAC
        self.remote_zconf = None
        self.remote_listener = {}
        
        self.pairing_code = None
        
        self.key_mapping = {
            "power": "KEYCODE_POWER",
            # "power": "KEYCODE_TV_POWER",
            "power_on": "KEYCODE_POWER",
            "power_off": "KEYCODE_POWER",
            # "power_on": "KEYCODE_WAKEUP",
            # "power_off": "KEYCODE_SLEEP",
            "up": "DPAD_UP",
            "down": "DPAD_DOWN",
            "left": "DPAD_LEFT",
            "right": "DPAD_RIGHT",
            "center": "DPAD_CENTER",
            "volumedown": "KEYCODE_VOLUME_DOWN",
            "volumeup": "KEYCODE_VOLUME_UP",
            "back": "KEYCODE_BACK",
            "home": "KEYCODE_HOME",
            "menu": "KEYCODE_MENU",
            "tv": "KEYCODE_TV",
            "channel_up": "KEYCODE_CHANNEL_UP",
            "channel_down": "KEYCODE_CHANNEL_DOWN",
            "zero": "KEYCODE_0",
            "one": "KEYCODE_1",
            "two": "KEYCODE_2",
            "three": "KEYCODE_3",
            "four": "KEYCODE_4",
            "five": "KEYCODE_5",
            "six": "KEYCODE_6",
            "seven": "KEYCODE_7",
            "eight": "KEYCODE_8",
            "nine": "KEYCODE_9",
            "info": "KEYCODE_INFO",
            "mute_on": "KEYCODE_VOLUME_MUTE",
            "mute_off": "KEYCODE_VOLUME_MUTE",
            "settings": "KEYCODE_SETTINGS",
            "input": "KEYCODE_TV_INPUT",
            "hdmi_1": "KEYCODE_TV_INPUT_HDMI_1",
            "hdmi_2": "KEYCODE_TV_INPUT_HDMI_2",
            "hdmi_3": "KEYCODE_TV_INPUT_HDMI_3",
            "hdmi_4": "KEYCODE_TV_INPUT_HDMI_4",
            "media_next": "KEYCODE_MEDIA_NEXT",
            "media_stop": "KEYCODE_MEDIA_STOP",
            "media_pause": "KEYCODE_MEDIA_PAUSE",
            "media_play": "KEYCODE_MEDIA_PLAY",
            "media_rewind": "KEYCODE_MEDIA_REWIND",
            "media_forward": "KEYCODE_MEDIA_FAST_FORWARD",
            "media_previous": "KEYCODE_MEDIA_PREVIOUS",
            "media_eject": "KEYCODE_MEDIA_EJECT",
            "oqee": "https://oq.ee/home/",
            "youtube": "https://www.youtube.com",
            "netflix": "https://www.netflix.com/title",
            "primevideo": "https://app.primevideo.com",
            "disneyplus": "https://www.disneyplus.com",
            "canaplus": "https://www.canalplus.com",
            "mycanal": "com.canal.android.canal",
            "appletv": "https://tv.apple.com",
            "twitch": "twitch://home",
            "plex": "plex://",
            "spotify": "spotify://",
            "molotov": "tv.molotov.app",
            "orangetv": "com.orange.owtv.tv",
            "vlc": "vlc://",
            "deezer": "https://www.deezer.com",
            "tunein": "https://tunein.com",
            "music": "https://music.youtube.com"
        }
        
    @property
    def plugin_version(self):
        return self._kwargs.get('pluginversion', '0.0.0')
        
    @property
    def callback_url(self):
        return self._kwargs.get('callback', '')

    @property
    def socket_host(self):
        return self._kwargs.get('sockethost', '127.0.0.1')

    @property
    def socket_port(self):
        return int(self._kwargs.get('socketport', 55112))

    @property
    def log_level(self):
        return self._kwargs.get('loglevel', 'error')

    @property
    def api_key(self):
        return self._kwargs.get('apikey', '')

    @property
    def pid_filename(self):
        return self._kwargs.get('pid', '/tmp/tvremoted.pid')

    @property
    def cycle_factor(self):
        return float(self._kwargs.get('cyclefactor', 1.0))
    
    @property
    def client_name(self):
        # Sanitize jeedom name: normalize accents, keep only alphanumeric, hyphens, underscores
        jeedom_name = self._kwargs.get('jeedomname', 'Jeedom').strip()
        # Normalize accents (é -> e, ç -> c, etc.)
        normalized = unicodedata.normalize('NFKD', jeedom_name).encode('ASCII', 'ignore').decode('ASCII')
        # Replace invalid characters with underscore
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', normalized) or 'Jeedom'
        return f"Plugin TVRemote :: {safe_name}"
    
    @property
    def cycle_event(self):
        return 0.5
    
    @property
    def cycle_comm(self):
        return 0.5
    
    @property
    def cycle_main(self):
        return 2.0
    
    @property
    def heartbeat_frequency(self):
        return 600
    
    @property
    def scanmode_timeout(self):
        return 60
    
    @property
    def scan_timeout(self):
        return 10
    
    @property
    def scan_schedule(self):
        return 60
    
    @property
    def pairing_timeout(self):
        return 300
    
    @property
    def cert_filepath(self):
        return 'data/config/tvremote_cert.pem'
    
    @property
    def cert_file(self):
        return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), self.cert_filepath))
    
    @property
    def key_filepath(self):
        return 'data/config/tvremote_key.pem'
    
    @property
    def key_file(self):
        return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), self.key_filepath))
    
    @property
    def adb_key_filepath(self):
        return 'data/config/adbkey'
    
    @property
    def adb_key_file(self):
        return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), self.adb_key_filepath))
    
    @property
    def adb_pub_filepath(self):
        return 'data/config/adbkey.pub'
    
    @property
    def adb_pub_file(self):
        return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), self.adb_pub_filepath))
    
    @property
    def adb_timeout(self):
        return 30
    
    @property
    def adb_auth_timeout(self):
        return 60