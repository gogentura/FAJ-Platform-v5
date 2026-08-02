#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Сравнение прогнозов
"""

import streamlit as st
import pandas as pd
import json
import os

DATA_DIR = "data"

def load_json(filename):
    path = os.path.join(DATA_DIR, filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def get_comparison_summary():
    comparison = load_json("comparison_log.json")
    if not comparison:
        return pd.DataFrame()
    df = pd.DataFrame(comparison)
    cols = ['match', 'faj_pred', 'expert_pred', 'actual', 
            'faj_correct', 'expert_correct', 'faj_score_correct', 'expert_score_correct']
    return df[[c for c in cols if c in df.columns]]

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
    st.markdown("### 📊 Сравнение прогнозов FAJ vs Эксперт")
    
    summary = get_comparison_summary()
    if summary.empty:
        st.info("Нет данных для сравнения. Загрузите данные 1-го тура через раздел '📥 Загрузка данных'.")
    else:
        rename_map = {
            'match': 'Матч',
            'faj_pred': 'Прогноз FAJ',
            'expert_pred': 'Прогноз эксперта',
            'actual': 'Факт',
            'faj_correct': 'FAJ совпал?',
            'expert_correct': 'Эксперт совпал?',
            'faj_score_correct': 'FAJ точный счёт?',
            'expert_score_correct': 'Эксперт точный счёт?'
        }
        summary = summary.rename(columns=rename_map)
        st.dataframe(summary, use_container_width=True, hide_index=True)
        
        stats = calculate_accuracy()
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Всего матчей", stats.get('total', 0))
        with col2:
            st.metric("FAJ (исход)", f"{stats.get('faj', 0)}%")
        with col3:
            st.metric("Эксперт (исход)", f"{stats.get('expert', 0)}%")
        with col4:
            st.metric("FAJ (точный счёт)", f"{stats.get('faj_score', 0)}%")
