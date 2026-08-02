#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Загрузка данных
"""

import streamlit as st
import json
import os
from datetime import datetime

DATA_DIR = "data"

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return [] if "log" in filename or "memory" in filename else {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return [] if "log" in filename or "memory" in filename else {}

def save_json(filename, data):
    path = os.path.join(DATA_DIR, filename)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_outcome(score):
    if not score or score == "-":
        return None
    try:
        h, a = map(int, score.split(':'))
        if h > a:
            return "П1"
        elif h == a:
            return "X"
        else:
            return "П2"
    except:
        return None

def load_tour1_to_comparison():
    tour1 = load_json("tour1_results.json")
    comparison = load_json("comparison_log.json")
    
    if not tour1:
        return {"status": "error", "message": "Файл tour1_results.json не найден или пуст"}
    
    existing = {r.get('match') for r in comparison}
    new_records = 0
    
    for match, data in tour1.items():
        if match in existing:
            continue
        
        faj_pred = data.get('faj', '—')
        expert_pred = data.get('expert', '—')
        actual = data.get('actual', '—')
        
        faj_outcome = get_outcome(faj_pred)
        expert_outcome = get_outcome(expert_pred)
        actual_outcome = get_outcome(actual)
        
        record = {
            'match': match,
            'faj_pred': faj_pred,
            'expert_pred': expert_pred,
            'actual': actual,
            'faj_outcome': faj_outcome,
            'expert_outcome': expert_outcome,
            'actual_outcome': actual_outcome,
            'faj_correct': faj_outcome == actual_outcome,
            'expert_correct': expert_outcome == actual_outcome,
            'faj_score_correct': faj_pred == actual,
            'expert_score_correct': expert_pred == actual,
            'timestamp': datetime.now().isoformat()
        }
        
        comparison.append(record)
        new_records += 1
    
    if new_records > 0:
        save_json("comparison_log.json", comparison)
    
    return {
        "status": "success",
        "new_records": new_records,
        "total_records": len(comparison)
    }

def render():
    st.markdown("### 📥 Загрузка данных в систему")
    
    from app.database import FAJDatabase
    db = FAJDatabase()
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div style="background: rgba(30, 30, 50, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 16px;">
            <h4 style="color: #f3f4f6; margin-top: 0;">📊 Данные 1-го тура</h4>
            <p style="color: #9ca3af;">Загрузить прогнозы и результаты 1-го тура в систему для сравнения.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div style="background: rgba(30, 30, 50, 0.8); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 16px;">
            <h4 style="color: #f3f4f6; margin-top: 0;">🗄️ Миграция в SQLite</h4>
            <p style="color: #9ca3af;">Перенести все данные из JSON в постоянную базу данных.</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.divider()
    
    if st.button("📥 Загрузить данные 1-го тура", use_container_width=True, type="primary"):
        with st.spinner("Загрузка данных..."):
            result = load_tour1_to_comparison()
        
        if result["status"] == "error":
            st.error(f"❌ {result['message']}")
        else:
            st.success(f"✅ Данные загружены! Добавлено {result['new_records']} записей.")
    
    st.divider()
    
    if st.button("🗄️ Перенести данные в SQLite", use_container_width=True):
        with st.spinner("Миграция данных в SQLite..."):
            result = db.migrate_from_json()
        
        if result.get("errors"):
            st.warning(f"⚠️ Миграция завершена с ошибками: {len(result['errors'])}")
            for err in result["errors"]:
                st.write(f"- {err}")
        else:
            st.success(f"✅ Миграция завершена! Паспортов: {result['passports']}, Матчей: {result['matches']}")
    
    st.divider()
    
    comparison = load_json("comparison_log.json")
    st.metric("Записей в сравнении (JSON)", len(comparison))
    db_status = db.get_status()
    st.metric("Записей в БД (SQLite)", db_status.get('matches', 0))
