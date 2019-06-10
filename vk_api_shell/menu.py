from __future__ import annotations

import json
import logging
import time
from functools import wraps
from typing import Optional

from vk_api.bot_longpoll import VkBotMessageEvent
from vk_api.keyboard import VkKeyboardColor, VkKeyboard

from appp_shell import BusStationItem
from db_classes import UsersActions, PopularStations, RecentStations
from . import config

logger = logging.getLogger(__name__)
payload_handlers = {}


def hash_func(func):
    return hex(hash(func.__name__))[2:]


def show_elapsed_time(text=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            res = func(*args, **kwargs)
            finish = time.monotonic() - start
            logger.debug('{} - {} sec'.format(
                text or func.__name__, finish
            ))
            return res
        return wrapper
    return decorator


def payload_handler(func):
    payload_handlers[hash_func(func)] = func.__name__
    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


def context_handler(add_menu_button=False):
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
    def __init__(self, spider):
        self.__spider = spider

    @show_elapsed_time('Обработка гео')
    @context_handler(add_menu_button=True)
    def got_message_with_geo(self, event: VkBotMessageEvent) -> dict:
        logger.debug('Сообщение с геопозицией')
        latitude: float = event.obj.geo['coordinates']['latitude']
        longitude: float = event.obj.geo['coordinates']['longitude']
        tmp_nearest_stations: list[BusStationItem, tuple[float, float]] = \
            self.__spider.stations.all_stations_by_coords(
                (latitude, longitude),
                config.max_distance_to_nearest_stations_meters,
                with_distance=True, sort=True
            )
        nearest_stations = {}
        # TODO добавить обработку конечной станции
        for station, distance in tmp_nearest_stations:
            nearest_stations.setdefault(station.name, {
                'sids': {},
            })
            nearest_stations[station.name]['sids'][station.sid] = \
                [x.name for x in station.next_stations]
            nearest_stations[station.name]['distance'] = distance

        context = {}
        if nearest_stations:
            keyboard = VkKeyboard()
            for station_name in nearest_stations:
                station = nearest_stations[station_name]
                btn_text = station_name
                if station['distance'] <= config.min_radius:
                    btn_color = VkKeyboardColor.POSITIVE
                else:
                    btn_color = VkKeyboardColor.NEGATIVE

                btn_payload = {
                    'type': hash_func(self.get_second_stations_page),
                    'data': {
                        'next_stations': station['sids'],
                        'distance': station['distance']
                    }
                }
                keyboard.add_button(
                    btn_text, btn_color, btn_payload
                )
                keyboard.add_line()

            context['message'] = config.message_for_first_station_selection
            context['keyboard'] = keyboard
        else:
            context['message'] = 'Рядом нет остановок'
        context['peer_id'] = event.obj.from_id
        return context

    @show_elapsed_time('Обработка payload')
    def got_message_with_payload(self, event: VkBotMessageEvent) -> dict:
        payload: dict = json.loads(event.obj.payload)
        hash_function = payload['type']
        if hash_function == 'main_menu':
            hash_function = hash_func(self.get_main_menu_page)
        elif hash_function == 'pass':
            return {}
        context = self.__getattribute__(payload_handlers[hash_function])(event)
        return context

    @context_handler()
    def got_unknown_message(self, event):
        context = {
            'message': config.unknown_command,
            'peer_id': event.obj.from_id
        }
        return context

    @context_handler(add_menu_button=True)
    @payload_handler
    def get_second_stations_page(self, event):
        payload = json.loads(event.obj.payload)
        keyboard = VkKeyboard()
        # TODO
        # have_last_station = all([
        #     i['sids'] for i in payload['data']['next_stations']['sids']
        # ])
        next_stations_names = []
        if payload['data']['next_stations']:
            for sid in payload['data']['next_stations']:
                for next_station in payload['data']['next_stations'][sid]:
                    if next_station in next_stations_names:
                        continue
                    btn_text = next_station
                    next_stations_names.append(next_station)
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
        else:
            keyboard.add_button(
                'Конечная', VkKeyboardColor.POSITIVE, payload={
                    'type': hash_func(self.get_schedule_for_station_page),
                    'data': {
                        'sid': payload['data']['sid']
                    }
                })
            keyboard.add_line()
        context = {
            'message': 'Выберите остановку, следующую после вашей',
            'peer_id': event.obj.from_id,
            'keyboard': keyboard
        }
        return context

    @context_handler(add_menu_button=True)
    @payload_handler
    def get_schedule_for_station_page(self, event):
        payload = json.loads(event.obj.payload)
        cursor = self.__spider.db_session()
        cursor.add(
            UsersActions(
                peer_id=event.obj.from_id,
                action_type='got_schedule',
                data={
                    'sid': payload['data']['sid']
                }
            )
        )
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
                    arrival_time * config.man_speed_meters_per_minute
                max_distance_to_station += config.man_speed_meters_per_minute/2
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
            message = config.message_for_station_schedule_without_distance
        else:
            message = config.message_for_station_schedule
        context = {
            'message': message,
            'keyboard': keyboard,
            'peer_id': event.obj.from_id
        }
        return context

    @context_handler()
    @payload_handler
    def get_main_menu_page(self, event):
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
    def get_recent_stations_page(self, event):
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
    def get_popular_stations(self, event):
        cursor = self.__spider.db_session()
        popular_stations_table = cursor.query(PopularStations)
        popular_stations = popular_stations_table.order_by(
            PopularStations.call_count
        )[-5:]

        keyboard = VkKeyboard()
        if popular_stations:
            for popular_station in popular_stations:
                keyboard.add_button(
                    self.__spider.stations[popular_station.sid],
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
    def get_about_us_page(self, event):
        context = {
            'message': config.about_us_message,
            'peer_id': event.obj.from_id,
        }
        return context

