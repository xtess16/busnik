from __future__ import annotations

import re
import bs4
import requests

from appp_shell import BusRoutes
from appp_shell import BusStations
import config


class Spider:
    def __init__(self):
        self._requests_session = requests.Session()
        self._all_stations = BusStations()
        self._bus_routes = BusRoutes(self._all_stations)
        self.__download_info()

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
