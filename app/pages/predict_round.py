# ========================================================
# 9. SAVE DATABASE TO GITHUB
# ========================================================
st.divider()
st.subheader("💾 Сохранение прогнозов")
st.caption(
    "После расчёта всех прогнозов FAJ и ввода прогнозов Директора "
    "сохраните текущую базу в GitHub."
)
if st.button(
    "💾 СОХРАНИТЬ ПРОГНОЗЫ ТУРА В GITHUB",
    type="primary",
    use_container_width=True,
):
    try:
        from app.github_db_sync import save_database_to_github
        result = save_database_to_github()
        st.success(
            f"✅ Прогнозы тура сохранены в GitHub. "
            f"Размер базы: {result.get('size', 0):,} байт."
        )
        logger.info(
            "PREDICTION ROUND SAVED TO GITHUB | %s",
            result,
        )
    except Exception as exc:
        logger.exception(
            "Ошибка сохранения прогнозов тура в GitHub"
        )
        st.error(
            f"❌ Ошибка сохранения базы в GitHub: {exc}"
        )
