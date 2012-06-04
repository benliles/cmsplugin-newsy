from logging import getLogger

try:
    from logging import NullHandler
except ImportError:
    from logging import Handler
    class NullHandler(Handler):
        def emit(self, record):
            pass

getLogger('newsy').addHandler(NullHandler())

import newsy.signals

