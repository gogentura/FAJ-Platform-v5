#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================

Файл:
    app/pages/etc.py

Назначение:
    Streamlit UI для Evolution Training Center.

АРХИТЕКТУРНЫЙ КОНТРАК:

    Streamlit Page
          │
          ▼
    ETCController
          │
          ├── BatchController
          ├── StatisticalAnalyzer
          ├── ETC LearningEngine
          └── LearningMemory
                  │
                  ▼
            FAJDatabase
                  │
                  ▼
             SQLite

ВАЖНО:

    - страница НЕ изменяет database.py;
    - страница НЕ выполняет SQL напрямую;
    - страница НЕ управляет календарём;
    - страница НЕ создаёт прогнозы;
    - вся логика ETC находится в:
          app/etc/etc_controller.py

ENTRY POINT:

    main()

Это обязательно, потому что основной загрузчик FAJ
импортирует:

    from app.pages.etc import main
============================================================
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

import streamlit as st

from app.database import FAJDatabase
from app.etc.etc_controller import ETCController


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
ETC_PAGE_VERSION = "1.0"

PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"


# ============================================================
# DATABASE / CONTROLLER
# ============================================================

@st.cache_resource
def get_etc_controller() -> ETCController:
    """
    Создаёт единый ETCController для Streamlit session.

    Вся работа с БД выполняется через FAJDatabase,
    а ETC-логика — через ETCController.
    """

    db = FAJDatabase()

    return ETCController(
        db=db
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Главная функция страницы ETC.

    Именно эту функцию импортирует основной
    Streamlit-роутер FAJ.
    """

    # ========================================================
    # PAGE CONFIG
    # ========================================================

    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
    )

    # ========================================================
    # HEADER
    # ========================================================

    st.title("🧠 FAJ ETC")

    st.subheader(
        "Evolution Training Center"
    )

    st.caption(
        "Постматчевое обучение и эволюция модели FAJ"
    )

    st.divider()

    # ========================================================
    # INITIALIZE
    # ========================================================

    try:

        controller = get_etc_controller()

    except Exception as exc:

        st.error(
            f"❌ Не удалось инициализировать ETC: {exc}"
        )

        return

    # ========================================================
    # STATUS
    # ========================================================

    st.markdown(
        "### 📡 Состояние ETC"
    )

    try:

        status = controller.status()

        if not isinstance(
            status,
            dict,
        ):
            status = {}

        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "Статус",
                status.get(
                    "status",
                    "unknown",
                ),
            )

        with col2:

            pending = status.get(
                "pending_matches"
            )

            st.metric(
                "Матчей ожидает обучения",
                (
                    "—"
                    if pending is None
                    else pending
                ),
            )

        with col3:

            st.metric(
                "Версия ETC",
                status.get(
                    "version",
                    ETC_PAGE_VERSION,
                ),
            )

    except Exception as exc:

        st.warning(
            f"⚠️ Не удалось получить статус ETC: {exc}"
        )

    st.divider()

    # ========================================================
    # CONTROL PANEL
    # ========================================================

    st.markdown(
        "### ⚙️ Управление ETC"
    )

    col1, col2 = st.columns(2)

    with col1:

        limit = st.number_input(
            "Максимум матчей за один batch",
            min_value=1,
            max_value=1000,
            value=50,
            step=1,
        )

    with col2:

        force = st.checkbox(
            "Force mode",
            value=False,
            help=(
                "Позволяет ETC продолжать обработку "
                "после ошибки отдельного матча."
            ),
        )

    # ========================================================
    # RUN
    # ========================================================

    if st.button(
        "🧠 Запустить ETC",
        type="primary",
        use_container_width=True,
        key="etc_run_button",
    ):

        started = datetime.now()

        with st.spinner(
            "ETC анализирует завершённые матчи..."
        ):

            try:

                result = controller.run(
                    limit=int(limit),
                    force=bool(force),
                )

            except Exception as exc:

                st.error(
                    f"❌ Критическая ошибка ETC: {exc}"
                )

                return

        finished = datetime.now()

        st.session_state[
            "etc_last_result"
        ] = result

        # ----------------------------------------------------
        # OPTIONAL TIMING
        # ----------------------------------------------------

        elapsed = (
            finished - started
        ).total_seconds()

        st.session_state[
            "etc_last_elapsed"
        ] = elapsed

        st.rerun()

    # ========================================================
    # LAST RESULT
    # ========================================================

    result: Optional[
        Dict[str, Any]
    ] = st.session_state.get(
        "etc_last_result"
    )

    if result is not None:

        st.divider()

        st.markdown(
            "### 📊 Последний ETC-run"
        )

        status_value = result.get(
            "status",
            "unknown",
        )

        # ----------------------------------------------------
        # STATUS MESSAGE
        # ----------------------------------------------------

        if status_value == "completed":

            st.success(
                "✅ ETC успешно завершён"
            )

        elif status_value == "nothing_to_process":

            st.info(
                "⏭️ Нет новых завершённых "
                "матчей для обучения"
            )

        elif status_value == "completed_with_errors":

            st.warning(
                "⚠️ ETC завершён с ошибками"
            )

        else:

            st.error(
                f"❌ ETC: {status_value}"
            )

        # ----------------------------------------------------
        # METRICS
        # ----------------------------------------------------

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "Batch",
                result.get(
                    "batch_size",
                    0,
                ),
            )

        with col2:

            st.metric(
                "Обработано",
                result.get(
                    "processed",
                    0,
                ),
            )

        with col3:

            st.metric(
                "Learning events",
                result.get(
                    "learning_events",
                    0,
                ),
            )

        with col4:

            st.metric(
                "Memory events",
                result.get(
                    "memory_events",
                    0,
                ),
            )

        # ----------------------------------------------------
        # ERRORS
        # ----------------------------------------------------

        errors = result.get(
            "errors",
            0,
        )

        if errors:

            st.warning(
                f"⚠️ Ошибок: {errors}"
            )

        # ----------------------------------------------------
        # MESSAGE
        # ----------------------------------------------------

        message = result.get(
            "message"
        )

        if message:

            st.caption(
                str(message)
            )

        # ----------------------------------------------------
        # EXECUTION TIME
        # ----------------------------------------------------

        elapsed = st.session_state.get(
            "etc_last_elapsed"
        )

        if elapsed is not None:

            st.caption(
                f"⏱ Время выполнения: "
                f"{elapsed:.2f} сек."
            )

    # ========================================================
    # MEMORY
    # ========================================================

    st.divider()

    st.markdown(
        "### 🧠 Learning Memory"
    )

    try:

        db = FAJDatabase()

        rows = db.get_learning_memory(
            limit=50
        )

        if rows:

            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
            )

        else:

            st.info(
                "Learning Memory пока пуста."
            )

    except Exception as exc:

        st.warning(
            "⚠️ Не удалось прочитать "
            f"Learning Memory: {exc}"
        )

    # ========================================================
    # ETC ARCHITECTURE
    # ========================================================

    st.divider()

    with st.expander(
        "🏗️ Архитектура ETC",
        expanded=False,
    ):

        st.code(
            """
Streamlit ETC Page
        │
        ▼
      main()
        │
        ▼
ETCController
        │
        ├── BatchController
        │       │
        │       ▼
        │   завершённые матчи
        │
        ├── StatisticalAnalyzer
        │       │
        │       ▼
        │   статистический анализ
        │
        ├── ETC LearningEngine
        │       │
        │       ▼
        │   learning events
        │
        └── LearningMemory
                │
                ▼
        FAJDatabase
                │
                ▼
        SQLite / database.py
            """,
            language="text",
        )

    # ========================================================
    # FOOTER
    # ========================================================

    st.caption(
        f"FAJ Platform v{APP_VERSION} • "
        f"ETC • Evolution Training Center • "
        f"Append-only learning architecture"
    )


# ============================================================
# DIRECT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
