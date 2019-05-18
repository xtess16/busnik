from __future__ import annotations

import logging
import threading
from typing import Union

import bs4
import requests

from appp_shell.stations import BusStations
from . import config
from . import exceptions


logger = logging.getLogger(__name__)


class BusRoutes:
    def __init__(self):
        logger.info(f'{self.__class__.__name__} инициализируется')
        self._bus_routes: list[BusRouteItem] = []
        self._bus_routes_rids: list[str] = []
        logger.info(f'{self.__class__.__name__} успешно инициализирован')

    def append(self, rid: str) -> None:
        if rid not in self.get_all_rids():
            bus_route = BusRouteItem(rid)
            self._bus_routes.append(bus_route)
            self._bus_routes_rids.append(rid)

    def remove(self, rid: str) -> None:
        try:
            remove_index = self._bus_routes_rids.index(rid)
        except IndexError:
            pass
        else:
            self._bus_routes.pop(remove_index)
            self._bus_routes_rids.pop(remove_index)

    def get_all(self) -> list[BusRouteItem]:
        return self._bus_routes

    def get_all_rids(self) -> list[str]:
        return self._bus_routes_rids

    def get_all_names(self) -> list[str]:
        routes = list(map(lambda x: x.name, self._bus_routes))
        return routes

    def __getitem__(self, item) -> BusRouteItem:
        if isinstance(item, int):
            return self._bus_routes[item]
        else:
            for route in self._bus_routes:
                if route.name.casefold() == item.casefold():
                    return route

    def __repr__(self):
        return f'{self.__class__.__name__}({self._bus_routes})'


class BusRouteItem:
    def __init__(self, rid: str):
        logger.info('{}(rid={}) инициализируется'.format(
            self.__class__.__name__, rid
        ))
        self.__route_page: Union[bs4.BeautifulSoup, None] = None
        self._stations: Union[BusStations, None] = None

        self._rid: str = rid
        self._requests_session = requests.Session()
        self.__download_page_flag = threading.Event()
        threading.Thread(
            target=self.download_page_by_rid, args=(rid,)
        ).start()
        logger.info('{}(rid={}) инициализирован'.format(
            self.__class__.__name__, rid
        ))

    def download_page_by_rid(self, rid: str) -> None:
        link: str = config.route_stations_link
        params: dict = config.route_stations_params
        params['rid'] = rid

        response = self._requests_session.get(link, params=params)
        route_name_css = 'fieldset legend'
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        route_name = soup.select(route_name_css)
        if route_name:
            self.__route_page = soup
            self._stations = BusStations(self.__route_page)
            self.__download_page_flag.set()
        else:
            logger.debug('rid={} не существует'.format(rid))
            raise exceptions.RouteByRidNotFound

    @property
    def rid(self) -> str:
        return self._rid

    def get_bus_info(self) -> tuple[str, str, str]:
        self.__download_page_flag.wait()
        route_name_css = 'fieldset legend'
        route_name: list[bs4.element.Tag] = \
            self.__route_page.select(route_name_css)
        route_name = route_name[0].text

        route_num, first_station, last_station = \
            config.route_name_reg_expr.search(route_name).groups()
        return route_num, first_station, last_station

    @property
    def name(self) -> str:
        route_num, first_station, last_station = self.get_bus_info()
        return f'#{route_num} ({first_station} - {last_station})'

    @property
    def number(self) -> str:
        return self.get_bus_info()[0]

    @property
    def stations(self) -> BusStations:
        self.__download_page_flag.wait()
        return self._stations

    def __repr__(self):
        classname = self.__class__.__name__
        return f'{classname}(rid="{self.rid}", name="{self.name}")'
