#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
Initial Passport Creator v1.2

Создание стартовых паспортов v1.0.

Турниры:
- АПЛ — ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ (если faj_rating == 50)
- Ла Лига
- Лига чемпионов

РПЛ НЕ ТРОГАЕМ.
"""

import streamlit as st

from app.database import FAJDatabase
from app.faj_club_ratings import (
    FAJ_CLUB_RATINGS,
    FAJ_SEASON,
)
from app.passports.passport_manager import PassportManager


SEASON_YEAR = 2026

TARGET_TOURNAMENTS = [
    "АПЛ",
    "Ла Лига",
    "Лига чемпионов",
]

COMPETITION_TYPES = {
    "АПЛ": "league",
    "Ла Лига": "league",
    "Лига чемпионов": "cup",
}


def get_or_create_season(db, tournament):
    return db.create_season(
        name=FAJ_SEASON,
        league=tournament,
        year=SEASON_YEAR,
        competition_type=COMPETITION_TYPES[tournament],
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


def create_initial_passports():
    db = FAJDatabase()
    manager = PassportManager(db=db)

    report = {
        "created": [],
        "existing": [],
        "updated": [],      # ← НОВОЕ: пересозданные паспорта
        "errors": [],
    }

    for tournament in TARGET_TOURNAMENTS:

        teams = FAJ_CLUB_RATINGS.get(tournament, {})

        if not teams:
            report["errors"].append(
                f"{tournament}: турнир отсутствует в FAJ_CLUB_RATINGS"
            )
            continue

        # --------------------------------------------------------
        # SEASON
        # --------------------------------------------------------

        try:
            season_id = get_or_create_season(
                db,
                tournament,
            )

        except Exception as exc:
            report["errors"].append(
                f"{tournament}: ошибка создания сезона: {exc}"
            )
            continue

        # --------------------------------------------------------
        # TEAMS
        # --------------------------------------------------------

        for team_name, start_rating in teams.items():

            try:

                team_id = get_or_create_team(
                    db,
                    tournament,
                    team_name,
                )

                # ------------------------------------------------
                # CHECK EXISTING PASSPORT
                # ------------------------------------------------

                current = manager.get_current_passport(
                    team_id=team_id,
                    season_id=season_id,
                )

                # ================================================
                # АПЛ: ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ ЕСЛИ faj_rating == 50
                # ================================================
                if tournament == "АПЛ" and current is not None:
                    current_rating = current.get("faj_rating")
                    try:
                        current_rating = float(current_rating)
                    except (TypeError, ValueError):
                        current_rating = None

                    if current_rating == 50.0:
                        # Пересоздаём паспорт с правильным рейтингом
                        passport = manager.create_passport(
                            team_id=team_id,
                            season_id=season_id,
                            data=build_initial_passport(start_rating),
                            source="expert_start_rating_force_update",
                        )

                        if passport is None:
                            report["errors"].append(
                                f"{tournament} / {team_name}: "
                                "не удалось обновить паспорт"
                            )
                            continue

                        report["updated"].append({
                            "tournament": tournament,
                            "team": team_name,
                            "old_rating": current_rating,
                            "new_rating": start_rating,
                            "version": passport.get("version"),
                            "passport_uuid": passport.get("passport_uuid"),
                        })
                        continue

                # ------------------------------------------------
                # ПАСПОРТ УЖЕ СУЩЕСТВУЕТ
                # ------------------------------------------------

                if current is not None:
                    report["existing"].append({
                        "tournament": tournament,
                        "team": team_name,
                        "version": current.get("version"),
                        "faj_rating": current.get("faj_rating"),
                    })
                    continue

                # ------------------------------------------------
                # СОЗДАЁМ НОВЫЙ ПАСПОРТ
                # ------------------------------------------------

                passport = manager.create_passport(
                    team_id=team_id,
                    season_id=season_id,
                    data=build_initial_passport(start_rating),
                    source="expert_start_rating",
                )

                if passport is None:
                    report["errors"].append(
                        f"{tournament} / {team_name}: "
                        "паспорт не сохранён"
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
        f"Сезон {FAJ_SEASON} | "
        "START_RATING → Passport v1.0"
    )

    # ------------------------------------------------------------
    # TOTAL
    # ------------------------------------------------------------

    total = sum(
        len(FAJ_CLUB_RATINGS.get(tournament, {}))
        for tournament in TARGET_TOURNAMENTS
    )

    st.info(
        f"Будут обработаны {total} команд: "
        "АПЛ, Ла Лига и Лига чемпионов."
    )

    st.warning(
        "⚠️ АПЛ — принудительное обновление (если faj_rating == 50).\n\n"
        "РПЛ не изменяется. "
        "Существующие паспорта с правильным рейтингом не перезаписываются."
    )

    st.divider()

    # ------------------------------------------------------------
    # CREATE
    # ------------------------------------------------------------

    if st.button(
        "🚀 СОЗДАТЬ / ОБНОВИТЬ СТАРТОВЫЕ ПАСПОРТА",
        type="primary",
        use_container_width=True,
    ):

        with st.spinner(
            "Создаю стартовые паспорта..."
        ):

            report = create_initial_passports()

        # --------------------------------------------------------
        # RESULT
        # --------------------------------------------------------

        st.success(
            f"Готово. Создано: {len(report['created'])}, "
            f"Обновлено: {len(report['updated'])}"
        )

        if report["updated"]:

            st.subheader(
                f"🔄 Обновлено (АПЛ): {len(report['updated'])}"
            )

            st.dataframe(
                report["updated"],
                use_container_width=True,
                hide_index=True,
            )

        if report["created"]:

            st.subheader(
                f"✅ Создано: {len(report['created'])}"
            )

            st.dataframe(
                report["created"],
                use_container_width=True,
                hide_index=True,
            )

        if report["existing"]:

            st.subheader(
                f"ℹ️ Уже существовали (не трогали): "
                f"{len(report['existing'])}"
            )

            st.dataframe(
                report["existing"],
                use_container_width=True,
                hide_index=True,
            )

        if report["errors"]:

            st.subheader(
                f"❌ Ошибки: {len(report['errors'])}"
            )

            for error in report["errors"]:
                st.error(error)

        else:

            st.success(
                "Ошибок нет. "
                "Стартовые паспорта созданы корректно."
            )


if __name__ == "__main__":
    main()
