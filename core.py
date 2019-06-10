from __future__ import annotations

import re
import bs4
import requests

import db_classes
from appp_shell import BusRoutes
from appp_shell import BusStations
import config
from sqlalchemy.orm import sessionmaker


class Spider:
    def __init__(self):
        self._requests_session = requests.Session()
        self.__db_engine = db_classes.get_db_engine(config.path_to_db)
        self.__db_session = sessionmaker(self.__db_engine)
        self._all_stations = BusStations(self.__db_session)
        self._bus_routes = BusRoutes(self._all_stations)
        self.__download_info()

    @property
    def db_engine(self):
        return self.__db_engine

    @property
    def db_session(self):
        return self.__db_session

    @property
    def routes(self):
        return self._bus_routes

    @property
    def stations(self):
        return self._all_stations

    def __download_info(self):
        print('Скачивание информации о маршрутах и станциях')
        link: str = config.route_selection_link
        params: dict = config.route_selection_params
        response = self._requests_session.get(link, params=params)
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        css = 'a[href*="page=stations"]'

        reg_expr_for_uid = re.compile(r'rid=([\d]+)', re.I)
        for route in soup.select(css):
            if reg_expr_for_uid.search(route['href']) is not None:
                rid = reg_expr_for_uid.search(route['href']).groups()[0]
                self._bus_routes.append(rid)
