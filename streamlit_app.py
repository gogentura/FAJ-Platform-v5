#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM
STREAMLIT ENTRYPOINT
============================================================

Единственная задача этого файла:

    Streamlit
        ↓
    FAJ Predictor

ВСЯ логика находится в:

    app/pages/faj_predictor.py

Predictor самостоятельно отвечает за:

    • выбор лиги
    • выбор матча
    • команды
    • ссылки
    • сбор исторических матчей
    • Soccer365
    • статистику
    • FormContext
    • FormModel
    • FormWin
    • Defence
    • GoalModel
    • Poisson
    • Score Distribution
    • CornersModel
    • CardsModel
    • итоговый прогноз
    • интерфейс прогнозной страницы

============================================================

ЗАПРЕЩЕНО ЗДЕСЬ:

    ❌ ETC
    ❌ Learning
    ❌ Learning Engine
    ❌ Learning Memory
    ❌ Batch Controller
    ❌ Tour Manager
    ❌ Round Manager
    ❌ старый FAJ Core
    ❌ старый Predictor
    ❌ ручной ввод команд
    ❌ отдельная навигация
    ❌ собственные карточки
    ❌ собственный header

Этот файл НЕ должен конкурировать с Predictor за интерфейс.

============================================================
"""

from __future__ import annotations

import logging
import os
import sys
import traceback


# ============================================================
# PROJECT ROOT
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
# STREAMLIT
# ============================================================

import streamlit as st


# ============================================================
# LOAD ONLY NEW PREDICTOR
# ============================================================

def load_predictor():
    """
    Загружает исключительно новый FAJ Predictor.

    Никаких fallback-механизмов.
    Никакого Legacy.
    Никакого ETC/Learning.
    """

    from app.pages.faj_predictor import main

    return main


# ============================================================
# ERROR SCREEN
# ============================================================

def show_error(exc: Exception) -> None:
    """
    Показывает техническую ошибку только если Predictor
    действительно не смог запуститься.

    В нормальном режиме никакого собственного UI
    здесь нет.
    """

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
    """
    Главный Streamlit entrypoint.

    ВАЖНО:

    Predictor сам владеет страницей.

    Поэтому здесь НЕ вызываются:

        st.set_page_config()
        st.title()
        st.header()
        st.markdown()
        st.columns()
        st.selectbox()
        st.button()

    Это принципиально.

    Иначе EntryPoint начинает вмешиваться
    в интерфейс Predictor.
    """

    try:

        predictor_main = load_predictor()

    except Exception as exc:

        logger.exception(
            "FAJ Predictor import failed"
        )

        show_error(exc)
        st.stop()

        return

    try:

        predictor_main()

    except Exception as exc:

        logger.exception(
            "FAJ Predictor runtime error"
        )

        show_error(exc)
        st.stop()

        return


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()
