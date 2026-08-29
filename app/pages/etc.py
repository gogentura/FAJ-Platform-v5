#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================
ФАЙЛ:
    app/pages/etc.py
ETC PAGE v6.1
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

ИСПРАВЛЕНИЯ v6.1 (по аудиту)
============================================================
1. Добавлено отображение warnings из ErrorClassifier v2.2
2. Добавлено отображение data_incomplete в error_type
3. Убран некорректный fallback analysis → learning_result → analysis
4. Использован правильный путь: result → batches → learning_result → analysis
5. Убран устаревший ключ success, используется status
6. Исправлен вызов _render_error_analysis() с правильным анализом
7. Исправлен вызов _render_patterns() с правильным анализом
8. Исправлен вызов _render_signals() с правильным анализом
9. Добавлена функция _extract_analysis() для единого получения analysis
10. Добавлена функция _extract_warnings() для получения warnings

ИСПРАВЛЕНИЯ v6.0
============================================================
1. Унифицирован контракт с ETCController v3.1
2. Убраны множественные fallback'и (already_processed_match_ids, analysis, learning_analysis, match_ledger)
3. Обновлён _render_status() под финальный status() контракт
4. Обновлён _render_last_result() под финальный run() контракт
5. Обновлён _render_error_analysis() под learning_analyzer v2.2
6. Обновлён _render_patterns() с unique_match_count
7. Обновлён _render_signals() с priority и unique_match_count
8. Добавлено отображение warnings и data_incomplete
9. Убраны match_ledger и другие устаревшие ключи
10. Обновлён _render_memory() под memory_before_ids и memory_after_ids
11. Добавлено отображение параметров до/после обучения
12. Совместимость с LearningBatch v2.1
13. Совместимость с ErrorClassifier v2.2

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
    ETCController v3.1
        ↓
    ETCLearningEngine v2.0
        ↓
    BatchController v2.1
        ↓
    LearningBatch v2.1
        ↓
    LearningAnalyzer v2.2
        ↓
    ErrorClassifier v2.2
        ↓
    LearningMemory v2.1

PAGE только отображает полученное состояние.
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
ETC_PAGE_VERSION = "6.1"
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
    """Единственная точка доступа страницы к ETC."""
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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_string(value: Any, default: str = "—") -> str:
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


def _normalize_ids(value: Any) -> List[int]:
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


def _get_errors(result: Dict[str, Any]) -> List[Any]:
    raw = result.get("errors", [])
    if isinstance(raw, list):
        return raw
    if raw:
        return [raw]
    return []


def _get_batches(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = result.get("batches", [])
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


# ============================================================
# EXTRACT ANALYSIS (ИСПРАВЛЕНО v6.1)
# ============================================================

def _extract_analysis(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Извлекает analysis из результата ETCController v3.1.

    Правильный путь:
        result
          └── batches[0]
                └── learning_result
                      └── analysis

    Возвращает пустой dict, если analysis не найден.
    """
    if not result:
        return {}

    # Прямой путь (если вдруг есть)
    direct = result.get("analysis")
    if isinstance(direct, dict) and direct:
        return direct

    # Правильный путь через batches
    batches = _get_batches(result)
    if batches:
        first_batch = batches[0]
        learning_result = _safe_dict(first_batch.get("learning_result"))
        analysis = _safe_dict(learning_result.get("analysis"))
        if analysis:
            return analysis

    return {}


def _extract_warnings(result: Dict[str, Any]) -> List[str]:
    """
    Извлекает warnings из result.

    Warnings могут быть в:
        1. result.warnings (верхний уровень)
        2. learning_result.warnings
        3. analysis.warnings
    """
    warnings: List[str] = []

    # 1. Верхний уровень
    top_warnings = result.get("warnings", [])
    if isinstance(top_warnings, list):
        warnings.extend(top_warnings)

    # 2. Через learning_result
    batches = _get_batches(result)
    if batches:
        first_batch = batches[0]
        learning_result = _safe_dict(first_batch.get("learning_result"))
        lr_warnings = learning_result.get("warnings", [])
        if isinstance(lr_warnings, list):
            warnings.extend(lr_warnings)

        # 3. Через analysis
        analysis = _safe_dict(learning_result.get("analysis"))
        analysis_warnings = analysis.get("warnings", [])
        if isinstance(analysis_warnings, list):
            warnings.extend(analysis_warnings)

    # Дедупликация
    seen = set()
    unique = []
    for w in warnings:
        w_str = str(w).strip()
        if w_str and w_str not in seen:
            seen.add(w_str)
            unique.append(w_str)

    return unique


# ============================================================
# HEADER
# ============================================================

def _render_header() -> None:
    st.title("🧠 FAJ ETC")
    st.subheader("Evolution Training Center")
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
BatchController v2.1
  ↓
READY
  ↓
get_learning_batch()
  ↓
LearningBatch v2.1
  ↓
ETCLearningEngine v2.0
  ↓
ErrorClassifier v2.2
  ↓
LearningAnalyzer v2.2
  ↓
LearningMemory v2.1
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

def _render_status(controller: ETCController) -> Dict[str, Any]:
    try:
        status = _safe_dict(controller.status())
    except Exception as exc:
        st.error("❌ Не удалось получить состояние ETC.")
        st.exception(exc)
        return {}

    status_value = _safe_string(status.get("status"), "UNKNOWN")
    pending = _safe_int(status.get("pending_matches"))
    last_batch_id = _safe_string(status.get("last_batch_id"), "—")
    timestamp = _safe_string(status.get("timestamp"), "—")

    st.markdown("### 📡 Состояние ETC")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Готово к обучению", pending)

    with col2:
        st.metric("Статус ETC", status_value)

    with col3:
        st.metric("Последний batch", last_batch_id[:12] if len(last_batch_id) > 12 else last_batch_id)

    with col4:
        st.metric("Обновлено", timestamp[:19] if len(timestamp) > 19 else timestamp)

    # Дополнительная информация
    features = _safe_dict(status.get("features", {}))
    if features:
        cols = st.columns(len(features))
        for idx, (key, value) in enumerate(features.items()):
            with cols[idx]:
                st.caption(f"{key}: {'✅' if value else '❌'}")

    st.divider()
    return status


# ============================================================
# CONTROL
# ============================================================

def _render_control(controller: ETCController) -> None:
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

    # Выбор лиги
    available_leagues = ["РПЛ", "АПЛ", "Ла Лига", "ЛЧ"]
    league = st.selectbox(
        "Турнир",
        options=[None] + available_leagues,
        format_func=lambda x: "Все турниры" if x is None else x,
        key="etc_league_select",
    )

    col1, col2 = st.columns([3, 1])

    with col1:
        if st.button(
            "🧠 ЗАПУСТИТЬ ОБУЧЕНИЕ",
            type="primary",
            use_container_width=True,
            key="etc_run_button",
        ):
            started = datetime.now()

            with st.spinner("FAJ ETC выполняет batch..."):
                try:
                    result = controller.run(
                        league=league,
                        limit=int(limit),
                        force=bool(force),
                    )
                except Exception as exc:
                    st.error(f"❌ Ошибка ETCController: {exc}")
                    st.exception(exc)
                    return

            elapsed = (datetime.now() - started).total_seconds()

            st.session_state["etc_last_result"] = _safe_dict(result)
            st.session_state["etc_last_elapsed"] = elapsed
            st.rerun()

    with col2:
        if st.button(
            "🔄 Очистить кеш",
            use_container_width=True,
            key="etc_clear_cache",
        ):
            st.cache_resource.clear()
            st.session_state.pop("etc_last_result", None)
            st.rerun()


# ============================================================
# RESULT STATUS
# ============================================================

def _render_result_status(result: Dict[str, Any]) -> None:
    """Отображает статус результата. Использует только status (без success)."""
    status = _safe_string(result.get("status"), "unknown")
    errors = _error_count(result.get("errors"))

    if status == "completed" and errors == 0:
        st.success("✅ BATCH COMPLETED — ETC успешно завершил обучение.")
        return

    if status == "completed_with_errors":
        st.warning(f"⚠️ BATCH COMPLETED WITH ERRORS — {errors} ошибок.")
        return

    if status == "nothing_to_process":
        st.info("⏭️ Новых готовых матчей для обучения нет.")
        return

    if status == "partial":
        st.warning("⚠️ Batch обработан частично.")
        return

    if status == "failed":
        st.error(f"❌ ETC завершился с ошибкой: {_safe_string(result.get('message'))}")
        return

    if errors > 0:
        st.error(f"❌ ETC завершился с ошибками. Ошибок: {errors}")
        return

    st.info(f"Статус ETC: {status}")


# ============================================================
# WARNINGS (НОВОЕ v6.1)
# ============================================================

def _render_warnings(result: Dict[str, Any]) -> None:
    """Отображает предупреждения из ErrorClassifier v2.2."""
    warnings = _extract_warnings(result)

    if not warnings:
        return

    st.markdown("### ⚠️ Предупреждения")
    st.caption("Отсутствие данных или неполная информация для анализа.")

    for warning in warnings:
        st.warning(f"• {warning}")


# ============================================================
# LAST RESULT
# ============================================================

def _render_last_result() -> None:
    result = st.session_state.get("etc_last_result")
    if not isinstance(result, dict):
        st.info("ETC ещё не запускался в этой сессии.")
        return

    st.divider()
    st.markdown("## 📦 Последний batch")

    _render_result_status(result)

    # Показываем warnings
    _render_warnings(result)

    # Основные метрики
    processed = _safe_int(result.get("processed"))
    already_processed = _safe_int(result.get("already_processed"))
    failed = _safe_int(result.get("failed"))
    learned = _safe_int(result.get("learned"))
    total = _safe_int(result.get("batch_size", 0))
    learning_events = _safe_int(result.get("learning_events"))
    memory_events = _safe_int(result.get("memory_events"))

    col1, col2, col3, col4, col5, col6 = st.columns(6)

    with col1:
        st.metric("Всего матчей", total)

    with col2:
        st.metric("Обработано", processed)

    with col3:
        st.metric("Уже было", already_processed)

    with col4:
        st.metric("Ошибки", failed)

    with col5:
        st.metric("Изменено параметров", learned)

    with col6:
        st.metric("Learning Events", learning_events)

    # ------------------------------------------------------------
    # PROCESSED MATCH IDS
    # ------------------------------------------------------------

    processed_ids = _normalize_ids(result.get("processed_match_ids", []))
    already_processed_ids = _normalize_ids(result.get("already_processed_match_ids", []))

    if processed_ids or already_processed_ids:
        col1, col2 = st.columns(2)

        with col1:
            if processed_ids:
                st.markdown("**✅ Обработано успешно**")
                st.caption(f"{len(processed_ids)} матчей")
                with st.expander("🔎 Показать match_id", expanded=False):
                    st.code(", ".join(str(mid) for mid in processed_ids[:20]))

        with col2:
            if already_processed_ids:
                st.markdown("**⏭️ Уже обработаны ранее**")
                st.caption(f"{len(already_processed_ids)} матчей")
                with st.expander("🔎 Показать match_id", expanded=False):
                    st.code(", ".join(str(mid) for mid in already_processed_ids[:20]))

    # ------------------------------------------------------------
    # PARAMETER CHANGES
    # ------------------------------------------------------------

    param_changes = _safe_list(result.get("parameter_changes", []))
    if param_changes:
        st.markdown("### 📊 Изменения параметров")
        rows = []
        for change in param_changes:
            rows.append({
                "Параметр": _safe_string(change.get("parameter")),
                "Было": round(_safe_float(change.get("old_value")), 4),
                "Стало": round(_safe_float(change.get("new_value")), 4),
                "Delta": round(_safe_float(change.get("delta")), 4),
                "History ID": _safe_int(change.get("history_id")),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # ------------------------------------------------------------
    # MEMORY
    # ------------------------------------------------------------

    _render_memory(result)

    # ------------------------------------------------------------
    # BATCH CHECK
    # ------------------------------------------------------------

    _render_batch(result)

    # ------------------------------------------------------------
    # ERRORS
    # ------------------------------------------------------------

    errors = _error_count(result.get("errors"))
    if errors:
        raw_errors = _get_errors(result)
        st.markdown("### ❌ Ошибки")
        with st.expander(f"Показать ошибки ({errors})", expanded=True):
            for idx, error in enumerate(raw_errors, start=1):
                if isinstance(error, dict):
                    match_id = error.get("match_id")
                    stage = error.get("stage")
                    status = error.get("status")
                    message = error.get("error", str(error))

                    prefix = f"#{match_id}" if match_id is not None else "BATCH"
                    if stage:
                        prefix += f" • {stage}"
                    if status:
                        prefix += f" • {status}"

                    st.error(f"{idx}. {prefix}\n\n{message}")
                else:
                    st.error(f"{idx}. {error}")

    elapsed = st.session_state.get("etc_last_elapsed")
    if elapsed is not None:
        st.caption(f"⏱️ Время выполнения: {float(elapsed):.2f} сек.")


# ============================================================
# MEMORY
# ============================================================

def _render_memory(result: Dict[str, Any]) -> None:
    memory_before_ids = _normalize_ids(result.get("memory_before_ids", []))
    memory_after_ids = _normalize_ids(result.get("memory_after_ids", []))
    parameter_history_ids = _normalize_ids(result.get("parameter_history_ids", []))

    st.markdown("### 🧠 LearningMemory")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("BEFORE snapshot", len(memory_before_ids))

    with col2:
        st.metric("AFTER snapshot", len(memory_after_ids))

    with col3:
        st.metric("Parameter History", len(parameter_history_ids))

    if memory_before_ids:
        with st.expander("🔎 BEFORE IDs", expanded=False):
            st.code(", ".join(str(mid) for mid in memory_before_ids[:20]))

    if memory_after_ids:
        with st.expander("🔎 AFTER IDs", expanded=False):
            st.code(", ".join(str(mid) for mid in memory_after_ids[:20]))


# ============================================================
# BATCH
# ============================================================

def _render_batch(result: Dict[str, Any]) -> None:
    # Проверяем batch_check в каждой лиге
    batches = _get_batches(result)

    if not batches:
        # Проверяем прямой batch_check
        batch_check = _safe_dict(result.get("batch_check"))
        if batch_check:
            _render_batch_check(batch_check)
        return

    st.markdown("### 📦 Детали batch")

    for idx, batch in enumerate(batches):
        with st.expander(f"Batch #{idx + 1}: {_safe_string(batch.get('league'))}", expanded=(idx == 0)):
            # Batch check
            batch_check = _safe_dict(batch.get("batch_check"))
            if batch_check:
                _render_batch_check(batch_check)

            col1, col2, col3, col4, col5 = st.columns(5)

            with col1:
                st.metric("Размер", _safe_int(batch.get("batch_size")))

            with col2:
                st.metric("Обработано", _safe_int(batch.get("processed")))

            with col3:
                st.metric("Уже было", _safe_int(batch.get("already_processed")))

            with col4:
                # errors в batch — это int (счётчик), не список
                st.metric("Ошибки", _safe_int(batch.get("errors")))

            with col5:
                st.metric("Статус", _safe_string(batch.get("status")))

            # Match IDs
            selected_ids = _normalize_ids(batch.get("selected_match_ids", []))
            if selected_ids:
                st.caption(f"Выбрано матчей: {len(selected_ids)}")
                with st.expander("🔎 Показать match_id", expanded=False):
                    st.code(", ".join(str(mid) for mid in selected_ids[:20]))


def _render_batch_check(batch_check: Dict[str, Any]) -> None:
    status = _safe_string(batch_check.get("status"))
    required = _safe_int(batch_check.get("required_matches"))
    completed = _safe_int(batch_check.get("completed_matches"))
    processed = _safe_int(batch_check.get("processed_matches"))
    new_matches = _safe_int(batch_check.get("new_matches"))
    remaining = _safe_int(batch_check.get("remaining_matches"))
    league = _safe_string(batch_check.get("league"))
    reason = _safe_string(batch_check.get("reason"))

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Статус", status)

    with col2:
        st.metric("Требуется", required)

    with col3:
        st.metric("Новых", new_matches)

    with col4:
        st.metric("Осталось", remaining)

    with col5:
        st.metric("Всего завершено", completed)

    st.caption(f"Лига: {league} | Обработано ранее: {processed}")

    if reason:
        st.caption(f"Причина: {reason}")

    fingerprint = batch_check.get("batch_fingerprint")
    if fingerprint:
        st.success("🔐 Batch fingerprint присутствует.")
        st.code(str(fingerprint)[:64] + ("..." if len(str(fingerprint)) > 64 else ""))
    else:
        st.info("ℹ️ Batch fingerprint не предоставлен.")


# ============================================================
# ERROR ANALYSIS (ИСПРАВЛЕНО v6.1)
# ============================================================

def _render_error_analysis(result: Dict[str, Any]) -> None:
    """
    Отображает результат LearningAnalyzer v2.2.
    Использует _extract_analysis() для правильного пути.
    """
    analysis = _extract_analysis(result)

    if not analysis:
        return

    st.divider()
    st.markdown("## 🔬 Анализ ошибок FAJ")

    records_analyzed = _safe_int(analysis.get("records_analyzed"))
    unique_matches = _safe_int(analysis.get("unique_matches_analyzed"))

    st.caption(f"Записей ошибок проанализировано: {records_analyzed} | Уникальных матчей: {unique_matches}")

    # Severity
    severity = _safe_dict(analysis.get("severity"))
    xg = _safe_dict(analysis.get("xg"))

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Средняя severity", round(_safe_float(severity.get("average")), 3))

    with col2:
        st.metric("Max severity", _safe_int(severity.get("max")))

    with col3:
        st.metric("xG записей", _safe_int(xg.get("count")))

    with col4:
        st.metric("Средняя xG ошибка", round(_safe_float(xg.get("average")), 3))

    # xG доступность
    has_xg = xg.get("has_xg_data", False)
    if not has_xg:
        st.info("ℹ️ xG данные отсутствуют или неполные.")
    elif xg.get("count", 0) > 0:
        st.caption(f"xG данные доступны: {xg.get('count')} записей")

    # Показываем warnings из analysis
    analysis_warnings = analysis.get("warnings", [])
    if isinstance(analysis_warnings, list) and analysis_warnings:
        st.markdown("#### ⚠️ Предупреждения анализа")
        for warning in analysis_warnings[:5]:
            st.caption(f"• {warning}")

    # ------------------------------------------------------------
    # ERROR FREQUENCY
    # ------------------------------------------------------------

    error_frequency = _safe_dict(analysis.get("error_frequency"))
    if error_frequency:
        st.markdown("### Ошибки по типам")
        rows = [
            {"Тип ошибки": key, "Количество": value}
            for key, value in error_frequency.items()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # ------------------------------------------------------------
    # CAUSE FREQUENCY
    # ------------------------------------------------------------

    cause_frequency = _safe_dict(analysis.get("cause_frequency"))
    if cause_frequency:
        st.markdown("### Причины ошибок")
        rows = [
            {"Причина": key, "Количество": value}
            for key, value in cause_frequency.items()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ============================================================
# PATTERNS (ИСПРАВЛЕНО v6.1)
# ============================================================

def _render_patterns(result: Dict[str, Any]) -> None:
    """Отображает повторяющиеся ошибки. Использует _extract_analysis()."""
    analysis = _extract_analysis(result)

    patterns = analysis.get("patterns", [])
    if not isinstance(patterns, list):
        return

    patterns = [item for item in patterns if isinstance(item, dict)]
    if not patterns:
        return

    st.markdown("### 🔁 Повторяющиеся ошибки")

    rows = []
    for pattern in patterns:
        rows.append({
            "Ошибка": _safe_string(pattern.get("error_type")),
            "Причина": _safe_string(pattern.get("cause_type")),
            "Событий": _safe_int(pattern.get("event_count")),
            "Матчей": _safe_int(pattern.get("unique_match_count")),
            "Severity": round(_safe_float(pattern.get("average_severity")), 3),
            "xG dev": round(_safe_float(pattern.get("average_xg_error")), 3),
            "Confidence": round(_safe_float(pattern.get("average_confidence")), 3),
            "Strength": round(_safe_float(pattern.get("signal_strength")), 3),
            "Priority": _safe_string(pattern.get("priority")),
        })

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # Показать рекомендации
    for pattern in patterns[:3]:
        recommendations = pattern.get("recommendations", [])
        if recommendations:
            with st.expander(f"💡 {_safe_string(pattern.get('error_type'))} → {_safe_string(pattern.get('cause_type'))}"):
                for rec in recommendations[:3]:
                    st.write(f"• {rec}")


# ============================================================
# SIGNALS (ИСПРАВЛЕНО v6.1)
# ============================================================

def _render_signals(result: Dict[str, Any]) -> None:
    """Отображает ETC signals. Использует _extract_analysis()."""
    analysis = _extract_analysis(result)

    signals = analysis.get("signals", [])
    if not isinstance(signals, list):
        return

    signals = [item for item in signals if isinstance(item, dict)]
    if not signals:
        return

    st.markdown("### 📡 ETC Signals")

    st.warning(
        "ETC Signal — это аналитический сигнал "
        "для следующего уровня ETC. "
        "Он НЕ означает автоматическое изменение параметра."
    )

    # Топ сигналы
    top_signals = analysis.get("top_signals", [])
    if top_signals:
        st.caption("**Топ сигналы для приоритетного анализа**")

        rows = []
        for signal in top_signals[:10]:
            rows.append({
                "Priority": _safe_string(signal.get("priority")),
                "Ошибка": _safe_string(signal.get("error_type")),
                "Причина": _safe_string(signal.get("cause_type")),
                "Событий": _safe_int(signal.get("event_count")),
                "Матчей": _safe_int(signal.get("unique_match_count")),
                "Severity": round(_safe_float(signal.get("average_severity")), 3),
                "Strength": round(_safe_float(signal.get("signal_strength")), 3),
            })

        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

        # Показать рекомендации для топ-сигналов
        for signal in top_signals[:2]:
            recommendations = signal.get("recommendations", [])
            if recommendations:
                with st.expander(f"💡 Signal: {_safe_string(signal.get('error_type'))} (Priority: {_safe_string(signal.get('priority'))})"):
                    for rec in recommendations[:2]:
                        st.write(f"• {rec}")


# ============================================================
# WHAT HAPPENED
# ============================================================

def _render_what_happened(result: Optional[Dict[str, Any]]) -> None:
    if not result:
        return

    st.divider()
    st.markdown("## 🔎 Что произошло")

    status = _safe_string(result.get("status"))
    processed = _safe_int(result.get("processed"))
    already_processed = _safe_int(result.get("already_processed"))
    failed = _safe_int(result.get("failed"))
    learned = _safe_int(result.get("learned"))
    total = _safe_int(result.get("batch_size", 0))
    learning_events = _safe_int(result.get("learning_events"))

    if status == "completed" and failed == 0 and total > 0:
        st.success("✅ Полная цепочка ETC завершена.")
        st.markdown(
            f"""
**{processed} из {total} матчей** успешно прошли ETC.

Цепочка:
1. `FACTS` → `BatchController v2.1`
2. `LearningBatch v2.1`
3. `ETCLearningEngine v2.0`
4. `ErrorClassifier v2.2`
5. `LearningAnalyzer v2.2`
6. `LearningMemory v2.1`
7. `batch_learning marker`
8. `BATCH COMPLETED`

Создано Learning Events: **{learning_events}**.
Изменено параметров: **{learned}**.
"""
        )
        if already_processed > 0:
            st.info(f"ℹ️ {already_processed} матчей уже были обработаны ранее.")
        return

    if processed > 0 and failed > 0:
        st.warning(f"⚠️ Batch частичный: {processed} успешно, {failed} с ошибкой.")
        return

    if status in ("empty", "nothing_to_process"):
        st.info("Новых матчей для обучения сейчас нет.")
        return

    st.info(f"Текущий результат ETC: `{status}`")


# ============================================================
# NEXT STEP
# ============================================================

def _render_next_step(status: Dict[str, Any], result: Optional[Dict[str, Any]]) -> None:
    st.divider()
    st.markdown("## 👉 Что делать дальше")

    pending = _safe_int(status.get("pending_matches"))

    if result:
        result_status = _safe_string(result.get("status"))
        errors = _error_count(result.get("errors"))

        if errors > 0:
            st.warning("⚠️ Сначала проверь ошибки выше. Не переходи дальше, пока причина не понятна.")
            return

        if result_status == "completed":
            st.success("✅ Этот batch успешно обучен.")
            if pending > 0:
                st.info(f"Следующий шаг: обработать следующий batch. Сейчас готово ещё {pending} матчей.")
            else:
                st.info("Сейчас новых готовых матчей нет. Следующий этап — добавить новые подтверждённые FACTS.")
            return

        if result_status in ("empty", "nothing_to_process"):
            st.info("⏳ Сейчас готовых матчей для обучения нет.")
            return

    if pending > 0:
        st.info(f"📦 Сейчас доступно {pending} матчей для обучения.")
    else:
        st.info("⏳ Готовых матчей для нового batch пока нет.")

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
→ ErrorClassifier
→ LearningAnalyzer
→ LearningMemory
→ следующий batch
"""
    )


# ============================================================
# TECHNICAL DETAILS
# ============================================================

def _render_technical_details(result: Optional[Dict[str, Any]]) -> None:
    if not result:
        return

    st.divider()
    with st.expander("🔧 Технические детали ETC", expanded=False):
        st.json(result)


# ============================================================
# CONTRACT
# ============================================================

def _render_contract() -> None:
    st.divider()
    st.markdown("### 🛡️ Архитектурные границы ETC v6.1")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.success("SQLite: только через backend")

    with col2:
        st.success("FACTS: не изменяются")

    with col3:
        st.success("DELETE / DROP: отсутствуют")

    with col4:
        st.success("Predictions: не изменяются")

    st.caption(
        "ETC Controller v3.1 | LearningBatch v2.1 | "
        "LearningAnalyzer v2.2 | ErrorClassifier v2.2 | "
        "ETC Page v6.1"
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
        st.error("❌ Не удалось запустить ETCController.")
        st.exception(exc)
        st.stop()

    _render_flow()

    status = _render_status(controller)

    _render_control(controller)

    result = st.session_state.get("etc_last_result")
    if not isinstance(result, dict):
        result = None

    _render_last_result()

    # Используем _extract_analysis() для всех аналитических компонентов
    if result:
        _render_error_analysis(result)
        _render_patterns(result)
        _render_signals(result)

    _render_what_happened(result)
    _render_next_step(status, result)
    _render_technical_details(result)
    _render_contract()

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
