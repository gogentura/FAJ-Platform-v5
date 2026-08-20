#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
TOUR MANAGER v4.3
============================================================

НАЗНАЧЕНИЕ:
    Управление календарём соревнований FAJ.

ОТВЕТСТВЕННОСТЬ:
    - выбор соревнования;
    - выбор сезона;
    - выбор тура;
    - создание тура;
    - добавление матчей;
    - просмотр матчей тура;
    - удаление отдельных матчей;
    - очистка матчей тура;
    - переход к Predict Round;
    - переход к Import Facts.

ВАЖНО:
    ТУРЫ НЕ УДАЛЯЮТСЯ.

    Кнопка «Очистить матчи тура» удаляет
    только матчи выбранного тура.

    Сам тур остаётся в базе данных и
    всегда доступен для повторного выбора.

    После очистки тура можно:
        - добавить матч;
        - добавить новые матчи;
        - полностью восстановить тур.

SQLite only.

database.py — единственный источник работы
со схемой БД.

Tour Manager НЕ рассчитывает:
    - xG;
    - рейтинг;
    - обучение;
    - статистику;
    - паспорта.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from app.database import FAJDatabase
from app.match_manager import MatchManager


# ============================================================
# COMPETITIONS
# ============================================================

COMPETITION_CONFIG = {
    "РПЛ": {
        "type": "domestic",
        "max_rounds": 30,
        "max_teams": 16,
        "rating_scope": "domestic",
    },
    "АПЛ": {
        "type": "domestic",
        "max_rounds": 38,
        "max_teams": 20,
        "rating_scope": "domestic",
    },
    "Ла Лига": {
        "type": "domestic",
        "max_rounds": 38,
        "max_teams": 20,
        "rating_scope": "domestic",
    },
    "Лига чемпионов": {
        "type": "ucl",
        "max_rounds": 17,
        "max_teams": 36,
        "rating_scope": "ucl",
    },
}


# ============================================================
# ROUND LABELS
# ============================================================

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
        9: "Стыковые матчи — 1-й матч",
        10: "Стыковые матчи — 2-й матч",
        11: "1/8 финала — 1-й матч",
        12: "1/8 финала — 2-й матч",
        13: "Четвертьфинал — 1-й матч",
        14: "Четвертьфинал — 2-й матч",
        15: "Полуфинал — 1-й матч",
        16: "Полуфинал — 2-й матч",
        17: "Финал",
    }
}


# ============================================================
# HELPERS
# ============================================================

def get_config(competition: str) -> dict[str, Any]:
    return COMPETITION_CONFIG.get(
        competition,
        {
            "type": "domestic",
            "max_rounds": 30,
            "max_teams": 16,
            "rating_scope": "domestic",
        },
    )


def get_max_rounds(competition: str) -> int:
    return int(
        get_config(competition)["max_rounds"]
    )


def get_round_label(
    competition: str,
    round_number: int,
) -> str:

    labels = ROUND_LABELS.get(
        competition,
        {},
    )

    return labels.get(
        int(round_number),
        f"Тур {round_number}",
    )


def row_value(
    row: Any,
    key: str,
    default: Any = None,
) -> Any:

    try:
        return row[key]

    except (
        KeyError,
        IndexError,
        TypeError,
    ):
        return default


def team_id(team: Any) -> Any:

    if isinstance(team, dict):
        return team.get("id")

    return team["id"]


def team_name(team: Any) -> str:

    if isinstance(team, dict):
        return str(team.get("name", ""))

    return str(team["name"])


def season_id(season: Any) -> Any:

    if isinstance(season, dict):
        return season.get("id")

    return season["id"]


def season_name(season: Any) -> str:

    if isinstance(season, dict):
        return str(season.get("name", ""))

    return str(season["name"])


# ============================================================
# LOCK STATUS
# ============================================================

def match_is_locked(
    db: FAJDatabase,
    match_id: int,
) -> bool:

    """
    LOCKED используется только как
    информационный статус.

    LOCKED НЕ запрещает удаление матча.
    """

    try:
        return bool(
            db.is_result_locked(match_id)
        )

    except Exception:
        return False


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    st.title("🏟️ Управление туром")

    st.caption(
        "FAJ Platform v12.1 — календарь соревнований"
    )

    db = FAJDatabase()

    match_mgr = MatchManager(db)

    # ========================================================
    # 1. COMPETITION
    # ========================================================

    st.subheader("🏆 Соревнование")

    competitions = list(
        COMPETITION_CONFIG.keys()
    )

    competition = st.selectbox(
        "Выберите соревнование",
        competitions,
        index=0,
        key="tour_competition",
    )

    config = get_config(competition)

    is_ucl = (
        config["type"] == "ucl"
    )

    if is_ucl:

        st.info(
            "🏆 Лига чемпионов работает "
            "в отдельном турнирном контуре. "
            "Турнирная таблица и FAJ Rating ЛЧ "
            "не смешиваются с внутренними "
            "чемпионатами."
        )

    # ========================================================
    # 2. SEASON
    # ========================================================

    st.subheader("📆 Сезон")

    seasons = db.get_seasons()

    league_seasons = [
        season
        for season in seasons
        if str(
            row_value(
                season,
                "league",
                "",
            )
        ) == competition
    ]

    if not league_seasons:

        st.warning(
            f"⚠️ В базе пока нет сезона "
            f"для «{competition}»."
        )

        st.info(
            "Сначала создайте соответствующий "
            "сезон в базе данных."
        )

        return

    # --------------------------------------------------------
    # Предпочитаем сезон 2026/27
    # --------------------------------------------------------

    selected_season = None

    for season in league_seasons:

        name = season_name(season)

        if (
            "2026/27" in name
            or "2026-27" in name
            or "2026" in name
        ):

            selected_season = season
            break

    if selected_season is None:

        selected_season = league_seasons[0]

    sid = season_id(selected_season)

    st.caption(
        f"Сезон: **{season_name(selected_season)}**"
    )

    # ========================================================
    # 3. TEAMS
    # ========================================================

    teams = db.get_teams(
        league=competition
    )

    if not teams:

        st.warning(
            f"⚠️ В базе нет команд "
            f"для «{competition}»."
        )

        if is_ucl:

            st.info(
                "Для Лиги чемпионов команды "
                "будут загружены отдельным "
                "турнирным контуром."
            )

        return

    name_to_id = {
        team_name(team): int(team_id(team))
        for team in teams
    }

    # ========================================================
    # 4. ROUND
    # ========================================================

    st.subheader("📅 Тур")

    max_rounds = get_max_rounds(
        competition
    )

    rounds = db.get_rounds(sid)

    # ========================================================
    # ВСЕ ТУРЫ ДОСТУПНЫ ВСЕГДА
    # ========================================================
    #
    # В отличие от v4.1:
    #
    # selectable_rounds НЕ зависит от БД.
    #
    # Например, для РПЛ:
    #
    # 1 ... 30
    #
    # Даже если Тур 1 пустой или был очищен,
    # он остаётся доступным.
    #
    # Если тура нет в БД — его можно создать.
    # ========================================================

    selectable_rounds = list(
        range(1, max_rounds + 1)
    )

    round_number = st.selectbox(
        "Выберите тур",
        selectable_rounds,
        index=0,
        key="tour_round_number",
        format_func=lambda number:
            get_round_label(
                competition,
                number,
            ),
    )

    # ========================================================
    # 5. EXISTING ROUND
    # ========================================================

    existing_round = None

    for current_round in rounds:

        current_number = row_value(
            current_round,
            "round_number",
        )

        if (
            current_number is not None
            and int(current_number)
            == int(round_number)
        ):

            existing_round = current_round
            break

    # ========================================================
    # 6. CREATE ROUND
    # ========================================================

    if existing_round is None:

        st.info(
            f"⚪ "
            f"{get_round_label(competition, round_number)} "
            f"ещё не создан."
        )

        if st.button(
            "➕ Создать тур",
            type="primary",
            use_container_width=True,
            key="create_round",
        ):

            try:

                created_round_id = (
                    db.create_round(
                        sid,
                        int(round_number),
                    )
                )

                if created_round_id is None:

                    st.error(
                        "❌ База данных "
                        "не вернула ID тура."
                    )

                    return

                st.success(
                    f"✅ "
                    f"{get_round_label(competition, round_number)} "
                    f"создан."
                )

                st.rerun()

            except Exception as exc:

                st.error(
                    f"❌ Не удалось создать тур: "
                    f"{exc}"
                )

        return

    round_id = int(
        row_value(
            existing_round,
            "id",
        )
    )

    st.success(
        f"🟢 "
        f"{get_round_label(competition, round_number)} "
        f"создан"
    )

    # ========================================================
    # 7. MATCHES
    # ========================================================

    matches = match_mgr.get_round_matches(
        round_id
    )

    # ========================================================
    # 8. LOCK INFORMATION
    # ========================================================

    locked_count = 0

    for match in matches:

        current_match_id = row_value(
            match,
            "id",
        )

        if current_match_id is None:
            continue

        if match_is_locked(
            db,
            int(current_match_id),
        ):

            locked_count += 1

    locked_round = locked_count > 0

    # ========================================================
    # 9. INFO
    # ========================================================

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:

        st.metric(
            "Матчей",
            len(matches),
        )

    with col2:

        st.metric(
            "LOCKED",
            locked_count,
        )

    with col3:

        if locked_round:

            st.metric(
                "Статус",
                "📚 История",
            )

        else:

            st.metric(
                "Статус",
                "🛠️ Календарь",
            )

    # ========================================================
    # 10. TOURNAMENT TABLE / RATING
    # ========================================================

    with st.expander(
        "📊 Турнирная таблица",
        expanded=False,
    ):

        if is_ucl:

            st.info(
                "Турнирная таблица Лиги чемпионов "
                "будет рассчитываться отдельно "
                "от внутренних чемпионатов."
            )

        else:

            st.info(
                "Турнирная таблица не рассчитывается "
                "Tour Manager. Она будет строиться "
                "из подтверждённых фактов матчей."
            )

    with st.expander(
        "⭐ FAJ Club Rating",
        expanded=False,
    ):

        st.info(
            "FAJ Club Rating не рассчитывается "
            "в Tour Manager. Рейтинг обновляется "
            "через FAJ Evolution Training Center."
        )

        if is_ucl:

            st.caption(
                "Для Лиги чемпионов используется "
                "отдельный UCL FAJ Rating."
            )

    # ========================================================
    # 11. MATCH LIST
    # ========================================================

    st.subheader(
        f"⚽ Матчи — "
        f"{get_round_label(competition, round_number)}"
    )

    if not matches:

        st.info(
            "В этом туре пока нет матчей."
        )

    else:

        st.caption(
            f"Всего матчей: **{len(matches)}**"
        )

        id_to_name = {
            int(team_id(team)): team_name(team)
            for team in teams
        }

        for index, match in enumerate(
            matches,
            start=1,
        ):

            home_id = row_value(
                match,
                "home_team_id",
            )

            away_id = row_value(
                match,
                "away_team_id",
            )

            home_name = id_to_name.get(
                int(home_id)
                if home_id is not None
                else -1,
                f"Команда #{home_id}",
            )

            away_name = id_to_name.get(
                int(away_id)
                if away_id is not None
                else -1,
                f"Команда #{away_id}",
            )

            match_id = row_value(
                match,
                "id",
            )

            if match_id is None:
                continue

            match_id = int(match_id)

            match_date = row_value(
                match,
                "date",
                "",
            )

            status = row_value(
                match,
                "status",
                "scheduled",
            )

            locked = match_is_locked(
                db,
                match_id,
            )

            col_match, col_delete = (
                st.columns([5, 1])
            )

            with col_match:

                if locked:

                    st.markdown(
                        f"### 🔒 {index}. "
                        f"{home_name} — "
                        f"{away_name}"
                    )

                else:

                    st.markdown(
                        f"### {index}. "
                        f"{home_name} — "
                        f"{away_name}"
                    )

                if match_date:

                    st.caption(
                        f"📅 {match_date}"
                    )

                st.caption(
                    f"Статус: {status}"
                )

                if locked:

                    st.warning(
                        "⚠️ Факт матча заблокирован. "
                        "Удаление всё равно разрешено "
                        "для исправления календаря "
                        "или ошибочно импортированного "
                        "матча."
                    )

            with col_delete:

                if st.button(
                    "🗑️ Удалить",
                    key=f"delete_match_{match_id}",
                    use_container_width=True,
                ):

                    if locked:

                        st.session_state[
                            f"confirm_delete_locked_{match_id}"
                        ] = True

                    else:

                        st.session_state[
                            f"confirm_delete_{match_id}"
                        ] = True

            # ------------------------------------------------
            # NORMAL DELETE CONFIRMATION
            # ------------------------------------------------

            if st.session_state.get(
                f"confirm_delete_{match_id}",
                False,
            ):

                st.warning(
                    f"Удалить матч "
                    f"**{home_name} — {away_name}**?"
                )

                confirm_col, cancel_col = (
                    st.columns(2)
                )

                with confirm_col:

                    if st.button(
                        "Да, удалить",
                        type="primary",
                        key=(
                            f"confirm_delete_button_"
                            f"{match_id}"
                        ),
                    ):

                        try:

                            deleted = db.delete_match(
                                match_id
                            )

                            st.session_state[
                                f"confirm_delete_{match_id}"
                            ] = False

                            if deleted:

                                st.success(
                                    "✅ Матч удалён."
                                )

                                st.rerun()

                            else:

                                st.warning(
                                    "Матч уже отсутствует."
                                )

                        except Exception as exc:

                            st.error(
                                f"❌ Ошибка удаления: "
                                f"{exc}"
                            )

                with cancel_col:

                    if st.button(
                        "Отмена",
                        key=f"cancel_delete_{match_id}",
                    ):

                        st.session_state[
                            f"confirm_delete_{match_id}"
                        ] = False

                        st.rerun()

            # ------------------------------------------------
            # LOCKED DELETE CONFIRMATION
            # ------------------------------------------------

            if st.session_state.get(
                f"confirm_delete_locked_{match_id}",
                False,
            ):

                st.error(
                    "⚠️ ВНИМАНИЕ: этот матч содержит "
                    "заблокированный исторический факт."
                )

                st.warning(
                    "Удаление уничтожит запись матча "
                    "через механизм database.py. "
                    "Используйте это только если матч "
                    "создан или импортирован ошибочно."
                )

                confirm_col, cancel_col = (
                    st.columns(2)
                )

                with confirm_col:

                    if st.button(
                        "⚠️ Да, удалить ошибочный матч",
                        type="primary",
                        key=(
                            f"confirm_locked_delete_"
                            f"button_{match_id}"
                        ),
                    ):

                        try:

                            deleted = db.delete_match(
                                match_id
                            )

                            st.session_state[
                                f"confirm_delete_locked_{match_id}"
                            ] = False

                            if deleted:

                                st.success(
                                    "✅ Ошибочный матч "
                                    "удалён."
                                )

                                st.rerun()

                            else:

                                st.warning(
                                    "Матч уже отсутствует."
                                )

                        except Exception as exc:

                            st.error(
                                f"❌ Ошибка удаления: "
                                f"{exc}"
                            )

                with cancel_col:

                    if st.button(
                        "Отмена",
                        key=(
                            f"cancel_locked_delete_"
                            f"{match_id}"
                        ),
                    ):

                        st.session_state[
                            f"confirm_delete_locked_{match_id}"
                        ] = False

                        st.rerun()

            st.divider()

    # ========================================================
    # 12. SAVE ROUND
    # ========================================================

    if matches:

        st.subheader(
            "💾 Сохранение тура"
        )

        if st.button(
            "💾 Сохранить тур",
            type="primary",
            use_container_width=True,
            key="save_round",
        ):

            try:

                saved_count = 0

                for match in matches:

                    match_data = dict(match)

                    match_id = (
                        match_mgr.save_match(
                            match_data
                        )
                    )

                    if match_id:

                        saved_count += 1

                st.success(
                    "✅ Проверено/сохранено "
                    f"матчей: {saved_count}"
                )

            except Exception as exc:

                st.error(
                    f"❌ Ошибка сохранения тура: "
                    f"{exc}"
                )

    # ========================================================
    # 13. ADD MATCH
    # ========================================================

    st.subheader(
        "➕ Добавить матч"
    )

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

            used_team_ids.add(
                int(home_id)
            )

        if away_id is not None:

            used_team_ids.add(
                int(away_id)
            )

    available_team_names = [
        name
        for name, tid in name_to_id.items()
        if tid not in used_team_ids
    ]

    if not available_team_names:

        st.success(
            "✅ Все команды уже распределены "
            "по матчам этого тура."
        )

    else:

        col1, col2 = st.columns(2)

        with col1:

            home_name = st.selectbox(
                "Хозяева",
                [
                    "— выберите команду —"
                ] + available_team_names,
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
                [
                    "— выберите команду —"
                ] + away_options,
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

            home_id = name_to_id.get(
                home_name
            )

            away_id = name_to_id.get(
                away_name
            )

            if (
                home_id is None
                or away_id is None
            ):

                st.error(
                    "❌ Не удалось определить "
                    "ID команды."
                )

            elif home_id == away_id:

                st.error(
                    "❌ Команда не может играть "
                    "сама с собой."
                )

            else:

                if st.button(
                    "➕ Добавить матч",
                    type="primary",
                    use_container_width=True,
                    key="add_match",
                ):

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
                            existing_home is not None
                            and existing_away is not None
                            and int(existing_home)
                            == home_id
                            and int(existing_away)
                            == away_id
                            and existing_date.startswith(
                                str(match_date)
                            )
                        ):

                            duplicate = True
                            break

                    if duplicate:

                        st.error(
                            f"❌ Матч "
                            f"{home_name} — "
                            f"{away_name} "
                            f"уже существует."
                        )

                    else:

                        try:

                            match_id = (
                                match_mgr.save_match(
                                    {
                                        "round_id": round_id,
                                        "home_team_id": home_id,
                                        "away_team_id": away_id,
                                        "date": str(match_date),
                                        "competition": competition,
                                        "status": "scheduled",
                                        "fact_status": "scheduled",
                                    }
                                )
                            )

                            st.success(
                                f"✅ Матч создан. "
                                f"ID: {match_id}"
                            )

                            st.rerun()

                        except Exception as exc:

                            st.error(
                                "❌ Ошибка сохранения "
                                f"матча: {exc}"
                            )

    # ========================================================
    # 14. CLEAR ROUND MATCHES
    # ========================================================

    st.divider()

    st.subheader(
        "🧹 Управление матчами тура"
    )

    if matches:

        st.info(
            "Здесь можно полностью очистить "
            "матчи выбранного тура. "
            "Сам тур НЕ будет удалён."
        )

        if locked_round:

            st.warning(
                "⚠️ В туре есть заблокированные "
                "исторические матчи."
            )

            st.caption(
                "Очистка всё равно разрешена для "
                "исправления ошибочно созданного "
                "или импортированного календаря."
            )

        if st.button(
            "🧹 Очистить матчи тура",
            key="clear_round_matches",
            use_container_width=True,
        ):

            st.session_state[
                "confirm_clear_round_matches"
            ] = True

    else:

        st.info(
            "В этом туре нет матчей для очистки."
        )

    # --------------------------------------------------------
    # CLEAR CONFIRMATION
    # --------------------------------------------------------

    if st.session_state.get(
        "confirm_clear_round_matches",
        False,
    ):

        st.warning(
            f"⚠️ Вы собираетесь удалить "
            f"все матчи из "
            f"{get_round_label(competition, round_number)}."
        )

        st.info(
            "Сам тур останется в базе данных "
            "и будет доступен для выбора. "
            "После очистки можно добавить матчи "
            "заново."
        )

        col_confirm, col_cancel = (
            st.columns(2)
        )

        with col_confirm:

            if st.button(
                "⚠️ Да, очистить матчи",
                type="primary",
                key="confirm_clear_round_matches_button",
                use_container_width=True,
            ):

                try:

                    deleted_count = 0

                    # ------------------------------------------------
                    # ВАЖНО:
                    # Сам round НЕ удаляется.
                    #
                    # Удаляются только матчи,
                    # которые принадлежат выбранному round_id.
                    #
                    # Используется существующий метод
                    # database.py:
                    #
                    #     db.delete_match(match_id)
                    #
                    # Новый API/метод НЕ требуется.
                    # ------------------------------------------------

                    for match in matches:

                        match_id = row_value(
                            match,
                            "id",
                        )

                        if match_id is None:
                            continue

                        deleted = db.delete_match(
                            int(match_id)
                        )

                        if deleted:
                            deleted_count += 1

                    st.session_state[
                        "confirm_clear_round_matches"
                    ] = False

                    st.success(
                        f"✅ Матчи тура очищены. "
                        f"Удалено: {deleted_count}."
                    )

                    st.rerun()

                except Exception as exc:

                    st.error(
                        f"❌ Ошибка очистки матчей: "
                        f"{exc}"
                    )

        with col_cancel:

            if st.button(
                "Отмена",
                key="cancel_clear_round_matches",
                use_container_width=True,
            ):

                st.session_state[
                    "confirm_clear_round_matches"
                ] = False

                st.rerun()

    # ========================================================
    # 15. NAVIGATION
    # ========================================================

    if matches:

        st.divider()

        st.subheader(
            "➡️ Следующий этап"
        )

        col1, col2 = st.columns(2)

        with col1:

            if st.button(
                "🧠 Прогнозы тура",
                type="primary",
                use_container_width=True,
                key="go_predictions",
            ):

                st.session_state.page = (
                    "predict_round"
                )

                st.session_state.selected_round_id = (
                    round_id
                )

                st.session_state.selected_round_number = (
                    round_number
                )

                st.session_state.selected_league = (
                    competition
                )

                st.session_state.selected_competition = (
                    competition
                )

                st.rerun()

        with col2:

            if st.button(
                "📥 Факты тура",
                use_container_width=True,
                key="go_facts",
            ):

                st.session_state.page = (
                    "import_facts"
                )

                st.session_state.selected_round_id = (
                    round_id
                )

                st.session_state.selected_round_number = (
                    round_number
                )

                st.session_state.selected_league = (
                    competition
                )

                st.session_state.selected_competition = (
                    competition
                )

                st.rerun()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
