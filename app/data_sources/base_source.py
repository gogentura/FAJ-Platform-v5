# =====================================================
# FAJ Platform v7.0
# Base Data Source
# =====================================================

from abc import ABC, abstractmethod


class BaseSource(ABC):
    """
    Базовый интерфейс любого источника данных FAJ.
    """

    name = "BaseSource"

    @abstractmethod
    def get_calendar(self, league=None):
        """
        Возвращает календарь матчей.
        """
        pass

    @abstractmethod
    def get_results(self, league=None):
        """
        Возвращает завершённые матчи.
        """
        pass

    @abstractmethod
    def get_match_stats(
        self,
        home_team,
        away_team,
        league=None
    ):
        """
        Возвращает статистику матча.
        """
        pass

    @abstractmethod
    def get_xg(
        self,
        home_team,
        away_team,
        league=None
    ):
        """
        Возвращает xG.
        """
        pass

    @abstractmethod
    def get_lineups(
        self,
        team
    ):
        """
        Возвращает состав команды.
        """
        pass

    @abstractmethod
    def get_injuries(
        self,
        team
    ):
        """
        Возвращает травмы.
        """
        pass

    @abstractmethod
    def get_transfers(
        self,
        team
    ):
        """
        Возвращает трансферы.
        """
        pass
