"""
    :author: xtess16
"""
import logging.handlers
import os

ROUTE_SELECTION_LINK = 'http://appp29.ru/mobile/op.php'
ROUTE_SELECTION_PARAMS = {
    'city': 'arhangelsk',
    'page': 'routes',
    'rt': 'А'
}
PATH_TO_DB = os.path.join('data', 'main_db.sqlite')


def create_logger(logger_name: str) -> logging.Logger:
    """
        Создает логгер для пакетов
    :param logger_name: Имя логгера
    :return: Логгер-объект через который будут вестись логи
    """

    log_folder = 'logs'
    if not os.path.exists(log_folder):
        os.mkdir(log_folder)
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)

    logger_file_handler = logging.handlers.TimedRotatingFileHandler(
        os.path.join(log_folder, 'main_log'), when='midnight'
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
    return logger
