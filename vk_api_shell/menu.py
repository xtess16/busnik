"""
    :author: xtess16
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from functools import wraps
from typing import Optional, Any, Dict, List, Tuple, Callable, Union

from vk_api.bot_longpoll import VkBotMessageEvent
from vk_api.keyboard import VkKeyboardColor, VkKeyboard

from appp_shell import BusStationItem
from core import Spider
from db_classes import PopularStations, RecentStations
from . import config

LOGGER = logging.getLogger(__name__)
PAYLOAD_HANDLERS = {}

ContextType = Dict[str, Any]


def hash_func(func: Callable) -> str:
    """
        Кодирует имя функции в md5, для дальнейшего вызова через handler
    :param func: Функция, имя которой надо закодировать
    :return: md5 хэш имени функции
    """
    _hash = hashlib.md5(func.__name__.encode()).hexdigest()
    return _hash


def show_elapsed_time(text: Optional[str] = None) -> Callable:
    """
        Декоратор для подсчета времени работы функции
    :param text: Дополнительный текст для записи в лог
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            res = func(*args, **kwargs)
            finish = time.monotonic() - start
            LOGGER.debug('%s - %s sec', text or func.__name__, finish)
            return res
        return wrapper
    return decorator


def payload_handler(func: Callable) -> Callable:
    """
        Декоратор, нужен для передачи handler-функции в payload vk api
    :param func: Функция handler - явялется обработчиком событий с payload
    """
    PAYLOAD_HANDLERS[hash_func(func)] = func.__name__
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def context_handler(add_menu_button=False) -> Callable:
    """
        Декоратор, производит необходимые операции с результатами работы
        функций, которые возвращают context для отсылки vk api
    :param add_menu_button: Если True, добавляет к клавиатуре кнопку для
        выхода в главное меню
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            context = func(*args, **kwargs)
            if 'keyboard' in context:
                if add_menu_button:
                    context['keyboard'].add_button(
                        'Главное меню', VkKeyboardColor.PRIMARY,
                        payload={
                            'type': 'main_menu'
                        }
                    )
                context['keyboard'] = context['keyboard'].get_keyboard()
            context['random_id'] = int(time.time()*1000000)
            return context
        return wrapper
    return decorator


class Menu:
    """
        Класс содержит в себе методы для обработки запросов,
        отправляемых пользователем
    """

    def __init__(self, spider: Spider):
        """
            Инициализатор
        :param spider: Класс, соединяющий бота в вк и парсера,
            через него происходит взаимодействие со станциями и маршрутами
        """
        self.__spider = spider

    @show_elapsed_time('Обработка гео')
    @context_handler(add_menu_button=True)
    def got_message_with_geo(self, event: VkBotMessageEvent) -> ContextType:
        """
            При получении геопозиции вызвается этот метод
        :param event: Событие полученное от лонгпулла
        """

        LOGGER.debug('Сообщение с геопозицией')

        def _get_nearest_stations(
                coords: Tuple[float, float], radius: Union[float, int]) -> \
                Dict[str, Dict[str, Union[int, List[str]]]]:
            """
                Получение ближайших, к заданной точке, остановок
            :param coords: Широта и долгота
            :param radius: Радиус поиска остановки
            :return: Словарь, в котором ключ - название остановки, а
                значение словарь состоящий из дистанции до остановки и словаря,
                в котором ключ - уникальный идентификатор остановки,
                а значение - список имен последующих остановок
            """
            # Ближайшие к пользователю остановки
            tmp_nearest_stations: List[BusStationItem, Tuple[float, float]] = \
                self.__spider.stations.all_stations_by_coords(
                    coords, radius, with_distance=True, sort=True
                )
            res = {}
            # TODO добавить обработку конечной станции
            for station_item, distance in tmp_nearest_stations:
                res.setdefault(station_item.name, {
                    'sids': [],
                })
                res[station_item.name]['sids'].append(station_item.sid)
                res[station_item.name]['distance'] = distance
            return res

        # Широта и долгота места, отправленного пользователем
        latitude: float = event.obj.geo['coordinates']['latitude']
        longitude: float = event.obj.geo['coordinates']['longitude']

        nearest_stations = _get_nearest_stations(
            (latitude, longitude),
            config.MAX_DISTANCE_TO_NEAREST_STATIONS_METERS
        )
        context = {}
        if nearest_stations:
            keyboard = VkKeyboard()
            for station_name in nearest_stations:
                station = nearest_stations[station_name]
                btn_text = station_name
                if station['distance'] <= config.MIN_RADIUS:
                    btn_color = VkKeyboardColor.POSITIVE
                else:
                    btn_color = VkKeyboardColor.NEGATIVE

                btn_payload = {
                    'type': hash_func(self.get_second_stations_page),
                    'data': {
                        'nearest_stations': station['sids'],
                        'distance': station['distance']
                    }
                }
                keyboard.add_button(
                    btn_text, btn_color, btn_payload
                )
                keyboard.add_line()

            context['message'] = config.MESSAGE_FOR_FIRST_STATION_SELECTION
            context['keyboard'] = keyboard
        else:
            context['message'] = 'Рядом нет остановок'
        context['peer_id'] = event.obj.from_id
        return context

    @show_elapsed_time('Обработка payload')
    def got_message_with_payload(
            self, event: VkBotMessageEvent) -> ContextType:
        """
            Вызывается, когда пользователь нажал на какую-либо кнопку у бота
        :param event: Событие полученное от лонгпулла
        """
        payload: dict = json.loads(event.obj.payload)
        hash_function = payload['type']
        if hash_function == 'main_menu':
            hash_function = hash_func(self.get_main_menu_page)
        elif hash_function == 'pass':
            return {}
        context = self.__getattribute__(PAYLOAD_HANDLERS[hash_function])(event)
        return context

    @context_handler()
    def got_unknown_message(self, event: VkBotMessageEvent) -> ContextType:
        """
            Вызывается при получении неизвестной команды
        :param event: Событие полученное от лонгпулла
        :return: Возвращает context для отправки пользователю
        """
        context = {
            'message': config.UNKNOWN_COMMAND,
            'peer_id': event.obj.from_id
        }
        return context

    @context_handler(add_menu_button=True)
    @payload_handler
    def get_second_stations_page(
            self, event: VkBotMessageEvent) -> ContextType:
        """
            Обрабатывает выбор станции, следующей после необходимой,
            метод нужен для однозначного определения станции, для которой
            нужно будет получить расписание
        :param event: Событие, полученное от лонгпулла
        """

        payload = json.loads(event.obj.payload)
        keyboard = VkKeyboard()
        # TODO
        # have_last_station = all([
        #     i['sids'] for i in payload['data']['next_stations']['sids']
        # ])
        next_stations_names = []
        nearest_stations_sids = payload['data']['nearest_stations']
        for sid in nearest_stations_sids:
            near_station = self.__spider.stations[sid]
            for next_station in near_station.next_stations:
                if next_station.name.casefold() in \
                        map(str.casefold, next_stations_names):
                    continue
                btn_text = next_station.name
                next_stations_names.append(next_station.name)
                btn_color = VkKeyboardColor.POSITIVE
                btn_payload = {
                    'type': hash_func(
                        self.get_schedule_for_station_page
                    ),
                    'data': {
                        'sid': sid,
                        'distance': payload['data']['distance']
                    }
                }
                keyboard.add_button(
                    btn_text, btn_color, btn_payload
                )
                keyboard.add_line()
        context = {
            'message': 'Выберите остановку, следующую после вашей',
            'peer_id': event.obj.from_id,
            'keyboard': keyboard
        }
        return context

    @context_handler(add_menu_button=True)
    @payload_handler
    def get_schedule_for_station_page(
            self, event: VkBotMessageEvent) -> ContextType:
        """
            Получение страницы с расписанием маршрутов
        :param event: Событие, полученное от лонгпулла
        """
        payload = json.loads(event.obj.payload)
        cursor = self.__spider.db_session()
        popular_stations_table = cursor.query(PopularStations)
        current_station = popular_stations_table.filter(
            PopularStations.sid == payload['data']['sid']
        ).one_or_none()
        if current_station is None:
            cursor.add(
                PopularStations(
                    sid=payload['data']['sid'],
                    call_count=1
                )
            )
        else:
            current_station.call_count += 1

        recent_stations_table = cursor.query(RecentStations)
        current_user_recent_stations = recent_stations_table.filter(
            RecentStations.peer_id == event.obj.from_id
        ).one_or_none()
        if current_user_recent_stations is None:
            cursor.add(
                RecentStations(
                    peer_id=event.obj.from_id,
                    stations=[payload['data']['sid'], ]
                )
            )
        else:
            current_user_recent_stations.add(payload['data']['sid'])
        cursor.commit()
        cursor.close()

        keyboard = VkKeyboard()
        LOGGER.critical(payload['data']['sid'])
        station: BusStationItem = \
            self.__spider.stations[payload['data']['sid']]
        distance_to_station: Optional[float] = payload['data'].get('distance')
        schedule: list = station.schedule
        if schedule:
            btn_count = 0
            for sch in schedule[:18]:
                route_name: str = sch['route_name']
                arrival_time: int = sch['arrival_time']
                max_distance_to_station: float = \
                    arrival_time * config.MAN_SPEED_METERS_PER_MINUTE
                max_distance_to_station += config.MAN_SPEED_METERS_PER_MINUTE/2
                if distance_to_station is None:
                    have_time_to_station = True
                else:
                    have_time_to_station: bool = \
                        max_distance_to_station >= distance_to_station
                btn_text = f'№{route_name} через {arrival_time} мин'
                if have_time_to_station:
                    btn_color = VkKeyboardColor.POSITIVE
                else:
                    btn_color = VkKeyboardColor.NEGATIVE
                btn_payload: dict = {}
                keyboard.add_button(
                    btn_text, btn_color, btn_payload
                )
                btn_count += 1
                if btn_count % 2 == 0:
                    keyboard.add_line()
            if btn_count % 2 != 0:
                keyboard.add_line()

        else:
            keyboard.add_button(
                'Автобусов пока нет', VkKeyboardColor.POSITIVE
            )
            keyboard.add_line()
        keyboard.add_button(
            'Обновить', VkKeyboardColor.PRIMARY, payload
        )
        if distance_to_station is None:
            message = config.MESSAGE_FOR_STATION_SCHEDULE_WITHOUT_DISTANCE
        else:
            message = config.MESSAGE_FOR_STATION_SCHEDULE
        context = {
            'message': message,
            'keyboard': keyboard,
            'peer_id': event.obj.from_id
        }
        return context

    @context_handler()
    @payload_handler
    def get_main_menu_page(self, event: VkBotMessageEvent) -> ContextType:
        """
            Страница с главным меню
        :param event: Событие, полученное от лонгпулла
        """
        keyboard = VkKeyboard()
        keyboard.add_button(
            'Последние остановки', VkKeyboardColor.POSITIVE,
            payload={
                'type': hash_func(self.get_recent_stations_page),
                'data': {
                    'peer_id': event.obj.from_id
                }
            }
        )
        keyboard.add_line()
        keyboard.add_button(
            'Популярные остановки', VkKeyboardColor.POSITIVE,
            payload={
                'type': hash_func(self.get_popular_stations),
                'data': {}
            }
        )
        keyboard.add_line()
        keyboard.add_button(
            'О нас', VkKeyboardColor.POSITIVE,
            payload={
                'type': hash_func(self.get_about_us_page)
            }
        )
        context = {
            'message': 'Главное меню',
            'keyboard': keyboard,
            'peer_id': event.obj.from_id
        }
        return context

    @context_handler(add_menu_button=True)
    @payload_handler
    def get_recent_stations_page(
            self, event: VkBotMessageEvent) -> ContextType:
        """
            Страница с последними остановками, расписание которых
            запрашивал пользователь
        :param event: Событие, полученное от лонгпулла
        """
        cursor = self.__spider.db_session()
        recent_stations_table = cursor.query(RecentStations)
        current_user = recent_stations_table.filter(
            RecentStations.peer_id == event.obj.from_id
        ).one_or_none()
        keyboard = VkKeyboard()
        if current_user is None:
            keyboard.add_button(
                'У вас нет последних остановок',
                VkKeyboardColor.POSITIVE
            )
            keyboard.add_line()
        else:
            recent_stations = current_user.stations
            for station in recent_stations[::-1]:
                keyboard.add_button(
                    self.__spider.stations[station].name,
                    VkKeyboardColor.POSITIVE,
                    payload={
                        'type': hash_func(self.get_schedule_for_station_page),
                        'data': {
                            'sid': station
                        }
                    }
                )
                keyboard.add_line()
        cursor.close()
        context = {
            'message': 'Ваши последние остановки',
            'keyboard': keyboard,
            'peer_id': event.obj.from_id
        }
        return context

    @context_handler(add_menu_button=True)
    @payload_handler
    def get_popular_stations(self, event: VkBotMessageEvent) -> ContextType:
        """
            Страница с самыми популярными остановками(всех пользователей)
        :param event: Событие, полученное от лонгпулла
        """
        cursor = self.__spider.db_session()
        popular_stations_table = cursor.query(PopularStations)
        popular_stations = popular_stations_table.order_by(
            PopularStations.call_count
        )[-5:]

        keyboard = VkKeyboard()
        if popular_stations:
            for popular_station in popular_stations:
                keyboard.add_button(
                    self.__spider.stations[popular_station.sid].name,
                    VkKeyboardColor.POSITIVE,
                    payload={
                        'type': hash_func(self.get_schedule_for_station_page),
                        'data': {
                            'sid': popular_station.sid
                        }
                    }
                )
                keyboard.add_line()
        else:
            keyboard.add_button(
                'Популярных остановок нет',
                VkKeyboardColor.POSITIVE
            )
            keyboard.add_line()
        cursor.close()
        context = {
            'message': 'Популярные остановки',
            'keyboard': keyboard,
            'peer_id': event.obj.from_id
        }
        return context

    @context_handler(add_menu_button=True)
    @payload_handler
    def get_about_us_page(self, event: VkBotMessageEvent) -> ContextType:
        """
            Страница с информацие о разработчике
        :param event: Событие, полученное от лонгпулла
        """
        context = {
            'message': config.ABOUT_US_MESSAGE,
            'peer_id': event.obj.from_id,
        }
        return context
