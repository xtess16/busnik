from __future__ import annotations

import json
import logging
import time
import traceback
from typing import Union

import requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.bot_longpoll import VkBotMessageEvent
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import sjson_dumps

from appp_shell.stations import BusStationItem
from . import exceptions, config

logger = logging.getLogger(__name__)
methods_by_types = {}


def show_elapsed_time(text=None):
    def decorator(func):
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


def call_method_by_payload_type(payload_type):
    def decorator(func):
        if payload_type not in methods_by_types:
            methods_by_types[payload_type] = func
        else:
            raise exceptions.PayloadTypeError(
                payload_type+' уже определен')

        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


def add_main_menu_button(func):
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        if 'keyboard' in res:
            res['keyboard'].add_button(
                'Главное меню', VkKeyboardColor.PRIMARY,
                payload={
                    'type': 'main_menu'
                }
            )
        return res
    return wrapper


class Bot:
    """
        params spider
        # TODO
    """
    def __init__(self, spider):
        logger.info(self.__class__.__name__ + ' инициализируется')
        self.__spider = spider
        self.__vk: Union[vk_api.VkApi, None] = None
        self.__longpoll: Union[VkBotLongPoll, None] = None
        logger.info(self.__class__.__name__ + ' инициализирован')

    def auth(self, token: str) -> bool:
        logger.info('Авторизация')
        try:
            self.__vk = vk_api.VkApi(token=token)
            self.__longpoll = VkBotLongPoll(self.__vk, config.bot_group_id)
        except vk_api.exceptions.ApiError as e:
            # Авторизация не удалась
            if '[5]' in str(e):
                logger.error(
                    'Авторизация не удалась: ' + str(e)
                )
                return False
            else:
                logger.critical(
                    'Неизвестная ошибка: ' + traceback.format_exc()
                )
        except Exception:
            logger.critical(
                'Неизвестная ошибка: ' + traceback.format_exc()
            )
        else:
            logger.info('Авторизован')
            print('Авторизован')
            return True

    def longpoll_listen(self) -> None:
        logger.info('Подключение к лонгпулл серверу')
        while True:
            try:
                for event in self.__longpoll.listen():
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        self._new_message(event)
            except requests.exceptions.ReadTimeout as e:
                logger.warning(str(e))

    def _new_message(self, event: VkBotMessageEvent) -> None:
        logger.debug('Новое сообщение ' + str(event))
        if event.obj.geo is not None:
            context: dict = self._got_message_with_geo(event)
        elif event.obj.payload is not None:
            context: dict = self._got_message_with_payload(event)
        else:
            context = {
                'message': config.unknown_command,
                'peer_id': event.obj.from_id
            }
        if 'keyboard' in context:
            context['keyboard'] = context['keyboard'].get_keyboard()
        context['random_id'] = int(time.time()*1000000)
        self.__vk.method('messages.send', context)

    @show_elapsed_time('Обработка гео')
    @add_main_menu_button
    def _got_message_with_geo(self, event: VkBotMessageEvent) -> dict:
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
                    'type': 'select_second_station',
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
    @add_main_menu_button
    def _got_message_with_payload(self, event: VkBotMessageEvent) -> dict:
        payload: dict = json.loads(event.obj.payload)
        context = methods_by_types[payload['type']](self, event)
        return context

    @call_method_by_payload_type('select_second_station')
    def _get_second_stations(self, event):
        payload = json.loads(event.obj.payload)
        keyboard = VkKeyboard()
        # TODO
        # have_last_station = all([
        #     i['sids'] for i in payload['data']['next_stations']['sids']
        # ])
        if payload['data']['next_stations']:
            for sid in payload['data']['next_stations']:
                for next_station in payload['data']['next_stations'][sid]:
                    btn_text = next_station
                    btn_color = VkKeyboardColor.POSITIVE
                    btn_payload = {
                        'type': 'station_schedule',
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
                    'type': 'station_schedule',
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

    @call_method_by_payload_type('station_schedule')
    def _get_schedule_for_station(self, event):
        payload = json.loads(event.obj.payload)
        keyboard = VkKeyboard()
        station: BusStationItem = \
            self.__spider.stations[payload['data']['sid']]
        distance_to_station: float = payload['data']['distance']
        schedule: list = station.schedule
        if schedule:
            btn_count = 0
            for sch in schedule[:19]:
                route_name: str = sch['route_name']
                arrival_time: int = sch['arrival_time']
                max_distance_to_station: float = \
                    arrival_time * config.man_speed_meters_per_minute
                max_distance_to_station += config.man_speed_meters_per_minute/2
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
        context = {
            'message': config.message_for_station_schedule,
            'keyboard': keyboard,
            'peer_id': event.obj.from_id
        }
        return context

    @call_method_by_payload_type('main_menu')
    def _get_main_menu(self, _):
        keyboard = VkKeyboard()
        keyboard.add_button(
            'Последние остановки', VkKeyboardColor.POSITIVE,
            payload={
                'type': 'recent_stations'
            }
        )
        keyboard.add_line()
        keyboard.add_button(
            'О нас', VkKeyboardColor.POSITIVE,
            payload={
                'type': 'about_us'
            }
        )
        context = {
            'message': 'Главное меню',
            'keyboard': keyboard
        }
        return context

    def __delete_all_empty_line_from_keyboard(
            self, keyboard: str) -> dict:
        keyboard: dict = json.loads(keyboard)
        while [] in keyboard['buttons']:
            keyboard['buttons'].remove([])
        return sjson_dumps(keyboard)
