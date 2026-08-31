#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================
ФАЙЛ:
    app/pages/etc.py
ETC PAGE v7.2 (E-FINAL UI)
============================================================
НАЗНАЧЕНИЕ
-----------
Прозрачная контрольная панель ETC.
Показывает:
    • состояние ETC;
    • готовые матчи;
    • уже обработанные матчи;
    • последний batch;
    • ошибки FAJ;
    • xG deviations;
    • повторяющиеся error patterns;
    • ETC signals (raw и normalized);
    • ParameterOptimizer proposals;
    • Review Gate (pending/rejected/approved);
    • Auto-apply: DISABLED;
    • следующий шаг цикла.

ИСПРАВЛЕНИЯ v7.2
============================================================
1. Добавлены карточки конкретных матчей из learning_records
2. Показывает для каждого матча: прогноз, факт, ошибки, классификацию, вывод

ИСПРАВЛЕНИЯ v7.1
============================================================
1. None НЕ превращается в 0.0 (_safe_float)
2. Добавлена _display_number() для отображения None как "—"
3. Технические детали перенесены в expander
4. Убран технический мусор с главного экрана
5. Сохранены proposals и review gate

ИСПРАВЛЕНИЯ v7.0 (E-FINAL UI)
============================================================
1. Обновлён Flow под E-FINAL цепочку
2. Убраны BEFORE/AFTER snapshots из UI
3. Убраны parameter_changes (заменены на proposals)
4. Добавлен блок Review Gate
5. Добавлен блок Proposals
6. Добавлено отображение normalized signals
7. Явно показано AUTO-APPLY: DISABLED

ВАЖНО
------
PAGE НЕ:
    • выполняет SQL;
    • изменяет SQLite;
    • изменяет match_results;
    • изменяет predictions;
    • изменяет model_parameters;
    • изменяет learning_memory.

Вся бизнес-логика находится в backend.
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
ETC_PAGE_VERSION = "7.2"
PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"
ETC_CONTROLLER_VERSION = "4.1"

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


# ПАТЧ №3: None НЕ превращается в 0.0
def _safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None:
            return default
        result = float(value)
        if pd.isna(result):
            return default
        return result
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


# ПАТЧ №3: отображение числа с заменой None на "—"
def _display_number(value: Any, digits: int = 2) -> str:
    """Отображает число, заменяя None на '—'."""
    if value is None:
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "—"


# ============================================================
# EXTRACT ANALYSIS
# ============================================================

def _extract_analysis(result: Dict[str, Any]) -> Dict[str, Any]:
    """Извлекает analysis из результата ETCController v4.1."""
    if not result:
        return {}

    direct = result.get("analysis")
    if isinstance(direct, dict) and direct:
        return direct

    batches = _get_batches(result)
    if batches:
        first_batch = batches[0]
        learning_result = _safe_dict(first_batch.get("learning_result"))
        analysis = _safe_dict(learning_result.get("analysis"))
        if analysis:
            return analysis

    return {}


def _extract_warnings(result: Dict[str, Any]) -> List[str]:
    warnings: List[str] = []

    top_warnings = result.get("warnings", [])
    if isinstance(top_warnings, list):
        warnings.extend(top_warnings)

    batches = _get_batches(result)
    if batches:
        first_batch = batches[0]
        learning_result = _safe_dict(first_batch.get("learning_result"))
        lr_warnings = learning_result.get("warnings", [])
        if isinstance(lr_warnings, list):
            warnings.extend(lr_warnings)

        analysis = _safe_dict(learning_result.get("analysis"))
        analysis_warnings = analysis.get("warnings", [])
        if isinstance(analysis_warnings, list):
            warnings.extend(analysis_warnings)

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
        "анализирует ошибки и формирует предложения. "
        "Автоматическое применение параметров отключено."
    )
    st.divider()


# ============================================================
# FLOW (перенесено в технические детали — ПАТЧ №4)
# ============================================================

def _render_flow_technical() -> None:
    """Цепочка ETC — показывается только в технических деталях."""
    st.markdown("### 🔄 Цепочка ETC (E-FINAL)")
    st.code(
        """
FACTS
  ↓
BatchController v2.1
  ↓
READY
  ↓
LearningBatch v2.1
  ↓
ETCLearningEngine v2.0
  ↓
ErrorClassifier v2.2
  ↓
LearningAnalyzer v2.2
  ↓
SIGNALS
  ↓
Signal Adapter (normalization)
  ↓
ParameterOptimizer v2.3
  ↓
PROPOSALS
  ↓
Review Gate (v4.1)
  ↓
├── pending (все)
├── rejected (0)
└── approved (0)
  ↓
🔒 AUTO-APPLY: DISABLED
  ↓
NEXT MATCHES
        """.strip(),
        language="text",
    )
    st.caption("E-FINAL: все proposals проходят Review Gate. Auto-apply отключён.")


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

    st.divider()
    return status


# ============================================================
# CONTROL
# ============================================================

def _render_control(controller: ETCController) -> None:
    st.markdown("### 🧠 Запуск обучения")
    st.caption(
        "ETC получает batch через ETCController v4.1. "
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
# WARNINGS
# ============================================================

def _render_warnings(result: Dict[str, Any]) -> None:
    warnings = _extract_warnings(result)

    if not warnings:
        return

    st.markdown("### ⚠️ Предупреждения")
    st.caption("Отсутствие данных или неполная информация для анализа.")

    for warning in warnings:
        st.warning(f"• {warning}")


# ============================================================
# PROPOSALS
# ============================================================

def _render_proposals(result: Dict[str, Any]) -> None:
    """Отображает proposals из ParameterOptimizer."""
    optimization = _safe_dict(result.get("optimization"))

    if not optimization:
        batches = _get_batches(result)
        if batches:
            first_batch = batches[0]
            optimization = _safe_dict(first_batch.get("optimization"))

    proposals = _safe_list(optimization.get("proposals", []))

    if not proposals:
        return

    st.markdown("### 📋 ParameterOptimizer Proposals")

    st.caption(f"Всего proposals: {len(proposals)}")

    rows = []
    for proposal in proposals:
        rows.append({
            "Параметр": _safe_string(proposal.get("parameter_name")),
            "Текущее": _display_number(proposal.get("current_value"), 4),
            "Предлагаемое": _display_number(proposal.get("proposed_value"), 4),
            "Delta": _display_number(proposal.get("delta"), 4),
            "Priority": _safe_string(proposal.get("priority")),
            "Confidence": _display_number(proposal.get("confidence"), 3),
            "Evidence": _safe_int(proposal.get("unique_match_count")),
            "Статус": _safe_string(proposal.get("status")),
        })

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    for proposal in proposals[:3]:
        reason = proposal.get("reason")
        if reason:
            with st.expander(f"💡 {_safe_string(proposal.get('parameter_name'))} — {_safe_string(proposal.get('priority'))}"):
                st.write(f"• {reason}")


# ============================================================
# REVIEW GATE
# ============================================================

def _render_review_gate(result: Dict[str, Any]) -> None:
    """Отображает Review Gate (pending/rejected/approved)."""
    review = _safe_dict(result.get("review"))

    if not review:
        batches = _get_batches(result)
        if batches:
            first_batch = batches[0]
            review = _safe_dict(first_batch.get("review"))

    if not review:
        return

    st.markdown("### 🛡️ Review Gate")

    total = _safe_int(review.get("total"))
    pending = _safe_int(len(review.get("pending", [])))
    rejected = _safe_int(len(review.get("rejected", [])))
    approved = _safe_int(len(review.get("approved", [])))

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("Всего", total)

    with col2:
        st.metric("⏳ Pending", pending)

    with col3:
        st.metric("❌ Rejected", rejected)

    with col4:
        st.metric("✅ Approved", approved)

    with col5:
        st.metric("🔒 Auto-apply", "DISABLED")

    st.caption("E-FINAL: все proposals находятся в статусе pending. Автоматическое применение отключено.")

    pending_proposals = _safe_list(review.get("pending", []))
    if pending_proposals:
        with st.expander(f"⏳ Pending proposals ({len(pending_proposals)})", expanded=False):
            rows = []
            for proposal in pending_proposals:
                rows.append({
                    "Параметр": _safe_string(proposal.get("parameter_name")),
                    "Предлагаемое": _display_number(proposal.get("proposed_value"), 4),
                    "Priority": _safe_string(proposal.get("priority")),
                    "Confidence": _display_number(proposal.get("confidence"), 3),
                    "Evidence": _safe_int(proposal.get("unique_match_count")),
                })
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ============================================================
# SIGNALS
# ============================================================

def _render_signals(result: Dict[str, Any]) -> None:
    """Отображает ETC signals (raw и normalized)."""
    analysis = _extract_analysis(result)

    raw_signals = _safe_list(analysis.get("signals", []))

    optimization = _safe_dict(result.get("optimization"))
    if not optimization:
        batches = _get_batches(result)
        if batches:
            first_batch = batches[0]
            optimization = _safe_dict(first_batch.get("optimization"))

    normalized_signals = _safe_list(optimization.get("signals", []))
    signals_analyzed = _safe_int(optimization.get("signals_analyzed", 0))

    if not raw_signals and not normalized_signals:
        return

    st.markdown("### 📡 ETC Signals")

    st.warning(
        "ETC Signal — это аналитический сигнал. "
        "Он НЕ означает автоматическое изменение параметра."
    )

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Raw signals (Analyzer)", len(raw_signals))

    with col2:
        st.metric("Normalized signals (Optimizer)", signals_analyzed)

    if normalized_signals:
        st.caption("**Нормализованные сигналы (вход для ParameterOptimizer)**")
        rows = []
        for signal in normalized_signals[:10]:
            rows.append({
                "Ошибка": _safe_string(signal.get("error_type")),
                "Причина": _safe_string(signal.get("cause_type")),
                "Матчей": _safe_int(signal.get("count")),
                "Confidence": _display_number(signal.get("confidence"), 3),
                "Strength": _display_number(signal.get("signal_strength"), 3),
                "Severity": _display_number(signal.get("average_severity"), 3),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    top_signals = _safe_list(analysis.get("top_signals", []))
    if top_signals:
        st.caption("**Топ сигналы (аналитические)**")
        rows = []
        for signal in top_signals[:5]:
            rows.append({
                "Priority": _safe_string(signal.get("priority")),
                "Ошибка": _safe_string(signal.get("error_type")),
                "Причина": _safe_string(signal.get("cause_type")),
                "Матчей": _safe_int(signal.get("unique_match_count")),
                "Strength": _display_number(signal.get("signal_strength"), 3),
            })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ============================================================
# MATCH CARDS (ПАТЧ №6)
# ============================================================

def _render_match_cards(result: Dict[str, Any]) -> None:
    """Показывает карточки конкретных матчей из learning_records."""
    processed_ids = _normalize_ids(result.get("processed_match_ids", []))
    
    if not processed_ids:
        return
    
    st.divider()
    st.markdown("## ⚽ Разбор матчей")
    
    try:
        db = FAJDatabase()
        records = db.get_learning_records(match_ids=processed_ids)
    except Exception as e:
        st.warning(f"⚠️ Не удалось загрузить learning_records: {e}")
        return
    
    if not records:
        st.info("ℹ️ Данные для карточек матчей пока отсутствуют.")
        return
    
    # Группируем по match_id (на случай, если несколько записей на матч)
    records_by_match: Dict[int, Dict[str, Any]] = {}
    for record in records:
        match_id = record.get("match_id")
        if match_id is None:
            continue
        if match_id not in records_by_match:
            records_by_match[match_id] = record
    
    # Показываем карточки
    for match_id in processed_ids:
        record = records_by_match.get(match_id)
        if not record:
            st.info(f"ℹ️ Матч #{match_id} — данные для карточки отсутствуют.")
            continue
        
        home_team = _safe_string(record.get('home_team'), '?')
        away_team = _safe_string(record.get('away_team'), '?')
        
        with st.expander(f"⚽ Матч #{match_id}: {home_team} — {away_team}", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📊 FAJ прогноз**")
                st.write(f"Счёт: {_safe_string(record.get('faj_score'), '—')}")
                faj_home = _display_number(record.get('faj_xg_home'), 2)
                faj_away = _display_number(record.get('faj_xg_away'), 2)
                st.write(f"xG: {faj_home} — {faj_away}")
            
            with col2:
                st.markdown("**📋 Факт**")
                st.write(f"Счёт: {_safe_string(record.get('actual_score'), '—')}")
                actual_home = _display_number(record.get('actual_xg_home'), 2)
                actual_away = _display_number(record.get('actual_xg_away'), 2)
                st.write(f"xG: {actual_home} — {actual_away}")
            
            # Ошибки
            st.markdown("**🔴 Ошибки**")
            errors = []
            if record.get('error_score') is not None:
                errors.append(f"Счёт: {record.get('error_score')}")
            if record.get('error_xg') is not None:
                errors.append(f"xG: {_display_number(record.get('error_xg'), 3)}")
            if record.get('error_btts') is not None:
                errors.append(f"BTTS: {record.get('error_btts')}")
            if record.get('error_total_25') is not None:
                errors.append(f"O2.5: {record.get('error_total_25')}")
            
            if errors:
                st.write(", ".join(errors))
            else:
                st.write("—")
            
            # Тип и причина
            error_type = record.get('error_type')
            cause_type = record.get('cause_type')
            if error_type or cause_type:
                st.markdown("**🏷️ Классификация**")
                st.write(f"Тип: {_safe_string(error_type, '—')} | Причина: {_safe_string(cause_type, '—')}")
                severity = record.get('error_severity')
                if severity is not None:
                    st.write(f"Severity: {severity}/5")
            
            # Рекомендация
            recommendation = record.get('recommendation')
            if recommendation:
                st.markdown("**💡 Вывод**")
                st.write(recommendation)


# ============================================================
# LAST RESULT (ОЧИЩЕН ОТ ТЕХНИЧЕСКОГО МУСОРА — ПАТЧ №4)
# ============================================================

def _render_last_result() -> None:
    result = st.session_state.get("etc_last_result")
    if not isinstance(result, dict):
        st.info("ETC ещё не запускался в этой сессии.")
        return

    st.divider()
    st.markdown("## 📦 Последний batch")

    _render_result_status(result)
    _render_warnings(result)

    # Только основные метрики (без technical мусора)
    processed = _safe_int(result.get("processed"))
    already_processed = _safe_int(result.get("already_processed"))
    failed = _safe_int(result.get("failed"))
    total = _safe_int(result.get("batch_size", 0))

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Всего матчей", total)

    with col2:
        st.metric("Обработано", processed)

    with col3:
        st.metric("Уже было", already_processed)

    with col4:
        st.metric("Ошибки", failed)

    # Показываем только матчи (без technical IDs)
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

    # Proposals и Review Gate (оставляем — они нужны)
    _render_proposals(result)
    _render_review_gate(result)

    # Ошибки (если есть)
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
# ERROR ANALYSIS
# ============================================================

def _render_error_analysis(result: Dict[str, Any]) -> None:
    analysis = _extract_analysis(result)

    if not analysis:
        return

    st.divider()
    st.markdown("## 🔬 Анализ ошибок FAJ")

    records_analyzed = _safe_int(analysis.get("records_analyzed"))
    unique_matches = _safe_int(analysis.get("unique_matches_analyzed"))

    st.caption(f"Записей ошибок проанализировано: {records_analyzed} | Уникальных матчей: {unique_matches}")

    severity = _safe_dict(analysis.get("severity"))
    xg = _safe_dict(analysis.get("xg"))

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Средняя severity", _display_number(severity.get("average"), 3))

    with col2:
        st.metric("Max severity", _safe_int(severity.get("max")))

    with col3:
        st.metric("xG записей", _safe_int(xg.get("count")))

    with col4:
        xg_avg = xg.get("average")
        if xg_avg is None:
            st.metric("Средняя xG ошибка", "—")
        else:
            st.metric("Средняя xG ошибка", _display_number(xg_avg, 3))

    has_xg = xg.get("has_xg_data", False)
    if not has_xg:
        st.info("ℹ️ xG данные отсутствуют или неполные.")
    elif xg.get("count", 0) > 0:
        st.caption(f"xG данные доступны: {xg.get('count')} записей")

    analysis_warnings = analysis.get("warnings", [])
    if isinstance(analysis_warnings, list) and analysis_warnings:
        st.markdown("#### ⚠️ Предупреждения анализа")
        for warning in analysis_warnings[:5]:
            st.caption(f"• {warning}")

    error_frequency = _safe_dict(analysis.get("error_frequency"))
    if error_frequency:
        st.markdown("### Ошибки по типам")
        rows = [
            {"Тип ошибки": key, "Количество": value}
            for key, value in error_frequency.items()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    cause_frequency = _safe_dict(analysis.get("cause_frequency"))
    if cause_frequency:
        st.markdown("### Причины ошибок")
        rows = [
            {"Причина": key, "Количество": value}
            for key, value in cause_frequency.items()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


# ============================================================
# PATTERNS
# ============================================================

def _render_patterns(result: Dict[str, Any]) -> None:
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
            "Severity": _display_number(pattern.get("average_severity"), 3),
            "xG dev": _display_number(pattern.get("average_xg_error"), 3),
            "Confidence": _display_number(pattern.get("average_confidence"), 3),
            "Strength": _display_number(pattern.get("signal_strength"), 3),
            "Priority": _safe_string(pattern.get("priority")),
        })

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    for pattern in patterns[:3]:
        recommendations = pattern.get("recommendations", [])
        if recommendations:
            with st.expander(f"💡 {_safe_string(pattern.get('error_type'))} → {_safe_string(pattern.get('cause_type'))}"):
                for rec in recommendations[:3]:
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
    total = _safe_int(result.get("batch_size", 0))
    learning_events = _safe_int(result.get("learning_events"))

    optimization = _safe_dict(result.get("optimization"))
    proposals = _safe_list(optimization.get("proposals", []))
    review = _safe_dict(result.get("review"))
    pending = _safe_int(len(review.get("pending", [])))

    if status == "completed" and failed == 0 and total > 0:
        st.success("✅ Полная цепочка ETC завершена.")
        st.markdown(
            f"""
**{processed} из {total} матчей** успешно прошли ETC.

Цепочка E-FINAL:
1. `FACTS` → `BatchController v2.1`
2. `LearningBatch v2.1`
3. `ETCLearningEngine v2.0`
4. `ErrorClassifier v2.2`
5. `LearningAnalyzer v2.2` → **{len(proposals)} proposals**
6. `Signal Adapter` → нормализация сигналов
7. `ParameterOptimizer v2.3` → создание proposals
8. `Review Gate` → **{pending} pending**
9. 🔒 **AUTO-APPLY: DISABLED**

Создано Learning Events: **{learning_events}**.
"""
        )
        if already_processed > 0:
            st.info(f"ℹ️ {already_processed} матчей уже были обработаны ранее.")
        if proposals:
            st.info(f"📋 Создано {len(proposals)} proposals. Все ожидают review.")
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

    pending_matches = _safe_int(status.get("pending_matches"))

    if result:
        result_status = _safe_string(result.get("status"))
        errors = _error_count(result.get("errors"))

        if errors > 0:
            st.warning("⚠️ Сначала проверь ошибки выше. Не переходи дальше, пока причина не понятна.")
            return

        if result_status == "completed":
            st.success("✅ Этот batch успешно обучен.")
            if pending_matches > 0:
                st.info(f"Следующий шаг: обработать следующий batch. Сейчас готово ещё {pending_matches} матчей.")
            else:
                st.info("Сейчас новых готовых матчей нет. Следующий этап — добавить новые подтверждённые FACTS.")
            return

        if result_status in ("empty", "nothing_to_process"):
            st.info("⏳ Сейчас готовых матчей для обучения нет.")
            return

    if pending_matches > 0:
        st.info(f"📦 Сейчас доступно {pending_matches} матчей для обучения.")
    else:
        st.info("⏳ Готовых матчей для нового batch пока нет.")

    st.markdown(
        """
### Рабочий цикл FAJ (E-FINAL)
**MATCH**
→ итоговый счёт
→ статистика
→ FACT
→ MATCH READY
→ накопление batch
→ ETC
→ ErrorClassifier
→ LearningAnalyzer
→ Signal Adapter
→ ParameterOptimizer
→ Proposals
→ Review Gate
→ PENDING (NO AUTO-APPLY)
→ следующий batch
"""
    )


# ============================================================
# TECHNICAL DETAILS (ПАТЧ №4 — сюда перенесён технический мусор)
# ============================================================

def _render_technical_details(result: Optional[Dict[str, Any]]) -> None:
    if not result:
        return

    st.divider()
    with st.expander("🔧 Технические детали ETC (v7.2)", expanded=False):
        # Цепочка ETC
        _render_flow_technical()

        # Memory IDs
        memory_ids = _normalize_ids(result.get("memory_ids", []))
        batch_memory_ids = _normalize_ids(result.get("batch_memory_ids", []))
        learning_events = _safe_int(result.get("learning_events"))

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Learning Events", learning_events)
        with col2:
            st.metric("Memory IDs", len(memory_ids))
        with col3:
            st.metric("Batch Memory", len(batch_memory_ids))

        if memory_ids:
            st.code(", ".join(str(mid) for mid in memory_ids[:20]))

        # Batch детали
        batches = _get_batches(result)
        if batches:
            st.markdown("#### 📦 Детали batch")
            for idx, batch in enumerate(batches):
                with st.expander(f"Batch #{idx + 1}: {_safe_string(batch.get('league'))}", expanded=False):
                    batch_check = _safe_dict(batch.get("batch_check"))
                    if batch_check:
                        status = _safe_string(batch_check.get("status"))
                        required = _safe_int(batch_check.get("required_matches"))
                        completed = _safe_int(batch_check.get("completed_matches"))
                        processed = _safe_int(batch_check.get("processed_matches"))
                        new_matches = _safe_int(batch_check.get("new_matches"))
                        remaining = _safe_int(batch_check.get("remaining_matches"))
                        league = _safe_string(batch_check.get("league"))
                        reason = _safe_string(batch_check.get("reason"))

                        c1, c2, c3, c4, c5 = st.columns(5)
                        with c1:
                            st.metric("Статус", status)
                        with c2:
                            st.metric("Требуется", required)
                        with c3:
                            st.metric("Новых", new_matches)
                        with c4:
                            st.metric("Осталось", remaining)
                        with c5:
                            st.metric("Всего завершено", completed)

                        st.caption(f"Лига: {league} | Обработано ранее: {processed}")
                        if reason:
                            st.caption(f"Причина: {reason}")

                        fingerprint = batch_check.get("batch_fingerprint")
                        if fingerprint:
                            st.success("🔐 Batch fingerprint присутствует.")
                            st.code(str(fingerprint)[:64] + ("..." if len(str(fingerprint)) > 64 else ""))

                    selected_ids = _normalize_ids(batch.get("selected_match_ids", []))
                    if selected_ids:
                        st.caption(f"Выбрано матчей: {len(selected_ids)}")
                        st.code(", ".join(str(mid) for mid in selected_ids[:20]))

        # Полный JSON
        st.json(result)


# ============================================================
# CONTRACT
# ============================================================

def _render_contract() -> None:
    st.divider()
    st.markdown("### 🛡️ Архитектурные границы ETC v7.2 (E-FINAL)")

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
        f"ETC Controller v{ETC_CONTROLLER_VERSION} | "
        "BatchController v2.1 | "
        "LearningBatch v2.1 | "
        "LearningAnalyzer v2.2 | "
        "ParameterOptimizer v2.3 | "
        "ErrorClassifier v2.2 | "
        "🔒 AUTO-APPLY: DISABLED"
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

    status = _render_status(controller)

    _render_control(controller)

    result = st.session_state.get("etc_last_result")
    if not isinstance(result, dict):
        result = None

    _render_last_result()

    if result:
        _render_error_analysis(result)
        _render_match_cards(result)  # ← НОВОЕ v7.2
        _render_patterns(result)
        _render_signals(result)

    _render_what_happened(result)
    _render_next_step(status, result)

    # Технические детали — в отдельном expander (ПАТЧ №4)
    _render_technical_details(result)

    _render_contract()

    st.divider()
    st.caption(
        f"FAJ Platform v{APP_VERSION} • "
        f"ETC Page v{ETC_PAGE_VERSION} (E-FINAL) • "
        f"ETC Controller v{ETC_CONTROLLER_VERSION} • "
        f"🔒 AUTO-APPLY: DISABLED"
    )


# ============================================================
# DIRECT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
