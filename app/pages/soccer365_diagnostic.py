#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SOCCER365 DIAGNOSTIC
============================================================

Изолированная диагностическая страница для проверки Soccer365 Parser.

Цели:
1. Собрать статистику двух тестовых матчей.
2. Показать полный набор фактов, который возвращает parser.
3. Проверить:
   - Удары
   - Удары в створ
   - Заблокированные удары
   - Удары в каркас
   - Угловые
   - Карточки
   - Владение
   - Фолы
   - Передачи
   - Точность передач
   - Большие моменты
   - Атаки
   - Опасные атаки
   - и остальные доступные показатели.
4. Не изменять основную страницу прогнозирования.
5. Не писать результаты в БД.
6. Не выполнять никакую модель или прогноз.

ВАЖНО:
Эта страница является диагностикой RAW DATA FLOW:

Soccer365
    ↓
Soccer365Parser
    ↓
RAW PARSED DATA
    ↓
DIAGNOSTIC UI

Она НЕ должна превращаться в часть FAJ Brain.
============================================================
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import streamlit as st


# ============================================================
# LOGGER
# ============================================================

logger = logging.getLogger(__name__)


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="FAJ — Soccer365 Diagnostic",
    page_icon="🔬",
    layout="wide",
)


# ============================================================
# IMPORT PARSER
# ============================================================

try:
    from app.parsers.soccer365_parser import Soccer365Parser
except Exception as exc:
    st.error("❌ Не удалось импортировать Soccer365Parser")
    st.exception(exc)
    st.stop()


# ============================================================
# HELPERS
# ============================================================

def safe_value(value: Any) -> Any:
    """
    Безопасное отображение значения.

    None остаётся None / "—".
    Никаких преобразований отсутствующих данных в 0.
    """
    if value is None:
        return "—"

    if isinstance(value, float):
        return round(value, 3)

    return value


def flatten_dict(
    data: Any,
    prefix: str = "",
) -> dict[str, Any]:
    """
    Рекурсивно разворачивает вложенный dict.

    Пример:

    {
        "home": {
            "shots": 10
        }
    }

    превращается в:

    home.shots = 10
    """

    result: dict[str, Any] = {}

    if not isinstance(data, dict):
        return result

    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else str(key)

        if isinstance(value, dict):
            result.update(
                flatten_dict(
                    value,
                    prefix=full_key,
                )
            )
        else:
            result[full_key] = value

    return result


def normalize_result(result: Any) -> dict[str, Any]:
    """
    Унификация результата parser независимо от того,
    dict это или объект с __dict__.
    """

    if result is None:
        return {}

    if isinstance(result, dict):
        return result

    if hasattr(result, "model_dump"):
        try:
            return result.model_dump()
        except Exception:
            pass

    if hasattr(result, "dict"):
        try:
            return result.dict()
        except Exception:
            pass

    if hasattr(result, "__dict__"):
        return dict(result.__dict__)

    return {"result": result}


def find_first(
    data: dict[str, Any],
    candidates: list[str],
) -> Any:
    """
    Ищет значение по нескольким возможным ключам.

    Используется ТОЛЬКО для диагностики отображения.
    Никакой математической обработки здесь нет.
    """

    for candidate in candidates:
        if candidate in data:
            return data[candidate]

    return None


def extract_team_stats(
    parsed: dict[str, Any],
    side: str,
) -> dict[str, Any]:
    """
    Пытается извлечь показатели конкретной команды.

    Поддерживает несколько возможных структур parser.

    Ничего не вычисляет.
    """

    stats: dict[str, Any] = {}

    side_prefixes = [
        f"{side}.",
        f"{side}_",
    ]

    flat = flatten_dict(parsed)

    for key, value in flat.items():
        lower_key = key.lower()

        if any(
            lower_key.startswith(prefix.lower())
            for prefix in side_prefixes
        ):
            clean_key = key

            for prefix in side_prefixes:
                if lower_key.startswith(prefix.lower()):
                    clean_key = key[len(prefix):]
                    break

            stats[clean_key] = value

    return stats


# ============================================================
# DIAGNOSTIC FIELD DEFINITIONS
# ============================================================

DIAGNOSTIC_FIELDS = [
    ("goals", "Голы"),
    ("xg", "xG"),
    ("shots", "Удары"),
    ("shots_on_target", "Удары в створ"),
    ("blocked_shots", "Заблокированные удары"),
    ("shots_woodwork", "Удары в каркас"),
    ("saves", "Сейвы"),
    ("possession", "Владение"),
    ("corners", "Угловые"),
    ("free_kicks", "Штрафные"),
    ("throw_ins", "Вбрасывания"),
    ("crosses", "Навесы"),
    ("fouls", "Фолы"),
    ("offsides", "Офсайды"),
    ("yellow_cards", "Жёлтые карточки"),
    ("red_cards", "Красные карточки"),
    ("passes", "Передачи"),
    ("pass_accuracy", "Точность передач"),
    ("tackles", "Отборы"),
    ("clearances", "Выносы"),
    ("big_chances", "Большие моменты"),
    ("attacks", "Атаки"),
    ("dangerous_attacks", "Опасные атаки"),
]


# Возможные варианты названий.
# Нужны именно для диагностики существующей структуры parser.
FIELD_ALIASES = {
    "goals": [
        "goals",
        "score",
    ],
    "xg": [
        "xg",
        "expected_goals",
        "expected_goals_xg",
    ],
    "shots": [
        "shots",
        "home_shots",
        "away_shots",
    ],
    "shots_on_target": [
        "shots_on_target",
        "sot",
        "shots_on_goal",
        "shots_on_target_total",
    ],
    "blocked_shots": [
        "blocked_shots",
        "shots_blocked",
    ],
    "shots_woodwork": [
        "shots_woodwork",
        "woodwork",
        "shots_off_post",
    ],
    "saves": [
        "saves",
        "goalkeeper_saves",
    ],
    "possession": [
        "possession",
    ],
    "corners": [
        "corners",
        "corner_kicks",
    ],
    "free_kicks": [
        "free_kicks",
    ],
    "throw_ins": [
        "throw_ins",
        "throwins",
    ],
    "crosses": [
        "crosses",
    ],
    "fouls": [
        "fouls",
    ],
    "offsides": [
        "offsides",
        "offside",
    ],
    "yellow_cards": [
        "yellow_cards",
        "cards_yellow",
    ],
    "red_cards": [
        "red_cards",
        "cards_red",
    ],
    "passes": [
        "passes",
    ],
    "pass_accuracy": [
        "pass_accuracy",
        "passes_accuracy",
    ],
    "tackles": [
        "tackles",
    ],
    "clearances": [
        "clearances",
    ],
    "big_chances": [
        "big_chances",
        "big_chances_created",
    ],
    "attacks": [
        "attacks",
    ],
    "dangerous_attacks": [
        "dangerous_attacks",
    ],
}


# ============================================================
# PARSER EXECUTION
# ============================================================

def run_parser(url: str) -> dict[str, Any]:
    """
    Запускает существующий Soccer365Parser.

    Важно:
    здесь не реализуется собственный парсер.

    Используется только тот parser, который уже существует
    в проекте.
    """

    parser = Soccer365Parser()

    # --------------------------------------------------------
    # Попытка наиболее вероятных API parser.
    # --------------------------------------------------------

    methods = [
        "parse_match",
        "parse_game",
        "parse",
        "get_match",
        "fetch_match",
    ]

    last_error: Exception | None = None

    for method_name in methods:
        method = getattr(parser, method_name, None)

        if method is None:
            continue

        try:
            result = method(url)
            return normalize_result(result)

        except TypeError as exc:
            last_error = exc
            continue

        except Exception as exc:
            last_error = exc
            logger.exception(
                "Ошибка Soccer365Parser.%s",
                method_name,
            )
            break

    if last_error:
        raise last_error

    raise AttributeError(
        "В Soccer365Parser не найден подходящий метод "
        "parse_match / parse_game / parse / get_match / fetch_match"
    )


# ============================================================
# RAW DATA TABLE
# ============================================================

def build_raw_table(
    parsed: dict[str, Any],
) -> pd.DataFrame:

    flat = flatten_dict(parsed)

    rows = []

    for key, value in sorted(flat.items()):
        rows.append(
            {
                "Поле parser": key,
                "Значение": safe_value(value),
                "Тип": type(value).__name__,
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# TEAM STAT TABLE
# ============================================================

def build_team_table(
    parsed: dict[str, Any],
    side: str,
) -> pd.DataFrame:

    team_stats = extract_team_stats(
        parsed,
        side,
    )

    rows = []

    for field_key, label in DIAGNOSTIC_FIELDS:

        aliases = FIELD_ALIASES.get(
            field_key,
            [field_key],
        )

        value = find_first(
            team_stats,
            aliases,
        )

        rows.append(
            {
                "Показатель": label,
                "Значение": safe_value(value),
                "Найдено": "✅" if value is not None else "❌",
            }
        )

    return pd.DataFrame(rows)


# ============================================================
# SHOTS / SOT SPECIAL TEST
# ============================================================

def render_shots_diagnostic(
    parsed: dict[str, Any],
) -> None:

    st.subheader("🎯 Специальная проверка: Удары / Удары в створ")

    st.info(
        """
        Здесь ничего не рассчитывается.

        Мы просто показываем те значения, которые вернул
        Soccer365 Parser.

        Нужно вручную сравнить их с Soccer365.

        Особенно проверить:

        • Удары
        • Удары в створ
        • Заблокированные удары
        • Удары в каркас
        """
    )

    col1, col2 = st.columns(2)

    for col, side, title in [
        (col1, "home", "🏠 Хозяева"),
        (col2, "away", "✈️ Гости"),
    ]:

        with col:

            st.markdown(f"### {title}")

            stats = extract_team_stats(
                parsed,
                side,
            )

            checks = [
                ("shots", "Удары"),
                ("shots_on_target", "Удары в створ"),
                ("blocked_shots", "Заблокированные удары"),
                ("shots_woodwork", "Удары в каркас"),
            ]

            rows = []

            for key, label in checks:

                value = find_first(
                    stats,
                    FIELD_ALIASES[key],
                )

                rows.append(
                    {
                        "Показатель": label,
                        "Parser": safe_value(value),
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )


# ============================================================
# SINGLE MATCH UI
# ============================================================

def render_match_result(
    index: int,
    url: str,
) -> None:

    st.markdown("---")

    st.header(
        f"Матч #{index}"
    )

    st.code(
        url,
        language="text",
    )

    if not st.button(
        f"🔬 Собрать матч #{index}",
        key=f"parse_{index}",
        width="stretch",
    ):
        return

    with st.spinner("Soccer365 Parser собирает данные..."):

        try:
            parsed = run_parser(url)

        except Exception as exc:

            st.error(
                "❌ Ошибка при работе Soccer365 Parser"
            )

            st.exception(exc)

            return

    st.success(
        "✅ Parser успешно вернул данные"
    )

    # --------------------------------------------------------
    # RAW DATA
    # --------------------------------------------------------

    st.subheader("📦 RAW DATA PARSER")

    raw_df = build_raw_table(
        parsed
    )

    st.caption(
        f"Найдено полей: {len(raw_df)}"
    )

    st.dataframe(
        raw_df,
        width="stretch",
        hide_index=True,
    )

    # --------------------------------------------------------
    # SHOTS TEST
    # --------------------------------------------------------

    render_shots_diagnostic(
        parsed
    )

    # --------------------------------------------------------
    # HOME / AWAY
    # --------------------------------------------------------

    col1, col2 = st.columns(2)

    with col1:

        st.subheader("🏠 Хозяева")

        home_df = build_team_table(
            parsed,
            "home",
        )

        st.dataframe(
            home_df,
            width="stretch",
            hide_index=True,
        )

    with col2:

        st.subheader("✈️ Гости")

        away_df = build_team_table(
            parsed,
            "away",
        )

        st.dataframe(
            away_df,
            width="stretch",
            hide_index=True,
        )

    # --------------------------------------------------------
    # FULL STRUCTURE
    # --------------------------------------------------------

    with st.expander(
        "🔎 Показать полный объект parser"
    ):

        st.json(
            parsed
        )


# ============================================================
# HEADER
# ============================================================

st.title(
    "🔬 FAJ — Soccer365 Parser Diagnostic"
)

st.caption(
    "Изолированная проверка фактических данных Soccer365. "
    "Не участвует в прогнозировании и не изменяет БД."
)


st.warning(
    """
    ⚠️ Диагностическая страница.

    Здесь мы проверяем только качество и полноту данных,
    которые возвращает Soccer365 Parser.

    Никаких формул FAJ здесь нет.
    Никакого обучения здесь нет.
    Никакого изменения параметров здесь нет.
    Никакой записи в database.py здесь нет.
    """
)


# ============================================================
# URL INPUT
# ============================================================

st.subheader(
    "🔗 Тестовые матчи"
)

st.markdown(
    """
    Вставь две ссылки Soccer365.

    Это могут быть наши текущие тестовые матчи.
    """
)

url1 = st.text_input(
    "Матч №1",
    placeholder="https://soccer365.ru/games/...",
)

url2 = st.text_input(
    "Матч №2",
    placeholder="https://soccer365.ru/games/...",
)


# ============================================================
# QUICK BUTTON
# ============================================================

col1, col2 = st.columns(2)

with col1:

    if st.button(
        "🔬 Собрать оба матча",
        width="stretch",
        type="primary",
    ):

        if not url1 or not url2:

            st.error(
                "Нужно указать обе ссылки."
            )

        else:

            st.session_state[
                "diagnostic_run_all"
            ] = True


with col2:

    if st.button(
        "🧹 Очистить",
        width="stretch",
    ):

        st.session_state.pop(
            "diagnostic_run_all",
            None,
        )

        st.rerun()


# ============================================================
# RUN
# ============================================================

if st.session_state.get(
    "diagnostic_run_all",
    False,
):

    if url1:

        render_match_result(
            1,
            url1,
        )

    if url2:

        render_match_result(
            2,
            url2,
        )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    """
FAJ Diagnostic Layer
Soccer365 Parser → RAW FACTS → Manual Verification

Следующий этап после проверки:
DATA MAP → FORM FEATURES → математические модели.
"""
)
