#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM
MAIN STREAMLIT ENTRYPOINT
============================================================

Новая архитектура FAJ.

Единственный пользовательский поток:

    Streamlit
        ↓
    FAJ Predictor
        ↓
    сбор исторических матчей
        ↓
    нормализация
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
    итоговый прогноз
        ↓
    аналитическая карточка

ВАЖНО
============================================================

Этот файл НЕ содержит:

    ❌ ETC
    ❌ Learning
    ❌ Learning Engine
    ❌ Learning Memory
    ❌ Batch Controller
    ❌ Tour Manager
    ❌ Round Manager
    ❌ старый FAJ Core
    ❌ старую систему обучения
    ❌ старую систему прогноза
    ❌ букмекерские коэффициенты

Этот файл является только ENTRYPOINT.

Вся математическая работа находится в:

    app/pages/faj_predictor.py

и подключаемых математических модулях:

    app/core/form_context.py
    app/core/form_model.py
    app/core/form_win.py
    app/core/defence.py
    app/core/goal_model.py
    app/core/corners_model.py
    app/core/cards_model.py

Database не является частью математического мозга.

SQLite может использоваться только инфраструктурными
компонентами, если это необходимо для хранения данных.

============================================================
"""

from __future__ import annotations

import logging
import os
import sys
import traceback

import streamlit as st


# ============================================================
# APPLICATION PATH
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
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="FAJ Predictor",
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

    /* ======================================================
       GLOBAL
    ====================================================== */

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        visibility: hidden;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 1rem;
        padding-bottom: 2rem;
        padding-left: 1rem;
        padding-right: 1rem;
    }


    /* ======================================================
       FAJ HEADER
    ====================================================== */

    .faj-header {
        display: flex;
        align-items: center;
        justify-content: space-between;

        margin-bottom: 1rem;
        padding: 0.2rem 0;
    }

    .faj-brand {
        display: flex;
        align-items: center;
        gap: 0.65rem;
    }

    .faj-logo {
        width: 42px;
        height: 42px;

        display: flex;
        align-items: center;
        justify-content: center;

        border-radius: 13px;

        background:
            linear-gradient(
                145deg,
                rgba(255,255,255,0.12),
                rgba(255,255,255,0.03)
            );

        border: 1px solid rgba(128,128,128,0.22);

        font-size: 1.45rem;
    }

    .faj-name {
        font-size: 1.55rem;
        font-weight: 800;
        line-height: 1;
        letter-spacing: -0.04em;
    }

    .faj-caption {
        margin-top: 0.2rem;
        font-size: 0.78rem;
        opacity: 0.55;
    }

    .faj-status {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;

        padding: 0.35rem 0.65rem;

        border-radius: 999px;

        font-size: 0.72rem;
        font-weight: 600;

        border: 1px solid rgba(128,128,128,0.2);

        opacity: 0.75;
    }


    /* ======================================================
       MAIN CARDS
    ====================================================== */

    .faj-card {
        border: 1px solid rgba(128,128,128,0.20);
        border-radius: 18px;

        padding: 1rem;

        margin-bottom: 0.75rem;

        background:
            rgba(128,128,128,0.025);

        box-shadow:
            0 4px 18px rgba(0,0,0,0.025);
    }


    /* ======================================================
       COMPACT RESULT CARD
    ====================================================== */

    .faj-result-card {
        border: 1px solid rgba(128,128,128,0.22);
        border-radius: 20px;

        padding: 1rem;

        margin: 0.6rem 0;

        background:
            linear-gradient(
                145deg,
                rgba(128,128,128,0.055),
                rgba(128,128,128,0.018)
            );
    }

    .faj-result-label {
        font-size: 0.72rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        opacity: 0.55;
        margin-bottom: 0.25rem;
    }

    .faj-result-value {
        font-size: 1.55rem;
        font-weight: 800;
        line-height: 1.05;
    }


    /* ======================================================
       SCORE
    ====================================================== */

    .faj-score {
        text-align: center;
        font-size: 2rem;
        font-weight: 900;
        letter-spacing: -0.05em;
    }


    /* ======================================================
       SMALL METRICS
    ====================================================== */

    .faj-metric {
        border: 1px solid rgba(128,128,128,0.18);
        border-radius: 15px;

        padding: 0.7rem 0.75rem;

        min-height: 70px;
    }

    .faj-metric-title {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        opacity: 0.5;
    }

    .faj-metric-value {
        font-size: 1.15rem;
        font-weight: 750;
        margin-top: 0.2rem;
    }


    /* ======================================================
       SECTION TITLES
    ====================================================== */

    .faj-section {
        margin-top: 0.85rem;
        margin-bottom: 0.45rem;

        font-size: 0.85rem;
        font-weight: 750;

        letter-spacing: -0.01em;
    }


    /* ======================================================
       STREAMLIT BUTTONS
    ====================================================== */

    .stButton > button {
        border-radius: 13px;
        min-height: 42px;

        font-weight: 650;

        transition:
            transform 0.12s ease,
            box-shadow 0.12s ease;
    }

    .stButton > button:hover {
        transform: translateY(-1px);
    }


    /* ======================================================
       INPUTS
    ====================================================== */

    div[data-baseweb="select"] > div {
        border-radius: 13px;
    }

    input {
        border-radius: 13px !important;
    }


    /* ======================================================
       EXPANDERS
    ====================================================== */

    .streamlit-expanderHeader {
        border-radius: 13px;
    }


    /* ======================================================
       MOBILE
    ====================================================== */

    @media (max-width: 768px) {

        .block-container {
            padding-top: 0.65rem;
            padding-left: 0.65rem;
            padding-right: 0.65rem;
            padding-bottom: 1rem;
        }

        .faj-header {
            margin-bottom: 0.65rem;
        }

        .faj-logo {
            width: 38px;
            height: 38px;
            border-radius: 11px;
        }

        .faj-name {
            font-size: 1.35rem;
        }

        .faj-caption {
            font-size: 0.7rem;
        }

        .faj-status {
            font-size: 0.65rem;
            padding: 0.3rem 0.5rem;
        }

        .faj-card,
        .faj-result-card {
            border-radius: 16px;
            padding: 0.8rem;
        }

        .faj-result-value {
            font-size: 1.3rem;
        }

        .faj-score {
            font-size: 1.7rem;
        }

        .faj-metric {
            min-height: 62px;
            padding: 0.55rem;
        }

        .faj-metric-value {
            font-size: 1rem;
        }

        /* Убираем лишние боковые отступы
           Streamlit на маленьком экране */

        [data-testid="column"] {
            padding-left: 0.18rem !important;
            padding-right: 0.18rem !important;
        }

        /* Компактные кнопки */

        .stButton > button {
            min-height: 40px;
            font-size: 0.86rem;
        }
    }


    /* ======================================================
       VERY SMALL PHONES
    ====================================================== */

    @media (max-width: 420px) {

        .faj-name {
            font-size: 1.2rem;
        }

        .faj-caption {
            display: none;
        }

        .faj-status {
            display: none;
        }

        .faj-result-value {
            font-size: 1.18rem;
        }

        .faj-score {
            font-size: 1.55rem;
        }
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HEADER
# ============================================================

def render_header() -> None:
    """
    Минимальный мобильный header.

    Никакой старой навигации.
    Никаких ETC/Learning разделов.
    """

    st.markdown(
        """
        <div class="faj-header">

            <div class="faj-brand">

                <div class="faj-logo">
                    ⚽
                </div>

                <div>
                    <div class="faj-name">
                        FAJ
                    </div>

                    <div class="faj-caption">
                        Personal Football Predictor
                    </div>
                </div>

            </div>

            <div class="faj-status">
                ● Predictor
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# PREDICTOR LOADER
# ============================================================

def load_predictor():
    """
    Загружает только новый FAJ Predictor.

    Никаких fallback на старый FAJ Core.
    """

    from app.pages.faj_predictor import main

    return main


# ============================================================
# ERROR SCREEN
# ============================================================

def render_error(
    title: str,
    exc: Exception,
) -> None:

    st.error(title)

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

    render_header()

    try:

        predictor_main = load_predictor()

    except Exception as exc:

        logger.exception(
            "FAJ Predictor import failed"
        )

        render_error(
            "❌ FAJ Predictor не удалось загрузить.",
            exc,
        )

        st.stop()

    try:

        predictor_main()

    except Exception as exc:

        logger.exception(
            "FAJ Predictor runtime error"
        )

        render_error(
            "❌ Ошибка FAJ Predictor.",
            exc,
        )

        st.stop()


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()
