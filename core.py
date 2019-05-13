import csv
import re

import bs4
import requests
from fuzzywuzzy import fuzz

import appp_shell
import config


class Spider:
    def __init__(self):
        self._session = requests.Session()
        self._bus_routes = appp_shell.BusRoutes()
        self.__download_info()
        self.__set_coords_every_stations()
        self._independent_stations = appp_shell.IndependentStations(
            self._bus_routes
        )

    @property
    def routes(self):
        return self._bus_routes

    @property
    def stations(self):
        return self._independent_stations

    def __download_info(self):
        link = config.route_selection_link
        params = config.route_selection_params
        response = self._session.get(link, params=params)
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        css = 'a[href*="page=stations"]'

        reg_expr_for_uid = re.compile(r'rid=([\d]+)', re.I)
        for route in soup.select(css):
            if reg_expr_for_uid.search(route['href']) is not None:
                uid = int(
                    reg_expr_for_uid.search(route['href']).groups()[0]
                )
                self._bus_routes.append(uid)

    def __set_coords_every_stations(self):
        with open('bus_stations.csv') as f:
            stations_csv = list(csv.reader(f, delimiter=';'))

        for route in self._bus_routes:
            for station in route.stations:
                max_equals = []
                for _, station_csv_name, lat, long, buses in stations_csv:
                    percent_eq = fuzz.ratio(
                        station_csv_name.lower(), station.name.lower()
                    )
                    is_bus_in_csv = station.name.lower() in buses.lower()
                    if percent_eq == 100 and is_bus_in_csv:
                        station.coords = (float(lat), float(long))
                        break
                    elif (not max_equals or max_equals[2] < percent_eq) and \
                            percent_eq >= 95:
                        max_equals = [lat, long, percent_eq]
                else:
                    if max_equals:
                        station.coords = (
                            float(max_equals[0]), float(max_equals[1])
                        )
