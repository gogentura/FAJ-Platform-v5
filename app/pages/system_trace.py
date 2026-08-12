#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
============================================================
FAJ Platform v12.1
SYSTEM TRACE / ARCHITECTURE DIAGNOSTIC
============================================================

Назначение:

    Не проверяет качество модели.
    Не проверяет точность прогнозов.
    Не изменяет БД.

    Показывает фактическую структуру проекта:

        Streamlit
            ↓
        Pages
            ↓
        Managers / Services
            ↓
        Core / Pipeline
            ↓
        Models
            ↓
        Database

Основные задачи:

    1. Найти Python-файлы проекта.
    2. Построить граф импортов.
    3. Определить достижимые файлы от streamlit_app.py.
    4. Найти потенциальный legacy.
    5. Найти подозрительные дубликаты.
    6. Найти опасные операции DELETE / DROP / TRUNCATE.
    7. Проверить runtime-модули.
    8. Показать отсутствующие импортируемые модули.
    9. Показать data-файлы.
   10. Дать архитектурный verdict.

ВАЖНО:

    Этот модуль только читает исходный код и файловую систему.
    Никаких изменений проекта или БД он не выполняет.
"""

from __future__ import annotations

import ast
import importlib.util
import os
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pandas as pd
import streamlit as st


# ============================================================
# PATHS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "app"
DATA_DIR = ROOT_DIR / "data"
ENTRYPOINT = ROOT_DIR / "streamlit_app.py"


# ============================================================
# PAGE
# ============================================================

def main():

    st.title("🧭 FAJ System Trace")

    st.caption(
        "Архитектурная диагностика FAJ Platform v12.1 · "
        "только чтение"
    )

    st.info(
        "Эта страница не проверяет качество модели и не считает "
        "систему рабочей только потому, что Bootstrap зелёный. "
        "Она исследует фактические связи между файлами проекта."
    )

    # ========================================================
    # PROJECT OVERVIEW
    # ========================================================

    py_files = find_python_files()
    data_files = find_data_files()

    imports, import_errors = build_import_graph(py_files)

    reachable = find_reachable_files(
        ENTRYPOINT,
        imports,
    )

    imported_by = reverse_graph(imports)

    orphan_files = [
        path for path in py_files
        if path not in reachable
        and path != ENTRYPOINT
    ]

    # ========================================================
    # TOP STATUS
    # ========================================================

    st.divider()
    st.subheader("📊 Общая картина")

    c1, c2, c3, c4, c5 = st.columns(5)

    with c1:
        st.metric(
            "Python файлов",
            len(py_files),
        )

    with c2:
        st.metric(
            "Достижимы от Streamlit",
            len(reachable),
        )

    with c3:
        st.metric(
            "Не достижимы",
            len(orphan_files),
        )

    with c4:
        st.metric(
            "Ошибки анализа",
            len(import_errors),
        )

    with c5:
        st.metric(
            "Data файлов",
            len(data_files),
        )

    # ========================================================
    # ARCHITECTURE VERDICT
    # ========================================================

    st.divider()
    st.subheader("🚦 Архитектурный verdict")

    if len(import_errors) == 0:
        st.success(
            "AST-анализ импортов завершён без синтаксических ошибок."
        )
    else:
        st.error(
            f"Обнаружено проблем при анализе импортов: "
            f"{len(import_errors)}"
        )

    if orphan_files:
        st.warning(
            f"Найдено {len(orphan_files)} Python-файлов, "
            "которые не обнаружены в цепочке от streamlit_app.py."
        )
    else:
        st.success(
            "Все Python-файлы достижимы из главной точки входа."
        )

    st.caption(
        "Важно: 'не достижим' означает только отсутствие "
        "статического пути импорта от Streamlit. "
        "Это НЕ автоматический приговор 'файл можно удалить'."
    )

    # ========================================================
    # MAIN CHAIN
    # ========================================================

    st.divider()
    st.subheader("⛓️ Основная цепочка FAJ")

    show_expected_chain(
        reachable,
        imports,
    )

    # ========================================================
    # DIRECT IMPORTS OF ENTRYPOINT
    # ========================================================

    st.divider()
    st.subheader("🚪 Что непосредственно подключает Streamlit")

    entry_imports = sorted(
        imports.get(
            ENTRYPOINT,
            set(),
        ),
        key=str,
    )

    if entry_imports:

        rows = []

        for target in entry_imports:

            rows.append(
                {
                    "Файл": relative_path(target),
                    "Статус": (
                        "🟢 найден"
                        if target.exists()
                        else "🔴 отсутствует"
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.warning(
            "Не удалось определить прямые импорты "
            "из streamlit_app.py."
        )

    # ========================================================
    # FULL REACHABILITY
    # ========================================================

    st.divider()
    st.subheader("🟢 Файлы в цепочке Streamlit")

    reachable_rows = []

    for path in sorted(
        reachable,
        key=lambda p: relative_path(p),
    ):

        reachable_rows.append(
            {
                "Файл": relative_path(path),
                "Тип": classify_file(path),
                "Импортируется из": len(
                    imported_by.get(path, set())
                ),
            }
        )

    if reachable_rows:

        st.dataframe(
            pd.DataFrame(reachable_rows),
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # ORPHANS
    # ========================================================

    st.divider()
    st.subheader("🟡 Файлы вне обнаруженной цепочки")

    st.warning(
        "Эти файлы НЕ удаляем автоматически. "
        "Сначала проверяем, не вызываются ли они динамически, "
        "через Streamlit, scheduler, handlers, CLI или другие механизмы."
    )

    orphan_rows = []

    for path in sorted(
        orphan_files,
        key=lambda p: relative_path(p),
    ):

        orphan_rows.append(
            {
                "Файл": relative_path(path),
                "Категория": classify_file(path),
                "Legacy-кандидат": (
                    "🔴"
                    if is_legacy_candidate(path)
                    else ""
                ),
                "Импортов": len(
                    imported_by.get(path, set())
                ),
            }
        )

    if orphan_rows:

        st.dataframe(
            pd.DataFrame(orphan_rows),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.success(
            "Отдельных orphan-файлов не обнаружено."
        )

    # ========================================================
    # LEGACY
    # ========================================================

    st.divider()
    st.subheader("🔴 Legacy-кандидаты")

    legacy = []

    for path in py_files:

        if is_legacy_candidate(path):

            legacy.append(
                {
                    "Файл": relative_path(path),
                    "Достижим": (
                        "🟢 Да"
                        if path in reachable
                        else "🔴 Нет"
                    ),
                    "Причина": legacy_reason(path),
                }
            )

    if legacy:

        st.dataframe(
            pd.DataFrame(legacy),
            use_container_width=True,
            hide_index=True,
        )

        st.warning(
            "Legacy пока только помечен. "
            "Ничего не удаляется."
        )

    else:

        st.success(
            "Явных legacy-кандидатов по имени не найдено."
        )

    # ========================================================
    # DUPLICATES
    # ========================================================

    st.divider()
    st.subheader("🧬 Возможные дубликаты")

    duplicate_groups = detect_duplicates(py_files)

    if duplicate_groups:

        for group_name, paths in duplicate_groups.items():

            st.markdown(
                f"### {group_name}"
            )

            rows = []

            for path in paths:

                rows.append(
                    {
                        "Файл": relative_path(path),
                        "Достижим": (
                            "🟢"
                            if path in reachable
                            else "🟡"
                        ),
                    }
                )

            st.dataframe(
                pd.DataFrame(rows),
                use_container_width=True,
                hide_index=True,
            )

    else:

        st.success(
            "По именам потенциальных дубликатов не найдено."
        )

    # ========================================================
    # DANGEROUS FILES
    # ========================================================

    st.divider()
    st.subheader("⚠️ Файлы с потенциально опасными операциями")

    dangerous = detect_dangerous_files(py_files)

    if dangerous:

        dangerous_rows = []

        for path, operations in dangerous.items():

            dangerous_rows.append(
                {
                    "Файл": relative_path(path),
                    "Операции": ", ".join(
                        sorted(operations)
                    ),
                    "Достижим": (
                        "🟢 Да"
                        if path in reachable
                        else "🟡 Нет"
                    ),
                }
            )

        st.dataframe(
            pd.DataFrame(dangerous_rows),
            use_container_width=True,
            hide_index=True,
        )

        st.error(
            "Наличие DELETE/DROP/TRUNCATE в файле "
            "не означает, что операция выполняется сейчас. "
            "Нужно отдельно проверить путь вызова."
        )

    else:

        st.success(
            "Опасных SQL-операций по статическому анализу не найдено."
        )

    # ========================================================
    # RUNTIME MODULES
    # ========================================================

    st.divider()
    st.subheader("🧠 Что реально загружено в текущем процессе")

    runtime_rows = []

    for module_name, module in sorted(
        sys.modules.items()
    ):

        if not module_name.startswith("app"):
            continue

        module_file = getattr(
            module,
            "__file__",
            None,
        )

        if not module_file:
            continue

        try:
            path = Path(module_file).resolve()
        except Exception:
            continue

        if ROOT_DIR in path.parents or path == ROOT_DIR:

            runtime_rows.append(
                {
                    "Module": module_name,
                    "Файл": relative_path(path),
                }
            )

    if runtime_rows:

        st.dataframe(
            pd.DataFrame(runtime_rows),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.warning(
            "В текущем процессе app-модули не обнаружены."
        )

    # ========================================================
    # DATA
    # ========================================================

    st.divider()
    st.subheader("💾 Data Layer")

    data_rows = []

    for path in data_files:

        size = 0

        try:
            size = path.stat().st_size
        except Exception:
            pass

        data_rows.append(
            {
                "Файл": relative_path(path),
                "Размер KB": round(
                    size / 1024,
                    1,
                ),
                "Тип": path.suffix.lower(),
            }
        )

    if data_rows:

        st.dataframe(
            pd.DataFrame(data_rows),
            use_container_width=True,
            hide_index=True,
        )

    # ========================================================
    # IMPORT ERRORS
    # ========================================================

    st.divider()
    st.subheader("🔴 Ошибки анализа импортов")

    if import_errors:

        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Файл": relative_path(path),
                        "Ошибка": error,
                    }
                    for path, error in import_errors.items()
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    else:

        st.success(
            "Ошибок AST-разбора Python-файлов не обнаружено."
        )

    # ========================================================
    # FILE TREE
    # ========================================================

    st.divider()
    st.subheader("📁 Полное дерево Python")

    tree_rows = []

    for path in sorted(
        py_files,
        key=lambda p: relative_path(p),
    ):

        tree_rows.append(
            {
                "Файл": relative_path(path),
                "В цепочке": (
                    "🟢"
                    if path in reachable
                    else "🟡"
                ),
                "Legacy": (
                    "🔴"
                    if is_legacy_candidate(path)
                    else ""
                ),
                "Опасный": (
                    "⚠️"
                    if path in dangerous
                    else ""
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(tree_rows),
        use_container_width=True,
        hide_index=True,
    )

    # ========================================================
    # FINAL
    # ========================================================

    st.divider()

    st.subheader("🎯 Что делать дальше")

    st.markdown(
        """
### Этап 1 — сейчас

**Ничего не удаляем.**

Сначала определяем:

`Streamlit → Pages → Managers → Core → Models → Database`

### Этап 2

Разбираем:

- orphan-файлы;
- legacy;
- дубликаты;
- старые loaders;
- старые engines;
- старые learning-модули.

### Этап 3

Для каждого подозрительного файла принимаем одно решение:

🟢 оставить  
🟡 проверить  
🔴 вывести из архитектуры

### Этап 4

Только после этого:

**чинить реальную рабочую цепочку FAJ.**
"""
    )


# ============================================================
# FILE DISCOVERY
# ============================================================

def find_python_files() -> List[Path]:

    result = []

    for path in ROOT_DIR.rglob("*.py"):

        if any(
            part.startswith(".")
            for part in path.relative_to(ROOT_DIR).parts
        ):
            continue

        if "__pycache__" in path.parts:
            continue

        result.append(
            path.resolve()
        )

    return result


def find_data_files() -> List[Path]:

    if not DATA_DIR.exists():
        return []

    result = []

    for path in DATA_DIR.rglob("*"):

        if path.is_file():

            result.append(
                path.resolve()
            )

    return result


# ============================================================
# AST IMPORT GRAPH
# ============================================================

def build_import_graph(
    py_files: List[Path],
) -> Tuple[
    Dict[Path, Set[Path]],
    Dict[Path, str],
]:

    imports = defaultdict(set)
    errors = {}

    file_map = {
        module_name_from_path(path): path
        for path in py_files
    }

    for path in py_files:

        try:

            source = path.read_text(
                encoding="utf-8"
            )

            tree = ast.parse(
                source,
                filename=str(path),
            )

        except Exception as e:

            errors[path] = str(e)
            continue

        current_module = module_name_from_path(
            path
        )

        for node in ast.walk(tree):

            imported_names = []

            if isinstance(
                node,
                ast.Import,
            ):

                imported_names = [
                    alias.name
                    for alias in node.names
                ]

            elif isinstance(
                node,
                ast.ImportFrom,
            ):

                if node.module:

                    imported_names = [
                        node.module
                    ]

            for imported in imported_names:

                target = resolve_import(
                    imported,
                    current_module,
                    file_map,
                )

                if target:

                    imports[path].add(
                        target
                    )

    return dict(imports), errors


def resolve_import(
    imported: str,
    current_module: str,
    file_map: Dict[str, Path],
) -> Path | None:

    if imported in file_map:
        return file_map[imported]

    parts = imported.split(".")

    for i in range(
        len(parts),
        0,
        -1,
    ):

        candidate = ".".join(
            parts[:i]
        )

        if candidate in file_map:

            return file_map[candidate]

    return None


def module_name_from_path(
    path: Path,
) -> str:

    relative = path.relative_to(
        ROOT_DIR
    )

    parts = list(
        relative.with_suffix("").parts
    )

    if parts and parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts)


# ============================================================
# REACHABILITY
# ============================================================

def find_reachable_files(
    entrypoint: Path,
    imports: Dict[Path, Set[Path]],
) -> Set[Path]:

    reachable = set()

    if not entrypoint.exists():
        return reachable

    queue = deque(
        [entrypoint.resolve()]
    )

    while queue:

        current = queue.popleft()

        if current in reachable:
            continue

        reachable.add(current)

        for target in imports.get(
            current,
            set(),
        ):

            if target not in reachable:
                queue.append(target)

    return reachable


def reverse_graph(
    graph: Dict[Path, Set[Path]],
) -> Dict[Path, Set[Path]]:

    result = defaultdict(set)

    for source, targets in graph.items():

        for target in targets:

            result[target].add(
                source
            )

    return dict(result)


# ============================================================
# CLASSIFICATION
# ============================================================

def classify_file(
    path: Path,
) -> str:

    rel = relative_path(path)

    if rel == "streamlit_app.py":
        return "ENTRYPOINT"

    if "/pages/" in rel:
        return "STREAMLIT PAGE"

    if "/core/" in rel:
        return "CORE"

    if "/models/" in rel:
        return "MODEL"

    if "/database" in rel:
        return "DATABASE"

    if "/passports/" in rel:
        return "PASSPORT"

    if "/parsers/" in rel:
        return "PARSER"

    if "/loaders/" in rel:
        return "LOADER"

    if "/services/" in rel:
        return "SERVICE"

    if "/managers/" in rel:
        return "MANAGER"

    if "/learning/" in rel:
        return "LEARNING"

    if "/brain/" in rel:
        return "BRAIN"

    if "/monitoring/" in rel:
        return "MONITORING"

    return "OTHER"


def relative_path(
    path: Path,
) -> str:

    try:
        return str(
            path.relative_to(ROOT_DIR)
        ).replace("\\", "/")
    except Exception:
        return str(path)


# ============================================================
# LEGACY
# ============================================================

LEGACY_PATTERNS = [
    "old",
    "legacy",
    "deprecated",
    "backup",
    "bak",
]


def is_legacy_candidate(
    path: Path,
) -> bool:

    name = path.name.lower()

    return any(
        pattern in name
        for pattern in LEGACY_PATTERNS
    )


def legacy_reason(
    path: Path,
) -> str:

    name = path.name.lower()

    reasons = []

    for pattern in LEGACY_PATTERNS:

        if pattern in name:
            reasons.append(
                f"name contains '{pattern}'"
            )

    return "; ".join(reasons)


# ============================================================
# DUPLICATES
# ============================================================

def detect_duplicates(
    py_files: List[Path],
) -> Dict[str, List[Path]]:

    groups = defaultdict(list)

    for path in py_files:

        stem = path.stem.lower()

        normalized = re.sub(
            r"(_old|_legacy|_engine|_model|_manager)$",
            "",
            stem,
        )

        groups[normalized].append(
            path
        )

    return {
        name: paths
        for name, paths in groups.items()
        if len(paths) > 1
    }


# ============================================================
# DANGEROUS SQL
# ============================================================

DANGEROUS_PATTERNS = {
    "DELETE": re.compile(
        r"\bDELETE\s+FROM\b",
        re.IGNORECASE,
    ),
    "DROP": re.compile(
        r"\bDROP\s+(TABLE|DATABASE|INDEX)\b",
        re.IGNORECASE,
    ),
    "TRUNCATE": re.compile(
        r"\bTRUNCATE\b",
        re.IGNORECASE,
    ),
}


def detect_dangerous_files(
    py_files: List[Path],
) -> Dict[Path, Set[str]]:

    result = {}

    for path in py_files:

        try:

            source = path.read_text(
                encoding="utf-8"
            )

        except Exception:
            continue

        found = set()

        for operation, pattern in DANGEROUS_PATTERNS.items():

            if pattern.search(source):

                found.add(
                    operation
                )

        if found:

            result[path] = found

    return result


# ============================================================
# EXPECTED FAJ CHAIN
# ============================================================

def show_expected_chain(
    reachable: Set[Path],
    imports: Dict[Path, Set[Path]],
):

    expected = [
        (
            "1",
            "Streamlit Entry Point",
            ROOT_DIR / "streamlit_app.py",
        ),
        (
            "2",
            "Prediction Manager",
            APP_DIR / "core" / "prediction_manager.py",
        ),
        (
            "3",
            "Prediction Pipeline",
            APP_DIR / "core" / "prediction_pipeline.py",
        ),
        (
            "4",
            "FAJ Core",
            APP_DIR / "core" / "faj_core.py",
        ),
        (
            "5",
            "xG / Poisson / Monte Carlo",
            None,
        ),
        (
            "6",
            "Database",
            APP_DIR / "database.py",
        ),
    ]

    rows = []

    for number, role, path in expected:

        if path is None:

            model_paths = [
                APP_DIR / "models" / "xg_model.py",
                APP_DIR / "models" / "poisson_model.py",
                APP_DIR / "models" / "monte_carlo_model.py",
            ]

            existing = [
                p for p in model_paths
                if p.exists()
            ]

            reachable_models = [
                p for p in existing
                if p in reachable
            ]

            rows.append(
                {
                    "Этап": number,
                    "Компонент": role,
                    "Файлы": ", ".join(
                        relative_path(p)
                        for p in existing
                    ) or "не найден",
                    "В цепочке": (
                        "🟢"
                        if reachable_models
                        else "🔴"
                    ),
                }
            )

        else:

            rows.append(
                {
                    "Этап": number,
                    "Компонент": role,
                    "Файлы": relative_path(path),
                    "В цепочке": (
                        "🟢"
                        if path in reachable
                        else "🔴"
                    ),
                }
            )

    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()
