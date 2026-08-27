#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ PLATFORM
TOUR MANAGER v5.0
============================================================

НАЗНАЧЕНИЕ:
    Управление календарём соревнований:

        соревнование
            ↓
        сезон 2026/27
            ↓
        тур
            ↓
        матчи

ОТВЕТСТВЕННОСТЬ:
    - выбор соревнования;
    - обеспечение сезона 2026/27;
    - обеспечение команд соревнования;
    - создание тура;
    - просмотр матчей тура;
    - добавление матча;
    - проверка дублей;
    - удаление отдельного матча;
    - очистка матчей тура;
    - переход к прогнозам;
    - переход к фактам.

НЕ ОТВЕЧАЕТ ЗА:
    - расчёт рейтинга;
    - прогнозирование;
    - расчёт фактов;
    - обучение;
    - парсинг;
    - прямую работу с SQL.

ПРИНЦИП:
    database.py = единственный слой работы с БД.

    Tour Manager использует только публичный API:
        FAJDatabase
        MatchManager

ПОДДЕРЖИВАЕМЫЕ СОРЕВНОВАНИЯ:
    - РПЛ
    - АПЛ
    - Ла Лига
    - Лига чемпионов

СЕЗОН:
    2026/27

ВАЖНО:
    Каждый турнир имеет собственный season_id.
    Команды фильтруются по league.
    Турнирные контуры между соревнованиями не смешиваются.
============================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st

from app.database import FAJDatabase
from app.match_manager import MatchManager
from app.faj_club_ratings import (
    get_all_tournaments,
    get_league_ratings,
)


# ============================================================
# CONFIGURATION
# ============================================================

SEASON_NAME = "2026/27"
SEASON_YEAR = 2026

COMPETITION_CONFIG = {
    "РПЛ": {
        "type": "domestic",
        "max_rounds": 30,
        "competition_type": "league",
    },
    "АПЛ": {
        "type": "domestic",
        "max_rounds": 38,
        "competition_type": "league",
    },
    "Ла Лига": {
        "type": "domestic",
        "max_rounds": 38,
        "competition_type": "league",
    },
    "Лига чемпионов": {
        "type": "ucl",
        "max_rounds": 17,
        "competition_type": "ucl",
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


PLACEHOLDER_TEAM = "— выберите команду —"


# ============================================================
# GENERIC HELPERS
# ============================================================

def row_value(
    row: Any,
    key: str,
    default: Any = None,
) -> Any:
    """
    Безопасно получает значение из dict / sqlite3.Row.
    """
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def team_id(team: Any) -> Optional[int]:
    value = row_value(team, "id")

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def team_name(team: Any) -> str:
    return str(row_value(team, "name", "") or "").strip()


def season_id(season: Any) -> Optional[int]:
    value = row_value(season, "id")

    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def season_name(season: Any) -> str:
    return str(
        row_value(season, "name", "")
        or ""
    ).strip()


def is_target_season(season: Any) -> bool:
    """
    Распознаёт:
        2026/27
        2026-27
        2026-2027

    как один целевой сезон.
    """

    value = season_name(season)

    normalized = (
        value
        .replace(" ", "")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )

    return normalized in {
        "2026/27",
        "2026-27",
        "2026-2027",
    }


def get_round_label(
    competition: str,
    number: int,
) -> str:
    """
    Возвращает человекочитаемое название тура.
    """

    return ROUND_LABELS.get(
        competition,
        {},
    ).get(
        int(number),
        f"Тур {number}",
    )


def match_is_locked(
    db: FAJDatabase,
    match_id: int,
) -> bool:
    """
    Безопасная проверка LOCK результата.
    """

    try:
        return bool(
            db.is_result_locked(match_id)
        )
    except Exception:
        return False


# ============================================================
# SEASON
# ============================================================

def find_season(
    db: FAJDatabase,
    competition: str,
) -> Optional[Any]:
    """
    Ищет сезон 2026/27 конкретного соревнования.
    """

    seasons = db.get_seasons()

    for season in seasons:
        season_league = str(
            row_value(
                season,
                "league",
                "",
            )
            or ""
        ).strip()

        if (
            season_league == competition
            and is_target_season(season)
        ):
            return season

    return None


def ensure_season(
    db: FAJDatabase,
    competition: str,
) -> Any:
    """
    Гарантирует наличие сезона 2026/27
    для выбранного соревнования.

    Используется только публичный API FAJDatabase.
    """

    existing = find_season(
        db,
        competition,
    )

    if existing is not None:
        return existing

    config = COMPETITION_CONFIG[competition]

    created_id = db.create_season(
        name=SEASON_NAME,
        league=competition,
        year=SEASON_YEAR,
        competition_type=config["competition_type"],
        status="active",
    )

    if created_id is None:
        raise RuntimeError(
            f"FAJDatabase.create_season() "
            f"не вернул ID сезона для «{competition}»."
        )

    created_id = int(created_id)

    # Повторно читаем БД.
    # Не полагаемся только на return value.
    created = find_season(
        db,
        competition,
    )

    if created is not None:
        return created

    # Теоретически create_season мог создать запись,
    # но get_seasons() мог вернуть другой формат.
    seasons = db.get_seasons()

    for season in seasons:
        sid = season_id(season)

        if sid == created_id:
            return season

    raise RuntimeError(
        f"Сезон «{SEASON_NAME}» для "
        f"«{competition}» был создан, "
        f"но не найден после повторного чтения БД."
    )


# ============================================================
# TEAMS
# ============================================================

def get_rating_team_names(
    competition: str,
) -> List[str]:
    """
    Получает список клубов соревнования
    из FAJ Club Rating.

    Сам рейтинг здесь НЕ записывается в БД.
    """

    raw = get_league_ratings(
        competition
    )

    result: List[str] = []

    for item in raw:
        if isinstance(item, str):
            name = item.strip()

        elif isinstance(item, dict):
            name = str(
                item.get("name", "")
            ).strip()

        else:
            name = str(item).strip()

        if name and name not in result:
            result.append(name)

    return result


def ensure_teams(
    db: FAJDatabase,
    competition: str,
) -> List[Any]:
    """
    Гарантирует наличие команд соревнования.

    Реальный API database.py:

        get_teams(league=None)
        add_team(...)

    create_team() НЕ используется.
    """

    existing = db.get_teams(
        league=competition
    )

    existing_names = {
        team_name(team)
        for team in existing
        if team_name(team)
    }

    rating_names = get_rating_team_names(
        competition
    )

    missing = [
        name
        for name in rating_names
        if name not in existing_names
    ]

    for name in missing:
        db.add_team(
            name=name,
            league=competition,
            country="",
            api_id=None,
            team_type="club",
            competition_group=None,
        )

    # Всегда перечитываем БД.
    teams = db.get_teams(
        league=competition
    )

    return teams


def ensure_competition_data(
    db: FAJDatabase,
    competition: str,
):
    """
    Полный bootstrap выбранного соревнования:

        season 2026/27
        +
        teams
    """

    if competition not in get_all_tournaments():
        raise RuntimeError(
            f"Для «{competition}» "
            f"нет данных FAJ Club Rating."
        )

    season = ensure_season(
        db,
        competition,
    )

    teams = ensure_teams(
        db,
        competition,
    )

    return season, teams


# ============================================================
# ROUND
# ============================================================

def find_round(
    rounds: List[Any],
    round_number: int,
) -> Optional[Any]:
    """
    Находит тур по номеру.
    """

    for current_round in rounds:
        value = row_value(
            current_round,
            "round_number",
        )

        if value is None:
            continue

        try:
            if int(value) == int(round_number):
                return current_round
        except (TypeError, ValueError):
            continue

    return None


def ensure_round(
    db: FAJDatabase,
    season_id_value: int,
    round_number: int,
) -> Any:
    """
    Возвращает существующий тур.
    Если тура нет — создаёт его.
    """

    rounds = db.get_rounds(
        season_id=season_id_value
    )

    existing = find_round(
        rounds,
        round_number,
    )

    if existing is not None:
        return existing

    created_id = db.create_round(
        season_id_value,
        int(round_number),
    )

    if created_id is None:
        raise RuntimeError(
            f"FAJDatabase.create_round() "
            f"не вернул ID для тура "
            f"{round_number}."
        )

    created_id = int(created_id)

    rounds = db.get_rounds(
        season_id=season_id_value
    )

    for current_round in rounds:
        rid = row_value(
            current_round,
            "id",
        )

        if rid is not None:
            try:
                if int(rid) == created_id:
                    return current_round
            except (TypeError, ValueError):
                pass

    existing = find_round(
        rounds,
        round_number,
    )

    if existing is not None:
        return existing

    raise RuntimeError(
        f"Тур {round_number} был создан, "
        f"но не найден после повторного чтения БД."
    )


# ============================================================
# MATCH HELPERS
# ============================================================

def build_team_maps(
    teams: List[Any],
):
    """
    Создаёт:

        name -> id
        id -> name
    """

    name_to_id: Dict[str, int] = {}
    id_to_name: Dict[int, str] = {}

    for team in teams:
        tid = team_id(team)
        name = team_name(team)

        if tid is None or not name:
            continue

        name_to_id[name] = tid
        id_to_name[tid] = name

    return name_to_id, id_to_name


def get_used_team_ids(
    matches: List[Dict[str, Any]],
) -> set[int]:
    """
    Возвращает команды, уже участвующие
    в матчах выбранного тура.
    """

    used: set[int] = set()

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
            try:
                used.add(int(home_id))
            except (TypeError, ValueError):
                pass

        if away_id is not None:
            try:
                used.add(int(away_id))
            except (TypeError, ValueError):
                pass

    return used


def count_locked_matches(
    db: FAJDatabase,
    matches: List[Dict[str, Any]],
) -> int:
    """
    Считает матчи с LOCK результатом.
    """

    count = 0

    for match in matches:
        match_id = row_value(
            match,
            "id",
        )

        if match_id is None:
            continue

        try:
            if match_is_locked(
                db,
                int(match_id),
            ):
                count += 1
        except (TypeError, ValueError):
            continue

    return count


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    st.title("🏟️ Управление туром")

    st.caption(
        "FAJ Platform — календарь соревнований"
    )

    db = FAJDatabase()

    match_mgr = MatchManager(db)

    # ========================================================
    # COMPETITION
    # ========================================================

    st.subheader("🏆 Соревнование")

    competition = st.selectbox(
        "Выберите соревнование",
        list(COMPETITION_CONFIG.keys()),
        index=0,
        key="tour_competition",
    )

    config = COMPETITION_CONFIG[
        competition
    ]

    is_ucl = (
        config["type"] == "ucl"
    )

    # ========================================================
    # BOOTSTRAP
    # ========================================================

    try:

        selected_season, teams = (
            ensure_competition_data(
                db,
                competition,
            )
        )

    except Exception as exc:

        st.error(
            f"❌ Не удалось подготовить "
            f"«{competition}» "
            f"для сезона {SEASON_NAME}."
        )

        st.exception(exc)

        st.info(
            "Tour Manager использует "
            "только публичный API FAJDatabase."
        )

        return

    # ========================================================
    # UCL NOTICE
    # ========================================================

    if is_ucl:

        st.info(
            "🏆 Лига чемпионов — отдельный "
            "турнирный контур. "
            "Её сезон и команды не смешиваются "
            "с внутренними чемпионатами."
        )

    # ========================================================
    # SEASON
    # ========================================================

    st.subheader("📆 Сезон")

    selected_season_id = season_id(
        selected_season
    )

    if selected_season_id is None:

        st.error(
            "❌ У выбранного сезона отсутствует ID."
        )

        return

    st.caption(
        f"Сезон: **{season_name(selected_season)}**  \n"
        f"Соревнование: **{competition}**"
    )

    # ========================================================
    # TEAMS
    # ========================================================

    if not teams:

        st.error(
            f"❌ В БД нет команд "
            f"для «{competition}»."
        )

        return

    name_to_id, id_to_name = (
        build_team_maps(teams)
    )

    if not name_to_id:

        st.error(
            "❌ Команды получены из БД, "
            "но ни у одной команды нет "
            "корректного ID или названия."
        )

        return

    # ========================================================
    # ROUND
    # ========================================================

    st.subheader("📅 Тур")

    max_rounds = int(
        config["max_rounds"]
    )

    rounds = db.get_rounds(
        season_id=selected_season_id
    )

    round_options = list(
        range(
            1,
            max_rounds + 1,
        )
    )

    round_number = st.selectbox(
        "Выберите тур",
        round_options,
        index=0,
        key="tour_round_number",
        format_func=lambda number:
            get_round_label(
                competition,
                number,
            ),
    )

    existing_round = find_round(
        rounds,
        round_number,
    )

    # ========================================================
    # CREATE ROUND
    # ========================================================

    if existing_round is None:

        st.info(
            f"⚪ {get_round_label(competition, round_number)} "
            f"ещё не создан."
        )

        if st.button(
            "➕ Создать тур",
            type="primary",
            use_container_width=True,
            key="create_round",
        ):

            try:

                created_id = db.create_round(
                    selected_season_id,
                    int(round_number),
                )

                if created_id is None:
                    st.error(
                        "❌ База не вернула ID тура."
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
                    f"❌ Не удалось создать тур: {exc}"
                )

        return

    # ========================================================
    # ROUND ID
    # ========================================================

    round_id_value = row_value(
        existing_round,
        "id",
    )

    if round_id_value is None:

        st.error(
            "❌ У выбранного тура отсутствует ID."
        )

        return

    round_id = int(
        round_id_value
    )

    st.success(
        f"🟢 {get_round_label(competition, round_number)} "
        f"создан"
    )

    # ========================================================
    # MATCHES
    # ========================================================

    matches = match_mgr.get_round_matches(
        round_id
    )

    locked_count = count_locked_matches(
        db,
        matches,
    )

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

        st.metric(
            "Статус",
            (
                "📚 История"
                if locked_count
                else "🛠️ Календарь"
            ),
        )

    # ========================================================
    # MATCH LIST
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

        for index, match in enumerate(
            matches,
            start=1,
        ):

            match_id_value = row_value(
                match,
                "id",
            )

            if match_id_value is None:
                continue

            match_id = int(
                match_id_value
            )

            home_id = row_value(
                match,
                "home_team_id",
            )

            away_id = row_value(
                match,
                "away_team_id",
            )

            # Предпочитаем имена, которые уже
            # возвращает get_matches().
            home_name = str(
                row_value(
                    match,
                    "home_team_name",
                    "",
                )
                or ""
            ).strip()

            away_name = str(
                row_value(
                    match,
                    "away_team_name",
                    "",
                )
                or ""
            ).strip()

            if not home_name and home_id is not None:
                try:
                    home_name = id_to_name.get(
                        int(home_id),
                        f"Команда #{home_id}",
                    )
                except (TypeError, ValueError):
                    home_name = (
                        f"Команда #{home_id}"
                    )

            if not away_name and away_id is not None:
                try:
                    away_name = id_to_name.get(
                        int(away_id),
                        f"Команда #{away_id}",
                    )
                except (TypeError, ValueError):
                    away_name = (
                        f"Команда #{away_id}"
                    )

            locked = match_is_locked(
                db,
                match_id,
            )

            col_match, col_delete = (
                st.columns([5, 1])
            )

            with col_match:

                prefix = (
                    "🔒 "
                    if locked
                    else ""
                )

                st.markdown(
                    f"### {prefix}{index}. "
                    f"{home_name} — {away_name}"
                )

                match_date = row_value(
                    match,
                    "date",
                    "",
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

                fact_status = row_value(
                    match,
                    "fact_status",
                    "",
                )

                st.caption(
                    f"Статус: {status}"
                )

                if fact_status:
                    st.caption(
                        f"Fact status: {fact_status}"
                    )

            with col_delete:

                if locked:

                    st.button(
                        "🔒",
                        disabled=True,
                        use_container_width=True,
                        key=f"locked_{match_id}",
                        help=(
                            "Результат матча "
                            "заблокирован."
                        ),
                    )

                else:

                    if st.button(
                        "🗑️ Удалить",
                        use_container_width=True,
                        key=f"delete_match_{match_id}",
                    ):

                        st.session_state[
                            f"confirm_delete_{match_id}"
                        ] = True

            # ------------------------------------------------
            # DELETE CONFIRMATION
            # ------------------------------------------------

            if st.session_state.get(
                f"confirm_delete_{match_id}",
                False,
            ):

                st.warning(
                    f"Удалить матч "
                    f"**{home_name} — {away_name}**?"
                )

                c1, c2 = st.columns(2)

                with c1:

                    if st.button(
                        "Да, удалить",
                        type="primary",
                        key=(
                            f"confirm_delete_button_"
                            f"{match_id}"
                        ),
                    ):

                        try:

                            deleted = (
                                match_mgr.delete_match(
                                    match_id
                                )
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
                                f"❌ Ошибка удаления: {exc}"
                            )

                with c2:

                    if st.button(
                        "Отмена",
                        key=(
                            f"cancel_delete_"
                            f"{match_id}"
                        ),
                    ):

                        st.session_state[
                            f"confirm_delete_{match_id}"
                        ] = False

                        st.rerun()

            st.divider()

    # ========================================================
    # ADD MATCH
    # ========================================================

    st.subheader("➕ Добавить матч")

    used_team_ids = get_used_team_ids(
        matches
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

        c1, c2 = st.columns(2)

        with c1:

            home_name = st.selectbox(
                "Хозяева",
                [
                    PLACEHOLDER_TEAM
                ]
                + available_team_names,
                key="home_team",
            )

        with c2:

            away_options = [
                name
                for name in available_team_names
                if name != home_name
            ]

            away_name = st.selectbox(
                "Гости",
                [
                    PLACEHOLDER_TEAM
                ]
                + away_options,
                key="away_team",
            )

        match_date = st.date_input(
            "Дата матча",
            key="match_date",
        )

        if (
            home_name != PLACEHOLDER_TEAM
            and away_name != PLACEHOLDER_TEAM
        ):

            home_id = name_to_id.get(
                home_name
            )

            away_id = name_to_id.get(
                away_name
            )

            if home_id is None:
                st.error(
                    "❌ Не найден ID хозяев."
                )

            elif away_id is None:
                st.error(
                    "❌ Не найден ID гостей."
                )

            elif home_id == away_id:
                st.error(
                    "❌ Команда не может "
                    "играть сама с собой."
                )

            elif st.button(
                "➕ Добавить матч",
                type="primary",
                use_container_width=True,
                key="add_match",
            ):

                match_date_string = str(
                    match_date
                )

                # --------------------------------------------
                # DUPLICATE CHECK
                # --------------------------------------------

                duplicate = (
                    match_mgr.find_duplicate(
                        round_id=round_id,
                        home_team_id=home_id,
                        away_team_id=away_id,
                        date=match_date_string,
                    )
                )

                if duplicate is not None:

                    duplicate_id = row_value(
                        duplicate,
                        "id",
                        "?",
                    )

                    st.error(
                        f"❌ Такой матч уже существует "
                        f"(ID: {duplicate_id})."
                    )

                else:

                    try:

                        match_id = (
                            match_mgr.save_match(
                                {
                                    "round_id": round_id,
                                    "home_team_id": home_id,
                                    "away_team_id": away_id,
                                    "date": match_date_string,
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
                            f"❌ Ошибка сохранения "
                            f"матча: {exc}"
                        )

    # ========================================================
    # CLEAR ROUND
    # ========================================================

    st.divider()

    st.subheader(
        "🧹 Управление матчами тура"
    )

    if matches:

        st.info(
            "Очистка удаляет только матчи. "
            "Сам тур и сезон остаются."
        )

        if locked_count:

            st.warning(
                f"🔒 В туре есть "
                f"{locked_count} заблокированных "
                f"результатов. "
                f"Они не могут быть удалены."
            )

        if st.button(
            "🧹 Очистить матчи тура",
            use_container_width=True,
            key="clear_round_matches",
        ):

            st.session_state[
                "confirm_clear_round_matches"
            ] = True

    if st.session_state.get(
        "confirm_clear_round_matches",
        False,
    ):

        st.warning(
            f"⚠️ Удалить доступные матчи из "
            f"{get_round_label(competition, round_number)}?"
        )

        if locked_count:

            st.caption(
                "🔒 Заблокированные матчи "
                "будут сохранены."
            )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "⚠️ Да, очистить",
                type="primary",
                key=(
                    "confirm_clear_round_matches_button"
                ),
            ):

                try:

                    deleted_count = 0
                    skipped_locked = 0

                    for match in matches:

                        match_id_value = row_value(
                            match,
                            "id",
                        )

                        if match_id_value is None:
                            continue

                        match_id = int(
                            match_id_value
                        )

                        if match_is_locked(
                            db,
                            match_id,
                        ):

                            skipped_locked += 1

                            continue

                        if match_mgr.delete_match(
                            match_id
                        ):

                            deleted_count += 1

                    st.session_state[
                        "confirm_clear_round_matches"
                    ] = False

                    if skipped_locked:

                        st.success(
                            f"✅ Удалено матчей: "
                            f"{deleted_count}. "
                            f"🔒 Сохранено LOCKED: "
                            f"{skipped_locked}."
                        )

                    else:

                        st.success(
                            f"✅ Удалено матчей: "
                            f"{deleted_count}."
                        )

                    st.rerun()

                except Exception as exc:

                    st.error(
                        f"❌ Ошибка очистки: {exc}"
                    )

        with c2:

            if st.button(
                "Отмена",
                key=(
                    "cancel_clear_round_matches"
                ),
            ):

                st.session_state[
                    "confirm_clear_round_matches"
                ] = False

                st.rerun()

    # ========================================================
    # NEXT STAGE
    # ========================================================

    if matches:

        st.divider()

        st.subheader(
            "➡️ Следующий этап"
        )

        c1, c2 = st.columns(2)

        with c1:

            if st.button(
                "🧠 Прогнозы тура",
                type="primary",
                use_container_width=True,
                key="go_predictions",
            ):

                st.session_state.page = (
                    "predict_round"
                )

                st.session_state[
                    "selected_round_id"
                ] = round_id

                st.session_state[
                    "selected_round_number"
                ] = round_number

                st.session_state[
                    "selected_league"
                ] = competition

                st.session_state[
                    "selected_competition"
                ] = competition

                st.rerun()

        with c2:

            if st.button(
                "📥 Факты тура",
                use_container_width=True,
                key="go_facts",
            ):

                st.session_state.page = (
                    "import_facts"
                )

                st.session_state[
                    "selected_round_id"
                ] = round_id

                st.session_state[
                    "selected_round_number"
                ] = round_number

                st.session_state[
                    "selected_league"
                ] = competition

                st.session_state[
                    "selected_competition"
                ] = competition

                st.rerun()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
