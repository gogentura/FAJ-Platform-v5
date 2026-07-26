# =====================================================
# FAJ Platform v7.0
# DataHub
#
# Единая точка получения данных
# =====================================================

import logging

from app.data_sources.soccer365_calendar import Soccer365Calendar
from app.data_sources.soccer365_results import Soccer365Results

from app.data_sources.fotmob_xg import FotmobXG
from app.data_sources.fbref_stats import FBrefStats

from app.data_sources.transfermarkt_lineups import TransfermarktLineups
from app.data_sources.transfermarkt_injuries import TransfermarktInjuries
from app.data_sources.transfermarkt_transfers import TransfermarktTransfers

from app.data_sources.api_football import APIFootball


logger = logging.getLogger(__name__)


class DataHub:

    def __init__(self):

        self.calendar = Soccer365Calendar()

        self.results = Soccer365Results()

        self.xg = FotmobXG()

        self.stats = FBrefStats()

        self.lineups = TransfermarktLineups()

        self.injuries = TransfermarktInjuries()

        self.transfers = TransfermarktTransfers()

        self.api = APIFootball()

    # ==================================================
    # CALENDAR
    # ==================================================

    def get_calendar(self, league):

        if league == "RPL":

            return self.calendar.get_calendar()

        return self.api.get_calendar(league)

    # ==================================================
    # RESULTS
    # ==================================================

    def get_results(self, league):

        if league == "RPL":

            return self.results.get_results()

        return self.api.get_results(league)

    # ==================================================
    # xG
    # ==================================================

    def get_xg(

        self,

        home_team,

        away_team,

        league

    ):

        if league == "RPL":

            return self.xg.get_xg(

                home_team,

                away_team

            )

        return self.api.get_xg(

            home_team,

            away_team,

            league

        )

    # ==================================================
    # MATCH STATS
    # ==================================================

    def get_stats(

        self,

        home_team,

        away_team,

        league

    ):

        if league == "RPL":

            return self.stats.get_match_stats(

                home_team,

                away_team

            )

        return self.api.get_match_stats(

            home_team,

            away_team,

            league

        )

    # ==================================================
    # LINEUPS
    # ==================================================

    def get_lineup(

        self,

        team,

        league="RPL"

    ):

        if league == "RPL":

            return self.lineups.get_lineups(team)

        return self.api.get_lineups(team)

    # ==================================================
    # INJURIES
    # ==================================================

    def get_injuries(

        self,

        team,

        league="RPL"

    ):

        if league == "RPL":

            return self.injuries.get_injuries(team)

        return self.api.get_injuries(team)

    # ==================================================
    # TRANSFERS
    # ==================================================

    def get_transfers(

        self,

        team,

        league="RPL"

    ):

        if league == "RPL":

            return self.transfers.get_transfers(team)

        return self.api.get_transfers(team)

    # ==================================================
    # FULL MATCH PACKAGE
    # ==================================================

    def get_full_match_data(

        self,

        home_team,

        away_team,

        league

    ):

        return {

            "xg": self.get_xg(

                home_team,

                away_team,

                league

            ),

            "stats": self.get_stats(

                home_team,

                away_team,

                league

            )

        }
