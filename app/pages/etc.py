#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================

ФАЙЛ:
    app/pages/etc.py

НАЗНАЧЕНИЕ:
    Streamlit UI для Evolution Training Center.

АРХИТЕКТУРНЫЙ КОНТРАК:

    Streamlit
        │
        ▼
    ETCController
        │
        ▼
    ETCLearningEngine
        │
        ├── BatchController
        ├── StatisticalAnalyzer
        ├── ObservedXG
        ├── PredictionErrorAnalyzer
        ├── XGCalibration
        ├── ClubRatingUpdater
        └── LearningMemory
                │
                ▼
            FAJDatabase
                │
                ▼
               SQLite


ВАЖНО:

    Эта страница является ТОЛЬКО UI.

    Страница НЕ:

        - выполняет SQL;
        - изменяет database.py;
        - изменяет match_results;
        - изменяет predictions;
        - изменяет календарь;
        - создаёт прогнозы;
        - самостоятельно запускает обучение;
        - самостоятельно изменяет model_parameters;
        - самостоятельно изменяет team_passports;
        - самостоятельно пишет team_history;
        - самостоятельно пишет learning_memory.

    Вся бизнес-логика находится внутри ETCController
    и его внутренних компонентов.

ENTRY POINT:

    main()

Основной загрузчик FAJ может использовать:

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
ETC_PAGE_VERSION = "1.2"

PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"


# ============================================================
# DATABASE / CONTROLLER
# ============================================================

@st.cache_resource
def get_etc_controller() -> ETCController:
    """
    Создаёт один экземпляр ETCController.

    UI передаёт database в controller один раз.

    Вся дальнейшая работа с БД выполняется
    внутренними компонентами ETC.
    """

    db = FAJDatabase()

    return ETCController(
        db=db
    )


# ============================================================
# SAFE HELPERS
# ============================================================

def _safe_dict(
    value: Any,
) -> Dict[str, Any]:
    """
    Безопасное преобразование в dict.
    """

    if isinstance(value, dict):
        return value

    return {}


def _safe_list(
    value: Any,
) -> List[Any]:
    """
    Безопасное преобразование в list.
    """

    if isinstance(value, list):
        return value

    return []


def _safe_number(
    value: Any,
    default: Any = 0,
) -> Any:
    """
    Безопасное отображение числового значения.
    """

    if value is None:
        return default

    return value


def _get_status_value(
    status: Dict[str, Any],
    key: str,
    default: Any = None,
) -> Any:
    """
    Безопасное получение значения статуса.
    """

    value = status.get(key)

    if value is None:
        return default

    return value


# ============================================================
# HEADER
# ============================================================

def _render_header() -> None:
    """
    Заголовок страницы ETC.
    """

    st.title("🧠 FAJ ETC")

    st.subheader(
        "Evolution Training Center"
    )

    st.caption(
        "Постматчевый анализ, обучение и "
        "контролируемая эволюция модели FAJ."
    )

    st.divider()


# ============================================================
# STATUS
# ============================================================

def _render_status(
    controller: ETCController,
) -> None:
    """
    Отображает состояние ETC.

    Используется только публичный API controller.status().
    """

    st.markdown(
        "### 📡 Состояние ETC"
    )

    try:

        status = controller.status()

        status = _safe_dict(status)

    except Exception as exc:

        st.error(
            "❌ Ошибка получения состояния ETC:\n\n"
            f"{exc}"
        )

        st.divider()

        return

    col1, col2, col3, col4 = st.columns(4)

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    with col1:

        status_value = _get_status_value(
            status,
            "status",
            "UNKNOWN",
        )

        st.metric(
            "Статус",
            str(status_value),
        )

    # --------------------------------------------------------
    # PENDING
    # --------------------------------------------------------

    with col2:

        pending = _get_status_value(
            status,
            "pending_matches",
        )

        st.metric(
            "Ожидает обучения",
            _safe_number(
                pending,
                "—",
            ),
        )

    # --------------------------------------------------------
    # VERSION
    # --------------------------------------------------------

    with col3:

        version = _get_status_value(
            status,
            "version",
            ETC_PAGE_VERSION,
        )

        st.metric(
            "Версия ETC",
            str(version),
        )

    # --------------------------------------------------------
    # PROCESSED
    # --------------------------------------------------------

    with col4:

        processed = _get_status_value(
            status,
            "processed_matches",
        )

        st.metric(
            "Обработано",
            _safe_number(
                processed,
                "—",
            ),
        )

    st.divider()


# ============================================================
# CONTROL PANEL
# ============================================================

def _render_control_panel(
    controller: ETCController,
) -> None:
    """
    Панель запуска ETC.

    UI только передаёт параметры в ETCController.

    Никаких внутренних ETC-операций здесь нет.
    """

    st.markdown(
        "### ⚙️ Управление ETC"
    )

    col1, col2 = st.columns(2)

    # --------------------------------------------------------
    # BATCH LIMIT
    # --------------------------------------------------------

    with col1:

        limit = st.number_input(
            "Максимум матчей за один batch",
            min_value=1,
            max_value=1000,
            value=50,
            step=1,
            key="etc_batch_limit",
        )

    # --------------------------------------------------------
    # FORCE
    # --------------------------------------------------------

    with col2:

        force = st.checkbox(
            "Force mode",
            value=False,
            key="etc_force_mode",
            help=(
                "Продолжать batch после ошибки "
                "отдельного матча."
            ),
        )

    st.markdown("")

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

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

        # ----------------------------------------------------
        # STORE LAST RESULT
        # ----------------------------------------------------

        st.session_state[
            "etc_last_result"
        ] = _safe_dict(result)

        st.session_state[
            "etc_last_elapsed"
        ] = elapsed

        # ----------------------------------------------------
        # REFRESH
        # ----------------------------------------------------

        st.rerun()


# ============================================================
# LAST RESULT
# ============================================================

def _render_last_result() -> None:
    """
    Отображает результат последнего запуска ETC.
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
    # STATUS
    # --------------------------------------------------------

    if status_value == "completed":

        st.success(
            "✅ ETC успешно завершён."
        )

    elif status_value == "nothing_to_process":

        st.info(
            "⏭️ Нет новых завершённых матчей "
            "для обучения."
        )

    elif status_value == "completed_with_errors":

        st.warning(
            "⚠️ ETC завершён с ошибками."
        )

    elif status_value in (
        "error",
        "failed",
        "failure",
    ):

        st.error(
            f"❌ ETC завершился ошибкой: "
            f"{status_value}"
        )

    else:

        st.warning(
            f"⚠️ ETC вернул статус: "
            f"{status_value}"
        )

    # --------------------------------------------------------
    # MAIN METRICS
    # --------------------------------------------------------

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Batch",
            _safe_number(
                result.get(
                    "batch_size",
                    0,
                )
            ),
        )

    with col2:

        st.metric(
            "Обработано",
            _safe_number(
                result.get(
                    "processed",
                    0,
                )
            ),
        )

    with col3:

        st.metric(
            "Learning events",
            _safe_number(
                result.get(
                    "learning_events",
                    0,
                )
            ),
        )

    with col4:

        st.metric(
            "Memory events",
            _safe_number(
                result.get(
                    "memory_events",
                    0,
                )
            ),
        )

    # --------------------------------------------------------
    # OPTIONAL METRICS
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
        (
            "Rating updates",
            "rating_updates",
        ),
    )

    available_metrics = []

    for label, key in optional_metrics:

        if key not in result:
            continue

        value = result.get(
            key,
            0,
        )

        # errors может быть list
        if key == "errors" and isinstance(
            value,
            list,
        ):
            value = len(value)

        available_metrics.append(
            (
                label,
                value,
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
        "errors"
    )

    if isinstance(errors, list):

        errors = _safe_list(
            errors
        )

        if errors:

            st.warning(
                f"⚠️ Ошибок: {len(errors)}"
            )

            with st.expander(
                "Показать ошибки",
                expanded=False,
            ):

                for index, error in enumerate(
                    errors,
                    start=1,
                ):

                    st.error(
                        f"{index}. {error}"
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
    # REFERENCE
    # --------------------------------------------------------

    reference_id = result.get(
        "reference_id"
    )

    if reference_id:

        st.caption(
            f"Reference ID: {reference_id}"
        )

    # --------------------------------------------------------
    # EXECUTION TIME
    # --------------------------------------------------------

    elapsed = st.session_state.get(
        "etc_last_elapsed"
    )

    if elapsed is not None:

        try:

            elapsed_value = float(
                elapsed
            )

            st.caption(
                f"⏱ Время выполнения: "
                f"{elapsed_value:.2f} сек."
            )

        except (
            TypeError,
            ValueError,
        ):
            pass


# ============================================================
# LEARNING MEMORY
# ============================================================

def _get_learning_memory(
    controller: ETCController,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """
    Получает Learning Memory только через ETCController.

    Страница НЕ обращается к SQLite напрямую.
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

        # ----------------------------------------------------
        # TRY limit API
        # ----------------------------------------------------

        try:

            result = method(
                limit=limit
            )

        except TypeError:

            # ------------------------------------------------
            # TRY no-argument API
            # ------------------------------------------------

            try:

                result = method()

            except Exception:

                continue

        except Exception:

            continue

        # ----------------------------------------------------
        # LIST
        # ----------------------------------------------------

        if isinstance(
            result,
            list,
        ):

            return [
                row
                for row in result
                if isinstance(
                    row,
                    dict,
                )
            ]

        # ----------------------------------------------------
        # DICT WRAPPER
        # ----------------------------------------------------

        if isinstance(
            result,
            dict,
        ):

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

            if isinstance(
                rows,
                list,
            ):

                return [
                    row
                    for row in rows
                    if isinstance(
                        row,
                        dict,
                    )
                ]

    return []


def _render_learning_memory(
    controller: ETCController,
) -> None:
    """
    Отображает последние записи Learning Memory.
    """

    st.divider()

    st.markdown(
        "### 🧠 Learning Memory"
    )

    rows = _get_learning_memory(
        controller=controller,
        limit=50,
    )

    if not rows:

        st.info(
            "Learning Memory пока пуста "
            "или публичный API памяти "
            "не подключён к ETCController."
        )

        return

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# ETC PIPELINE
# ============================================================

def _render_pipeline() -> None:
    """
    Показывает фактический логический цикл ETC.
    """

    st.divider()

    with st.expander(
        "🔄 ETC Pipeline",
        expanded=False,
    ):

        st.code(
            """
MATCH_RESULT
     │
     ▼
BatchController
     │
     ▼
ETCController
     │
     ▼
ETCLearningEngine
     │
     ├── StatisticalAnalyzer
     │
     ├── PredictionErrorAnalyzer
     │
     ├── ObservedXG
     │
     ├── XGCalibration
     │
     └── ClubRatingUpdater
              │
              ├── Team Passport revision
              ├── Team History
              └── Learning Memory
                       │
                       ▼
                  NEXT BATCH
            """,
            language="text",
        )

        st.caption(
            "ETC работает только с завершёнными матчами. "
            "Исторические факты и сохранённые прогнозы "
            "не переписываются."
        )


# ============================================================
# ARCHITECTURE
# ============================================================

def _render_architecture() -> None:
    """
    Архитектурная схема ETC.

    Это информационный блок UI.
    """

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
                  ETCController
                         │
                         ▼
                ETCLearningEngine
                         │
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
   BatchController  Statistical    Error Analysis
                       Analyzer
          │              │              │
          └──────────────┼──────────────┘
                         │
             ┌───────────┼────────────┐
             ▼           ▼            ▼
          ObservedXG  XGCalibration  ClubRating
                                      Updater
                                         │
                                         ▼
                                  LearningMemory
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
            "ETC UI не содержит бизнес-логики. "
            "Все изменения выполняются ETCController "
            "и его внутренними компонентами."
        )


# ============================================================
# DIAGNOSTICS
# ============================================================

def _render_diagnostics(
    controller: ETCController,
) -> None:
    """
    Безопасная диагностика публичного API ETCController.

    Не пытается проверять внутренние реализации
    и не выполняет никаких операций.
    """

    st.divider()

    with st.expander(
        "🔎 ETC Diagnostics",
        expanded=False,
    ):

        public_methods = (
            "status",
            "run",
            "get_learning_memory",
            "learning_memory",
            "memory",
        )

        rows = []

        for method_name in public_methods:

            attribute = getattr(
                controller,
                method_name,
                None,
            )

            rows.append(
                {
                    "API": method_name,
                    "Status": (
                        "available"
                        if callable(attribute)
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

    Основной загрузчик FAJ:

        from app.pages.etc import main
    """

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    _render_header()

    # --------------------------------------------------------
    # CONTROLLER
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
    # PIPELINE
    # --------------------------------------------------------

    _render_pipeline()

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
