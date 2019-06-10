from __future__ import annotations

import json
from typing import Union

import sqlalchemy
from sqlalchemy import String, Integer, Column, Float, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class StationsCoord(Base):
    __tablename__ = 'stations_coord'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    sid = Column(String(4), unique=True)
    latitude = Column(Float)
    longitude = Column(Float)

    def __init__(self, name: str, sid: str, lat: float, long: float):
        self.name = name
        self.sid = sid
        self.latitude = lat
        self.longitude = long

    def __repr__(self):
        return '{classname}({name}, {sid}, ({lat}, {long}))'.format(
            classname=self.__class__.__name__, name=self.name,
            sid=self.sid, lat=self.latitude, long=self.longitude
        )


class UsersActions(Base):
    __tablename__ = 'users_actions'
    id = Column(Integer, primary_key=True)
    peer_id = Column(Integer)
    action_type = Column(String)
    data = Column(String)

    def __init__(self, peer_id: int, action_type: str,
                 data: Union[dict, list]):
        self.peer_id = peer_id
        self.action_type = action_type
        self.data = json.dumps(data)

    def __repr__(self):
        return '{classname}({peer_id}, {action_type}, {data)'.format(
            classname=self.__class__.__name__, peer_id=self.peer_id,
            action_type=self.action_type, data=self.data
        )


class RecentStations(Base):
    __tablename__ = 'recent_stations_of_users'
    id = Column(Integer, primary_key=True)
    peer_id = Column(Integer, unique=True)
    stations = Column(JSON)

    def __init__(self, peer_id: int, stations: list[str]):
        self.peer_id = peer_id
        self.stations = stations

    def __repr__(self):
        return '{}(peer_id={}, stations={})'.format(
            self.__class__.__name__, self.peer_id, self.stations
        )

    def add(self, sid):
        tmp_stations = self.stations[:]
        if sid in tmp_stations:
            tmp_stations.remove(sid)
        tmp_stations.append(sid)
        if len(tmp_stations) > 10:
            tmp_stations.pop(0)
        self.stations = tmp_stations


class PopularStations(Base):
    __tablename__ = 'popular_stations'
    id = Column(Integer, primary_key=True)
    sid = Column(String(5))
    call_count = Column(Integer)

    def __init__(self, sid: str, call_count: int):
        self.sid = sid
        self.call_count = call_count

    def __repr__(self):
        return '{}(id={}, sid={}, call_count={})'.format(
            self.__class__.__name__, self.id, self.sid, self.call_count
        )


def get_db_engine(path_to_db):
    engine = sqlalchemy.create_engine('sqlite:///'+path_to_db)
    Base.metadata.create_all(engine)
    return engine
