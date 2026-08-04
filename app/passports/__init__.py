#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Passports Package
Вшитые паспорта команд (НЕ JSON!)
"""

from .rpl_2026_27 import RPL_PASSPORTS_2026_27, TEAM_ALIASES, normalize_team_name
from .passport_schema import validate_passport, PASSPORT_SCHEMA
