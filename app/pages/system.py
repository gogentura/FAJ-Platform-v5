#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Система
"""

import streamlit as st
import pandas as pd
import json
import os

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

def calculate_accuracy():
    comparison = load_json("comparison_log.json")
    if not comparison:
        return {"total": 0, "faj": 0, "expert": 0, "faj_score": 0, "expert_score": 0}
    
    total = len(comparison)
    faj_correct = sum(1 for r in comparison if r.get('faj_correct', False))
    expert_correct = sum(1 for r in comparison if r.get('expert_correct', False))
    faj_score_correct = sum(1 for r in comparison if r.get('faj_score_correct', False))
    expert_score_correct = sum(1 for r in comparison if r.get('expert_score_correct', False))
    
    return {
        "total": total,
        "faj": round(faj_correct / total * 100, 1) if total > 0 else 0,
        "expert": round(expert_correct / total * 100, 1) if total > 0 else 0,
        "faj_score": round(faj_score_correct / total * 100, 1) if total > 0 else 0,
        "expert_score": round(expert_score_correct / total * 100, 1) if total > 0 else 0
    }

def render():
    st.markdown("### ⚙️ Системная информация")
    
    from app.database import FAJDatabase
    db = FAJDatabase()
    db_status = db.get_status()
    
    comparison = load_json("comparison_log.json")
    passports = load_json("passports_2026.json")
    memory = load_json("learning_memory.json")
    weights = load_json("weights_history.json")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Версия", "10.0")
    with col2:
        st.metric("Команд в БД", db_status.get('teams', 0))
    with col3:
        st.metric("Матчей в БД", db_status.get('matches', 0))
    with col4:
        st.metric("Записей журнала", db_status.get('journal', 0))
    
    st.divider()
    
    api_stats = db.get_api_stats_today()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("API Football запросов сегодня", api_stats.get('football_api', 0))
    with col2:
        st.metric("Football-data запросов сегодня", api_stats.get('football_data', 0))
    with col3:
        remaining = max(0, 100 - api_stats.get('football_api', 0))
        st.metric("Осталось (API Football)", remaining)
    
    st.divider()
    
    st.markdown("### ⚖️ Текущие веса")
    if weights:
        st.json(weights[-1].get('weights', {}))
    else:
        st.info("Нет сохранённых весов")
    
    st.divider()
    st.markdown("### 📊 Статистика точности")
    stats = calculate_accuracy()
    st.json(stats)
    
    st.divider()
    
    with st.expander("🗄️ Информация о базе данных"):
        st.json(db_status)
        st.caption(f"Путь к БД: {db_status.get('db_path', '—')}")
