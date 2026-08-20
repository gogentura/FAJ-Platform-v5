#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
PARSER DIAGNOSTIC v1.0
============================================================

НАЗНАЧЕНИЕ:

    Диагностика внешних страниц перед созданием парсеров.

    Источники:

        Bombardir
        Soccer365

    Модуль НЕ записывает данные в SQLite.

    Модуль НЕ изменяет:
        matches
        match_results
        match_statistics
        predictions
        gold
        learning_memory

    Он только получает страницу и формирует
    технический диагностический отчёт.

============================================================
"""

from __future__ import annotations

import json
import re
import html
import hashlib
from datetime import datetime
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import requests
import streamlit as st


# ============================================================
# CONFIG
# ============================================================

APP_VERSION = "12.1"
DIAGNOSTIC_VERSION = "1.0"

REQUEST_TIMEOUT = 20

USER_AGENT = (
    "Mozilla/5.0 "
    "(Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 "
    "(KHTML, like Gecko) "
    "Chrome/139.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,"
        "image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}


# ============================================================
# URL VALIDATION
# ============================================================

def validate_url(
    url: str,
    expected_domain: str,
) -> Tuple[bool, str]:

    url = (url or "").strip()

    if not url:
        return False, "URL не указан."

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Не удалось разобрать URL."

    if parsed.scheme not in ("http", "https"):
        return False, "URL должен начинаться с http:// или https://."

    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return False, "В URL отсутствует домен."

    if expected_domain not in hostname:
        return (
            False,
            f"Ожидался домен {expected_domain}, "
            f"получен {hostname}.",
        )

    return True, ""


# ============================================================
# HTTP
# ============================================================

def fetch_page(url: str) -> Dict[str, Any]:

    result: Dict[str, Any] = {
        "success": False,
        "url": url,
        "final_url": None,
        "status_code": None,
        "content_type": None,
        "content_length": None,
        "encoding": None,
        "elapsed": None,
        "html": "",
        "error": None,
        "headers": {},
    }

    started = datetime.now()

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        elapsed = (
            datetime.now() - started
        ).total_seconds()

        result["elapsed"] = elapsed
        result["status_code"] = response.status_code
        result["final_url"] = response.url
        result["content_type"] = response.headers.get(
            "Content-Type"
        )
        result["content_length"] = len(
            response.content
        )
        result["encoding"] = response.encoding
        result["headers"] = dict(
            response.headers
        )

        result["html"] = response.text

        result["success"] = (
            response.status_code >= 200
            and response.status_code < 400
        )

        if not result["success"]:
            result["error"] = (
                f"HTTP status {response.status_code}"
            )

        return result

    except requests.exceptions.Timeout:

        result["error"] = (
            f"Timeout: сайт не ответил "
            f"за {REQUEST_TIMEOUT} секунд."
        )

        return result

    except requests.exceptions.RequestException as exc:

        result["error"] = (
            f"HTTP error: {exc}"
        )

        return result

    except Exception as exc:

        result["error"] = (
            f"Неизвестная ошибка: {exc}"
        )

        return result


# ============================================================
# HTML HELPERS
# ============================================================

def strip_html(text: str) -> str:

    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.I | re.S,
    )

    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = html.unescape(text)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def extract_title(html_text: str) -> str:

    match = re.search(
        r"<title[^>]*>(.*?)</title>",
        html_text,
        flags=re.I | re.S,
    )

    if not match:
        return ""

    return strip_html(
        match.group(1)
    )


def extract_meta(
    html_text: str,
    name: str,
) -> str:

    patterns = [
        rf'<meta[^>]+name=["\']{re.escape(name)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+property=["\']{re.escape(name)}["\'][^>]+content=["\'](.*?)["\']',
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            html_text,
            flags=re.I | re.S,
        )

        if match:
            return html.unescape(
                match.group(1)
            ).strip()

    return ""


# ============================================================
# STRUCTURE ANALYSIS
# ============================================================

def count_tag(
    html_text: str,
    tag: str,
) -> int:

    return len(
        re.findall(
            rf"<{tag}\b",
            html_text,
            flags=re.I,
        )
    )


def extract_tables(
    html_text: str,
) -> List[Dict[str, Any]]:

    tables = []

    for index, match in enumerate(
        re.finditer(
            r"<table\b[^>]*>(.*?)</table>",
            html_text,
            flags=re.I | re.S,
        ),
        start=1,
    ):

        table_html = match.group(0)

        rows = re.findall(
            r"<tr\b[^>]*>(.*?)</tr>",
            table_html,
            flags=re.I | re.S,
        )

        tables.append(
            {
                "number": index,
                "html_size": len(table_html),
                "rows": len(rows),
                "text": strip_html(
                    table_html
                )[:1500],
            }
        )

    return tables


def extract_scripts(
    html_text: str,
) -> List[Dict[str, Any]]:

    scripts = []

    for index, match in enumerate(
        re.finditer(
            r"<script\b([^>]*)>(.*?)</script>",
            html_text,
            flags=re.I | re.S,
        ),
        start=1,
    ):

        attributes = match.group(1) or ""
        content = match.group(2) or ""

        scripts.append(
            {
                "number": index,
                "attributes": attributes.strip(),
                "size": len(content),
                "preview": content[:1000],
            }
        )

    return scripts


def extract_links(
    html_text: str,
) -> List[str]:

    links = re.findall(
        r'href=["\']([^"\']+)["\']',
        html_text,
        flags=re.I,
    )

    unique = []

    for link in links:

        if link not in unique:
            unique.append(link)

    return unique[:100]


def extract_classes(
    html_text: str,
) -> List[str]:

    classes = re.findall(
        r'class=["\']([^"\']+)["\']',
        html_text,
        flags=re.I,
    )

    result = []

    for item in classes:

        for cls in item.split():

            if cls and cls not in result:
                result.append(cls)

    return result[:200]


# ============================================================
# JSON DETECTION
# ============================================================

def looks_like_json(
    text: str,
) -> bool:

    text = text.strip()

    if not text:
        return False

    if not (
        text.startswith("{")
        or text.startswith("[")
    ):
        return False

    try:
        json.loads(text)
        return True
    except Exception:
        return False


def detect_json_scripts(
    scripts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    found = []

    for script in scripts:

        content = script.get(
            "preview",
            "",
        )

        if looks_like_json(content):

            found.append(
                {
                    "script": script["number"],
                    "type": "JSON",
                    "preview": content[:2000],
                }
            )

    return found


# ============================================================
# DATA PATTERN DETECTION
# ============================================================

PATTERNS = {

    "xG": [
        r"\bxG\b",
        r"\bXG\b",
        r"expected\s+goals",
        r"expected_goals",
    ],

    "Владение": [
        r"владение",
        r"possession",
    ],

    "Удары": [
        r"\bудары\b",
        r"\bshots\b",
    ],

    "Удары в створ": [
        r"удары\s+в\s+створ",
        r"shots\s+on\s+target",
        r"on\s+target",
    ],

    "Угловые": [
        r"углов",
        r"corners",
    ],

    "Передачи": [
        r"передач",
        r"passes",
    ],

    "Точность передач": [
        r"точност.*передач",
        r"pass\s+accuracy",
    ],

    "Точные передачи": [
        r"точн.*передач",
        r"accurate\s+passes",
    ],

    "Отборы": [
        r"отбор",
        r"tackles",
    ],

    "Счёт": [
        r"\b\d{1,2}\s*[:\-]\s*\d{1,2}\b",
    ],
}


def detect_patterns(
    text: str,
) -> Dict[str, List[str]]:

    results = {}

    for name, patterns in PATTERNS.items():

        matches = []

        for pattern in patterns:

            for match in re.finditer(
                pattern,
                text,
                flags=re.I,
            ):

                start = max(
                    0,
                    match.start() - 100,
                )

                end = min(
                    len(text),
                    match.end() + 150,
                )

                fragment = text[
                    start:end
                ]

                fragment = re.sub(
                    r"\s+",
                    " ",
                    fragment,
                )

                if fragment not in matches:
                    matches.append(
                        fragment
                    )

                if len(matches) >= 5:
                    break

            if len(matches) >= 5:
                break

        results[name] = matches

    return results


# ============================================================
# NUMERIC PATTERNS
# ============================================================

def detect_numbers(
    text: str,
) -> List[str]:

    patterns = [
        r"\b\d{1,3}[.,]\d{1,3}\b",
        r"\b\d{1,3}%\b",
        r"\b\d{1,3}\b",
    ]

    found = []

    for pattern in patterns:

        for match in re.finditer(
            pattern,
            text,
        ):

            value = match.group(0)

            if value not in found:
                found.append(value)

            if len(found) >= 100:
                return found

    return found


# ============================================================
# HTML FRAGMENTS AROUND KEYWORDS
# ============================================================

def extract_html_fragments(
    html_text: str,
    keywords: List[str],
) -> List[str]:

    fragments = []

    lower_html = html_text.lower()

    for keyword in keywords:

        position = lower_html.find(
            keyword.lower()
        )

        if position == -1:
            continue

        start = max(
            0,
            position - 500,
        )

        end = min(
            len(html_text),
            position + 1500,
        )

        fragment = html_text[
            start:end
        ]

        if fragment not in fragments:
            fragments.append(
                fragment
            )

    return fragments[:10]


# ============================================================
# DIAGNOSTIC REPORT
# ============================================================

def build_report(
    source_name: str,
    expected_domain: str,
    url: str,
    page: Dict[str, Any],
) -> str:

    timestamp = datetime.now().isoformat()

    html_text = page.get(
        "html",
        "",
    )

    title = extract_title(
        html_text
    )

    description = extract_meta(
        html_text,
        "description",
    )

    og_title = extract_meta(
        html_text,
        "og:title",
    )

    visible_text = strip_html(
        html_text
    )

    tables = extract_tables(
        html_text
    )

    scripts = extract_scripts(
        html_text
    )

    links = extract_links(
        html_text
    )

    classes = extract_classes(
        html_text
    )

    patterns = detect_patterns(
        visible_text
    )

    numbers = detect_numbers(
        visible_text
    )

    html_hash = hashlib.sha256(
        html_text.encode(
            "utf-8",
            errors="ignore",
        )
    ).hexdigest()

    report = []

    report.append(
        "=" * 70
    )

    report.append(
        f"FAJ SOURCE DIAGNOSTIC v{DIAGNOSTIC_VERSION}"
    )

    report.append(
        "=" * 70
    )

    report.append("")

    report.append(
        f"SOURCE: {source_name}"
    )

    report.append(
        f"EXPECTED DOMAIN: {expected_domain}"
    )

    report.append(
        f"DIAGNOSTIC TIME: {timestamp}"
    )

    report.append(
        f"INPUT URL: {url}"
    )

    report.append(
        f"FINAL URL: {page.get('final_url')}"
    )

    report.append("")

    report.append(
        "-" * 70
    )

    report.append(
        "HTTP"
    )

    report.append(
        "-" * 70
    )

    report.append(
        f"SUCCESS: {page.get('success')}"
    )

    report.append(
        f"STATUS CODE: {page.get('status_code')}"
    )

    report.append(
        f"CONTENT TYPE: {page.get('content_type')}"
    )

    report.append(
        f"CONTENT LENGTH: {page.get('content_length')}"
    )

    report.append(
        f"ENCODING: {page.get('encoding')}"
    )

    report.append(
        f"ELAPSED: {page.get('elapsed')} sec"
    )

    report.append(
        f"ERROR: {page.get('error')}"
    )

    report.append("")

    report.append(
        "-" * 70
    )

    report.append(
        "PAGE IDENTITY"
    )

    report.append(
        "-" * 70
    )

    report.append(
        f"TITLE: {title}"
    )

    report.append(
        f"DESCRIPTION: {description}"
    )

    report.append(
        f"OG TITLE: {og_title}"
    )

    report.append("")

    report.append(
        "-" * 70
    )

    report.append(
        "HTML STRUCTURE"
    )

    report.append(
        "-" * 70
    )

    for tag in (
        "html",
        "head",
        "body",
        "div",
        "span",
        "table",
        "tr",
        "td",
        "script",
        "a",
    ):

        report.append(
            f"<{tag}>: {count_tag(html_text, tag)}"
        )

    report.append(
        f"HTML SHA256: {html_hash}"
    )

    report.append("")

    # --------------------------------------------------------
    # TABLES
    # --------------------------------------------------------

    report.append(
        "-" * 70
    )

    report.append(
        f"TABLES: {len(tables)}"
    )

    report.append(
        "-" * 70
    )

    for table in tables:

        report.append(
            f"TABLE #{table['number']}"
        )

        report.append(
            f"HTML SIZE: {table['html_size']}"
        )

        report.append(
            f"ROWS: {table['rows']}"
        )

        report.append(
            f"TEXT: {table['text']}"
        )

        report.append("")

    # --------------------------------------------------------
    # SCRIPTS
    # --------------------------------------------------------

    report.append(
        "-" * 70
    )

    report.append(
        f"SCRIPTS: {len(scripts)}"
    )

    report.append(
        "-" * 70
    )

    for script in scripts[:50]:

        report.append(
            f"SCRIPT #{script['number']}"
        )

        report.append(
            f"ATTRIBUTES: {script['attributes']}"
        )

        report.append(
            f"SIZE: {script['size']}"
        )

        report.append(
            f"PREVIEW:\n{script['preview'][:1000]}"
        )

        report.append("")

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    json_scripts = detect_json_scripts(
        scripts
    )

    report.append(
        "-" * 70
    )

    report.append(
        f"POSSIBLE JSON SCRIPTS: {len(json_scripts)}"
    )

    report.append(
        "-" * 70
    )

    for item in json_scripts:

        report.append(
            f"SCRIPT #{item['script']}"
        )

        report.append(
            item["preview"]
        )

        report.append("")

    # --------------------------------------------------------
    # PATTERNS
    # --------------------------------------------------------

    report.append(
        "-" * 70
    )

    report.append(
        "IMPORTANT DATA PATTERNS"
    )

    report.append(
        "-" * 70
    )

    for name, matches in patterns.items():

        report.append(
            f"\n### {name}"
        )

        if not matches:

            report.append(
                "NOT FOUND"
            )

        else:

            for fragment in matches:

                report.append(
                    f"- {fragment}"
                )

    # --------------------------------------------------------
    # LINKS
    # --------------------------------------------------------

    report.append(
        "-" * 70
    )

    report.append(
        "LINKS"
    )

    report.append(
        "-" * 70
    )

    for link in links:

        report.append(
            link
        )

    # --------------------------------------------------------
    # CLASSES
    # --------------------------------------------------------

    report.append(
        "-" * 70
    )

    report.append(
        "CSS CLASSES"
    )

    report.append(
        "-" * 70
    )

    for cls in classes:

        report.append(
            cls
        )

    # --------------------------------------------------------
    # NUMBERS
    # --------------------------------------------------------

    report.append(
        "-" * 70
    )

    report.append(
        "DETECTED NUMERIC VALUES"
    )

    report.append(
        "-" * 70
    )

    report.append(
        ", ".join(numbers)
    )

    # --------------------------------------------------------
    # HTML FRAGMENTS
    # --------------------------------------------------------

    fragments = extract_html_fragments(
        html_text,
        [
            "xG",
            "expected",
            "possession",
            "владение",
            "shots",
            "удары",
            "corners",
            "углов",
            "passes",
            "передач",
        ],
    )

    report.append(
        "-" * 70
    )

    report.append(
        "IMPORTANT HTML FRAGMENTS"
    )

    report.append(
        "-" * 70
    )

    for index, fragment in enumerate(
        fragments,
        start=1,
    ):

        report.append(
            f"\n### FRAGMENT #{index}"
        )

        report.append(
            fragment
        )

    # --------------------------------------------------------
    # VISIBLE TEXT
    # --------------------------------------------------------

    report.append(
        "-" * 70
    )

    report.append(
        "VISIBLE TEXT PREVIEW"
    )

    report.append(
        "-" * 70
    )

    report.append(
        visible_text[:10000]
    )

    # --------------------------------------------------------
    # RAW HTML PREVIEW
    # --------------------------------------------------------

    report.append(
        "-" * 70
    )

    report.append(
        "RAW HTML PREVIEW"
    )

    report.append(
        "-" * 70
    )

    report.append(
        html_text[:15000]
    )

    report.append("")

    report.append(
        "=" * 70
    )

    report.append(
        "END OF DIAGNOSTIC REPORT"
    )

    report.append(
        "=" * 70
    )

    return "\n".join(report)


# ============================================================
# RUN DIAGNOSTIC
# ============================================================

def run_diagnostic(
    source_name: str,
    expected_domain: str,
    url: str,
) -> Dict[str, Any]:

    valid, error = validate_url(
        url,
        expected_domain,
    )

    if not valid:

        return {
            "success": False,
            "error": error,
            "report": "",
        }

    page = fetch_page(
        url
    )

    if not page["success"]:

        report = build_report(
            source_name,
            expected_domain,
            url,
            page,
        )

        return {
            "success": False,
            "error": page.get(
                "error"
            ),
            "report": report,
        }

    report = build_report(
        source_name,
        expected_domain,
        url,
        page,
    )

    return {
        "success": True,
        "error": None,
        "report": report,
    }


# ============================================================
# UI
# ============================================================

def main() -> None:

    st.set_page_config(
        page_title="FAJ — Parser Diagnostic",
        page_icon="🔎",
        layout="wide",
    )

    st.title(
        "🔎 FAJ — Диагностика парсеров"
    )

    st.caption(
        f"FAJ Platform {APP_VERSION} | "
        f"Parser Diagnostic {DIAGNOSTIC_VERSION}"
    )

    st.info(
        "Эта страница только исследует внешние сайты. "
        "Она не записывает данные в FAJ и не изменяет SQLite."
    )

    # ========================================================
    # BOMBARDIR
    # ========================================================

    st.markdown(
        "## 📊 Bombardir"
    )

    bombardir_url = st.text_input(
        "Ссылка на страницу матча Bombardir",
        placeholder=(
            "https://bombardir.ru/online/..."
        ),
        key="diagnostic_bombardir_url",
    )

    if st.button(
        "🔎 Исследовать Bombardir",
        key="diagnostic_bombardir_button",
        use_container_width=True,
    ):

        with st.spinner(
            "Исследуем страницу Bombardir..."
        ):

            result = run_diagnostic(
                source_name="Bombardir",
                expected_domain="bombardir.ru",
                url=bombardir_url,
            )

        st.session_state[
            "diagnostic_bombardir_result"
        ] = result

    bombardir_result = st.session_state.get(
        "diagnostic_bombardir_result"
    )

    if bombardir_result:

        if bombardir_result["success"]:

            st.success(
                "✅ Страница Bombardir получена."
            )

        else:

            st.error(
                "❌ Не удалось получить страницу."
            )

            if bombardir_result.get(
                "error"
            ):

                st.warning(
                    bombardir_result["error"]
                )

        if bombardir_result.get(
            "report"
        ):

            st.text_area(
                "📋 Отчёт Bombardir — скопируй полностью",
                value=bombardir_result["report"],
                height=600,
                key="bombardir_report",
            )

            st.download_button(
                "💾 Сохранить отчёт Bombardir",
                data=bombardir_result["report"],
                file_name="bombardir_diagnostic.txt",
                mime="text/plain",
                use_container_width=True,
            )

    st.divider()

    # ========================================================
    # SOCCER365
    # ========================================================

    st.markdown(
        "## 🎯 Soccer365"
    )

    soccer365_url = st.text_input(
        "Ссылка на страницу матча Soccer365",
        placeholder=(
            "https://soccer365.ru/games/..."
        ),
        key="diagnostic_soccer365_url",
    )

    if st.button(
        "🔎 Исследовать Soccer365",
        key="diagnostic_soccer365_button",
        use_container_width=True,
    ):

        with st.spinner(
            "Исследуем страницу Soccer365..."
        ):

            result = run_diagnostic(
                source_name="Soccer365",
                expected_domain="soccer365.ru",
                url=soccer365_url,
            )

        st.session_state[
            "diagnostic_soccer365_result"
        ] = result

    soccer365_result = st.session_state.get(
        "diagnostic_soccer365_result"
    )

    if soccer365_result:

        if soccer365_result["success"]:

            st.success(
                "✅ Страница Soccer365 получена."
            )

        else:

            st.error(
                "❌ Не удалось получить страницу."
            )

            if soccer365_result.get(
                "error"
            ):

                st.warning(
                    soccer365_result["error"]
                )

        if soccer365_result.get(
            "report"
        ):

            st.text_area(
                "📋 Отчёт Soccer365 — скопируй полностью",
                value=soccer365_result["report"],
                height=600,
                key="soccer365_report",
            )

            st.download_button(
                "💾 Сохранить отчёт Soccer365",
                data=soccer365_result["report"],
                file_name="soccer365_diagnostic.txt",
                mime="text/plain",
                use_container_width=True,
            )

    st.divider()

    st.caption(
        "FAJ Parser Diagnostic не является парсером. "
        "Он предназначен для исследования структуры источников "
        "перед созданием устойчивых адаптеров."
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
