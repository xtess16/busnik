import os
import re

route_stations_link = 'http://appp29.ru/mobile/op.php'
route_stations_params = {
    'city': 'arhangelsk',
    'page': 'stations',
    'rid': None,
    'rt': 'A'
}

station_link = 'http://appp29.ru/mobile/{}'
route_name_reg_expr = re.compile(r'№\s*([\d\w]+).*?\((.+)\s+-\s+(.+)\)', re.I)

replace_station_names_dictionary = {
    'Урицкого-Обводный': 'пр. Обводный канал',
    'Поликлиника': 'Поликлиника №3',
    'ул. Розы Люксенбург': 'ул. Розы Люксембург',
    'Тимме-Воскресенская': 'ул. Тимме-Воскресенская',
    'Ленинградский проспект д.350': 'пр. Ленинградский, 350'
}


def replace_station_name(name):
    return replace_station_names_dictionary.get(name, name)


bus_stations_csv_path = os.path.join('data', 'bus_stations.csv')

reg_expr_for_stid = re.compile(r'stid=(\d+)')
