# =====================================================
# FAJ Platform v6.3
# Source Manager
#
# Единая точка доступа ко всем источникам
# =====================================================

import logging

from app.monitoring.sources.soccer365 import Soccer365Source

logger = logging.getLogger(__name__)


class SourceManager:

    def __init__(self):

        self.calendar_sources = [

            Soccer365Source(),

        ]

        self.result_sources = [

            Soccer365Source(),

        ]

        self.statistics_sources = [

            # Soccer365StatsSource()
            # SofaScoreSource()
            # LiveResultSource()

        ]

    # ==================================================
    # КАЛЕНДАРЬ
    # ==================================================

    def get_calendar(self):

        for source in self.calendar_sources:

            try:

                fixtures = source.parse_calendar()

                if fixtures:

                    logger.info(

                        f"Calendar loaded from "
                        f"{source.__class__.__name__}"

                    )

                    return fixtures

            except Exception as e:

                logger.exception(e)

        return []

    # ==================================================
    # РЕЗУЛЬТАТЫ
    # ==================================================

    def get_results(self):

        for source in self.result_sources:

            try:

                if hasattr(source, "parse_results"):

                    results = source.parse_results()

                    if results:

                        logger.info(

                            f"Results loaded from "
                            f"{source.__class__.__name__}"

                        )

                        return results

            except Exception as e:

                logger.exception(e)

        return []

    # ==================================================
    # СТАТИСТИКА
    # ==================================================

    def get_statistics(

        self,

        fixture

    ):

        for source in self.statistics_sources:

            try:

                stats = source.load_statistics(

                    fixture

                )

                if stats:

                    logger.info(

                        f"Statistics loaded from "
                        f"{source.__class__.__name__}"

                    )

                    return stats

            except Exception as e:

                logger.exception(e)

        return None
