#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
FAJ Platform v12.1
UI: Создание стартовых паспортов v1.0

Страница запускает корневой скрипт:
    create_initial_passports.py

Никакого SQL и никаких изменений database.py здесь нет.
"""

import runpy
from pathlib import Path

import streamlit as st


st.set_page_config(
    page_title="FAJ — Стартовые паспорта",
    page_icon="🛡️",
    layout="wide",
)

st.title("🛡️ Создание стартовых паспортов")
st.write(
    "Однократная инициализация паспортов v1.0 "
    "из реестра FAJ_CLUB_RATINGS."
)

st.warning(
    "Существующие паспорта не должны перезаписываться. "
    "После создания повторный запуск безопасен."
)

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT = ROOT / "create_initial_passports.py"

if not SCRIPT.exists():
    st.error(f"Не найден скрипт: {SCRIPT}")
    st.stop()

if st.button(
    "🚀 СОЗДАТЬ ВСЕ СТАРТОВЫЕ ПАСПОРТА",
    type="primary",
    use_container_width=True,
):
    try:
        with st.spinner("Создаю стартовые паспорта..."):
            namespace = runpy.run_path(str(SCRIPT))

            creator = namespace.get("create_all_initial_passports")

            if creator is None:
                st.error(
                    "В create_initial_passports.py "
                    "не найдена функция create_all_initial_passports()."
                )
                st.stop()

            report = creator()

        created = report.get("created", [])
        existing = report.get("existing", [])
        errors = report.get("errors", [])

        st.success(
            f"Готово. Создано новых паспортов: {len(created)}"
        )

        col1, col2, col3 = st.columns(3)
        col1.metric("Создано", len(created))
        col2.metric("Уже существовали", len(existing))
        col3.metric("Ошибок", len(errors))

        if created:
            st.subheader("Созданные паспорта")
            st.dataframe(
                created,
                use_container_width=True,
                hide_index=True,
            )

        if existing:
            st.subheader("Пропущены — уже существуют")
            st.dataframe(
                existing,
                use_container_width=True,
                hide_index=True,
            )

        if errors:
            st.subheader("Ошибки")
            for error in errors:
                st.error(str(error))

    except Exception as exc:
        st.error(f"Ошибка запуска: {exc}")
        st.exception(exc)
