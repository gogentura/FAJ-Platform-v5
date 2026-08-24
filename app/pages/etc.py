#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================

ФАЙЛ:
    app/pages/etc.py

ETC PAGE v2.0
============================================================

НАЗНАЧЕНИЕ
-----------

Полноценный Streamlit Dashboard Evolution Training Center.

UI показывает:

    • состояние ETC;
    • запуск обучения;
    • последний batch;
    • Learning Events;
    • Memory Events;
    • обработанные матчи;
    • ошибки;
    • Learning Memory;
    • типы learning events;
    • динамику обучения;
    • xG calibration;
    • evolution statistics;
    • pipeline;
    • architecture;
    • diagnostics.

АРХИТЕКТУРНЫЙ КОНТРАК
----------------------

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
    ├── PredictionErrorAnalyzer
    ├── ObservedXG
    ├── XGCalibration
    ├── ClubRatingUpdater
    └── LearningMemory
            │
            ▼
        FAJDatabase
            │
            ▼
           SQLite


ВАЖНО
------

Эта страница:

    НЕ выполняет SQL;

    НЕ изменяет database.py;

    НЕ изменяет match_results;

    НЕ изменяет predictions;

    НЕ изменяет календарь;

    НЕ создаёт прогнозы;

    НЕ запускает обучение напрямую;

    НЕ пишет learning_memory напрямую;

    НЕ изменяет model_parameters;

    НЕ изменяет team_passports;

    НЕ изменяет team_history.

Вся бизнес-логика принадлежит ETCController
и внутренним компонентам ETC.


ENTRY POINT
-----------

    main()

Совместимый импорт:

    from app.pages.etc import main

============================================================
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st

from app.database import FAJDatabase
from app.etc.etc_controller import ETCController


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
ETC_PAGE_VERSION = "2.0"

PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"


# ============================================================
# DATABASE / CONTROLLER
# ============================================================

@st.cache_resource
def get_etc_controller() -> ETCController:
    """
    Создаёт ETCController.

    UI не работает с SQLite напрямую.
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

    if isinstance(value, dict):
        return value

    return {}


def _safe_list(
    value: Any,
) -> List[Any]:

    if isinstance(value, list):
        return value

    return []


def _number(
    value: Any,
    default: float = 0,
) -> float:

    try:

        if value is None:
            return default

        return float(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


def _int(
    value: Any,
    default: int = 0,
) -> int:

    try:

        if value is None:
            return default

        return int(value)

    except (
        TypeError,
        ValueError,
    ):

        return default


def _call_public_api(
    controller: ETCController,
    names: List[str],
    **kwargs: Any,
) -> Any:
    """
    Безопасно вызывает первый существующий
    публичный метод ETCController.

    UI не зависит от конкретной внутренней
    реализации Controller.
    """

    for name in names:

        method = getattr(
            controller,
            name,
            None,
        )

        if not callable(method):
            continue

        try:

            return method(
                **kwargs
            )

        except TypeError:

            try:

                return method()

            except Exception:
                continue

        except Exception:

            continue

    return None


def _extract_rows(
    value: Any,
) -> List[Dict[str, Any]]:
    """
    Нормализует различные формы ответа Controller.
    """

    if isinstance(
        value,
        list,
    ):

        return [
            item
            for item in value
            if isinstance(
                item,
                dict,
            )
        ]

    if isinstance(
        value,
        dict,
    ):

        for key in (
            "rows",
            "data",
            "memory",
            "events",
            "history",
            "items",
            "records",
        ):

            rows = value.get(key)

            if isinstance(
                rows,
                list,
            ):

                return [
                    item
                    for item in rows
                    if isinstance(
                        item,
                        dict,
                    )
                ]

    return []


# ============================================================
# HEADER
# ============================================================

def _render_header() -> None:

    st.title("🧠 FAJ ETC")

    st.subheader(
        "Evolution Training Center"
    )

    st.caption(
        "Центр постматчевого анализа, "
        "обучения и контролируемой эволюции FAJ."
    )

    st.divider()


# ============================================================
# STATUS
# ============================================================

def _render_status(
    controller: ETCController,
) -> Dict[str, Any]:

    st.markdown(
        "### 📡 Состояние ETC"
    )

    try:

        status = _safe_dict(
            controller.status()
        )

    except Exception as exc:

        st.error(
            f"❌ Ошибка получения состояния ETC: {exc}"
        )

        return {}

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:

        st.metric(
            "Статус",
            str(
                status.get(
                    "status",
                    "UNKNOWN",
                )
            ),
        )

    with col2:

        st.metric(
            "Ожидает",
            status.get(
                "pending_matches",
                "—",
            ),
        )

    with col3:

        st.metric(
            "Обработано",
            status.get(
                "processed_matches",
                "—",
            ),
        )

    with col4:

        st.metric(
            "Learning Events",
            status.get(
                "learning_events",
                "—",
            ),
        )

    with col5:

        st.metric(
            "ETC version",
            str(
                status.get(
                    "version",
                    ETC_PAGE_VERSION,
                )
            ),
        )

    st.divider()

    return status


# ============================================================
# CONTROL PANEL
# ============================================================

def _render_control_panel(
    controller: ETCController,
) -> None:

    st.markdown(
        "### ⚙️ Управление ETC"
    )

    col1, col2 = st.columns(2)

    with col1:

        limit = st.number_input(
            "Максимум матчей за batch",
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
                "Продолжать batch после ошибки "
                "отдельного матча."
            ),
        )

    if st.button(
        "🧠 ЗАПУСТИТЬ ОБУЧЕНИЕ ETC",
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

        elapsed = (
            datetime.now() - started
        ).total_seconds()

        st.session_state[
            "etc_last_result"
        ] = _safe_dict(result)

        st.session_state[
            "etc_last_elapsed"
        ] = elapsed

        st.session_state[
            "etc_refresh"
        ] = datetime.now().isoformat()

        st.rerun()


# ============================================================
# LAST RESULT
# ============================================================

def _render_last_result() -> None:

    result = st.session_state.get(
        "etc_last_result"
    )

    if not isinstance(
        result,
        dict,
    ):
        return

    st.divider()

    st.markdown(
        "### 📊 Последний ETC Batch"
    )

    status = str(
        result.get(
            "status",
            "unknown",
        )
    )

    if status == "completed":

        st.success(
            "✅ ETC batch полностью завершён."
        )

    elif status in (
        "nothing_to_process",
        "empty",
    ):

        st.info(
            "⏭️ Новых матчей для обучения нет."
        )

    elif status in (
        "completed_with_errors",
        "partial",
    ):

        st.warning(
            "⚠️ Batch завершён частично."
        )

    elif status in (
        "failed",
        "error",
        "failure",
    ):

        st.error(
            f"❌ ETC завершился ошибкой: {status}"
        )

    else:

        st.warning(
            f"⚠️ ETC status: {status}"
        )

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:

        st.metric(
            "Batch",
            _int(
                result.get(
                    "batch_size",
                    result.get(
                        "total",
                        0,
                    ),
                )
            ),
        )

    with col2:

        st.metric(
            "Обработано",
            _int(
                result.get(
                    "processed",
                    0,
                )
            ),
        )

    with col3:

        st.metric(
            "Ошибки",
            len(
                result.get(
                    "errors",
                    [],
                )
            )
            if isinstance(
                result.get("errors", []),
                list,
            )
            else _int(
                result.get(
                    "errors",
                    0,
                )
            ),
        )

    with col4:

        st.metric(
            "Learning Events",
            _int(
                result.get(
                    "learning_events",
                    0,
                )
            ),
        )

    with col5:

        st.metric(
            "Memory Events",
            _int(
                result.get(
                    "memory_events",
                    len(
                        result.get(
                            "memory_ids",
                            [],
                        )
                    )
                    if isinstance(
                        result.get(
                            "memory_ids",
                            [],
                        ),
                        list,
                    )
                    else 0,
                )
            ),
        )

    elapsed = st.session_state.get(
        "etc_last_elapsed"
    )

    if elapsed is not None:

        st.caption(
            f"⏱ Время выполнения: "
            f"{float(elapsed):.2f} сек."
        )

    errors = result.get(
        "errors"
    )

    if errors:

        with st.expander(
            "❌ Ошибки batch",
            expanded=False,
        ):

            if isinstance(
                errors,
                list,
            ):

                for index, error in enumerate(
                    errors,
                    start=1,
                ):

                    st.error(
                        f"{index}. {error}"
                    )

            else:

                st.error(
                    str(errors)
                )


# ============================================================
# LOAD LEARNING MEMORY
# ============================================================

def _get_learning_memory(
    controller: ETCController,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    """
    Только публичный API ETCController.
    """

    result = _call_public_api(
        controller,
        [
            "get_learning_memory",
            "learning_memory",
            "memory",
        ],
        limit=limit,
    )

    return _extract_rows(
        result
    )


# ============================================================
# LEARNING MEMORY TABLE
# ============================================================

def _render_learning_memory(
    rows: List[Dict[str, Any]],
) -> None:

    st.markdown(
        "### 🧠 Learning Memory"
    )

    if not rows:

        st.info(
            "Learning Memory пока не содержит "
            "доступных для отображения событий."
        )

        return

    df = pd.DataFrame(
        rows
    )

    st.caption(
        f"Доступно событий: {len(df)}"
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# LEARNING EVENTS DISTRIBUTION
# ============================================================

def _render_event_distribution(
    rows: List[Dict[str, Any]],
) -> None:

    st.markdown(
        "### 🧩 Структура обучения"
    )

    if not rows:

        st.info(
            "Нет данных для построения графика."
        )

        return

    event_types = []

    for row in rows:

        event_type = (
            row.get(
                "event_type"
            )
            or row.get(
                "feature"
            )
            or row.get(
                "type"
            )
            or "unknown"
        )

        event_types.append(
            str(event_type)
        )

    counts = Counter(
        event_types
    )

    if not counts:
        return

    df = pd.DataFrame(
        {
            "Event": list(
                counts.keys()
            ),
            "Count": list(
                counts.values()
            ),
        }
    )

    df = df.sort_values(
        "Count",
        ascending=False,
    )

    st.bar_chart(
        df.set_index(
            "Event"
        )
    )


# ============================================================
# LEARNING TIMELINE
# ============================================================

def _render_learning_timeline(
    rows: List[Dict[str, Any]],
) -> None:

    st.markdown(
        "### 📈 Динамика обучения"
    )

    if not rows:

        st.info(
            "Недостаточно данных для динамики."
        )

        return

    timestamp_keys = (
        "created_at",
        "timestamp",
        "event_time",
        "date",
    )

    timestamp_key = None

    for key in timestamp_keys:

        if any(
            key in row
            for row in rows
        ):

            timestamp_key = key
            break

    if timestamp_key is None:

        st.info(
            "У Learning Memory нет временной "
            "метки для построения timeline."
        )

        return

    data = []

    for row in rows:

        raw_date = row.get(
            timestamp_key
        )

        if not raw_date:
            continue

        try:

            date_value = pd.to_datetime(
                raw_date
            )

        except Exception:

            continue

        data.append(
            {
                "date": date_value,
            }
        )

    if not data:

        st.info(
            "Временные данные обучения "
            "не удалось распознать."
        )

        return

    df = pd.DataFrame(
        data
    )

    timeline = (
        df.groupby(
            df["date"].dt.date
        )
        .size()
        .rename(
            "learning_events"
        )
        .to_frame()
    )

    st.line_chart(
        timeline
    )


# ============================================================
# EVOLUTION METRICS
# ============================================================

def _render_evolution_metrics(
    rows: List[Dict[str, Any]],
) -> None:

    st.markdown(
        "### 🧬 Метрики эволюции модели"
    )

    if not rows:

        st.info(
            "Нет learning events."
        )

        return

    impacts = []
    confidences = []
    deltas = []

    for row in rows:

        if row.get(
            "impact"
        ) is not None:

            impacts.append(
                _number(
                    row.get(
                        "impact"
                    )
                )
            )

        if row.get(
            "confidence"
        ) is not None:

            confidences.append(
                _number(
                    row.get(
                        "confidence"
                    )
                )
            )

        if row.get(
            "delta"
        ) is not None:

            deltas.append(
                _number(
                    row.get(
                        "delta"
                    )
                )
            )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Learning Events",
            len(rows),
        )

    with col2:

        st.metric(
            "Средний impact",
            (
                f"{sum(impacts) / len(impacts):.4f}"
                if impacts
                else "—"
            ),
        )

    with col3:

        st.metric(
            "Средняя confidence",
            (
                f"{sum(confidences) / len(confidences):.4f}"
                if confidences
                else "—"
            ),
        )

    with col4:

        st.metric(
            "Изменений delta",
            len(deltas),
        )

    if deltas:

        df = pd.DataFrame(
            {
                "delta": deltas
            }
        )

        st.line_chart(
            df
        )


# ============================================================
# MATCH LEARNING
# ============================================================

def _render_match_learning(
    rows: List[Dict[str, Any]],
) -> None:

    st.markdown(
        "### ⚽ Обучение по матчам"
    )

    if not rows:

        st.info(
            "Нет данных."
        )

        return

    match_ids = []

    for row in rows:

        reference = row.get(
            "reference_id"
        )

        if reference is None:
            continue

        try:

            match_ids.append(
                int(reference)
            )

        except (
            TypeError,
            ValueError,
        ):

            continue

    if not match_ids:

        st.info(
            "В памяти нет reference_id матчей."
        )

        return

    counts = Counter(
        match_ids
    )

    df = pd.DataFrame(
        {
            "match_id": list(
                counts.keys()
            ),
            "events": list(
                counts.values()
            ),
        }
    )

    df = df.sort_values(
        "events",
        ascending=False,
    )

    st.bar_chart(
        df.set_index(
            "match_id"
        )
    )


# ============================================================
# XG / CALIBRATION
# ============================================================

def _get_calibration_data(
    controller: ETCController,
) -> List[Dict[str, Any]]:

    result = _call_public_api(
        controller,
        [
            "get_xg_calibration",
            "get_calibration",
            "xg_calibration",
            "calibration",
        ],
        limit=500,
    )

    return _extract_rows(
        result
    )


def _render_xg_calibration(
    controller: ETCController,
) -> None:

    st.markdown(
        "### 🎯 xG Calibration"
    )

    rows = _get_calibration_data(
        controller
    )

    if not rows:

        st.info(
            "xG calibration пока не опубликован "
            "через ETCController или данных ещё нет."
        )

        return

    df = pd.DataFrame(
        rows
    )

    numeric_columns = []

    for column in df.columns:

        converted = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        if converted.notna().sum() >= 2:

            df[column] = converted

            numeric_columns.append(
                column
            )

    if len(
        numeric_columns
    ) >= 2:

        st.line_chart(
            df[
                numeric_columns[:4]
            ]
        )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# GENERIC EVOLUTION DATA
# ============================================================

def _get_evolution_data(
    controller: ETCController,
) -> List[Dict[str, Any]]:

    result = _call_public_api(
        controller,
        [
            "get_evolution_statistics",
            "get_evolution_stats",
            "evolution_statistics",
            "evolution_stats",
        ],
        limit=500,
    )

    return _extract_rows(
        result
    )


def _render_evolution_chart(
    controller: ETCController,
) -> None:

    st.markdown(
        "### 🧬 Evolution Statistics"
    )

    rows = _get_evolution_data(
        controller
    )

    if not rows:

        st.info(
            "Evolution Statistics пока не опубликована "
            "через ETCController."
        )

        return

    df = pd.DataFrame(
        rows
    )

    numeric = []

    for column in df.columns:

        values = pd.to_numeric(
            df[column],
            errors="coerce",
        )

        if values.notna().sum() >= 2:

            df[column] = values

            numeric.append(
                column
            )

    if not numeric:

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )

        return

    st.line_chart(
        df[
            numeric[:6]
        ]
    )

    with st.expander(
        "Показать evolution data",
        expanded=False,
    ):

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# DASHBOARD
# ============================================================

def _render_dashboard(
    controller: ETCController,
    memory_rows: List[Dict[str, Any]],
) -> None:

    st.divider()

    st.markdown(
        "## 📊 ETC Learning Dashboard"
    )

    # --------------------------------------------------------
    # ROW 1
    # --------------------------------------------------------

    col1, col2 = st.columns(2)

    with col1:

        _render_learning_timeline(
            memory_rows
        )

    with col2:

        _render_event_distribution(
            memory_rows
        )

    # --------------------------------------------------------
    # ROW 2
    # --------------------------------------------------------

    col1, col2 = st.columns(2)

    with col1:

        _render_evolution_metrics(
            memory_rows
        )

    with col2:

        _render_match_learning(
            memory_rows
        )

    # --------------------------------------------------------
    # XG
    # --------------------------------------------------------

    st.divider()

    _render_xg_calibration(
        controller
    )

    # --------------------------------------------------------
    # EVOLUTION
    # --------------------------------------------------------

    st.divider()

    _render_evolution_chart(
        controller
    )


# ============================================================
# MEMORY FILTERS
# ============================================================

def _render_memory_filters(
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    if not rows:

        return []

    st.markdown(
        "### 🔍 Фильтр Learning Memory"
    )

    event_types = sorted(
        {
            str(
                row.get(
                    "event_type",
                    "unknown",
                )
            )
            for row in rows
        }
    )

    selected = st.multiselect(
        "Тип события",
        options=event_types,
        default=event_types,
        key="etc_memory_event_filter",
    )

    filtered = [
        row
        for row in rows
        if str(
            row.get(
                "event_type",
                "unknown",
            )
        )
        in selected
    ]

    return filtered


# ============================================================
# PIPELINE
# ============================================================

def _render_pipeline() -> None:

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
     ├── WAIT
     ├── READY
     ├── UNKNOWN_LEAGUE
     └── ALREADY_PROCESSED
              │
              ▼
      get_learning_batch()
              │
              ▼
        ETCController
              │
              ▼
      ETCLearningEngine
              │
              ▼
      StatisticalAnalyzer
              │
       ┌──────┼──────────────┐
       ▼      ▼              ▼
    Error   ObservedXG   Prediction Error
    Analysis              Analysis
       │      │              │
       └──────┼──────────────┘
              ▼
        XG Calibration
              │
              ▼
      Club Rating Updater
              │
              ▼
       Learning Memory
              │
              ▼
          NEXT BATCH
            """,
            language="text",
        )

        st.caption(
            "ETC обучается только на завершённых фактах. "
            "Исторические факты не переписываются."
        )


# ============================================================
# ARCHITECTURE
# ============================================================

def _render_architecture() -> None:

    st.divider()

    with st.expander(
        "🏗️ Архитектура ETC",
        expanded=False,
    ):

        st.code(
            """
                 FAJ STREAMLIT
                       │
                       ▼
                 ETC PAGE
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
 BatchController  Statistical    LearningMemory
                  Analyzer            │
        │              │              │
        │       ┌──────┼──────┐       │
        │       ▼      ▼      ▼       │
        │    Error   Observed  XG     │
        │   Analysis   XG    Calib.    │
        │              │              │
        └──────────────┼──────────────┘
                       ▼
                  FAJDatabase
                       │
                       ▼
                     SQLite
            """,
            language="text",
        )

        st.caption(
            "UI является read-only представлением "
            "ETC и вызывает только публичный API Controller."
        )


# ============================================================
# DIAGNOSTICS
# ============================================================

def _render_diagnostics(
    controller: ETCController,
) -> None:

    st.divider()

    with st.expander(
        "🔎 ETC Diagnostics",
        expanded=False,
    ):

        public_methods = [
            "status",
            "run",
            "get_learning_memory",
            "learning_memory",
            "memory",
            "get_xg_calibration",
            "get_calibration",
            "get_evolution_statistics",
            "get_evolution_stats",
        ]

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

    st.divider()

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
    Главная точка страницы ETC.
    """

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
    # CONTROL
    # --------------------------------------------------------

    _render_control_panel(
        controller
    )

    # --------------------------------------------------------
    # LAST RUN
    # --------------------------------------------------------

    _render_last_result()

    # --------------------------------------------------------
    # MEMORY
    # --------------------------------------------------------

    memory_rows = _get_learning_memory(
        controller,
        limit=500,
    )

    # --------------------------------------------------------
    # DASHBOARD
    # --------------------------------------------------------

    _render_dashboard(
        controller,
        memory_rows,
    )

    # --------------------------------------------------------
    # FILTERED MEMORY
    # --------------------------------------------------------

    filtered_rows = _render_memory_filters(
        memory_rows
    )

    _render_learning_memory(
        filtered_rows
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
