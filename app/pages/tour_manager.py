#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1 — MEMORY HARDENED
Управление туром v3.1

Главный экран FAJ.

ОТВЕТСТВЕННОСТЬ:
    - выбор лиги;
    - выбор тура;
    - создание тура;
    - добавление матчей;
    - СОХРАНЕНИЕ ТУРА (НОВОЕ);
    - удаление матча;
    - удаление тура;
    - отображение текущих матчей тура;
    - переход к прогнозам;
    - переход к фактам.

НЕ ОТВЕЧАЕТ ЗА:
    - прогнозирование;
    - факты матчей;
    - статистику;
    - обучение;
    - паспорта.

DATABASE.PY:
    Единственный источник работы со схемой БД.

SQLite only.
"""

from __future__ import annotations

import streamlit as st

from app.database import FAJDatabase
from app.match_manager import MatchManager


# ============================================================
# КОНФИГУРАЦИЯ ЛИГ
# ============================================================

LEAGUE_CONFIG = {
    "РПЛ": {
        "max_rounds": 30,
        "max_teams": 16,
    },
    "АПЛ": {
        "max_rounds": 38,
        "max_teams": 20,
    },
    "Ла Лига": {
        "max_rounds": 38,
        "max_teams": 20,
    },
    "Лига чемпионов": {
        "max_rounds": 17,
        "max_teams": 36,
    },
}

ROUND_LABELS = {
    "Лига чемпионов": {
        1: "Общий этап — Тур 1",
        2: "Общий этап — Тур 2",
        3: "Общий этап — Тур 3",
        4: "Общий этап — Тур 4",
        5: "Общий этап — Тур 5",
        6: "Общий этап — Тур 6",
        7: "Общий этап — Тур 7",
        8: "Общий этап — Тур 8",
        9: "Стыковые матчи (1-й матч)",
        10: "Стыковые матчи (2-й матч)",
        11: "1/8 финала (1-й матч)",
        12: "1/8 финала (2-й матч)",
        13: "Четвертьфиналы (1-й матч)",
        14: "Четвертьфиналы (2-й матч)",
        15: "Полуфиналы (1-й матч)",
        16: "Полуфиналы (2-й матч)",
        17: "Финал",
    }
}


def get_max_rounds(league: str) -> int:
    return LEAGUE_CONFIG.get(league, {}).get("max_rounds", 30)


def get_round_label(league: str, round_number: int) -> str:
    if league in ROUND_LABELS:
        return ROUND_LABELS[league].get(round_number, f"Тур {round_number}")
    return f"Тур {round_number}"


# ============================================================
# HELPERS
# ============================================================

def team_id(team):
    """Безопасно получает ID команды."""
    if isinstance(team, dict):
        return team.get("id")
    return team["id"]


def team_name(team):
    """Безопасно получает название команды."""
    if isinstance(team, dict):
        return str(team.get("name", ""))
    return str(team["name"])


def season_id(season):
    """Безопасно получает ID сезона."""
    if isinstance(season, dict):
        return season.get("id")
    return season["id"]


def season_name(season):
    """Безопасно получает название сезона."""
    if isinstance(season, dict):
        return str(season.get("name", ""))
    return str(season["name"])


def row_value(row, key, default=None):
    """Безопасное получение значения из sqlite3.Row/dict."""
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


# ============================================================
# MAIN
# ============================================================

def main():

    st.title("🏠 Управление туром")
    st.caption("Создание турнира и ручного календаря матчей FAJ")

    db = FAJDatabase()
    match_mgr = MatchManager(db)

    # ========================================================
    # 1. ЛИГА
    # ========================================================

    st.subheader("🏆 Лига")

    leagues = list(LEAGUE_CONFIG.keys())

    league = st.selectbox(
        "Выберите соревнование",
        leagues,
        index=0,
        key="tour_league",
    )

    max_rounds = get_max_rounds(league)

    # ========================================================
    # 2. СЕЗОН
    # ========================================================

    seasons = db.get_seasons()

    league_seasons = [
        s for s in seasons
        if str(row_value(s, "league", "")) == league
    ]

    if not league_seasons:
        st.warning(
            f"⚠️ В базе пока нет сезона для «{league}»."
        )
        st.info(
            "Сначала создайте сезон в базе данных."
        )
        return

    # Предпочитаем текущий сезон.
    selected_season = None

    for s in league_seasons:
        name = season_name(s)

        if "2026" in name or "2026-27" in name or "2026/27" in name:
            selected_season = s
            break

    if selected_season is None:
        selected_season = league_seasons[0]

    sid = season_id(selected_season)

    st.caption(
        f"Сезон: **{season_name(selected_season)}**"
    )

    # ========================================================
    # 3. КОМАНДЫ
    # ========================================================

    teams = db.get_teams(league=league)

    if not teams:
        st.warning(
            f"⚠️ В базе нет команд для «{league}»."
        )
        return

    name_to_id = {
        team_name(team): int(team_id(team))
        for team in teams
    }

    team_names = sorted(name_to_id.keys())

    # ========================================================
    # 4. ТУР
    # ========================================================

    st.subheader("📅 Тур")

    rounds = db.get_rounds(sid)

    round_numbers = sorted(
        {
            int(row_value(r, "round_number", 0))
            for r in rounds
            if row_value(r, "round_number") is not None
        }
    )

    # Максимальный существующий тур
    max_existing = max(round_numbers, default=0)

    # Создаём список для выбора: существующие туры + следующий (если не превышает лимит)
    selectable_rounds = list(round_numbers)

    if max_existing < max_rounds:
        selectable_rounds.append(max_existing + 1)

    selectable_rounds = sorted(set(selectable_rounds))

    # Индекс для выбора — последний
    default_index = len(selectable_rounds) - 1 if selectable_rounds else 0

    round_number = st.selectbox(
        "Выберите тур",
        selectable_rounds,
        index=default_index,
        key="tour_round_number",
        format_func=lambda x: get_round_label(league, x),
    )

    # ========================================================
    # 5. НАХОДИМ / СОЗДАЁМ ТУР
    # ========================================================

    existing_round = None

    for r in rounds:
        if int(row_value(r, "round_number", -1)) == int(round_number):
            existing_round = r
            break

    if existing_round:
        round_id = int(row_value(existing_round, "id"))
        round_exists = True
    else:
        round_id = None
        round_exists = False

    # ========================================================
    # 6. СОЗДАТЬ ТУР
    # ========================================================

    if not round_exists:

        st.info(
            f"⚪ {get_round_label(league, round_number)} ещё не создан."
        )

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "➕ Создать тур",
                type="primary",
                key="create_round",
            ):
                try:
                    round_id = db.create_round(
                        sid,
                        int(round_number),
                    )

                    st.success(
                        f"✅ {get_round_label(league, round_number)} создан."
                    )

                    st.rerun()

                except Exception as exc:
                    st.error(
                        f"❌ Не удалось создать тур: {exc}"
                    )

        return

    # ========================================================
    # 7. ТЕКУЩИЙ ТУР
    # ========================================================

    st.success(
        f"🟡 {get_round_label(league, round_number)} создан"
    )

    matches = match_mgr.get_round_matches(round_id)

    # ========================================================
    # 8. ТУРНИРНАЯ ТАБЛИЦА / РЕЙТИНГ
    # ========================================================

    with st.expander("📊 Турнирная таблица", expanded=False):
        st.info(
            "Турнирная таблица будет рассчитываться "
            "из фактов матчей."
        )

    with st.expander("⭐ FAJ Rating команд", expanded=False):
        st.info(
            "FAJ Rating будет отображаться из текущего "
            "слоя рейтингов/паспортов."
        )

    st.divider()

    # ========================================================
    # 9. МАТЧИ ТУРА
    # ========================================================

    st.subheader(
        f"⚽ Матчи {get_round_label(league, round_number)}"
    )

    if not matches:

        st.info(
            "В этом туре пока нет матчей."
        )

    else:

        st.caption(
            f"Всего матчей: **{len(matches)}**"
        )

        for index, match in enumerate(matches, start=1):

            home_id = row_value(match, "home_team_id")
            away_id = row_value(match, "away_team_id")

            id_to_name = {
                int(team_id(team)): team_name(team)
                for team in teams
            }

            home_name = id_to_name.get(
                int(home_id),
                f"Команда #{home_id}",
            )

            away_name = id_to_name.get(
                int(away_id),
                f"Команда #{away_id}",
            )

            match_id = int(
                row_value(match, "id")
            )

            match_date = row_value(
                match,
                "date",
                "",
            )

            col_match, col_delete = st.columns(
                [5, 1]
            )

            with col_match:

                st.markdown(
                    f"### {index}. {home_name} — {away_name}"
                )

                if match_date:
                    st.caption(
                        f"📅 {match_date}"
                    )

                status = row_value(
                    match,
                    "status",
                    "scheduled",
                )

                st.caption(
                    f"Статус: {status}"
                )

            with col_delete:

                if st.button(
                    "🗑️ Удалить",
                    key=f"delete_match_{match_id}",
                ):

                    try:

                        deleted = db.delete_match(
                            match_id
                        )

                        if deleted:
                            st.success(
                                "Матч удалён."
                            )
                            st.rerun()
                        else:
                            st.warning(
                                "Матч уже отсутствует."
                            )

                    except Exception as exc:

                        st.error(
                            f"❌ Ошибка удаления: {exc}"
                        )

            st.divider()

    # ========================================================
    # 10. СОХРАНИТЬ ТУР (НОВОЕ!)
    # ========================================================

    if matches:
        st.divider()

        st.subheader("💾 Сохранение тура")

        col_save1, col_save2 = st.columns(2)

        with col_save1:
            if st.button(
                "💾 Сохранить тур",
                type="primary",
                key="save_round",
                use_container_width=True,
            ):
                try:
                    # Все матчи уже сохранены в БД при добавлении,
                    # но на всякий случай пробегаемся и сохраняем.
                    saved_count = 0
                    for match in matches:
                        match_data = dict(match)
                        match_id = match_mgr.save_match(match_data)
                        if match_id:
                            saved_count += 1

                    st.success(
                        f"✅ Тур {round_number} сохранён "
                        f"({saved_count} матчей)"
                    )

                except Exception as exc:
                    st.error(
                        f"❌ Ошибка сохранения тура: {exc}"
                    )

        with col_save2:
            st.info(
                "Матчи сохраняются в БД автоматически "
                "при добавлении. Эта кнопка — дополнительная "
                "страховка."
            )

    # ========================================================
    # 11. ДОБАВЛЕНИЕ МАТЧА
    # ========================================================

    st.subheader("➕ Добавить матч")

    # Команды, уже участвующие в туре.
    used_team_ids = set()

    for match in matches:

        home_id = row_value(
            match,
            "home_team_id",
        )

        away_id = row_value(
            match,
            "away_team_id",
        )

        if home_id is not None:
            used_team_ids.add(int(home_id))

        if away_id is not None:
            used_team_ids.add(int(away_id))

    available_team_names = [
        name
        for name, tid in name_to_id.items()
        if tid not in used_team_ids
    ]

    if not available_team_names:

        st.success(
            "✅ Все команды уже распределены по матчам этого тура."
        )

    else:

        col1, col2 = st.columns(2)

        with col1:

            home_name = st.selectbox(
                "Хозяева",
                ["— выберите команду —"]
                + available_team_names,
                key="home_team",
            )

        with col2:

            away_options = [
                name
                for name in available_team_names
                if name != home_name
            ]

            away_name = st.selectbox(
                "Гости",
                ["— выберите команду —"]
                + away_options,
                key="away_team",
            )

        match_date = st.date_input(
            "Дата матча",
            key="match_date",
        )

        if (
            home_name != "— выберите команду —"
            and away_name != "— выберите команду —"
        ):

            home_id = name_to_id.get(home_name)
            away_id = name_to_id.get(away_name)

            if home_id is None or away_id is None:

                st.error(
                    "❌ Не удалось определить ID команды."
                )

            elif home_id == away_id:

                st.error(
                    "❌ Команда не может играть сама с собой."
                )

            else:

                if st.button(
                    "➕ Добавить матч",
                    type="primary",
                    key="add_match",
                ):

                    # Проверяем существующий матч.
                    duplicate = False

                    for existing_match in matches:

                        existing_home = row_value(
                            existing_match,
                            "home_team_id",
                        )

                        existing_away = row_value(
                            existing_match,
                            "away_team_id",
                        )

                        existing_date = str(
                            row_value(
                                existing_match,
                                "date",
                                "",
                            )
                        )

                        if (
                            int(existing_home) == home_id
                            and int(existing_away) == away_id
                            and existing_date.startswith(
                                str(match_date)
                            )
                        ):
                            duplicate = True
                            break

                    if duplicate:

                        st.error(
                            f"❌ Матч {home_name} — "
                            f"{away_name} уже существует."
                        )

                    else:

                        try:

                            match_id = match_mgr.save_match(
                                {
                                    "round_id": round_id,
                                    "home_team_id": home_id,
                                    "away_team_id": away_id,
                                    "date": str(match_date),
                                    "competition": league,
                                    "status": "scheduled",
                                    "fact_status": "scheduled",
                                }
                            )

                            st.success(
                                f"✅ Матч создан. "
                                f"ID: {match_id}"
                            )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                f"❌ Ошибка сохранения матча: {exc}"
                            )

    # ========================================================
    # 12. УДАЛИТЬ ТУР
    # ========================================================

    st.divider()

    st.subheader("⚠️ Управление туром")

    if st.button(
        "🗑️ Удалить тур",
        key="delete_round",
    ):

        st.session_state[
            "confirm_delete_round"
        ] = True

    if st.session_state.get(
        "confirm_delete_round",
        False,
    ):

        st.warning(
            f"⚠️ Вы собираетесь удалить "
            f"{get_round_label(league, round_number)} и его матчи."
        )

        col_confirm, col_cancel = st.columns(2)

        with col_confirm:

            if st.button(
                "Да, удалить тур",
                type="primary",
                key="confirm_delete_round_button",
            ):

                try:

                    deleted = db.delete_round(
                        round_id
                    )

                    st.session_state[
                        "confirm_delete_round"
                    ] = False

                    if deleted:

                        st.success(
                            f"✅ {get_round_label(league, round_number)} удалён."
                        )

                        st.rerun()

                    else:

                        st.warning(
                            "Тур уже отсутствует."
                        )

                except Exception as exc:

                    st.error(
                        f"❌ Ошибка удаления тура: {exc}"
                    )

        with col_cancel:

            if st.button(
                "Отмена",
                key="cancel_delete_round",
            ):

                st.session_state[
                    "confirm_delete_round"
                ] = False

                st.rerun()

    # ========================================================
    # 13. НАВИГАЦИЯ
    # ========================================================

    if matches:

        st.divider()

        st.subheader("➡️ Следующий этап")

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "🧠 Прогнозы тура",
                type="primary",
                use_container_width=True,
                key="go_predictions",
            ):

                st.session_state.page = "predict_round"
                st.session_state.selected_round_id = round_id
                st.session_state.selected_round_number = round_number
                st.session_state.selected_league = league

                st.rerun()

        with col2:

            if st.button(
                "📥 Факты тура",
                use_container_width=True,
                key="go_facts",
            ):

                st.session_state.page = "import_facts"
                st.session_state.selected_round_id = round_id
                st.session_state.selected_round_number = round_number
                st.session_state.selected_league = league

                st.rerun()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
