import os
import time


class Config(object):
    def __init__(self, **kwargs):
        self._kwargs = kwargs
        
        self.heartbeat_lasttime = int(time.time())
        
        self.scanmode = False
        self.scanmode_start = int(time.time())
        self.scan_pending = False
        self.scan_lasttime = int(time.time())
        
        self.resources_lastused = 0
        self.resources_lasttime = int(time.time())
        self.resources_firsttime = int(time.time())
        
    @property
    def callback_url(self):
        return self._kwargs.get('callback', '')

    @property
    def socket_host(self):
        return self._kwargs.get('sockethost', '127.0.0.1')

    @property
    def socket_port(self):
        return self._kwargs.get('socketport', 55112)

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
        return self._kwargs.get('cyclefactor', 1.0)
    
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
        return 30
    
    @property
    def scanmode_timeout(self):
        return 60
    
    @property
    def scan_timemout(self):
        return 10
    
    @property
    def scan_schedule(self):
        return 60
    
    @property
    def config_folder(self):
        return 'data/config'
    
    @property
    def config_fullpath(self):
        return os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), self.config_folder))
    