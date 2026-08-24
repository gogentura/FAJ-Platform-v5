#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
ETC — Evolution Training Center
============================================================

ФАЙЛ:
    app/pages/etc.py

ETC PAGE v5.0
============================================================

НАЗНАЧЕНИЕ
-----------

Простой и прозрачный рабочий экран ETC.

Страница показывает:

    • сколько матчей готово к обучению;
    • сколько уже обработано;
    • сколько Learning Events создано;
    • состояние ETC;
    • последний batch;
    • каждый обработанный match_id;
    • ошибки по этапам;
    • batch fingerprint;
    • memory events;
    • что происходит внутри ETC;
    • что делать дальше.

ВАЖНО
------

UI НЕ работает с SQLite напрямую.

UI НЕ выполняет SQL.

UI НЕ изменяет:

    • matches
    • match_results
    • match_statistics
    • predictions
    • model_parameters
    • calendar
    • learning_memory

Вся бизнес-логика находится в:

    ETCController
        ↓
    ETCLearningEngine
        ↓
    StatisticalAnalyzer
        ↓
    LearningMemory

============================================================

ЦЕЛЬ v5.0
----------

Сделать ETC полностью прозрачным для ручной проверки.

Рабочая цепочка:

    FACTS
      │
      ▼
    BatchController
      │
      ▼
    READY
      │
      ▼
    get_learning_batch()
      │
      ▼
    ETCLearningEngine
      │
      ▼
    StatisticalAnalyzer
      │
      ▼
    analysis memory
      │
      ▼
    batch_learning marker
      │
      ▼
    BATCH COMPLETED
      │
      ▼
    NEXT MATCHES

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
ETC_PAGE_VERSION = "5.0"

PAGE_TITLE = "FAJ ETC"
PAGE_ICON = "🧠"

DEFAULT_BATCH_LIMIT = 50
MAX_BATCH_LIMIT = 1000


# ============================================================
# PAGE CONFIG
# ============================================================

def _configure_page() -> None:
    """
    Настройка страницы Streamlit.
    """

    try:

        st.set_page_config(
            page_title=PAGE_TITLE,
            page_icon=PAGE_ICON,
            layout="wide",
        )

    except Exception:
        # set_page_config может быть уже вызван
        # внешним entrypoint.
        pass


# ============================================================
# CONTROLLER
# ============================================================

@st.cache_resource
def get_etc_controller() -> ETCController:
    """
    ETCController — единственная точка
    взаимодействия страницы с ETC.

    UI не создаёт LearningEngine напрямую.
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
    Безопасно возвращает dict.
    """

    if isinstance(value, dict):
        return value

    return {}


def _safe_list(
    value: Any,
) -> List[Any]:
    """
    Безопасно возвращает list.
    """

    if isinstance(value, list):
        return value

    return []


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:
    """
    Безопасное преобразование в int.
    """

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
    """
    Безопасное преобразование в строку.
    """

    if value is None:
        return default

    text = str(value).strip()

    return text if text else default


def _error_count(
    value: Any,
) -> int:
    """
    Считает количество ошибок.

    Поддерживает:

        list
        int
        bool
        None
    """

    if isinstance(value, list):

        return len(value)

    if isinstance(value, int):

        return max(
            0,
            value,
        )

    if value:

        return 1

    return 0


def _get_errors(
    result: Dict[str, Any],
) -> List[Any]:
    """
    Нормализует ошибки последнего запуска.
    """

    raw = result.get(
        "errors",
        [],
    )

    if isinstance(
        raw,
        list,
    ):

        return raw

    if raw:

        return [raw]

    return []


def _get_batches(
    result: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Получает batch-детали.

    Сохраняется совместимость с более
    старым ETCController.
    """

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


def _get_processed_ids(
    result: Dict[str, Any],
) -> List[int]:
    """
    Получает список обработанных match_id.
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

    result_ids: List[int] = []

    for value in raw:

        try:

            match_id = int(value)

            if match_id > 0:

                result_ids.append(
                    match_id
                )

        except (
            TypeError,
            ValueError,
        ):

            continue

    return result_ids


def _get_memory_ids(
    result: Dict[str, Any],
) -> List[int]:
    """
    Получает все memory IDs последнего batch.
    """

    raw = result.get(
        "memory_ids",
        [],
    )

    if not isinstance(
        raw,
        list,
    ):

        return []

    result_ids: List[int] = []

    for value in raw:

        try:

            memory_id = int(value)

            if memory_id > 0:

                result_ids.append(
                    memory_id
                )

        except (
            TypeError,
            ValueError,
        ):

            continue

    return result_ids


def _get_batch_memory_ids(
    result: Dict[str, Any],
) -> List[int]:
    """
    Получает memory IDs,
    относящиеся непосредственно к batch.
    """

    raw = result.get(
        "batch_memory_ids",
        [],
    )

    if not isinstance(
        raw,
        list,
    ):

        return []

    result_ids: List[int] = []

    for value in raw:

        try:

            memory_id = int(value)

            if memory_id > 0:

                result_ids.append(
                    memory_id
                )

        except (
            TypeError,
            ValueError,
        ):

            continue

    return result_ids


# ============================================================
# HEADER
# ============================================================

def _render_header() -> None:
    """
    Главный заголовок ETC.
    """

    st.title(
        "🧠 FAJ ETC"
    )

    st.subheader(
        "Evolution Training Center"
    )

    st.caption(
        "FAJ учится на завершённых и подтверждённых матчах."
    )

    st.info(
        "ETC не изменяет исторические факты. "
        "Он анализирует готовые матчи и записывает "
        "результаты обучения в LearningMemory."
    )

    st.divider()


# ============================================================
# ARCHITECTURE FLOW
# ============================================================

def _render_flow() -> None:
    """
    Показывает пользователю реальную цепочку ETC.
    """

    st.markdown(
        "### 🔄 Цепочка ETC"
    )

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
analysis memory
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
    """
    Показывает текущее read-only состояние ETC.
    """

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
        status.get(
            "status"
        ),
        "UNKNOWN",
    )

    pending = _safe_int(
        status.get(
            "pending_matches"
        )
    )

    processed = _safe_int(
        status.get(
            "processed_matches"
        )
    )

    learning_events = _safe_int(
        status.get(
            "learning_events"
        )
    )

    st.markdown(
        "### 📡 Состояние ETC"
    )

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

    st.divider()

    return status


# ============================================================
# CONTROL
# ============================================================

def _render_control(
    controller: ETCController,
) -> None:
    """
    Панель запуска ETC.
    """

    st.markdown(
        "### 🧠 Запуск обучения"
    )

    st.caption(
        "ETC сам получает готовый batch через ETCController."
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
        "Для обычной проверки цепочки оставь "
        "значение по умолчанию."
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
        ] = _safe_dict(
            result
        )

        st.session_state[
            "etc_last_elapsed"
        ] = elapsed

        st.rerun()


# ============================================================
# STATUS BADGE
# ============================================================

def _render_result_status(
    result: Dict[str, Any],
) -> None:
    """
    Понятное отображение итогового статуса.
    """

    status = _safe_string(
        result.get(
            "status"
        ),
        "unknown",
    )

    success = bool(
        result.get(
            "success",
            False,
        )
    )

    batch_completed = bool(
        result.get(
            "batch_completed",
            False,
        )
    )

    errors = _error_count(
        result.get(
            "errors"
        )
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
            "ℹ️ Матч уже был обработан ранее."
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
# LAST RESULT
# ============================================================

def _render_last_result() -> None:
    """
    Показывает подробный результат последнего запуска.
    """

    result = st.session_state.get(
        "etc_last_result"
    )

    if not isinstance(
        result,
        dict,
    ):

        st.info(
            "ETC ещё не запускался в этой сессии."
        )

        return

    st.divider()

    st.markdown(
        "## 📦 Последний batch"
    )

    _render_result_status(
        result
    )

    processed = _safe_int(
        result.get(
            "processed"
        )
    )

    failed = _safe_int(
        result.get(
            "failed"
        )
    )

    total = _safe_int(
        result.get(
            "total"
        )
    )

    learning_events = _safe_int(
        result.get(
            "learning_events"
        )
    )

    memory_ids = _get_memory_ids(
        result
    )

    batch_memory_ids = _get_batch_memory_ids(
        result
    )

    processed_ids = _get_processed_ids(
        result
    )

    errors = _error_count(
        result.get(
            "errors"
        )
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
            "Ошибки",
            failed,
        )

    with col4:

        st.metric(
            "Learning Events",
            learning_events,
        )

    with col5:

        st.metric(
            "Batch Memory",
            len(
                batch_memory_ids
            ),
        )

    # --------------------------------------------------------
    # MATCHES
    # --------------------------------------------------------

    st.markdown(
        "### ⚽ Матчи"
    )

    if processed_ids:

        rows = []

        for match_id in processed_ids:

            rows.append(
                {
                    "Статус": "✅ Обработан",
                    "match_id": match_id,
                }
            )

        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
        )

    else:

        st.caption(
            "В последнем результате нет обработанных матчей."
        )

    # --------------------------------------------------------
    # MEMORY
    # --------------------------------------------------------

    st.markdown(
        "### 🧠 LearningMemory"
    )

    memory_col1, memory_col2 = st.columns(2)

    with memory_col1:

        st.metric(
            "Всего Memory IDs",
            len(
                memory_ids
            ),
        )

    with memory_col2:

        st.metric(
            "Batch Memory IDs",
            len(
                batch_memory_ids
            ),
        )

    if memory_ids:

        with st.expander(
            "🔎 Показать Memory IDs",
            expanded=False,
        ):

            st.code(
                ", ".join(
                    str(x)
                    for x in memory_ids
                )
            )

    # --------------------------------------------------------
    # BATCH CHECK
    # --------------------------------------------------------

    batch_check = _safe_dict(
        result.get(
            "batch_check"
        )
    )

    if batch_check:

        st.markdown(
            "### 🔍 BatchController"
        )

        controller_status = _safe_string(
            batch_check.get(
                "status"
            ),
            "—",
        )

        league = _safe_string(
            batch_check.get(
                "league"
            ),
            "—",
        )

        season_id = _safe_string(
            batch_check.get(
                "season_id"
            ),
            "—",
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
                str(
                    fingerprint
                )
            )

        else:

            st.info(
                "ℹ️ Batch fingerprint не предоставлен."
            )

    # --------------------------------------------------------
    # BATCH DETAILS
    # --------------------------------------------------------

    batches = _get_batches(
        result
    )

    if batches:

        st.markdown(
            "### 📦 Детали batch"
        )

        rows = []

        for batch in batches:

            rows.append(
                {
                    "Лига": _safe_string(
                        batch.get(
                            "league"
                        )
                    ),
                    "Batch": _safe_int(
                        batch.get(
                            "batch_size"
                        )
                    ),
                    "Обработано": _safe_int(
                        batch.get(
                            "processed"
                        )
                    ),
                    "Обучено": _safe_int(
                        batch.get(
                            "learned"
                        )
                    ),
                    "Memory": _safe_int(
                        batch.get(
                            "memory_events"
                        )
                    ),
                    "Ошибки": _error_count(
                        batch.get(
                            "errors"
                        )
                    ),
                    "Статус": _safe_string(
                        batch.get(
                            "status"
                        )
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True,
        )

    # --------------------------------------------------------
    # ERRORS
    # --------------------------------------------------------

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

                if isinstance(
                    error,
                    dict,
                ):

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
    """
    Показывает понятное объяснение результата.
    """

    if not result:

        return

    st.divider()

    st.markdown(
        "## 🔎 Что произошло"
    )

    status = _safe_string(
        result.get(
            "status"
        ),
        "unknown",
    )

    processed = _safe_int(
        result.get(
            "processed"
        )
    )

    failed = _safe_int(
        result.get(
            "failed"
        )
    )

    total = _safe_int(
        result.get(
            "total"
        )
    )

    learning_events = _safe_int(
        result.get(
            "learning_events"
        )
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

Для них:

1. `StatisticalAnalyzer` выполнил анализ.
2. Analysis memory была передана в `LearningMemory`.
3. Созданы `batch_learning` markers.
4. Batch завершён успешно.
5. Создано Learning Events: **{learning_events}**.
            """
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
    """
    Показывает пользователю следующий шаг.
    """

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

            st.info(
                "Теперь можно переходить к следующим "
                "завершённым матчам и формировать следующий batch."
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

**Матч**

→ ввести итоговый счёт

→ загрузить статистику

→ сохранить факт

→ матч становится готовым для ETC

→ накопить batch

→ запустить ETC

→ StatisticalAnalyzer

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
    """
    Техническая информация.

    Спрятана в expander, чтобы не перегружать
    основной рабочий экран.
    """

    if not result:

        return

    st.divider()

    with st.expander(
        "🔧 Технические детали ETC",
        expanded=False,
    ):

        st.json(
            result
        )


# ============================================================
# SAFETY / CONTRACT
# ============================================================

def _render_contract() -> None:
    """
    Коротко показывает архитектурные границы ETC.
    """

    st.divider()

    st.markdown(
        "### 🛡️ Границы ETC"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.success(
            "SQLite: только через backend"
        )

    with col2:

        st.success(
            "Исторические факты: НЕ изменяются"
        )

    with col3:

        st.success(
            "DELETE / DROP: отсутствуют"
        )

    with col4:

        st.success(
            "Прогнозы: НЕ изменяются"
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
            "❌ Не удалось запустить ETCController."
        )

        st.exception(exc)

        st.stop()

    # --------------------------------------------------------
    # FLOW
    # --------------------------------------------------------

    _render_flow()

    # --------------------------------------------------------
    # CURRENT STATUS
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
