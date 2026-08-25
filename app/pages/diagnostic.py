#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
DIAGNOSTIC — READ ONLY
============================================================

Назначение:
    Диагностика реального состояния FAJ SQLite.

КРИТИЧЕСКИ ВАЖНО:

    Фактическая статистика приходит из NB-BET parser.

    NB-BET parser формирует:

        home_xg
        away_xg

    Источник:
        match_statistics

    Диагностика НЕ изменяет БД.

    НЕ:
        INSERT
        UPDATE
        DELETE
        ALTER
        DROP
"""

import os
from datetime import datetime

import streamlit as st

from app.database import FAJDatabase, DB_FILE


# ============================================================
# DATABASE HELPERS
# ============================================================

def get_db():
    return FAJDatabase()


def get_columns(db, table_name):
    try:
        conn = db.get_connection()
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


def table_exists(db, table_name):
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name=?
            """,
            (table_name,),
        )

        result = cursor.fetchone() is not None

        cursor.close()
        conn.close()

        return result

    except Exception:
        return False


def count_rows(db, table_name):
    if not table_exists(db, table_name):
        return 0

    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        )

        result = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return int(result)

    except Exception:
        return 0


def select_rows(db, sql, params=()):
    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def row_to_dict(row, columns):
    if hasattr(row, "keys"):
        return dict(row)

    return {
        columns[i]: row[i]
        for i in range(min(len(columns), len(row)))
    }


# ============================================================
# MAIN
# ============================================================

def main():

    st.title("🔧 Диагностика FAJ")

    st.caption(
        "READ-ONLY. База данных не изменяется."
    )

    # ========================================================
    # 1. DATABASE
    # ========================================================

    st.subheader("📁 1. База данных")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "Файл",
            "✅ существует"
            if os.path.exists(DB_FILE)
            else "❌ отсутствует",
        )

    with c2:
        if os.path.exists(DB_FILE):
            size = os.path.getsize(DB_FILE) / 1024 / 1024
            st.metric(
                "Размер",
                f"{size:.2f} MB",
            )
        else:
            st.metric("Размер", "—")

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
            st.metric("Изменён", "—")

    st.code(DB_FILE)

    st.divider()

    # ========================================================
    # 2. INITIALIZATION
    # ========================================================

    st.subheader("🚀 2. Проверка инициализации")

    try:

        db = get_db()

        status = db.get_status()

        st.success(
            f"Database initialized: {status.get('status')}"
        )

        with st.expander(
            "Показать структуру SQLite"
        ):
            st.json(status)

    except Exception as exc:

        st.error(
            f"❌ Ошибка Database: {exc}"
        )

        return

    st.divider()

    # ========================================================
    # 3. MATCH LIFECYCLE
    # ========================================================

    st.subheader("📋 3. Жизненный цикл")

    matches = count_rows(db, "matches")
    predictions = count_rows(db, "predictions")
    results = count_rows(db, "match_results")
    statistics = count_rows(db, "match_statistics")
    validation = count_rows(db, "prediction_validation")
    gold = count_rows(db, "gold_dataset")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Матчи", matches)

    with c2:
        st.metric("Прогнозы", predictions)

    with c3:
        st.metric("Результаты", results)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Статистика", statistics)

    with c2:
        st.metric("Валидация", validation)

    with c3:
        st.metric("Gold", gold)

    st.divider()

    # ========================================================
    # 4. FACTUAL xG
    # ========================================================

    st.subheader(
        "🎯 4. ФАКТИЧЕСКИЙ xG"
    )

    st.info(
        """
        Здесь мы НЕ ищем отдельную таблицу Result xG.

        Реальный поток такой:

            NB-BET
               ↓
            home_xg / away_xg
               ↓
            match_statistics
               ↓
            ETC / Learning

        NB-BET parser действительно формирует
        home_xg и away_xg.
        """
    )

    if not table_exists(db, "match_statistics"):

        st.error(
            "❌ Таблица match_statistics отсутствует."
        )

    else:

        stats_columns = get_columns(
            db,
            "match_statistics",
        )

        st.write(
            "### Реальные колонки `match_statistics`"
        )

        st.code(
            "\n".join(stats_columns)
        )

        # ----------------------------------------------------
        # XG COLUMNS
        # ----------------------------------------------------

        xg_columns = [
            column
            for column in stats_columns
            if "xg" in column.lower()
        ]

        st.write(
            "### xG-колонки"
        )

        if xg_columns:

            st.success(
                "Найдены: "
                + ", ".join(xg_columns)
            )

        else:

            st.error(
                "❌ В match_statistics вообще нет "
                "колонок с xG."
            )

        # ----------------------------------------------------
        # EXACT HOME/AWAY XG
        # ----------------------------------------------------

        has_home_xg = "home_xg" in stats_columns
        has_away_xg = "away_xg" in stats_columns

        c1, c2 = st.columns(2)

        with c1:
            st.metric(
                "home_xg",
                "✅ есть"
                if has_home_xg
                else "❌ нет",
            )

        with c2:
            st.metric(
                "away_xg",
                "✅ есть"
                if has_away_xg
                else "❌ нет",
            )

        # ----------------------------------------------------
        # COUNTS
        # ----------------------------------------------------

        factual_xg_count = 0

        if has_home_xg and has_away_xg:

            rows = select_rows(
                db,
                """
                SELECT COUNT(*)
                FROM match_statistics
                WHERE home_xg IS NOT NULL
                  AND away_xg IS NOT NULL
                """,
            )

            factual_xg_count = rows[0][0]

            st.metric(
                "Матчей с ПОЛНЫМ фактическим xG",
                factual_xg_count,
            )

        # ----------------------------------------------------
        # SHOW ACTUAL DATA
        # ----------------------------------------------------

        st.write(
            "### 🔎 Фактические значения xG"
        )

        if has_home_xg and has_away_xg:

            optional_columns = [
                "id",
                "match_id",
                "home_xg",
                "away_xg",
                "source",
                "created_at",
                "updated_at",
            ]

            selected = [
                column
                for column in optional_columns
                if column in stats_columns
            ]

            if "match_id" not in selected:

                st.error(
                    "❌ В match_statistics нет match_id. "
                    "Невозможно связать xG с матчем."
                )

            else:

                sql = (
                    "SELECT "
                    + ", ".join(selected)
                    + """
                    FROM match_statistics
                    WHERE home_xg IS NOT NULL
                      AND away_xg IS NOT NULL
                    ORDER BY rowid DESC
                    LIMIT 50
                    """
                )

                rows = select_rows(
                    db,
                    sql,
                )

                if rows:

                    data = [
                        row_to_dict(
                            row,
                            selected,
                        )
                        for row in rows
                    ]

                    st.success(
                        f"Найдено записей: {len(data)}"
                    )

                    st.dataframe(
                        data,
                        use_container_width=True,
                    )

                else:

                    st.warning(
                        """
                        Колонки home_xg и away_xg существуют,
                        но фактических значений в них сейчас нет.
                        """
                    )

        # ----------------------------------------------------
        # PARTIAL XG
        # ----------------------------------------------------

        if has_home_xg:

            rows = select_rows(
                db,
                """
                SELECT COUNT(*)
                FROM match_statistics
                WHERE home_xg IS NOT NULL
                """,
            )

            st.caption(
                f"home_xg заполнен: {rows[0][0]}"
            )

        if has_away_xg:

            rows = select_rows(
                db,
                """
                SELECT COUNT(*)
                FROM match_statistics
                WHERE away_xg IS NOT NULL
                """,
            )

            st.caption(
                f"away_xg заполнен: {rows[0][0]}"
            )

    st.divider()

    # ========================================================
    # 5. RESULT + FACTUAL xG
    # ========================================================

    st.subheader(
        "🔗 5. RESULT → FACTUAL xG"
    )

    if (
        table_exists(db, "match_results")
        and table_exists(db, "match_statistics")
    ):

        result_columns = get_columns(
            db,
            "match_results",
        )

        stats_columns = get_columns(
            db,
            "match_statistics",
        )

        required = {
            "result_match_id": "match_id" in result_columns,
            "stats_match_id": "match_id" in stats_columns,
            "home_xg": "home_xg" in stats_columns,
            "away_xg": "away_xg" in stats_columns,
        }

        if all(required.values()):

            sql = """
                SELECT
                    mr.match_id,
                    mr.home_goals,
                    mr.away_goals,
                    ms.home_xg,
                    ms.away_xg
                FROM match_results mr
                JOIN match_statistics ms
                  ON ms.match_id = mr.match_id
                WHERE ms.home_xg IS NOT NULL
                  AND ms.away_xg IS NOT NULL
                ORDER BY mr.match_id DESC
                LIMIT 50
            """

            try:

                rows = select_rows(
                    db,
                    sql,
                )

                if rows:

                    data = [
                        row_to_dict(
                            row,
                            [
                                "match_id",
                                "home_goals",
                                "away_goals",
                                "home_xg",
                                "away_xg",
                            ],
                        )
                        for row in rows
                    ]

                    st.success(
                        f"✅ Связано матчей: {len(data)}"
                    )

                    st.dataframe(
                        data,
                        use_container_width=True,
                    )

                else:

                    st.warning(
                        """
                        В БД пока нет матча,
                        где одновременно присутствуют:

                        RESULT
                        +
                        home_xg
                        +
                        away_xg
                        """
                    )

            except Exception as exc:

                st.error(
                    f"Ошибка связи RESULT → xG: {exc}"
                )

        else:

            missing = [
                key
                for key, value in required.items()
                if not value
            ]

            st.warning(
                "Не хватает колонок: "
                + ", ".join(missing)
            )

    st.divider()

    # ========================================================
    # 6. OTHER XG STORAGE
    # ========================================================

    st.subheader(
        "🗃️ 6. Остальные xG-слои"
    )

    for table_name in [
        "gold_dataset",
        "prediction_validation",
        "xg_memory",
    ]:

        if not table_exists(db, table_name):

            st.warning(
                f"❌ {table_name}: таблица отсутствует"
            )

            continue

        columns = get_columns(
            db,
            table_name,
        )

        xg_columns = [
            column
            for column in columns
            if "xg" in column.lower()
        ]

        count = count_rows(
            db,
            table_name,
        )

        with st.expander(
            f"{table_name} — {count} строк"
        ):

            st.write(
                "Все xG-связанные колонки:"
            )

            if xg_columns:
                st.success(
                    ", ".join(xg_columns)
                )
            else:
                st.caption(
                    "xG-колонки не обнаружены."
                )

            st.code(
                "\n".join(columns)
            )

    st.divider()

    # ========================================================
    # 7. LEARNING
    # ========================================================

    st.subheader(
        "🧠 7. Learning Memory"
    )

    lm = count_rows(
        db,
        "learning_memory",
    )

    le = count_rows(
        db,
        "learning_events",
    )

    lr = count_rows(
        db,
        "learning_records",
    )

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric(
            "learning_memory",
            lm,
        )

    with c2:
        st.metric(
            "learning_events",
            le,
        )

    with c3:
        st.metric(
            "learning_records",
            lr,
        )

    st.divider()

    # ========================================================
    # 8. MODEL HISTORY
    # ========================================================

    st.subheader(
        "📊 8. Model History"
    )

    mp = count_rows(
        db,
        "model_parameters",
    )

    ph = count_rows(
        db,
        "parameter_history",
    )

    c1, c2 = st.columns(2)

    with c1:
        st.metric(
            "model_parameters",
            mp,
        )

    with c2:
        st.metric(
            "parameter_history",
            ph,
        )

    st.divider()

    # ========================================================
    # 9. SNAPSHOTS
    # ========================================================

    st.subheader(
        "📸 9. Match Snapshots"
    )

    snapshots = count_rows(
        db,
        "match_snapshots",
    )

    st.metric(
        "match_snapshots",
        snapshots,
    )

    st.divider()

    # ========================================================
    # 10. EVOLUTION STATUS
    # ========================================================

    st.subheader(
        "🚀 10. ETC / Evolution состояние"
    )

    st.write(
        """
        ### Правильная цепочка FAJ

        **MATCH**
        ↓

        **PREDICTION**
        ↓

        **MATCH RESULT**
        ↓

        **MATCH STATISTICS**
        ↓

        **FACTUAL xG**
        ↓

        **VALIDATION**
        ↓

        **GOLD**
        ↓

        **ETC**
        ↓

        **LEARNING MEMORY**
        """
    )

    if factual_xg_count > 0:

        st.success(
            f"""
            ✅ Фактический xG найден.

            Источник:
            match_statistics

            Полные записи:
            {factual_xg_count}

            Поля:
            home_xg
            away_xg
            """
        )

    else:

        st.warning(
            """
            ⚠️ Фактический xG пока не найден
            среди заполненных записей match_statistics.

            Это НЕ означает, что нужно создавать
            новую таблицу или менять database.py.

            Сначала проверяем импорт статистики.
            """
        )

    # ========================================================
    # 11. DATA DIRECTORY
    # ========================================================

    st.subheader(
        "📁 11. Содержимое data/"
    )

    data_dir = os.path.dirname(DB_FILE)

    if os.path.exists(data_dir):

        files = os.listdir(data_dir)

        st.code(
            "\n".join(files)
        )

    else:

        st.warning(
            "Директория data не найдена."
        )

    st.divider()

    # ========================================================
    # REFRESH
    # ========================================================

    if st.button(
        "🔄 Обновить диагностику",
        use_container_width=True,
    ):

        st.rerun()

    st.caption(
        "READ-ONLY. Никаких изменений SQLite."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
