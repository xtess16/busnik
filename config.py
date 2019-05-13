import re

headers = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 7.1; Mi A1 Build/N2G47H)'
}


route_selection_link = 'http://appp29.ru/mobile/op.php'
route_selection_params = {
    'city': 'arhangelsk',
    'page': 'routes',
    'rt': 'А'
}


route_stations_link = 'http://appp29.ru/mobile/op.php'
route_stations_params = {
    'city': 'arhangelsk',
    'page': 'stations',
    'rid': None,
    'rt': 'A'
}

station_link = 'http://appp29.ru/mobile/{}'

route_name_reg_expr = re.compile(r'№\s*([\d\w]+).*?\((.+)\s+-\s+(.+)\)', re.I)

replace_station_names = {
    'Урицкого-Обводный': 'пр. Обводный канал',
    'Поликлиника': 'Поликлиника №3',
    'ул. Розы Люксенбург': 'ул. Розы Люксембург',
    'Тимме-Воскресенская': 'ул. Тимме-Воскресенская',
    'Ленинградский проспект д.350': 'пр. Ленинградский, 350'
}

bot_group_id = 157126910
