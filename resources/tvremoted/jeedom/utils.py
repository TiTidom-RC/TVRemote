import logging
import os

class Utils():

    @staticmethod
    def convert_log_level(level='error'):
        LEVELS = {'debug': logging.DEBUG,
                  'info': logging.INFO,
                  'notice': logging.WARNING,
                  'warning': logging.WARNING,
                  'error': logging.ERROR,
                  'critical': logging.CRITICAL,
                  'none': logging.NOTSET}
        return LEVELS.get(level, logging.NOTSET)

    @staticmethod
    def init_logger(level='error'):
        FORMAT = '[%(asctime)-15s][%(levelname)s] : %(message)s'
        logging.basicConfig(level=Utils.convert_log_level(level), format=FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    @staticmethod
    def write_pid(path):
        pid = str(os.getpid())
        logging.debug("Writing PID %s to %s", pid, path)
        open(path, 'w').write("%s\n" % pid)
