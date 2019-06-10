from __future__ import annotations

import json
import logging
import traceback
from typing import Optional

import requests
import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.bot_longpoll import VkBotMessageEvent
from vk_api.utils import sjson_dumps

from . import menu, config

logger = logging.getLogger(__name__)


class Bot:
    def __init__(self, spider):
        logger.info(self.__class__.__name__ + ' инициализируется')
        self.__spider = spider
        self.__vk: Optional[vk_api.VkApi] = None
        self.__longpoll: Optional[VkBotLongPoll] = None
        self.__menu_handler: menu.Menu = menu.Menu(self.__spider)
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
            context: dict = self.__menu_handler.got_message_with_geo(event)
        elif event.obj.payload is not None:
            context: dict = self.__menu_handler.got_message_with_payload(event)
        else:
            context = self.__menu_handler.got_unknown_message(event)
        if context:
            self.__vk.method('messages.send', context)

    def __delete_all_empty_line_from_keyboard(self, keyboard: str) -> dict:
        keyboard: dict = json.loads(keyboard)
        while [] in keyboard['buttons']:
            keyboard['buttons'].remove([])
        return sjson_dumps(keyboard)
