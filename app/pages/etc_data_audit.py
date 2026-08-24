#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
ETC — Data Audit

Read-only диагностика данных для Evolution Report.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st


# ------------------------------------------------------------
# ROOT
# ------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


from scripts.audit_faj_data import FAJDataAudit


# ------------------------------------------------------------
# PAGE
# ------------------------------------------------------------

def main():

    st.set_page_config(
        page_title="FAJ ETC — Data Audit",
        page_icon="🔍",
        layout="wide",
    )

    st.title("🔍 FAJ ETC — Data Audit")

    st.caption(
        "Диагностика данных перед построением Evolution Report v2.0"
    )

    st.warning(
        "READ-ONLY: аудит не изменяет faj.db."
    )

    # --------------------------------------------------------
    # BUTTON
    # --------------------------------------------------------

    if st.button(
        "🔍 ЗАПУСТИТЬ ПОЛНЫЙ АУДИТ",
        type="primary",
        use_container_width=True,
    ):

        with st.spinner(
            "FAJ проверяет SQLite..."
        ):

            try:

                audit = FAJDataAudit()

                result = audit.run()

                st.session_state[
                    "faj_audit_result"
                ] = result

                st.success(
                    "Аудит завершён."
                )

            except Exception as exc:

                st.error(
                    f"Ошибка аудита: {exc}"
                )

    # --------------------------------------------------------
    # RESULT
    # --------------------------------------------------------

    result = st.session_state.get(
        "faj_audit_result"
    )

    if not result:

        st.info(
            "Нажми «ЗАПУСТИТЬ ПОЛНЫЙ АУДИТ»."
        )

        return

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    st.divider()

    st.subheader("🗄️ Database")

    tables = result.get(
        "tables",
        {}
    )

    capabilities = result.get(
        "capabilities",
        {}
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "Таблиц",
            len(tables),
        )

    with c2:

        total_rows = sum(
            item.get("rows", 0)
            for item in tables.values()
        )

        st.metric(
            "Всего строк",
            total_rows,
        )

    with c3:

        st.metric(
            "Evolution capabilities",
            sum(
                bool(v)
                for v in capabilities.values()
            ),
        )

    # --------------------------------------------------------
    # CAPABILITIES
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🧬 Evolution Readiness"
    )

    capability_names = {
        "league_trends":
            "League Trends",

        "prediction":
            "Prediction History",

        "prediction_scores":
            "Prediction Scores",

        "facts":
            "Match Results",

        "result_xg":
            "Result xG",

        "learning_memory":
            "Learning Memory",

        "model_history":
            "Model History",

        "snapshots":
            "Match Snapshots",

        "match_lifecycle":
            "Full Match Lifecycle",
    }

    cols = st.columns(3)

    for index, (
        key,
        label
    ) in enumerate(
        capability_names.items()
    ):

        value = bool(
            capabilities.get(
                key,
                False,
            )
        )

        with cols[index % 3]:

            if value:

                st.success(
                    f"✅ {label}"
                )

            else:

                st.error(
                    f"❌ {label}"
                )

    # --------------------------------------------------------
    # LEAGUE TRENDS
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🏆 League Trends"
    )

    if capabilities.get(
        "league_trends",
        False,
    ):

        st.success(
            "Фактические голы позволяют "
            "искать лиговые закономерности."
        )

        # Получаем повторно безопасно
        db_path = Path(
            result["database"]
        )

        try:

            audit = FAJDataAudit(
                db_path=db_path
            )

            audit.connect()

            if audit.table_exists(
                "match_results"
            ):

                columns = audit.get_columns(
                    "match_results"
                )

                if (
                    "home_goals" in columns
                    and "away_goals" in columns
                ):

                    row = audit.execute(
                        """
                        SELECT
                            COUNT(*) AS total,

                            SUM(
                                CASE
                                WHEN away_goals = 0
                                THEN 1 ELSE 0
                                END
                            ) AS away_zero,

                            SUM(
                                CASE
                                WHEN away_goals >= 2
                                THEN 1 ELSE 0
                                END
                            ) AS away_2plus,

                            SUM(
                                CASE
                                WHEN away_goals >= 3
                                THEN 1 ELSE 0
                                END
                            ) AS away_3plus

                        FROM match_results

                        WHERE home_goals IS NOT NULL
                          AND away_goals IS NOT NULL
                        """
                    ).fetchone()

                    total = row["total"] or 0

                    if total:

                        c1, c2, c3 = st.columns(3)

                        with c1:

                            value = row["away_zero"] or 0

                            st.metric(
                                "Гости 0",
                                f"{value}/{total}",
                                f"{value / total:.1%}",
                            )

                        with c2:

                            value = row["away_2plus"] or 0

                            st.metric(
                                "Гости 2+",
                                f"{value}/{total}",
                                f"{value / total:.1%}",
                            )

                        with c3:

                            value = row["away_3plus"] or 0

                            st.metric(
                                "Гости 3+",
                                f"{value}/{total}",
                                f"{value / total:.1%}",
                            )

                    audit.close()

        except Exception as exc:

            st.warning(
                f"Не удалось построить тренды: {exc}"
            )

    else:

        st.warning(
            "Недостаточно фактических данных "
            "для League Trends."
        )

    # --------------------------------------------------------
    # LIFECYCLE
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🔗 Match Lifecycle"
    )

    links = result.get(
        "links",
        {}
    )

    c1, c2, c3 = st.columns(3)

    with c1:

        st.metric(
            "MATCH → PREDICTION",
            links.get(
                "matches_predictions",
                0,
            ),
        )

    with c2:

        st.metric(
            "MATCH → RESULT",
            links.get(
                "matches_results",
                0,
            ),
        )

    with c3:

        st.metric(
            "FULL LIFECYCLE",
            links.get(
                "full_lifecycle",
                0,
            ),
        )

    # --------------------------------------------------------
    # SAMPLE MATCHES
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "🧪 Реальные завершённые матчи"
    )

    samples = result.get(
        "sample_matches",
        []
    )

    if samples:

        st.dataframe(
            samples,
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.info(
            "Нет матчей, для которых можно "
            "восстановить полный жизненный цикл."
        )

    # --------------------------------------------------------
    # MISSING
    # --------------------------------------------------------

    st.divider()

    st.subheader(
        "⚠️ Что пока не готово"
    )

    missing = result.get(
        "missing_capabilities",
        []
    )

    if missing:

        for item in missing:

            st.warning(
                item
            )

    else:

        st.success(
            "Все диагностические возможности доступны."
        )

    # --------------------------------------------------------
    # RAW JSON
    # --------------------------------------------------------

    with st.expander(
        "🔧 Технический результат аудита"
    ):

        st.json(
            result
        )


if __name__ == "__main__":

    main()
