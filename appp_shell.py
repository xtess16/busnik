import re

import bs4
import requests

import config
import exceptions


class BusRoutes:
    def __init__(self):
        self._bus_routes = []

    def append(self, uid):
        if uid not in self.get_all_uids():
            bus_route = BusRouteItem(uid)
            self._bus_routes.append(bus_route)

    def remove(self, uid):
        for route in self._bus_routes:
            if route.uid == uid:
                self._bus_routes.remove(route)

    def get_all(self):
        return self._bus_routes

    def get_all_uids(self):
        uids = list(map(lambda x: x.uid, self._bus_routes))
        return uids

    def get_all_names(self):
        routes = list(map(lambda x: x.name, self._bus_routes))
        return routes

    def get_routes_by_2_stations(self, from_station, to_station):
        suitable_routes = []
        for route in self._bus_routes:
            from_station_index, to_station_index = \
                route.get_station_indexes_or_none_by_station_names(
                    from_station, to_station
                )
            if not (from_station_index is None or to_station_index is None):
                if from_station_index < to_station_index:
                    suitable_routes.append(route)
        return suitable_routes

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._bus_routes[item]
        else:
            for route in self._bus_routes:
                if route.name.lower() == item.lower():
                    return route

    def __repr__(self):
        return f'{self.__class__.__name__}({self._bus_routes})'


class BusRouteItem:
    def __init__(self, uid):
        self._uid: int = uid
        self.__route_page: bs4.BeautifulSoup = \
            BusRouteItem.download_page_by_uid(uid)
        self._stations: BusStations = BusStations(self.__route_page)

    @property
    def uid(self):
        return self._uid

    def get_bus_params(self):
        route_name_css = 'fieldset legend'
        route_name = self.__route_page.select(route_name_css)
        route_name = route_name[0].text

        route_num, first_station, last_station = \
            config.route_name_reg_expr.search(route_name).groups()
        return route_num, first_station, last_station

    @property
    def name(self):
        route_num, first_station, last_station = self.get_bus_params()
        return f'#{route_num} ({first_station} - {last_station})'

    @property
    def number(self):
        return self.get_bus_params()[0]

    @property
    def stations(self):
        return self._stations

    @staticmethod
    def download_page_by_uid(uid):
        link = config.route_stations_link
        params = config.route_stations_params
        params['rid'] = uid

        response = requests.get(link, params=params)
        route_name_css = 'fieldset legend'
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        route_name = soup.select(route_name_css)
        if route_name:
            return soup
        else:
            raise exceptions.RouteByUidNotFound

    def get_station_indexes_or_none_by_station_names(self, *station_names):
        station_indexes = []
        for station_name in station_names:
            try:
                station_indexes.append(
                    self._stations.lower_case_all_names().index(
                        station_name.lower())
                )
            except ValueError:
                station_indexes.append(None)
        return station_indexes

    def __repr__(self):
        classname = self.__class__.__name__
        return f'{classname}(uid="{self.uid}", name="{self.name}")'


class BusStations:
    def __init__(self, page: bs4.BeautifulSoup):
        self.__route_page = page
        self._bus_stations: list = self._get_stations_by_route_page(page)

    def _get_stations_by_route_page(self, page):
        css = 'fieldset a[href*="page=forecasts"]'
        stations = []
        for station in page.select(css):
            stations.append(
                BusStationItem(
                    link=config.station_link.format(station['href']),
                    name=station.text.strip()
                )
            )
        for i in range(len(stations)-1):
            stations[i].next_station = stations[i+1]
        return stations

    def all_names(self):
        stations_css = 'fieldset a[href*="page=forecasts"]'
        tmp_stations = self.__route_page.select(stations_css)
        stations = [station.text.strip() for station in tmp_stations]
        return stations

    def all_uids(self):
        pass

    def lower_case_all_names(self):
        return [station.name.lower() for station in self._bus_stations]

    def __repr__(self):
        return str(self._bus_stations)

    def __contains__(self, station):
        return station.lower() in self.lower_case_all_names()

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._bus_stations[item]
        else:
            for station in self._bus_stations:
                if station.name.lower() == item.lower():
                    return station


class BusStationItem:
    uid_reg_expr = re.compile(r'stid=(\d+)')
    LAST_STATION = 'last_station'

    def __init__(self, link, name, next_station=None):
        self.__link = link
        self._name = config.replace_station_names.get(name, name)
        self._uid = self.uid_reg_expr.search(link).groups()[0]
        self._coords = None
        if next_station is None:
            self._next_station = BusStationItem.LAST_STATION
        else:
            self._next_station = next_station

    @property
    def name(self):
        return self._name

    @property
    def coords(self):
        return self._coords

    @coords.setter
    def coords(self, value):
        self._coords = value

    @property
    def uid(self):
        return self._uid

    @property
    def next_station(self):
        return self._next_station

    @next_station.setter
    def next_station(self, value):
        self._next_station = value

    @property
    def schedule(self):
        route_num_css = '.main tr td fieldset table tr:not(:first-child) td'
        response = requests.get(self.__link)
        tmp_schedule_table = []
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        for td in soup.select(route_num_css):
            tmp_schedule_table.append(td.text.strip())
        schedule_table = []
        for i in range(len(tmp_schedule_table)//4):
            tr = tmp_schedule_table[i*4:i*4+4]
            schedule_table.append({
                'route_name': tr[0],
                'arrival_time': tr[1],
                'current_station': tr[2],
                'last_station': tr[3]
            })
        return schedule_table

    def __repr__(self):
        classname = self.__class__.__name__
        uid = f'uid="{self.uid}"'
        name = f'name="{self.name}"'
        if self.next_station == BusStationItem.LAST_STATION:
            next_station = 'next_station="Конечная"'
        else:
            next_station = f'next_station="{self.next_station.name}"'
        return f'{classname}({uid}, {name}, {next_station})'


class IndependentStations:
    def __init__(self, routes):
        self.__bus_routes = routes

    def get_stations_by_substring(self, substring):
        stations = []
        uids = []
        for route in self.__bus_routes:
            for station in route.stations:
                if substring.lower() in station.name.lower():
                    if station.uid not in uids:
                        stations.append(station)
                        uids.append(station.uid)
        return stations

    def get_station_by_name_and_next_station(self, name, next_station):
        for route in self.__bus_routes:
            for station in route.stations:
                is_equal_names = name.lower() == station.name.lower()
                if station.next_station == BusStationItem.LAST_STATION:
                    continue
                is_equal_next_stations = \
                    next_station.lower() == station.next_station.name.lower()
                if is_equal_names and is_equal_next_stations:
                    return station

    def get_all(self):
        stations = []
        uids = []
        for route in self.__bus_routes:
            for station in route.stations:
                if station.uid not in uids:
                    stations.append(station)
                    uids.append(station.uid)
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

    def __repr__(self):
        return str(self.get_all())

