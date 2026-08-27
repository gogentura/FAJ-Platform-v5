#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Tour Manager v5.2

Главная задача:
    календарь -> сезон -> тур -> матчи.

Tour Manager НЕ рассчитывает рейтинг.

v5.1:
    При выборе пары команд отображается FAJ рейтинг
    из START_RATINGS (только в UI, не сохраняется).

v5.2:
    Исправлен импорт: FAJ_CLUB_RATINGS вместо START_RATINGS.
"""

from __future__ import annotations

import inspect
import logging
from typing import Any, Dict, List, Optional

import streamlit as st

from app.database import FAJDatabase
from app.match_manager import MatchManager
from app.faj_club_ratings import (
    get_league_ratings,
    get_all_tournaments,
)

logger = logging.getLogger(__name__)


COMPETITION_CONFIG = {
    "РПЛ": {
        "type": "domestic",
        "max_rounds": 30,
    },
    "АПЛ": {
        "type": "domestic",
        "max_rounds": 38,
    },
    "Ла Лига": {
        "type": "domestic",
        "max_rounds": 38,
    },
    "Лига чемпионов": {
        "type": "ucl",
        "max_rounds": 17,
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


SEASON_NAME = "2026/27"
DEFAULT_RATING = 50.0
PASSPORT_VERSION = "v1.0"


def row_value(row: Any, key: str, default: Any = None) -> Any:
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
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


def is_target_season(season: Any) -> bool:
    """Распознаёт 2026/27, 2026-2027 и 2026-27 как один сезон."""
    name = season_name(season).strip().replace("\u2013", "-").replace("\u2014", "-")
    normalized = name.replace(" ", "")
    return normalized in {"2026/27", "2026-27", "2026-2027"} or "2026/27" in normalized or "2026-27" in normalized or "2026-2027" in normalized


def get_round_label(competition: str, number: int) -> str:
    return ROUND_LABELS.get(competition, {}).get(
        int(number),
        f"Тур {number}",
    )


def match_is_locked(db: FAJDatabase, match_id: int) -> bool:
    try:
        return bool(db.is_result_locked(match_id))
    except Exception:
        return False


def get_team_rating(team_name: str) -> Optional[float]:
    """Получает стартовый рейтинг команды из FAJ Club Ratings."""
    try:
        from app.faj_club_ratings import FAJ_CLUB_RATINGS
        for league, teams in FAJ_CLUB_RATINGS.items():
            if team_name in teams:
                return float(teams[team_name])
    except Exception:
        pass
    return None


def get_team_rating_display(team_name: str) -> str:
    """Возвращает строку с названием и рейтингом для selectbox."""
    rating = get_team_rating(team_name)
    if rating is not None:
        return f"{team_name} — {rating:.1f}"
    return team_name


# ============================================================
# DATABASE API COMPATIBILITY
# ============================================================

def _call_db_create(method, values: dict[str, Any]):
    """
    Вызывает публичный метод database.py без прямого SQL.

    Поддерживает небольшие различия имён аргументов между версиями
    database.py.
    """
    signature = inspect.signature(method)
    params = signature.parameters

    aliases = {
        "name": ["name", "season_name", "team_name"],
        "league": ["league", "competition"],
        "year": ["year", "season_year"],
        "status": ["status"],
    }

    kwargs = {}

    for logical_name, candidates in aliases.items():
        value = values.get(logical_name)
        if value is None:
            continue

        for candidate in candidates:
            if candidate in params:
                kwargs[candidate] = value
                break

    if any(
        p.kind == inspect.Parameter.VAR_KEYWORD
        for p in params.values()
    ):
        for key, value in values.items():
            if value is not None:
                kwargs.setdefault(key, value)

    return method(**kwargs)


def _season_matches(name: str) -> bool:
    """Распознаёт 2026/27, 2026-27 и 2026-2027 как один сезон."""
    value = str(name or "").strip()
    return (
        "2026/27" in value
        or "2026-27" in value
        or "2026-2027" in value
    )


def _ensure_season(db: FAJDatabase, competition: str):
    """Гарантирует наличие сезона 2026/27."""
    seasons = db.get_seasons()

    for season in seasons:
        if (
            str(row_value(season, "league", "")) == competition
            and is_target_season(season)
        ):
            return season

    candidates = (
        "create_season",
        "add_season",
        "insert_season",
    )

    for method_name in candidates:
        method = getattr(db, method_name, None)
        if not callable(method):
            continue

        created = _call_db_create(
            method,
            {
                "name": SEASON_NAME,
                "league": competition,
                "year": 2026,
                "competition_type": "league" if competition != "Лига чемпионов" else "ucl",
                "status": "active",
            },
        )

        seasons = db.get_seasons()

        for season in seasons:
            if (
                str(row_value(season, "league", "")) == competition
                and _season_matches(season_name(season))
            ):
                return season

        if created:
            try:
                for season in seasons:
                    if season_id(season) == created:
                        return season
            except Exception:
                pass

    raise RuntimeError(
        f"database.py не предоставляет публичный метод создания сезона "
        f"для «{competition}». Нужен create_season/add_season."
    )


def _ensure_teams(db: FAJDatabase, competition: str):
    """
    Гарантирует наличие клубов турнира в таблице teams.

    Источник списка клубов — FAJ Club Rating.
    Сам рейтинг в БД не записывается.
    """
    rating_teams = get_league_ratings(competition)
    existing = db.get_teams(league=competition)

    existing_names = {
        team_name(team)
        for team in existing
    }

    missing = [
        name
        for name in rating_teams
        if name not in existing_names
    ]

    if not missing:
        return db.get_teams(league=competition)

    candidates = (
        "create_team",
        "add_team",
        "insert_team",
    )

    create_method = None

    for method_name in candidates:
        method = getattr(db, method_name, None)
        if callable(method):
            create_method = method
            break

    if create_method is None:
        raise RuntimeError(
            f"database.py не предоставляет публичный метод создания "
            f"команд для «{competition}». Нужен create_team/add_team."
        )

    for name in missing:
        _call_db_create(
            create_method,
            {
                "name": name,
                "league": competition,
            },
        )

    return db.get_teams(league=competition)


def _ensure_passports(db: FAJDatabase, competition: str, season_id: int, teams: List[Dict]) -> None:
    """
    Гарантирует наличие паспорта для каждой команды в сезоне.

    Если паспорт отсутствует, создаёт его с начальными параметрами:
        - все компоненты = 50.0
        - faj_rating = START_RATING (если есть) или 50.0
        - version = "v1.0"
        - source = "initial"
    """
    logger.info(f"🔍 Проверка паспортов для {competition} (season_id={season_id})")

    missing_count = 0

    for team in teams:
        team_id_val = int(team_id(team))
        team_name_val = team_name(team)

        existing_passport = db.get_team_passport(team_id_val, season_id)

        if existing_passport:
            continue

        logger.info(f"📝 Создаём паспорт для {team_name_val} (team_id={team_id_val})")

        rating = get_team_rating(team_name_val) or DEFAULT_RATING

        passport_data = {
            "attack": 50.0,
            "defense": 50.0,
            "control": 50.0,
            "tempo": 50.0,
            "press": 50.0,
            "transition": 50.0,
            "finishing": 50.0,
            "goalkeeper": 50.0,
            "discipline": 50.0,
            "squad_quality": 50.0,
            "bench_quality": 50.0,
            "coach_factor": 50.0,
            "mental": 50.0,
            "home_strength": 50.0,
            "away_strength": 50.0,
            "injury_factor": 50.0,
            "key_player_loss": 50.0,
            "league_adaptation": 80.0,
            "form": 50.0,
            "passport_confidence": 0.5,
            "faj_rating": rating,
            "force_update": True,
        }

        result = db.save_team_passport(
            team_id=team_id_val,
            season_id=season_id,
            data=passport_data,
            version=PASSPORT_VERSION,
            source="initial",
        )

        if result is not None:
            logger.info(f"✅ Паспорт создан для {team_name_val}: faj_rating={rating}")
            missing_count += 1
        else:
            logger.warning(f"⚠️ Не удалось создать паспорт для {team_name_val}")

    if missing_count > 0:
        logger.info(f"✅ Создано паспортов для {competition}: {missing_count}")
    else:
        logger.info(f"✅ Все паспорта для {competition} уже существуют")


def ensure_competition_data(db: FAJDatabase, competition: str):
    """
    Один bootstrap для Tour Manager:
        сезон 2026/27 + команды соревнования + паспорта.
    """
    if competition not in get_all_tournaments():
        raise RuntimeError(
            f"Для «{competition}» нет FAJ Club Rating."
        )

    season = _ensure_season(db, competition)
    teams = _ensure_teams(db, competition)

    season_id_val = int(season_id(season))

    _ensure_passports(db, competition, season_id_val, teams)

    return season, teams


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    st.title("🏟️ Управление туром")
    st.caption("FAJ Platform — календарь соревнований")

    db = FAJDatabase()
    match_mgr = MatchManager(db)

    st.subheader("🏆 Соревнование")

    competition = st.selectbox(
        "Выберите соревнование",
        list(COMPETITION_CONFIG.keys()),
        index=0,
        key="tour_competition",
    )

    config = COMPETITION_CONFIG[competition]
    is_ucl = config["type"] == "ucl"

    # --------------------------------------------------------
    # AUTO BOOTSTRAP
    # --------------------------------------------------------

    try:
        selected_season, teams = ensure_competition_data(
            db,
            competition,
        )
    except Exception as exc:
        st.error(
            f"❌ Не удалось подготовить «{competition}» "
            f"для сезона {SEASON_NAME}."
        )
        st.code(str(exc))
        st.info(
            "Tour Manager не создаёт SQL сам. "
            "Он использует только публичный API database.py."
        )
        return

    if is_ucl:
        st.info(
            "🏆 Лига чемпионов — отдельный турнирный контур. "
            "Его сезон и команды не смешиваются с внутренными чемпионатами."
        )

    # --------------------------------------------------------
    # SEASON
    # --------------------------------------------------------

    st.subheader("📆 Сезон")
    st.caption(
        f"Сезон: **{season_name(selected_season)}**"
    )

    sid = int(season_id(selected_season))

    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

    if not teams:
        st.error(
            f"❌ После инициализации в БД всё ещё нет команд "
            f"для «{competition}»."
        )
        return

    name_to_id = {
        team_name(team): int(team_id(team))
        for team in teams
    }

    # --------------------------------------------------------
    # ROUND
    # --------------------------------------------------------

    st.subheader("📅 Тур")

    max_rounds = int(config["max_rounds"])
    rounds = db.get_rounds(sid)

    round_number = st.selectbox(
        "Выберите тур",
        list(range(1, max_rounds + 1)),
        index=0,
        key="tour_round_number",
        format_func=lambda number: get_round_label(
            competition,
            number,
        ),
    )

    existing_round = None

    for current_round in rounds:
        current_number = row_value(
            current_round,
            "round_number",
        )

        if (
            current_number is not None
            and int(current_number) == int(round_number)
        ):
            existing_round = current_round
            break

    if existing_round is None:
        st.info(
            f"⚪ {get_round_label(competition, round_number)} ещё не создан."
        )

        if st.button(
            "➕ Создать тур",
            type="primary",
            use_container_width=True,
            key="create_round",
        ):
            try:
                created_round_id = db.create_round(
                    sid,
                    int(round_number),
                )

                if created_round_id is None:
                    st.error("❌ База не вернула ID тура.")
                    return

                st.success(
                    f"✅ {get_round_label(competition, round_number)} создан."
                )
                st.rerun()

            except Exception as exc:
                st.error(f"❌ Не удалось создать тур: {exc}")

        return

    round_id = int(row_value(existing_round, "id"))

    st.success(
        f"🟢 {get_round_label(competition, round_number)} создан"
    )

    # --------------------------------------------------------
    # MATCHES
    # --------------------------------------------------------

    matches = match_mgr.get_round_matches(round_id)

    locked_count = sum(
        1
        for match in matches
        if row_value(match, "id") is not None
        and match_is_locked(db, int(row_value(match, "id")))
    )

    st.divider()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Матчей", len(matches))

    with col2:
        st.metric("LOCKED", locked_count)

    with col3:
        st.metric(
            "Статус",
            "📚 История" if locked_count else "🛠️ Календарь",
        )

    # --------------------------------------------------------
    # MATCH LIST
    # --------------------------------------------------------

    st.subheader(
        f"⚽ Матчи — {get_round_label(competition, round_number)}"
    )

    if not matches:
        st.info("В этом туре пока нет матчей.")
    else:
        id_to_name = {
            int(team_id(team)): team_name(team)
            for team in teams
        }

        for index, match in enumerate(matches, start=1):
            home_id = row_value(match, "home_team_id")
            away_id = row_value(match, "away_team_id")
            match_id = row_value(match, "id")

            home_name = id_to_name.get(
                int(home_id) if home_id is not None else -1,
                f"Команда #{home_id}",
            )
            away_name = id_to_name.get(
                int(away_id) if away_id is not None else -1,
                f"Команда #{away_id}",
            )

            if match_id is None:
                continue

            match_id = int(match_id)
            locked = match_is_locked(db, match_id)

            col_match, col_delete = st.columns([5, 1])

            with col_match:
                prefix = "🔒 " if locked else ""
                st.markdown(
                    f"### {prefix}{index}. "
                    f"{home_name} — {away_name}"
                )

                match_date = row_value(match, "date", "")
                if match_date:
                    st.caption(f"📅 {match_date}")

                st.caption(
                    f"Статус: {row_value(match, 'status', 'scheduled')}"
                )

            with col_delete:
                if st.button(
                    "🗑️ Удалить",
                    key=f"delete_match_{match_id}",
                    use_container_width=True,
                ):
                    st.session_state[
                        f"confirm_delete_{match_id}"
                    ] = True

            if st.session_state.get(
                f"confirm_delete_{match_id}",
                False,
            ):
                st.warning(
                    f"Удалить матч **{home_name} — {away_name}**?"
                )

                c1, c2 = st.columns(2)

                with c1:
                    if st.button(
                        "Да, удалить",
                        type="primary",
                        key=f"confirm_delete_button_{match_id}",
                    ):
                        try:
                            deleted = db.delete_match(match_id)
                            st.session_state[
                                f"confirm_delete_{match_id}"
                            ] = False

                            if deleted:
                                st.success("✅ Матч удалён.")
                                st.rerun()
                            else:
                                st.warning("Матч уже отсутствует.")
                        except Exception as exc:
                            st.error(f"❌ Ошибка удаления: {exc}")

                with c2:
                    if st.button(
                        "Отмена",
                        key=f"cancel_delete_{match_id}",
                    ):
                        st.session_state[
                            f"confirm_delete_{match_id}"
                        ] = False
                        st.rerun()

            st.divider()

    # ============================================================
    # ADD MATCH
    # ============================================================

    st.subheader("➕ Добавить матч")

    used_team_ids = set()

    for match in matches:
        home_id = row_value(match, "home_team_id")
        away_id = row_value(match, "away_team_id")

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
        # Формируем список с рейтингами для отображения
        available_with_ratings = [
            get_team_rating_display(name)
            for name in available_team_names
        ]

        c1, c2 = st.columns(2)

        with c1:
            selected_display = st.selectbox(
                "Хозяева",
                ["— выберите команду —"] + available_with_ratings,
                key="home_team",
            )

            # Извлекаем имя из строки с рейтингом
            if selected_display and selected_display != "— выберите команду —":
                home_name = selected_display.split(" — ")[0]
            else:
                home_name = "— выберите команду —"

        with c2:
            # Список гостей с рейтингами (исключаем выбранного хозяина)
            away_options = [
                get_team_rating_display(name)
                for name in available_team_names
                if name != home_name and home_name != "— выберите команду —"
            ]

            away_display = st.selectbox(
                "Гости",
                ["— выберите команду —"] + away_options,
                key="away_team",
            )

            # Извлекаем имя из строки с рейтингом
            if away_display and away_display != "— выберите команду —":
                away_name = away_display.split(" — ")[0]
            else:
                away_name = "— выберите команду —"

        match_date = st.date_input(
            "Дата матча",
            key="match_date",
        )

        # Показываем рейтинги выбранных команд (дополнительная информация)
        if home_name != "— выберите команду —" and away_name != "— выберите команду —":
            home_rating = get_team_rating(home_name)
            away_rating = get_team_rating(away_name)

            rating_col1, rating_col2 = st.columns(2)
            with rating_col1:
                if home_rating is not None:
                    st.caption(f"🏷️ FAJ Rating хозяев: **{home_rating:.1f}**")
                else:
                    st.caption("🏷️ FAJ Rating хозяев: не найден")

            with rating_col2:
                if away_rating is not None:
                    st.caption(f"🏷️ FAJ Rating гостей: **{away_rating:.1f}**")
                else:
                    st.caption("🏷️ FAJ Rating гостей: не найден")

        if (
            home_name != "— выберите команду —"
            and away_name != "— выберите команду —"
        ):
            home_id = name_to_id.get(home_name)
            away_id = name_to_id.get(away_name)

            if home_id == away_id:
                st.error("❌ Команда не может играть сама с собой.")
            elif st.button(
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
                        row_value(existing_match, "date", "")
                    )

                    if (
                        existing_home is not None
                        and existing_away is not None
                        and int(existing_home) == home_id
                        and int(existing_away) == away_id
                        and existing_date.startswith(str(match_date))
                    ):
                        duplicate = True
                        break

                if duplicate:
                    st.error("❌ Такой матч уже существует.")
                else:
                    try:
                        match_id = match_mgr.save_match(
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

                        st.success(
                            f"✅ Матч создан. ID: {match_id}"
                        )
                        st.rerun()

                    except Exception as exc:
                        st.error(
                            f"❌ Ошибка сохранения матча: {exc}"
                        )

    # --------------------------------------------------------
    # CLEAR ROUND
    # --------------------------------------------------------

    st.divider()
    st.subheader("🧹 Управление матчами тура")

    if matches:
        st.info(
            "Очистка удаляет только матчи. Сам тур и сезон остаются."
        )

        if st.button(
            "🧹 Очистить матчи тура",
            key="clear_round_matches",
            use_container_width=True,
        ):
            st.session_state[
                "confirm_clear_round_matches"
            ] = True

    if st.session_state.get(
        "confirm_clear_round_matches",
        False,
    ):
        st.warning(
            f"⚠️ Удалить все матчи из "
            f"{get_round_label(competition, round_number)}?"
        )

        c1, c2 = st.columns(2)

        with c1:
            if st.button(
                "⚠️ Да, очистить",
                type="primary",
                key="confirm_clear_round_matches_button",
            ):
                try:
                    deleted_count = 0

                    for match in matches:
                        match_id = row_value(match, "id")
                        if match_id is not None:
                            if db.delete_match(int(match_id)):
                                deleted_count += 1

                    st.session_state[
                        "confirm_clear_round_matches"
                    ] = False

                    st.success(
                        f"✅ Удалено матчей: {deleted_count}"
                    )
                    st.rerun()

                except Exception as exc:
                    st.error(
                        f"❌ Ошибка очистки: {exc}"
                    )

        with c2:
            if st.button(
                "Отмена",
                key="cancel_clear_round_matches",
            ):
                st.session_state[
                    "confirm_clear_round_matches"
                ] = False
                st.rerun()

    # --------------------------------------------------------
    # NEXT
    # --------------------------------------------------------

    if matches:
        st.divider()
        st.subheader("➡️ Следующий этап")

        c1, c2 = st.columns(2)

        with c1:
            if st.button(
                "🧠 Прогнозы тура",
                type="primary",
                use_container_width=True,
                key="go_predictions",
            ):
                st.session_state.page = "predict_round"
                st.session_state.selected_round_id = round_id
                st.session_state.selected_round_number = round_number
                st.session_state.selected_league = competition
                st.session_state.selected_competition = competition
                st.rerun()

        with c2:
            if st.button(
                "📥 Факты тура",
                use_container_width=True,
                key="go_facts",
            ):
                st.session_state.page = "import_facts"
                st.session_state.selected_round_id = round_id
                st.session_state.selected_round_number = round_number
                st.session_state.selected_league = competition
                st.session_state.selected_competition = competition
                st.rerun()


if __name__ == "__main__":
    main()
