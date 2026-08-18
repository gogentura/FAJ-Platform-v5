#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1 — MEMORY HARDENED
Управление туром v3.0

Главный экран FAJ.

ОТВЕТСТВЕННОСТЬ:
    - выбор лиги;
    - выбор тура;
    - создание тура;
    - добавление матчей;
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

    leagues = [
        "РПЛ",
        "АПЛ",
        "Ла Лига",
        "Лига чемпионов",
    ]

    league = st.selectbox(
        "Выберите соревнование",
        leagues,
        index=0,
        key="tour_league",
    )

    # ========================================================
    # 2. СЕЗОН
    # ========================================================

    seasons = db.get_seasons()

    league_seasons = [
        s for s in seasons
        if str(row_value(s, "league", "")) == league
    ]

    # Для текущего проекта РПЛ 2026/27.
    # Для остальных лиг показываем сообщение, если сезон ещё
    # не создан в БД.

    if not league_seasons:
        st.warning(
            f"⚠️ В базе пока нет сезона для «{league}»."
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

    # Создаём map ОДИН раз.
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

    # Добавляем возможность создать новый тур.
    max_round = max(round_numbers, default=0)

    selectable_rounds = sorted(
        set(round_numbers + [max_round + 1])
    )

    round_number = st.selectbox(
        "Выберите тур",
        selectable_rounds,
        index=(
            selectable_rounds.index(max_round + 1)
            if max_round + 1 in selectable_rounds
            else 0
        ),
        key="tour_round_number",
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
            f"⚪ Тур {round_number} ещё не создан."
        )

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
                    f"✅ Тур {round_number} создан."
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
        f"🟡 Тур {round_number} создан"
    )

    matches = match_mgr.get_round_matches(round_id)

    # ========================================================
    # 8. ТУРНИРНАЯ ТАБЛИЦА / РЕЙТИНГ
    # ========================================================
    #
    # Пока оставляем этот блок безопасным:
    # он не вмешивается в календарь и не создаёт
    # дополнительных зависимостей.
    #
    # Когда подключим standings_manager / FAJ Rating,
    # сюда будет выведен реальный расчёт из БД.
    #

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
        f"⚽ Матчи тура {round_number}"
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

            # Обратный map для отображения.
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
    # 10. ДОБАВЛЕНИЕ МАТЧА
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

            # Если хозяева выбраны — не показываем
            # их повторно среди гостей.
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
    # 11. УДАЛИТЬ ТУР
    # ========================================================

    st.divider()

    st.subheader("⚠️ Управление туром")

    if st.button(
        "🗑️ Удалить тур",
        key="delete_round",
    ):

        # Дополнительное подтверждение.
        st.session_state[
            "confirm_delete_round"
        ] = True

    if st.session_state.get(
        "confirm_delete_round",
        False,
    ):

        st.warning(
            f"⚠️ Вы собираетесь удалить тур "
            f"{round_number} и его матчи."
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
                            f"✅ Тур {round_number} удалён."
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
    # 12. НАВИГАЦИЯ
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
