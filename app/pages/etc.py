#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================
ФАЙЛ:
    app/pages/etc.py
ETC PAGE v5.2
============================================================
НАЗНАЧЕНИЕ
-----------
Прозрачная контрольная панель ETC.
Показывает:
    • состояние ETC;
    • готовые матчи;
    • уже обработанные матчи;
    • последний batch;
    • batch fingerprint;
    • LearningMemory;
    • ошибки FAJ;
    • xG deviations;
    • повторяющиеся error patterns;
    • ETC signals;
    • ошибки отдельных матчей;
    • следующий шаг цикла.
ВАЖНО
------
PAGE НЕ:
    • выполняет SQL;
    • изменяет SQLite;
    • изменяет match_results;
    • изменяет predictions;
    • изменяет model_parameters;
    • изменяет learning_memory;
    • самостоятельно определяет, обучен матч или нет;
    • самостоятельно рассчитывает xG;
    • самостоятельно классифицирует ошибки.
Вся бизнес-логика находится в backend:
    ETCController v2.7
        ↓
    ETCLearningEngine v1.8
        ↓
    BatchController v1.3
        ↓
    StatisticalAnalyzer v1.3
        ↓
    LearningAnalyzer v2.1
        ↓
    LearningMemory v2.1
PAGE только отображает полученное состояние.
============================================================
ИСПРАВЛЕНИЯ v5.2
============================================================
1. Добавлена поддержка already_processed из ETCController v2.7.
2. Улучшено отображение already_processed в метриках.
3. Добавлено отображение already_processed_match_ids.
4. Совместимость с LearningEngine v1.8 сохранена.
============================================================
"""
from __future__ import annotations
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
ETC_PAGE_VERSION = "5.2"
PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"
DEFAULT_BATCH_LIMIT = 50
MAX_BATCH_LIMIT = 1000
# ============================================================
# PAGE CONFIG
# ============================================================
def _configure_page() -> None:
    try:
        st.set_page_config(
            page_title=PAGE_TITLE,
            page_icon=PAGE_ICON,
            layout="wide",
        )
    except Exception:
        pass
# ============================================================
# CONTROLLER
# ============================================================
@st.cache_resource
def get_etc_controller() -> ETCController:
    """
    Единственная точка доступа страницы к ETC.
    """
    db = FAJDatabase()
    return ETCController(db=db)
# ============================================================
# SAFE HELPERS
# ============================================================
def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}
def _safe_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return []
def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default
def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default
def _safe_string(
    value: Any,
    default: str = "—",
) -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default
def _error_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, int):
        return max(0, value)
    if value:
        return 1
    return 0
def _get_errors(
    result: Dict[str, Any],
) -> List[Any]:
    raw = result.get("errors", [])
    if isinstance(raw, list):
        return raw
    if raw:
        return [raw]
    return []
def _get_batches(
    result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    raw = result.get("batches", [])
    if not isinstance(raw, list):
        return []
    return [
        item
        for item in raw
        if isinstance(item, dict)
    ]
def _normalize_ids(
    value: Any,
) -> List[int]:
    result: List[int] = []
    if not isinstance(value, list):
        return result
    seen = set()
    for item in value:
        try:
            item_id = int(item)
        except (TypeError, ValueError):
            continue
        if item_id <= 0:
            continue
        if item_id in seen:
            continue
        seen.add(item_id)
        result.append(item_id)
    return result
def _get_processed_ids(
    result: Dict[str, Any],
) -> List[int]:
    return _normalize_ids(
        result.get("processed_match_ids", [])
    )
def _get_already_processed_ids(
    result: Dict[str, Any],
) -> List[int]:
    """
    Получает already_processed_match_ids из результата.
    Поддерживает несколько вариантов именования.
    """
    raw = result.get("already_processed_match_ids")
    if raw is None:
        raw = result.get("already_processed_ids")
    if raw is None:
        raw = result.get("already_processed")
    return _normalize_ids(raw)
def _get_memory_ids(
    result: Dict[str, Any],
) -> List[int]:
    return _normalize_ids(
        result.get("memory_ids", [])
    )
def _get_batch_memory_ids(
    result: Dict[str, Any],
) -> List[int]:
    return _normalize_ids(
        result.get("batch_memory_ids", [])
    )
# ============================================================
# HEADER
# ============================================================
def _render_header() -> None:
    st.title("🧠 FAJ ETC")
    st.subheader(
        "Evolution Training Center"
    )
    st.caption(
        "Прозрачная панель обучения FAJ "
        "на завершённых и подтверждённых матчах."
    )
    st.info(
        "ETC не изменяет исторические факты. "
        "Он получает готовые данные через backend, "
        "анализирует ошибки и сохраняет результат "
        "обучения в LearningMemory."
    )
    st.divider()
# ============================================================
# FLOW
# ============================================================
def _render_flow() -> None:
    st.markdown("### 🔄 Цепочка ETC")
    st.code(
        """
FACTS
  ↓
BatchController
  ↓
READY
  ↓
get_learning_batch()
  ↓
ETCLearningEngine
  ↓
StatisticalAnalyzer
  ↓
LearningAnalyzer
  ↓
LearningMemory
  ↓
batch_learning marker
  ↓
BATCH COMPLETED
  ↓
NEXT MATCHES
        """.strip(),
        language="text",
    )
# ============================================================
# STATUS
# ============================================================
def _render_status(
    controller: ETCController,
) -> Dict[str, Any]:
    try:
        status = _safe_dict(
            controller.status()
        )
    except Exception as exc:
        st.error(
            "❌ Не удалось получить состояние ETC."
        )
        st.exception(exc)
        return {}
    status_value = _safe_string(
        status.get("status"),
        "UNKNOWN",
    )
    pending = _safe_int(
        status.get("pending_matches")
    )
    processed = _safe_int(
        status.get("processed_matches")
    )
    learning_events = _safe_int(
        status.get("learning_events")
    )
    total_ready = _safe_int(
        status.get("ready_matches")
    )
    last_batch = _safe_string(
        status.get("last_batch_id"),
        "—",
    )
    last_run = _safe_string(
        status.get("last_run"),
        "—",
    )
    st.markdown("### 📡 Состояние ETC")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(
            "Готово к обучению",
            pending,
        )
    with col2:
        st.metric(
            "Уже обработано",
            processed,
        )
    with col3:
        st.metric(
            "Learning Events",
            learning_events,
        )
    with col4:
        st.metric(
            "ETC",
            status_value,
        )
    if total_ready or last_batch != "—" or last_run != "—":
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(
                f"READY matches: {total_ready}"
            )
        with col2:
            st.caption(
                f"Последний batch: {last_batch}"
            )
        with col3:
            st.caption(
                f"Последний запуск: {last_run}"
            )
    st.divider()
    return status
# ============================================================
# CONTROL
# ============================================================
def _render_control(
    controller: ETCController,
) -> None:
    st.markdown("### 🧠 Запуск обучения")
    st.caption(
        "ETC получает batch через ETCController. "
        "Страница не выбирает матчи самостоятельно."
    )
    col1, col2 = st.columns(2)
    with col1:
        limit = st.number_input(
            "Максимум матчей за запуск",
            min_value=1,
            max_value=MAX_BATCH_LIMIT,
            value=DEFAULT_BATCH_LIMIT,
            step=1,
            key="etc_batch_limit",
        )
    with col2:
        force = st.checkbox(
            "Продолжать при ошибке отдельного матча",
            value=False,
            key="etc_force_mode",
        )
    st.caption(
        "Force mode позволяет продолжить batch после "
        "ошибки отдельного матча. Он НЕ означает "
        "повторное обучение уже обработанного матча."
    )
    if st.button(
        "🧠 ЗАПУСТИТЬ ОБУЧЕНИЕ",
        type="primary",
        width="stretch",
        key="etc_run_button",
    ):
        started = datetime.now()
        with st.spinner(
            "FAJ ETC выполняет batch..."
        ):
            try:
                result = controller.run(
                    limit=int(limit),
                    force=bool(force),
                )
            except Exception as exc:
                st.error(
                    f"❌ Ошибка ETCController: {exc}"
                )
                st.exception(exc)
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
        st.rerun()
# ============================================================
# RESULT STATUS
# ============================================================
def _render_result_status(
    result: Dict[str, Any],
) -> None:
    status = _safe_string(
        result.get("status"),
        "unknown",
    )
    success = bool(
        result.get("success", False)
    )
    batch_completed = bool(
        result.get("batch_completed", False)
    )
    errors = _error_count(
        result.get("errors")
    )
    if (
        success
        and (
            status == "completed"
            or batch_completed
        )
        and errors == 0
    ):
        st.success(
            "✅ BATCH COMPLETED — "
            "ETC успешно завершил обучение."
        )
        return
    if status == "already_processed":
        st.info(
            "ℹ️ Выбранный матч / batch уже "
            "обрабатывался ранее."
        )
        return
    if status in (
        "nothing_to_process",
        "empty",
        "WAIT",
    ):
        st.info(
            "⏭️ Новых готовых матчей для обучения нет."
        )
        return
    if status == "partial":
        st.warning(
            "⚠️ Batch обработан частично."
        )
        return
    if errors > 0:
        st.error(
            f"❌ ETC завершился с ошибками. "
            f"Ошибок: {errors}"
        )
        return
    if not success:
        st.error(
            f"❌ ETC не завершил batch. "
            f"Статус: {status}"
        )
        return
    st.info(
        f"Статус ETC: {status}"
    )
# ============================================================
# MATCH LEDGER
# ============================================================
def _render_match_ledger(
    result: Dict[str, Any],
) -> None:
    """
    Показывает состояние матчей.
    Поддерживает несколько вариантов backend contract:
        match_ledger
        matches
        processed_matches
        processed_match_ids
    """
    ledger_raw = result.get("match_ledger")
    if ledger_raw is None:
        ledger_raw = result.get("matches")
    if isinstance(ledger_raw, list):
        rows = []
        for item in ledger_raw:
            if not isinstance(item, dict):
                continue
            match_id = item.get(
                "match_id"
            )
            if match_id is None:
                continue
            rows.append(
                {
                    "match_id": match_id,
                    "FACTS": _safe_string(
                        item.get("facts"),
                        "—",
                    ),
                    "RESULT": _safe_string(
                        item.get("result"),
                        "—",
                    ),
                    "STATISTICS": _safe_string(
                        item.get("statistics"),
                        "—",
                    ),
                    "PREDICTION": _safe_string(
                        item.get("prediction"),
                        "—",
                    ),
                    "READY": _safe_string(
                        item.get("ready"),
                        "—",
                    ),
                    "ETC": _safe_string(
                        item.get("etc"),
                        "—",
                    ),
                    "STATUS": _safe_string(
                        item.get("status"),
                        "—",
                    ),
                }
            )
        if rows:
            st.markdown(
                "### ⚽ Match Ledger"
            )
            st.dataframe(
                pd.DataFrame(rows),
                width="stretch",
                hide_index=True,
            )
            return
    processed_ids = _get_processed_ids(
        result
    )
    if processed_ids:
        st.markdown(
            "### ⚽ Обработанные матчи текущего batch"
        )
        rows = [
            {
                "match_id": match_id,
                "ETC": "✅ Обработан",
            }
            for match_id in processed_ids
        ]
        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
        )
# ============================================================
# HISTORICAL PROCESSED MATCHES
# ============================================================
def _render_historical_processed(
    result: Dict[str, Any],
) -> None:
    """
    Отображает исторически обработанные матчи,
    если ETCController их возвращает.
    Это намеренно не вычисляется на UI.
    """
    raw = result.get(
        "already_processed_match_ids"
    )
    if raw is None:
        raw = result.get(
            "processed_history"
        )
    ids = _normalize_ids(raw)
    if not ids:
        return
    st.markdown(
        "### 🗂️ Уже обработанные матчи"
    )
    st.caption(
        "Эти match_id backend уже определил "
        "как обработанные ETC."
    )
    st.metric(
        "Количество",
        len(ids),
    )
    with st.expander(
        "🔎 Показать match_id",
        expanded=False,
    ):
        st.code(
            ", ".join(
                str(item)
                for item in ids
            )
        )
# ============================================================
# MEMORY
# ============================================================
def _render_memory(
    result: Dict[str, Any],
) -> None:
    memory_ids = _get_memory_ids(
        result
    )
    batch_memory_ids = _get_batch_memory_ids(
        result
    )
    learning_events = _safe_int(
        result.get("learning_events")
    )
    st.markdown(
        "### 🧠 LearningMemory"
    )
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Learning Events",
            learning_events,
        )
    with col2:
        st.metric(
            "Memory IDs",
            len(memory_ids),
        )
    with col3:
        st.metric(
            "Batch Memory",
            len(batch_memory_ids),
        )
    if memory_ids:
        with st.expander(
            "🔎 Показать Memory IDs",
            expanded=False,
        ):
            st.code(
                ", ".join(
                    str(item)
                    for item in memory_ids
                )
            )
# ============================================================
# BATCH
# ============================================================
def _render_batch(
    result: Dict[str, Any],
) -> None:
    batch_check = _safe_dict(
        result.get("batch_check")
    )
    if batch_check:
        st.markdown(
            "### 🔍 BatchController"
        )
        controller_status = _safe_string(
            batch_check.get("status")
        )
        league = _safe_string(
            batch_check.get("league")
        )
        season_id = _safe_string(
            batch_check.get("season_id")
        )
        required = _safe_int(
            batch_check.get(
                "required_matches"
            )
        )
        new_matches = _safe_int(
            batch_check.get(
                "new_matches"
            )
        )
        fingerprint = batch_check.get(
            "batch_fingerprint"
        )
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(
                "Controller",
                controller_status,
            )
        with col2:
            st.metric(
                "Новых матчей",
                new_matches,
            )
        with col3:
            st.metric(
                "Требуется",
                required,
            )
        with col4:
            st.metric(
                "Season",
                season_id,
            )
        st.caption(
            f"Лига: {league}"
        )
        if fingerprint:
            st.success(
                "🔐 Batch fingerprint присутствует."
            )
            st.code(
                str(fingerprint)
            )
        else:
            st.info(
                "ℹ️ Batch fingerprint не предоставлен."
            )
    batches = _get_batches(result)
    if not batches:
        return
    st.markdown(
        "### 📦 Детали batch"
    )
    rows = []
    for batch in batches:
        rows.append(
            {
                "Лига": _safe_string(
                    batch.get("league")
                ),
                "Batch": _safe_int(
                    batch.get("batch_size")
                ),
                "Обработано": _safe_int(
                    batch.get("processed")
                ),
                "Уже было": _safe_int(
                    batch.get("already_processed")
                ),
                "Обучено": _safe_int(
                    batch.get("learned")
                ),
                "Memory": _safe_int(
                    batch.get("memory_events")
                ),
                "Ошибки": _error_count(
                    batch.get("errors")
                ),
                "Статус": _safe_string(
                    batch.get("status")
                ),
            }
        )
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
    )
# ============================================================
# ERROR ANALYSIS
# ============================================================
def _render_error_analysis(
    result: Dict[str, Any],
) -> None:
    """
    Отображает результат LearningAnalyzer,
    если он возвращён ETC backend.
    """
    analysis = _safe_dict(
        result.get("analysis")
    )
    if not analysis:
        analysis = _safe_dict(
            result.get("learning_analysis")
        )
    if not analysis:
        return
    st.divider()
    st.markdown(
        "## 🔬 Анализ ошибок FAJ"
    )
    records = _safe_int(
        analysis.get("records_analyzed")
    )
    st.caption(
        f"Записей ошибок проанализировано: {records}"
    )
    col1, col2, col3 = st.columns(3)
    severity = _safe_dict(
        analysis.get("severity")
    )
    xg = _safe_dict(
        analysis.get("xg")
    )
    with col1:
        st.metric(
            "Средняя severity",
            round(
                _safe_float(
                    severity.get("average")
                ),
                3,
            ),
        )
    with col2:
        st.metric(
            "xG ошибок",
            _safe_int(
                xg.get("count")
            ),
        )
    with col3:
        st.metric(
            "Средняя xG ошибка",
            round(
                _safe_float(
                    xg.get("average")
                ),
                3,
            ),
        )
    # --------------------------------------------------------
    # ERROR FREQUENCY
    # --------------------------------------------------------
    error_frequency = _safe_dict(
        analysis.get("error_frequency")
    )
    if error_frequency:
        st.markdown(
            "### Ошибки по типам"
        )
        rows = [
            {
                "Тип ошибки": key,
                "Количество": value,
            }
            for key, value
            in error_frequency.items()
        ]
        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
        )
    # --------------------------------------------------------
    # CAUSE FREQUENCY
    # --------------------------------------------------------
    cause_frequency = _safe_dict(
        analysis.get("cause_frequency")
    )
    if cause_frequency:
        st.markdown(
            "### Причины ошибок"
        )
        rows = [
            {
                "Причина": key,
                "Количество": value,
            }
            for key, value
            in cause_frequency.items()
        ]
        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
        )
# ============================================================
# PATTERNS
# ============================================================
def _render_patterns(
    result: Dict[str, Any],
) -> None:
    analysis = _safe_dict(
        result.get("analysis")
    )
    if not analysis:
        analysis = _safe_dict(
            result.get("learning_analysis")
        )
    patterns = analysis.get(
        "patterns",
        [],
    )
    if not isinstance(patterns, list):
        return
    patterns = [
        item
        for item in patterns
        if isinstance(item, dict)
    ]
    if not patterns:
        return
    st.markdown(
        "### 🔁 Повторяющиеся ошибки"
    )
    rows = []
    for pattern in patterns:
        rows.append(
            {
                "Ошибка": _safe_string(
                    pattern.get("error_type")
                ),
                "Причина": _safe_string(
                    pattern.get("cause_type")
                ),
                "Количество": _safe_int(
                    pattern.get("count")
                ),
                "Severity": round(
                    _safe_float(
                        pattern.get(
                            "average_severity"
                        )
                    ),
                    3,
                ),
                "xG deviation": round(
                    _safe_float(
                        pattern.get(
                            "average_xg_error"
                        )
                    ),
                    3,
                ),
                "Confidence": round(
                    _safe_float(
                        pattern.get(
                            "average_confidence"
                        )
                    ),
                    3,
                ),
                "Signal": round(
                    _safe_float(
                        pattern.get(
                            "signal_strength"
                        )
                    ),
                    3,
                ),
                "Priority": _safe_string(
                    pattern.get("priority")
                ),
            }
        )
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
    )
# ============================================================
# SIGNALS
# ============================================================
def _render_signals(
    result: Dict[str, Any],
) -> None:
    analysis = _safe_dict(
        result.get("analysis")
    )
    if not analysis:
        analysis = _safe_dict(
            result.get("learning_analysis")
        )
    signals = analysis.get(
        "signals",
        [],
    )
    if not isinstance(signals, list):
        return
    signals = [
        item
        for item in signals
        if isinstance(item, dict)
    ]
    if not signals:
        return
    st.markdown(
        "### 📡 ETC Signals"
    )
    st.warning(
        "ETC Signal — это аналитический сигнал "
        "для следующего уровня ETC. "
        "Он НЕ означает автоматическое изменение параметра."
    )
    rows = []
    for signal in signals:
        rows.append(
            {
                "Priority": _safe_string(
                    signal.get("priority")
                ),
                "Тип": _safe_string(
                    signal.get("signal_type")
                ),
                "Ошибка": _safe_string(
                    signal.get("error_type")
                ),
                "Причина": _safe_string(
                    signal.get("cause_type")
                ),
                "Count": _safe_int(
                    signal.get("count")
                ),
                "Severity": round(
                    _safe_float(
                        signal.get(
                            "average_severity"
                        )
                    ),
                    3,
                ),
                "xG": round(
                    _safe_float(
                        signal.get(
                            "average_xg_error"
                        )
                    ),
                    3,
                ),
                "Strength": round(
                    _safe_float(
                        signal.get(
                            "signal_strength"
                        )
                    ),
                    3,
                ),
            }
        )
    st.dataframe(
        pd.DataFrame(rows),
        width="stretch",
        hide_index=True,
    )
# ============================================================
# LAST RESULT
# ============================================================
def _render_last_result() -> None:
    result = st.session_state.get(
        "etc_last_result"
    )
    if not isinstance(result, dict):
        st.info(
            "ETC ещё не запускался в этой сессии."
        )
        return
    st.divider()
    st.markdown(
        "## 📦 Последний batch"
    )
    _render_result_status(result)
    processed = _safe_int(
        result.get("processed")
    )
    already_processed = _safe_int(
        result.get("already_processed")
    )
    failed = _safe_int(
        result.get("failed")
    )
    total = _safe_int(
        result.get("total")
    )
    learning_events = _safe_int(
        result.get("learning_events")
    )
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric(
            "Всего",
            total,
        )
    with col2:
        st.metric(
            "Обработано",
            processed,
        )
    with col3:
        st.metric(
            "Уже было",
            already_processed,
        )
    with col4:
        st.metric(
            "Ошибки",
            failed,
        )
    with col5:
        st.metric(
            "Learning Events",
            learning_events,
        )
    _render_match_ledger(result)
    _render_historical_processed(result)
    _render_memory(result)
    _render_batch(result)
    errors = _error_count(
        result.get("errors")
    )
    if errors:
        raw_errors = _get_errors(
            result
        )
        st.markdown(
            "### ❌ Ошибки"
        )
        with st.expander(
            f"Показать ошибки ({errors})",
            expanded=True,
        ):
            for index, error in enumerate(
                raw_errors,
                start=1,
            ):
                if isinstance(error, dict):
                    match_id = error.get(
                        "match_id"
                    )
                    stage = error.get(
                        "stage"
                    )
                    status = error.get(
                        "status"
                    )
                    message = error.get(
                        "error",
                        str(error),
                    )
                    prefix = (
                        f"#{match_id}"
                        if match_id is not None
                        else "BATCH"
                    )
                    if stage:
                        prefix += (
                            f" • {stage}"
                        )
                    if status:
                        prefix += (
                            f" • {status}"
                        )
                    st.error(
                        f"{index}. "
                        f"{prefix}\n\n"
                        f"{message}"
                    )
                else:
                    st.error(
                        f"{index}. {error}"
                    )
    elapsed = st.session_state.get(
        "etc_last_elapsed"
    )
    if elapsed is not None:
        st.caption(
            f"⏱️ Время запуска: "
            f"{float(elapsed):.2f} сек."
        )
# ============================================================
# WHAT HAPPENED
# ============================================================
def _render_what_happened(
    result: Optional[Dict[str, Any]],
) -> None:
    if not result:
        return
    st.divider()
    st.markdown(
        "## 🔎 Что произошло"
    )
    status = _safe_string(
        result.get("status"),
        "unknown",
    )
    processed = _safe_int(
        result.get("processed")
    )
    already_processed = _safe_int(
        result.get("already_processed")
    )
    failed = _safe_int(
        result.get("failed")
    )
    total = _safe_int(
        result.get("total")
    )
    learning_events = _safe_int(
        result.get("learning_events")
    )
    batch_completed = bool(
        result.get(
            "batch_completed",
            False,
        )
    )
    if (
        batch_completed
        and failed == 0
        and total > 0
    ):
        st.success(
            "✅ Полная цепочка ETC завершена."
        )
        st.markdown(
            f"""
**{processed} из {total} матчей** успешно прошли ETC.
Цепочка:
1. `FACTS`
2. `BatchController`
3. `ETCLearningEngine`
4. `StatisticalAnalyzer`
5. `LearningAnalyzer`
6. `LearningMemory`
7. `batch_learning marker`
8. `BATCH COMPLETED`
Создано Learning Events: **{learning_events}**.
"""
        )
        if already_processed > 0:
            st.info(
                f"ℹ️ {already_processed} матчей уже были обработаны ранее."
            )
        return
    if (
        processed > 0
        and failed > 0
    ):
        st.warning(
            f"⚠️ Batch частичный: "
            f"{processed} успешно, "
            f"{failed} с ошибкой."
        )
        return
    if status in (
        "empty",
        "nothing_to_process",
    ):
        st.info(
            "Новых матчей для обучения сейчас нет."
        )
        return
    if status == "already_processed":
        st.info(
            "ℹ️ Backend определил, что матч "
            "или batch уже обрабатывался."
        )
        return
    st.info(
        f"Текущий результат ETC: `{status}`"
    )
# ============================================================
# NEXT STEP
# ============================================================
def _render_next_step(
    status: Dict[str, Any],
    result: Optional[Dict[str, Any]],
) -> None:
    st.divider()
    st.markdown(
        "## 👉 Что делать дальше"
    )
    pending = _safe_int(
        status.get("pending_matches")
    )
    if result:
        result_status = _safe_string(
            result.get("status"),
            "",
        )
        errors = _error_count(
            result.get("errors")
        )
        batch_completed = bool(
            result.get(
                "batch_completed",
                False,
            )
        )
        if errors > 0:
            st.warning(
                "⚠️ Сначала проверь ошибки выше. "
                "Не переходи дальше, пока причина "
                "не понятна."
            )
            return
        if (
            result_status == "completed"
            or batch_completed
        ):
            st.success(
                "✅ Этот batch успешно обучен."
            )
            if pending > 0:
                st.info(
                    f"Следующий шаг: обработать "
                    f"следующий batch. Сейчас готово "
                    f"ещё {pending} матчей."
                )
            else:
                st.info(
                    "Сейчас новых готовых матчей нет. "
                    "Следующий этап — добавить новые "
                    "подтверждённые FACTS."
                )
            return
        if result_status in (
            "empty",
            "nothing_to_process",
        ):
            st.info(
                "⏳ Сейчас готовых матчей для обучения нет."
            )
            return
    if pending > 0:
        st.info(
            f"📦 Сейчас доступно {pending} "
            f"матчей для обучения."
        )
    else:
        st.info(
            "⏳ Готовых матчей для нового batch пока нет."
        )
    st.markdown(
        """
### Рабочий цикл FAJ
**MATCH**
→ итоговый счёт
→ статистика
→ FACT
→ MATCH READY
→ накопление batch
→ ETC
→ StatisticalAnalyzer
→ LearningAnalyzer
→ LearningMemory
→ следующий batch
"""
    )
# ============================================================
# TECHNICAL DETAILS
# ============================================================
def _render_technical_details(
    result: Optional[Dict[str, Any]],
) -> None:
    if not result:
        return
    st.divider()
    with st.expander(
        "🔧 Технические детали ETC",
        expanded=False,
    ):
        st.json(result)
# ============================================================
# CONTRACT
# ============================================================
def _render_contract() -> None:
    st.divider()
    st.markdown(
        "### 🛡️ Архитектурные границы ETC"
    )
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.success(
            "SQLite: только через backend"
        )
    with col2:
        st.success(
            "FACTS: не изменяются"
        )
    with col3:
        st.success(
            "DELETE / DROP: отсутствуют"
        )
    with col4:
        st.success(
            "Predictions: не изменяются"
        )
    st.caption(
        "LearningAnalyzer формирует аналитические сигналы. "
        "ETC Page не применяет эти сигналы автоматически."
    )
# ============================================================
# MAIN
# ============================================================
def main() -> None:
    _configure_page()
    _render_header()
    try:
        controller = get_etc_controller()
    except Exception as exc:
        st.error(
            "❌ Не удалось запустить ETCController."
        )
        st.exception(exc)
        st.stop()
    # --------------------------------------------------------
    # FLOW
    # --------------------------------------------------------
    _render_flow()
    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------
    status = _render_status(
        controller
    )
    # --------------------------------------------------------
    # CONTROL
    # --------------------------------------------------------
    _render_control(
        controller
    )
    # --------------------------------------------------------
    # LAST RESULT
    # --------------------------------------------------------
    result = st.session_state.get(
        "etc_last_result"
    )
    if not isinstance(
        result,
        dict,
    ):
        result = None
    _render_last_result()
    # --------------------------------------------------------
    # ANALYSIS
    # --------------------------------------------------------
    _render_error_analysis(
        result or {}
    )
    _render_patterns(
        result or {}
    )
    _render_signals(
        result or {}
    )
    # --------------------------------------------------------
    # EXPLANATION
    # --------------------------------------------------------
    _render_what_happened(
        result
    )
    # --------------------------------------------------------
    # NEXT STEP
    # --------------------------------------------------------
    _render_next_step(
        status,
        result,
    )
    # --------------------------------------------------------
    # TECHNICAL
    # --------------------------------------------------------
    _render_technical_details(
        result
    )
    # --------------------------------------------------------
    # CONTRACT
    # --------------------------------------------------------
    _render_contract()
    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------
    st.divider()
    st.caption(
        f"FAJ Platform v{APP_VERSION} • "
        f"ETC Page v{ETC_PAGE_VERSION} • "
        f"Evolution Training Center"
    )
# ============================================================
# DIRECT ENTRY POINT
# ============================================================
if __name__ == "__main__":
    main()
