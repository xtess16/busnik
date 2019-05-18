import logging.handlers
import os

LOG_FOLDER = 'logs'
if not os.path.exists(LOG_FOLDER):
    os.mkdir(LOG_FOLDER)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


logger_file_handler = logging.handlers.TimedRotatingFileHandler(
    os.path.join(LOG_FOLDER, 'main_log'), when='midnight'
)
logger_file_handler.setLevel(logging.DEBUG)
logger_file_handler.suffix = '%d-%m-%Y'
logger_file_handler.setFormatter(logging.Formatter(
    '[%(levelname)s]  (%(asctime)s)  ' +
    '%(filename)s(%(name)s):%(funcName)s:%(lineno)d' +
    ' -- Thread: %(threadName)s\n\t%(message)s'
))
logger.addHandler(logger_file_handler)

logger_stream_handler = logging.StreamHandler()
logger_stream_handler.setLevel(logging.ERROR)

logger.addHandler(logger_stream_handler)
