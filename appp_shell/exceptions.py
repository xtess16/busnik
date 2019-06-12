"""
    :author: xtess16
"""


class RouteByRidNotFound(Exception):
    """
        Возбуждается когда не найден маршрут по уникальному идентификатору
    """


class StationsCsvNotFound(Exception):
    """
        Возбуждается, когда не получен csv файл остановок с координатами
    """
