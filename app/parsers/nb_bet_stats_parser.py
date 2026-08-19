#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
NB-BET Stats Parser v5.0

Назначение:
    Только чтение статистики матча с NB-BET.

ВАЖНО:
    Итоговый счёт НЕ парсится.
    Счёт вводится оператором вручную в интерфейсе FAJ.
    Parser не изменяет SQLite и не изменяет прогнозы.

Источник статистики:
    pageSoccerEvent.match["17"][0]

Поддерживаемые показатели:
    - possession
    - corners
    - shots
    - shots_on_target
    - xg
    - total_passes
    - pass_accuracy
    - accurate_passes
    - tackles

Если отдельный показатель невозможно безопасно определить:
    его значение = None.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class NbBetStatsParser:
    """Безопасный парсер статистики NB-BET без извлечения счёта."""

    VERSION = "5.0-nb-bet-stats-only"
    SOURCE = "nb-bet"
    DEFAULT_TIMEOUT = 20

    STAT_MAP = {
        1: "possession",
        5: "corners",
        7: "shots",
        8: "shots_on_target",
        21: "xg",
        22: "total_passes",
        23: "pass_accuracy",
        39: "accurate_passes",
        46: "tackles",
    }

    RESULT_KEYS = {
        "possession": ("home_possession", "away_possession"),
        "corners": ("home_corners", "away_corners"),
        "shots": ("home_shots", "away_shots"),
        "shots_on_target": (
            "home_shots_on_target",
            "away_shots_on_target",
        ),
        "xg": ("home_xg", "away_xg"),
        "total_passes": (
            "home_total_passes",
            "away_total_passes",
        ),
        "pass_accuracy": (
            "home_pass_accuracy",
            "away_pass_accuracy",
        ),
        "accurate_passes": (
            "home_accurate_passes",
            "away_accurate_passes",
        ),
        "tackles": ("home_tackles", "away_tackles"),
    }

    LIMITS = {
        "possession": (0, 100),
        "corners": (0, 30),
        "shots": (0, 80),
        "shots_on_target": (0, 50),
        "xg": (0.0, 10.0),
        "total_passes": (0, 1500),
        "pass_accuracy": (0, 100),
        "accurate_passes": (0, 1500),
        "tackles": (0, 100),
    }

    TEAM_PAIRS = (
        ("homeTeam", "awayTeam"),
        ("home_team", "away_team"),
        ("homeTeamName", "awayTeamName"),
        ("home_team_name", "away_team_name"),
        ("homeName", "awayName"),
        ("home_name", "away_name"),
    )

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/128.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Referer": "https://nb-bet.com/",
            }
        )

    # ========================================================
    # PUBLIC API
    # ========================================================

    def parse(self, url: str) -> Dict[str, Any]:
        """Загрузить URL и вернуть только статистику матча."""
        result = self._empty_result(url)

        if not url:
            result["error"] = "empty_url"
            return result

        if "nb-bet.com" not in url.lower():
            logger.warning("NB-BET parser получил чужой URL: %s", url)
            result["error"] = "invalid_source"
            return result

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = response.encoding or "utf-8"

            html = response.text
            soup = BeautifulSoup(html, "html.parser")

            event_data = self._extract_event_data(soup)

            # Основной путь: структурированный pageSoccerEvent.
            stats = self._extract_nb_bet_stats(event_data)

            # Команды нужны только для идентификации строки,
            # но счёт здесь принципиально отсутствует.
            home_team, away_team = self._extract_teams(
                soup=soup,
                event_data=event_data,
            )

            # Если JSON не найден, пробуем HTML статистику.
            if not stats:
                stats = self._extract_stats_from_html(soup)

            stats = self._validate_stats(stats)

            result["home_team"] = home_team
            result["away_team"] = away_team
            result["stats"] = stats
            result["stats_count"] = sum(v is not None for v in stats.values())
            result["success"] = result["stats_count"] > 0
            result["data_quality"] = self._calculate_quality(result)

            if not result["success"]:
                result["error"] = "statistics_not_found"
                logger.warning(
                    "NB-BET: статистика не найдена: %s",
                    url,
                )

            return result

        except requests.RequestException as exc:
            result["error"] = "request_error"
            result["error_message"] = str(exc)
            logger.error("NB-BET request error: %s", exc)
            return result

        except Exception as exc:
            result["error"] = "parser_error"
            result["error_message"] = str(exc)
            logger.exception("NB-BET parser error: %s", exc)
            return result

    def parse_match_page(self, url: str) -> Dict[str, Any]:
        return self.parse(url)

    # ========================================================
    # RESULT
    # ========================================================

    def _empty_result(self, url: str) -> Dict[str, Any]:
        return {
            "success": False,
            "source": self.SOURCE,
            "parser_version": self.VERSION,
            "url": url,
            "home_team": None,
            "away_team": None,
            # Счёта здесь НЕТ намеренно.
            "stats": {},
            "stats_count": 0,
            "data_quality": 0.0,
            "error": None,
            "error_message": None,
        }

    # ========================================================
    # EVENT JSON
    # ========================================================

    def _extract_event_data(
        self,
        soup: BeautifulSoup,
    ) -> Optional[Dict[str, Any]]:
        for index, script in enumerate(soup.find_all("script")):
            text = script.string or script.get_text()
            if not text or "pageSoccerEvent" not in text:
                continue

            data = self._parse_page_soccer_event(text)
            if data is not None:
                logger.info(
                    "NB-BET: pageSoccerEvent найден в script #%s",
                    index,
                )
                return data

            logger.warning(
                "NB-BET: pageSoccerEvent найден, но JSON не разобран"
            )

        return None

    def _parse_page_soccer_event(
        self,
        text: str,
    ) -> Optional[Dict[str, Any]]:
        marker = "pageSoccerEvent"
        position = text.find(marker)
        if position < 0:
            return None

        start = text.find("{", position)
        if start >= 0:
            json_text = self._extract_balanced_object(text, start)
            if json_text:
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    pass

        # Иногда удобнее найти непосредственно объект match.
        match_pos = text.find('"match"', position)
        if match_pos < 0:
            match_pos = text.find("match", position)
        if match_pos < 0:
            return None

        match_start = text.find("{", match_pos)
        if match_start < 0:
            return None

        match_text = self._extract_balanced_object(text, match_start)
        if not match_text:
            return None

        try:
            return {"match": json.loads(match_text)}
        except json.JSONDecodeError:
            return None

    def _extract_balanced_object(
        self,
        text: str,
        start: int,
    ) -> Optional[str]:
        depth = 0
        in_string = False
        escaped = False

        for index in range(start, len(text)):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        return None

    # ========================================================
    # TEAMS
    # ========================================================

    def _extract_teams(
        self,
        soup: BeautifulSoup,
        event_data: Optional[Dict[str, Any]],
    ) -> Tuple[Optional[str], Optional[str]]:
        pair = self._find_teams_in_json(event_data)
        if pair:
            return self._normalize_pair(*pair)

        # Fallback: заголовки страницы. Счёт намеренно отбрасывается.
        candidates = []
        for element in soup.find_all(["h1", "h2", "h3"]):
            text = self._clean(element.get_text(" ", strip=True))
            if text:
                candidates.append(text)
        if soup.title:
            candidates.append(self._clean(soup.title.get_text(" ", strip=True)))

        separators = (" — ", " – ", " - ", " vs ", " VS ", " против ")
        for text in candidates:
            for separator in separators:
                if separator not in text:
                    continue
                left, right = text.split(separator, 1)
                # Убираем счёт из правой части заголовка.
                right = self._strip_score_suffix(right)
                pair = self._normalize_pair(left, right)
                if pair:
                    return pair

        return None, None

    def _find_teams_in_json(
        self,
        data: Any,
    ) -> Optional[Tuple[str, str]]:
        if isinstance(data, dict):
            for home_key, away_key in self.TEAM_PAIRS:
                if home_key in data and away_key in data:
                    home = self._team_value(data[home_key])
                    away = self._team_value(data[away_key])
                    if home and away:
                        return home, away

            # NB-BET фактическая структура: match["7"]["1"] и match["8"]["1"]
            match = data.get("match")
            if isinstance(match, dict):
                home = match.get("7", match.get(7))
                away = match.get("8", match.get(8))
                if isinstance(home, dict) and isinstance(away, dict):
                    home_name = self._team_value(
                        home.get("1", home.get(1))
                    )
                    away_name = self._team_value(
                        away.get("1", away.get(1))
                    )
                    if home_name and away_name:
                        return home_name, away_name

            for value in data.values():
                pair = self._find_teams_in_json(value)
                if pair:
                    return pair

        elif isinstance(data, list):
            for value in data:
                pair = self._find_teams_in_json(value)
                if pair:
                    return pair

        return None

    def _team_value(self, value: Any) -> Optional[str]:
        if isinstance(value, str):
            return self._clean(value)
        if isinstance(value, dict):
            for key in ("name", "teamName", "team_name", "title"):
                if key in value:
                    candidate = self._team_value(value[key])
                    if candidate:
                        return candidate
        return None

    def _normalize_pair(
        self,
        home: Any,
        away: Any,
    ) -> Optional[Tuple[str, str]]:
        home = self._clean(str(home))
        away = self._clean(str(away))
        if not home or not away:
            return None

        try:
            from app.parsers.rpl_normalizer import normalize_team_names

            normalized_home, normalized_away = normalize_team_names(
                home,
                away,
                strict=True,
            )
            if normalized_home and normalized_away:
                return normalized_home, normalized_away
        except Exception as exc:
            logger.debug("NB-BET team normalizer failed: %s", exc)

        return None

    # ========================================================
    # JSON STATS
    # ========================================================

    def _extract_nb_bet_stats(
        self,
        event_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not isinstance(event_data, dict):
            return {}

        match = event_data.get("match")
        if not isinstance(match, dict):
            return {}

        stats_block = match.get("17")
        if stats_block is None:
            stats_block = match.get(17)
        if not isinstance(stats_block, list) or not stats_block:
            return {}

        first = stats_block[0]
        if not isinstance(first, dict):
            return {}

        result: Dict[str, Any] = {}

        for raw_key, raw_value in first.items():
            try:
                key = int(raw_key)
            except (TypeError, ValueError):
                continue

            stat_name = self.STAT_MAP.get(key)
            if not stat_name:
                continue

            pair = self._extract_pair(raw_value)
            if pair is None:
                continue

            home, away = pair
            home_key, away_key = self.RESULT_KEYS[stat_name]
            result[home_key] = home
            result[away_key] = away

        return result

    def _extract_pair(
        self,
        value: Any,
    ) -> Optional[Tuple[Any, Any]]:
        if not isinstance(value, (list, tuple)) or len(value) < 2:
            return None
        return value[0], value[1]

    # ========================================================
    # HTML FALLBACK STATS
    # ========================================================

    def _extract_stats_from_html(
        self,
        soup: BeautifulSoup,
    ) -> Dict[str, Any]:
        """Fallback по текстовым labels, без зависимости от hash-классов."""
        result: Dict[str, Any] = {}

        label_map = {
            "Ожидаемые голы (xG)": "xg",
            "xG": "xg",
            "Удары": "shots",
            "Удары в створ": "shots_on_target",
            "Угловые": "corners",
            "Владение мячом (%)": "possession",
            "Владение": "possession",
            "Всего передач": "total_passes",
            "Передачи": "total_passes",
            "Точность передач": "pass_accuracy",
            "Точные передачи": "accurate_passes",
            "Отборы": "tackles",
        }

        for label_element in soup.find_all(string=True):
            label = self._clean(str(label_element))
            stat_type = label_map.get(label)
            if not stat_type:
                continue

            parent = label_element.parent
            if parent is None:
                continue

            container = parent.parent
            if container is None:
                continue

            values = self._numeric_values_in_element(container)
            if len(values) < 2:
                continue

            home_key, away_key = self.RESULT_KEYS[stat_type]
            result[home_key] = values[-2]
            result[away_key] = values[-1]

        return result

    def _numeric_values_in_element(self, element: Any) -> list[Any]:
        values = []
        for node in element.find_all("div"):
            text = self._clean(node.get_text(" ", strip=True))
            if not text or len(text) > 20:
                continue
            value = self._parse_numeric(text)
            if value is not None:
                values.append(value)
        return values

    def _parse_numeric(self, text: str) -> Optional[Any]:
        text = text.replace("%", "").replace(",", ".").strip()
        if not text:
            return None
        try:
            value = float(text)
        except (TypeError, ValueError):
            return None
        if value.is_integer():
            return int(value)
        return value

    # ========================================================
    # VALIDATION
    # ========================================================

    def _validate_stats(
        self,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        result: Dict[str, Any] = {}

        for key, value in stats.items():
            stat_type = None
            for name, keys in self.RESULT_KEYS.items():
                if key in keys:
                    stat_type = name
                    break
            if stat_type is None:
                continue
            result[key] = self._validate_value(stat_type, value)

        self._invalidate_relation(
            result,
            "home_shots_on_target",
            "home_shots",
        )
        self._invalidate_relation(
            result,
            "away_shots_on_target",
            "away_shots",
        )

        hp = result.get("home_possession")
        ap = result.get("away_possession")
        if hp is not None and ap is not None and not 98 <= hp + ap <= 102:
            logger.warning(
                "NB-BET: invalid possession %s + %s",
                hp,
                ap,
            )
            result["home_possession"] = None
            result["away_possession"] = None

        for side in ("home", "away"):
            total = result.get(f"{side}_total_passes")
            accurate = result.get(f"{side}_accurate_passes")
            if total is not None and accurate is not None and accurate > total:
                result[f"{side}_total_passes"] = None
                result[f"{side}_accurate_passes"] = None

        return result

    def _validate_value(
        self,
        stat_type: str,
        value: Any,
    ) -> Optional[Any]:
        try:
            value = float(value) if stat_type == "xg" else int(value)
        except (TypeError, ValueError):
            return None

        minimum, maximum = self.LIMITS[stat_type]
        if not minimum <= value <= maximum:
            return None
        return value

    def _invalidate_relation(
        self,
        stats: Dict[str, Any],
        smaller_key: str,
        larger_key: str,
    ) -> None:
        smaller = stats.get(smaller_key)
        larger = stats.get(larger_key)
        if smaller is not None and larger is not None and smaller > larger:
            stats[smaller_key] = None
            stats[larger_key] = None

    # ========================================================
    # QUALITY
    # ========================================================

    def _calculate_quality(self, result: Dict[str, Any]) -> float:
        """Качество статистики, а не качество счёта."""
        expected = len(self.STAT_MAP) * 2
        actual = result.get("stats_count", 0)
        if expected <= 0:
            return 0.0
        return round(min(actual / expected, 1.0), 2)

    # ========================================================
    # HELPERS
    # ========================================================

    def _strip_score_suffix(self, text: str) -> str:
        # Примеры: "Крылья Советов 0-0", "Крылья Советов 0 : 0"
        return __import__("re").sub(
            r"\s+\d{1,2}\s*[:\-]\s*\d{1,2}\s*$",
            "",
            text,
        ).strip()

    def _clean(self, text: str) -> str:
        if not text:
            return ""
        text = text.replace("\xa0", " ")
        import re
        text = re.sub(r"\s+", " ", text)
        return text.strip()


# ============================================================
# CONVENIENCE
# ============================================================

def parse_match_stats(url: str) -> Dict[str, Any]:
    return NbBetStatsParser().parse_match_page(url)


# ============================================================
# SELF TEST
# ============================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(message)s",
    )

    if len(sys.argv) < 2:
        print(
            "Usage: python app/parsers/nb_bet_stats_parser.py <NB-BET URL>"
        )
        raise SystemExit(1)

    parser = NbBetStatsParser()
    result = parser.parse(sys.argv[1])

    print("=" * 70)
    print(f"FAJ NB-BET STATS PARSER v{parser.VERSION}")
    print("=" * 70)
    print("Success:", result["success"])
    print("Source:", result["source"])
    print("Home:", result["home_team"])
    print("Away:", result["away_team"])
    print("Score: вводится вручную в FAJ")
    print("Quality:", result["data_quality"])
    print("Error:", result["error"])
    if result["error_message"]:
        print("Error message:", result["error_message"])
    print("\nStats:")
    for key, value in result["stats"].items():
        print(f"  {key}: {value}")
    print("=" * 70)
