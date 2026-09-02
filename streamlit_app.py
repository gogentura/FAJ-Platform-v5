#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ — Personal Football Analytics Platform

Главная точка входа Streamlit.

Архитектура:

    Streamlit
        ↓
    FAJ Predictor
        ↓
    Data Collection
        ↓
    FAJ Brain
        ↓
    Prediction Card

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
# SIDEBAR NAVIGATION
# ============================================================

def render_sidebar() -> None:
    """Рендерит боковую панель с навигацией."""
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center; margin-bottom: 1.5rem;">
                <div style="font-size: 2rem;">⚽</div>
                <div style="font-weight: 700; font-size: 1.1rem;">FAJ</div>
                <div style="opacity: 0.5; font-size: 0.8rem;">v12.1</div>
            </div>
            """
        )

        st.markdown("---")

        if st.button(
            "📊 Прогноз",
            use_container_width=True,
            type="primary",
        ):
            st.session_state.faj_page = "predictor"
            st.rerun()

        if st.button(
            "🔬 Диагностика Soccer365",
            use_container_width=True,
        ):
            st.session_state.faj_page = "diagnostic"
            st.rerun()

        st.markdown("---")

        st.caption(
            "FAJ — Personal Football Analyst\n"
            "Личный футбольный аналитик"
        )


# ============================================================
# MAIN PAGE
# ============================================================

def main() -> None:

    # Инициализация состояния страницы
    if "faj_page" not in st.session_state:
        st.session_state.faj_page = "predictor"

    # Рендерим сайдбар
    render_sidebar()

    # Рендерим выбранную страницу
    if st.session_state.faj_page == "predictor":
        try:
            from app.pages.faj_predictor import main as predictor_main
            predictor_main()

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

    elif st.session_state.faj_page == "diagnostic":
        try:
            from app.pages.soccer365_diagnostic import main as diagnostic_main
            diagnostic_main()

        except Exception as exc:
            st.error(
                "❌ Не удалось загрузить диагностику Soccer365."
            )
            with st.expander(
                "Техническая информация",
                expanded=True,
            ):
                st.exception(exc)
            logger.exception(
                "Soccer365 Diagnostic import failed"
            )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()
