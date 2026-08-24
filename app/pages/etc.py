#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================

ФАЙЛ:
    app/pages/etc.py

ETC PAGE v3.1
============================================================

НАЗНАЧЕНИЕ
-----------

Streamlit Dashboard Evolution Training Center.

Страница отображает:

    • состояние ETC;
    • запуск batch обучения;
    • результат последнего batch;
    • Learning Events;
    • Memory Events;
    • обработанные матчи;
    • ошибки;
    • статистику batch;
    • графики обучения;
    • динамику Learning Events;
    • структуру batch;
    • evolution metrics;
    • pipeline;
    • архитектурный контракт;
    • diagnostics.

============================================================
ЖЁСТКИЙ UI CONTRACT
============================================================

Страница НЕ:

    - выполняет SQL;
    - открывает SQLite напрямую;
    - изменяет database.py;
    - изменяет match_results;
    - изменяет match_statistics;
    - изменяет matches;
    - изменяет predictions;
    - пишет learning_memory напрямую;
    - изменяет model_parameters;
    - изменяет team_passports;
    - запускает ETCLearningEngine напрямую.

Вся бизнес-логика принадлежит ETCController.

UI взаимодействует с ETC только через:

    ETCController.status()
    ETCController.run(...)

============================================================
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from app.database import FAJDatabase
from app.etc.etc_controller import ETCController


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
ETC_PAGE_VERSION = "3.1"

PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"

DEFAULT_BATCH_LIMIT = 50
MAX_BATCH_LIMIT = 1000


# ============================================================
# PAGE CONFIG
# ============================================================

def _configure_page() -> None:
    """
    Настройка Streamlit page.
    """

    try:
        st.set_page_config(
            page_title=PAGE_TITLE,
            page_icon=PAGE_ICON,
            layout="wide",
            initial_sidebar_state="expanded",
        )
    except Exception:
        pass


# ============================================================
# CONTROLLER
# ============================================================

@st.cache_resource
def get_etc_controller() -> ETCController:
    """
    Создаёт ETCController.

    ВАЖНО:

    Страница не работает с SQLite напрямую.
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


def _safe_string(
    value: Any,
    default: str = "—",
) -> str:

    if value is None:
        return default

    text = str(value).strip()

    return text if text else default


def _safe_int(
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


def _safe_float(
    value: Any,
    default: float = 0.0,
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


def _error_count(
    value: Any,
) -> int:

    if isinstance(
        value,
        list,
    ):

        return len(value)

    if isinstance(
        value,
        int,
    ):

        return max(
            0,
            value,
        )

    return 1 if value else 0


# ============================================================
# RESULT NORMALIZATION
# ============================================================

def _extract_processed_ids(
    result: Dict[str, Any],
) -> List[int]:

    raw = result.get(
        "processed_match_ids",
        [],
    )

    if not isinstance(
        raw,
        list,
    ):

        return []

    output = []

    for value in raw:

        match_id = _safe_int(
            value,
            0,
        )

        if match_id > 0:
            output.append(
                match_id
            )

    return output


def _extract_failed_matches(
    result: Dict[str, Any],
) -> List[Dict[str, Any]]:

    raw = result.get(
        "failed_matches",
        [],
    )

    if not isinstance(
        raw,
        list,
    ):

        return []

    rows = []

    for item in raw:

        if isinstance(
            item,
            dict,
        ):

            rows.append(
                item
            )

        else:

            rows.append(
                {
                    "match_id": None,
                    "stage": "unknown",
                    "error": str(item),
                }
            )

    return rows


def _extract_batch_rows(
    result: Dict[str, Any],
) -> List[Dict[str, Any]]:

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ):

        return []

    rows = []

    for batch in batches:

        if not isinstance(
            batch,
            dict,
        ):

            continue

        rows.append(
            {
                "league": batch.get(
                    "league"
                ),
                "season_id": batch.get(
                    "season_id"
                ),
                "status": batch.get(
                    "status"
                ),
                "batch_size": batch.get(
                    "batch_size",
                    0,
                ),
                "analyzed": batch.get(
                    "analyzed",
                    0,
                ),
                "learned": batch.get(
                    "learned",
                    0,
                ),
                "processed": batch.get(
                    "processed",
                    0,
                ),
                "learning_events": batch.get(
                    "learning_events",
                    0,
                ),
                "memory_events": batch.get(
                    "memory_events",
                    0,
                ),
                "errors": _error_count(
                    batch.get(
                        "errors",
                        0,
                    )
                ),
            }
        )

    return rows


# ============================================================
# HEADER
# ============================================================

def _render_header() -> None:

    col1, col2 = st.columns(
        [1, 5]
    )

    with col1:

        st.markdown(
            "# 🧠"
        )

    with col2:

        st.title(
            "FAJ ETC"
        )

        st.subheader(
            "Evolution Training Center"
        )

        st.caption(
            "Постматчевый анализ, пакетное обучение "
            "и контролируемая эволюция FAJ."
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
            f"❌ Не удалось получить состояние ETC: {exc}"
        )

        return {}

    status_value = _safe_string(
        status.get(
            "status"
        ),
        "UNKNOWN",
    )

    if status_value.lower() in (
        "ready",
        "ok",
        "healthy",
    ):

        st.success(
            "🟢 ETC готов к работе."
        )

    elif status_value.lower() in (
        "degraded",
        "warning",
    ):

        st.warning(
            "🟡 ETC находится в degraded state."
        )

    else:

        st.error(
            f"🔴 ETC status: {status_value}"
        )

    col1, col2, col3, col4, col5 = st.columns(
        5
    )

    with col1:

        st.metric(
            "Статус",
            status_value,
        )

    with col2:

        st.metric(
            "Ожидает",
            _safe_string(
                status.get(
                    "pending_matches"
                )
            ),
        )

    with col3:

        st.metric(
            "Обработано",
            _safe_string(
                status.get(
                    "processed_matches"
                )
            ),
        )

    with col4:

        st.metric(
            "Learning Events",
            _safe_string(
                status.get(
                    "learning_events"
                )
            ),
        )

    with col5:

        st.metric(
            "Версия",
            _safe_string(
                status.get(
                    "version"
                ),
                ETC_PAGE_VERSION,
            ),
        )

    api_contract = _safe_dict(
        status.get(
            "api_contract"
        )
    )

    if api_contract:

        with st.expander(
            "🔌 ETC API Contract",
            expanded=False,
        ):

            rows = []

            for key, value in api_contract.items():

                rows.append(
                    {
                        "API": key,
                        "Status": (
                            "✅"
                            if value
                            else "❌"
                        ),
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
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

    col1, col2 = st.columns(
        2
    )

    with col1:

        limit = st.number_input(
            "Максимум матчей за batch",
            min_value=1,
            max_value=MAX_BATCH_LIMIT,
            value=DEFAULT_BATCH_LIMIT,
            step=1,
            key="etc_batch_limit",
        )

    with col2:

        force = st.checkbox(
            "Force mode",
            value=False,
            key="etc_force_mode",
            help=(
                "Продолжать обработку batch "
                "при ошибке отдельного матча."
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
            "ETC обрабатывает готовые batch..."
        ):

            try:

                result = controller.run(
                    limit=int(
                        limit
                    ),
                    force=bool(
                        force
                    ),
                )

            except TypeError:

                # Совместимость с Controller,
                # который может принимать только limit/force
                try:

                    result = controller.run(
                        int(limit),
                        bool(force),
                    )

                except Exception as exc:

                    st.error(
                        f"❌ Ошибка ETC: {exc}"
                    )

                    return

            except Exception as exc:

                st.error(
                    f"❌ Критическая ошибка ETC: {exc}"
                )

                return

        elapsed = (
            datetime.now()
            - started
        ).total_seconds()

        st.session_state[
            "etc_last_result"
        ] = _safe_dict(
            result
        )

        st.session_state[
            "etc_last_elapsed"
        ] = elapsed

        st.session_state[
            "etc_refresh"
        ] = datetime.now().isoformat()

        st.rerun()


# ============================================================
# MAIN DASHBOARD
# ============================================================

def _render_learning_dashboard(
    result: Dict[str, Any],
) -> None:

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ) or not batches:

        st.info(
            "Нет batch-данных для построения графиков."
        )

        return

    st.divider()

    st.markdown(
        "## 📊 ETC Learning Dashboard"
    )

    # --------------------------------------------------------
    # TOTALS
    # --------------------------------------------------------

    total_learning = _safe_int(
        result.get(
            "learning_events"
        )
    )

    total_memory = _safe_int(
        result.get(
            "memory_events"
        )
    )

    total_processed = _safe_int(
        result.get(
            "processed"
        )
    )

    total_errors = _error_count(
        result.get(
            "errors"
        )
    )

    total_batch_size = _safe_int(
        result.get(
            "batch_size"
        )
    )

    col1, col2, col3, col4, col5, col6 = st.columns(
        6
    )

    with col1:

        st.metric(
            "📦 Batch Size",
            total_batch_size,
        )

    with col2:

        st.metric(
            "📊 Обработано",
            total_processed,
        )

    with col3:

        st.metric(
            "🧠 Learning Events",
            total_learning,
        )

    with col4:

        st.metric(
            "💾 Memory Events",
            total_memory,
        )

    with col5:

        st.metric(
            "❌ Ошибки",
            total_errors,
        )

    with col6:

        if total_processed:

            ratio = (
                total_learning
                / total_processed
            )

            st.metric(
                "📈 Events / Match",
                f"{ratio:.2f}",
            )

        else:

            st.metric(
                "📈 Events / Match",
                "—",
            )

    st.markdown(
        "---"
    )

    # --------------------------------------------------------
    # LEARNING EVENTS BY LEAGUE
    # --------------------------------------------------------

    league_data = []

    for batch in batches:

        if not isinstance(
            batch,
            dict,
        ):

            continue

        league_data.append(
            {
                "Лига": _safe_string(
                    batch.get(
                        "league"
                    ),
                    "Unknown",
                ),
                "Learning Events": _safe_int(
                    batch.get(
                        "learning_events"
                    )
                ),
            }
        )

    if league_data:

        df = pd.DataFrame(
            league_data
        )

        fig = px.bar(
            df,
            x="Лига",
            y="Learning Events",
            title="🧠 Learning Events по лигам",
            text_auto=True,
        )

        fig.update_layout(
            height=350,
            showlegend=False,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    # --------------------------------------------------------
    # MEMORY EVENTS BY LEAGUE
    # --------------------------------------------------------

    memory_data = []

    for batch in batches:

        if not isinstance(
            batch,
            dict,
        ):

            continue

        memory_data.append(
            {
                "Лига": _safe_string(
                    batch.get(
                        "league"
                    ),
                    "Unknown",
                ),
                "Memory Events": _safe_int(
                    batch.get(
                        "memory_events"
                    )
                ),
            }
        )

    if memory_data:

        df = pd.DataFrame(
            memory_data
        )

        fig = px.bar(
            df,
            x="Лига",
            y="Memory Events",
            title="💾 Memory Events по лигам",
            text_auto=True,
        )

        fig.update_layout(
            height=350,
            showlegend=False,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    # --------------------------------------------------------
    # STATUS + ERRORS
    # --------------------------------------------------------

    col1, col2 = st.columns(
        2
    )

    with col1:

        status_values = []

        for batch in batches:

            if not isinstance(
                batch,
                dict,
            ):

                continue

            status_values.append(
                _safe_string(
                    batch.get(
                        "status"
                    ),
                    "unknown",
                )
            )

        if status_values:

            counts = Counter(
                status_values
            )

            df = pd.DataFrame(
                {
                    "Status": list(
                        counts.keys()
                    ),
                    "Count": list(
                        counts.values()
                    ),
                }
            )

            fig = px.pie(
                df,
                values="Count",
                names="Status",
                title="📊 Структура статусов batch",
            )

            fig.update_layout(
                height=350
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

    with col2:

        processed_error_data = []

        for batch in batches:

            if not isinstance(
                batch,
                dict,
            ):

                continue

            processed_error_data.append(
                {
                    "Лига": _safe_string(
                        batch.get(
                            "league"
                        ),
                        "Unknown",
                    ),
                    "Обработано": _safe_int(
                        batch.get(
                            "processed"
                        )
                    ),
                    "Ошибки": _error_count(
                        batch.get(
                            "errors"
                        )
                    ),
                }
            )

        if processed_error_data:

            df = pd.DataFrame(
                processed_error_data
            )

            df = df.melt(
                id_vars=["Лига"],
                var_name="Тип",
                value_name="Количество",
            )

            fig = px.bar(
                df,
                x="Лига",
                y="Количество",
                color="Тип",
                barmode="group",
                title="⚖️ Обработано vs ошибки",
            )

            fig.update_layout(
                height=350
            )

            st.plotly_chart(
                fig,
                use_container_width=True,
            )

    # --------------------------------------------------------
    # LEARNING VS MEMORY
    # --------------------------------------------------------

    comparison_data = []

    for batch in batches:

        if not isinstance(
            batch,
            dict,
        ):

            continue

        comparison_data.append(
            {
                "Лига": _safe_string(
                    batch.get(
                        "league"
                    ),
                    "Unknown",
                ),
                "Learning Events": _safe_int(
                    batch.get(
                        "learning_events"
                    )
                ),
                "Memory Events": _safe_int(
                    batch.get(
                        "memory_events"
                    )
                ),
            }
        )

    if comparison_data:

        df = pd.DataFrame(
            comparison_data
        )

        df = df.melt(
            id_vars=["Лига"],
            var_name="Тип",
            value_name="Количество",
        )

        fig = px.bar(
            df,
            x="Лига",
            y="Количество",
            color="Тип",
            barmode="group",
            title="⚡ Learning Events vs Memory Events",
        )

        fig.update_layout(
            height=350
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )


# ============================================================
# EVOLUTION METRICS
# ============================================================

def _render_evolution_metrics(
    result: Dict[str, Any],
) -> None:

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ) or not batches:

        return

    total_learning = sum(
        _safe_int(
            batch.get(
                "learning_events"
            )
        )
        for batch in batches
        if isinstance(
            batch,
            dict,
        )
    )

    total_memory = sum(
        _safe_int(
            batch.get(
                "memory_events"
            )
        )
        for batch in batches
        if isinstance(
            batch,
            dict,
        )
    )

    total_processed = sum(
        _safe_int(
            batch.get(
                "processed"
            )
        )
        for batch in batches
        if isinstance(
            batch,
            dict,
        )
    )

    total_errors = sum(
        _error_count(
            batch.get(
                "errors"
            )
        )
        for batch in batches
        if isinstance(
            batch,
            dict,
        )
    )

    total_batches = len(
        batches
    )

    if not (
        total_learning
        or total_memory
        or total_processed
    ):

        st.info(
            "Нет данных для evolution metrics."
        )

        return

    st.divider()

    st.markdown(
        "### 🧬 Evolution Metrics"
    )

    col1, col2 = st.columns(
        2
    )

    with col1:

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=[
                    "Learning Events",
                    "Memory Events",
                ],
                y=[
                    total_learning,
                    total_memory,
                ],
                text=[
                    total_learning,
                    total_memory,
                ],
                textposition="outside",
            )
        )

        fig.update_layout(
            title="🧬 Learning vs Memory",
            height=320,
            showlegend=False,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    with col2:

        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=[
                    "Processed",
                    "Errors",
                ],
                y=[
                    total_processed,
                    total_errors,
                ],
                text=[
                    total_processed,
                    total_errors,
                ],
                textposition="outside",
            )
        )

        fig.update_layout(
            title="⚖️ Processed vs Errors",
            height=320,
            showlegend=False,
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

    col1, col2, col3 = st.columns(
        3
    )

    with col1:

        st.metric(
            "Средний Learning Events / batch",
            f"{total_learning / total_batches:.2f}"
            if total_batches
            else "—",
        )

    with col2:

        st.metric(
            "Средний Memory Events / batch",
            f"{total_memory / total_batches:.2f}"
            if total_batches
            else "—",
        )

    with col3:

        st.metric(
            "Средний Processed / batch",
            f"{total_processed / total_batches:.2f}"
            if total_batches
            else "—",
        )


# ============================================================
# MATCH LEARNING
# ============================================================

def _render_match_learning(
    result: Dict[str, Any],
) -> None:

    processed_ids = _extract_processed_ids(
        result
    )

    if not processed_ids:

        return

    st.divider()

    st.markdown(
        "### ⚽ Обучение по матчам"
    )

    counts = Counter(
        processed_ids
    )

    rows = [
        {
            "match_id": match_id,
            "learning_runs": count,
        }
        for match_id, count in counts.items()
    ]

    df = pd.DataFrame(
        rows
    )

    df = df.sort_values(
        "learning_runs",
        ascending=False,
    ).head(20)

    fig = px.bar(
        df,
        x="match_id",
        y="learning_runs",
        title="Топ-20 матчей по learning runs",
        text_auto=True,
    )

    fig.update_layout(
        height=350,
        xaxis_title="Match ID",
        yaxis_title="Learning Runs",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )

    with st.expander(
        "📋 Матчи",
        expanded=False,
    ):

        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# BATCH STATUS
# ============================================================

def _render_batch_status(
    result: Dict[str, Any],
) -> None:

    rows = _extract_batch_rows(
        result
    )

    if not rows:

        return

    st.divider()

    st.markdown(
        "### 📊 Batch Status"
    )

    df = pd.DataFrame(
        rows
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    if "league" not in df.columns:

        return

    fig = px.bar(
        df,
        x="league",
        y="batch_size",
        color="status",
        title="Размер batch по лигам",
        text_auto=True,
    )

    fig.update_layout(
        height=350
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# TIMELINE
# ============================================================

def _render_learning_timeline(
    result: Dict[str, Any],
) -> None:

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ):

        return

    timeline_data = []

    for batch in batches:

        if not isinstance(
            batch,
            dict,
        ):

            continue

        learning_result = batch.get(
            "learning_result",
            {},
        )

        if not isinstance(
            learning_result,
            dict,
        ):

            continue

        created_at = learning_result.get(
            "created_at"
        )

        if not created_at:

            continue

        try:

            date_value = pd.to_datetime(
                created_at
            )

        except Exception:

            continue

        events = _safe_int(
            learning_result.get(
                "learning_events"
            )
        )

        if events <= 0:

            continue

        timeline_data.append(
            {
                "Дата": date_value,
                "Learning Events": events,
                "Лига": _safe_string(
                    batch.get(
                        "league"
                    ),
                    "Unknown",
                ),
            }
        )

    if not timeline_data:

        return

    st.divider()

    st.markdown(
        "### 📈 Динамика обучения"
    )

    df = pd.DataFrame(
        timeline_data
    )

    df = df.sort_values(
        "Дата"
    )

    fig = px.line(
        df,
        x="Дата",
        y="Learning Events",
        color="Лига",
        markers=True,
        title="Динамика Learning Events",
    )

    fig.update_layout(
        height=400,
        xaxis_title="Дата",
        yaxis_title="Learning Events",
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# LEARNING STRUCTURE
# ============================================================

def _render_learning_structure(
    result: Dict[str, Any],
) -> None:

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ) or not batches:

        return

    statuses = []

    for batch in batches:

        if not isinstance(
            batch,
            dict,
        ):

            continue

        status = batch.get(
            "status"
        )

        if status:

            statuses.append(
                str(status)
            )

    if not statuses:

        return

    counts = Counter(
        statuses
    )

    df = pd.DataFrame(
        {
            "Тип": list(
                counts.keys()
            ),
            "Количество": list(
                counts.values()
            ),
        }
    )

    st.divider()

    st.markdown(
        "### 🧩 Структура обучения"
    )

    fig = px.pie(
        df,
        values="Количество",
        names="Тип",
        title="Структура batch по статусам",
    )

    fig.update_layout(
        height=350
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )


# ============================================================
# MEMORY IDS
# ============================================================

def _render_learning_memory(
    result: Dict[str, Any],
) -> None:

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ):

        return

    memory_events = []

    for batch in batches:

        if not isinstance(
            batch,
            dict,
        ):

            continue

        learning_result = batch.get(
            "learning_result",
            {},
        )

        if not isinstance(
            learning_result,
            dict,
        ):

            continue

        memory_ids = learning_result.get(
            "memory_ids",
            [],
        )

        if not isinstance(
            memory_ids,
            list,
        ):

            continue

        for memory_id in memory_ids:

            memory_events.append(
                {
                    "memory_id": memory_id,
                    "league": batch.get(
                        "league"
                    ),
                }
            )

    if not memory_events:

        return

    st.divider()

    with st.expander(
        "💾 Learning Memory IDs",
        expanded=False,
    ):

        st.dataframe(
            pd.DataFrame(
                memory_events
            ),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# FAILED MATCHES
# ============================================================

def _render_failed_matches(
    result: Dict[str, Any],
) -> None:

    rows = _extract_failed_matches(
        result
    )

    if not rows:

        return

    st.divider()

    st.markdown(
        "### ❌ Ошибки матчей"
    )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


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

        st.info(
            "ETC ещё не запускался. "
            "После первого batch здесь появится аналитика."
        )

        return

    status = _safe_string(
        result.get(
            "status"
        ),
        "unknown",
    )

    st.divider()

    st.markdown(
        "## 📊 Последний ETC Batch"
    )

    if status == "completed":

        st.success(
            "✅ ETC batch успешно завершён."
        )

    elif status in (
        "nothing_to_process",
        "empty",
    ):

        st.info(
            "⏭️ Новых готовых матчей для обучения нет."
        )

    elif status in (
        "partial",
        "completed_with_errors",
    ):

        st.warning(
            "⚠️ Batch завершён частично, "
            "есть ошибки."
        )

    elif status in (
        "failed",
        "error",
        "failure",
    ):

        st.error(
            "❌ ETC завершился ошибкой."
        )

    else:

        st.warning(
            f"⚠️ ETC status: {status}"
        )

    _render_learning_dashboard(
        result
    )

    _render_learning_structure(
        result
    )

    _render_evolution_metrics(
        result
    )

    _render_match_learning(
        result
    )

    _render_batch_status(
        result
    )

    _render_learning_timeline(
        result
    )

    _render_learning_memory(
        result
    )

    _render_failed_matches(
        result
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
            "❌ Общие ошибки batch",
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

    with st.expander(
        "🧾 Полный результат ETC",
        expanded=False,
    ):

        st.json(
            result
        )


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
MATCH
  │
  ▼
IMPORT FACTS
  │
  ▼
match_results
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
 Statistical Analysis
          │
          ├── Prediction Error
          ├── Observed xG
          ├── Calibration
          └── Team / Club Learning
                  │
                  ▼
           Learning Memory
                  │
                  ▼
               SQLite
                  │
                  ▼
             NEXT BATCH
            """,
            language="text",
        )

        st.caption(
            "ETC работает только с завершёнными "
            "фактами матчей. Исторические факты "
            "не переписываются."
        )


# ============================================================
# ARCHITECTURE
# ============================================================

def _render_architecture() -> None:

    st.divider()

    with st.expander(
        "🏗️ Архитектурный контракт ETC",
        expanded=False,
    ):

        st.code(
            """
                 FAJ
                  │
                  ▼
             MATCH FACTS
                  │
                  ▼
           ETCController
                  │
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
 BatchController     ETCLearningEngine
                            │
                ┌───────────┼───────────┐
                │           │           │
                ▼           ▼           ▼
           Statistical   Prediction   Learning
             Analysis      Error       Memory
                │           │           │
                └───────────┼───────────┘
                            ▼
                       FAJDatabase
                            │
                            ▼
                          SQLite
            """,
            language="text",
        )

        st.caption(
            "ETC Page является UI-слоем. "
            "Бизнес-логика находится внутри ETCController "
            "и ETCLearningEngine."
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

        methods = [
            "status",
            "run",
        ]

        rows = []

        for method_name in methods:

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
                        else "MISSING"
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            "UI намеренно проверяет только "
            "публичный ETCController API."
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
        f"SQLite • Controller-driven architecture"
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    """
    Главная точка входа страницы ETC.

    Совместимый импорт:

        from app.pages.etc import main
    """

    _configure_page()

    _render_header()

    # --------------------------------------------------------
    # CONTROLLER
    # --------------------------------------------------------

    try:

        controller = get_etc_controller()

    except Exception as exc:

        st.error(
            "❌ Не удалось инициализировать ETCController.\n\n"
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
    # LAST RESULT
    # --------------------------------------------------------

    _render_last_result()

    # --------------------------------------------------------
    # ARCHITECTURE
    # --------------------------------------------------------

    _render_pipeline()

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
