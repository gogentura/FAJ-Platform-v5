#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
Soccerway Stats Parser v1.1
============================================================

НАЗНАЧЕНИЕ:
    Универсальный парсер статистики матчей Soccerway.

ИСТОЧНИК:
    Soccerway

ПРИНЦИП:
    URL матча -> HTML -> структурированные данные -> FAJ

ВАЖНО:
    - Не ищем случайные числа по всей странице.
    - Счёт ищется отдельно.
    - Статистика ищется по названию показателя.
    - Невозможно определить значение -> None.
    - Подозрительное значение не принимается.
    - Парсер не изменяет БД.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

import requests
from bs4 import BeautifulSoup, Tag

from app.parsers.rpl_normalizer import normalize_team_names


logger = logging.getLogger(__name__)


class SoccerwayStatsParser:
    VERSION = "1.1"
    DEFAULT_TIMEOUT = 20

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 "
            "(KHTML, like Gecko) "
            "Chrome/128.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,image/avif,image/webp,"
            "*/*;q=0.8"
        ),
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    }

    # ========================================================
    # НАЗВАНИЯ СТАТИСТИКИ
    # ========================================================

    STAT_ALIASES = {
        "xg": [
            "xG",
            "Ожидаемые голы",
            "Expected Goals",
        ],
        "xgot": [
            "xGOT",
            "Ожидаемые голы после ударов в створ",
        ],
        "possession": [
            "Владение",
            "Владение мячом",
            "Possession",
        ],
        "shots": [
            "Удары",
            "Всего ударов",
            "Total shots",
            "Shots",
        ],
        "shots_on_target": [
            "Удары в створ",
            "Shots on target",
        ],
        "big_chances": [
            "Голевые моменты",
            "Большие моменты",
            "Big chances",
        ],
        "corners": [
            "Угловые",
            "Угловые удары",
            "Corners",
            "Corner kicks",
        ],
        "fouls": [
            "Фолы",
            "Нарушения",
            "Fouls",
        ],
        "yellow_cards": [
            "Жёлтые карточки",
            "Желтые карточки",
            "Yellow cards",
        ],
        "red_cards": [
            "Красные карточки",
            "Red cards",
        ],
        "offsides": [
            "Офсайды",
            "Положения вне игры",
            "Offsides",
        ],
        "goalkeeper_saves": [
            "Сэйвы",
            "Сейвы",
            "Спасения",
            "Saves",
        ],
        "goal_kicks": [
            "Удары от ворот",
            "Goal kicks",
        ],
        "clearances": [
            "Выносы",
            "Clearances",
        ],
        "interceptions": [
            "Перехваты",
            "Interceptions",
        ],
        "duels_won": [
            "Выиграно дуэлей",
            "Дуэли выиграны",
            "Duels won",
        ],
        "touches_penalty_area": [
            "Касания мяча в штрафной",
            "Touches in opposition box",
        ],
        "passes": [
            "Передачи",
            "Passes",
        ],
        "xA": [
            "xA",
            "Ожидаемые ассисты",
            "Expected assists",
        ],
    }

    # ========================================================
    # РЕЗУЛЬТАТЫ FAJ
    # ========================================================

    RESULT_KEYS = {
        "xg": ("home_xg", "away_xg"),
        "xgot": ("home_xgot", "away_xgot"),
        "possession": ("home_possession", "away_possession"),
        "shots": ("home_shots", "away_shots"),
        "shots_on_target": ("home_shots_on_target", "away_shots_on_target"),
        "big_chances": ("home_big_chances", "away_big_chances"),
        "corners": ("home_corners", "away_corners"),
        "fouls": ("home_fouls", "away_fouls"),
        "yellow_cards": ("home_yellow_cards", "away_yellow_cards"),
        "red_cards": ("home_red_cards", "away_red_cards"),
        "offsides": ("home_offsides", "away_offsides"),
        "goalkeeper_saves": ("home_goalkeeper_saves", "away_goalkeeper_saves"),
        "goal_kicks": ("home_goal_kicks", "away_goal_kicks"),
        "clearances": ("home_clearances", "away_clearances"),
        "interceptions": ("home_interceptions", "away_interceptions"),
        "duels_won": ("home_duels_won", "away_duels_won"),
        "touches_penalty_area": ("home_touches_penalty_area", "away_touches_penalty_area"),
        "passes": ("home_passes", "away_passes"),
        "xA": ("home_xa", "away_xa"),
    }

    # ========================================================
    # ДОПУСТИМЫЕ ДИАПАЗОНЫ
    # ========================================================

    VALID_RANGES = {
        "xg": (0.0, 10.0),
        "xgot": (0.0, 10.0),
        "possession": (0.0, 100.0),
        "shots": (0, 60),
        "shots_on_target": (0, 30),
        "big_chances": (0, 20),
        "corners": (0, 20),
        "fouls": (0, 50),
        "yellow_cards": (0, 15),
        "red_cards": (0, 5),
        "offsides": (0, 15),
        "goalkeeper_saves": (0, 20),
        "goal_kicks": (0, 30),
        "clearances": (0, 60),
        "interceptions": (0, 50),
        "duels_won": (0, 150),
        "touches_penalty_area": (0, 100),
        "passes": (0, 1500),
        "xA": (0.0, 10.0),
    }

    # ========================================================
    # INIT
    # ========================================================

    def __init__(self, timeout: int = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    # ========================================================
    # ПУБЛИЧНЫЙ МЕТОД
    # ========================================================

    def parse_match(self, url: str) -> Dict[str, Any]:
        result = self._empty_result()

        if not url:
            result["error"] = "URL is empty"
            return result

        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            result["source_url"] = url

            # ------------------------------------------------
            # КОМАНДЫ
            # ------------------------------------------------

            home, away = self._extract_teams(soup)
            if home or away:
                home, away = normalize_team_names(home, away, strict=False)

            result["home_team"] = home
            result["away_team"] = away

            # ------------------------------------------------
            # СЧЁТ
            # ------------------------------------------------

            score = self._extract_score(soup, home, away)
            if score:
                result["home_score"] = score[0]
                result["away_score"] = score[1]

            # ------------------------------------------------
            # СТАТИСТИКА
            # ------------------------------------------------

            stats = self._extract_statistics(soup)
            stats = self._validate_statistics(stats)
            result.update(stats)

            # ------------------------------------------------
            # СТАТУС
            # ------------------------------------------------

            result["status"] = self._extract_status(soup)
            result["success"] = True

            return result

        except requests.RequestException as exc:
            logger.error("Soccerway request error: %s", exc)
            result["error"] = str(exc)
            return result

        except Exception as exc:
            logger.exception("Soccerway parser error")
            result["error"] = str(exc)
            return result

    # ========================================================
    # ПУСТОЙ РЕЗУЛЬТАТ
    # ========================================================

    def _empty_result(self) -> Dict[str, Any]:
        result = {
            "success": False,
            "source_url": None,
            "home_team": None,
            "away_team": None,
            "home_score": None,
            "away_score": None,
            "status": None,
            "error": None,
        }

        for key in self.RESULT_KEYS.values():
            result[key[0]] = None
            result[key[1]] = None

        return result

    # ========================================================
    # КОМАНДЫ
    # ========================================================

    def _extract_teams(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        candidates = []

        # Сначала специальные классы
        selectors = [
            "[class*='team']",
            "[class*='Team']",
            "[class*='home']",
            "[class*='away']",
        ]

        for selector in selectors:
            for element in soup.select(selector):
                text = self._clean_text(element.get_text(" ", strip=True))
                if self._looks_like_team_name(text):
                    candidates.append(text)

        # Затем заголовки
        for element in soup.find_all(["h1", "h2", "h3"]):
            text = self._clean_text(element.get_text(" ", strip=True))
            if " - " in text:
                parts = text.split(" - ")
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()

        # Удаляем дубликаты
        unique = []
        for item in candidates:
            if item not in unique:
                unique.append(item)

        if len(unique) >= 2:
            return unique[0], unique[1]

        return None, None

    # ========================================================
    # СЧЁТ — ИСПРАВЛЕННАЯ ВЕРСИЯ
    # ========================================================

    def _extract_score(
        self,
        soup: BeautifulSoup,
        home: Optional[str],
        away: Optional[str],
    ) -> Optional[Tuple[int, int]]:
        """
        Безопасное извлечение счёта Soccerway.

        Приоритет:
            1. score/result блок
            2. заголовок страницы (h1-h4)
            3. title

        Никакого глобального поиска по всей странице.
        """

        # ========================================================
        # 1. SCORE / RESULT БЛОКИ
        # ========================================================

        selectors = [
            ".score",
            ".match-score",
            ".scoreboard",
            ".result",
            ".match-result",
            "[class*='score']",
            "[class*='Score']",
            "[class*='result']",
            "[class*='Result']",
        ]

        checked = set()

        for selector in selectors:
            for element in soup.select(selector):
                element_id = id(element)
                if element_id in checked:
                    continue
                checked.add(element_id)

                text = self._clean_text(element.get_text(" ", strip=True))
                score = self._parse_score(text)

                if score is None:
                    continue

                # Дополнительная проверка
                if self._reasonable_score(score):
                    return score

        # ========================================================
        # 2. ЗАГОЛОВКИ МАТЧА (h1-h4)
        # ========================================================

        for element in soup.find_all(["h1", "h2", "h3", "h4"]):
            text = self._clean_text(element.get_text(" ", strip=True))

            if not text:
                continue

            # Если известны команды — заголовок должен содержать ОБЕ
            if home and away:
                if not self._contains_team_pair(text, home, away):
                    continue

            score = self._parse_score(text)
            if score is not None and self._reasonable_score(score):
                return score

        # ========================================================
        # 3. TITLE
        # ========================================================

        title = soup.find("title")
        if title:
            text = self._clean_text(title.get_text(" ", strip=True))

            if home and away:
                if self._contains_team_pair(text, home, away):
                    score = self._parse_score(text)
                    if score is not None:
                        return score

        # ========================================================
        # 4. НИЧЕГО НАДЁЖНОГО НЕ НАШЛИ
        # ========================================================

        logger.warning("Soccerway: не удалось надёжно определить счёт")
        return None

    # ========================================================
    # ПАРСИНГ СЧЁТА — ИСПРАВЛЕННАЯ ВЕРСИЯ
    # ========================================================

    def _parse_score(self, text: str) -> Optional[Tuple[int, int]]:
        """
        Извлекает счёт только из короткого
        и явно похожего на результат текста.

        Поддерживает:
            0-0
            0 : 0
            1–2
            1 : 2
        """

        if not text:
            return None

        text = self._clean_text(text)

        # Защита от огромного текста страницы
        if len(text) > 250:
            return None

        # Нормализуем разные тире
        normalized = text.replace("–", "-").replace("—", "-").replace("−", "-")

        # --------------------------------------------------------
        # Основной формат Soccerway:
        #   Динамо Москва - Крылья Советов 0-0
        # --------------------------------------------------------

        patterns = [
            r"\b(\d{1,2})\s*-\s*(\d{1,2})\b",
            r"\b(\d{1,2})\s*:\s*(\d{1,2})\b",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, normalized)

            for home_score, away_score in matches:
                home_score = int(home_score)
                away_score = int(away_score)

                if 0 <= home_score <= 15 and 0 <= away_score <= 15:
                    return home_score, away_score

        return None

    # ========================================================
    # СТАТИСТИКА (НЕ ТРОГАЕМ)
    # ========================================================

    def _extract_statistics(self, soup: BeautifulSoup) -> Dict[str, Any]:
        result = {}

        # ----------------------------------------------------
        # 1. Таблицы
        # ----------------------------------------------------

        for table in soup.find_all("table"):
            for row in table.find_all("tr"):
                extracted = self._extract_stat_row(row)
                if extracted:
                    key, home_value, away_value = extracted
                    result[key] = (home_value, away_value)

        # ----------------------------------------------------
        # 2. DIV / блоки статистики
        # ----------------------------------------------------

        for element in soup.find_all(["div", "li", "section"]):
            extracted = self._extract_stat_block(element)
            if extracted:
                key, home_value, away_value = extracted
                if key not in result:
                    result[key] = (home_value, away_value)

        return self._flatten_statistics(result)

    def _extract_stat_row(self, row: Tag) -> Optional[Tuple[str, Any, Any]]:
        text = self._clean_text(row.get_text(" ", strip=True))
        key = self._identify_stat(text)

        if not key:
            return None

        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            return None

        values = []
        for cell in cells:
            value = self._parse_stat_value(cell.get_text(" ", strip=True))
            if value is not None:
                values.append(value)

        if len(values) < 2:
            return None

        return key, values[0], values[-1]

    def _extract_stat_block(self, element: Tag) -> Optional[Tuple[str, Any, Any]]:
        text = self._clean_text(element.get_text(" ", strip=True))

        if len(text) > 300:
            return None

        key = self._identify_stat(text)

        if not key:
            return None

        # Ищем дочерние элементы
        values = []
        for child in element.find_all(["span", "div", "strong", "b"]):
            value = self._parse_stat_value(child.get_text(" ", strip=True))
            if value is not None:
                values.append(value)

        if len(values) < 2:
            return None

        return key, values[0], values[-1]

    # ========================================================
    # ОПРЕДЕЛЕНИЕ ПОКАЗАТЕЛЯ
    # ========================================================

    def _identify_stat(self, text: str) -> Optional[str]:
        normalized = self._normalize_label(text)

        for key, aliases in self.STAT_ALIASES.items():
            for alias in aliases:
                alias_normalized = self._normalize_label(alias)
                if normalized == alias_normalized:
                    return key

        # Если строка содержит label + значения,
        # проверяем только начало/основную часть
        for key, aliases in self.STAT_ALIASES.items():
            for alias in aliases:
                alias_normalized = self._normalize_label(alias)
                if alias_normalized in normalized:
                    return key

        return None

    # ========================================================
    # ПАРСИНГ ЗНАЧЕНИЯ
    # ========================================================

    def _parse_stat_value(self, text: str) -> Optional[Any]:
        if not text:
            return None

        value = text.strip()

        # Передачи вида 453/539 (84%)
        match = re.fullmatch(r"(\d+)\s*/\s*(\d+)\s*(?:\(\s*\d+%\s*\))?", value)
        if match:
            return int(match.group(1))

        # Процент
        match = re.fullmatch(r"(\d+(?:[.,]\d+)?)\s*%", value)
        if match:
            return float(match.group(1).replace(",", "."))

        # Обычное число
        match = re.fullmatch(r"\d+(?:[.,]\d+)?", value)
        if match:
            number = float(value.replace(",", "."))
            if number.is_integer():
                return int(number)
            return number

        return None

    # ========================================================
    # ВАЛИДАЦИЯ
    # ========================================================

    def _validate_statistics(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        validated = {}

        for key, pair in stats.items():
            if not isinstance(pair, tuple):
                continue

            home_value, away_value = pair

            if not self._valid_value(key, home_value):
                home_value = None
            if not self._valid_value(key, away_value):
                away_value = None

            # Логические проверки
            if key == "shots_on_target":
                shots = stats.get("shots")
                if shots:
                    if home_value is not None and home_value > shots[0]:
                        home_value = None
                    if away_value is not None and away_value > shots[1]:
                        away_value = None

            validated[key] = (home_value, away_value)

        # Владение
        possession = validated.get("possession")
        if possession:
            home = possession[0]
            away = possession[1]
            if home is not None and away is not None and abs((home + away) - 100) > 3:
                logger.warning("Soccerway: invalid possession %s : %s", home, away)
                validated["possession"] = (None, None)

        return self._flatten_statistics(validated)

    def _valid_value(self, key: str, value: Any) -> bool:
        if value is None:
            return False

        rules = self.VALID_RANGES.get(key)
        if not rules:
            return True

        minimum, maximum = rules
        return minimum <= value <= maximum

    # ========================================================
    # FLATTEN
    # ========================================================

    def _flatten_statistics(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        result = {}

        for key, pair in stats.items():
            if key not in self.RESULT_KEYS:
                continue

            home_key, away_key = self.RESULT_KEYS[key]
            result[home_key] = pair[0]
            result[away_key] = pair[1]

        return result

    # ========================================================
    # STATUS
    # ========================================================

    def _extract_status(self, soup: BeautifulSoup) -> Optional[str]:
        text = self._clean_text(soup.get_text(" ", strip=True))

        if re.search(r"\b(завершен|завершён|finished|ft)\b", text, re.IGNORECASE):
            return "finished"

        if re.search(r"\b(live|в прямом эфире)\b", text, re.IGNORECASE):
            return "live"

        return None

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _clean_text(text: str) -> str:
        text = text.replace("\xa0", " ")
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _normalize_label(text: str) -> str:
        text = text.lower()
        text = text.replace("ё", "е")
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    @staticmethod
    def _reasonable_score(score: Tuple[int, int]) -> bool:
        home, away = score
        return 0 <= home <= 15 and 0 <= away <= 15

    @staticmethod
    def _contains_team_pair(text: str, home: str, away: str) -> bool:
        normalized = text.lower()
        return home.lower() in normalized and away.lower() in normalized

    @staticmethod
    def _looks_like_team_name(text: str) -> bool:
        if not text:
            return False

        if len(text) < 3 or len(text) > 80:
            return False

        # Командное название не должно быть просто числом/временем/датой
        if re.fullmatch(r"[\d\s:./-]+", text):
            return False

        return True


# ============================================================
# CONVENIENCE API
# ============================================================

def parse_soccerway_match(url: str) -> Dict[str, Any]:
    parser = SoccerwayStatsParser()
    return parser.parse_match(url)


# ============================================================
# ТЕСТ ИЗ КОМАНДНОЙ СТРОКИ
# ============================================================

if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("Usage:\npython soccerway_stats_parser.py <URL>")
        raise SystemExit(1)

    url = sys.argv[1]
    data = parse_soccerway_match(url)

    print(json.dumps(data, ensure_ascii=False, indent=2))
