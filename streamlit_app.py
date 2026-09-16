#!/usr/bin/env python3

-- coding: utf-8 --

"""
FAJ — Streamlit Interface

FAJ Brain prediction interface.

Архитектура:

Streamlit UI
    ↓
Soccer365Parser
    ↓
factual history (6 + 6)
    ↓
FAJBrain.predict()
    ↓
Brain result
    ↓
ТОЛЬКО ОТОБРАЖЕНИЕ

ВАЖНО:

Streamlit НЕ рассчитывает:

- xG
- λ
- Poisson
- 1X2
- BTTS
- totals
- exact scores
- confidence
- risk
- corners
- cards

Также НЕ используются:

- Pair Rating
- Winner Synthesis
- Winner Signal
- отдельная UI-математика

FAJBrain является единственным источником
математического прогноза.
"""

from future import annotations

import logging
import re
from datetime import date
from typing import Any, Dict, List, Optional

import streamlit as st

from app.parsers.soccer365_parser import Soccer365Parser
from app.core.faj_brain import FAJBrain
from app.core.form_context import build_form_context
from app.faj_club_ratings import (
get_all_tournaments,
get_all_teams,
get_team_rating,
)

============================================================

CONFIG

============================================================

PAGE_TITLE = "FAJ — Персональный прогноз"
PAGE_ICON = "⚽"
LAYOUT = "wide"

MAX_HISTORY_MATCHES = 6
MAX_ANALYSIS_MATCHES = 6

logger = logging.getLogger(name)

============================================================

SERVICES

============================================================

@st.cache_resource
def get_soccer365_parser() -> Soccer365Parser:
return Soccer365Parser()

@st.cache_resource
def get_faj_brain() -> FAJBrain:
return FAJBrain()

============================================================

HELPERS

============================================================

def normalize_name(value: Any) -> str:
if value is None:
return ""

return (
    str(value)
    .strip()
    .lower()
    .replace("ё", "е")
)

def safe_float(value: Any) -> Optional[float]:
if value is None:
return None

try:
    return float(value)
except (TypeError, ValueError):
    return None

def num(
value: Any,
digits: int = 2,
) -> str:
if value is None:
return "—"

try:
    return f"{float(value):.{digits}f}"
except (TypeError, ValueError):
    return "—"

def pct(value: Any) -> str:
if value is None:
return "—"

try:
    return f"{float(value):.1f}%"
except (TypeError, ValueError):
    return "—"

def probability_percent(value: Any) -> Optional[float]:
"""
Brain хранит вероятности как 0..100
в публичных prediction-полях.

Если значение оказалось 0..1, приводим
только для отображения.
"""
value = safe_float(value)

if value is None:
    return None

if 0.0 <= value <= 1.0:
    return value * 100.0

return value

def parse_score(
score: Any,
) -> tuple[Optional[int], Optional[int]]:

if not score:
    return None, None

text = (
    str(score)
    .strip()
    .replace("–", "-")
    .replace(":", "-")
)

parts = text.split("-")

if len(parts) != 2:
    return None, None

try:
    return (
        int(parts[0].strip()),
        int(parts[1].strip()),
    )
except ValueError:
    return None, None

def parse_date_value(
value: Any,
) -> Optional[date]:

if value is None:
    return None

text = str(value).strip()

match = re.search(
    r"(\d{4})-(\d{2})-(\d{2})",
    text,
)

if match:
    try:
        return date(
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
    except ValueError:
        return None

match = re.search(
    r"(\d{2})\.(\d{2})\.(\d{4})",
    text,
)

if match:
    try:
        return date(
            int(match.group(3)),
            int(match.group(2)),
            int(match.group(1)),
        )
    except ValueError:
        return None

return None

============================================================

SESSION STATE

============================================================

def init_state() -> None:

defaults = {
    "faj_competition": None,
    "faj_matches": [],
    "faj_collected": {},
    "faj_predictions": {},
    "faj_form_context": {},
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

def reset_workspace() -> None:

st.session_state.faj_competition = None
st.session_state.faj_matches = []
st.session_state.faj_collected = {}
st.session_state.faj_predictions = {}
st.session_state.faj_form_context = {}

def create_match_slot() -> Dict[str, Any]:

return {
    "home_name": None,
    "away_name": None,
    "match_date": date.today().isoformat(),
    "urls_home": [""] * MAX_HISTORY_MATCHES,
    "urls_away": [""] * MAX_HISTORY_MATCHES,
}

def add_match() -> None:

if (
    len(st.session_state.faj_matches)
    >= MAX_ANALYSIS_MATCHES
):
    st.warning(
        f"Можно добавить максимум "
        f"{MAX_ANALYSIS_MATCHES} матчей."
    )
    return

st.session_state.faj_matches.append(
    create_match_slot()
)

def remove_match(index: int) -> None:

if not (
    0 <= index
    < len(st.session_state.faj_matches)
):
    return

st.session_state.faj_matches.pop(index)

st.session_state.faj_collected.pop(
    index,
    None,
)

st.session_state.faj_predictions.pop(
    index,
    None,
)

st.session_state.faj_form_context.pop(
    index,
    None,
)

============================================================

TEAM SOURCE

============================================================

def load_teams(
league: Optional[str] = None,
) -> List[str]:

try:
    teams = get_all_teams(league)

    return list(teams) if teams else []

except Exception:
    logger.exception(
        "Ошибка загрузки команд"
    )
    return []

============================================================

SOCCER365

============================================================

def parse_soccer365(
url: str,
) -> Dict[str, Any]:

parser = get_soccer365_parser()

return parser.parse(
    url.strip()
)

============================================================

FACTUAL HISTORY RECORD

============================================================

def build_history_record(
parsed: Dict[str, Any],
) -> Dict[str, Any]:

stats = parsed.get(
    "stats",
    {},
)

if not isinstance(stats, dict):
    stats = {}

home_goals, away_goals = parse_score(
    parsed.get("score")
)

return {
    "home_team": parsed.get("home_team"),
    "away_team": parsed.get("away_team"),
    "match_date": parsed.get("match_date"),
    "score": parsed.get("score"),

    "home_goals": home_goals,
    "away_goals": away_goals,

    "xg": {
        "home": stats.get("home_xg"),
        "away": stats.get("away_xg"),
    },

    "shots": {
        "home": stats.get("home_shots"),
        "away": stats.get("away_shots"),
    },

    "shots_on_target": {
        "home": stats.get(
            "home_shots_on_target"
        ),
        "away": stats.get(
            "away_shots_on_target"
        ),
    },

    "blocked_shots": {
        "home": stats.get(
            "home_blocked_shots"
        ),
        "away": stats.get(
            "away_blocked_shots"
        ),
    },

    "big_chances": {
        "home": stats.get(
            "home_big_chances"
        ),
        "away": stats.get(
            "away_big_chances"
        ),
    },

    "possession": {
        "home": stats.get(
            "home_possession"
        ),
        "away": stats.get(
            "away_possession"
        ),
    },

    "passes": {
        "home": stats.get(
            "home_total_passes"
        ),
        "away": stats.get(
            "away_total_passes"
        ),
    },

    "pass_accuracy": {
        "home": stats.get(
            "home_pass_accuracy"
        ),
        "away": stats.get(
            "away_pass_accuracy"
        ),
    },

    "crosses": {
        "home": stats.get("home_crosses"),
        "away": stats.get("away_crosses"),
    },

    "throw_ins": {
        "home": stats.get("home_throw_ins"),
        "away": stats.get("away_throw_ins"),
    },

    "fouls": {
        "home": stats.get("home_fouls"),
        "away": stats.get("away_fouls"),
    },

    "offsides": {
        "home": stats.get("home_offsides"),
        "away": stats.get("away_offsides"),
    },

    "yellow_cards": {
        "home": stats.get(
            "home_yellow_cards"
        ),
        "away": stats.get(
            "away_yellow_cards"
        ),
    },

    "red_cards": {
        "home": stats.get(
            "home_red_cards"
        ),
        "away": stats.get(
            "away_red_cards"
        ),
    },

    "corners": {
        "home": stats.get("home_corners"),
        "away": stats.get("away_corners"),
    },

    "home_corners": stats.get(
        "home_corners"
    ),

    "away_corners": stats.get(
        "away_corners"
    ),

    "home_yellow_cards": stats.get(
        "home_yellow_cards"
    ),

    "away_yellow_cards": stats.get(
        "away_yellow_cards"
    ),

    "stats": dict(stats),

    "source_url": parsed.get(
        "source_url"
    ),

    "quality": parsed.get(
        "quality",
        parsed.get("data_quality"),
    ),

    "source": "Soccer365",

    "parser_version": parsed.get(
        "parser_version"
    ),
}

============================================================

MATCH VALIDATION

============================================================

def validate_parsed_match(
parsed: Dict[str, Any],
selected_team: str,
) -> tuple[bool, str]:

home = parsed.get("home_team")
away = parsed.get("away_team")

if not home or not away:
    return (
        False,
        "Не удалось определить команды.",
    )

target = normalize_name(
    selected_team
)

if (
    target != normalize_name(home)
    and target != normalize_name(away)
):
    return (
        False,
        f"Матч {home} — {away} "
        f"не содержит {selected_team}.",
    )

return (
    True,
    f"{home} — {away}",
)

============================================================

COLLECT HISTORY

============================================================

def collect_team_history(
team_name: str,
urls: List[str],
forecast_date: Optional[str] = None,
) -> tuple[
List[Dict[str, Any]],
List[str],
]:

clean_urls = [
    url.strip()
    for url in urls
    if url and url.strip()
]

clean_urls = list(
    dict.fromkeys(clean_urls)
)

records: List[Dict[str, Any]] = []
errors: List[str] = []

forecast_date_obj = (
    parse_date_value(forecast_date)
    if forecast_date
    else None
)

if (
    forecast_date
    and not forecast_date_obj
):
    errors.append(
        f"Некорректная дата "
        f"прогноза: {forecast_date}"
    )
    return records, errors

for position, url in enumerate(
    clean_urls,
    start=1,
):

    try:
        parsed = parse_soccer365(url)

    except Exception as exc:
        errors.append(
            f"{position}. {exc}"
        )
        continue

    if parsed.get("error"):
        errors.append(
            f"{position}. "
            f"{parsed.get('error')}"
        )
        continue

    valid, message = validate_parsed_match(
        parsed,
        team_name,
    )

    if not valid:
        errors.append(
            f"{position}. {message}"
        )
        continue

    record = build_history_record(
        parsed
    )

    record["team"] = team_name
    record["team_name"] = team_name

    if (
        normalize_name(
            parsed.get("home_team")
        )
        == normalize_name(team_name)
    ):
        record["is_home"] = True
        record["venue"] = "home"

    elif (
        normalize_name(
            parsed.get("away_team")
        )
        == normalize_name(team_name)
    ):
        record["is_home"] = False
        record["venue"] = "away"

    else:
        errors.append(
            f"{position}. "
            f"Не удалось определить "
            f"сторону {team_name}."
        )
        continue

    match_date = record.get(
        "match_date"
    )

    if not match_date:
        errors.append(
            f"{position}. "
            f"Не удалось определить "
            f"дату матча."
        )
        continue

    match_date_obj = parse_date_value(
        match_date
    )

    if not match_date_obj:
        errors.append(
            f"{position}. "
            f"Некорректная дата: "
            f"{match_date}"
        )
        continue

    if (
        forecast_date_obj
        and match_date_obj >= forecast_date_obj
    ):
        errors.append(
            f"{position}. "
            f"Матч от {match_date} "
            f"не является прошлым "
            f"относительно "
            f"{forecast_date}."
        )
        continue

    records.append(record)

# FormContext получает историю
# oldest → newest.
records.sort(
    key=lambda item: (
        parse_date_value(
            item.get("match_date")
        )
        or date.min
    )
)

records = records[
    -MAX_HISTORY_MATCHES:
]

return records, errors

============================================================

FORM CONTEXT

============================================================

def make_form_context(
team_name: str,
records: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:

if not records:
    return None

try:
    context = build_form_context(
        team_name=team_name,
        records=records,
        limit=MAX_HISTORY_MATCHES,
    )

    if isinstance(context, dict):
        return context

    if hasattr(context, "__dict__"):
        return vars(context)

    return None

except Exception:
    logger.exception(
        "Ошибка построения FormContext"
    )
    return None

============================================================

BRAIN

============================================================

def build_prediction(
home_team: str,
away_team: str,
history_home: List[Dict[str, Any]],
history_away: List[Dict[str, Any]],
) -> Dict[str, Any]:

brain = get_faj_brain()

result = brain.predict(
    home_team=home_team,
    away_team=away_team,
    home_matches=history_home,
    away_matches=history_away,
)

if hasattr(result, "to_dict"):
    prediction = result.to_dict()

elif isinstance(result, dict):
    prediction = dict(result)

else:
    raise TypeError(
        "FAJBrain.predict() "
        "вернул неподдерживаемый тип."
    )

if not isinstance(prediction, dict):
    raise TypeError(
        "FAJBrain result должен быть dict."
    )

return prediction

============================================================

COLLECT

============================================================

def collect_and_store_match(
index: int,
match: Dict[str, Any],
) -> None:

home_team = match.get("home_name")
away_team = match.get("away_name")

if not home_team or not away_team:
    st.error(
        "Сначала выберите обе команды."
    )
    return

forecast_date = match.get(
    "match_date"
)

with st.spinner(
    "Собираю 6 последних матчей..."
):

    home_records, home_errors = (
        collect_team_history(
            home_team,
            match.get(
                "urls_home",
                [],
            ),
            forecast_date,
        )
    )

    away_records, away_errors = (
        collect_team_history(
            away_team,
            match.get(
                "urls_away",
                [],
            ),
            forecast_date,
        )
    )

errors = [
    f"{home_team}: {error}"
    for error in home_errors
]

errors.extend(
    f"{away_team}: {error}"
    for error in away_errors
)

st.session_state.faj_collected[index] = {
    "home_records": home_records,
    "away_records": away_records,
    "errors": errors,
}

st.session_state.faj_form_context[index] = {
    "home": make_form_context(
        home_team,
        home_records,
    ),
    "away": make_form_context(
        away_team,
        away_records,
    ),
}

if home_records and away_records:
    st.success(
        "История успешно собрана."
    )
else:
    st.warning(
        "История собрана не полностью."
    )

============================================================

PREDICTION

============================================================

def generate_prediction(
index: int,
match: Dict[str, Any],
) -> None:

home_team = match.get("home_name")
away_team = match.get("away_name")

if not home_team or not away_team:
    st.error(
        "Сначала выберите обе команды."
    )
    return

collected = (
    st.session_state
    .faj_collected
    .get(index)
)

if not collected:
    collect_and_store_match(
        index,
        match,
    )

    collected = (
        st.session_state
        .faj_collected
        .get(index)
    )

if not collected:
    st.error(
        "Не удалось собрать историю."
    )
    return

history_home = collected.get(
    "home_records",
    [],
)

history_away = collected.get(
    "away_records",
    [],
)

if not history_home:
    st.error(
        f"Нет истории для {home_team}."
    )
    return

if not history_away:
    st.error(
        f"Нет истории для {away_team}."
    )
    return

with st.spinner(
    "FAJ Brain анализирует матч..."
):

    try:
        prediction = build_prediction(
            home_team=home_team,
            away_team=away_team,
            history_home=history_home,
            history_away=history_away,
        )

    except Exception as exc:
        logger.exception(
            "Ошибка FAJ Brain"
        )

        st.error(
            f"Ошибка получения прогноза: "
            f"{exc}"
        )
        return

st.session_state.faj_predictions[index] = (
    prediction
)

st.success(
    "FAJ Brain сформировал прогноз."
)

============================================================

DATA SUMMARY

============================================================

def render_data_summary(
team_name: str,
records: List[Dict[str, Any]],
) -> None:

if not records:
    return

goals_for = []
goals_against = []
corners = []
cards = []
xg_values = []
xga_values = []

for record in records:

    is_home = (
        normalize_name(
            record.get("home_team")
        )
        == normalize_name(team_name)
    )

    if is_home:
        gf = record.get("home_goals")
        ga = record.get("away_goals")
        corner = record.get("home_corners")
        card = record.get("home_yellow_cards")

        xg = (
            record.get("xg", {})
            .get("home")
        )

        xga = (
            record.get("xg", {})
            .get("away")
        )

    else:
        gf = record.get("away_goals")
        ga = record.get("home_goals")
        corner = record.get("away_corners")
        card = record.get("away_yellow_cards")

        xg = (
            record.get("xg", {})
            .get("away")
        )

        xga = (
            record.get("xg", {})
            .get("home")
        )

    if gf is not None:
        goals_for.append(gf)

    if ga is not None:
        goals_against.append(ga)

    if corner is not None:
        corners.append(corner)

    if card is not None:
        cards.append(card)

    if xg is not None:
        xg_values.append(xg)

    if xga is not None:
        xga_values.append(xga)

def avg(
    values: List[Any],
) -> Optional[float]:

    if not values:
        return None

    return sum(values) / len(values)

st.markdown(
    f"**{team_name} — последние "
    f"{len(records)} матчей**"
)

c1, c2, c3, c4, c5, c6 = st.columns(6)

with c1:
    st.metric(
        "Матчей",
        len(records),
    )

with c2:
    st.metric(
        "Голы",
        num(avg(goals_for)),
    )

with c3:
    st.metric(
        "Пропущено",
        num(avg(goals_against)),
    )

with c4:
    st.metric(
        "xG",
        num(avg(xg_values)),
    )

with c5:
    st.metric(
        "Угловые",
        num(avg(corners)),
    )

with c6:
    st.metric(
        "Карточки",
        num(avg(cards)),
    )

============================================================

FORM CONTEXT

============================================================

def render_form_context_card(
home_team: str,
away_team: str,
home_context: Optional[Dict[str, Any]],
away_context: Optional[Dict[str, Any]],
) -> None:

if not home_context and not away_context:
    return

st.markdown(
    "### 📊 Форма перед матчем"
)

c1, c2 = st.columns(2)

def format_form(
    context: Optional[Dict[str, Any]],
) -> str:

    if not isinstance(context, dict):
        return "—"

    form = context.get("form")

    if isinstance(form, str):
        return form.strip() or "—"

    if isinstance(form, (list, tuple)):

        mapping = {
            "W": "В",
            "WIN": "В",
            "D": "Н",
            "DRAW": "Н",
            "L": "П",
            "LOSS": "П",
        }

        values = []

        for item in form[:6]:
            value = (
                str(item)
                .strip()
                .upper()
            )

            values.append(
                mapping.get(
                    value,
                    value,
                )
            )

        return (
            "-".join(values)
            if values
            else "—"
        )

    return "—"

def render_team_context(
    team_name: str,
    context: Optional[Dict[str, Any]],
) -> None:

    st.markdown(
        f"**{team_name}**"
    )

    if not isinstance(context, dict):
        st.write("Нет данных.")
        return

    st.write(
        f"Форма: "
        f"{format_form(context)}"
    )

    st.write(
        f"Средний xG: "
        f"{num(context.get('xg'))}"
    )

    st.write(
        f"Средний xGA: "
        f"{num(context.get('xga'))}"
    )

    st.write(
        f"Голы: "
        f"{num(context.get('goals_for_avg'))}"
    )

    st.write(
        f"Пропущено: "
        f"{num(context.get('goals_against_avg'))}"
    )

    st.write(
        f"Угловые: "
        f"{num(context.get('corners_for_avg'))}"
    )

    st.write(
        f"Карточки: "
        f"{num(context.get('team_cards_avg'))}"
    )

with c1:
    render_team_context(
        f"🏠 {home_team}",
        home_context,
    )

with c2:
    render_team_context(
        f"✈️ {away_team}",
        away_context,
    )

============================================================

SCORE DISPLAY

============================================================

def render_scores(
prediction: Dict[str, Any],
) -> None:

st.subheader(
    "3. Наиболее вероятные точные счета"
)

primary = prediction.get(
    "predicted_score"
)

second = prediction.get(
    "second_score"
)

third = prediction.get(
    "third_score"
)

top_scores = prediction.get(
    "top_scores"
)

if not primary and isinstance(
    top_scores,
    list,
):
    if top_scores:
        first = top_scores[0]

        if isinstance(first, dict):
            primary = first.get("score")

if primary:
    st.markdown(
        f"### 🎯 Основной счёт: {primary}"
    )

cols = st.columns(3)

with cols[0]:
    st.metric(
        "1-й",
        primary or "—",
    )

with cols[1]:
    st.metric(
        "2-й",
        second or "—",
    )

with cols[2]:
    st.metric(
        "3-й",
        third or "—",
    )

if isinstance(top_scores, list):
    with st.expander(
        "Полное распределение top scores"
    ):
        for item in top_scores[:10]:

            if isinstance(item, dict):

                score = item.get("score")
                probability = (
                    item.get("probability")
                )

                if probability is not None:
                    probability = (
                        probability_percent(
                            probability
                        )
                    )

                st.write(
                    f"{score or '—'}"
                    f" — "
                    f"{pct(probability)}"
                )

            else:
                st.write(item)

============================================================

PREDICTION CARD

============================================================

def render_prediction_card(
prediction: Dict[str, Any],
) -> None:

home = prediction.get(
    "home_team",
    "Хозяева",
)

away = prediction.get(
    "away_team",
    "Гости",
)

st.markdown("---")

st.markdown(
    f"## ⚽ {home} — {away}"
)

# ========================================================
# 1X2
# ========================================================

st.subheader(
    "1. Главный исход"
)

c1, c2, c3 = st.columns(3)

home_win = probability_percent(
    prediction.get(
        "home_win_probability"
    )
)

draw = probability_percent(
    prediction.get(
        "draw_probability"
    )
)

away_win = probability_percent(
    prediction.get(
        "away_win_probability"
    )
)

with c1:
    st.metric(
        f"🏠 {home}",
        pct(home_win),
    )

with c2:
    st.metric(
        "🤝 Ничья",
        pct(draw),
    )

with c3:
    st.metric(
        f"✈️ {away}",
        pct(away_win),
    )

# ========================================================
# CONFIDENCE / RISK
# ========================================================

confidence = probability_percent(
    prediction.get("confidence")
)

risk = prediction.get(
    "risk"
)

c1, c2 = st.columns(2)

with c1:
    st.metric(
        "Уверенность FAJ",
        pct(confidence),
    )

with c2:
    st.metric(
        "Риск",
        risk if risk else "—",
    )

# ========================================================
# GOALS
# ========================================================

st.subheader(
    "2. Голы"
)

c1, c2 = st.columns(2)

with c1:
    st.metric(
        f"🏠 {home} xG",
        num(
            prediction.get(
                "home_xg"
            )
        ),
    )

with c2:
    st.metric(
        f"✈️ {away} xG",
        num(
            prediction.get(
                "away_xg"
            )
        ),
    )

btts = probability_percent(
    prediction.get(
        "btts_probability"
    )
)

over15 = probability_percent(
    prediction.get(
        "over15_probability"
    )
)

over25 = probability_percent(
    prediction.get(
        "over25_probability"
    )
)

over35 = probability_percent(
    prediction.get(
        "over35_probability"
    )
)

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric(
        "Обе забьют",
        pct(btts),
    )

with c2:
    st.metric(
        "ТБ 1.5",
        pct(over15),
    )

with c3:
    st.metric(
        "ТБ 2.5",
        pct(over25),
    )

with c4:
    st.metric(
        "ТБ 3.5",
        pct(over35),
    )

# ========================================================
# SCORES
# ========================================================

render_scores(prediction)

# ========================================================
# CORNERS
# ========================================================

st.subheader(
    "4. Угловые"
)

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "Всего",
        num(
            prediction.get(
                "corners_expected"
            )
        ),
    )

with c2:
    st.metric(
        home,
        num(
            prediction.get(
                "home_corners_expected"
            )
        ),
    )

with c3:
    st.metric(
        away,
        num(
            prediction.get(
                "away_corners_expected"
            )
        ),
    )

# ========================================================
# CARDS
# ========================================================

st.subheader(
    "5. Карточки"
)

c1, c2, c3 = st.columns(3)

with c1:
    st.metric(
        "Всего",
        num(
            prediction.get(
                "cards_expected"
            )
        ),
    )

with c2:
    st.metric(
        home,
        num(
            prediction.get(
                "home_cards_expected"
            )
        ),
    )

with c3:
    st.metric(
        away,
        num(
            prediction.get(
                "away_cards_expected"
            )
        ),
    )

# ========================================================
# CONCLUSION
# ========================================================

st.subheader(
    "6. Аналитический вывод FAJ"
)

conclusion = prediction.get(
    "conclusion"
)

if conclusion:
    st.info(conclusion)
else:
    st.info(
        "FAJ Brain пока не сформировал "
        "текстовый аналитический вывод."
    )

# ========================================================
# DIAGNOSTICS
# ========================================================

diagnostics = prediction.get(
    "diagnostics"
)

if diagnostics:

    with st.expander(
        "🔍 Диагностика FAJ Brain"
    ):
        st.json(diagnostics)

calculation_meta = prediction.get(
    "calculation_meta"
)

if calculation_meta:

    with st.expander(
        "🧮 Calculation Meta"
    ):
        st.json(calculation_meta)

============================================================

MATCH SETUP

============================================================

def render_match_setup(
index: int,
match: Dict[str, Any],
team_names: List[str],
) -> None:

st.markdown(
    f"### Матч {index + 1}"
)

if len(team_names) < 2:
    st.warning(
        "В выбранном турнире "
        "нужно минимум две команды."
    )
    return

# ========================================================
# TEAMS
# ========================================================

home_current = (
    match.get("home_name")
    or team_names[0]
)

if home_current not in team_names:
    home_current = team_names[0]

away_options = [
    name
    for name in team_names
    if name != home_current
]

away_current = (
    match.get("away_name")
    or away_options[0]
)

if away_current not in away_options:
    away_current = away_options[0]

c1, c2 = st.columns(2)

with c1:
    selected_home = st.selectbox(
        "🏠 Хозяева",
        team_names,
        index=team_names.index(
            home_current
        ),
        key=f"home_{index}",
    )

with c2:

    available_away = [
        name
        for name in team_names
        if name != selected_home
    ]

    if not available_away:
        st.error(
            "Нет доступной команды соперника."
        )
        return

    selected_away = st.selectbox(
        "✈️ Гости",
        available_away,
        index=(
            available_away.index(
                away_current
            )
            if away_current in available_away
            else 0
        ),
        key=f"away_{index}",
    )

match["home_name"] = selected_home
match["away_name"] = selected_away

# ========================================================
# CLUB RATING — DISPLAY ONLY
# ========================================================

st.markdown(
    "#### ⭐ FAJ Club Rating"
)

club_c1, club_c2 = st.columns(2)

with club_c1:

    rating = get_team_rating(
        selected_home,
        st.session_state.faj_competition,
    )

    st.metric(
        f"🏠 {selected_home}",
        rating if rating is not None else "—",
    )

with club_c2:

    rating = get_team_rating(
        selected_away,
        st.session_state.faj_competition,
    )

    st.metric(
        f"✈️ {selected_away}",
        rating if rating is not None else "—",
    )

st.caption(
    "Club Rating — справочная информация. "
    "В этот прогноз UI его не подмешивает."
)

# ========================================================
# DATE
# ========================================================

current_date = match.get(
    "match_date"
)

try:
    default_date = (
        date.fromisoformat(current_date)
        if current_date
        else date.today()
    )

except (TypeError, ValueError):
    default_date = date.today()

forecast_date = st.date_input(
    "📅 Дата матча",
    value=default_date,
    key=f"date_{index}",
)

match["match_date"] = (
    forecast_date.isoformat()
)

# ========================================================
# SOCCER365 URLS
# ========================================================

st.markdown(
    "#### 🔗 Последние 6 матчей Soccer365"
)

col_home, col_away = st.columns(2)

with col_home:

    st.markdown(
        f"**🏠 {selected_home}**"
    )

    for i in range(
        MAX_HISTORY_MATCHES
    ):

        match["urls_home"][i] = (
            st.text_input(
                f"Матч {i + 1}",
                value=match[
                    "urls_home"
                ][i],
                key=(
                    f"home_url_"
                    f"{index}_{i}"
                ),
                placeholder=(
                    "https://soccer365.ru/games/..."
                ),
            )
        )

with col_away:

    st.markdown(
        f"**✈️ {selected_away}**"
    )

    for i in range(
        MAX_HISTORY_MATCHES
    ):

        match["urls_away"][i] = (
            st.text_input(
                f"Матч {i + 1}",
                value=match[
                    "urls_away"
                ][i],
                key=(
                    f"away_url_"
                    f"{index}_{i}"
                ),
                placeholder=(
                    "https://soccer365.ru/games/..."
                ),
            )
        )

# ========================================================
# BUTTONS
# ========================================================

c1, c2 = st.columns(2)

with c1:

    if st.button(
        "📥 Собрать статистику",
        key=f"collect_{index}",
        width="stretch",
    ):

        collect_and_store_match(
            index,
            match,
        )

with c2:

    if st.button(
        "🧠 Получить прогноз",
        key=f"predict_{index}",
        width="stretch",
    ):

        generate_prediction(
            index,
            match,
        )

# ========================================================
# COLLECTED DATA
# ========================================================

collected = (
    st.session_state
    .faj_collected
    .get(index)
)

if collected:

    home_records = collected.get(
        "home_records",
        [],
    )

    away_records = collected.get(
        "away_records",
        [],
    )

    st.success(
        f"Собрано: "
        f"{len(home_records)} матчей "
        f"{selected_home}; "
        f"{len(away_records)} матчей "
        f"{selected_away}."
    )

    c1, c2 = st.columns(2)

    with c1:
        render_data_summary(
            selected_home,
            home_records,
        )

    with c2:
        render_data_summary(
            selected_away,
            away_records,
        )

    errors = collected.get(
        "errors",
        [],
    )

    if errors:

        with st.expander(
            "⚠️ Сообщения сбора"
        ):

            for error in errors:
                st.warning(error)

# ========================================================
# FORM
# ========================================================

form_data = (
    st.session_state
    .faj_form_context
    .get(index)
)

if form_data:

    render_form_context_card(
        selected_home,
        selected_away,
        form_data.get("home"),
        form_data.get("away"),
    )

# ========================================================
# PREDICTION
# ========================================================

prediction = (
    st.session_state
    .faj_predictions
    .get(index)
)

if prediction:
    render_prediction_card(
        prediction
    )

# ========================================================
# REMOVE
# ========================================================

if len(
    st.session_state.faj_matches
) > 1:

    if st.button(
        "🗑 Удалить матч",
        key=f"remove_{index}",
    ):

        remove_match(index)
        st.rerun()

============================================================

MAIN

============================================================

def main() -> None:

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon=PAGE_ICON,
    layout=LAYOUT,
)

init_state()

st.title(
    "⚽ FAJ Personal Prediction Brain"
)

st.caption(
    "6 последних матчей каждой команды → "
    "FAJ Brain → прогноз"
)

# ========================================================
# TOP CONTROLS
# ========================================================

c1, c2 = st.columns([3, 1])

with c1:

    tournaments = get_all_tournaments()

    current_competition = (
        st.session_state.faj_competition
    )

    if (
        current_competition not in tournaments
    ):
        current_competition = (
            tournaments[0]
            if tournaments
            else None
        )

    selected_competition = st.selectbox(
        "🏆 Турнир",
        tournaments,
        index=(
            tournaments.index(
                current_competition
            )
            if current_competition
            in tournaments
            else 0
        ),
    )

    if (
        selected_competition
        != st.session_state.faj_competition
    ):

        st.session_state.faj_competition = (
            selected_competition
        )

        st.session_state.faj_matches = []
        st.session_state.faj_collected = {}
        st.session_state.faj_predictions = {}
        st.session_state.faj_form_context = {}

with c2:

    if st.button(
        "🔄 Сбросить",
        width="stretch",
    ):

        reset_workspace()
        st.rerun()

# ========================================================
# TEAMS
# ========================================================

team_names = load_teams(
    st.session_state.faj_competition
)

if not team_names:

    st.error(
        "В выбранном турнире "
        "нет команд в FAJ Club Ratings."
    )

    return

# ========================================================
# FIRST MATCH
# ========================================================

if not st.session_state.faj_matches:

    st.session_state.faj_matches.append(
        create_match_slot()
    )

# ========================================================
# MATCHES
# ========================================================

for index, match in enumerate(
    list(
        st.session_state.faj_matches
    )
):

    with st.container(border=True):

        render_match_setup(
            index=index,
            match=match,
            team_names=team_names,
        )

# ========================================================
# ADD MATCH
# ========================================================

st.markdown("---")

if (
    len(st.session_state.faj_matches)
    < MAX_ANALYSIS_MATCHES
):

    if st.button(
        "➕ Добавить матч",
        width="stretch",
    ):

        add_match()
        st.rerun()

st.caption(
    f"Матчей: "
    f"{len(st.session_state.faj_matches)} / "
    f"{MAX_ANALYSIS_MATCHES}"
)

if name == "main":
main()
