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
          ├── PredictionErrorAnalyzer
          ├── ObservedXG
          ├── XGCalibration
          ├── StatisticalAnalyzer
          ├── ETC LearningEngine
          ├── ParameterOptimizer
          └── LearningMemory
                  │
                  ▼
              FAJDatabase
                  │
                  ▼
                 SQLite

ВАЖНО:

    Страница НЕ:

        - изменяет database.py;
        - выполняет SQL напрямую;
        - управляет календарём;
        - создаёт прогнозы;
        - применяет параметры;
        - изменяет model_parameters;
        - изменяет team_passports;
        - изменяет predictions;
        - изменяет historical facts.

    Вся ETC-логика должна находиться
    внутри ETCController и его внутренних модулей.

ENTRY POINT:

    main()

Основной загрузчик FAJ импортирует:

    from app.pages.etc import main

============================================================
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import streamlit as st

from app.database import FAJDatabase
from app.etc.etc_controller import ETCController


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
ETC_PAGE_VERSION = "1.1"

PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"


# ============================================================
# DATABASE / CONTROLLER
# ============================================================

@st.cache_resource
def get_etc_controller() -> ETCController:
    """
    Создаёт ETCController.

    ВАЖНО:

        UI не управляет БД самостоятельно.

    FAJDatabase передаётся в ETCController,
    после чего вся ETC-логика работает через controller.
    """

    db = FAJDatabase()

    return ETCController(
        db=db
    )


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
    """
    Безопасно приводит значение к dict.
    """

    if isinstance(value, dict):
        return value

    return {}


def _safe_list(value: Any) -> List[Any]:
    """
    Безопасно приводит значение к list.
    """

    if isinstance(value, list):
        return value

    return []


def _get_status_value(
    status: Dict[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    """
    Безопасно получает значение статуса.
    """

    value = status.get(key)

    if value is None:
        return default

    return value


# ============================================================
# MEMORY ACCESS
# ============================================================

def _get_learning_memory(
    controller: ETCController,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Получает Learning Memory через ETCController.

    ВАЖНО:

        Страница НЕ вызывает FAJDatabase напрямую
        для чтения Learning Memory.

    Поддерживаются возможные имена controller API,
    чтобы UI не был жёстко связан с одной внутренней
    реализацией ETCController.

    Приоритет:

        1. controller.get_learning_memory()
        2. controller.learning_memory()
        3. controller.memory()

    Если API пока отсутствует — возвращается [].
    """

    methods = (
        "get_learning_memory",
        "learning_memory",
        "memory",
    )

    for method_name in methods:

        method = getattr(
            controller,
            method_name,
            None,
        )

        if not callable(method):
            continue

        try:

            result = method(
                limit=limit
            )

        except TypeError:

            try:
                result = method()

            except Exception:
                continue

        except Exception:
            continue

        if isinstance(result, list):
            return [
                row
                for row in result
                if isinstance(row, dict)
            ]

        if isinstance(result, dict):

            rows = result.get(
                "rows",
                result.get(
                    "memory",
                    result.get(
                        "data",
                        [],
                    ),
                ),
            )

            if isinstance(rows, list):
                return [
                    row
                    for row in rows
                    if isinstance(row, dict)
                ]

    return []


# ============================================================
# HEADER
# ============================================================

def _render_header() -> None:
    """
    Рендерит заголовок ETC.
    """

    st.title("🧠 FAJ ETC")

    st.subheader(
        "Evolution Training Center"
    )

    st.caption(
        "Постматчевый анализ, обучение и "
        "контролируемая эволюция модели FAJ"
    )

    st.divider()


# ============================================================
# STATUS
# ============================================================

def _render_status(
    controller: ETCController,
) -> None:
    """
    Отображает текущее состояние ETC.
    """

    st.markdown(
        "### 📡 Состояние ETC"
    )

    try:

        status = controller.status()

        status = _safe_dict(status)

        col1, col2, col3, col4 = st.columns(4)

        with col1:

            st.metric(
                "Статус",
                _get_status_value(
                    status,
                    "status",
                    "unknown",
                ),
            )

        with col2:

            pending = _get_status_value(
                status,
                "pending_matches",
            )

            st.metric(
                "Ожидает обучения",
                (
                    "—"
                    if pending is None
                    else pending
                ),
            )

        with col3:

            version = _get_status_value(
                status,
                "version",
                ETC_PAGE_VERSION,
            )

            st.metric(
                "Версия ETC",
                version,
            )

        with col4:

            processed = _get_status_value(
                status,
                "processed_matches",
            )

            st.metric(
                "Обработано",
                (
                    "—"
                    if processed is None
                    else processed
                ),
            )

    except Exception as exc:

        st.warning(
            "⚠️ Не удалось получить статус ETC: "
            f"{exc}"
        )

    st.divider()


# ============================================================
# CONTROL PANEL
# ============================================================

def _render_control_panel(
    controller: ETCController,
) -> None:
    """
    Панель управления ETC.
    """

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
            key="etc_batch_limit",
        )

    with col2:

        force = st.checkbox(
            "Force mode",
            value=False,
            key="etc_force_mode",
            help=(
                "Позволяет ETC продолжать обработку "
                "после ошибки отдельного матча."
            ),
        )

    st.markdown("")

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
                    "❌ Критическая ошибка ETC:\n\n"
                    f"{exc}"
                )

                return

        finished = datetime.now()

        elapsed = (
            finished - started
        ).total_seconds()

        st.session_state[
            "etc_last_result"
        ] = _safe_dict(result)

        st.session_state[
            "etc_last_elapsed"
        ] = elapsed

        st.rerun()


# ============================================================
# RESULT
# ============================================================

def _render_last_result() -> None:
    """
    Отображает результат последнего ETC-run.
    """

    result = st.session_state.get(
        "etc_last_result"
    )

    if not isinstance(result, dict):
        return

    st.divider()

    st.markdown(
        "### 📊 Последний ETC-run"
    )

    status_value = result.get(
        "status",
        "unknown",
    )

    # --------------------------------------------------------
    # STATUS MESSAGE
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # OPTIONAL ETC METRICS
    # --------------------------------------------------------

    optional_metrics = (
        (
            "Ошибки",
            "errors",
        ),
        (
            "xG calibration",
            "xg_calibrations",
        ),
        (
            "Proposals",
            "proposals_created",
        ),
    )

    available_metrics = []

    for label, key in optional_metrics:

        if key in result:

            available_metrics.append(
                (
                    label,
                    key,
                    result.get(key, 0),
                )
            )

    if available_metrics:

        st.markdown(
            "#### Дополнительные показатели"
        )

        columns = st.columns(
            len(available_metrics)
        )

        for column, (
            label,
            _key,
            value,
        ) in zip(
            columns,
            available_metrics,
        ):

            with column:

                st.metric(
                    label,
                    value,
                )

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

    errors = result.get(
        "errors",
        0,
    )

    if isinstance(errors, list):

        if errors:

            st.warning(
                f"⚠️ Ошибок: {len(errors)}"
            )

            with st.expander(
                "Показать ошибки",
                expanded=False,
            ):

                for error in errors:

                    st.error(
                        str(error)
                    )

    elif errors:

        st.warning(
            f"⚠️ Ошибок: {errors}"
        )

    # --------------------------------------------------------
    # MESSAGE
    # --------------------------------------------------------

    message = result.get(
        "message"
    )

    if message:

        st.caption(
            str(message)
        )

    # --------------------------------------------------------
    # EXECUTION TIME
    # --------------------------------------------------------

    elapsed = st.session_state.get(
        "etc_last_elapsed"
    )

    if elapsed is not None:

        st.caption(
            f"⏱ Время выполнения: "
            f"{float(elapsed):.2f} сек."
        )


# ============================================================
# LEARNING MEMORY
# ============================================================

def _render_learning_memory(
    controller: ETCController,
) -> None:
    """
    Отображает Learning Memory.

    Страница получает данные только через ETCController.
    """

    st.divider()

    st.markdown(
        "### 🧠 Learning Memory"
    )

    rows = _get_learning_memory(
        controller=controller,
        limit=50,
    )

    if rows:

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Learning Memory пока пуста "
            "или API памяти ещё не подключён "
            "к ETCController."
        )


# ============================================================
# ARCHITECTURE
# ============================================================

def _render_architecture() -> None:
    """
    Показывает архитектуру ETC.
    """

    st.divider()

    with st.expander(
        "🏗️ Архитектура ETC",
        expanded=False,
    ):

        st.code(
            """
                    FAJ Platform
                         │
                         ▼
                 Streamlit ETC Page
                         │
                         ▼
                  ETCController
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
    BatchController  Error Analyzer  Observed xG
          │              │              │
          │              ▼              ▼
          │         Error Patterns  XG Calibration
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                  Statistical Analysis
                         │
                         ▼
                  Learning Analyzer
                         │
                         ▼
                 Parameter Optimizer
                         │
                         ▼
                  Proposal ONLY
                         │
                         ▼
                  Evolution Engine
                         │
                         ▼
                 model_parameters

                         ▲
                         │
                  Learning Memory
                         │
                         ▼
                    FAJDatabase
                         │
                         ▼
                       SQLite
            """,
            language="text",
        )

        st.caption(
            "ETC анализирует факты и формирует "
            "сигналы/предложения. Изменение параметров "
            "не выполняется автоматически этим UI."
        )


# ============================================================
# DIAGNOSTICS
# ============================================================

def _render_diagnostics(
    controller: ETCController,
) -> None:
    """
    Неблокирующая диагностическая информация.

    Помогает увидеть, какие ETC-компоненты реально
    доступны в текущей сборке проекта.
    """

    st.divider()

    with st.expander(
        "🔎 ETC Diagnostics",
        expanded=False,
    ):

        components = (
            "BatchController",
            "PredictionErrorAnalyzer",
            "ObservedXG",
            "XGCalibration",
            "StatisticalAnalyzer",
            "LearningEngine",
            "ParameterOptimizer",
            "LearningMemory",
        )

        rows = []

        for component in components:

            available = False

            controller_name = component

            if component == "LearningEngine":

                available = any(
                    hasattr(
                        controller,
                        name,
                    )
                    for name in (
                        "run_learning",
                        "learning_engine",
                        "learn",
                    )
                )

            elif component == "LearningMemory":

                available = any(
                    callable(
                        getattr(
                            controller,
                            name,
                            None,
                        )
                    )
                    for name in (
                        "get_learning_memory",
                        "learning_memory",
                        "memory",
                    )
                )

            else:

                available = any(
                    hasattr(
                        controller,
                        name,
                    )
                    for name in (
                        component.lower(),
                        f"_{component.lower()}",
                    )
                )

            rows.append(
                {
                    "Component": controller_name,
                    "Controller API": (
                        "available"
                        if available
                        else "not exposed"
                    ),
                }
            )

        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# FOOTER
# ============================================================

def _render_footer() -> None:
    """
    Footer страницы.
    """

    st.caption(
        f"FAJ Platform v{APP_VERSION} • "
        f"ETC Page v{ETC_PAGE_VERSION} • "
        f"Evolution Training Center • "
        f"SQLite • Append-only learning architecture"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Главная функция страницы ETC.

    Именно её импортирует основной Streamlit-роутер:

        from app.pages.etc import main
    """

    # --------------------------------------------------------
    # PAGE CONFIG
    # --------------------------------------------------------

    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon=PAGE_ICON,
        layout="wide",
    )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    _render_header()

    # --------------------------------------------------------
    # INITIALIZE CONTROLLER
    # --------------------------------------------------------

    try:

        controller = get_etc_controller()

    except Exception as exc:

        st.error(
            "❌ Не удалось инициализировать ETC.\n\n"
            f"{exc}"
        )

        st.stop()

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    _render_status(
        controller
    )

    # --------------------------------------------------------
    # CONTROL PANEL
    # --------------------------------------------------------

    _render_control_panel(
        controller
    )

    # --------------------------------------------------------
    # LAST RESULT
    # --------------------------------------------------------

    _render_last_result()

    # --------------------------------------------------------
    # MEMORY
    # --------------------------------------------------------

    _render_learning_memory(
        controller
    )

    # --------------------------------------------------------
    # ARCHITECTURE
    # --------------------------------------------------------

    _render_architecture()

    # --------------------------------------------------------
    # DIAGNOSTICS
    # --------------------------------------------------------

    _render_diagnostics(
        controller
    )

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    _render_footer()


# ============================================================
# DIRECT ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
