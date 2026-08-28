#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v12.1 — Initial Passport Creator v1.0

Однократное создание стартовых паспортов v1.0 из FAJ_CLUB_RATINGS.

Правила:
- START_RATING берётся только из app.faj_club_ratings.
- database.py не изменяется.
- Прямого SQL нет.
- Команды/сезоны создаются через FAJDatabase.
- Паспорта создаются через PassportManager.
- Повторный запуск существующие паспорта не перезаписывает.
- ETC/обучение не запускается.
"""

import streamlit as st

from app.database import FAJDatabase
from app.faj_club_ratings import FAJ_CLUB_RATINGS, FAJ_SEASON, get_all_ratings
from app.passport_manager import PassportManager


SEASON_YEAR = 2026

COMPETITION_TYPES = {
    "РПЛ": "league",
    "АПЛ": "league",
    "Ла Лига": "league",
    "Лига чемпионов": "cup",
}


def get_or_create_season(db, tournament):
    return db.create_season(
        name=FAJ_SEASON,
        league=tournament,
        year=SEASON_YEAR,
        competition_type=COMPETITION_TYPES.get(tournament, "league"),
        status="active",
    )


def get_or_create_team(db, tournament, team_name):
    teams = db.get_teams(league=tournament)
    for team in teams:
        if team["name"] == team_name:
            return int(team["id"])

    return int(
        db.add_team(
            name=team_name,
            league=tournament,
            country="",
            team_type="club",
            competition_group=tournament,
        )
    )


def build_initial_passport(start_rating):
    r = float(start_rating)

    # Все силовые параметры v1.0 получают исторический START_RATING.
    # Поэтому PassportManager.calculate_rating() сохраняет тот же рейтинг.
    return {
        "attack": r,
        "defense": r,
        "control": r,
        "tempo": r,
        "press": r,
        "transition": r,
        "finishing": r,
        "goalkeeper": r,
        "discipline": r,
        "squad_quality": r,
        "bench_quality": r,
        "coach_factor": r,
        "mental": r,
        "home_strength": r,
        "away_strength": r,
        "injury_factor": r,
        "key_player_loss": r,
        "league_adaptation": r,
        "form": r,
        "results_strength": None,
        "opponent_strength": None,
        "matches_count": 0,
    }


def create_all_initial_passports():
    db = FAJDatabase()
    manager = PassportManager(db=db)

    report = {
        "created": [],
        "existing": [],
        "errors": [],
    }

    for tournament, teams in get_all_ratings().items():
        try:
            season_id = get_or_create_season(db, tournament)
        except Exception as exc:
            report["errors"].append(f"{tournament}: ошибка сезона: {exc}")
            continue

        for team_name, start_rating in teams.items():
            try:
                team_id = get_or_create_team(db, tournament, team_name)

                current = manager.get_current_passport(
                    team_id=team_id,
                    season_id=season_id,
                )

                if current is not None:
                    report["existing"].append({
                        "tournament": tournament,
                        "team": team_name,
                        "version": current.get("version"),
                        "faj_rating": current.get("faj_rating"),
                    })
                    continue

                passport = manager.create_passport(
                    team_id=team_id,
                    season_id=season_id,
                    data=build_initial_passport(start_rating),
                    source="expert_start_rating",
                )

                if passport is None:
                    report["errors"].append(
                        f"{tournament} / {team_name}: паспорт не сохранён"
                    )
                    continue

                report["created"].append({
                    "tournament": tournament,
                    "team": team_name,
                    "version": passport.get("version"),
                    "start_rating": start_rating,
                    "faj_rating": passport.get("faj_rating"),
                    "passport_uuid": passport.get("passport_uuid"),
                })

            except Exception as exc:
                report["errors"].append(
                    f"{tournament} / {team_name}: {exc}"
                )

    return report


def main():
    st.set_page_config(
        page_title="FAJ — Стартовые паспорта",
        page_icon="🛂",
        layout="wide",
    )

    st.title("🛂 FAJ — Стартовые паспорта")
    st.caption(
        f"Сезон {FAJ_SEASON} | START_RATING → Passport v1.0"
    )

    total = sum(len(teams) for teams in FAJ_CLUB_RATINGS.values())

    st.info(
        f"В реестре FAJ: {total} команд. "
        "Будут созданы только отсутствующие паспорта v1.0."
    )

    st.warning(
        "⚠️ Повторный запуск безопасен: существующие паспорта не перезаписываются."
    )

    if st.button(
        "🚀 СОЗДАТЬ ВСЕ СТАРТОВЫЕ ПАСПОРТА",
        type="primary",
        use_container_width=True,
    ):
        with st.spinner("Создаю паспорта..."):
            report = create_all_initial_passports()

        st.success(
            f"Готово. Создано: {len(report['created'])}"
        )

        if report["created"]:
            st.subheader("Создано")
            st.dataframe(
                report["created"],
                use_container_width=True,
                hide_index=True,
            )

        if report["existing"]:
            st.subheader("Уже существовали — пропущены")
            st.dataframe(
                report["existing"],
                use_container_width=True,
                hide_index=True,
            )

        if report["errors"]:
            st.error(f"Ошибок: {len(report['errors'])}")
            for error in report["errors"]:
                st.write(f"❌ {error}")
        else:
            st.success("Ошибок нет.")


if __name__ == "__main__":
    main()
