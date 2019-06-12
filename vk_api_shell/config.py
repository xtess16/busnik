"""
    :author: xtess16
"""
BOT_GROUP_ID = 157126910
MAN_SPEED_KM_H = 6
MAN_SPEED_METERS_PER_MINUTE = MAN_SPEED_KM_H*1000/60
MAX_DISTANCE_TO_NEAREST_STATIONS_METERS = 400

MIN_RADIUS = int(MAX_DISTANCE_TO_NEAREST_STATIONS_METERS/2)
MAX_RADIUS = int(MAX_DISTANCE_TO_NEAREST_STATIONS_METERS)
MESSAGE_FOR_FIRST_STATION_SELECTION = 'Выберите остановку ' + \
    'с которой хотите уехать\n' +\
    f'-Зеленым выделены остановки в радиусе {MIN_RADIUS} метров от вас\n' + \
    '-Красным выделены остановки в радиусе ' + \
    f'{MIN_RADIUS} - {MAX_RADIUS} метров от вас'
MESSAGE_FOR_STATION_SCHEDULE = 'Номера маршрутов и время прибытия\n' + \
    '-Зеленым выделены маршруты на которые вы успеваете\n' + \
    '-Красным выделены маршруты на которые вы не успеваете'
MESSAGE_FOR_STATION_SCHEDULE_WITHOUT_DISTANCE = \
    MESSAGE_FOR_STATION_SCHEDULE[:MESSAGE_FOR_STATION_SCHEDULE.index('\n')]
UNKNOWN_COMMAND = 'Отправьте геопозицию или выберите один из пунктов меню'
ABOUT_US_MESSAGE = 'Разработчик: https://vk.com/id133801315\n' + \
    'Исходный код: https://github.com/xtess16/busnik'
