bot_group_id = 157126910
man_speed_km_h = 6
man_speed_meters_per_minute = man_speed_km_h*1000/60
max_distance_to_nearest_stations_meters = 400

min_radius = int(max_distance_to_nearest_stations_meters/2)
max_radius = int(max_distance_to_nearest_stations_meters)
message_for_first_station_selection = 'Выберите остановку ' + \
    'с которой хотите уехать\n' +\
    f'-Зеленым выделены остановки в радиусе {min_radius} метров от вас\n' + \
    '-Красным выделены остановки в радиусе ' + \
    f'{min_radius} - {max_radius} метров от вас'
message_for_station_schedule = 'Номера маршрутов и время прибытия\n' + \
    '-Зеленым выделены маршруты на которые вы успеваете\n' + \
    '-Красным выделены маршруты на которые вы не успеваете'
message_for_station_schedule_without_distance = \
    message_for_station_schedule[:message_for_station_schedule.index('\n')]
unknown_command = 'Отправьте геопозицию или выберите один из пунктов меню'
about_us_message = 'Разработчик: https://vk.com/id133801315\n' + \
    'Исходный код: https://github.com/xtess16/busnik'