#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================

ФАЙЛ:
    app/pages/etc.py

ETC PAGE v3.0
============================================================

НАЗНАЧЕНИЕ
-----------

Полноценная Streamlit-страница ETC.

Страница является UI-слоем над ETCController.

АРХИТЕКТУРА:

    Streamlit
        │
        ▼
    ETC PAGE
        │
        ▼
    ETCController
        │
        ├── BatchController
        │       │
        │       ├── check()
        │       └── get_learning_batch()
        │
        └── ETCLearningEngine
                │
                ├── process_match()
                └── run_batch()
                        │
                        ▼
                    SQLite

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
    - изменяет rounds;
    - изменяет predictions;
    - создаёт прогнозы;
    - пишет learning_memory;
    - изменяет model_parameters;
    - изменяет team_passports;
    - изменяет team_history;
    - вызывает BatchController напрямую;
    - вызывает ETCLearningEngine напрямую.

Страница вызывает только:

    ETCController.status()
    ETCController.run()
    ETCController.process_match()

============================================================

ВАЖНО
============================================================

ETCController является единственной точкой входа
для UI.

Страница НЕ должна придумывать API, которого нет
в ETCController.

Поэтому:

    get_learning_memory()
    get_xg_calibration()
    get_evolution_statistics()

НЕ вызываются страницей напрямую.

Если соответствующая аналитика понадобится в UI,
она сначала должна быть опубликована через официальный
API ETCController.

============================================================

ENTRY POINT
============================================================

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
from app.etc.batch_controller import (
    BATCH_RULES,
    STATUS_ALREADY_PROCESSED,
    STATUS_READY,
    STATUS_UNKNOWN_LEAGUE,
    STATUS_WAIT,
)


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
ETC_PAGE_VERSION = "3.0"

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

    Вызывается безопасно при запуске страницы.
    """

    try:

        st.set_page_config(
            page_title=PAGE_TITLE,
            page_icon=PAGE_ICON,
            layout="wide",
            initial_sidebar_state="expanded",
        )

    except Exception:
        # set_page_config может быть уже вызван
        # внешним entrypoint.
        pass


# ============================================================
# DATABASE / CONTROLLER
# ============================================================

@st.cache_resource
def get_etc_controller() -> ETCController:
    """
    Создаёт единый ETCController для Streamlit session.

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
    """
    Нормализует errors из Controller.

    Controller может вернуть:

        []
        [error, error]
        0
        2
        "error"
    """

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

    if value:

        return 1

    return 0


# ============================================================
# EXTRACT RESULT DATA
# ============================================================

def _extract_processed_ids(
    result: Dict[str, Any],
) -> List[int]:
    """
    Извлекает processed_match_ids.
    """

    raw = result.get(
        "processed_match_ids",
        [],
    )

    if not isinstance(
        raw,
        list,
    ):

        return []

    ids: List[int] = []

    for value in raw:

        match_id = _safe_int(
            value,
            default=0,
        )

        if match_id > 0:
            ids.append(match_id)

    return ids


def _extract_failed_matches(
    result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Нормализует failed_matches.
    """

    raw = result.get(
        "failed_matches",
        [],
    )

    if not isinstance(
        raw,
        list,
    ):

        return []

    rows: List[Dict[str, Any]] = []

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
    """
    Извлекает результаты отдельных лиг из
    ETCController.run().
    """

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ):

        return []

    rows: List[Dict[str, Any]] = []

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
                "message": batch.get(
                    "message",
                    "",
                ),
            }
        )

    return rows


# ============================================================
# HEADER
# ============================================================

def _render_header() -> None:

    st.title(
        "🧠 FAJ ETC"
    )

    st.subheader(
        "Evolution Training Center"
    )

    st.caption(
        "Постматчевый анализ, пакетное обучение "
        "и контролируемая эволюция FAJ."
    )

    st.info(
        "ETC работает только с завершёнными фактами. "
        "Исторические факты, календарь и существующие "
        "прогнозы не являются объектами изменения ETC."
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
            "❌ Не удалось получить состояние ETC.\n\n"
            f"{exc}"
        )

        return {}

    status_value = _safe_string(
        status.get(
            "status"
        ),
        "UNKNOWN",
    )

    if status_value == "ready":

        st.success(
            "🟢 ETC API готов к работе."
        )

    elif status_value == "degraded":

        st.warning(
            "🟡 ETC API находится в degraded state."
        )

    else:

        st.error(
            f"🔴 ETC status: {status_value}"
        )

    api_contract = _safe_dict(
        status.get(
            "api_contract"
        )
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "ETC",
            status_value,
        )

    with col2:

        st.metric(
            "Controller",
            _safe_string(
                status.get(
                    "batch_controller"
                )
            ),
        )

    with col3:

        st.metric(
            "Learning Engine",
            _safe_string(
                status.get(
                    "learning_engine"
                )
            ),
        )

    with col4:

        st.metric(
            "Version",
            _safe_string(
                status.get(
                    "version"
                ),
                ETC_PAGE_VERSION,
            ),
        )

    st.markdown(
        "#### API Contract"
    )

    api_rows = []

    for name, available in api_contract.items():

        api_rows.append(
            {
                "API": name,
                "Status": (
                    "available"
                    if bool(available)
                    else "missing"
                ),
            }
        )

    if api_rows:

        st.dataframe(
            pd.DataFrame(api_rows),
            use_container_width=True,
            hide_index=True,
        )

    missing_api = _safe_list(
        status.get(
            "missing_api"
        )
    )

    if missing_api:

        st.error(
            "Отсутствует обязательный API ETC:\n\n"
            + "\n".join(
                f"- {item}"
                for item in missing_api
            )
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

    st.caption(
        "Запуск выполняется только через ETCController.run()."
    )

    available_leagues = list(
        BATCH_RULES.keys()
    )

    league_options = [
        "ALL"
    ] + available_leagues

    col1, col2, col3 = st.columns(3)

    with col1:

        selected_league = st.selectbox(
            "Турнир",
            options=league_options,
            index=0,
            key="etc_league",
        )

    with col2:

        limit = st.number_input(
            "Максимум матчей",
            min_value=1,
            max_value=MAX_BATCH_LIMIT,
            value=DEFAULT_BATCH_LIMIT,
            step=1,
            key="etc_batch_limit",
        )

    with col3:

        force = st.checkbox(
            "Force mode",
            value=False,
            key="etc_force_mode",
            help=(
                "Передаётся ETCController. "
                "Ошибки отдельных матчей не должны "
                "превращать успешно обработанные матчи "
                "в ошибочные."
            ),
        )

    if selected_league == "ALL":

        league_value: Optional[str] = None

    else:

        league_value = selected_league

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
                    league=league_value,
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
        "### 📊 Последний запуск ETC"
    )

    status = _safe_string(
        result.get(
            "status"
        ),
        "unknown",
    )

    if status == "completed":

        st.success(
            "✅ ETC успешно обработал доступные batch."
        )

    elif status == "nothing_to_process":

        st.info(
            "⏭️ Нового готового batch нет."
        )

    elif status in (
        "empty",
        STATUS_WAIT,
        STATUS_ALREADY_PROCESSED,
        STATUS_UNKNOWN_LEAGUE,
    ):

        st.info(
            f"ℹ️ ETC: {status}"
        )

    elif status in (
        "partial",
        "completed_with_errors",
    ):

        st.warning(
            "⚠️ ETC завершил обработку с ошибками."
        )

    elif status == "failed":

        st.error(
            "❌ ETC завершился с ошибкой."
        )

    else:

        st.warning(
            f"⚠️ ETC status: {status}"
        )

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:

        st.metric(
            "Batch",
            _safe_int(
                result.get(
                    "batch_size"
                )
            ),
        )

    with col2:

        st.metric(
            "Analyzed",
            _safe_int(
                result.get(
                    "analyzed"
                )
            ),
        )

    with col3:

        st.metric(
            "Learned",
            _safe_int(
                result.get(
                    "learned"
                )
            ),
        )

    with col4:

        st.metric(
            "Processed",
            _safe_int(
                result.get(
                    "processed"
                )
            ),
        )

    with col5:

        st.metric(
            "Learning Events",
            _safe_int(
                result.get(
                    "learning_events"
                )
            ),
        )

    with col6:

        st.metric(
            "Memory Events",
            _safe_int(
                result.get(
                    "memory_events"
                )
            ),
        )

    errors_count = _error_count(
        result.get(
            "errors"
        )
    )

    if errors_count > 0:

        st.error(
            f"❌ Ошибок: {errors_count}"
        )

    elapsed = st.session_state.get(
        "etc_last_elapsed"
    )

    if elapsed is not None:

        st.caption(
            f"⏱ Время выполнения: "
            f"{float(elapsed):.2f} сек."
        )

    processed_ids = _extract_processed_ids(
        result
    )

    if processed_ids:

        with st.expander(
            f"✅ Обработанные матчи ({len(processed_ids)})",
            expanded=False,
        ):

            st.dataframe(
                pd.DataFrame(
                    {
                        "match_id": processed_ids
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

    failed_matches = _extract_failed_matches(
        result
    )

    if failed_matches:

        with st.expander(
            f"❌ Неуспешные матчи ({len(failed_matches)})",
            expanded=True,
        ):

            st.dataframe(
                pd.DataFrame(
                    failed_matches
                ),
                use_container_width=True,
                hide_index=True,
            )

    batch_rows = _extract_batch_rows(
        result
    )

    if batch_rows:

        st.markdown(
            "#### Batch по турнирам"
        )

        st.dataframe(
            pd.DataFrame(batch_rows),
            use_container_width=True,
            hide_index=True,
        )

    message = result.get(
        "message"
    )

    if message:

        st.caption(
            f"ETC: {message}"
        )


# ============================================================
# BATCH STATUS
# ============================================================

def _render_batch_status(
    result: Optional[Dict[str, Any]],
) -> None:

    if not isinstance(
        result,
        dict,
    ):

        return

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ) or not batches:

        return

    st.divider()

    st.markdown(
        "### 📦 Состояние batch"
    )

    rows = []

    for batch in batches:

        if not isinstance(
            batch,
            dict,
        ):

            continue

        rows.append(
            {
                "Лига": batch.get(
                    "league",
                    "—",
                ),
                "Season": batch.get(
                    "season_id",
                    "—",
                ),
                "Status": batch.get(
                    "status",
                    "—",
                ),
                "Batch": _safe_int(
                    batch.get(
                        "batch_size"
                    )
                ),
                "Analyzed": _safe_int(
                    batch.get(
                        "analyzed"
                    )
                ),
                "Learned": _safe_int(
                    batch.get(
                        "learned"
                    )
                ),
                "Processed": _safe_int(
                    batch.get(
                        "processed"
                    )
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
                "Errors": _error_count(
                    batch.get(
                        "errors"
                    )
                ),
            }
        )

    if rows:

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )


# ============================================================
# LEARNING RESULT DETAILS
# ============================================================

def _render_learning_details(
    result: Optional[Dict[str, Any]],
) -> None:

    if not isinstance(
        result,
        dict,
    ):

        return

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ):

        return

    st.divider()

    st.markdown(
        "### 🧠 Детали Learning Engine"
    )

    for index, batch in enumerate(
        batches,
        start=1,
    ):

        if not isinstance(
            batch,
            dict,
        ):

            continue

        league = _safe_string(
            batch.get(
                "league"
            ),
            f"Batch {index}",
        )

        learning_result = batch.get(
            "learning_result"
        )

        if not isinstance(
            learning_result,
            dict,
        ):

            continue

        with st.expander(
            f"🧠 {league} — Learning Engine",
            expanded=False,
        ):

            status = _safe_string(
                learning_result.get(
                    "status"
                ),
                "unknown",
            )

            st.write(
                f"**Status:** `{status}`"
            )

            metric_col1, metric_col2, metric_col3 = st.columns(3)

            with metric_col1:

                st.metric(
                    "Processed",
                    _safe_int(
                        learning_result.get(
                            "processed"
                        )
                    ),
                )

            with metric_col2:

                st.metric(
                    "Learning Events",
                    _safe_int(
                        learning_result.get(
                            "learning_events"
                        )
                    ),
                )

            with metric_col3:

                memory_ids = learning_result.get(
                    "memory_ids",
                    [],
                )

                memory_count = (
                    len(memory_ids)
                    if isinstance(
                        memory_ids,
                        list,
                    )
                    else _safe_int(
                        learning_result.get(
                            "memory_events"
                        )
                    )
                )

                st.metric(
                    "Memory Events",
                    memory_count,
                )

            processed_ids = learning_result.get(
                "processed_match_ids",
                [],
            )

            if isinstance(
                processed_ids,
                list,
            ) and processed_ids:

                st.markdown(
                    "##### Обработанные match_id"
                )

                st.dataframe(
                    pd.DataFrame(
                        {
                            "match_id": processed_ids
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            errors = learning_result.get(
                "errors",
                [],
            )

            if errors:

                st.markdown(
                    "##### Ошибки Learning Engine"
                )

                if isinstance(
                    errors,
                    list,
                ):

                    error_rows = []

                    for error in errors:

                        if isinstance(
                            error,
                            dict,
                        ):

                            error_rows.append(
                                error
                            )

                        else:

                            error_rows.append(
                                {
                                    "error": str(
                                        error
                                    )
                                }
                            )

                    if error_rows:

                        st.dataframe(
                            pd.DataFrame(
                                error_rows
                            ),
                            use_container_width=True,
                            hide_index=True,
                        )

                else:

                    st.error(
                        str(errors)
                    )


# ============================================================
# LEARNING EVENTS SUMMARY
# ============================================================

def _render_learning_events_summary(
    result: Optional[Dict[str, Any]],
) -> None:

    if not isinstance(
        result,
        dict,
    ):

        return

    batches = result.get(
        "batches",
        [],
    )

    if not isinstance(
        batches,
        list,
    ):

        return

    total_events = _safe_int(
        result.get(
            "learning_events"
        )
    )

    total_memory = _safe_int(
        result.get(
            "memory_events"
        )
    )

    processed = _safe_int(
        result.get(
            "processed"
        )
    )

    if (
        total_events == 0
        and total_memory == 0
        and processed == 0
    ):

        return

    st.divider()

    st.markdown(
        "### 🧬 Результат эволюционного обучения"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Матчи обработаны",
            processed,
        )

    with col2:

        st.metric(
            "Learning Events",
            total_events,
        )

    with col3:

        st.metric(
            "Memory Events",
            total_memory,
        )

    with col4:

        if processed > 0:

            events_per_match = (
                total_events / processed
            )

            st.metric(
                "Events / match",
                f"{events_per_match:.2f}",
            )

        else:

            st.metric(
                "Events / match",
                "—",
            )


# ============================================================
# PROCESSED MATCHES
# ============================================================

def _render_processed_matches(
    result: Optional[Dict[str, Any]],
) -> None:

    if not isinstance(
        result,
        dict,
    ):

        return

    processed_ids = _extract_processed_ids(
        result
    )

    if not processed_ids:

        return

    st.divider()

    st.markdown(
        "### ⚽ Обработанные матчи"
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
        "match_id"
    )

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# ERROR PANEL
# ============================================================

def _render_error_panel(
    result: Optional[Dict[str, Any]],
) -> None:

    if not isinstance(
        result,
        dict,
    ):

        return

    failed_matches = _extract_failed_matches(
        result
    )

    if not failed_matches:

        return

    st.divider()

    st.markdown(
        "### 🚨 Ошибки ETC"
    )

    for index, error in enumerate(
        failed_matches,
        start=1,
    ):

        match_id = error.get(
            "match_id",
            "unknown",
        )

        stage = error.get(
            "stage",
            "unknown",
        )

        message = (
            error.get(
                "error"
            )
            or error.get(
                "message"
            )
            or str(error)
        )

        st.error(
            f"{index}. match_id={match_id} | "
            f"stage={stage} | {message}"
        )


# ============================================================
# SESSION STATE
# ============================================================

def _render_session_info() -> None:

    refresh_value = st.session_state.get(
        "etc_refresh"
    )

    if not refresh_value:

        return

    st.caption(
        f"Последнее обновление UI: {refresh_value}"
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
                   SQLite
                      │
                      ▼
              BatchController
                      │
          ┌───────────┼───────────┐
          │           │           │
        WAIT        READY      ALREADY
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
              ┌───────┴───────┐
              │               │
              ▼               ▼
        process_match()   run_batch()
                              │
                              ▼
                    Statistical Analysis
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
            "ETC является постматчевым обучающим контуром. "
            "Факты матча являются входом, а не объектом "
            "модификации."
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
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
       BatchController          ETCLearningEngine
             │                         │
       ┌─────┴─────┐          ┌────────┼────────┐
       │           │          │        │        │
      check()   get_batch()   Analysis Memory  Events
             │                         │
             └────────────┬────────────┘
                          ▼
                      FAJDatabase
                          │
                          ▼
                        SQLite
            """,
            language="text",
        )

        st.markdown(
            """
**Границы ETC**

- `BatchController` определяет готовность batch.
- `ETCController` оркестрирует выполнение.
- `ETCLearningEngine` выполняет обучение.
- `LearningMemory` принадлежит обучающему слою.
- SQLite остаётся единственным хранилищем.
- UI не является частью бизнес-логики.
            """
        )


# ============================================================
# CONTROLLER DIAGNOSTICS
# ============================================================

def _render_diagnostics(
    controller: ETCController,
) -> None:

    st.divider()

    with st.expander(
        "🔎 ETC Diagnostics",
        expanded=False,
    ):

        st.markdown(
            "#### Публичный API Controller"
        )

        public_methods = [
            "status",
            "run",
            "process_match",
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
                        else "MISSING"
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown(
            "#### Внутренние компоненты"
        )

        component_rows = [
            {
                "Component": "BatchController",
                "Class": controller.batch_controller.__class__.__name__,
            },
            {
                "Component": "ETCLearningEngine",
                "Class": controller.learning_engine.__class__.__name__,
            },
            {
                "Component": "Database",
                "Class": controller.db.__class__.__name__,
            },
        ]

        st.dataframe(
            pd.DataFrame(component_rows),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown(
            "#### Legacy API"
        )

        st.success(
            "create_batch() и mark_processed() "
            "не используются ETCController."
        )

        st.markdown(
            "#### Запрещённые операции UI"
        )

        forbidden = [
            "SQL напрямую",
            "DELETE",
            "DROP",
            "изменение match_results",
            "изменение match_statistics",
            "изменение predictions",
            "изменение календаря",
            "прямая запись learning_memory",
        ]

        for item in forbidden:

            st.write(
                f"🚫 {item}"
            )


# ============================================================
# RAW LAST RESULT
# ============================================================

def _render_raw_result(
    result: Optional[Dict[str, Any]],
) -> None:

    if not isinstance(
        result,
        dict,
    ):

        return

    with st.expander(
        "🧾 Полный результат ETCController.run()",
        expanded=False,
    ):

        st.json(
            result
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
    Главная точка страницы ETC.
    """

    _configure_page()

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
            "❌ Не удалось инициализировать ETCController.\n\n"
            f"{exc}"
        )

        st.stop()

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = _render_status(
        controller
    )

    if not status:

        st.warning(
            "ETC status недоступен."
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

    last_result = st.session_state.get(
        "etc_last_result"
    )

    if isinstance(
        last_result,
        dict,
    ):

        _render_last_result()

        _render_batch_status(
            last_result
        )

        _render_learning_events_summary(
            last_result
        )

        _render_processed_matches(
            last_result
        )

        _render_learning_details(
            last_result
        )

        _render_error_panel(
            last_result
        )

        _render_raw_result(
            last_result
        )

    else:

        st.divider()

        st.info(
            "ETC ещё не запускался из этого интерфейса. "
            "После запуска здесь появится полный результат "
            "Controller."
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
    # SESSION
    # --------------------------------------------------------

    _render_session_info()

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    _render_footer()


# ============================================================
# DIRECT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
