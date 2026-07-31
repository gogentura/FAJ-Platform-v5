#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - API Package
"""

from app.api.football_api import FootballAPI
from app.api.football_data import FootballDataAPI
from app.api.ids import IDs

__all__ = ["FootballAPI", "FootballDataAPI", "IDs"]
