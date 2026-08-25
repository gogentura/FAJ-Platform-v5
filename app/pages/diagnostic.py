#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ DATABASE DIAGNOSTIC
============================================================

READ ONLY.

Назначение:
    Диагностика фактических данных FAJ после Soccer365.

Главный источник фактической статистики:

    Soccer365
        ↓
    soccer365_parser.py
        ↓
    import_facts.py
        ↓
    SQLite FAJ

Диагностика НЕ:
    INSERT
    UPDATE
    DELETE
    ALTER
    DROP

ВАЖНО:

    Никаких предположений о схеме.

    Диагностика сначала читает реальные колонки SQLite,
    а затем работает только с существующими колонками.

    Это позволяет безопасно определить:

        MATCH
          ↓
        PREDICTION
          ↓
        RESULT
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
"""

import streamlit as st
import os
from datetime import datetime

from app.database import FAJDatabase, DB_FILE


# ============================================================
# BASIC DB HELPERS
# ============================================================

def get_db():
    return FAJDatabase()


def get_connection(db):
    return db.get_connection()


def table_exists(db, table_name):
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


def get_table_count(db, table_name):
    if not table_exists(db, table_name):
        return 0

    try:
        conn = get_connection(db)
        cursor = conn.cursor()

        cursor.execute(
            f'SELECT COUNT(*) FROM "{table_name}"'
        )

        result = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return result

    except Exception:
        return 0


def get_table_columns(db, table_name):
    if not table_exists(db, table_name):
        return []

    try:
        conn = get_connection(db)
        cursor = conn.cursor()

        cursor.execute(
            f'PRAGMA table_info("{table_name}")'
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return [row[1] for row in rows]

    except Exception:
        return []


def select_rows(db, sql, params=()):
    """
    READ ONLY.
    Выполняет только SELECT.
    """

    conn = get_connection(db)
    cursor = conn.cursor()

    try:
        cursor.execute(sql, params)
        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()


def rows_to_dicts(rows, columns):
    result = []

    for row in rows:

        if hasattr(row, "keys"):
            result.append(dict(row))

        else:
            result.append(
                {
                    columns[i]: row[i]
                    for i in range(len(columns))
                }
            )

    return result


# ============================================================
# COLUMN DISCOVERY
# ============================================================

def find_xg_columns(columns):
    """
    Ищем только реально существующие колонки,
    содержащие xg/xG в имени.
    """

    return [
        column
        for column in columns
        if "xg" in column.lower()
    ]


def find_match_id_column(columns):
    candidates = [
        "match_id",
        "game_id",
        "fixture_id",
    ]

    for candidate in candidates:
        if candidate in columns:
            return candidate

    return None


# ============================================================
# MAIN
# ============================================================

def main():

    st.title("🔧 Диагностика FAJ")

    st.caption(
        "READ-ONLY. Проверка фактических данных "
        "Soccer365 → SQLite → ETC."
    )

    st.divider()

    # ========================================================
    # 1. DATABASE
    # ========================================================

    st.subheader("📁 1. База данных")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Файл",
            DB_FILE,
        )

    with c2:

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

    with c3:

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

    # ========================================================
    # 2. INITIALIZATION
    # ========================================================

    st.divider()

    st.subheader("🚀 2. Инициализация")

    try:

        db = get_db()

        status = db.get_status()

        if status.get("status") == "online":

            st.success(
                "✅ Database initialized: online"
            )

        else:

            st.warning(
                f"⚠️ Database status: "
                f"{status.get('status')}"
            )

        with st.expander("Показать статус БД"):

            st.json(status)

    except Exception as exc:

        st.error(
            f"❌ Ошибка инициализации: {exc}"
        )

        return

    # ========================================================
    # 3. TABLE INVENTORY
    # ========================================================

    st.divider()

    st.subheader("🗄️ 3. Реальная структура SQLite")

    try:

        tables = status.get("tables", [])

        if tables:

            st.success(
                f"Найдено таблиц: {len(tables)}"
            )

            st.write(tables)

        else:

            st.warning(
                "Список таблиц не получен."
            )

    except Exception as exc:

        st.error(
            f"❌ Ошибка чтения структуры: {exc}"
        )

    # ========================================================
    # 4. LIFECYCLE COUNTS
    # ========================================================

    st.divider()

    st.subheader("🔗 4. Жизненный цикл данных")

    lifecycle_tables = [
        ("matches", "📋 Матчи"),
        ("predictions", "🧠 Прогнозы"),
        ("match_results", "🏁 Результаты"),
        ("match_statistics", "📊 Статистика матчей"),
        ("prediction_validation", "✅ Validation"),
        ("gold_dataset", "⭐ Gold"),
        ("learning_memory", "🧠 Learning Memory"),
        ("learning_events", "📚 Learning Events"),
        ("learning_records", "📚 Learning Records"),
        ("match_snapshots", "📸 Snapshots"),
    ]

    lifecycle_values = []

    for table_name, label in lifecycle_tables:

        count = get_table_count(
            db,
            table_name,
        )

        lifecycle_values.append(
            (table_name, label, count)
        )

    cols = st.columns(5)

    for index, (_, label, count) in enumerate(
        lifecycle_values[:5]
    ):

        with cols[index]:

            st.metric(
                label,
                count,
            )

    cols2 = st.columns(5)

    for index, (_, label, count) in enumerate(
        lifecycle_values[5:]
    ):

        with cols2[index]:

            st.metric(
                label,
                count,
            )

    # ========================================================
    # 5. SOCCER365 FACTUAL DATA
    # ========================================================

    st.divider()

    st.subheader(
        "⚽ 5. Soccer365 — фактическая статистика"
    )

    st.info(
        "Источник фактов FAJ: Soccer365. "
        "Здесь мы НЕ запускаем парсер и НЕ записываем БД. "
        "Мы проверяем, что уже попало в SQLite после импорта."
    )

    # --------------------------------------------------------
    # MATCH STATISTICS
    # --------------------------------------------------------

    if not table_exists(
        db,
        "match_statistics",
    ):

        st.error(
            "❌ Таблица match_statistics отсутствует."
        )

    else:

        count = get_table_count(
            db,
            "match_statistics",
        )

        columns = get_table_columns(
            db,
            "match_statistics",
        )

        st.markdown(
            f"### 📊 match_statistics — {count} строк"
        )

        st.write(
            "**Реальные колонки таблицы:**"
        )

        st.code(
            ", ".join(columns)
        )

        xg_columns = find_xg_columns(
            columns
        )

        if xg_columns:

            st.success(
                "🎯 Найдены реальные xG-колонки: "
                + ", ".join(xg_columns)
            )

        else:

            st.warning(
                "⚠️ В match_statistics нет колонок "
                "с `xg` в названии."
            )

        match_id_column = find_match_id_column(
            columns
        )

        if match_id_column:

            st.success(
                f"🔗 Идентификатор матча: "
                f"`{match_id_column}`"
            )

        else:

            st.warning(
                "⚠️ В match_statistics не найден "
                "match_id/game_id/fixture_id."
            )

        # ----------------------------------------------------
        # SHOW REAL DATA
        # ----------------------------------------------------

        if columns:

            # Берём безопасный набор:
            # id + match_id + xG + остальные первые поля.

            selected = []

            preferred = [
                "id",
                "match_id",
                "game_id",
                "fixture_id",
            ]

            for column in preferred:

                if column in columns:
                    selected.append(column)

            for column in xg_columns:

                if column not in selected:
                    selected.append(column)

            for column in columns:

                if column not in selected:

                    selected.append(column)

                if len(selected) >= 15:
                    break

            if selected:

                try:

                    sql = (
                        "SELECT "
                        + ", ".join(
                            f'"{column}"'
                            for column in selected
                        )
                        + ' FROM "match_statistics" '
                        + "ORDER BY rowid DESC "
                        + "LIMIT 30"
                    )

                    rows = select_rows(
                        db,
                        sql,
                    )

                    if rows:

                        st.write(
                            "### Последние записи "
                            "match_statistics"
                        )

                        st.dataframe(
                            rows_to_dicts(
                                rows,
                                selected,
                            ),
                            use_container_width=True,
                        )

                    else:

                        st.warning(
                            "match_statistics существует, "
                            "но записей нет."
                        )

                except Exception as exc:

                    st.error(
                        f"❌ Ошибка чтения match_statistics: {exc}"
                    )

    # ========================================================
    # 6. OTHER ACTUAL xG TABLES
    # ========================================================

    st.divider()

    st.subheader(
        "🎯 6. Где ещё реально находится xG"
    )

    xg_tables = [
        "match_statistics",
        "prediction_validation",
        "gold_dataset",
        "xg_memory",
    ]

    for table_name in xg_tables:

        if not table_exists(
            db,
            table_name,
        ):

            continue

        columns = get_table_columns(
            db,
            table_name,
        )

        xg_columns = find_xg_columns(
            columns
        )

        count = get_table_count(
            db,
            table_name,
        )

        with st.expander(
            f"📦 {table_name} — {count} строк"
        ):

            if xg_columns:

                st.success(
                    "xG-колонки: "
                    + ", ".join(xg_columns)
                )

            else:

                st.warning(
                    "xG-колонок по названию не найдено."
                )

            st.write(
                "**Все реальные колонки:**"
            )

            st.code(
                ", ".join(columns)
            )

    # ========================================================
    # 7. RESULT + SOCCER365 STATISTICS
    # ========================================================

    st.divider()

    st.subheader(
        "🏁 7. RESULT ↔ Soccer365 STATISTICS"
    )

    if (
        table_exists(db, "match_results")
        and table_exists(db, "match_statistics")
    ):

        result_columns = get_table_columns(
            db,
            "match_results",
        )

        stats_columns = get_table_columns(
            db,
            "match_statistics",
        )

        result_match_id = find_match_id_column(
            result_columns
        )

        stats_match_id = find_match_id_column(
            stats_columns
        )

        st.write(
            f"RESULT match key: `{result_match_id}`"
        )

        st.write(
            f"STATISTICS match key: `{stats_match_id}`"
        )

        if (
            result_match_id
            and stats_match_id
        ):

            xg_columns = find_xg_columns(
                stats_columns
            )

            if xg_columns:

                # ------------------------------------------------
                # Берём первый реальный xG столбец.
                # Ничего не выдумываем.
                # ------------------------------------------------

                xg_column = xg_columns[0]

                sql = f"""
                    SELECT
                        mr."{result_match_id}" AS result_match_id,
                        ms."{stats_match_id}" AS statistics_match_id,
                        ms."{xg_column}" AS factual_xg
                    FROM "match_results" mr
                    JOIN "match_statistics" ms
                      ON mr."{result_match_id}"
                       = ms."{stats_match_id}"
                    WHERE ms."{xg_column}" IS NOT NULL
                    ORDER BY mr."{result_match_id}" DESC
                    LIMIT 50
                """

                try:

                    rows = select_rows(
                        db,
                        sql,
                    )

                    if rows:

                        st.success(
                            f"✅ Найдено связанных записей: "
                            f"{len(rows)}"
                        )

                        st.dataframe(
                            rows_to_dicts(
                                rows,
                                [
                                    "result_match_id",
                                    "statistics_match_id",
                                    "factual_xg",
                                ],
                            ),
                            use_container_width=True,
                        )

                    else:

                        st.warning(
                            "⚠️ RESULT и match_statistics "
                            "существуют, но связанных записей "
                            "с xG не найдено."
                        )

                except Exception as exc:

                    st.error(
                        f"❌ Ошибка связи RESULT ↔ STATISTICS: {exc}"
                    )

            else:

                st.warning(
                    "⚠️ В match_statistics нет xG-колонки."
                )

        else:

            st.warning(
                "⚠️ Не найден общий идентификатор матча."
            )

    else:

        st.warning(
            "⚠️ match_results или match_statistics отсутствует."
        )

    # ========================================================
    # 8. PREDICTION -> RESULT
    # ========================================================

    st.divider()

    st.subheader(
        "🧠 8. PREDICTION ↔ RESULT"
    )

    if (
        table_exists(db, "predictions")
        and table_exists(db, "match_results")
    ):

        prediction_columns = get_table_columns(
            db,
            "predictions",
        )

        result_columns = get_table_columns(
            db,
            "match_results",
        )

        prediction_match_id = find_match_id_column(
            prediction_columns
        )

        result_match_id = find_match_id_column(
            result_columns
        )

        if (
            prediction_match_id
            and result_match_id
        ):

            sql = f"""
                SELECT COUNT(DISTINCT p."{prediction_match_id}")
                FROM "predictions" p
                JOIN "match_results" mr
                  ON p."{prediction_match_id}"
                   = mr."{result_match_id}"
            """

            try:

                rows = select_rows(
                    db,
                    sql,
                )

                linked = (
                    rows[0][0]
                    if rows
                    else 0
                )

                st.metric(
                    "Матчи с прогнозом + результатом",
                    linked,
                )

            except Exception as exc:

                st.warning(
                    f"⚠️ Ошибка: {exc}"
                )

        else:

            st.warning(
                "⚠️ Не найден общий match_id."
            )

    # ========================================================
    # 9. VALIDATION
    # ========================================================

    st.divider()

    st.subheader(
        "✅ 9. Prediction Validation"
    )

    for table_name in [
        "prediction_validation",
        "gold_dataset",
    ]:

        if not table_exists(
            db,
            table_name,
        ):

            continue

        count = get_table_count(
            db,
            table_name,
        )

        columns = get_table_columns(
            db,
            table_name,
        )

        xg_columns = find_xg_columns(
            columns
        )

        st.write(
            f"**{table_name}:** {count} строк"
        )

        if xg_columns:

            st.success(
                "xG: "
                + ", ".join(xg_columns)
            )

        else:

            st.caption(
                "xG-поля по названию не обнаружены."
            )

    # ========================================================
    # 10. LEARNING
    # ========================================================

    st.divider()

    st.subheader(
        "🧠 10. Learning Memory"
    )

    for table_name in [
        "learning_memory",
        "learning_events",
        "learning_records",
    ]:

        count = get_table_count(
            db,
            table_name,
        )

        st.write(
            f"**{table_name}:** {count}"
        )

    # ========================================================
    # 11. MODEL HISTORY
    # ========================================================

    st.divider()

    st.subheader(
        "📊 11. Model History"
    )

    for table_name in [
        "model_parameters",
        "parameter_history",
    ]:

        count = get_table_count(
            db,
            table_name,
        )

        st.write(
            f"**{table_name}:** {count}"
        )

    # ========================================================
    # 12. SNAPSHOTS
    # ========================================================

    st.divider()

    st.subheader(
        "📸 12. Match Snapshots"
    )

    snapshot_count = get_table_count(
        db,
        "match_snapshots",
    )

    st.metric(
        "match_snapshots",
        snapshot_count,
    )

    # ========================================================
    # 13. DATA DIRECTORY
    # ========================================================

    st.divider()

    st.subheader(
        "📁 13. data/"
    )

    data_dir = os.path.dirname(
        DB_FILE
    )

    if os.path.exists(data_dir):

        files = os.listdir(
            data_dir
        )

        st.write(
            f"Директория: {data_dir}"
        )

        st.write(
            f"Файлы: {files}"
        )

    else:

        st.warning(
            "Директория data отсутствует."
        )

    # ========================================================
    # 14. FINAL DIAGNOSTIC CONCLUSION
    # ========================================================

    st.divider()

    st.subheader(
        "🧭 14. Что сейчас известно"
    )

    st.info(
        """
        Источник фактической статистики:

        Soccer365

        Парсер:

        app/parsers/soccer365_parser.py

        Поток:

        Soccer365 URL
             ↓
        soccer365_parser.py
             ↓
        FACTS
             ↓
        import_facts.py
             ↓
        SQLite
             ↓
        match_statistics / validation / gold
             ↓
        ETC Learning

        Эта страница ничего не записывает в БД.
        """
    )

    # ========================================================
    # REFRESH
    # ========================================================

    st.divider()

    if st.button(
        "🔄 Обновить диагностику",
        use_container_width=True,
    ):

        st.rerun()

    st.caption(
        "READ-ONLY. Диагностика не изменяет SQLite."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
