#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
===========================================================
FAJ Platform v12.1
RPL Results Parser
===========================================================

Назначение:
    Загрузка фактических результатов матчей РПЛ.

Источники:
    - smart-tables.ru
    - championat.com
    - soccerland.ru

Роль:
    Этот модуль НЕ записывает данные непосредственно в БД.

    Он:
        1. получает страницы источников;
        2. извлекает матчи;
        3. определяет тур;
        4. определяет дату;
        5. определяет команды;
        6. извлекает счёт;
        7. нормализует названия команд;
        8. возвращает единый формат.

Принцип:
    Parser -> normalized data -> load_all.py -> database.py

Важно:
    Парсер не удаляет существующие данные.
    Парсер не делает DELETE.
    Парсер не создаёт паспорта.
    Парсер не рассчитывает прогнозы.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from app.parsers.rpl_normalizer import normalize_team_names


logger = logging.getLogger(__name__)


class RPLResultsParser:
    """
    Универсальный парсер результатов РПЛ.

    Основная задача:
        получить фактические результаты матчей
        за указанный диапазон туров.

    Источники используются последовательно:
        1. Smart Tables
        2. Championat
        3. Soccerland

    Если один источник не дал данные, парсер
    продолжает работу с другим.
    """

    SOURCE_URLS = {
        "smart_tables": (
            "https://smart-tables.ru/league/"
            "Russia/Premier_League"
        ),
        "championat": (
            "https://www.championat.com/football/"
            "_russiapl/tournament/6594/calendar/"
        ),
        "soccerland": (
            "https://soccerland.ru/russia/"
            "premier-liga/2026-2027"
        ),
    }

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        timeout: int = 20,
        request_delay: float = 0.5,
    ) -> None:

        self.timeout = timeout
        self.request_delay = request_delay

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": self.USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,image/avif,"
                    "image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
            }
        )

    # =========================================================
    # PUBLIC API
    # =========================================================

    def parse(
        self,
        start_round: int = 1,
        end_round: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Загружает результаты РПЛ.

        Возвращает список нормализованных матчей.

        Каждый матч имеет формат:

        {
            "round": 1,
            "date": "2026-07-17",
            "home_team": "ЦСКА",
            "away_team": "Балтика",
            "home_goals": 2,
            "away_goals": 0,
            "status": "finished",
            "source": "...",
            "source_url": "...",
            "parser": "rpl_results_parser",
            "parser_version": "1.0"
        }
        """

        if start_round < 1:
            start_round = 1

        if end_round < start_round:
            end_round = start_round

        logger.info(
            "RPL Results Parser: туры %s-%s",
            start_round,
            end_round,
        )

        all_matches: List[Dict[str, Any]] = []

        # -----------------------------------------------------
        # 1. CHAMPIONAT
        # -----------------------------------------------------

        championat_matches = self._parse_championat(
            self.SOURCE_URLS["championat"],
            start_round,
            end_round,
        )

        all_matches.extend(championat_matches)

        logger.info(
            "Championat: получено %s матчей",
            len(championat_matches),
        )

        # -----------------------------------------------------
        # 2. SMART TABLES
        # -----------------------------------------------------

        smart_matches = self._parse_smart_tables(
            self.SOURCE_URLS["smart_tables"],
            start_round,
            end_round,
        )

        all_matches.extend(smart_matches)

        logger.info(
            "Smart Tables: получено %s матчей",
            len(smart_matches),
        )

        # -----------------------------------------------------
        # 3. SOCCERLAND
        # -----------------------------------------------------

        soccerland_matches = self._parse_soccerland(
            self.SOURCE_URLS["soccerland"],
            start_round,
            end_round,
        )

        all_matches.extend(soccerland_matches)

        logger.info(
            "Soccerland: получено %s матчей",
            len(soccerland_matches),
        )

        # -----------------------------------------------------
        # 4. ОБЪЕДИНЕНИЕ
        # -----------------------------------------------------

        merged = self._merge_sources(all_matches)

        # -----------------------------------------------------
        # 5. ФИЛЬТРАЦИЯ ПО ТУРАМ
        # -----------------------------------------------------

        result = [
            match
            for match in merged
            if start_round
            <= int(match.get("round", 0))
            <= end_round
        ]

        result.sort(
            key=lambda x: (
                int(x.get("round", 0)),
                x.get("date") or "",
                x.get("home_team") or "",
            )
        )

        logger.info(
            "Итого после объединения: %s матчей",
            len(result),
        )

        return result

    # =========================================================
    # CHAMPIONAT
    # =========================================================

    def _parse_championat(
        self,
        url: str,
        start_round: int,
        end_round: int,
    ) -> List[Dict[str, Any]]:

        html = self._get(url)

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")

        matches: List[Dict[str, Any]] = []

        current_round: Optional[int] = None

        # -----------------------------------------------------
        # Ищем потенциальные блоки календаря
        # -----------------------------------------------------

        containers = soup.find_all(
            ["div", "section", "table", "tr"]
        )

        for container in containers:

            text = self._clean_text(
                container.get_text(" ", strip=True)
            )

            if not text:
                continue

            # -------------------------------------------------
            # Определение тура
            # -------------------------------------------------

            round_match = re.search(
                r"(?:Тур|тур)\s*(\d{1,2})",
                text,
            )

            if round_match:

                try:
                    detected_round = int(
                        round_match.group(1)
                    )

                    if (
                        start_round
                        <= detected_round
                        <= end_round
                    ):
                        current_round = detected_round

                except ValueError:
                    pass

            # -------------------------------------------------
            # Если тур неизвестен — пропускаем
            # -------------------------------------------------

            if current_round is None:
                continue

            # -------------------------------------------------
            # Пытаемся найти счёт
            # -------------------------------------------------

            score = self._extract_score(text)

            if score is None:
                continue

            home_goals, away_goals = score

            # -------------------------------------------------
            # Команды
            # -------------------------------------------------

            teams = self._extract_teams_from_text(text)

            if not teams:
                continue

            home_team, away_team = teams

            # -------------------------------------------------
            # Дата
            # -------------------------------------------------

            date = self._extract_date(text)

            match = self._build_match(
                round_number=current_round,
                date=date,
                home_team=home_team,
                away_team=away_team,
                home_goals=home_goals,
                away_goals=away_goals,
                source="championat.com",
                source_url=url,
            )

            if match:
                matches.append(match)

        return self._deduplicate(matches)

    # =========================================================
    # SMART TABLES
    # =========================================================

    def _parse_smart_tables(
        self,
        url: str,
        start_round: int,
        end_round: int,
    ) -> List[Dict[str, Any]]:

        html = self._get(url)

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")

        matches: List[Dict[str, Any]] = []

        # -----------------------------------------------------
        # Smart Tables может использовать таблицы.
        # Работаем сначала с <tr>.
        # -----------------------------------------------------

        rows = soup.find_all("tr")

        current_round: Optional[int] = None

        for row in rows:

            text = self._clean_text(
                row.get_text(" ", strip=True)
            )

            if not text:
                continue

            # -------------------------------------------------
            # Тур
            # -------------------------------------------------

            round_match = re.search(
                r"(?:тур|Тур|round|Round)\s*(\d{1,2})",
                text,
            )

            if round_match:

                try:
                    current_round = int(
                        round_match.group(1)
                    )
                except ValueError:
                    pass

            # -------------------------------------------------
            # Иногда номер тура находится отдельной ячейкой
            # -------------------------------------------------

            if current_round is None:

                numbers = re.findall(
                    r"\b([1-9]|[12]\d|30)\b",
                    text,
                )

                if numbers:

                    possible_round = int(numbers[0])

                    if (
                        start_round
                        <= possible_round
                        <= end_round
                    ):
                        current_round = possible_round

            if current_round is None:
                continue

            if not (
                start_round
                <= current_round
                <= end_round
            ):
                continue

            # -------------------------------------------------
            # Счёт
            # -------------------------------------------------

            score = self._extract_score(text)

            if score is None:
                continue

            home_goals, away_goals = score

            # -------------------------------------------------
            # Команды
            # -------------------------------------------------

            teams = self._extract_teams_from_text(text)

            if not teams:
                continue

            home_team, away_team = teams

            date = self._extract_date(text)

            match = self._build_match(
                round_number=current_round,
                date=date,
                home_team=home_team,
                away_team=away_team,
                home_goals=home_goals,
                away_goals=away_goals,
                source="smart-tables.ru",
                source_url=url,
            )

            if match:
                matches.append(match)

        # -----------------------------------------------------
        # Если таблиц нет — пробуем общий текст.
        # -----------------------------------------------------

        if not matches:

            matches = self._generic_html_parser(
                soup,
                url,
                start_round,
                end_round,
                source="smart-tables.ru",
            )

        return self._deduplicate(matches)

    # =========================================================
    # SOCCERLAND
    # =========================================================

    def _parse_soccerland(
        self,
        url: str,
        start_round: int,
        end_round: int,
    ) -> List[Dict[str, Any]]:

        html = self._get(url)

        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")

        matches: List[Dict[str, Any]] = []

        # -----------------------------------------------------
        # Сначала ищем элементы, содержащие счёт.
        # -----------------------------------------------------

        elements = soup.find_all(
            ["div", "li", "tr", "article"]
        )

        current_round: Optional[int] = None

        for element in elements:

            text = self._clean_text(
                element.get_text(" ", strip=True)
            )

            if not text:
                continue

            # -------------------------------------------------
            # Тур
            # -------------------------------------------------

            round_match = re.search(
                r"(?:тур|Тур|round|Round)\s*(\d{1,2})",
                text,
            )

            if round_match:

                try:
                    current_round = int(
                        round_match.group(1)
                    )
                except ValueError:
                    pass

            if current_round is None:
                continue

            if not (
                start_round
                <= current_round
                <= end_round
            ):
                continue

            score = self._extract_score(text)

            if score is None:
                continue

            home_goals, away_goals = score

            teams = self._extract_teams_from_text(text)

            if not teams:
                continue

            home_team, away_team = teams

            date = self._extract_date(text)

            match = self._build_match(
                round_number=current_round,
                date=date,
                home_team=home_team,
                away_team=away_team,
                home_goals=home_goals,
                away_goals=away_goals,
                source="soccerland.ru",
                source_url=url,
            )

            if match:
                matches.append(match)

        if not matches:

            matches = self._generic_html_parser(
                soup,
                url,
                start_round,
                end_round,
                source="soccerland.ru",
            )

        return self._deduplicate(matches)

    # =========================================================
    # GENERIC HTML PARSER
    # =========================================================

    def _generic_html_parser(
        self,
        soup: BeautifulSoup,
        url: str,
        start_round: int,
        end_round: int,
        source: str,
    ) -> List[Dict[str, Any]]:

        matches: List[Dict[str, Any]] = []

        text_blocks = soup.find_all(
            ["div", "li", "tr", "p"]
        )

        current_round: Optional[int] = None

        for block in text_blocks:

            text = self._clean_text(
                block.get_text(" ", strip=True)
            )

            if not text:
                continue

            # Тур
            round_match = re.search(
                r"(?:Тур|тур|Round|round)\s*(\d{1,2})",
                text,
            )

            if round_match:

                try:
                    current_round = int(
                        round_match.group(1)
                    )
                except ValueError:
                    pass

            if current_round is None:
                continue

            if not (
                start_round
                <= current_round
                <= end_round
            ):
                continue

            score = self._extract_score(text)

            if score is None:
                continue

            teams = self._extract_teams_from_text(text)

            if not teams:
                continue

            date = self._extract_date(text)

            match = self._build_match(
                round_number=current_round,
                date=date,
                home_team=teams[0],
                away_team=teams[1],
                home_goals=score[0],
                away_goals=score[1],
                source=source,
                source_url=url,
            )

            if match:
                matches.append(match)

        return self._deduplicate(matches)

    # =========================================================
    # MATCH EXTRACTION
    # =========================================================

    def _extract_score(
        self,
        text: str,
    ) -> Optional[tuple]:

        if not text:
            return None

        # 2:1
        patterns = [
            r"\b(\d{1,2})\s*[:\-]\s*(\d{1,2})\b",
            r"\b(\d{1,2})\s*:\s*(\d{1,2})\b",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
            )

            if not match:
                continue

            try:
                home = int(match.group(1))
                away = int(match.group(2))

                # Защита от случайных дат.
                if home > 15 or away > 15:
                    continue

                return home, away

            except ValueError:
                continue

        return None

    def _extract_date(
        self,
        text: str,
    ) -> Optional[str]:

        if not text:
            return None

        # DD.MM.YYYY
        match = re.search(
            r"\b(\d{2})\.(\d{2})\.(\d{4})\b",
            text,
        )

        if match:

            day, month, year = match.groups()

            try:
                dt = datetime(
                    int(year),
                    int(month),
                    int(day),
                )

                return dt.strftime("%Y-%m-%d")

            except ValueError:
                pass

        # YYYY-MM-DD
        match = re.search(
            r"\b(2026|2027)-(\d{2})-(\d{2})\b",
            text,
        )

        if match:

            try:

                year, month, day = match.groups()

                dt = datetime(
                    int(year),
                    int(month),
                    int(day),
                )

                return dt.strftime("%Y-%m-%d")

            except ValueError:
                pass

        return None

    def _extract_teams_from_text(
        self,
        text: str,
    ) -> Optional[tuple]:

        if not text:
            return None

        # -----------------------------------------------------
        # Список известных названий.
        #
        # Здесь специально допускаются варианты.
        # Нормализатор затем приведёт их к одному имени.
        # -----------------------------------------------------

        known_teams = [
            "Динамо Махачкала",
            "Динамо (Махачкала)",
            "Динамо-Махачкала",
            "Динамо Мх",

            "Динамо Москва",
            "Динамо (Москва)",
            "Динамо-Москва",
            "Динамо М",

            "Крылья Советов",
            "Крылья Советов Самара",

            "Спартак Москва",
            "Спартак-Москва",
            "Спартак",

            "Зенит Санкт-Петербург",
            "Зенит",

            "ЦСКА Москва",
            "ПФК ЦСКА",
            "ЦСКА",

            "Локомотив Москва",
            "Локомотив",

            "Краснодар",
            "Ростов",

            "Ахмат Грозный",
            "Ахмат",

            "Рубин Казань",
            "Рубин",

            "Оренбург",

            "Факел Воронеж",
            "Факел",

            "Акрон Тольятти",
            "Акрон",

            "Балтика Калининград",
            "Балтика",

            "Родина Москва",
            "Родина",
        ]

        # -----------------------------------------------------
        # Сначала ищем длинные названия.
        # -----------------------------------------------------

        found: List[tuple] = []

        for team in sorted(
            known_teams,
            key=len,
            reverse=True,
        ):

            pattern = (
                r"(?<!\w)"
                + re.escape(team)
                + r"(?!\w)"
            )

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:

                start = match.start()

                # Не дублируем одно и то же место.
                duplicate = False

                for existing_team, existing_start in found:

                    if abs(
                        start - existing_start
                    ) < 2:
                        duplicate = True
                        break

                if not duplicate:
                    found.append(
                        (team, start)
                    )

        if len(found) < 2:
            return None

        # -----------------------------------------------------
        # Сортировка по позиции в тексте.
        # -----------------------------------------------------

        found.sort(
            key=lambda x: x[1]
        )

        home_team = found[0][0]
        away_team = found[1][0]

        # -----------------------------------------------------
        # Нормализация.
        # -----------------------------------------------------

        home_team, away_team = normalize_team_names(
            home_team,
            away_team,
        )

        if home_team == away_team:
            return None

        return home_team, away_team

    # =========================================================
    # BUILD MATCH
    # =========================================================

    def _build_match(
        self,
        round_number: int,
        date: Optional[str],
        home_team: str,
        away_team: str,
        home_goals: int,
        away_goals: int,
        source: str,
        source_url: str,
    ) -> Optional[Dict[str, Any]]:

        if not home_team or not away_team:
            return None

        if home_team == away_team:
            return None

        home_team, away_team = normalize_team_names(
            home_team,
            away_team,
        )

        return {
            "round": int(round_number),
            "date": date,
            "home_team": home_team,
            "away_team": away_team,
            "home_goals": int(home_goals),
            "away_goals": int(away_goals),
            "status": "finished",
            "source": source,
            "source_url": source_url,
            "parser": "rpl_results_parser",
            "parser_version": "1.0",
            "parsed_at": datetime.now().isoformat(),
        }

    # =========================================================
    # SOURCE MERGE
    # =========================================================

    def _merge_sources(
        self,
        matches: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        unique: Dict[str, Dict[str, Any]] = {}

        for match in matches:

            key = self._match_key(match)

            if not key:
                continue

            if key not in unique:

                unique[key] = match

            else:

                unique[key] = self._merge_match_data(
                    unique[key],
                    match,
                )

        return list(unique.values())

    def _merge_match_data(
        self,
        first: Dict[str, Any],
        second: Dict[str, Any],
    ) -> Dict[str, Any]:

        result = dict(first)

        # -----------------------------------------------------
        # Если первый источник не дал дату,
        # используем второй.
        # -----------------------------------------------------

        if not result.get("date") and second.get("date"):
            result["date"] = second["date"]

        # -----------------------------------------------------
        # Если первый источник дал нулевой счёт,
        # но второй дал нормальный — используем второй.
        # -----------------------------------------------------

        first_score = (
            result.get("home_goals"),
            result.get("away_goals"),
        )

        second_score = (
            second.get("home_goals"),
            second.get("away_goals"),
        )

        if (
            first_score == (0, 0)
            and second_score != (0, 0)
        ):
            result["home_goals"] = second[
                "home_goals"
            ]
            result["away_goals"] = second[
                "away_goals"
            ]

        # -----------------------------------------------------
        # Сохраняем сведения об источниках.
        # -----------------------------------------------------

        sources = []

        for source in (
            result.get("sources"),
            [result.get("source")],
            [second.get("source")],
            second.get("sources"),
        ):

            if not source:
                continue

            if isinstance(source, str):
                source = [source]

            for item in source:

                if item and item not in sources:
                    sources.append(item)

        result["sources"] = sources

        return result

    # =========================================================
    # DEDUPLICATION
    # =========================================================

    def _deduplicate(
        self,
        matches: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        unique: Dict[str, Dict[str, Any]] = {}

        for match in matches:

            key = self._match_key(match)

            if key:
                unique[key] = match

        return list(unique.values())

    def _match_key(
        self,
        match: Dict[str, Any],
    ) -> Optional[str]:

        try:

            round_number = int(
                match.get("round", 0)
            )

            home = normalize_team_names(
                match.get("home_team"),
                match.get("away_team"),
            )[0]

            away = normalize_team_names(
                match.get("home_team"),
                match.get("away_team"),
            )[1]

            if not home or not away:
                return None

            return (
                f"{round_number}|"
                f"{home}|"
                f"{away}"
            )

        except Exception:
            return None

    # =========================================================
    # HTTP
    # =========================================================

    def _get(
        self,
        url: str,
    ) -> Optional[str]:

        try:

            logger.info(
                "GET %s",
                url,
            )

            response = self.session.get(
                url,
                timeout=self.timeout,
            )

            response.raise_for_status()

            time.sleep(self.request_delay)

            # -------------------------------------------------
            # Принудительно определяем UTF-8,
            # если сайт сообщает некорректную кодировку.
            # -------------------------------------------------

            if not response.encoding:
                response.encoding = "utf-8"

            return response.text

        except requests.RequestException as exc:

            logger.error(
                "Ошибка HTTP %s: %s",
                url,
                exc,
            )

            return None

        except Exception as exc:

            logger.error(
                "Ошибка загрузки %s: %s",
                url,
                exc,
            )

            return None

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _clean_text(
        text: str,
    ) -> str:

        if not text:
            return ""

        text = re.sub(
            r"\s+",
            " ",
            text,
        )

        return text.strip()


# =============================================================
# CONVENIENCE FUNCTION
# =============================================================

def parse_rpl_results(
    start_round: int = 1,
    end_round: int = 3,
) -> List[Dict[str, Any]]:
    """
    Удобная функция для load_all.py.

    Пример:

        results = parse_rpl_results(1, 3)
    """

    parser = RPLResultsParser()

    return parser.parse(
        start_round=start_round,
        end_round=end_round,
    )


# =============================================================
# LOCAL TEST
# =============================================================

if __name__ == "__main__":

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(message)s"
        ),
    )

    parser = RPLResultsParser()

    results = parser.parse(
        start_round=1,
        end_round=3,
    )

    print()
    print("=" * 70)
    print(
        f"НАЙДЕНО МАТЧЕЙ: {len(results)}"
    )
    print("=" * 70)

    for match in results:

        print(
            f"Тур {match['round']}: "
            f"{match['home_team']} — "
            f"{match['away_team']} "
            f"{match['home_goals']}:{match['away_goals']} "
            f"{match.get('date') or 'дата не определена'} "
            f"[{match.get('source')}]"
        )
