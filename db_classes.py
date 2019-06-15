"""
    :author: xtess16
"""
from __future__ import annotations

from typing import List

import sqlalchemy
from sqlalchemy import String, Integer, Column, Float, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class StationsCoord(Base):
    """
        Таблица содежращая в себе:
            name - имя остановки
            sid - уникальный идентификатор
            latitude - ширата
            longitude - долгота
    """
    __tablename__ = 'stations_coord'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    sid = Column(String(4), unique=True)
    latitude = Column(Float)
    longitude = Column(Float)

    def __init__(self, name: str, sid: str, lat: float, long: float):
        """
            Инициализтор
        :param name: Имя остановки
        :param sid: Уникальный идентификатор
        :param lat: Широта
        :param long: Долгота
        """
        self.name = name
        self.sid = sid
        self.latitude = lat
        self.longitude = long

    def __repr__(self):
        return '{classname}({name}, {sid}, ({lat}, {long}))'.format(
            classname=self.__class__.__name__, name=self.name,
            sid=self.sid, lat=self.latitude, long=self.longitude
        )


class RecentStations(Base):
    """
        Таблица последних остановок, расписание которых получал пользователь
            peer_id - id пользователя
            stations - список sid остановок
    """
    __tablename__ = 'recent_stations_of_users'
    id = Column(Integer, primary_key=True)
    peer_id = Column(Integer, unique=True)
    stations = Column(JSON)

    def __init__(self, peer_id: int, stations: List[str]):
        """
            Инициализатор
        :param peer_id: id пользователя
        :param stations: Список имен остановок
        """
        self.peer_id = peer_id
        self.stations = stations

    def __repr__(self):
        return '{}(peer_id={}, stations={})'.format(
            self.__class__.__name__, self.peer_id, self.stations
        )

    def add(self, name: str) -> None:
        """
            Добавляет остановку в список последних, при этом,
            убирая самую старую
        :param name: Имя остановки
        """
        tmp_stations = self.stations[:]
        if name in tmp_stations:
            tmp_stations.remove(name)
        tmp_stations.append(name)
        self.stations = tmp_stations[-5:]


class PopularStations(Base):
    """
        Таблица самых популярных остановок среди всех пользователей
            sid - уникальный идентификатор остановки
            call_count - количество вызовов
    """
    __tablename__ = 'popular_stations'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    call_count = Column(Integer)

    def __init__(self, name: str, call_count: int):
        """
            Инициализатор
        :param name: Имя остановки
        :param call_count: Количество вызовов
        """
        self.name = name
        self.call_count = call_count

    def __repr__(self):
        return '{}(id={}, sid={}, call_count={})'.format(
            self.__class__.__name__, self.id, self.sid, self.call_count
        )


def get_db_engine(path_to_db: str) -> sqlalchemy.engine.base.Engine:
    """
        Создание engine для работы с БД
    :param path_to_db: Путь к базе данных
    :return: engine объект для работы с БД
    """
    engine = sqlalchemy.create_engine('sqlite:///'+path_to_db)
    Base.metadata.create_all(engine)
    return engine
