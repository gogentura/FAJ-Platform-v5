#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Диагностика FAJ Database
============================================================

READ-ONLY.

НЕ:
    INSERT
    UPDATE
    DELETE
    ALTER
    DROP

Главная задача диагностики:

    MATCH
      ↓
    PREDICTION
      ↓
    MATCH RESULT
      ↓
    MATCH STATISTICS
      ↓
    FACTUAL xG
      ↓
    VALIDATION
      ↓
    GOLD
      ↓
    LEARNING

ВАЖНО:

    Никакие названия xG-полей заранее не предполагаются.

    Диагностика сама читает реальную SQLite-схему
    и ищет все колонки, содержащие "xg".

============================================================
"""

import os
from datetime import datetime

import streamlit as st

from app.database import FAJDatabase, DB_FILE


# ============================================================
# HELPERS
# ============================================================

def get_connection(db: FAJDatabase):
    return db.get_connection()


def table_exists(db: FAJDatabase, table_name: str) -> bool:
    try:
        conn = get_connection(db)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type='table'
              AND name=?
            LIMIT 1
            """,
            (table_name,),
        )

        result = cursor.fetchone() is not None

        cursor.close()
        conn.close()

        return result

    except Exception:
        return False


def get_table_columns(db: FAJDatabase, table_name: str) -> list:
    try:
        if not table_exists(db, table_name):
            return []

        conn = get_connection(db)
        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA table_info({table_name})"
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return [row[1] for row in rows]

    except Exception:
        return []


def get_table_count(db: FAJDatabase, table_name: str) -> int:
    try:
        if not table_exists(db, table_name):
            return 0

        conn = get_connection(db)
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        )

        result = cursor.fetchone()
        count = result[0] if result else 0

        cursor.close()
        conn.close()

        return int(count or 0)

    except Exception:
        return 0


def read_rows(db: FAJDatabase, sql: str, params=()):
    """
    Только SELECT.
    """
    conn = get_connection(db)
    cursor = conn.cursor()

    try:
        cursor.execute(sql, params)
        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def row_to_dict(row, columns):
    try:
        return dict(row)
    except Exception:
        return {
            columns[i]: row[i]
            for i in range(min(len(columns), len(row)))
        }


def xg_columns(columns: list) -> list:
    """
    Находит ВСЕ реальные колонки, где в имени встречается xg.
    """
    return [
        column
        for column in columns
        if "xg" in column.lower()
    ]


def column_has_values(
    db: FAJDatabase,
    table: str,
    column: str,
) -> int:
    """
    Сколько строк реально содержат значение
    в конкретной колонке.
    """
    try:
        rows = read_rows(
            db,
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE "{column}" IS NOT NULL
            """,
        )

        return int(rows[0][0] or 0)

    except Exception:
        return 0


# ============================================================
# DATABASE OVERVIEW
# ============================================================

def show_database_overview(db: FAJDatabase):

    st.subheader("📁 1. База данных")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Путь",
            DB_FILE,
        )

    with col2:
        if os.path.exists(DB_FILE):

            size_mb = (
                os.path.getsize(DB_FILE)
                / 1024
                / 1024
            )

            st.metric(
                "Размер",
                f"{size_mb:.2f} MB",
            )

        else:
            st.metric(
                "Размер",
                "❌",
            )

    with col3:
        if os.path.exists(DB_FILE):

            mtime = os.path.getmtime(DB_FILE)

            st.metric(
                "Изменён",
                datetime.fromtimestamp(
                    mtime
                ).strftime("%d.%m %H:%M"),
            )

        else:
            st.metric(
                "Изменён",
                "—",
            )


# ============================================================
# INITIALIZATION
# ============================================================

def show_initialization():

    st.subheader("🚀 2. Инициализация")

    try:

        db = FAJDatabase()
        status = db.get_status()

        st.success(
            f"✅ Database initialized: "
            f"{status.get('status', 'unknown')}"
        )

        with st.expander("Детали SQLite"):

            st.json(status)

        return db

    except Exception as exc:

        st.error(
            f"❌ Ошибка инициализации: {exc}"
        )

        return None


# ============================================================
# TABLE OVERVIEW
# ============================================================

def show_table_overview(db: FAJDatabase):

    st.subheader("🗄️ 3. Реальная структура ETC")

    important = [
        "matches",
        "predictions",
        "match_results",
        "match_statistics",
        "prediction_validation",
        "gold_dataset",
        "learning_memory",
        "learning_events",
        "learning_records",
        "model_parameters",
        "parameter_history",
        "match_snapshots",
        "xg_memory",
    ]

    rows = []

    for table in important:

        exists = table_exists(db, table)

        rows.append(
            {
                "Таблица": table,
                "Существует": "✅" if exists else "❌",
                "Строк": (
                    get_table_count(db, table)
                    if exists
                    else 0
                ),
            }
        )

    st.dataframe(
        rows,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# MATCH LIFECYCLE
# ============================================================

def show_match_lifecycle(db: FAJDatabase):

    st.subheader("📋 4. Жизненный цикл матча")

    matches = get_table_count(db, "matches")
    predictions = get_table_count(db, "predictions")
    results = get_table_count(db, "match_results")
    validation = get_table_count(
        db,
        "prediction_validation",
    )
    gold = get_table_count(
        db,
        "gold_dataset",
    )

    full_prediction_result = 0

    if (
        table_exists(db, "predictions")
        and table_exists(db, "match_results")
    ):

        try:

            rows = read_rows(
                db,
                """
                SELECT COUNT(DISTINCT p.match_id)
                FROM predictions p
                JOIN match_results mr
                  ON p.match_id = mr.match_id
                """,
            )

            if rows:
                full_prediction_result = int(
                    rows[0][0] or 0
                )

        except Exception:
            full_prediction_result = 0

    cols = st.columns(6)

    metrics = [
        ("📋 Матчи", matches),
        ("🧠 Прогнозы", predictions),
        ("🏁 Результаты", results),
        ("✅ Валидация", validation),
        ("⭐ Gold", gold),
        ("🔗 PRED → RESULT", full_prediction_result),
    ]

    for index, (label, value) in enumerate(metrics):

        with cols[index]:

            st.metric(
                label,
                value,
            )

    st.caption(
        "Связь PRED → RESULT считается по одинаковому match_id."
    )


# ============================================================
# FACTUAL xG
# ============================================================

def show_factual_xg(db: FAJDatabase):

    st.subheader(
        "🎯 5. ФАКТИЧЕСКИЙ xG — ТОЧНОЕ МЕСТО В БД"
    )

    st.info(
        "Этот блок ничего не записывает. "
        "Он читает реальную схему SQLite и показывает, "
        "в каких таблицах и колонках действительно находятся xG."
    )

    xg_tables = [
        "match_statistics",
        "gold_dataset",
        "prediction_validation",
        "xg_memory",
    ]

    total_sources_with_data = 0

    for table in xg_tables:

        if not table_exists(db, table):

            st.error(
                f"❌ {table}: таблица отсутствует"
            )

            continue

        columns = get_table_columns(
            db,
            table,
        )

        total_rows = get_table_count(
            db,
            table,
        )

        detected = xg_columns(columns)

        with st.expander(
            f"📦 {table} — {total_rows} строк",
            expanded=(table == "match_statistics"),
        ):

            st.write("### Реальные колонки таблицы")

            st.code(
                "\n".join(columns)
                if columns
                else "Колонки не прочитаны"
            )

            st.write("### 🔎 Автоматически найденные xG-колонки")

            if not detected:

                st.warning(
                    "В имени колонок этой таблицы "
                    "нет поля, содержащего 'xg'."
                )

                continue

            st.success(
                ", ".join(detected)
            )

            # ----------------------------------------------
            # VALUE COUNTS
            # ----------------------------------------------

            st.write(
                "### 📊 Где реально есть значения"
            )

            value_info = []

            for column in detected:

                count = column_has_values(
                    db,
                    table,
                    column,
                )

                if count > 0:
                    total_sources_with_data += 1

                value_info.append(
                    {
                        "Колонка": column,
                        "Всего строк": total_rows,
                        "Со значением": count,
                    }
                )

            st.dataframe(
                value_info,
                use_container_width=True,
                hide_index=True,
            )

            # ----------------------------------------------
            # SAMPLE
            # ----------------------------------------------

            if detected:

                select_fields = []

                if "id" in columns:
                    select_fields.append("id")

                if "match_id" in columns:
                    select_fields.append("match_id")

                for column in detected:
                    if column not in select_fields:
                        select_fields.append(column)

                if "created_at" in columns:
                    select_fields.append("created_at")

                sql = (
                    "SELECT "
                    + ", ".join(
                        f'"{column}"'
                        for column in select_fields
                    )
                    + f' FROM "{table}" '
                    + "ORDER BY rowid DESC "
                    + "LIMIT 30"
                )

                try:

                    sample_rows = read_rows(
                        db,
                        sql,
                    )

                    if sample_rows:

                        data = [
                            row_to_dict(
                                row,
                                select_fields,
                            )
                            for row in sample_rows
                        ]

                        st.write(
                            "### Последние реальные записи"
                        )

                        st.dataframe(
                            data,
                            use_container_width=True,
                            hide_index=True,
                        )

                    else:

                        st.warning(
                            "xG-колонки существуют, "
                            "но записей нет."
                        )

                except Exception as exc:

                    st.error(
                        f"Ошибка чтения записей: {exc}"
                    )

    st.divider()

    st.write(
        "### 🧭 Вывод по фактическому xG"
    )

    if total_sources_with_data > 0:

        st.success(
            "✅ Найдены реальные xG-значения. "
            "Смотри конкретную таблицу и колонку выше."
        )

    else:

        st.warning(
            "⚠️ В перечисленных источниках "
            "xG-значения не обнаружены."
        )


# ============================================================
# RESULT + MATCH STATISTICS + xG
# ============================================================

def show_result_xg_link(db: FAJDatabase):

    st.subheader(
        "🔎 6. RESULT → MATCH_STATISTICS → FACTUAL xG"
    )

    if not table_exists(db, "match_results"):

        st.error(
            "❌ match_results отсутствует"
        )

        return

    if not table_exists(db, "match_statistics"):

        st.error(
            "❌ match_statistics отсутствует"
        )

        return

    result_columns = get_table_columns(
        db,
        "match_results",
    )

    stats_columns = get_table_columns(
        db,
        "match_statistics",
    )

    if "match_id" not in result_columns:

        st.error(
            "❌ В match_results отсутствует match_id"
        )

        return

    if "match_id" not in stats_columns:

        st.error(
            "❌ В match_statistics отсутствует match_id"
        )

        return

    stats_xg = xg_columns(stats_columns)

    if not stats_xg:

        st.warning(
            "⚠️ В match_statistics нет колонок, "
            "в названии которых присутствует xG."
        )

        return

    st.write(
        "**xG-поля match_statistics:**"
    )

    st.code(
        ", ".join(stats_xg)
    )

    # --------------------------------------------------------
    # СТРОИМ ЗАПРОС ДИНАМИЧЕСКИ
    # --------------------------------------------------------

    result_fields = []

    for field in [
        "match_id",
        "home_goals",
        "away_goals",
        "result",
    ]:

        if field in result_columns:
            result_fields.append(
                f'mr."{field}" AS "result_{field}"'
            )

    stats_fields = [
        f'ms."{field}" AS "stats_{field}"'
        for field in stats_xg
    ]

    select_sql = ", ".join(
        result_fields + stats_fields
    )

    sql = f"""
        SELECT
            {select_sql}
        FROM match_results mr
        JOIN match_statistics ms
          ON ms.match_id = mr.match_id
        WHERE mr.match_id IS NOT NULL
        ORDER BY mr.match_id DESC
        LIMIT 50
    """

    try:

        rows = read_rows(
            db,
            sql,
        )

        if not rows:

            st.warning(
                "⚠️ match_results и match_statistics "
                "не имеют связанных записей по match_id."
            )

            return

        data = [
            row_to_dict(
                row,
                []
            )
            for row in rows
        ]

        st.success(
            f"✅ Связано записей: {len(data)}"
        )

        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True,
        )

    except Exception as exc:

        st.error(
            f"❌ Ошибка связи RESULT → xG: {exc}"
        )


# ============================================================
# PREDICTION → RESULT → VALIDATION → GOLD
# ============================================================

def show_full_chain(db: FAJDatabase):

    st.subheader(
        "🔗 7. MATCH → PREDICTION → RESULT → VALIDATION → GOLD"
    )

    required = [
        "matches",
        "predictions",
        "match_results",
        "prediction_validation",
        "gold_dataset",
    ]

    missing = [
        table
        for table in required
        if not table_exists(db, table)
    ]

    if missing:

        st.warning(
            "Отсутствуют таблицы: "
            + ", ".join(missing)
        )

        return

    prediction_columns = get_table_columns(
        db,
        "predictions",
    )

    result_columns = get_table_columns(
        db,
        "match_results",
    )

    validation_columns = get_table_columns(
        db,
        "prediction_validation",
    )

    gold_columns = get_table_columns(
        db,
        "gold_dataset",
    )

    if "match_id" not in prediction_columns:

        st.warning(
            "predictions не содержит match_id"
        )

        return

    if "match_id" not in result_columns:

        st.warning(
            "match_results не содержит match_id"
        )

        return

    # --------------------------------------------------------
    # Сначала безопасно определяем связи
    # --------------------------------------------------------

    validation_match_field = (
        "match_id"
        if "match_id" in validation_columns
        else None
    )

    gold_match_field = (
        "match_id"
        if "match_id" in gold_columns
        else None
    )

    if not validation_match_field:

        st.warning(
            "⚠️ prediction_validation не содержит match_id. "
            "Автоматическая полная связь невозможна."
        )

    if not gold_match_field:

        st.warning(
            "⚠️ gold_dataset не содержит match_id. "
            "Автоматическая полная связь невозможна."
        )

    # --------------------------------------------------------
    # Базовая связь PRED → RESULT
    # --------------------------------------------------------

    rows = read_rows(
        db,
        """
        SELECT
            p.match_id,
            COUNT(DISTINCT p.id) AS predictions,
            COUNT(DISTINCT mr.match_id) AS results
        FROM predictions p
        LEFT JOIN match_results mr
          ON mr.match_id = p.match_id
        GROUP BY p.match_id
        HAVING results > 0
        ORDER BY p.match_id DESC
        LIMIT 50
        """,
    )

    if rows:

        data = [
            {
                "match_id": row[0],
                "predictions": row[1],
                "results": row[2],
            }
            for row in rows
        ]

        st.success(
            f"✅ PREDICTION → RESULT: "
            f"{len(data)} матчей"
        )

        st.dataframe(
            data,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.warning(
            "⚠️ Связанных PREDICTION → RESULT нет."
        )


# ============================================================
# LEARNING MEMORY
# ============================================================

def show_learning_memory(db: FAJDatabase):

    st.subheader("🧠 8. Learning Memory")

    tables = [
        "learning_memory",
        "learning_events",
        "learning_records",
    ]

    info = []

    for table in tables:

        info.append(
            {
                "Таблица": table,
                "Строк": get_table_count(
                    db,
                    table,
                ),
                "Есть": (
                    "✅"
                    if table_exists(db, table)
                    else "❌"
                ),
            }
        )

    st.dataframe(
        info,
        use_container_width=True,
        hide_index=True,
    )

    if table_exists(db, "learning_memory"):

        columns = get_table_columns(
            db,
            "learning_memory",
        )

        if "event_type" in columns:

            rows = read_rows(
                db,
                """
                SELECT
                    event_type,
                    COUNT(*) AS cnt
                FROM learning_memory
                GROUP BY event_type
                ORDER BY cnt DESC
                """,
            )

            if rows:

                st.write(
                    "### Типы событий"
                )

                st.dataframe(
                    [
                        {
                            "event_type": row[0],
                            "count": row[1],
                        }
                        for row in rows
                    ],
                    use_container_width=True,
                    hide_index=True,
                )


# ============================================================
# MODEL HISTORY
# ============================================================

def show_model_history(db: FAJDatabase):

    st.subheader("📊 9. Model History")

    model_parameters = get_table_count(
        db,
        "model_parameters",
    )

    parameter_history = get_table_count(
        db,
        "parameter_history",
    )

    st.write(
        f"**model_parameters:** {model_parameters}"
    )

    st.write(
        f"**parameter_history:** {parameter_history}"
    )

    if table_exists(db, "predictions"):

        columns = get_table_columns(
            db,
            "predictions",
        )

        if "model_version" in columns:

            rows = read_rows(
                db,
                """
                SELECT
                    model_version,
                    COUNT(*) AS cnt
                FROM predictions
                WHERE model_version IS NOT NULL
                GROUP BY model_version
                ORDER BY cnt DESC
                """,
            )

            if rows:

                st.write(
                    "### Версии модели в predictions"
                )

                st.dataframe(
                    [
                        {
                            "model_version": row[0],
                            "predictions": row[1],
                        }
                        for row in rows
                    ],
                    use_container_width=True,
                    hide_index=True,
                )


# ============================================================
# SNAPSHOTS
# ============================================================

def show_snapshots(db: FAJDatabase):

    st.subheader("📸 10. Match Snapshots")

    count = get_table_count(
        db,
        "match_snapshots",
    )

    st.metric(
        "match_snapshots",
        count,
    )

    if count > 0:

        st.success(
            "✅ Snapshots существуют."
        )

    else:

        st.warning(
            "⚠️ Snapshots пока отсутствуют."
        )


# ============================================================
# EVOLUTION READINESS
# ============================================================

def show_evolution_readiness(db: FAJDatabase):

    st.subheader(
        "🚀 11. Evolution Readiness"
    )

    predictions = get_table_count(
        db,
        "predictions",
    )

    results = get_table_count(
        db,
        "match_results",
    )

    learning = get_table_count(
        db,
        "learning_memory",
    )

    snapshots = get_table_count(
        db,
        "match_snapshots",
    )

    model_history = (
        get_table_count(
            db,
            "model_parameters",
        )
        + get_table_count(
            db,
            "parameter_history",
        )
    )

    full_lifecycle = 0

    if (
        table_exists(db, "predictions")
        and table_exists(db, "match_results")
    ):

        rows = read_rows(
            db,
            """
            SELECT COUNT(DISTINCT p.match_id)
            FROM predictions p
            JOIN match_results mr
              ON mr.match_id = p.match_id
            """,
        )

        if rows:
            full_lifecycle = int(
                rows[0][0] or 0
            )

    checks = [
        ("Прогнозы", predictions > 0, predictions),
        ("Факты", results > 0, results),
        (
            "Фактический xG",
            _has_any_factual_xg(db),
            _factual_xg_total(db),
        ),
        (
            "Prediction → Result",
            full_lifecycle > 0,
            full_lifecycle,
        ),
        ("Learning Memory", learning > 0, learning),
        (
            "Model History",
            model_history > 0,
            model_history,
        ),
        (
            "Match Snapshots",
            snapshots > 0,
            snapshots,
        ),
    ]

    for name, ok, count in checks:

        st.write(
            f"{'✅' if ok else '❌'} "
            f"**{name}:** {count}"
        )

    missing = [
        name
        for name, ok, _ in checks
        if not ok
    ]

    st.divider()

    if not missing:

        st.success(
            "✅ Все проверяемые компоненты присутствуют."
        )

    else:

        st.warning(
            "⚠️ Требуют проверки: "
            + ", ".join(missing)
        )


# ============================================================
# FACTUAL xG HELPERS
# ============================================================

def _has_any_factual_xg(db: FAJDatabase) -> bool:

    return _factual_xg_total(db) > 0


def _factual_xg_total(db: FAJDatabase) -> int:

    total = 0

    for table in [
        "match_statistics",
        "gold_dataset",
        "prediction_validation",
    ]:

        if not table_exists(db, table):
            continue

        columns = get_table_columns(
            db,
            table,
        )

        for column in xg_columns(columns):

            total += column_has_values(
                db,
                table,
                column,
            )

    return total


# ============================================================
# DATA DIRECTORY
# ============================================================

def show_data_directory():

    st.subheader(
        "📁 12. Содержимое data/"
    )

    data_dir = os.path.dirname(
        DB_FILE
    )

    if not os.path.exists(data_dir):

        st.warning(
            f"Директория не существует: {data_dir}"
        )

        return

    files = sorted(
        os.listdir(data_dir)
    )

    st.write(
        f"Директория: {data_dir}"
    )

    st.dataframe(
        [
            {"Файл": filename}
            for filename in files
        ],
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# MAIN
# ============================================================

def main():

    st.title("🔧 Диагностика FAJ")

    st.caption(
        "FAJ Platform v12.1 — READ-ONLY диагностика "
        "реальной SQLite БД и ETC"
    )

    st.divider()

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    show_database_overview(
        FAJDatabase()
    )

    st.divider()

    # --------------------------------------------------------
    # INITIALIZATION
    # --------------------------------------------------------

    db = show_initialization()

    if db is None:
        return

    st.divider()

    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    show_table_overview(db)

    st.divider()

    # --------------------------------------------------------
    # LIFECYCLE
    # --------------------------------------------------------

    show_match_lifecycle(db)

    st.divider()

    # --------------------------------------------------------
    # FACTUAL XG — MAIN
    # --------------------------------------------------------

    show_factual_xg(db)

    st.divider()

    # --------------------------------------------------------
    # RESULT → XG
    # --------------------------------------------------------

    show_result_xg_link(db)

    st.divider()

    # --------------------------------------------------------
    # FULL CHAIN
    # --------------------------------------------------------

    show_full_chain(db)

    st.divider()

    # --------------------------------------------------------
    # LEARNING
    # --------------------------------------------------------

    show_learning_memory(db)

    st.divider()

    # --------------------------------------------------------
    # MODEL HISTORY
    # --------------------------------------------------------

    show_model_history(db)

    st.divider()

    # --------------------------------------------------------
    # SNAPSHOTS
    # --------------------------------------------------------

    show_snapshots(db)

    st.divider()

    # --------------------------------------------------------
    # EVOLUTION
    # --------------------------------------------------------

    show_evolution_readiness(db)

    st.divider()

    # --------------------------------------------------------
    # DATA
    # --------------------------------------------------------

    show_data_directory()

    st.divider()

    # --------------------------------------------------------
    # REFRESH
    # --------------------------------------------------------

    if st.button(
        "🔄 Обновить диагностику",
        use_container_width=True,
    ):

        st.rerun()

    st.caption(
        "🔒 READ-ONLY. "
        "Диагностика не изменяет faj.db."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
