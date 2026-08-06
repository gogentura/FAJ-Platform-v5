"""
=====================================================
FAJ Platform v12.0
Диагностическая страница

ТОЛЬКО UI. Вся логика в DiagnosticService.
=====================================================
"""

import streamlit as st
from datetime import datetime

from app.services.diagnostic_service import get_diagnostic_service


# ============================================================
# ИНИЦИАЛИЗАЦИЯ (set_page_config УЖЕ в streamlit_app.py)
# ============================================================

st.title("🔬 FAJ Platform v12.0 — Диагностика")

service = get_diagnostic_service()

if "last_diagnostic" not in st.session_state:
    st.session_state["last_diagnostic"] = service.get_cached_result()


# ============================================================
# HEALTH SCORE
# ============================================================

health = service.get_health_score()

col1, col2, col3, col4 = st.columns(4)
col1.metric("🟢 Health Score", f"{health['score']:.1f}%")
col2.metric("✅ Пройдено", health["passed"])
col3.metric("❌ Ошибок", health["total"] - health["passed"])
col4.metric("📊 Статус", health["status_label"].upper())

st.caption(f"Последнее обновление: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")
st.divider()


# ============================================================
# БОКОВАЯ ПАНЕЛЬ
# ============================================================

with st.sidebar:
    st.header("⚙️ Управление")

    if st.button("🔄 Полная диагностика", type="primary", use_container_width=True):
        with st.spinner("Проверка всех компонентов..."):
            result = service.run_all(save_history=True)
            st.session_state["last_diagnostic"] = result
        st.rerun()

    st.divider()

    if st.button("📊 База данных", use_container_width=True):
        st.session_state["last_diagnostic"] = {"checks": [service.check_database()]}

    if st.button("📋 Паспорта", use_container_width=True):
        st.session_state["last_diagnostic"] = {"checks": [service.check_passports()]}

    if st.button("⚙️ Prediction Pipeline", use_container_width=True):
        st.session_state["last_diagnostic"] = {"checks": [service.check_pipeline()]}

    if st.button("🎯 Prediction Manager", use_container_width=True):
        st.session_state["last_diagnostic"] = {"checks": [service.check_prediction()]}

    if st.button("🧠 Learning Engine", use_container_width=True):
        st.session_state["last_diagnostic"] = {"checks": [service.check_learning()]}

    if st.button("⚡ Производительность", use_container_width=True):
        st.session_state["last_diagnostic"] = {"checks": [service.check_performance()]}

    if st.button("📌 Версии", use_container_width=True):
        st.session_state["last_diagnostic"] = {"checks": [service.check_versions()]}

    if st.button("🔍 SQLite Integrity", use_container_width=True):
        st.session_state["last_diagnostic"] = {"checks": [service.check_sqlite_integrity()]}

    st.divider()

    if st.button("📜 История диагностик", use_container_width=True):
        history = service.get_history()
        st.session_state["last_diagnostic"] = {"history": history}

    st.divider()

    if st.button("📤 Экспорт HTML", use_container_width=True):
        html_data = service.export_html()
        st.download_button(
            label="Скачать отчёт",
            data=html_data,
            file_name=f"faj_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
            mime="text/html",
            use_container_width=True
        )

    st.divider()

    if st.button("🗑️ Очистить", use_container_width=True):
        st.session_state["last_diagnostic"] = None
        st.rerun()


# ============================================================
# РЕЗУЛЬТАТЫ
# ============================================================

result = st.session_state.get("last_diagnostic")

if result:
    if "history" in result:
        st.subheader("📜 История диагностик")
        history = result["history"]
        if history:
            data = []
            for entry in history:
                summary = entry.get("summary", {})
                data.append({
                    "Дата": entry.get("timestamp", "")[:16],
                    "Статус": summary.get("status", "N/A"),
                    "Пройдено": f"{summary.get('passed', 0)}/{summary.get('total', 0)}",
                    "Крит. ошибок": summary.get("critical_fail", 0),
                    "Время": f"{entry.get('elapsed_seconds', 0):.1f}с"
                })
            st.dataframe(data, use_container_width=True)
        else:
            st.info("История диагностик пуста")
        st.session_state["last_diagnostic"] = None
        st.stop()

    checks = result.get("checks", [])

    if checks:
        for check in checks:
            name = check.get("name", "Unknown")
            status = check.get("status", "unknown")
            severity = check.get("severity", "info")
            details = check.get("details", {})
            error = check.get("error", None)
            duration = check.get("duration_ms", 0)

            if status == "pass":
                icon = "🟢"
            elif status == "warn":
                icon = "🟡"
            elif status == "fail":
                icon = "🔴"
            elif status == "info":
                icon = "ℹ️"
            else:
                icon = "⚪"

            sev_icon = {"critical": "🔥", "major": "⚠️", "minor": "ℹ️", "info": "📌"}.get(severity, "📌")

            with st.expander(f"{icon} {name} {sev_icon} ({duration:.0f}мс)", expanded=status != "pass"):
                if error:
                    st.error(f"❌ {error}")
                else:
                    if details:
                        cols = st.columns(min(len(details), 4))
                        for i, (key, value) in enumerate(details.items()):
                            cols[i % len(cols)].metric(
                                key.replace("_", " ").title(),
                                value if isinstance(value, str) else str(value)
                            )
                    else:
                        st.success("✅ Проверка пройдена")

        summary = result.get("summary", {})
        if summary:
            st.divider()
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("✅ Пройдено", summary.get("passed", 0))
            col2.metric("⚠️ Предупреждений", summary.get("warned", 0))
            col3.metric("❌ Ошибок", summary.get("failed", 0))
            col4.metric("🔥 Критических", summary.get("critical_fail", 0))

            status_icon = {
                "healthy": "🟢",
                "warning": "🟡",
                "degraded": "🟠",
                "critical": "🔴"
            }.get(summary.get("status", "unknown"), "⚪")

            if summary.get("status") == "healthy":
                st.success(f"{status_icon} Все компоненты работают корректно!")
            elif summary.get("status") == "warning":
                st.warning(f"{status_icon} Есть предупреждения, рекомендуется проверить")
            elif summary.get("status") == "degraded":
                st.warning(f"{status_icon} Есть ошибки, требуется внимание")
            else:
                st.error(f"{status_icon} Есть критические ошибки, требуется немедленное вмешательство")

        if "elapsed_seconds" in result:
            st.caption(f"⏱️ Время выполнения: {result['elapsed_seconds']:.2f}с")

else:
    st.info("👈 Выберите проверку в боковой панели или нажмите 'Полная диагностика'")


# ============================================================
# БЫСТРЫЙ ПРОГНОЗ
# ============================================================

st.divider()
st.subheader("🔮 Быстрый прогноз")

col1, col2 = st.columns(2)
with col1:
    home_team = st.selectbox(
        "Хозяева",
        ["Зенит", "Спартак", "ЦСКА", "Краснодар", "Динамо", "Ростов", "Локомотив"],
        key="home_select"
    )
with col2:
    away_team = st.selectbox(
        "Гости",
        ["Спартак", "Зенит", "ЦСКА", "Краснодар", "Динамо", "Ростов", "Локомотив"],
        key="away_select"
    )

if st.button("🔮 Прогноз", type="primary"):
    if home_team == away_team:
        st.error("Команды не могут быть одинаковыми")
    else:
        with st.spinner("Расчёт..."):
            from app.prediction.prediction_manager import get_prediction_manager
            pm = get_prediction_manager()
            result = pm.predict(home_team, away_team)

        if result.get("status") == "error":
            st.error(f"❌ {result.get('message')}")
        else:
            prediction = result.get("prediction", {}) or result

            cols = st.columns(3)
            cols[0].metric("Счёт", prediction.get("score", "N/A"))
            cols[1].metric("Уверенность", f"{prediction.get('confidence', {}).get('overall', 0)*100:.1f}%")
            cols[2].metric("Риск", prediction.get("risk", {}).get("level", "N/A"))

            probs = prediction.get("probability", {})
            st.write("**Вероятности:**")
            st.progress(probs.get("home", 0), text=f"🏠 Победа хозяев: {probs.get('home', 0)*100:.1f}%")
            st.progress(probs.get("draw", 0), text=f"🤝 Ничья: {probs.get('draw', 0)*100:.1f}%")
            st.progress(probs.get("away", 0), text=f"✈️ Победа гостей: {probs.get('away', 0)*100:.1f}%")
