#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM
MAIN STREAMLIT ENTRYPOINT
============================================================

FAJ Predictor — единственный пользовательский интерфейс.

Архитектура:

    Streamlit
        ↓
    FAJ Predictor
        ↓
    Historical Data
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
    Final Prediction

ВАЖНО:

Этот файл НЕ содержит:

    ETC
    Learning
    Learning Engine
    Learning Memory
    Batch Controller
    Tour Manager
    Round Manager
    Legacy FAJ Core
    Legacy Predictor
    Bookmaker Odds

Этот файл отвечает только за:

    • запуск приложения
    • внешний интерфейс
    • глобальный CSS
    • загрузку FAJ Predictor
    • обработку ошибок

Вся аналитика находится в:

    app/pages/faj_predictor.py

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
    page_title="FAJ",
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

/* ==========================================================
   RESET / APP
   ========================================================== */

#MainMenu {
    visibility: hidden;
}

header {
    visibility: hidden;
}

footer {
    visibility: hidden;
}

[data-testid="stToolbar"] {
    visibility: hidden;
}

[data-testid="stDecoration"] {
    display: none;
}

.block-container {
    max-width: 1160px;
    padding-top: 0.55rem;
    padding-bottom: 1.5rem;
    padding-left: 0.8rem;
    padding-right: 0.8rem;
}


/* ==========================================================
   GLOBAL TYPOGRAPHY
   ========================================================== */

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


/* ==========================================================
   FAJ TOP BAR
   ========================================================== */

.faj-topbar {
    width: 100%;

    display: flex;
    align-items: center;
    justify-content: space-between;

    margin-bottom: 0.8rem;

    padding: 0.25rem 0.1rem;
}

.faj-brand {
    display: flex;
    align-items: center;
    gap: 0.65rem;
}

.faj-brand-icon {
    width: 40px;
    height: 40px;

    display: flex;
    align-items: center;
    justify-content: center;

    border-radius: 12px;

    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,0.13),
            rgba(255,255,255,0.035)
        );

    border: 1px solid rgba(255,255,255,0.11);

    box-shadow:
        0 6px 24px rgba(0,0,0,0.18);

    font-size: 1.25rem;
}

.faj-brand-name {
    font-size: 1.35rem;
    font-weight: 850;

    letter-spacing: -0.055em;

    line-height: 1;
}

.faj-brand-sub {
    margin-top: 0.18rem;

    font-size: 0.66rem;

    letter-spacing: 0.06em;
    text-transform: uppercase;

    opacity: 0.42;
}

.faj-live {
    display: inline-flex;
    align-items: center;
    gap: 0.35rem;

    padding: 0.32rem 0.58rem;

    border-radius: 999px;

    border: 1px solid rgba(255,255,255,0.09);

    background:
        rgba(255,255,255,0.035);

    font-size: 0.65rem;
    font-weight: 700;

    letter-spacing: 0.04em;

    text-transform: uppercase;

    opacity: 0.72;
}

.faj-live-dot {
    width: 6px;
    height: 6px;

    border-radius: 50%;

    background: currentColor;

    box-shadow:
        0 0 8px currentColor;
}


/* ==========================================================
   HERO
   ========================================================== */

.faj-hero {
    position: relative;

    overflow: hidden;

    border-radius: 22px;

    padding: 1.05rem 1.1rem;

    margin-bottom: 0.75rem;

    border: 1px solid rgba(255,255,255,0.10);

    background:
        linear-gradient(
            135deg,
            rgba(255,255,255,0.075),
            rgba(255,255,255,0.025)
        );

    box-shadow:
        0 14px 45px rgba(0,0,0,0.13);
}

.faj-hero::after {
    content: "";

    position: absolute;

    width: 170px;
    height: 170px;

    right: -80px;
    top: -90px;

    border-radius: 50%;

    border: 1px solid rgba(255,255,255,0.07);
}

.faj-hero-kicker {
    font-size: 0.65rem;

    text-transform: uppercase;

    letter-spacing: 0.12em;

    opacity: 0.42;

    margin-bottom: 0.3rem;
}

.faj-hero-title {
    font-size: clamp(
        1.35rem,
        4vw,
        2.15rem
    );

    line-height: 1.03;

    font-weight: 850;

    letter-spacing: -0.055em;
}

.faj-hero-text {
    margin-top: 0.42rem;

    font-size: 0.78rem;

    line-height: 1.4;

    opacity: 0.52;

    max-width: 620px;
}


/* ==========================================================
   UNIVERSAL CARDS
   ========================================================== */

.faj-card {
    border-radius: 18px;

    border: 1px solid rgba(255,255,255,0.09);

    background:
        rgba(255,255,255,0.028);

    padding: 0.85rem;

    margin-bottom: 0.65rem;

    box-shadow:
        0 7px 28px rgba(0,0,0,0.08);
}


/* ==========================================================
   RESULT CARD
   ========================================================== */

.faj-result-card {
    border-radius: 19px;

    border: 1px solid rgba(255,255,255,0.11);

    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,0.075),
            rgba(255,255,255,0.025)
        );

    padding: 0.82rem;

    box-shadow:
        0 9px 32px rgba(0,0,0,0.12);
}

.faj-result-label {
    font-size: 0.61rem;

    text-transform: uppercase;

    letter-spacing: 0.095em;

    opacity: 0.43;
}

.faj-result-value {
    margin-top: 0.22rem;

    font-size: 1.35rem;

    line-height: 1.05;

    font-weight: 850;

    letter-spacing: -0.04em;
}


/* ==========================================================
   SCORE
   ========================================================== */

.faj-score-card {
    text-align: center;

    border-radius: 20px;

    padding: 0.9rem;

    border: 1px solid rgba(255,255,255,0.10);

    background:
        linear-gradient(
            145deg,
            rgba(255,255,255,0.085),
            rgba(255,255,255,0.025)
        );
}

.faj-score-caption {
    font-size: 0.61rem;

    text-transform: uppercase;

    letter-spacing: 0.10em;

    opacity: 0.42;
}

.faj-score {
    margin-top: 0.22rem;

    font-size: clamp(
        1.75rem,
        6vw,
        2.55rem
    );

    font-weight: 900;

    letter-spacing: -0.065em;

    line-height: 1;
}


/* ==========================================================
   METRIC
   ========================================================== */

.faj-metric {
    min-height: 64px;

    padding: 0.65rem 0.7rem;

    border-radius: 15px;

    border: 1px solid rgba(255,255,255,0.075);

    background:
        rgba(255,255,255,0.025);
}

.faj-metric-title {
    font-size: 0.59rem;

    text-transform: uppercase;

    letter-spacing: 0.075em;

    opacity: 0.4;
}

.faj-metric-value {
    margin-top: 0.2rem;

    font-size: 1rem;

    font-weight: 800;

    letter-spacing: -0.025em;
}


/* ==========================================================
   SECTION
   ========================================================== */

.faj-section {
    margin-top: 0.75rem;
    margin-bottom: 0.38rem;

    font-size: 0.72rem;

    font-weight: 800;

    text-transform: uppercase;

    letter-spacing: 0.075em;

    opacity: 0.52;
}


/* ==========================================================
   INPUTS
   ========================================================== */

div[data-baseweb="select"] > div {
    border-radius: 13px !important;

    min-height: 42px;
}

input {
    border-radius: 13px !important;
}

textarea {
    border-radius: 13px !important;
}


/* ==========================================================
   BUTTONS
   ========================================================== */

.stButton > button {
    width: 100%;

    min-height: 43px;

    border-radius: 13px;

    font-weight: 750;

    border: 1px solid rgba(255,255,255,0.10);

    transition:
        transform 0.12s ease,
        box-shadow 0.12s ease;
}

.stButton > button:hover {
    transform: translateY(-1px);

    box-shadow:
        0 7px 20px rgba(0,0,0,0.12);
}


/* ==========================================================
   EXPANDERS
   ========================================================== */

[data-testid="stExpander"] {
    border-radius: 15px !important;

    border: 1px solid rgba(255,255,255,0.075) !important;
}


/* ==========================================================
   DIVIDERS
   ========================================================== */

hr {
    margin-top: 0.65rem !important;
    margin-bottom: 0.65rem !important;

    border-color:
        rgba(255,255,255,0.07) !important;
}


/* ==========================================================
   DATAFRAME
   ========================================================== */

[data-testid="stDataFrame"] {
    border-radius: 15px;
    overflow: hidden;
}


/* ==========================================================
   ALERTS
   ========================================================== */

[data-testid="stAlert"] {
    border-radius: 15px;
}


/* ==========================================================
   MOBILE
   ========================================================== */

@media (max-width: 768px) {

    .block-container {
        max-width: 100%;

        padding-top: 0.35rem;
        padding-left: 0.55rem;
        padding-right: 0.55rem;
        padding-bottom: 1rem;
    }

    .faj-topbar {
        margin-bottom: 0.55rem;
    }

    .faj-brand-icon {
        width: 36px;
        height: 36px;

        border-radius: 11px;
    }

    .faj-brand-name {
        font-size: 1.2rem;
    }

    .faj-brand-sub {
        font-size: 0.58rem;
    }

    .faj-live {
        font-size: 0.58rem;
        padding: 0.28rem 0.45rem;
    }

    .faj-hero {
        border-radius: 18px;

        padding: 0.82rem;

        margin-bottom: 0.55rem;
    }

    .faj-hero-text {
        font-size: 0.7rem;
    }

    .faj-card {
        padding: 0.7rem;

        border-radius: 16px;
    }

    .faj-result-card {
        padding: 0.7rem;

        border-radius: 16px;
    }

    .faj-result-value {
        font-size: 1.15rem;
    }

    .faj-score-card {
        padding: 0.75rem;

        border-radius: 17px;
    }

    .faj-score {
        font-size: 1.75rem;
    }

    .faj-metric {
        min-height: 58px;

        padding: 0.52rem;
    }

    .faj-metric-title {
        font-size: 0.54rem;
    }

    .faj-metric-value {
        font-size: 0.9rem;
    }

    .faj-section {
        margin-top: 0.55rem;

        font-size: 0.64rem;
    }

    [data-testid="column"] {
        padding-left: 0.14rem !important;
        padding-right: 0.14rem !important;
    }

    .stButton > button {
        min-height: 39px;

        font-size: 0.82rem;
    }
}


/* ==========================================================
   VERY SMALL PHONE
   ========================================================== */

@media (max-width: 420px) {

    .faj-live {
        display: none;
    }

    .faj-brand-sub {
        display: none;
    }

    .faj-hero-title {
        font-size: 1.3rem;
    }

    .faj-result-value {
        font-size: 1.05rem;
    }

    .faj-score {
        font-size: 1.6rem;
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
    Новый минимальный FAJ header.

    Никаких:
        ETC
        Learning
        Round Manager
        старой навигации
    """

    st.markdown(
        """
        <div class="faj-topbar">

            <div class="faj-brand">

                <div class="faj-brand-icon">
                    ⚽
                </div>

                <div>
                    <div class="faj-brand-name">
                        FAJ
                    </div>

                    <div class="faj-brand-sub">
                        Football Analytical Predictor
                    </div>
                </div>

            </div>

            <div class="faj-live">
                <span class="faj-live-dot">●</span>
                Predictor
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# HERO
# ============================================================

def render_hero() -> None:
    """
    Небольшой верхний блок.

    Не перегружает экран телефона.
    """

    st.markdown(
        """
        <div class="faj-hero">

            <div class="faj-hero-kicker">
                FAJ ANALYTICAL ENGINE
            </div>

            <div class="faj-hero-title">
                Match intelligence.
            </div>

            <div class="faj-hero-text">
                История команд → форма → сила → голы →
                вероятности → итоговый прогноз.
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# PREDICTOR
# ============================================================

def load_predictor():
    """
    Загружает ТОЛЬКО новый Predictor.

    ВАЖНО:
    никаких fallback на legacy FAJ.
    """

    from app.pages.faj_predictor import main

    return main


# ============================================================
# ERROR
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

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    render_header()

    # --------------------------------------------------------
    # PREDICTOR IMPORT
    # --------------------------------------------------------

    try:

        predictor_main = load_predictor()

    except Exception as exc:

        logger.exception(
            "FAJ Predictor import failed"
        )

        render_error(
            "FAJ Predictor не удалось загрузить.",
            exc,
        )

        st.stop()

    # --------------------------------------------------------
    # PREDICTOR EXECUTION
    # --------------------------------------------------------

    try:

        predictor_main()

    except Exception as exc:

        logger.exception(
            "FAJ Predictor runtime error"
        )

        render_error(
            "Ошибка FAJ Predictor.",
            exc,
        )

        st.stop()


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()
