#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM
MAIN STREAMLIT ENTRYPOINT
============================================================

FAJ Predictor — единственная основная пользовательская страница.

ARCHITECTURE
------------------------------------------------------------

Streamlit
    ↓
FAJ Predictor
    ↓
historical matches
    ↓
FormContext
    ↓
FormModel
    ↓
FormWin
    ↓
Defence
    ↓
GoalModel
    ↓
Poisson
    ↓
Score Distribution
    ↓
CornersModel
    ↓
CardsModel
    ↓
FINAL PREDICTION


ВАЖНО
------------------------------------------------------------

Этот файл НЕ занимается:

    ❌ командами
    ❌ матчами
    ❌ Soccer365
    ❌ сбором статистики
    ❌ FormContext
    ❌ FormModel
    ❌ GoalModel
    ❌ расчётом вероятностей
    ❌ прогнозом
    ❌ сохранением прогноза

Всё это находится в:

    app/pages/faj_predictor.py


Этот файл является ТОЛЬКО:

    Streamlit entrypoint
    + глобальный внешний стиль
    + запуск FAJ Predictor

============================================================
"""

from __future__ import annotations

import logging
import os
import sys
import traceback

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
    format=(
        "%(asctime)s | "
        "%(levelname)s | "
        "%(name)s | "
        "%(message)s"
    ),
)

logger = logging.getLogger("FAJ")


# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="FAJ Predictor",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ============================================================
# GLOBAL UI
# ============================================================

st.markdown(
    """
    <style>

    /* =====================================================
       STREAMLIT CLEANUP
       ===================================================== */

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        visibility: hidden;
    }

    [data-testid="stToolbar"] {
        display: none;
    }

    [data-testid="stDecoration"] {
        display: none;
    }


    /* =====================================================
       MAIN CONTAINER
       ===================================================== */

    .block-container {
        max-width: 1180px;

        padding-top: 0.45rem;
        padding-bottom: 1.5rem;

        padding-left: 0.75rem;
        padding-right: 0.75rem;
    }


    /* =====================================================
       TYPOGRAPHY
       ===================================================== */

    html,
    body,
    [class*="css"] {

        font-family:
            -apple-system,
            BlinkMacSystemFont,
            "SF Pro Display",
            "SF Pro Text",
            Inter,
            system-ui,
            sans-serif;
    }


    /* =====================================================
       STREAMLIT ELEMENT SPACING
       ===================================================== */

    [data-testid="stVerticalBlock"] {
        gap: 0.45rem;
    }

    hr {
        margin-top: 0.5rem !important;
        margin-bottom: 0.5rem !important;

        border-color:
            rgba(128,128,128,0.16) !important;
    }


    /* =====================================================
       INPUTS
       ===================================================== */

    div[data-baseweb="select"] > div {

        border-radius: 12px !important;

        min-height: 40px;
    }

    input {

        border-radius: 12px !important;
    }

    textarea {

        border-radius: 12px !important;
    }


    /* =====================================================
       BUTTONS
       ===================================================== */

    .stButton > button {

        min-height: 40px;

        border-radius: 12px;

        font-weight: 700;

        transition:
            transform 0.12s ease,
            box-shadow 0.12s ease;
    }

    .stButton > button:hover {

        transform: translateY(-1px);

        box-shadow:
            0 6px 18px rgba(0,0,0,0.10);
    }


    /* =====================================================
       LINKS
       ===================================================== */

    a {

        text-decoration: none;
    }


    /* =====================================================
       EXPANDERS
       ===================================================== */

    [data-testid="stExpander"] {

        border-radius: 14px !important;

        border: 1px solid
            rgba(128,128,128,0.16) !important;
    }


    /* =====================================================
       ALERTS
       ===================================================== */

    [data-testid="stAlert"] {

        border-radius: 14px;
    }


    /* =====================================================
       DATAFRAME
       ===================================================== */

    [data-testid="stDataFrame"] {

        border-radius: 14px;

        overflow: hidden;
    }


    /* =====================================================
       MOBILE
       ===================================================== */

    @media (max-width: 768px) {

        .block-container {

            max-width: 100%;

            padding-top: 0.25rem;
            padding-bottom: 0.8rem;

            padding-left: 0.45rem;
            padding-right: 0.45rem;
        }


        [data-testid="stVerticalBlock"] {

            gap: 0.3rem;
        }


        [data-testid="column"] {

            padding-left: 0.12rem !important;
            padding-right: 0.12rem !important;
        }


        .stButton > button {

            min-height: 38px;

            font-size: 0.82rem;
        }
    }


    /* =====================================================
       SMALL IPHONE
       ===================================================== */

    @media (max-width: 420px) {

        .block-container {

            padding-left: 0.35rem;
            padding-right: 0.35rem;
        }

        [data-testid="column"] {

            padding-left: 0.08rem !important;
            padding-right: 0.08rem !important;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# LOAD PREDICTOR
# ============================================================

def load_predictor():
    """
    Загружает ТОЛЬКО новый FAJ Predictor.

    Никаких fallback.
    Никаких старых страниц.
    Никакого Legacy FAJ.
    """

    from app.pages.faj_predictor import main

    return main


# ============================================================
# ERROR
# ============================================================

def render_error(exc: Exception) -> None:

    st.error(
        "FAJ Predictor не удалось запустить."
    )

    with st.expander(
        "Техническая информация",
        expanded=False,
    ):

        st.code(
            "".join(
                traceback.format_exception(
                    type(exc),
                    exc,
                    exc.__traceback__,
                )
            ),
            language="text",
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    try:

        predictor_main = load_predictor()

    except Exception as exc:

        logger.exception(
            "Unable to import FAJ Predictor"
        )

        render_error(exc)

        st.stop()


    try:

        # ----------------------------------------------------
        # ВАЖНО:
        #
        # Здесь НЕТ никакого дополнительного интерфейса.
        #
        # Predictor полностью контролирует страницу:
        #
        # команды
        # матчи
        # ссылки
        # статистику
        # уточнения
        # расчёт
        # прогноз
        # ----------------------------------------------------

        predictor_main()

    except Exception as exc:

        logger.exception(
            "FAJ Predictor runtime error"
        )

        render_error(exc)

        st.stop()


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()
