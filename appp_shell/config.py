"""
    :author: xtess16
"""
import os
import re

ROUTE_STATIONS_LINK = 'http://appp29.ru/mobile/op.php'
ROUTE_STATIONS_PARAMS = {
    'city': 'arhangelsk',
    'page': 'stations',
    'rid': None,
    'rt': 'A'
}

STATION_LINK = 'http://appp29.ru/mobile/{}'
ROUTE_NAME_REG_EXPR = re.compile(r'№\s*([\d\w]+).*?\((.+)\s+-\s+(.+)\)', re.I)

REPLACE_STATION_NAMES_DICTIONARY = {
    'Урицкого-Обводный': 'пр. Обводный канал',
    'Поликлиника': 'Поликлиника №3',
    'ул. Розы Люксенбург': 'ул. Розы Люксембург',
    'Тимме-Воскресенская': 'ул. Тимме-Воскресенская',
    'Ленинградский проспект д.350': 'пр. Ленинградский, 350'
}


def replace_station_name(name: str) -> str:
    """
        Получение имени, измененного в соответствие со словарем
    :param name:
    """
    return REPLACE_STATION_NAMES_DICTIONARY.get(name, name)


BUS_STATIONS_CSV_PATH = os.path.join('data', 'bus_stations.csv')

REG_EXPR_FOR_STID = re.compile(r'stid=(\d+)')
