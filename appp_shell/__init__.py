"""
    :author: xtess16
"""
import logging.handlers
import os

from .routes import BusRoutes, BusRouteItem
from .stations import BusStations, BusStationItem

LOG_FOLDER = 'logs'
if not os.path.exists(LOG_FOLDER):
    os.mkdir(LOG_FOLDER)

LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)


LOGGER_FILE_HANDLER = logging.handlers.TimedRotatingFileHandler(
    os.path.join(LOG_FOLDER, 'main_log'), when='midnight'
)
LOGGER_FILE_HANDLER.setLevel(logging.DEBUG)
LOGGER_FILE_HANDLER.suffix = '%d-%m-%Y'
LOGGER_FILE_HANDLER.setFormatter(logging.Formatter(
    '[%(levelname)s]  (%(asctime)s)  ' +
    '%(filename)s(%(name)s):%(funcName)s:%(lineno)d' +
    ' -- Thread: %(threadName)s\n\t%(message)s'
))
LOGGER.addHandler(LOGGER_FILE_HANDLER)

LOGGER_STREAM_HANDLER = logging.StreamHandler()
LOGGER_STREAM_HANDLER.setLevel(logging.ERROR)

LOGGER.addHandler(LOGGER_STREAM_HANDLER)
