# =========================================================
    # КНОПКА ОБНОВЛЕНИЯ РЕЗУЛЬТАТОВ
    # =========================================================
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Обновить результаты", use_container_width=True):
            with st.spinner("Обновление статусов матчей..."):
                from app.database import FAJDatabase
                db = FAJDatabase()
                
                matches = db.get_matches(limit=1000)
                updated = 0
                
                for m in matches:
                    match_id = m.get('id')
                    home_goals = m.get('home_goals')
                    away_goals = m.get('away_goals')
                    
                    if home_goals is not None and away_goals is not None:
                        try:
                            hg = int(home_goals)
                            ag = int(away_goals)
                            if hg >= 0 and ag >= 0:
                                with db._get_connection() as conn:
                                    cursor = conn.cursor()
                                    cursor.execute("""
                                        UPDATE matches SET status = 'FT' WHERE id = ?
                                    """, (match_id,))
                                    conn.commit()
                                    updated += 1
                        except:
                            pass
                
                st.success(f"✅ Обновлено статусов: {updated} матчей")
                st.rerun()
