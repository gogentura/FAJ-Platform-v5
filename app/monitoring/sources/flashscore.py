# =====================================================
# FAJ Platform v6.2
# Flashscore Source
# Results Monitor
# =====================================================

import logging


logger = logging.getLogger(__name__)


class FlashscoreSource:


    def __init__(self):

        self.name = "Flashscore"



    # ================================================
    # LOAD SOURCE
    # ================================================

    def get_html(self):

        logger.info(
            "Flashscore source initialized"
        )

        return None



    # ================================================
    # PARSE RESULTS
    # ================================================

    def parse_results(self):

        return []
