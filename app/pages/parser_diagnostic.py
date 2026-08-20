#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
PARSER DIAGNOSTIC v1.0
============================================================

НАЗНАЧЕНИЕ:

    Диагностика внешних страниц перед созданием парсеров.

    Поддерживаемые источники:

        Bombardir
        Soccer365

ПРИНЦИП:

    Сначала изучаем реальную HTML-структуру страницы.

    Только после этого создаём production parser.

ВАЖНО:

    Этот модуль НЕ записывает данные в SQLite.

    Он НЕ изменяет FAJ Database.

    Он НЕ создаёт факты матча.

    Он только получает страницу и формирует
    диагностический отчёт.

============================================================
"""

from __future__ import annotations

import re
import time
import html
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
    "Chrome/138.0.0.0 Safari/537.36"
)


# ============================================================
# PAGE CONFIG
# ============================================================

def configure_page() -> None:

    st.set_page_config(
        page_title="FAJ — Parser Diagnostic",
        page_icon="🔬",
        layout="wide",
    )


# ============================================================
# URL
# ============================================================

def validate_url(url: str) -> Tuple[bool, str]:

    if not url:
        return False, "URL пустой."

    url = url.strip()

    try:

        parsed = urlparse(url)

        if parsed.scheme not in (
            "http",
            "https",
        ):
            return False, "URL должен начинаться с http:// или https://"

        if not parsed.netloc:
            return False, "Не удалось определить домен."

        return True, ""

    except Exception as exc:

        return False, f"Ошибка URL: {exc}"


def detect_source(url: str) -> str:

    try:

        host = (
            urlparse(url)
            .netloc
            .lower()
            .replace("www.", "")
        )

        if "bombardir.ru" in host:
            return "Bombardir"

        if "soccer365.ru" in host:
            return "Soccer365"

        return host

    except Exception:

        return "Unknown"


# ============================================================
# HTTP
# ============================================================

def download_page(url: str) -> Dict[str, Any]:

    started = time.time()

    result: Dict[str, Any] = {
        "success": False,
        "url": url,
        "status_code": None,
        "final_url": None,
        "content_type": None,
        "encoding": None,
        "elapsed": None,
        "text": "",
        "headers": {},
        "error": None,
    }

    try:

        response = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml,"
                    "application/xml;q=0.9,"
                    "*/*;q=0.8"
                ),
                "Accept-Language": (
                    "ru-RU,ru;q=0.9,"
                    "en-US;q=0.8,en;q=0.7"
                ),
            },
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        result["status_code"] = response.status_code
        result["final_url"] = response.url
        result["content_type"] = (
            response.headers.get(
                "Content-Type"
            )
        )

        result["encoding"] = (
            response.encoding
        )

        result["headers"] = dict(
            response.headers
        )

        result["text"] = response.text

        result["success"] = (
            response.status_code == 200
        )

    except requests.RequestException as exc:

        result["error"] = (
            f"HTTP error: {exc}"
        )

    except Exception as exc:

        result["error"] = (
            f"Unexpected error: {exc}"
        )

    finally:

        result["elapsed"] = round(
            time.time() - started,
            3,
        )

    return result


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_whitespace(text: str) -> str:

    text = re.sub(
        r"\r\n?",
        "\n",
        text,
    )

    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def strip_html_to_text(
    source: str,
) -> str:

    text = source

    # Remove scripts
    text = re.sub(
        r"<script\b[^>]*>.*?</script>",
        " ",
        text,
        flags=re.I | re.S,
    )

    # Remove styles
    text = re.sub(
        r"<style\b[^>]*>.*?</style>",
        " ",
        text,
        flags=re.I | re.S,
    )

    # Remove comments
    text = re.sub(
        r"<!--.*?-->",
        " ",
        text,
        flags=re.S,
    )

    # Basic line breaks
    text = re.sub(
        r"<br\s*/?>",
        "\n",
        text,
        flags=re.I,
    )

    text = re.sub(
        r"</(p|div|tr|li|h1|h2|h3|h4|h5|h6)>",
        "\n",
        text,
        flags=re.I,
    )

    # Remove remaining tags
    text = re.sub(
        r"<[^>]+>",
        " ",
        text,
    )

    text = html.unescape(text)

    return normalize_whitespace(
        text
    )


# ============================================================
# HTML STRUCTURE
# ============================================================

def extract_title(
    source: str,
) -> str:

    match = re.search(
        r"<title[^>]*>(.*?)</title>",
        source,
        flags=re.I | re.S,
    )

    if not match:
        return ""

    return normalize_whitespace(
        html.unescape(
            match.group(1)
        )
    )


def extract_meta(
    source: str,
) -> List[Dict[str, str]]:

    result = []

    pattern = re.compile(
        r"<meta\b([^>]*)>",
        flags=re.I | re.S,
    )

    for match in pattern.finditer(
        source
    ):

        attrs = match.group(1)

        name_match = re.search(
            r'(?:name|property|itemprop)\s*=\s*["\']([^"\']+)["\']',
            attrs,
            flags=re.I,
        )

        content_match = re.search(
            r'content\s*=\s*["\']([^"\']*)["\']',
            attrs,
            flags=re.I,
        )

        if name_match:

            result.append(
                {
                    "name": name_match.group(1),
                    "content": (
                        content_match.group(1)
                        if content_match
                        else ""
                    ),
                }
            )

    return result


def extract_links(
    source: str,
    limit: int = 200,
) -> List[str]:

    links = []

    pattern = re.compile(
        r'<a\b[^>]*href\s*=\s*["\']([^"\']+)["\']',
        flags=re.I,
    )

    for match in pattern.finditer(
        source
    ):

        href = html.unescape(
            match.group(1)
        ).strip()

        if href and href not in links:

            links.append(href)

        if len(links) >= limit:
            break

    return links


def extract_scripts(
    source: str,
    limit: int = 100,
) -> List[str]:

    scripts = []

    pattern = re.compile(
        r"<script\b([^>]*)>",
        flags=re.I | re.S,
    )

    for match in pattern.finditer(
        source
    ):

        attrs = normalize_whitespace(
            match.group(1)
        )

        if attrs:

            scripts.append(
                attrs
            )

        if len(scripts) >= limit:
            break

    return scripts


# ============================================================
# INTERESTING TERMS
# ============================================================

INTERESTING_TERMS = [

    # Score
    "счёт",
    "счет",
    "result",
    "score",
    "full-time",
    "fulltime",

    # xG
    "xg",
    "expected goals",
    "ожидаемые голы",

    # Possession
    "владение",
    "possession",

    # Shots
    "удары",
    "shots",
    "shots on target",
    "удары в створ",

    # Corners
    "угловые",
    "corners",

    # Passes
    "передачи",
    "passes",
    "pass accuracy",

    # Fouls
    "фолы",
    "fouls",

    # Cards
    "желтые",
    "красные",
    "yellow",
    "red",

    # Match
    "матч",
    "match",
    "game",
]


def find_interesting_terms(
    source: str,
) -> List[Dict[str, Any]]:

    lower = source.lower()

    result = []

    for term in INTERESTING_TERMS:

        count = lower.count(
            term.lower()
        )

        if count:

            result.append(
                {
                    "term": term,
                    "count": count,
                }
            )

    return result


# ============================================================
# CONTEXT SEARCH
# ============================================================

def extract_contexts(
    source: str,
    terms: List[str],
    radius: int = 500,
    max_contexts: int = 30,
) -> List[str]:

    contexts = []

    lower = source.lower()

    for term in terms:

        start = 0

        while True:

            position = lower.find(
                term.lower(),
                start,
            )

            if position == -1:
                break

            left = max(
                0,
                position - radius,
            )

            right = min(
                len(source),
                position
                + len(term)
                + radius,
            )

            context = source[
                left:right
            ]

            context = normalize_whitespace(
                context
            )

            contexts.append(
                f"[TERM: {term}]\n"
                f"{context}"
            )

            if len(contexts) >= max_contexts:
                return contexts

            start = (
                position
                + len(term)
            )

    return contexts


# ============================================================
# RAW HTML SAMPLE
# ============================================================

def build_html_sample(
    source: str,
    max_chars: int = 12000,
) -> str:

    if len(source) <= max_chars:

        return source

    half = max_chars // 2

    return (
        source[:half]
        + "\n\n"
        + "..."
        + "\n\n"
        + source[-half:]
    )


# ============================================================
# JSON-LD
# ============================================================

def extract_json_ld(
    source: str,
) -> List[str]:

    result = []

    pattern = re.compile(
        r'<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>'
        r"(.*?)"
        r"</script>",
        flags=re.I | re.S,
    )

    for match in pattern.finditer(
        source
    ):

        content = match.group(1).strip()

        if content:

            result.append(
                content
            )

    return result


# ============================================================
# DATA ATTRIBUTES
# ============================================================

def extract_data_attributes(
    source: str,
    limit: int = 300,
) -> List[str]:

    result = []

    pattern = re.compile(
        r'\s(data-[a-zA-Z0-9_-]+)\s*=\s*["\']([^"\']*)["\']',
        flags=re.I,
    )

    for match in pattern.finditer(
        source
    ):

        item = (
            f"{match.group(1)}="
            f"{match.group(2)}"
        )

        if item not in result:

            result.append(
                item
            )

        if len(result) >= limit:
            break

    return result


# ============================================================
# CLASS / ID DISCOVERY
# ============================================================

def extract_classes_and_ids(
    source: str,
    limit: int = 300,
) -> Dict[str, List[str]]:

    classes = []
    ids = []

    class_pattern = re.compile(
        r'\bclass\s*=\s*["\']([^"\']+)["\']',
        flags=re.I,
    )

    id_pattern = re.compile(
        r'\bid\s*=\s*["\']([^"\']+)["\']',
        flags=re.I,
    )

    for match in class_pattern.finditer(
        source
    ):

        value = normalize_whitespace(
            match.group(1)
        )

        for item in value.split():

            if item not in classes:

                classes.append(
                    item
                )

            if len(classes) >= limit:
                break

        if len(classes) >= limit:
            break

    for match in id_pattern.finditer(
        source
    ):

        value = normalize_whitespace(
            match.group(1)
        )

        if value not in ids:

            ids.append(
                value
            )

        if len(ids) >= limit:
            break

    return {
        "classes": classes,
        "ids": ids,
    }


# ============================================================
# REPORT
# ============================================================

def build_report(
    source_name: str,
    result: Dict[str, Any],
) -> str:

    source = result.get(
        "text",
        "",
    )

    final_url = result.get(
        "final_url"
    )

    status_code = result.get(
        "status_code"
    )

    title = extract_title(
        source
    )

    meta = extract_meta(
        source
    )

    links = extract_links(
        source
    )

    scripts = extract_scripts(
        source
    )

    json_ld = extract_json_ld(
        source
    )

    data_attributes = (
        extract_data_attributes(
            source
        )
    )

    classes_ids = (
        extract_classes_and_ids(
            source
        )
    )

    interesting = (
        find_interesting_terms(
            source
        )
    )

    contexts = extract_contexts(
        source,
        [
            item["term"]
            for item in interesting
        ],
    )

    text = strip_html_to_text(
        source
    )

    lines = []

    lines.append(
        "============================================================"
    )

    lines.append(
        "FAJ PARSER DIAGNOSTIC REPORT"
    )

    lines.append(
        "============================================================"
    )

    lines.append(
        f"Diagnostic version: {DIAGNOSTIC_VERSION}"
    )

    lines.append(
        f"FAJ Platform: {APP_VERSION}"
    )

    lines.append(
        f"Source: {source_name}"
    )

    lines.append(
        f"Generated: {datetime.now().isoformat()}"
    )

    lines.append("")

    # --------------------------------------------------------
    # HTTP
    # --------------------------------------------------------

    lines.append(
        "================ HTTP ================="
    )

    lines.append(
        f"Status code: {status_code}"
    )

    lines.append(
        f"Original URL: {result.get('url')}"
    )

    lines.append(
        f"Final URL: {final_url}"
    )

    lines.append(
        f"Content-Type: {result.get('content_type')}"
    )

    lines.append(
        f"Encoding: {result.get('encoding')}"
    )

    lines.append(
        f"Request time: {result.get('elapsed')} sec"
    )

    if result.get("error"):

        lines.append(
            f"ERROR: {result.get('error')}"
        )

    lines.append("")

    # --------------------------------------------------------
    # PAGE
    # --------------------------------------------------------

    lines.append(
        "================ PAGE ================="
    )

    lines.append(
        f"Title: {title}"
    )

    lines.append(
        f"HTML length: {len(source)}"
    )

    lines.append(
        f"Visible text length: {len(text)}"
    )

    lines.append("")

    # --------------------------------------------------------
    # META
    # --------------------------------------------------------

    lines.append(
        "================ META ================="
    )

    for item in meta[:100]:

        lines.append(
            f"{item['name']} = {item['content']}"
        )

    lines.append("")

    # --------------------------------------------------------
    # INTERESTING TERMS
    # --------------------------------------------------------

    lines.append(
        "================ INTERESTING TERMS ================="
    )

    for item in interesting:

        lines.append(
            f"{item['term']} -> {item['count']}"
        )

    lines.append("")

    # --------------------------------------------------------
    # CONTEXTS
    # --------------------------------------------------------

    lines.append(
        "================ CONTEXTS ================="
    )

    for index, context in enumerate(
        contexts,
        start=1,
    ):

        lines.append(
            f"\n--- CONTEXT {index} ---\n"
        )

        lines.append(
            context
        )

    lines.append("")

    # --------------------------------------------------------
    # JSON-LD
    # --------------------------------------------------------

    lines.append(
        "================ JSON-LD ================="
    )

    for index, item in enumerate(
        json_ld,
        start=1,
    ):

        lines.append(
            f"\n--- JSON-LD {index} ---"
        )

        lines.append(
            item[:10000]
        )

    lines.append("")

    # --------------------------------------------------------
    # DATA ATTRIBUTES
    # --------------------------------------------------------

    lines.append(
        "================ DATA ATTRIBUTES ================="
    )

    for item in data_attributes:

        lines.append(
            item
        )

    lines.append("")

    # --------------------------------------------------------
    # CLASSES / IDS
    # --------------------------------------------------------

    lines.append(
        "================ CLASSES ================="
    )

    for item in classes_ids["classes"]:

        lines.append(
            item
        )

    lines.append("")

    lines.append(
        "================ IDS ================="
    )

    for item in classes_ids["ids"]:

        lines.append(
            item
        )

    lines.append("")

    # --------------------------------------------------------
    # LINKS
    # --------------------------------------------------------

    lines.append(
        "================ LINKS ================="
    )

    for link in links:

        lines.append(
            link
        )

    lines.append("")

    # --------------------------------------------------------
    # SCRIPTS
    # --------------------------------------------------------

    lines.append(
        "================ SCRIPTS ================="
    )

    for script in scripts:

        lines.append(
            script
        )

    lines.append("")

    # --------------------------------------------------------
    # VISIBLE TEXT
    # --------------------------------------------------------

    lines.append(
        "================ VISIBLE TEXT ================="
    )

    lines.append(
        text[:20000]
    )

    lines.append("")

    # --------------------------------------------------------
    # RAW HTML
    # --------------------------------------------------------

    lines.append(
        "================ RAW HTML SAMPLE ================="
    )

    lines.append(
        build_html_sample(
            source,
            max_chars=20000,
        )
    )

    lines.append("")

    lines.append(
        "============================================================"
    )

    lines.append(
        "END OF REPORT"
    )

    lines.append(
        "============================================================"
    )

    return "\n".join(
        lines
    )


# ============================================================
# DIAGNOSTIC RUNNER
# ============================================================

def run_diagnostic(
    url: str,
) -> Tuple[Dict[str, Any], str]:

    source_name = detect_source(
        url
    )

    result = download_page(
        url
    )

    report = build_report(
        source_name,
        result,
    )

    return result, report


# ============================================================
# UI
# ============================================================

def render_source_block(
    title: str,
    key_prefix: str,
) -> None:

    st.subheader(
        title
    )

    url = st.text_input(
        "Ссылка",
        key=f"{key_prefix}_url",
        placeholder="Вставьте полную ссылку...",
    )

    if st.button(
        f"🔬 Исследовать {title}",
        key=f"{key_prefix}_run",
        type="primary",
        use_container_width=True,
    ):

        valid, error = validate_url(
            url
        )

        if not valid:

            st.error(
                f"❌ {error}"
            )

            return

        with st.spinner(
            f"Получаем страницу {title}..."
        ):

            result, report = run_diagnostic(
                url
            )

        st.session_state[
            f"{key_prefix}_result"
        ] = result

        st.session_state[
            f"{key_prefix}_report"
        ] = report

        st.rerun()

    result = st.session_state.get(
        f"{key_prefix}_result"
    )

    report = st.session_state.get(
        f"{key_prefix}_report"
    )

    if not result:
        return

    st.divider()

    if result.get("success"):

        st.success(
            "✅ Страница успешно получена."
        )

    else:

        st.error(
            "❌ Не удалось нормально получить страницу."
        )

    # --------------------------------------------------------
    # QUICK STATUS
    # --------------------------------------------------------

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "HTTP",
            result.get(
                "status_code"
            )
            or "—",
        )

    with c2:

        st.metric(
            "Размер HTML",
            f"{len(result.get('text', '')):,}",
        )

    with c3:

        st.metric(
            "Время",
            f"{result.get('elapsed', 0)} s",
        )

    with c4:

        st.metric(
            "Источник",
            detect_source(
                result.get(
                    "url",
                    "",
                )
            ),
        )

    if result.get(
        "final_url"
    ):

        st.caption(
            f"Фактический URL: "
            f"{result['final_url']}"
        )

    # --------------------------------------------------------
    # REPORT
    # --------------------------------------------------------

    st.subheader(
        "📋 Диагностический отчёт"
    )

    st.text_area(
        "Отчёт можно полностью скопировать",
        value=report,
        height=500,
        key=f"{key_prefix}_report_view",
    )

    st.download_button(
        "💾 Сохранить отчёт",
        data=report,
        file_name=(
            f"faj_{key_prefix}_"
            "diagnostic.txt"
        ),
        mime="text/plain",
        key=f"{key_prefix}_download",
        use_container_width=True,
    )

    # --------------------------------------------------------
    # RAW HTML
    # --------------------------------------------------------

    with st.expander(
        "🔎 Посмотреть полученный HTML"
    ):

        st.code(
            result.get(
                "text",
                "",
            )[:30000],
            language="html",
        )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    configure_page()

    st.title(
        "🔬 FAJ — Диагностика парсеров"
    )

    st.caption(
        "Изучаем реальные страницы Bombardir и Soccer365 "
        "перед созданием production-парсеров."
    )

    st.warning(
        "⚠️ Этот модуль ничего не записывает в SQLite "
        "и не изменяет данные FAJ."
    )

    st.divider()

    # ========================================================
    # INSTRUCTIONS
    # ========================================================

    st.markdown(
        """
### Как работаем

**1. Bombardir**

Вставьте ссылку на страницу матча, например:

`https://bombardir.ru/online/...`

Нажмите **«Исследовать Bombardir»**.

**2. Soccer365**

Вставьте ссылку на страницу матча, например:

`https://soccer365.ru/games/...`

Нажмите **«Исследовать Soccer365»**.

После получения отчёта скопируйте его и пришлите сюда.

Мы сначала изучим структуру сайтов, а уже потом напишем парсеры.
"""
    )

    st.divider()

    # ========================================================
    # BOMBARDIR
    # ========================================================

    render_source_block(
        "📊 Bombardir",
        "bombardir",
    )

    st.divider()

    # ========================================================
    # SOCCER365
    # ========================================================

    render_source_block(
        "🎯 Soccer365",
        "soccer365",
    )

    st.divider()

    st.caption(
        f"FAJ Platform v{APP_VERSION} · "
        f"Parser Diagnostic v{DIAGNOSTIC_VERSION}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
