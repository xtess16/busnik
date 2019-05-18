from __future__ import annotations

import json
import logging
import time
import traceback
from typing import Union, Callable

import requests
import vk_api
from haversine import haversine, Unit
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.bot_longpoll import VkBotMessageEvent
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import sjson_dumps

from appp_shell.stations import BusStationItem
from . import config

logger = logging.getLogger(__name__)


def show_elapsed_time(func: Callable):
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        res = func(*args, **kwargs)
        finish = time.monotonic() - start
        logger.debug('{} - {} sec'.format(
            func.__name__, finish
        ))
        return res
    return wrapper


class Bot:
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
            self._got_message_with_geo(event)
        elif event.obj.payload is not None:
            self._got_message_with_payload(event)

    @show_elapsed_time
    def _got_message_with_geo(self, event: VkBotMessageEvent) -> None:
        logger.debug('Сообщение с геопозицией')
        latitude: float = event.obj.geo['coordinates']['latitude']
        longitude: float = event.obj.geo['coordinates']['longitude']
        nearest_stations = {}
        for station in self.__spider.stations.get_all_without_none_coords():
            distance: float = haversine(
                (latitude, longitude), station.coords, Unit.METERS
            )
            if distance <= 350:
                if station.name in nearest_stations:
                    nearest_stations[
                        station.name]['objects'].append(station)
                else:
                    nearest_stations[station.name] = {
                        'distance': distance,
                        'objects': [station, ]
                    }
        context = {}
        if nearest_stations:
            keyboard = VkKeyboard()
            nearest_stations_items: list[tuple[str, dict]] = sorted(
                nearest_stations.items(),
                key=lambda x: x[1]['distance']
            )
            for station_name, station_info in nearest_stations_items:
                btn_text = f'{station_name}'
                btn_color = VkKeyboardColor.POSITIVE
                btn_payload_sids: list[str] = \
                    [st.sid for st in station_info['objects']]
                btn_payload = {
                    'type': 'station_next_station',
                    'data': {
                        'sids': btn_payload_sids,
                        'distance': station_info['distance']
                    }
                }
                keyboard.add_button(
                    btn_text, btn_color, btn_payload
                )
                keyboard.add_line()

            context['message'] = 'Остановки рядом:'
            context['keyboard'] = self.__delete_all_empty_line_from_keyboard(
                keyboard.get_keyboard()
            )
        else:
            context['message'] = 'Рядом нет остановок'
        context['peer_id'] = event.obj.from_id
        context['random_id'] = int(time.time()*1000000)
        self.__vk.method('messages.send', context)

    @show_elapsed_time
    def _got_message_with_payload(self, event: VkBotMessageEvent) -> None:
        payload: dict = json.loads(event.obj.payload)
        if payload['type'] == 'station_next_station':
            keyboard = VkKeyboard()
            for sid in payload['data']['sids']:
                station = self.__spider.stations.get_station_by_sid(sid)
                next_station = station.next_station
                if next_station is not None:
                    btn_text = next_station.name
                else:
                    btn_text = 'Конечная'
                btn_color = VkKeyboardColor.POSITIVE
                btn_payload = {
                    'type': 'station_schedule',
                    'data': {
                        'sid': station.sid,
                        'distance': payload['data']['distance']
                    }
                }
                keyboard.add_button(
                    btn_text, btn_color, btn_payload
                )
                keyboard.add_line()
            self.__vk.method('messages.send', {
                'message': 'Выберите остановку, следующую после вашей',
                'random_id': time.time()*1000000,
                'peer_id': event.obj.from_id,
                'keyboard': self.__delete_all_empty_line_from_keyboard(
                    keyboard.get_keyboard()
                )
            })
        elif payload['type'] == 'station_schedule':
            keyboard = VkKeyboard()
            station: BusStationItem = \
                self.__spider.stations.get_station_by_sid(
                    payload['data']['sid']
                )
            distance_to_station: float = payload['data']['distance']
            schedule: dict = station.schedule
            if schedule:
                btn_count = 0
                for sch in station.schedule[:19]:
                    route_name: str = sch['route_name']
                    arrival_time: int = sch['arrival_time']
                    max_distance_to_station: float = \
                        arrival_time * config.man_speed_meters_per_minute
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
                keyboard = self.__delete_all_empty_line_from_keyboard(
                    keyboard.get_keyboard()
                )
            else:
                keyboard.add_button(
                    'Автобусов пока нет', VkKeyboardColor.POSITIVE
                )
                keyboard = keyboard.get_keyboard()
            self.__vk.method('messages.send', {
                'message': 'Список автобусов, которые скоро прибудут',
                'random_id': time.time() * 1000000,
                'peer_id': event.obj.from_id,
                'keyboard': keyboard
            })

    def __delete_all_empty_line_from_keyboard(
            self, keyboard: str) -> dict:
        keyboard: dict = json.loads(keyboard)
        while [] in keyboard['buttons']:
            keyboard['buttons'].remove([])
        return sjson_dumps(keyboard)
