class Config(object):
    def __init__(self, **kwargs):
        self._kwargs = kwargs

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
    def cyclefactor(self):
        return self._kwargs.get('cyclefactor', 1.0)