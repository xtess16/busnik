from __future__ import annotations

import csv
import logging
import os
import threading
from typing import Union, Optional, Tuple

import bs4
import requests
from fuzzywuzzy import fuzz
from haversine import haversine, Unit

from . import exceptions, config
from . import routes as routes_module
from db_classes import StationsCoord

logger = logging.getLogger(__name__)
if os.path.exists(config.bus_stations_csv_path):
    with open(config.bus_stations_csv_path) as f:
        STATIONS_CSV = list(csv.reader(f, delimiter=';'))
else:
    STATIONS_CSV = None


class BusStations:
    def __init__(self, session):
        logger.info(self.__class__.__name__ + ' инициализируется')
        self.__session = session
        self._bus_stations: list[BusStationItem] = []
        self.__append_stations_locker = threading.Lock()
        logger.info(self.__class__.__name__ + ' инициализирован')

    @property
    def stations(self):
        return self._bus_stations

    def all(self):
        return self.stations

    def all_stations_without_none_coords(self):
        stations = []
        for station in self._bus_stations:
            if station.coords is not None:
                stations.append(station)
        return stations

    def append_stations_by_route_page(
            self, route_page: bs4.BeautifulSoup,
            route: Optional[routes_module.BusRouteItem] = None):
        css = 'fieldset a[href*="page=forecasts"]'
        stations = []
        self.__append_stations_locker.acquire()
        cursor = self.__session()
        # TODO если все станции имеют
        # остановку A(которая лежит на одной из сторон)
        # то все станции из сета лежат на этой стороне
        for station_html in route_page.select(css):
            sid = config.reg_expr_for_stid.search(
                station_html['href']).groups()[0]
            name = station_html.text.strip()
            name = config.replace_station_name(name)
            if stations and stations[-1] and name == stations[-1]['name']:
                stations.append(None)
                continue
            stations.append({
                'sid': sid,
                'name': name
            })
            if sid not in self:
                coords = cursor.query(
                    StationsCoord.latitude, StationsCoord.longitude
                ).filter(StationsCoord.sid == sid).one_or_none()
                station_item = \
                    BusStationItem(
                        link=config.station_link.format(station_html['href']),
                        name=name,
                        coords=coords
                    )
                station_db = cursor.query(StationsCoord).filter(
                    StationsCoord.sid == sid).one_or_none()
                if station_db is not None:
                    station_db.latitude, station_db.longitude = \
                        station_item.coords
                elif station_item.coords is not None:
                    cursor.add(
                        StationsCoord(name, sid, *station_item.coords)
                    )
                cursor.commit()
                cursor.close()
                if route is not None:
                    station_item.append_route(route)
                    route.append_my_station(station_item)
                self._bus_stations.append(station_item)
            else:
                self[sid].append_route(route)
                route.append_my_station(self[sid])
        for i in range(len(stations)-1):
            if stations[i] is not None and stations[i+1] is not None:
                sid = stations[i]['sid']
                next_station_sid = stations[i+1]['sid']
                self[sid].append_next_station(self[next_station_sid])
        self.__append_stations_locker.release()

    def all_sids(self) -> list[str]:
        return [i.sid for i in self.stations]

    def all_names(self, casefold=False) -> list[str]:
        if casefold:
            names = [i.name.casefold() for i in self.stations]
        else:
            names = [i.name for i in self.stations]
        return names

    def all_stations_by_route(self, route: routes_module.BusRouteItem):
        stations = [station for station in self.stations if route in station]
        return stations

    def all_stations_by_coords(self, coords: tuple[float],
                               max_distance: int, with_distance=False,
                               sort=False):
        nearest_stations = []
        for station in self.all_stations_without_none_coords():
            distance = haversine(coords, station.coords, Unit.METERS)
            if distance <= max_distance:
                nearest_stations.append((station, distance))

        if sort:
            nearest_stations.sort(key=lambda x: x[1])
        if with_distance:
            return nearest_stations
        else:
            return list(map(lambda x: x[0], nearest_stations))

    def __len__(self):
        return len(self._bus_stations)

    def __repr__(self):
        return str(self._bus_stations)

    def __contains__(self, sid: str):
        return sid in self.all_sids()

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._bus_stations[item]
        else:
            for station in self._bus_stations:
                if station.sid == item:
                    return station
            else:
                return None


class BusStationItem:
    __COORDS_NOT_FOUND = 'coords_not_found'

    def __init__(self, link: str, name: str,
                 coords: Optional[Tuple[float, float]] = None):
        logger.info('{}(name="{}") инициализируется'.format(
            self.__class__.__name__, name
        ))
        self.__link = link
        self._name: str = name

        self._requests_session = requests.Session()
        self._sid: str = config.reg_expr_for_stid.search(link).groups()[0]
        self._next_stations: list[BusStationItem] = []
        self._routes: list[routes_module.BusRouteItem] = []

        self._coords = coords
        if coords is None:
            self.calculate_coords_from_stations_csv(STATIONS_CSV)
        logger.info('{}(name="{}") инициализирован'.format(
            self.__class__.__name__, name
        ))

    @property
    def name(self) -> str:
        return self._name

    @property
    def coords(self) -> Union[tuple[float, float], None]:
        return self._coords

    @coords.setter
    def coords(self, value: tuple[float, float]):
        self._coords = value

    @property
    def sid(self) -> str:
        return self._sid

    @property
    def next_stations(self):
        return self._next_stations

    def append_next_station(self, station: BusStationItem) -> None:
        if station not in self._next_stations:
            self._next_stations.append(station)

    def remove_next_station_by_sid(self, sid: str) -> None:
        for station in self._next_stations:
            if station.sid == sid:
                self._next_stations.remove(station)
                break

    @property
    def routes(self):
        return self._routes

    def append_route(self, route: routes_module.BusRouteItem):
        if route not in self._routes:
            self._routes.append(route)

    def remove_route(self, route: routes_module.BusRouteItem):
        self._routes.remove(route)

    @property
    def schedule(self) -> list[dict]:
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

    def calculate_coords_from_stations_csv(
            self, stations_csv: Optional[list[list]]):
        if stations_csv is None:
            raise exceptions.StationsCsvNotFound
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
                self._coords = None

    def __contains__(self, item: routes_module.BusRouteItem):
        return item in self._routes

    def __repr__(self):
        classname = self.__class__.__name__
        sid = self.sid
        name = self.name
        next_stations = [i.name for i in self.next_stations]
        routes = [route.name for route in self._routes]
        return f'{classname}' + \
               f"(sid='{sid}', name='{name}', " + \
               f'next_stations={next_stations}, routes={routes})'
