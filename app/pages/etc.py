#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================

ФАЙЛ:
    app/pages/etc.py

ETC PAGE v4.0
============================================================

НАЗНАЧЕНИЕ
-----------

Простой рабочий экран ETC.

ETC показывает:

    • сколько матчей готово к обучению;
    • сколько матчей уже обработано;
    • какой batch только что обучен;
    • есть ли ошибки;
    • что делать дальше.

ETC НЕ:

    • работает с SQLite напрямую;
    • выполняет SQL;
    • изменяет факты;
    • изменяет календарь;
    • создаёт прогнозы;
    • запускает Learning Engine напрямую.

Вся бизнес-логика находится в ETCController.

UI использует:

    ETCController.status()
    ETCController.run(...)

============================================================
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from app.database import FAJDatabase
from app.etc.etc_controller import ETCController


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
ETC_PAGE_VERSION = "4.0"

PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"

DEFAULT_BATCH_LIMIT = 50
MAX_BATCH_LIMIT = 1000


# ============================================================
# PAGE
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
    ETCController — единственная точка
    взаимодействия страницы с ETC.
    """

    db = FAJDatabase()

    return ETCController(
        db=db
    )


# ============================================================
# HELPERS
# ============================================================

def _safe_dict(
    value: Any,
) -> Dict[str, Any]:

    if isinstance(value, dict):
        return value

    return {}


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


def _safe_string(
    value: Any,
    default: str = "—",
) -> str:

    if value is None:
        return default

    text = str(value).strip()

    return text if text else default


def _error_count(
    value: Any,
) -> int:

    if isinstance(value, list):

        return len(value)

    if isinstance(value, int):

        return max(
            0,
            value,
        )

    return 1 if value else 0


def _get_batches(
    result: Dict[str, Any],
) -> List[Dict[str, Any]]:

    raw = result.get(
        "batches",
        [],
    )

    if not isinstance(
        raw,
        list,
    ):

        return []

    return [
        item
        for item in raw
        if isinstance(
            item,
            dict,
        )
    ]


# ============================================================
# HEADER
# ============================================================

def _render_header() -> None:

    st.title("🧠 FAJ ETC")

    st.subheader(
        "Evolution Training Center"
    )

    st.caption(
        "Здесь FAJ учится на завершённых матчах."
    )

    st.divider()


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
            f"❌ Не удалось получить состояние ETC: {exc}"
        )

        return {}

    status_value = _safe_string(
        status.get("status"),
        "UNKNOWN",
    )

    pending = status.get(
        "pending_matches"
    )

    processed = status.get(
        "processed_matches"
    )

    learning_events = status.get(
        "learning_events"
    )

    st.markdown("### 📡 Сейчас")

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Готово к обучению",
            _safe_string(
                pending
            ),
        )

    with col2:

        st.metric(
            "Уже обработано",
            _safe_string(
                processed
            ),
        )

    with col3:

        st.metric(
            "Learning Events",
            _safe_string(
                learning_events
            ),
        )

    with col4:

        st.metric(
            "ETC",
            status_value,
        )

    st.divider()

    return status


# ============================================================
# CONTROL
# ============================================================

def _render_control(
    controller: ETCController,
) -> None:

    st.markdown(
        "### 🧠 Обучение"
    )

    st.caption(
        "ETC сам найдёт готовые batch. "
        "Тебе не нужно выбирать матчи вручную."
    )

    limit = st.number_input(
        "Максимум матчей за один запуск",
        min_value=1,
        max_value=MAX_BATCH_LIMIT,
        value=DEFAULT_BATCH_LIMIT,
        step=1,
        key="etc_batch_limit",
    )

    force = st.checkbox(
        "Продолжить при ошибке отдельного матча",
        value=False,
        key="etc_force_mode",
    )

    if st.button(
        "🧠 ЗАПУСТИТЬ ОБУЧЕНИЕ",
        type="primary",
        width="stretch",
        key="etc_run_button",
    ):

        started = datetime.now()

        with st.spinner(
            "FAJ обучается..."
        ):

            try:

                result = controller.run(
                    limit=int(limit),
                    force=bool(force),
                )

            except Exception as exc:

                st.error(
                    f"❌ Ошибка ETC: {exc}"
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

        st.info(
            "ETC ещё не запускался."
        )

        return

    st.divider()

    st.markdown(
        "## 📦 Последнее обучение"
    )

    status = _safe_string(
        result.get("status"),
        "unknown",
    )

    processed = _safe_int(
        result.get("processed")
    )

    learned = _safe_int(
        result.get("learned")
    )

    memory = _safe_int(
        result.get("memory_events")
    )

    errors = _error_count(
        result.get("errors")
    )

    if status == "completed" and errors == 0:

        st.success(
            "✅ Обучение завершено успешно."
        )

    elif errors > 0:

        st.warning(
            "⚠️ Обучение завершено, "
            "но есть ошибки."
        )

    elif status in (
        "nothing_to_process",
        "empty",
    ):

        st.info(
            "⏭️ Новых готовых матчей пока нет."
        )

    else:

        st.info(
            f"Статус: {status}"
        )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Матчей обработано",
            processed,
        )

    with col2:

        st.metric(
            "Обучено",
            learned,
        )

    with col3:

        st.metric(
            "Memory Events",
            memory,
        )

    with col4:

        st.metric(
            "Ошибки",
            errors,
        )

    # --------------------------------------------------------
    # BATCHES
    # --------------------------------------------------------

    batches = _get_batches(
        result
    )

    if batches:

        st.markdown(
            "### 📦 Batch"
        )

        for batch in batches:

            league = _safe_string(
                batch.get("league"),
                "Лига",
            )

            batch_size = _safe_int(
                batch.get("batch_size")
            )

            batch_processed = _safe_int(
                batch.get("processed")
            )

            batch_learned = _safe_int(
                batch.get("learned")
            )

            batch_errors = _error_count(
                batch.get("errors")
            )

            if batch_errors == 0:

                st.success(
                    f"⚽ {league} — "
                    f"{batch_processed}/{batch_size} "
                    f"матчей обработано • "
                    f"обучено: {batch_learned}"
                )

            else:

                st.warning(
                    f"⚽ {league} — "
                    f"{batch_processed}/{batch_size} "
                    f"матчей • "
                    f"ошибок: {batch_errors}"
                )

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

    if errors:

        raw_errors = result.get(
            "errors"
        )

        with st.expander(
            "❌ Что пошло не так",
            expanded=True,
        ):

            if isinstance(
                raw_errors,
                list,
            ):

                for index, error in enumerate(
                    raw_errors,
                    start=1,
                ):

                    st.error(
                        f"{index}. {error}"
                    )

            else:

                st.error(
                    str(raw_errors)
                )

    elapsed = st.session_state.get(
        "etc_last_elapsed"
    )

    if elapsed is not None:

        st.caption(
            f"Время обучения: "
            f"{float(elapsed):.2f} сек."
        )


# ============================================================
# WHAT NEXT
# ============================================================

def _render_next_step(
    status: Dict[str, Any],
    result: Dict[str, Any] | None,
) -> None:

    st.divider()

    st.markdown(
        "## 👉 Что делать дальше"
    )

    pending = _safe_int(
        status.get(
            "pending_matches"
        )
    )

    if result:

        result_status = _safe_string(
            result.get(
                "status"
            ),
            "",
        )

        errors = _error_count(
            result.get(
                "errors"
            )
        )

        if errors > 0:

            st.warning(
                "Сначала исправь ошибки выше. "
                "После этого снова запусти ETC."
            )

            return

        if result_status == "completed":

            st.success(
                "✅ Этот batch обучен."
            )

            st.info(
                "Теперь переходи к следующим матчам: "
                "введи результат → загрузи статистику → "
                "сохрани факт."
            )

            return

    if pending > 0:

        st.info(
            f"📦 Сейчас доступно {pending} "
            f"готовых матчей для обучения."
        )

    else:

        st.info(
            "⏳ Готовых матчей для нового batch пока нет."
        )

    st.markdown(
        """
**Твой рабочий цикл:**

1. ⚽ Открыть следующий матч.
2. 📝 Ввести итоговый счёт.
3. 📊 Загрузить статистику.
4. 💾 Сохранить факт.
5. 🧠 Когда накопится нужный batch — запустить ETC.
6. 🔄 Перейти к следующим матчам.
        """
    )


# ============================================================
# SIMPLE HISTORY
# ============================================================

def _render_simple_history(
    result: Dict[str, Any] | None,
) -> None:

    if not result:
        return

    batches = _get_batches(
        result
    )

    if not batches:
        return

    st.divider()

    with st.expander(
        "📋 Подробности последнего batch",
        expanded=False,
    ):

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
# MAIN
# ============================================================

def main() -> None:
    """
    Главная точка входа ETC.

    Совместимый импорт:

        from app.pages.etc import main
    """

    _configure_page()

    _render_header()

    try:

        controller = get_etc_controller()

    except Exception as exc:

        st.error(
            "❌ Не удалось запустить ETCController.\n\n"
            f"{exc}"
        )

        st.stop()

    # --------------------------------------------------------
    # CURRENT STATE
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
    # NEXT STEP
    # --------------------------------------------------------

    _render_next_step(
        status,
        result,
    )

    # --------------------------------------------------------
    # DETAILS
    # --------------------------------------------------------

    _render_simple_history(
        result
    )

    # --------------------------------------------------------
    # FOOTER
    # --------------------------------------------------------

    st.divider()

    st.caption(
        f"FAJ Platform v{APP_VERSION} • "
        f"ETC v{ETC_PAGE_VERSION} • "
        f"Evolution Training Center"
    )


# ============================================================
# DIRECT ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
