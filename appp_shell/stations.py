"""
    :author: xtess16
"""
from __future__ import annotations

import csv
import logging
import os
import threading
from typing import Optional, Tuple, Union, List, Dict, Any, NoReturn

import bs4
import requests
import sqlalchemy.orm
from fuzzywuzzy import fuzz
from haversine import haversine, Unit

from db_classes import StationsCoord
from . import exceptions, config
from . import routes as routes_module

LOGGER = logging.getLogger(__name__)
if os.path.exists(config.BUS_STATIONS_CSV_PATH):
    with open(config.BUS_STATIONS_CSV_PATH) as f:
        STATIONS_CSV = list(csv.reader(f, delimiter=';'))
else:
    STATIONS_CSV = None


class BusStations:
    """
        Класс для хранения всех существующих остановок и работы с ними
    """

    def __init__(self, session: sqlalchemy.orm.session.sessionmaker):
        """
            Инициализатор
        :param session: Сессия для работы с БД
        """
        LOGGER.info('%s инициализируется', self.__class__.__name__)
        self.__session = session
        self._bus_stations: List[BusStationItem] = []

        # threading lock. Нужен для того, чтобы во время добавления остановки
        # в список остановок, только один поток имел доступ к списку
        self.__append_stations_locker = threading.Lock()
        LOGGER.info('%s инициализирован', self.__class__.__name__)

    @property
    def stations(self) -> List[BusStationItem]:
        """
            Получение всех станций
        :return: Список всех станций
        """
        return self._bus_stations

    def all(self) -> List[BusStationItem]:
        """
            Тоже что и self.stations
        :return: Список всех станций
        """
        return self.stations

    def all_stations_without_none_coords(self) -> List[BusStationItem]:
        """
            Получение всех станций, у которых известны координаты
        :return: Список станций с координатами != None
        """
        stations = []
        for station in self._bus_stations:
            if station.coords is not None:
                stations.append(station)
        return stations

    def append_stations_by_route_page(
            self, route_page: bs4.BeautifulSoup,
            route: Optional[routes_module.BusRouteItem] = None) -> NoReturn:
        """
            Добавляет остановки в список всех остановок путем
            парсинга переданной в качестве аргумента страницы
        :param route_page: Страница, с которой будут парситься остановки
        :param route: Опциональный аргумент, если передан маршрут, то
            все остановки, которые спарсятся со страницы, будут присвоены этому
            маршруту, т.е будет считаться что
            маршрут проезжает через все эти остановки
        """

        def _get_stations_by_route_page(page: bs4.BeautifulSoup) -> \
                List[Dict[str, str]]:
            """
                Получение остановок из html страницы
            :param page: html страница, с которой парсятся остановки
            :return: Список остановок(словарей)
            """
            # Селектор для выбора каждой остановки на странице
            css = 'fieldset a[href*="page=forecasts"]'
            _stations = []
            # Тут содержится имя предыдущей остановки, нужно для того, чтобы
            # избежать добавлений несколько одинаковых остановок подряд
            prev_name = None
            # Проходим по всем остановкам на странице
            for station_html in page.select(css):
                # Извлекаем из ссылки на остановку уникальный идентификатор
                # sid (station id)
                station_html_sid = config.REG_EXPR_FOR_STID.search(
                    station_html['href']).groups()[0]
                # Парсим имя и приводим его к форме, необходимой для
                # дальнейшего получения координат этой остановки.
                # Это связано с тем, что название остановок в csv файле с
                # координатами остановок частично не совпадает с названиями
                # которые мы парсим с сайта
                station_html_name = config.replace_station_name(
                    station_html.text.strip())
                # Пропускаем остановку, если ее имя такое же
                # как и у предыдущей
                if prev_name is not None and prev_name == station_html_name:
                    continue
                _stations.append({
                    'sid': station_html_sid,
                    'name': station_html_name,
                    'href': station_html['href']
                })
                prev_name = station_html_name
            return _stations

        self.__append_stations_locker.acquire()
        cursor = self.__session()
        stations = _get_stations_by_route_page(route_page)
        try:
            for station in stations:
                _sid = station['sid']
                _name = station['name']
                _href = station['href']
                # Если остановки нет в списке остановок, добавляем
                if _sid not in self:
                    db_station = cursor.query(StationsCoord).filter(
                        StationsCoord.sid == _sid
                    ).one_or_none()
                    # Если этой остановки нет в БД таблице остановок
                    # с координатами, то создаем остановку и передаем
                    # координаты = None, если при создании остановки
                    # передать координаты = None, класс попытается получить
                    # координаты остановки из csv файла
                    if db_station is None:
                        station_item = BusStationItem(
                            link=config.STATION_LINK.format(_href),
                            name=_name, coords=None
                        )
                        # Если координаты нашлись в csv файле
                        # то добавляем остановку в БД таблицу остановок с
                        # координатами, после перезапуска программы,
                        # координаты будут находиться быстрее
                        # из-за ненадобности копаться в csv файле
                        if station_item.coords is not None:
                            cursor.add(StationsCoord(
                                _name, _sid, *station_item.coords
                            ))
                    # Иначе, берем координаты из таблицы и создаем остановку
                    # с этими координатами
                    else:
                        coords = (db_station.latitude, db_station.longitude)
                        station_item = BusStationItem(
                            link=config.STATION_LINK.format(_href),
                            name=_name, coords=coords
                        )
                    # Добавляем остановку в список всех остановок
                    self._bus_stations.append(station_item)
                # Если маршрут был передан аргументом, то добавляем этот
                # маршрут в список маршрутов, которые проходят через
                # остановку и добавляет остановку маршруту в список
                # остановок через которые он проходит
                if route is not None:
                    self[_sid].append_route(route)
                    route.append_my_station(self[_sid])
            # i-ой остановке добавляем в список следующих остановок
            # остановку i+1
            for i in range(len(stations)-1):
                sid = stations[i]['sid']
                next_station_sid = stations[i+1]['sid']
                self[sid].append_next_station(self[next_station_sid])
        except Exception as error:
            cursor.rollback()
            raise error
        else:
            cursor.commit()
        finally:
            self.__append_stations_locker.release()
            cursor.close()

    def all_sids(self) -> List[str]:
        """
            Получение списка sid всех остановок
        :return: list из sid всех остановок
        """
        return [i.sid for i in self.stations]

    def all_names(self, casefold=False) -> List[str]:
        """
            Получение имен всех остановок
        :param casefold: Если True, то ко всем именам применяется
            метод casefold
        :return: list из имен всех остановок
        """
        if casefold:
            names = [i.name.casefold() for i in self.stations]
        else:
            names = [i.name for i in self.stations]
        return names

    def all_stations_by_route(
            self, route: routes_module.BusRouteItem) -> List[BusStationItem]:
        """
            Получения списка всех остановок принадлежащих маршруту,
            переданному аргументом
        :param route: Маршрут, остановки которого надо вернуть
        :return: Список остановок через которые проходит маршрут,
            переданный аргументом
        """
        stations = [station for station in self.stations if route in station]
        return stations

    def all_stations_by_coords(self, coords: Tuple[float, float],
                               max_distance: int, with_distance=False,
                               sort=False) -> \
            Union[List[Tuple[BusStationItem, float]], List[BusStationItem]]:
        """
            Получение списка остановок и дистанций до них в определенном
            радиусе от переданных координат
        :param coords: Широта и долгота точки,
            рядом с которой искать остановки
        :param max_distance: Максимальный радиус поиска остановок
        :param with_distance: Возвращать дистанцию до остановки или нет
        :param sort: Сортировать результат по
            расстоянию от переданной точки
        :return: Список кортежей с остановками и расстоянием до них.
            Либо же список остановок, в зависимости от аргумента with_distance
        """

        nearest_stations = []
        for station in self.all_stations_without_none_coords():
            distance = haversine(coords, station.coords, Unit.METERS)
            if distance <= max_distance:
                nearest_stations.append((station, distance))

        if sort:
            nearest_stations.sort(key=lambda x: x[1])
        if with_distance:
            return nearest_stations
        return list(map(lambda x: x[0], nearest_stations))

    def all_stations_by_name(self, name: str) -> List[BusStationItem]:
        """
            Получение списка всех остановок по имени
        :param name: Имя остановки
        :return: Список остановок
        """
        res = []
        for station in self.stations:
            if station.name.casefold() == name.casefold():
                res.append(station)
        return res

    def __len__(self) -> int:
        """
            Получение количества существующих остановок
        :return: Количество остановок
        """
        return len(self._bus_stations)

    def __repr__(self):
        return str(self._bus_stations)

    def __contains__(self, sid: str) -> bool:
        """
            Есть ли остановка в списке всех остановок
        :param sid: Уникальный идентификатор остановки
        """
        return sid in self.all_sids()

    def __getitem__(self, item: Union[int, str]) -> Optional[BusStationItem]:
        """
            Получение остановки по:
                индексу - как есть, обращение по индексу к списку остановок
                ключу - возвращает остановку у которой ключ == rid
        :param item: Индекс/ключ
        :return: Одна остановка или None
        """
        if isinstance(item, int):
            return self._bus_stations[item]
        for station in self._bus_stations:
            if station.sid == item:
                return station
        return None


class BusStationItem:
    """
        Класс для хранения одной остановки и работы с ней
    """

    def __init__(self, link: str, name: str,
                 coords: Optional[Tuple[float, float]] = None):
        """
            Инициализатор
        :param link: Ссылка на остановку
        :param name: Имя остановки
        :param coords: Координаты остановки (широта, долгота)
        """

        LOGGER.info('%s(name="%s") инициализируется',
                    self.__class__.__name__, name)
        self.__link = link
        self._name: str = name

        self._requests_session = requests.Session()
        self._sid: str = config.REG_EXPR_FOR_STID.search(link).groups()[0]
        # Список остановок, которые идут после текущей
        self._next_stations: List[BusStationItem] = []
        # Список маршрутов, которые проходят через текущую остановку
        self._routes: List[routes_module.BusRouteItem] = []

        self._coords = coords
        # Если координаты не заданы, ищет координаты в csv файле
        if coords is None:
            self.calculate_coords_from_stations_csv(STATIONS_CSV)
        LOGGER.info('%s(name="%s") инициализирован',
                    self.__class__.__name__, name)

    @property
    def name(self) -> str:
        """
            Получение имени остановки
        """
        return self._name

    @property
    def coords(self) -> Optional[Tuple[float, float]]:
        """
            Получение координат остановки
        """
        return self._coords

    @coords.setter
    def coords(self, value: Optional[Tuple[float, float]]):
        """
            Установка координат остановки
        :param value: Координаты, кортеж из широты и долготы
        """
        self._coords = value

    @property
    def sid(self) -> str:
        """
            Получение уникального идентификатора остановки
        """
        return self._sid

    @property
    def next_stations(self) -> List[BusStationItem]:
        """
            Получение списка остановок, следующих после текущей
        :return: list остановок, которые идут после текущей
        """
        return self._next_stations

    def append_next_station(self, station: BusStationItem) -> NoReturn:
        """
            Добавление остановки(если не было до этого)
            в список следующих остановок
        :param station: Остановка
        """
        if station not in self._next_stations:
            self._next_stations.append(station)

    def remove_next_station_by_sid(self, sid: str) -> NoReturn:
        """
            Удаление остановки из списка следующих остановок (по sid)
        :param sid: Уникальный идентификатор остановки
        """
        for station in self._next_stations:
            if station.sid == sid:
                self._next_stations.remove(station)
                break

    @property
    def routes(self) -> List[routes_module.BusRouteItem]:
        """
            Получение списка маршрутов, которые проходят через
            текущую остановку
        :return: list маршрутов
        """
        return self._routes

    def append_route(self, route: routes_module.BusRouteItem) -> NoReturn:
        """
            Добавление маршрута в список маршрутов, проходящих
            через текущую остановку (если его там не было до этого)
        :param route: Маршрут
        """
        if route not in self._routes:
            self._routes.append(route)

    def remove_route(self, route: routes_module.BusRouteItem) -> NoReturn:
        """
            Удаляет маршрут из списка маршрутов, проходящих через
            текущую остановку
        :param route: Маршрут
        """
        self._routes.remove(route)

    @property
    def schedule(self) -> List[Dict[str, Any]]:
        """
            Получение расписания маршрутов текущей остановки
        :return: Расписание маршрутов в формате списка, каждый элемент которого
            является словарем и содержит в себе ключи:
                route_name - имя маршрута
                arrival_time - время прибытия на остановку в минутах
                current_station - название остановки, на которой на данный
                    момент находится маршрут
                last_station - конечная остановка маршрута
        """

        route_num_css = '.main tr td fieldset table tr:not(:first-child) td'
        response = self._requests_session.get(self.__link)
        tmp_schedule_table = []
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        for k in soup.select(route_num_css):
            tmp_schedule_table.append(k.text.strip())
        schedule_table = []
        for i in range(len(tmp_schedule_table)//4):
            line = tmp_schedule_table[i*4:i*4+4]
            schedule_table.append({
                'route_name': line[0],
                'arrival_time': int(line[1]),
                'current_station': line[2],
                'last_station': line[3]
            })
        return schedule_table

    def calculate_coords_from_stations_csv(
            self, stations_csv: Optional[List[List[Any]]]) -> NoReturn:
        """
            Расчет координат текущей остановки исходя из csv файла,
            представленного в виде матрицы и
            переданного в качестве аргумента
        :param stations_csv: матрица csv файла с координатами остановок
        """

        if stations_csv is None:
            raise exceptions.StationsCsvNotFound
        # Список для сохранения координат остановки и процентную точность имени
        max_equals: List[float] = []
        for station_csv_name, lat, long, _ in stations_csv:
            # Совпадение имени текущей остановки и остановки, указанной в файле
            percent_eq = fuzz.ratio(
                station_csv_name.casefold(), self._name.casefold()
            )
            # Если процент совпадения имен = 100,
            # то считается что остановка найдена
            if percent_eq == 100:
                self._coords = (float(lat), float(long))
                break
            # Иначе, если список координат
            # поодходящей остановки пуст(max_equals) или
            # процент совпадения имен больше чем тот, что есть в max_equals и
            # процент совпадения >= 95
            # То найденная остановка считается наиболее подходящей
            # для получения ее координат
            elif (not max_equals or max_equals[2] < percent_eq) and \
                    percent_eq >= 95:
                max_equals = [lat, long, percent_eq]
        else:
            # Если в max_equals есть координаты остановки,
            # то присваиваем их текущей остановке
            if max_equals:
                self._coords = (
                    float(max_equals[0]), float(max_equals[1])
                )
            else:
                self._coords = None

    def __contains__(self, item: routes_module.BusRouteItem) -> bool:
        """
            Есть ли маршрут в списке маршрутов, которые
            проходят через текущую остановку
        :param item: Маршрут
        """
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
