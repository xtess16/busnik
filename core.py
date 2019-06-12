"""
    :author: xtess16
"""
from __future__ import annotations

import re

import bs4
import requests
import sqlalchemy
from sqlalchemy.orm import sessionmaker

import config
import db_classes
from appp_shell import BusRoutes
from appp_shell import BusStations


class Spider:
    """
        Является связующим между вк ботом и парсером.
        Предоставляет для бота доступ к остановкам и маршрутам
    """

    def __init__(self):
        """
            Инициализтор, создает сессии, экземпляры основных классов
        """
        self._requests_session = requests.Session()
        self.__db_engine: sqlalchemy.engine.base.Engine = \
            db_classes.get_db_engine(config.PATH_TO_DB)
        self.__db_session: sqlalchemy.orm.session.sessionmaker = \
            sessionmaker(self.__db_engine)
        self._all_stations = BusStations(self.__db_session)
        self._bus_routes = BusRoutes(self._all_stations)
        self.__download_info()

    @property
    def db_engine(self) -> sqlalchemy.engine.base.Engine:
        """
            Получение engine sqlalchemy для работы с БД
        """
        return self.__db_engine

    @property
    def db_session(self) -> sqlalchemy.orm.session.sessionmaker:
        """
            Получение сессии для дальнейшего создания курсоров
            для работы с БД
        """
        return self.__db_session

    @property
    def routes(self) -> BusRoutes:
        """
            Получение экземпляра класса BusRoutes для работы с маршрутами
        """
        return self._bus_routes

    @property
    def stations(self) -> BusStations:
        """
            Получение экземпляра класса BusStations для работы с остановками
        """
        return self._all_stations

    def __download_info(self):
        """
            Загрузка основной информации о маршрутах и остановках
        """
        print('Скачивание информации о маршрутах и остановках')
        link: str = config.ROUTE_SELECTION_LINK
        params: dict = config.ROUTE_SELECTION_PARAMS
        response = self._requests_session.get(link, params=params)
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        css = 'a[href*="page=stations"]'

        reg_expr_for_uid = re.compile(r'rid=([\d]+)', re.I)
        for route in soup.select(css):
            if reg_expr_for_uid.search(route['href']) is not None:
                rid = reg_expr_for_uid.search(route['href']).groups()[0]
                self._bus_routes.append(rid)
