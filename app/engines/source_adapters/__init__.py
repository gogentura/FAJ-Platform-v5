#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Source Adapters — адаптеры для различных источников данных
"""

from .base_adapter import BaseAdapter
from .soccerland_adapter import SoccerlandAdapter

__all__ = [
    'BaseAdapter',
    'SoccerlandAdapter',
]
