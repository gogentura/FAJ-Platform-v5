#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ — Personal Football Analytics Platform

Главная точка входа Streamlit.

Архитектура:

    Streamlit
        ↓
    Navigation
        ├── FAJ Predictor
        │       ↓
        │   Data Collection
        │       ↓
        │   FAJ Brain
        │       ↓
        │   Prediction Card
        │
        └── Soccer365 Diagnostic
                ↓
            Parser testing

Старая архитектура Round / ETC / Learning / Tour Manager
не используется.

Технические системные модули вроде database,
GitHub DB Sync и bootstrap остаются независимыми
от пользовательского интерфейса.
"""

from __future__ import annotations

import logging
import os
import sys

import streamlit as st


# ============================================================
# PATH
# ============================================================

ROOT_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


# ============================================================
# LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
)

logger = logging.getLogger("FAJ")


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="FAJ — Персональная аналитика",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# GLOBAL CSS
# ============================================================

st.markdown(
    """
    <style>

    /* --------------------------------------------------------
       GENERAL
    -------------------------------------------------------- */

    .block-container {
        max-width: 1400px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    /* --------------------------------------------------------
       HEADER
    -------------------------------------------------------- */

    .faj-header {
        padding: 0.5rem 0 1.2rem 0;
    }

    .faj-title {
        font-size: 2.4rem;
        font-weight: 800;
        margin-bottom: 0.1rem;
    }

    .faj-subtitle {
        font-size: 1.05rem;
        opacity: 0.72;
    }

    /* --------------------------------------------------------
       CARDS
    -------------------------------------------------------- */

    .faj-card {
        border: 1px solid rgba(128, 128, 128, 0.22);
        border-radius: 18px;
        padding: 1.2rem;
        margin: 0.6rem 0;
    }

    /* --------------------------------------------------------
       MOBILE
    -------------------------------------------------------- */

    @media (max-width: 768px) {

        .block-container {
            padding-left: 0.8rem;
            padding-right: 0.8rem;
        }

        .faj-title {
            font-size: 1.9rem;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# NAVIGATION
# ============================================================

def render_navigation() -> str:
    """
    Внутренняя навигация FAJ.

    Важно:
    - Predictor и Diagnostic запускаются независимо.
    - Диагностическая страница не вмешивается
      в основной Predictor.
    """

    st.sidebar.markdown("## ⚽ FAJ")

    page = st.sidebar.radio(
        "Раздел",
        [
            "⚽ FAJ Predictor",
            "🔬 Soccer365 Diagnostic",
        ],
        index=0,
    )

    st.sidebar.markdown("---")

    if page == "🔬 Soccer365 Diagnostic":
        st.sidebar.caption(
            "Тестовый инструмент.\n"
            "Не изменяет основной прогнозный интерфейс."
        )

    return page


# ============================================================
# MAIN PAGE
# ============================================================

def run_predictor() -> None:
    """
    Запуск основной страницы FAJ Predictor.
    """

    try:

        from app.pages.faj_predictor import main as predictor_main

    except Exception as exc:

        st.error(
            "❌ Не удалось загрузить FAJ Predictor."
        )

        with st.expander(
            "Техническая информация",
            expanded=True,
        ):
            st.exception(exc)

        logger.exception(
            "FAJ Predictor import failed"
        )

        return

    try:

        predictor_main()

    except Exception as exc:

        st.error(
            "❌ Ошибка работы FAJ Predictor."
        )

        with st.expander(
            "Техническая информация",
            expanded=True,
        ):
            st.exception(exc)

        logger.exception(
            "FAJ Predictor runtime error"
        )


# ============================================================
# SOCCER365 DIAGNOSTIC
# ============================================================

def run_soccer365_diagnostic() -> None:
    """
    Запуск диагностической страницы Soccer365.

    Диагностика полностью отделена от Predictor.
    """

    try:

        from app.pages.soccer365_diagnostic import (
            main as diagnostic_main
        )

    except Exception as exc:

        st.error(
            "❌ Не удалось загрузить Soccer365 Diagnostic."
        )

        with st.expander(
            "Техническая информация",
            expanded=True,
        ):
            st.exception(exc)

        logger.exception(
            "Soccer365 Diagnostic import failed"
        )

        return

    try:

        diagnostic_main()

    except Exception as exc:

        st.error(
            "❌ Ошибка работы Soccer365 Diagnostic."
        )

        with st.expander(
            "Техническая информация",
            expanded=True,
        ):
            st.exception(exc)

        logger.exception(
            "Soccer365 Diagnostic runtime error"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    page = render_navigation()

    if page == "⚽ FAJ Predictor":

        run_predictor()

    elif page == "🔬 Soccer365 Diagnostic":

        run_soccer365_diagnostic()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
