#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Platform v10.0 - Обучение модели
"""

import streamlit as st
import pandas as pd
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

def run_training():
    comparison = load_json("comparison_log.json")
    weights = load_json("weights_history.json")
    memory = load_json("learning_memory.json")
    
    if not comparison:
        return {"status": "error", "message": "Нет данных для обучения. Загрузите данные 1-го тура."}
    
    errors = []
    for record in comparison:
        if not record.get('faj_correct', False):
            errors.append({
                'match': record.get('match'),
                'faj_pred': record.get('faj_pred'),
                'actual': record.get('actual'),
                'faj_outcome': record.get('faj_outcome'),
                'actual_outcome': record.get('actual_outcome')
            })
    
    if not errors:
        return {"status": "info", "message": "Ошибок нет! Модель уже идеальна."}
    
    if weights:
        last_weights = weights[-1].get('weights', {})
    else:
        last_weights = {
            "attack": 0.18, "defense": 0.18, "control": 0.15,
            "efficiency": 0.12, "mentality": 0.10, "tempo": 0.07,
            "press": 0.05, "transition": 0.05, "flexibility": 0.05,
            "coach": 0.05
        }
    
    new_weights = last_weights.copy()
    
    attack_errors = sum(1 for e in errors if e.get('faj_outcome') == "П1" and e.get('actual_outcome') != "П1")
    defense_errors = sum(1 for e in errors if e.get('faj_outcome') == "П2" and e.get('actual_outcome') != "П2")
    total_errors = len(errors)
    
    new_weights["attack"] = max(0.10, new_weights.get("attack", 0.18) - 0.02 * (attack_errors / max(total_errors, 1)))
    new_weights["defense"] = max(0.10, new_weights.get("defense", 0.18) - 0.02 * (defense_errors / max(total_errors, 1)))
    new_weights["form"] = min(0.20, new_weights.get("form", 0.10) + 0.02 * (total_errors / 8))
    new_weights["mentality"] = min(0.15, new_weights.get("mentality", 0.10) + 0.01)
    
    total_weight = sum(new_weights.values())
    for k in new_weights:
        new_weights[k] = round(new_weights[k] / total_weight, 3)
    
    new_record = {
        "version": f"10.{len(weights)}",
        "timestamp": datetime.now().isoformat(),
        "weights": new_weights,
        "reason": f"Корректировка после 1-го тура (ошибок: {total_errors})",
        "errors_analyzed": total_errors,
        "attack_errors": attack_errors,
        "defense_errors": defense_errors
    }
    weights.append(new_record)
    save_json("weights_history.json", weights)
    
    memory_record = {
        "type": "training",
        "tour": 1,
        "errors_found": total_errors,
        "weights_updated": new_weights,
        "timestamp": datetime.now().isoformat()
    }
    memory.append(memory_record)
    save_json("learning_memory.json", memory)
    
    return {
        "status": "success",
        "errors_analyzed": total_errors,
        "new_weights": new_weights,
        "version": new_record["version"]
    }

def render():
    st.markdown("### 🧠 Самообучение модели")
    
    memory = load_json("learning_memory.json")
    weights = load_json("weights_history.json")
    comparison = load_json("comparison_log.json")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📚 Записей в памяти", len(memory))
    with col2:
        st.metric("⚖️ Обновлений весов", len(weights))
    with col3:
        st.metric("📊 Сравнений", len(comparison))
    
    st.divider()
    
    if st.button("🧠 Запустить обучение на 1-м туре", use_container_width=True, type="primary"):
        with st.spinner("Анализ ошибок и корректировка весов..."):
            result = run_training()
        
        if result["status"] == "error":
            st.error(f"❌ {result['message']}")
        elif result["status"] == "info":
            st.info(f"ℹ️ {result['message']}")
        else:
            st.success(f"✅ Обучение завершено! Проанализировано ошибок: {result['errors_analyzed']}")
            st.markdown("### ⚖️ Новые веса")
            st.json(result['new_weights'])
    
    st.divider()
    
    if weights:
        st.markdown("### ⚖️ Последние веса")
        st.json(weights[-1].get('weights', {}))
        
        st.markdown("### 📋 История изменений")
        df_weights = pd.DataFrame(weights)
        st.dataframe(df_weights, use_container_width=True, hide_index=True)
