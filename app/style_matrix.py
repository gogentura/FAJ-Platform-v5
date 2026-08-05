#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Style Matrix — Матрица стилевых характеристик
Возвращает вектор бонусов для attack, defense, control
"""

STYLE_VECTORS = {
    "possession":  {"attack": 0.0, "defense": 0.0, "control": 1.2, "keeper": 0.0},
    "direct":      {"attack": 1.0, "defense": -0.3, "control": -0.2, "keeper": 0.0},
    "high_press":  {"attack": 0.6, "defense": 0.8, "control": 0.4, "keeper": 0.0},
    "low_block":   {"attack": -0.5, "defense": 1.2, "control": -0.3, "keeper": 0.2},
    "organized":   {"attack": 0.0, "defense": 0.8, "control": 0.6, "keeper": 0.1},
    "physical":    {"attack": 0.8, "defense": 0.2, "control": -0.2, "keeper": 0.0},
    "defensive":   {"attack": -0.3, "defense": 1.0, "control": -0.1, "keeper": 0.3},
    "mixed":       {"attack": 0.0, "defense": 0.0, "control": 0.0, "keeper": 0.0},
}


def get_style_bonus_vector(style: str) -> dict:
    """Возвращает вектор бонусов для attack, defense, control, keeper"""
    return STYLE_VECTORS.get(style, {"attack": 0.0, "defense": 0.0, "control": 0.0, "keeper": 0.0})
