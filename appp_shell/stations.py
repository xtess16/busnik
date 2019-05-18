from __future__ import annotations

import csv
import logging
import re
from typing import Union

import bs4
import requests
from fuzzywuzzy import fuzz

from . import config
from .import exceptions

logger = logging.getLogger(__name__)
with open(config.bus_stations_csv_path) as f:
    STATIONS_CSV = list(csv.reader(f, delimiter=';'))


class BusStations:
    def __init__(self, page: bs4.BeautifulSoup):
        logger.info(self.__class__.__name__ + ' инициализируется')
        self.__route_page = page
        self._bus_stations: list[BusStationItem] = \
            self._get_stations_by_route_page(page)
        logger.info(self.__class__.__name__ + ' инициализирован')

    def _get_stations_by_route_page(
            self, page: bs4.BeautifulSoup) -> list[BusStationItem]:
        css = 'fieldset a[href*="page=forecasts"]'
        stations: list[BusStationItem] = []
        for station in page.select(css):
            stations.append(
                BusStationItem(
                    link=config.station_link.format(station['href']),
                    name=station.text.strip(),
                    stations_csv=STATIONS_CSV
                )
            )
        for i in range(len(stations)-1):
            stations[i].next_station = stations[i+1]
        return stations

    def all_names(self) -> list[str]:
        stations_css = 'fieldset a[href*="page=forecasts"]'
        tmp_stations: list[bs4.element.Tag] = \
            self.__route_page.select(stations_css)
        stations = [station.text.strip() for station in tmp_stations]
        return stations

    def casefold_all_names(self) -> list[str]:
        return [station.name.casefold() for station in self._bus_stations]

    def __repr__(self):
        return str(self._bus_stations)

    def __contains__(self, station_name: str):
        return station_name.casefold() in self.casefold_all_names()

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._bus_stations[item]
        else:
            for station in self._bus_stations:
                if station.name.casefold() == item.casefold():
                    return station


class BusStationItem:
    sid_reg_expr = re.compile(r'stid=(\d+)')
    LAST_STATION = 'last_station'
    __COORDS_NOT_FOUND = 'coords_not_found'

    def __init__(self, link: str, name: str,
                 next_station=None, stations_csv=None):
        logger.info('{}(name="{}") инициализируется'.format(
            self.__class__.__name__, name
        ))
        self.__link = link
        self._requests_session = requests.Session()
        self._name: str = config.replace_station_names(name)
        self._sid: str = self.sid_reg_expr.search(link).groups()[0]
        if next_station is None:
            self._next_station = BusStationItem.LAST_STATION
        else:
            self._next_station = next_station
        self._coords: Union[tuple[float, float], str, None] = None
        if stations_csv is not None:
            self.calculate_coords_from_stations_csv(stations_csv)
        else:
            self._coords = None
        self._stations_csv = stations_csv
        logger.info('{}(name="{}") инициализирован'.format(
            self.__class__.__name__, name
        ))

    @property
    def name(self) -> str:
        return self._name

    @property
    def coords(self) -> Union[tuple[float, float], None]:
        if self._coords is None:
            if self._stations_csv is None:
                raise exceptions.StationsCsvNotFound
            else:
                self.calculate_coords_from_stations_csv(
                    self._stations_csv
                )
        if self._coords == BusStationItem.__COORDS_NOT_FOUND:
            return None
        else:
            return self._coords

    @coords.setter
    def coords(self, value: tuple[float, float]):
        self._coords = value

    @property
    def sid(self) -> str:
        return self._sid

    @property
    def next_station(self):
        return self._next_station

    @next_station.setter
    def next_station(self, value):
        self._next_station = value

    @property
    def schedule(self):
        route_num_css = '.main tr td fieldset table tr:not(:first-child) td'
        response = self._requests_session.get(self.__link)
        tmp_schedule_table = []
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        for td in soup.select(route_num_css):
            tmp_schedule_table.append(td.text.strip())
        schedule_table = []
        for i in range(len(tmp_schedule_table)//4):
            tr = tmp_schedule_table[i*4:i*4+4]
            schedule_table.append({
                'route_name': tr[0],
                'arrival_time': int(tr[1]),
                'current_station': tr[2],
                'last_station': tr[3]
            })
        return schedule_table

    def calculate_coords_from_stations_csv(self, stations_csv):
        max_equals = []
        for station_csv_name, lat, long, buses in stations_csv:
            percent_eq = fuzz.ratio(
                station_csv_name.casefold(), self._name.casefold()
            )
            is_bus_in_csv = self._name.casefold() in buses.casefold()
            if percent_eq == 100 and is_bus_in_csv:
                self._coords = (float(lat), float(long))
                break
            elif (not max_equals or max_equals[2] < percent_eq) and \
                    percent_eq >= 95:
                max_equals = [lat, long, percent_eq]
        else:
            if max_equals:
                self._coords = (
                    float(max_equals[0]), float(max_equals[1])
                )
            else:
                self._coords = BusStationItem.__COORDS_NOT_FOUND
                return BusStationItem.__COORDS_NOT_FOUND

    def __repr__(self):
        classname = self.__class__.__name__
        sid = f'sid="{self.sid}"'
        name = f'name="{self.name}"'
        if self.next_station == BusStationItem.LAST_STATION:
            next_station = 'next_station="Конечная"'
        else:
            next_station = f'next_station="{self.next_station.name}"'
        return f'{classname}({sid}, {name}, {next_station})'


class IndependentStations:
    def __init__(self, routes):
        self.__bus_routes = routes

    def get_stations_by_substring(self, substring):
        stations = []
        sids = []
        for route in self.__bus_routes:
            for station in route.stations:
                if substring.lower() in station.name.lower():
                    if station.rid not in sids:
                        stations.append(station)
                        sids.append(station.sid)
        return stations

    def get_all(self):
        stations = []
        sids = []
        for route in self.__bus_routes:
            for station in route.stations:
                if station.sid not in sids:
                    stations.append(station)
                    sids.append(station.sid)
        return stations

    def get_all_names(self):
        stations = []
        for station in self.get_all():
            stations.append(station.name)
        return stations

    def get_all_without_none_coords(self):
        stations = []
        for station in self.get_all():
            if station.coords is not None:
                stations.append(station)
        return stations

    def get_station_by_sid(self, sid):
        for route in self.__bus_routes:
            for station in route.stations:
                if station.sid == sid:
                    return station

    def __repr__(self):
        return str(self.get_all())
