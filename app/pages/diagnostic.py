#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
FAJ DATABASE DIAGNOSTIC
============================================================

READ-ONLY.

Ничего не изменяет:
    INSERT
    UPDATE
    DELETE
    ALTER
    DROP

Главная задача:
    НЕ УГАДЫВАТЬ, ГДЕ ЛЕЖИТ ФАКТИЧЕСКИЙ xG.

Диагностика сама исследует реальную SQLite-схему:

    ВСЕ ТАБЛИЦЫ
        ↓
    ВСЕ КОЛОНКИ
        ↓
    КОЛОНКИ, СОДЕРЖАЩИЕ xG
        ↓
    КОЛОНКИ С match_id
        ↓
    ФАКТИЧЕСКИЕ ЗАПИСИ
        ↓
    СВЯЗЬ С match_results
        ↓
    PREDICTION
        ↓
    VALIDATION
        ↓
    GOLD

Новые таблицы НЕ создаются.
Схема НЕ изменяется.
"""

import streamlit as st
import os
from datetime import datetime

from app.database import FAJDatabase, DB_FILE


# ============================================================
# HELPERS
# ============================================================

def table_exists(db, table_name):
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
              AND name = ?
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


def get_tables(db):
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            ORDER BY name
            """
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return [row[0] for row in rows]

    except Exception:
        return []


def get_columns(db, table_name):
    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"PRAGMA table_info([{table_name}])"
        )

        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        return [row[1] for row in rows]

    except Exception:
        return []


def get_table_count(db, table_name):
    if not table_exists(db, table_name):
        return 0

    try:
        conn = db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            f"SELECT COUNT(*) FROM [{table_name}]"
        )

        value = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        return int(value or 0)

    except Exception:
        return 0


def read_rows(db, sql, params=()):
    """
    Только SELECT.
    """

    conn = db.get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(sql, params)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()


def quote_identifier(name):
    """
    Безопасное quoting имени SQLite-таблицы/колонки.
    """

    return "[" + str(name).replace("]", "]]") + "]"


# ============================================================
# XG DISCOVERY
# ============================================================

def discover_xg_columns(db):
    """
    Ищет xG НЕ по заранее известным названиям,
    а по реальной схеме всей БД.

    Любая колонка, в имени которой присутствует:
        xg
        XG
        Xg

    будет найдена.
    """

    found = []

    tables = get_tables(db)

    for table in tables:

        columns = get_columns(db, table)

        for column in columns:

            if "xg" in column.lower():

                found.append(
                    {
                        "table": table,
                        "column": column,
                        "has_match_id": "match_id" in columns,
                        "rows": get_table_count(db, table),
                    }
                )

    return found


def get_xg_population(db, table, column):
    """
    Сколько реально заполненных значений находится
    в конкретной xG-колонке.
    """

    try:

        sql = f"""
            SELECT COUNT(*)
            FROM {quote_identifier(table)}
            WHERE {quote_identifier(column)} IS NOT NULL
        """

        rows = read_rows(db, sql)

        return int(rows[0][0] or 0)

    except Exception:
        return 0


# ============================================================
# MAIN
# ============================================================

def main():

    st.title("🔧 Диагностика FAJ")

    st.caption(
        "READ-ONLY. Диагностика исследует реальную SQLite-схему "
        "и не изменяет faj.db."
    )

    st.divider()

    # ========================================================
    # 1. DATABASE
    # ========================================================

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
                "❌ Файл отсутствует",
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

    st.divider()

    # ========================================================
    # 2. INITIALIZATION
    # ========================================================

    st.subheader("🚀 2. Инициализация")

    try:

        db = FAJDatabase()

        status = db.get_status()

        st.success(
            f"✅ Database initialized: "
            f"{status.get('status', 'unknown')}"
        )

        with st.expander("Реальный статус БД"):

            st.json(status)

    except Exception as exc:

        st.error(
            f"❌ Ошибка инициализации: {exc}"
        )

        return

    st.divider()

    # ========================================================
    # 3. REAL SCHEMA
    # ========================================================

    st.subheader("🗄️ 3. Реальная схема SQLite")

    try:

        tables = get_tables(db)

        st.metric(
            "Таблиц",
            len(tables),
        )

        for table in tables:

            columns = get_columns(
                db,
                table,
            )

            count = get_table_count(
                db,
                table,
            )

            with st.expander(
                f"📦 {table} — {count} строк"
            ):

                st.write(
                    f"Количество колонок: {len(columns)}"
                )

                st.code(
                    ", ".join(columns)
                )

    except Exception as exc:

        st.error(
            f"❌ Ошибка чтения схемы: {exc}"
        )

    st.divider()

    # ========================================================
    # 4. MATCH LIFECYCLE
    # ========================================================

    st.subheader(
        "🔗 4. MATCH → PREDICTION → RESULT → VALIDATION → GOLD"
    )

    lifecycle_tables = [
        ("matches", "Матчи"),
        ("predictions", "Прогнозы"),
        ("match_results", "Фактические результаты"),
        ("prediction_validation", "Валидация"),
        ("gold_dataset", "Gold"),
    ]

    lifecycle_counts = {}

    for table, label in lifecycle_tables:

        count = get_table_count(
            db,
            table,
        )

        lifecycle_counts[table] = count

        st.write(
            f"{'✅' if count > 0 else '⚪'} "
            f"**{label}** (`{table}`): {count}"
        )

    # --------------------------------------------------------
    # MATCH -> RESULT
    # --------------------------------------------------------

    st.markdown("### Связь MATCH → RESULT")

    if (
        table_exists(db, "matches")
        and table_exists(db, "match_results")
    ):

        match_columns = get_columns(
            db,
            "matches",
        )

        result_columns = get_columns(
            db,
            "match_results",
        )

        if (
            "id" in match_columns
            and "match_id" in result_columns
        ):

            rows = read_rows(
                db,
                """
                SELECT COUNT(DISTINCT m.id)
                FROM matches m
                JOIN match_results mr
                  ON mr.match_id = m.id
                """,
            )

            linked = rows[0][0] if rows else 0

            st.success(
                f"✅ MATCH → RESULT: {linked}"
            )

        else:

            st.warning(
                "⚠️ Не найдены стандартные ID-поля "
                "для MATCH → RESULT."
            )

    st.divider()

    # ========================================================
    # 5. FACTUAL xG — DYNAMIC DISCOVERY
    # ========================================================

    st.subheader(
        "🎯 5. ФАКТИЧЕСКИЙ xG — АВТОМАТИЧЕСКИЙ ПОИСК"
    )

    st.info(
        "Здесь FAJ больше ничего не предполагает заранее. "
        "Система проходит по ВСЕЙ реальной схеме SQLite "
        "и показывает каждую колонку, в имени которой есть xG."
    )

    try:

        xg_columns = discover_xg_columns(db)

        if not xg_columns:

            st.error(
                "❌ В реальной SQLite-схеме не обнаружено "
                "ни одной колонки с 'xg' в названии."
            )

        else:

            st.success(
                f"✅ Найдено xG-колонок: {len(xg_columns)}"
            )

            for item in xg_columns:

                table = item["table"]
                column = item["column"]

                population = get_xg_population(
                    db,
                    table,
                    column,
                )

                match_id_status = (
                    "✅ есть match_id"
                    if item["has_match_id"]
                    else "⚪ нет match_id"
                )

                st.write(
                    f"**{table}.{column}** — "
                    f"{population} заполненных значений — "
                    f"{match_id_status}"
                )

    except Exception as exc:

        st.error(
            f"❌ Ошибка автоматического поиска xG: {exc}"
        )

    st.divider()

    # ========================================================
    # 6. XG TABLE DETAILS
    # ========================================================

    st.subheader(
        "🔬 6. ДЕТАЛЬНО: ВСЕ РЕАЛЬНЫЕ xG-ИСТОЧНИКИ"
    )

    try:

        xg_columns = discover_xg_columns(db)

        if xg_columns:

            for item in xg_columns:

                table = item["table"]
                column = item["column"]

                with st.expander(
                    f"📊 {table}.{column}"
                ):

                    columns = get_columns(
                        db,
                        table,
                    )

                    st.write(
                        "**Колонки таблицы:**"
                    )

                    st.code(
                        ", ".join(columns)
                    )

                    population = get_xg_population(
                        db,
                        table,
                        column,
                    )

                    st.metric(
                        "Заполненных xG",
                        population,
                    )

                    # ------------------------------------------------
                    # Если есть match_id — показываем реальные строки
                    # ------------------------------------------------

                    if "match_id" in columns:

                        select_columns = [
                            "match_id",
                            column,
                        ]

                        # Добавляем полезные поля,
                        # только если они реально существуют.

                        for candidate in [
                            "id",
                            "home_goals",
                            "away_goals",
                            "home_team_id",
                            "away_team_id",
                            "created_at",
                            "updated_at",
                        ]:

                            if (
                                candidate in columns
                                and candidate not in select_columns
                            ):

                                select_columns.append(
                                    candidate
                                )

                        sql = (
                            "SELECT "
                            + ", ".join(
                                quote_identifier(c)
                                for c in select_columns
                            )
                            + f" FROM {quote_identifier(table)} "
                            + f"WHERE {quote_identifier(column)} IS NOT NULL "
                            + "ORDER BY rowid DESC "
                            + "LIMIT 30"
                        )

                        rows = read_rows(
                            db,
                            sql,
                        )

                        if rows:

                            data = []

                            for row in rows:

                                data.append(
                                    {
                                        select_columns[i]:
                                            row[i]
                                        for i in range(
                                            len(select_columns)
                                        )
                                    }
                                )

                            st.dataframe(
                                data,
                                use_container_width=True,
                            )

                        else:

                            st.warning(
                                "xG-колонка существует, "
                                "но заполненных строк нет."
                            )

                    else:

                        st.warning(
                            "У этой xG-таблицы нет match_id. "
                            "Она может быть памятью/агрегатом, "
                            "но напрямую связать её с матчем "
                            "сейчас нельзя."
                        )

    except Exception as exc:

        st.error(
            f"❌ Ошибка детализации xG: {exc}"
        )

    st.divider()

    # ========================================================
    # 7. RESULT + FACTUAL xG
    # ========================================================

    st.subheader(
        "🏁 7. RESULT + ФАКТИЧЕСКИЙ xG"
    )

    st.info(
        "Ищем не конкретную таблицу и не конкретное имя поля, "
        "а реально существующую xG-колонку, которую можно "
        "связать через match_id с match_results."
    )

    try:

        result_columns = get_columns(
            db,
            "match_results",
        )

        xg_sources = discover_xg_columns(
            db
        )

        found_links = []

        if (
            "match_id" in result_columns
            and xg_sources
        ):

            for source in xg_sources:

                table = source["table"]
                column = source["column"]

                if not source["has_match_id"]:
                    continue

                if table == "match_results":
                    continue

                sql = f"""
                    SELECT COUNT(*)
                    FROM match_results mr
                    JOIN {quote_identifier(table)} x
                      ON x.match_id = mr.match_id
                    WHERE mr.home_goals IS NOT NULL
                      AND mr.away_goals IS NOT NULL
                      AND x.{quote_identifier(column)} IS NOT NULL
                """

                try:

                    rows = read_rows(
                        db,
                        sql,
                    )

                    linked = (
                        int(rows[0][0])
                        if rows
                        else 0
                    )

                    found_links.append(
                        {
                            "source":
                                f"{table}.{column}",
                            "linked_matches":
                                linked,
                        }
                    )

                except Exception:
                    pass

        if found_links:

            for item in found_links:

                if item["linked_matches"] > 0:

                    st.success(
                        f"✅ {item['source']} → "
                        f"match_results: "
                        f"{item['linked_matches']} матчей"
                    )

                else:

                    st.warning(
                        f"⚪ {item['source']} → "
                        f"match_results: 0 связанных матчей"
                    )

        else:

            st.warning(
                "⚠️ Пока не найдена xG-таблица, "
                "которую можно связать с match_results через match_id."
            )

    except Exception as exc:

        st.error(
            f"❌ Ошибка связи RESULT + xG: {exc}"
        )

    st.divider()

    # ========================================================
    # 8. PREDICTION DATA
    # ========================================================

    st.subheader("🧠 8. Prediction History")

    try:

        for table in [
            "predictions",
            "prediction_scores",
            "prediction_distributions",
            "match_predictions",
        ]:

            count = get_table_count(
                db,
                table,
            )

            if table_exists(
                db,
                table,
            ):

                st.write(
                    f"✅ `{table}`: {count}"
                )

                with st.expander(
                    f"Колонки {table}"
                ):

                    st.code(
                        ", ".join(
                            get_columns(
                                db,
                                table,
                            )
                        )
                    )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка prediction: {exc}"
        )

    st.divider()

    # ========================================================
    # 9. VALIDATION + GOLD
    # ========================================================

    st.subheader(
        "✅ 9. Validation → Gold"
    )

    try:

        validation_count = get_table_count(
            db,
            "prediction_validation",
        )

        gold_count = get_table_count(
            db,
            "gold_dataset",
        )

        st.write(
            f"**prediction_validation:** "
            f"{validation_count}"
        )

        st.write(
            f"**gold_dataset:** "
            f"{gold_count}"
        )

        if (
            table_exists(db, "prediction_validation")
            and table_exists(db, "gold_dataset")
        ):

            vc = get_columns(
                db,
                "prediction_validation",
            )

            gc = get_columns(
                db,
                "gold_dataset",
            )

            st.write(
                "**prediction_validation columns:**"
            )

            st.code(
                ", ".join(vc)
            )

            st.write(
                "**gold_dataset columns:**"
            )

            st.code(
                ", ".join(gc)
            )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка validation/gold: {exc}"
        )

    st.divider()

    # ========================================================
    # 10. LEARNING MEMORY
    # ========================================================

    st.subheader("🧠 10. Learning Memory")

    try:

        for table in [
            "learning_memory",
            "learning_events",
            "learning_records",
        ]:

            count = get_table_count(
                db,
                table,
            )

            st.write(
                f"{'✅' if count > 0 else '⚪'} "
                f"`{table}`: {count}"
            )

        if table_exists(
            db,
            "learning_memory",
        ):

            columns = get_columns(
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

                    st.caption(
                        "Типы Learning Memory:"
                    )

                    for row in rows:

                        st.write(
                            f"• {row[0]}: {row[1]}"
                        )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка Learning Memory: {exc}"
        )

    st.divider()

    # ========================================================
    # 11. MODEL HISTORY
    # ========================================================

    st.subheader("📈 11. Model History")

    try:

        mp = get_table_count(
            db,
            "model_parameters",
        )

        ph = get_table_count(
            db,
            "parameter_history",
        )

        st.write(
            f"**model_parameters:** {mp}"
        )

        st.write(
            f"**parameter_history:** {ph}"
        )

        if table_exists(
            db,
            "predictions",
        ):

            columns = get_columns(
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

                    st.caption(
                        "Версии модели:"
                    )

                    for row in rows:

                        st.write(
                            f"• {row[0]}: {row[1]}"
                        )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка Model History: {exc}"
        )

    st.divider()

    # ========================================================
    # 12. SNAPSHOTS
    # ========================================================

    st.subheader("📸 12. Match Snapshots")

    snapshot_count = get_table_count(
        db,
        "match_snapshots",
    )

    st.metric(
        "match_snapshots",
        snapshot_count,
    )

    if snapshot_count > 0:

        st.success(
            "✅ Snapshots присутствуют"
        )

    else:

        st.warning(
            "⚪ Snapshots пока пусты"
        )

    st.divider()

    # ========================================================
    # 13. FINAL DIAGNOSTIC SUMMARY
    # ========================================================

    st.subheader(
        "🎯 13. ИТОГ ДИАГНОСТИКИ"
    )

    prediction_count = get_table_count(
        db,
        "predictions",
    )

    result_count = get_table_count(
        db,
        "match_results",
    )

    validation_count = get_table_count(
        db,
        "prediction_validation",
    )

    gold_count = get_table_count(
        db,
        "gold_dataset",
    )

    learning_count = get_table_count(
        db,
        "learning_memory",
    )

    model_count = (
        get_table_count(
            db,
            "model_parameters",
        )
        +
        get_table_count(
            db,
            "parameter_history",
        )
    )

    xg_total = 0

    try:

        for source in discover_xg_columns(db):

            xg_total += get_xg_population(
                db,
                source["table"],
                source["column"],
            )

    except Exception:
        pass

    summary = [
        (
            "Прогнозы",
            prediction_count,
            prediction_count > 0,
        ),
        (
            "Факты",
            result_count,
            result_count > 0,
        ),
        (
            "Фактический xG",
            xg_total,
            xg_total > 0,
        ),
        (
            "Validation",
            validation_count,
            validation_count > 0,
        ),
        (
            "Gold",
            gold_count,
            gold_count > 0,
        ),
        (
            "Learning Memory",
            learning_count,
            learning_count > 0,
        ),
        (
            "Model History",
            model_count,
            model_count > 0,
        ),
        (
            "Snapshots",
            snapshot_count,
            snapshot_count > 0,
        ),
    ]

    for name, count, ok in summary:

        st.write(
            f"{'✅' if ok else '❌'} "
            f"**{name}:** {count}"
        )

    st.divider()

    # ========================================================
    # IMPORTANT
    # ========================================================

    st.info(
        "ВАЖНО: эта диагностика НЕ утверждает заранее, "
        "что фактический xG находится в match_statistics, "
        "gold_dataset или prediction_validation. "
        "Она сначала исследует реальную схему БД и показывает, "
        "ГДЕ ДЕЙСТВИТЕЛЬНО находятся xG-колонки и сколько "
        "значений в них реально заполнено."
    )

    # ========================================================
    # DATA DIRECTORY
    # ========================================================

    st.subheader("📁 14. Содержимое data/")

    try:

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
                files
            )

    except Exception as exc:

        st.warning(
            f"⚠️ Ошибка чтения data/: {exc}"
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
        "READ-ONLY. FAJDatabase используется только для чтения. "
        "База данных не изменяется."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
