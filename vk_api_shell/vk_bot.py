"""
    :author: xtess16
"""
from __future__ import annotations

import logging
import traceback
from typing import Optional

import requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.bot_longpoll import VkBotMessageEvent

from . import menu, config

LOGGER = logging.getLogger(__name__)


class Bot:
    """
        Класс - "скелет" бота, авторизовывается в вк, отлавливает сообщение
        через лонгпулл и передает их на обработку классу Menu
    """

    def __init__(self, spider):
        """
            Инициализатор
        :param spider: Класс, соединяющий бота в вк и парсера,
            через него происходит взаимодействие со станциями и маршрутами
        """
        LOGGER.info('%s инициализируется', self.__class__.__name__)
        self.__spider = spider
        self.__vk: Optional[vk_api.VkApi] = None
        self.__longpoll: Optional[VkBotLongPoll] = None
        self.__menu_handler: menu.Menu = menu.Menu(self.__spider)
        LOGGER.info('%s инициализирован', self.__class__.__name__)

    def auth(self, token: str) -> bool:
        """
            Авторизация бота в вк
        :param token: Токен для авторизации
        :return: True/False в зависимости от успешности авторизации
        """

        LOGGER.info('Авторизация')
        try:
            self.__vk = vk_api.VkApi(token=token)
            self.__longpoll = VkBotLongPoll(self.__vk, config.BOT_GROUP_ID)
        except vk_api.exceptions.ApiError as error:
            # Авторизация не удалась
            if '[5]' in str(error):
                LOGGER.error('Авторизация не удалась: %s', str(error))
            else:
                LOGGER.critical(
                    'Неизвестная ошибка: %s', traceback.format_exc())
                raise error
            return False
        else:
            LOGGER.info('Авторизован')
            print('Авторизован')
            return True

    def longpoll_listen(self) -> None:
        """
            Прослушивание лонгпулл
        """
        LOGGER.info('Подключение к лонгпулл серверу')
        while True:
            try:
                for event in self.__longpoll.listen():
                    if event.type == VkBotEventType.MESSAGE_NEW:
                        self._new_message(event)
            except requests.exceptions.ReadTimeout as error:
                LOGGER.warning(str(error))

    def _new_message(self, event: VkBotMessageEvent) -> None:
        """
            Получение нового сообщения от лонгпулла
        :param event: Событие, полученное от лонгпулла
        """
        LOGGER.debug('Новое сообщение %s', str(event))
        if event.obj.geo is not None:
            context: dict = self.__menu_handler.got_message_with_geo(event)
        elif event.obj.payload:
            context: dict = self.__menu_handler.got_message_with_payload(event)
        else:
            context: dict = self.__menu_handler.got_unknown_message(event)
        if context:
            self.__vk.method('messages.send', context)
