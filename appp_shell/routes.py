"""
    :author: xtess16
"""
from __future__ import annotations

import logging
import threading
from typing import Union, Optional, List, Tuple

import bs4
import requests

from . import exceptions, config
from . import stations as stations_module

LOGGER = logging.getLogger(__name__)


class BusRoutes:
    """
        Класс для хранения всех существующих маршрутов и работы с ними
    """

    def __init__(self, all_stations: stations_module.BusStations):
        """
            Инициализатор
        :param all_stations: Список всех остановок
        """
        LOGGER.info('%s инициализируется', self.__class__.__name__)
        self._bus_routes: List[BusRouteItem] = []
        self._all_stations = all_stations
        LOGGER.info('%s успешно инициализирован', self.__class__.__name__)

    def append(self, rid: str) -> None:
        """
            Добавляет автобсную остановку в список всех остановок
        :param rid: Уникальный идентификатор остановки
        """
        if rid not in self.get_all_rids():
            bus_route = BusRouteItem(rid, self._all_stations)
            self._bus_routes.append(bus_route)

    def remove(self, rid: str) -> None:
        """
            Удаляет автобусную остановку из списка всех остановок
        :param rid: Уникальный идентификатор остановки
        """
        try:
            remove_index = self.get_all_rids().index(rid)
        except IndexError:
            pass
        else:
            self._bus_routes.pop(remove_index)
            # TODO удалить из "моих" станций

    def get_all(self) -> List[BusRouteItem]:
        """
            Получение списка всех маршрутов
        """
        return self._bus_routes

    def get_all_rids(self) -> List[str]:
        """
            Получение rid всех маршрутов
        :return: list состоящий из rid всех маршрутов
        """

        rids = [i.rid for i in self._bus_routes]
        return rids

    def get_all_names(self) -> List[str]:
        """
            Получение имен всех маршрутов
        :return: list состоящий из имен всех маршрутов
        """
        routes = [i.name for i in self._bus_routes]
        return routes

    def __getitem__(self, item: Union[int, str]) -> Optional[BusRouteItem]:
        """
            Получение маршрутов по:
                индексу - как есть, обращение по индексу к списку маршрутов
                ключу - возвращает маршрут у которого rid равен ключу
        :param item: Индекс/ключ
        :return: Один маршрут или None
        """
        if isinstance(item, int):
            return self._bus_routes[item]
        for route in self._bus_routes:
            if route.rid == item:
                return route
        return None

    def __len__(self) -> int:
        """
            Получение количества маршрутов
        """
        return len(self._bus_routes)

    def __repr__(self):
        return f'{self.__class__.__name__}({self._bus_routes})'


class BusRouteItem:
    """
        Класс для хранения одного маршрута и работы с ним
    """

    def __init__(self, rid: str, all_stations: stations_module.BusStations):
        """
            Инициализатор
        :param rid: Уникальный идентификатор маршрута (route id)
        :param all_stations: Все существующие остановки
        """

        LOGGER.info(
            '%s(rid=%s) инициализируется', self.__class__.__name__, rid)
        self.__route_page: Optional[bs4.BeautifulSoup] = None

        self._rid = rid
        self._all_stations = all_stations
        # Список остановок, через которые проезжает маршрут
        self.__my_stations = []
        self._requests_session = requests.Session()

        # threading событие. Нужно для того, чтобы методы,
        # сначала дождались пока веб-страница, с которой будет парситься
        # информация о маршруте, загрузится
        self.__download_page_flag = threading.Event()
        threading.Thread(
            target=self.download_page_by_rid, args=(rid,)
        ).start()
        LOGGER.info('%s(rid=%s) инициализирован', self.__class__.__name__, rid)

    def download_page_by_rid(self, rid: str) -> None:
        """
            Загрузка страницы, с которой будет парситься информация о маршруте
        :param rid: Уникальный идентификатор маршрута
        """

        link: str = config.ROUTE_STATIONS_LINK
        params: dict = config.ROUTE_STATIONS_PARAMS
        params['rid'] = rid

        response = self._requests_session.get(link, params=params)
        # Имя маршрута в этом селекторе
        route_name_css = 'fieldset legend'
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        route_name = soup.select(route_name_css)
        if route_name:
            self.__route_page = soup
            self.__download_page_flag.set()
            self._all_stations.append_stations_by_route_page(
                soup, route=self
            )
        else:
            LOGGER.debug('rid=%s не существует', rid)
            raise exceptions.RouteByRidNotFound

    @property
    def rid(self) -> str:
        """
            Получение уникального идентификатора маршрута
        :return: Уникальный идентификатор маршрута
        """
        return self._rid

    def get_bus_info(self) -> Tuple[str, str, str]:
        """
            Получение информации о маршруте
        :return: tuple из (номер маршрута, название первой остановки,
            название последней остановки)
        """

        self.__download_page_flag.wait()
        route_name_css = 'fieldset legend'
        route_name: List[bs4.element.Tag] = \
            self.__route_page.select(route_name_css)
        route_name = route_name[0].text

        route_num, first_station, last_station = \
            config.ROUTE_NAME_REG_EXPR.search(route_name).groups()
        return route_num, first_station, last_station

    @property
    def name(self) -> str:
        """
            Получение полного имени маршрута
        :return: Имя маршрута + первая и конечная остановки
        """
        route_num, first_station, last_station = self.get_bus_info()
        return f'#{route_num} ({first_station} - {last_station})'

    @property
    def number(self) -> str:
        """
            Получение номера маршрута
        :return: Номер маршрута
        """
        return self.get_bus_info()[0]

    @property
    def stations(self) -> List[stations_module.BusStationItem]:
        """
            Получение всех остановок, через которые проезжает маршрут
        :return: Список остановок, через которые проезжает маршрут
        """
        self.__download_page_flag.wait()
        return self.__my_stations

    def append_my_station(
            self, station: stations_module.BusStationItem) -> None:
        """
            Добавляет остановку в список остановок,
            через которые проезжает маршрут
        :param station: Остановка
        """
        self.__my_stations.append(station)

    def remove_my_station(
            self, station: stations_module.BusStationItem) -> None:
        """
            Удаляет остановку из списка остановок,
            через которые проезжает маршрут
        :param station: Остановка
        """
        self.__my_stations.remove(station)

    def __repr__(self):
        classname = self.__class__.__name__
        return f"{classname}(rid='{self.rid}', name='{self.name}', " +\
            f' stations={[x.name for x in self.stations]})'
