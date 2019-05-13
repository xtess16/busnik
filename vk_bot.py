import getpass
import time
from typing import Union

from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType, VkBotEvent, \
    VkBotMessageEvent
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import vk_api
import config
from haversine import haversine, Unit
from appp_shell import BusStationItem
import keyring


class Bot:
    __vk: vk_api.VkApi
    __longpoll: VkBotLongPoll

    def __init__(self, spider):
        self.__spider = spider

    def auth(self, token):
        try:
            self.__vk = vk_api.VkApi(token=token)
            self.__longpoll = VkBotLongPoll(self.__vk, config.bot_group_id)
        except vk_api.exceptions.ApiError as e:
            if '[5]' in str(e):
                print('ERROR:', e)
                return False
        else:
            print('Authorized')
            return True

    def longpoll_listen(self):
        for event in self.__longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                self._new_message(event)

    def _new_message(self, event):
        if event.obj.geo is not None:
            self._got_message_with_geo(event)

    def _got_message_with_geo(self, event):
        latitude = event.obj.geo['coordinates']['latitude']
        longitude = event.obj.geo['coordinates']['longitude']
        nearest_stations = []
        for station in self.__spider.stations.get_all_without_none_coords():
            distance = haversine(
                (latitude, longitude), station.coords, Unit.METERS
            )
            if distance <= 350:
                nearest_stations.append([station, distance])

        if nearest_stations:
            message = []
            for station, distance in nearest_stations:
                if station.next_station == BusStationItem.LAST_STATION:
                    message.append(f'{station.name} (Конечная)')
                else:
                    message.append(
                        f'{station.name} --> {station.next_station.name}'
                    )
                if station.schedule:
                    for route in station.schedule:
                        message.append(
                            f'---№{route["route_name"]} через {route["arrival_time"]} мин.'
                        )
                else:
                    message.append('---На данный момент автобусов нет')
            message = '\n'.join(message)
        else:
            message = 'Рядом нет остановок'
        self.__vk.method('messages.send', {
            'peer_id': event.obj.peer_id,
            'message': message,
            'random_id': int(time.time()*1000000)
        })
