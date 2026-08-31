#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================

FILE:
    app/pages/etc.py

ETC PAGE v8.0

НАЗНАЧЕНИЕ
----------
Наглядная панель Evolution Training Center.

Главное:
    • сколько матчей ETC видит;
    • КАКИЕ именно матчи ETC видит;
    • готов ли полный batch;
    • запуск обучения;
    • результат последнего batch;
    • разбор обработанных матчей;
    • ошибки;
    • signals;
    • proposals;
    • Review Gate.

АРХИТЕКТУРНО
------------
PAGE НЕ:
    • выполняет SQL;
    • выбирает матчи самостоятельно;
    • изменяет FACTS;
    • изменяет predictions;
    • изменяет model_parameters;
    • изменяет learning_memory.

READY MATCHES:
    BatchController.check()
            ↓
    BatchController.get_learning_batch()
            ↓
    UI

RUN:
    ETCController.run()
            ↓
    backend ETC

AUTO-APPLY:
    DISABLED
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
ETC_PAGE_VERSION = "8.0"
ETC_CONTROLLER_VERSION = "4.2"

PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"

DEFAULT_BATCH_LIMIT = 50
MAX_BATCH_LIMIT = 1000

LEAGUES = [
    "РПЛ",
    "АПЛ",
    "Ла Лига",
    "ЛЧ",
]


# ============================================================
# PAGE CONFIG
# ============================================================

def _configure_page() -> None:
    try:
        st.set_page_config(
            page_title=PAGE_TITLE,
            page_icon=PAGE_ICON,
            layout="wide",
            initial_sidebar_state="collapsed",
        )
    except Exception:
        pass


# ============================================================
# UI STYLE
# ============================================================

def _inject_css() -> None:
    st.markdown(
        """
        <style>

        .block-container {
            max-width: 1180px;
            padding-top: 1.3rem;
            padding-bottom: 3rem;
        }

        /* HERO */

        .faj-hero {
            padding: 28px 30px;
            border-radius: 28px;
            margin-bottom: 18px;
            background:
                linear-gradient(
                    135deg,
                    rgba(99,102,241,.16),
                    rgba(59,130,246,.08)
                );
            border: 1px solid rgba(100,100,130,.16);
            box-shadow: 0 12px 35px rgba(30,40,80,.08);
        }

        .faj-title {
            font-size: 34px;
            line-height: 1.05;
            font-weight: 850;
            letter-spacing: -1.2px;
        }

        .faj-subtitle {
            margin-top: 7px;
            font-size: 15px;
            opacity: .65;
        }

        .faj-pill {
            display: inline-block;
            margin-top: 14px;
            margin-right: 6px;
            padding: 6px 11px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 750;
            background: rgba(99,102,241,.10);
            border: 1px solid rgba(99,102,241,.15);
        }

        /* SECTION */

        .faj-section {
            margin: 26px 0 12px 2px;
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -.35px;
        }

        /* METRIC CARDS */

        .faj-metric {
            min-height: 105px;
            padding: 17px 18px;
            border-radius: 21px;
            background: rgba(255,255,255,.78);
            border: 1px solid rgba(100,100,130,.13);
            box-shadow: 0 8px 24px rgba(30,40,80,.05);
        }

        .faj-metric-label {
            font-size: 11px;
            font-weight: 750;
            opacity: .52;
        }

        .faj-metric-value {
            margin-top: 5px;
            font-size: 27px;
            font-weight: 850;
        }

        .faj-metric-note {
            margin-top: 3px;
            font-size: 11px;
            opacity: .45;
        }

        /* MATCH CARD */

        .faj-match {
            padding: 18px 20px;
            margin: 9px 0;
            border-radius: 21px;
            background: rgba(255,255,255,.82);
            border: 1px solid rgba(100,100,130,.14);
            box-shadow: 0 8px 24px rgba(30,40,80,.055);
        }

        .faj-match-ready {
            border-left: 5px solid #6366f1;
        }

        .faj-match-done {
            border-left: 5px solid #22c55e;
        }

        .faj-match-id {
            font-size: 11px;
            font-weight: 750;
            opacity: .5;
        }

        .faj-match-teams {
            margin-top: 3px;
            font-size: 19px;
            font-weight: 850;
        }

        .faj-match-meta {
            margin-top: 6px;
            font-size: 12px;
            opacity: .55;
        }

        .faj-score {
            padding: 10px;
            border-radius: 15px;
            text-align: center;
            background: rgba(99,102,241,.08);
            font-weight: 850;
        }

        /* FOOTER */

        .faj-footer {
            margin-top: 35px;
            text-align: center;
            font-size: 11px;
            opacity: .42;
        }

        /* STREAMLIT */

        button[kind="primary"] {
            min-height: 48px;
            border-radius: 15px !important;
            font-weight: 850 !important;
        }

        div[data-testid="stExpander"] {
            border-radius: 18px;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# CONTROLLER
# ============================================================

@st.cache_resource
def get_etc_controller() -> ETCController:
    """
    Единственная точка создания ETCController.
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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(
    value: Any,
    default: Optional[float] = None,
) -> Optional[float]:
    try:
        if value is None:
            return default

        result = float(value)

        if pd.isna(result):
            return default

        return result

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


def _display_number(
    value: Any,
    digits: int = 2,
) -> str:
    value = _safe_float(value)

    if value is None:
        return "—"

    return f"{value:.{digits}f}"


def _normalize_ids(value: Any) -> List[int]:
    if not isinstance(value, (list, tuple, set)):
        return []

    result: List[int] = []
    seen = set()

    for item in value:

        match_id = _safe_int(item)

        if match_id <= 0:
            continue

        if match_id in seen:
            continue

        seen.add(match_id)
        result.append(match_id)

    return result


def _error_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)

    if isinstance(value, int):
        return max(0, value)

    return 1 if value else 0


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


def _extract_analysis(
    result: Dict[str, Any],
) -> Dict[str, Any]:

    direct = result.get("analysis")

    if isinstance(direct, dict) and direct:
        return direct

    batches = _get_batches(result)

    if batches:

        learning_result = _safe_dict(
            batches[0].get("learning_result")
        )

        return _safe_dict(
            learning_result.get("analysis")
        )

    return {}


# ============================================================
# HERO
# ============================================================

def _render_header() -> None:

    st.markdown(
        """
        <div class="faj-hero">

            <div class="faj-title">
                🧠 FAJ ETC
            </div>

            <div class="faj-subtitle">
                Evolution Training Center · обучение на подтверждённых FACTS
            </div>

            <span class="faj-pill">
                🔒 AUTO-APPLY OFF
            </span>

            <span class="faj-pill">
                📚 FACTS READ-ONLY
            </span>

            <span class="faj-pill">
                🧩 BATCH CONTROLLED
            </span>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# STATUS
# ============================================================

def _read_status(
    controller: ETCController,
) -> Dict[str, Any]:

    try:
        return _safe_dict(
            controller.status()
        )

    except Exception as exc:

        st.error(
            "❌ Не удалось получить состояние ETC."
        )

        st.exception(exc)

        return {}


def _render_status(
    status: Dict[str, Any],
) -> None:

    status_value = _safe_string(
        status.get("status"),
        "UNKNOWN",
    )

    pending = _safe_int(
        status.get("pending_matches")
    )

    last_batch = _safe_string(
        status.get("last_batch_id")
    )

    timestamp = _safe_string(
        status.get("timestamp")
    )

    st.markdown(
        '<div class="faj-section">📡 ETC сейчас</div>',
        unsafe_allow_html=True,
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.markdown(
            f"""
            <div class="faj-metric">
                <div class="faj-metric-label">
                    ГОТОВЫХ МАТЧЕЙ
                </div>

                <div class="faj-metric-value">
                    {pending}
                </div>

                <div class="faj-metric-note">
                    видит BatchController
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown(
            f"""
            <div class="faj-metric">
                <div class="faj-metric-label">
                    СТАТУС
                </div>

                <div class="faj-metric-value">
                    {status_value}
                </div>

                <div class="faj-metric-note">
                    ETC Controller
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c3:

        batch_text = (
            last_batch[:12]
            if last_batch != "—"
            else "—"
        )

        st.markdown(
            f"""
            <div class="faj-metric">
                <div class="faj-metric-label">
                    ПОСЛЕДНИЙ BATCH
                </div>

                <div class="faj-metric-value">
                    {batch_text}
                </div>

                <div class="faj-metric-note">
                    текущая сессия
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with c4:

        time_text = (
            timestamp[:19]
            if timestamp != "—"
            else "—"
        )

        st.markdown(
            f"""
            <div class="faj-metric">
                <div class="faj-metric-label">
                    ОБНОВЛЕНО
                </div>

                <div
                    class="faj-metric-value"
                    style="font-size:18px"
                >
                    {time_text}
                </div>

                <div class="faj-metric-note">
                    read-only status
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# READY MATCHES
# ============================================================

def _get_ready_matches(
    controller: ETCController,
    league: Optional[str],
    season_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    ВАЖНО:

    Страница НЕ реализует собственную логику готовности.

    Используется backend API:

        BatchController.check()
                    ↓
        BatchController.get_learning_batch()

    Поэтому список ниже — это именно те матчи,
    которые ETC считает готовыми для batch.
    """

    leagues = (
        [league]
        if league
        else LEAGUES
    )

    collected: List[Dict[str, Any]] = []

    for current_league in leagues:

        try:
            check = controller.batch_controller.check(
                current_league,
                season_id=season_id,
            )

        except Exception:
            continue

        if not isinstance(check, dict):
            continue

        if str(
            check.get("status", "")
        ).upper() != "READY":
            continue

        try:

            batch = (
                controller
                .batch_controller
                .get_learning_batch(
                    current_league,
                    season_id=season_id,
                    limit=None,
                )
            )

        except Exception:
            batch = []

        if not isinstance(batch, list):
            continue

        for match in batch:

            if not isinstance(match, dict):
                continue

            item = dict(match)

            item["_etc_league"] = (
                current_league
            )

            collected.append(item)

    return collected


def _match_team(
    match: Dict[str, Any],
    side: str,
) -> str:

    keys = (
        f"{side}_team",
        f"{side}_team_name",
        f"{side}_name",
    )

    for key in keys:

        value = match.get(key)

        if value:
            return str(value)

    team_id = match.get(
        f"{side}_team_id"
    )

    if team_id:
        return f"Team #{team_id}"

    return "—"


def _match_date(
    match: Dict[str, Any],
) -> str:

    for key in (
        "match_date",
        "date",
        "match_datetime",
    ):

        value = match.get(key)

        if value:
            return str(value)[:19]

    return "—"


def _render_ready_match(
    match: Dict[str, Any],
) -> None:

    match_id = _safe_int(
        match.get("id")
    )

    home = _match_team(
        match,
        "home",
    )

    away = _match_team(
        match,
        "away",
    )

    league = _safe_string(
        match.get("_etc_league")
    )

    date = _match_date(match)

    home_goals = match.get(
        "result_home_goals"
    )

    away_goals = match.get(
        "result_away_goals"
    )

    if (
        home_goals is not None
        and away_goals is not None
    ):
        score = (
            f"{home_goals}:{away_goals}"
        )
    else:
        score = "—"

    st.markdown(
        f"""
        <div class="faj-match faj-match-ready">

            <div class="faj-match-id">
                MATCH #{match_id} · {league}
            </div>

            <div class="faj-match-teams">
                {home}
                <span style="opacity:.3">
                    —
                </span>
                {away}
            </div>

            <div class="faj-match-meta">
                📅 {date}
                &nbsp; · &nbsp;
                🟣 READY FOR ETC
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander(
        f"Данные матча #{match_id}",
        expanded=False,
    ):

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "Match ID",
                match_id,
            )

        with c2:
            st.metric(
                "Факт",
                score,
            )

        with c3:
            st.metric(
                "Турнир",
                league,
            )


def _render_ready_matches(
    controller: ETCController,
) -> None:

    st.markdown(
        '<div class="faj-section">🎯 Матчи, которые ETC видит</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Это главный экран ETC: здесь отображаются "
        "конкретные матчи следующего готового batch."
    )

    selected_label = st.selectbox(
        "Турнир",
        ["Все турниры"] + LEAGUES,
        key="etc_preview_league",
    )

    league = (
        None
        if selected_label == "Все турниры"
        else selected_label
    )

    matches = _get_ready_matches(
        controller,
        league,
    )

    if not matches:

        st.info(
            "⏳ Для выбранного турнира ETC "
            "сейчас не получил готовый полный batch."
        )

        return

    st.success(
        f"🟢 ETC видит {len(matches)} матчей."
    )

    for match in matches:
        _render_ready_match(match)


# ============================================================
# RUN CONTROL
# ============================================================

def _render_control(
    controller: ETCController,
) -> None:

    st.markdown(
        '<div class="faj-section">▶️ Запуск обучения</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:

        league_label = st.selectbox(
            "Турнир",
            ["Все турниры"] + LEAGUES,
            key="etc_run_league",
        )

    with c2:

        limit = st.number_input(
            "Максимум матчей",
            min_value=1,
            max_value=MAX_BATCH_LIMIT,
            value=DEFAULT_BATCH_LIMIT,
            step=1,
            key="etc_batch_limit",
        )

    force = st.checkbox(
        "Продолжать при ошибке отдельного матча",
        value=False,
        key="etc_force_mode",
    )

    st.caption(
        "Force mode продолжает batch после ошибки. "
        "Он НЕ означает повторное обучение уже обработанного матча."
    )

    if st.button(
        "🧠  ЗАПУСТИТЬ ETC",
        type="primary",
        use_container_width=True,
        key="etc_run_button",
    ):

        league = (
            None
            if league_label == "Все турниры"
            else league_label
        )

        started = datetime.now()

        with st.spinner(
            "FAJ ETC выполняет batch..."
        ):

            try:

                result = controller.run(
                    league=league,
                    limit=int(limit),
                    force=bool(force),
                )

            except Exception as exc:

                st.error(
                    "❌ ETCController завершился исключением."
                )

                st.exception(exc)

                return

        elapsed = (
            datetime.now()
            - started
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

def _render_result_status(
    result: Dict[str, Any],
) -> None:

    status = _safe_string(
        result.get("status"),
        "unknown",
    )

    errors = _error_count(
        result.get("errors")
    )

    if (
        status == "completed"
        and errors == 0
    ):

        st.success(
            "✅ BATCH COMPLETED"
        )

    elif status == "completed_with_errors":

        st.warning(
            f"⚠️ Batch завершён с ошибками: {errors}"
        )

    elif status in (
        "nothing_to_process",
        "empty",
    ):

        st.info(
            "⏭️ Новых матчей для обучения нет."
        )

    elif status == "partial":

        st.warning(
            "⚠️ Batch обработан частично."
        )

    elif status == "failed":

        st.error(
            "❌ ETC завершился с ошибкой: "
            + _safe_string(
                result.get("message")
            )
        )

    else:

        st.info(
            f"Статус ETC: {status}"
        )


def _render_last_batch(
    result: Dict[str, Any],
) -> None:

    st.markdown(
        '<div class="faj-section">📦 Последний batch</div>',
        unsafe_allow_html=True,
    )

    _render_result_status(result)

    total = _safe_int(
        result.get("batch_size")
    )

    processed = _safe_int(
        result.get("processed")
    )

    already = _safe_int(
        result.get("already_processed")
    )

    failed = _safe_int(
        result.get("failed")
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Матчей в batch",
            total,
        )

    with c2:
        st.metric(
            "Обработано",
            processed,
        )

    with c3:
        st.metric(
            "Уже было",
            already,
        )

    with c4:
        st.metric(
            "Ошибок",
            failed,
        )

    processed_ids = _normalize_ids(
        result.get(
            "processed_match_ids"
        )
    )

    already_ids = _normalize_ids(
        result.get(
            "already_processed_match_ids"
        )
    )

    if processed_ids:

        st.success(
            "✅ Обработаны: "
            + ", ".join(
                f"#{x}"
                for x in processed_ids
            )
        )

    if already_ids:

        st.info(
            "⏭️ Уже обработаны ранее: "
            + ", ".join(
                f"#{x}"
                for x in already_ids
            )
        )

    elapsed = st.session_state.get(
        "etc_last_elapsed"
    )

    if elapsed is not None:

        st.caption(
            f"⏱️ Время выполнения: "
            f"{float(elapsed):.2f} сек."
        )


# ============================================================
# PROCESSED MATCH CARDS
# ============================================================

def _render_match_cards(
    result: Dict[str, Any],
) -> None:

    processed_ids = _normalize_ids(
        result.get(
            "processed_match_ids"
        )
    )

    if not processed_ids:
        return

    st.markdown(
        '<div class="faj-section">⚽ Разбор матчей</div>',
        unsafe_allow_html=True,
    )

    try:

        db = FAJDatabase()

        getter = getattr(
            db,
            "get_learning_records",
            None,
        )

        if not callable(getter):

            st.info(
                "Learning records API "
                "недоступен в database.py."
            )

            return

        records = getter(
            match_ids=processed_ids
        )

    except Exception as exc:

        st.warning(
            "⚠️ Не удалось загрузить "
            f"learning_records: {exc}"
        )

        return

    if not records:

        st.info(
            "Learning records для этих "
            "матчей пока отсутствуют."
        )

        return

    by_match: Dict[
        int,
        Dict[str, Any]
    ] = {}

    for record in records:

        if not isinstance(
            record,
            dict,
        ):
            continue

        match_id = _safe_int(
            record.get("match_id")
        )

        if (
            match_id > 0
            and match_id not in by_match
        ):

            by_match[match_id] = record

    for match_id in processed_ids:

        record = by_match.get(
            match_id
        )

        if not record:

            st.info(
                f"Матч #{match_id}: "
                "learning record отсутствует."
            )

            continue

        home = _safe_string(
            record.get("home_team")
        )

        away = _safe_string(
            record.get("away_team")
        )

        st.markdown(
            f"""
            <div class="faj-match faj-match-done">

                <div class="faj-match-id">
                    MATCH #{match_id}
                </div>

                <div class="faj-match-teams">
                    {home}
                    <span style="opacity:.3">
                        —
                    </span>
                    {away}
                </div>

            </div>
            """,
            unsafe_allow_html=True,
        )

        c1, c2 = st.columns(2)

        with c1:

            st.markdown(
                "**📊 FAJ прогноз**"
            )

            st.write(
                "Счёт:",
                _safe_string(
                    record.get("faj_score")
                ),
            )

            st.write(
                "xG:",
                (
                    f"{_display_number(record.get('faj_xg_home'))}"
                    f" — "
                    f"{_display_number(record.get('faj_xg_away'))}"
                ),
            )

        with c2:

            st.markdown(
                "**📋 Факт**"
            )

            st.write(
                "Счёт:",
                _safe_string(
                    record.get("actual_score")
                ),
            )

            st.write(
                "xG:",
                (
                    f"{_display_number(record.get('actual_xg_home'))}"
                    f" — "
                    f"{_display_number(record.get('actual_xg_away'))}"
                ),
            )

        errors = []

        if record.get(
            "error_score"
        ) is not None:

            errors.append(
                f"score: "
                f"{record.get('error_score')}"
            )

        if record.get(
            "error_xg"
        ) is not None:

            errors.append(
                "xG: "
                + _display_number(
                    record.get("error_xg"),
                    3,
                )
            )

        if record.get(
            "error_btts"
        ) is not None:

            errors.append(
                f"BTTS: "
                f"{record.get('error_btts')}"
            )

        if record.get(
            "error_total_25"
        ) is not None:

            errors.append(
                f"O2.5: "
                f"{record.get('error_total_25')}"
            )

        if errors:

            st.warning(
                "🔴 Ошибки · "
                + " · ".join(errors)
            )

        error_type = record.get(
            "error_type"
        )

        cause_type = record.get(
            "cause_type"
        )

        severity = record.get(
            "error_severity"
        )

        if (
            error_type
            or cause_type
            or severity is not None
        ):

            st.markdown(
                f"🏷️ **Классификация:** "
                f"{_safe_string(error_type)} · "
                f"{_safe_string(cause_type)} · "
                f"severity {_safe_string(severity)}"
            )

        recommendation = record.get(
            "recommendation"
        )

        if recommendation:

            st.info(
                f"💡 {recommendation}"
            )


# ============================================================
# ANALYSIS
# ============================================================

def _render_error_analysis(
    result: Dict[str, Any],
) -> None:

    analysis = _extract_analysis(
        result
    )

    if not analysis:
        return

    st.markdown(
        '<div class="faj-section">🔬 Анализ ошибок FAJ</div>',
        unsafe_allow_html=True,
    )

    severity = _safe_dict(
        analysis.get("severity")
    )

    xg = _safe_dict(
        analysis.get("xg")
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Средняя severity",
            _display_number(
                severity.get("average"),
                3,
            ),
        )

    with c2:

        st.metric(
            "Max severity",
            _safe_int(
                severity.get("max")
            ),
        )

    with c3:

        st.metric(
            "xG записей",
            _safe_int(
                xg.get("count")
            ),
        )

    with c4:

        st.metric(
            "Средняя xG ошибка",
            _display_number(
                xg.get("average"),
                3,
            ),
        )

    error_frequency = _safe_dict(
        analysis.get(
            "error_frequency"
        )
    )

    if error_frequency:

        st.markdown(
            "**Ошибки по типам**"
        )

        rows = [
            {
                "Ошибка": key,
                "Количество": value,
            }
            for key, value
            in error_frequency.items()
        ]

        st.dataframe(
            pd.DataFrame(rows),
            hide_index=True,
            use_container_width=True,
        )

    cause_frequency = _safe_dict(
        analysis.get(
            "cause_frequency"
        )
    )

    if cause_frequency:

        st.markdown(
            "**Причины ошибок**"
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
            hide_index=True,
            use_container_width=True,
        )


# ============================================================
# SIGNALS
# ============================================================

def _render_signals(
    result: Dict[str, Any],
) -> None:

    analysis = _extract_analysis(
        result
    )

    optimization = _safe_dict(
        result.get("optimization")
    )

    raw_signals = _safe_list(
        analysis.get("signals")
    )

    normalized_signals = _safe_list(
        optimization.get("signals")
    )

    if (
        not raw_signals
        and not normalized_signals
    ):
        return

    st.markdown(
        '<div class="faj-section">📡 ETC Signals</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)

    with c1:

        st.metric(
            "Raw signals",
            len(raw_signals),
        )

    with c2:

        st.metric(
            "Normalized signals",
            _safe_int(
                optimization.get(
                    "signals_analyzed"
                )
            ),
        )

    if normalized_signals:

        rows = []

        for signal in normalized_signals[:20]:

            if not isinstance(
                signal,
                dict,
            ):
                continue

            rows.append(
                {
                    "Ошибка": _safe_string(
                        signal.get(
                            "error_type"
                        )
                    ),
                    "Причина": _safe_string(
                        signal.get(
                            "cause_type"
                        )
                    ),
                    "Матчей": _safe_int(
                        signal.get(
                            "count"
                        )
                    ),
                    "Confidence": _display_number(
                        signal.get(
                            "confidence"
                        ),
                        3,
                    ),
                    "Strength": _display_number(
                        signal.get(
                            "signal_strength"
                        ),
                        3,
                    ),
                    "Severity": _display_number(
                        signal.get(
                            "average_severity"
                        ),
                        3,
                    ),
                }
            )

        if rows:

            st.dataframe(
                pd.DataFrame(rows),
                hide_index=True,
                use_container_width=True,
            )


# ============================================================
# PROPOSALS
# ============================================================

def _render_proposals(
    result: Dict[str, Any],
) -> None:

    optimization = _safe_dict(
        result.get("optimization")
    )

    if not optimization:

        batches = _get_batches(
            result
        )

        if batches:

            optimization = _safe_dict(
                batches[0].get(
                    "optimization"
                )
            )

    proposals = [
        item
        for item
        in _safe_list(
            optimization.get(
                "proposals"
            )
        )
        if isinstance(
            item,
            dict,
        )
    ]

    if not proposals:
        return

    st.markdown(
        '<div class="faj-section">📋 Parameter Proposals</div>',
        unsafe_allow_html=True,
    )

    rows = []

    for proposal in proposals:

        rows.append(
            {
                "Параметр": _safe_string(
                    proposal.get(
                        "parameter_name"
                    )
                ),
                "Текущее": _display_number(
                    proposal.get(
                        "current_value"
                    ),
                    4,
                ),
                "Предлагаемое": _display_number(
                    proposal.get(
                        "proposed_value"
                    ),
                    4,
                ),
                "Delta": _display_number(
                    proposal.get(
                        "delta"
                    ),
                    4,
                ),
                "Priority": _safe_string(
                    proposal.get(
                        "priority"
                    )
                ),
                "Confidence": _display_number(
                    proposal.get(
                        "confidence"
                    ),
                    3,
                ),
                "Evidence": _safe_int(
                    proposal.get(
                        "unique_match_count"
                    )
                ),
                "Статус": _safe_string(
                    proposal.get(
                        "status"
                    )
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        use_container_width=True,
    )


# ============================================================
# REVIEW GATE
# ============================================================

def _render_review(
    result: Dict[str, Any],
) -> None:

    review = _safe_dict(
        result.get("review")
    )

    if not review:

        batches = _get_batches(
            result
        )

        if batches:

            review = _safe_dict(
                batches[0].get(
                    "review"
                )
            )

    if not review:
        return

    st.markdown(
        '<div class="faj-section">🛡️ Review Gate</div>',
        unsafe_allow_html=True,
    )

    pending = len(
        _safe_list(
            review.get("pending")
        )
    )

    approved = len(
        _safe_list(
            review.get("approved")
        )
    )

    rejected = len(
        _safe_list(
            review.get("rejected")
        )
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Pending",
            pending,
        )

    with c2:
        st.metric(
            "Approved",
            approved,
        )

    with c3:
        st.metric(
            "Rejected",
            rejected,
        )

    with c4:
        st.metric(
            "Auto-apply",
            "OFF",
        )

    st.caption(
        "Все proposals проходят Review Gate. "
        "Автоматическое применение отключено."
    )


# ============================================================
# WARNINGS / ERRORS
# ============================================================

def _render_warnings(
    result: Dict[str, Any],
) -> None:

    warnings = []

    for item in _safe_list(
        result.get("warnings")
    ):

        text = str(item).strip()

        if text:
            warnings.append(text)

    analysis = _extract_analysis(
        result
    )

    for item in _safe_list(
        analysis.get("warnings")
    ):

        text = str(item).strip()

        if text:
            warnings.append(text)

    warnings = list(
        dict.fromkeys(warnings)
    )

    if not warnings:
        return

    with st.expander(
        "⚠️ Предупреждения",
        expanded=False,
    ):

        for warning in warnings:
            st.warning(warning)


def _render_errors(
    result: Dict[str, Any],
) -> None:

    errors = _error_count(
        result.get("errors")
    )

    if errors <= 0:
        return

    raw_errors = result.get(
        "errors"
    )

    if not isinstance(
        raw_errors,
        list,
    ):
        raw_errors = [
            raw_errors
        ]

    with st.expander(
        f"❌ Ошибки ETC ({errors})",
        expanded=True,
    ):

        for index, error in enumerate(
            raw_errors,
            start=1,
        ):

            if isinstance(
                error,
                dict,
            ):

                match_id = error.get(
                    "match_id"
                )

                stage = _safe_string(
                    error.get("stage"),
                    "",
                )

                message = _safe_string(
                    error.get("error"),
                    str(error),
                )

                prefix = (
                    f"#{match_id}"
                    if match_id is not None
                    else "BATCH"
                )

                if stage:
                    prefix += (
                        f" · {stage}"
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


# ============================================================
# TECHNICAL DETAILS
# ============================================================

def _render_technical(
    result: Optional[Dict[str, Any]],
) -> None:

    if not result:
        return

    with st.expander(
        "🔧 Технические детали ETC",
        expanded=False,
    ):

        st.caption(
            "Диагностический раздел. "
            "На основном экране технические поля не показываются."
        )

        batches = _get_batches(
            result
        )

        if batches:

            for index, batch in enumerate(
                batches,
                start=1,
            ):

                with st.expander(
                    f"Batch #{index} · "
                    f"{_safe_string(batch.get('league'))}",
                    expanded=False,
                ):

                    batch_check = _safe_dict(
                        batch.get(
                            "batch_check"
                        )
                    )

                    if batch_check:
                        st.json(
                            batch_check
                        )

                    selected_ids = _normalize_ids(
                        batch.get(
                            "selected_match_ids"
                        )
                    )

                    if selected_ids:

                        st.write(
                            "Selected match IDs:",
                            selected_ids,
                        )

        st.json(result)


# ============================================================
# NEXT STEP
# ============================================================

def _render_next_step(
    status: Dict[str, Any],
    result: Optional[Dict[str, Any]],
) -> None:

    st.markdown(
        '<div class="faj-section">👉 Что делать дальше</div>',
        unsafe_allow_html=True,
    )

    pending = _safe_int(
        status.get(
            "pending_matches"
        )
    )

    if result:

        result_status = _safe_string(
            result.get("status"),
            "unknown",
        )

        errors = _error_count(
            result.get("errors")
        )

        if errors:

            st.warning(
                "⚠️ Сначала проверь ошибки "
                "последнего batch."
            )

            return

        if result_status == "completed":

            if pending:

                st.success(
                    f"✅ Batch обучен. "
                    f"ETC сейчас видит ещё "
                    f"{pending} готовых матчей."
                )

            else:

                st.info(
                    "✅ Batch обучен. "
                    "Новых готовых матчей сейчас нет."
                )

            return

        if result_status in (
            "empty",
            "nothing_to_process",
        ):

            st.info(
                "⏳ Готового полного batch сейчас нет."
            )

            return

    if pending:

        st.success(
            f"🟢 Сейчас ETC видит "
            f"{pending} готовых матчей."
        )

    else:

        st.info(
            "⏳ Сейчас ETC не видит "
            "готового полного batch."
        )


# ============================================================
# ARCHITECTURAL CONTRACT
# ============================================================

def _render_contract() -> None:

    with st.expander(
        "🛡️ Архитектурные границы ETC",
        expanded=False,
    ):

        c1, c2, c3, c4 = st.columns(4)

        with c1:
            st.success(
                "FACTS: READ ONLY"
            )

        with c2:
            st.success(
                "Predictions: READ ONLY"
            )

        with c3:
            st.success(
                "SQLite: backend only"
            )

        with c4:
            st.success(
                "AUTO-APPLY: OFF"
            )

        st.caption(
            f"ETC Controller v{ETC_CONTROLLER_VERSION} · "
            f"ETC Page v{ETC_PAGE_VERSION} · "
            "BatchController: "
            "check() / get_learning_batch()"
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    _configure_page()
    _inject_css()
    _render_header()

    try:

        controller = get_etc_controller()

    except Exception as exc:

        st.error(
            "❌ Не удалось создать ETCController."
        )

        st.exception(exc)

        st.stop()

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = _read_status(
        controller
    )

    _render_status(
        status
    )

    # --------------------------------------------------------
    # ГЛАВНОЕ:
    # КАКИЕ МАТЧИ ETC ВИДИТ
    # --------------------------------------------------------

    _render_ready_matches(
        controller
    )

    st.divider()

    # --------------------------------------------------------
    # RUN
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

    if result:

        st.divider()

        _render_last_batch(
            result
        )

        _render_warnings(
            result
        )

        _render_match_cards(
            result
        )

        _render_error_analysis(
            result
        )

        _render_signals(
            result
        )

        _render_proposals(
            result
        )

        _render_review(
            result
        )

        _render_errors(
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

    _render_technical(
        result
    )

    _render_contract()

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    st.markdown(
        f"""
        <div class="faj-footer">
            FAJ Platform v{APP_VERSION}
            · ETC Page v{ETC_PAGE_VERSION}
            · ETC Controller v{ETC_CONTROLLER_VERSION}
            · 🔒 AUTO-APPLY DISABLED
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# DIRECT ENTRY
# ============================================================

if __name__ == "__main__":
    main()
