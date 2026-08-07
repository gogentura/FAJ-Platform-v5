#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Engines — Модуль движков FAJ Platform
"""

from .parser_engine import ParserEngine
from .source_adapters.base_adapter import BaseAdapter
from .source_adapters.soccerland_adapter import SoccerlandAdapter

__all__ = [
    'ParserEngine',
    'BaseAdapter',
    'SoccerlandAdapter',
]
