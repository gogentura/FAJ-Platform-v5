#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Audit Engine
Анализ ошибок прогнозов с определением ПРИЧИН
"""

import sqlite3
from datetime import datetime

from app.database import DB_FILE, FAJDatabase


def parse_score(score_str):
    """Парсит счёт '1:2' → (1, 2)"""
    if not score_str:
        return None, None
    parts = score_str.split(':')
    if len(parts) == 2:
        try:
            return int(parts[0]), int(parts[1])
        except ValueError:
            return None, None
    return None, None


def determine_cause(gold, error_type, xg_error):
    """Определяет ПРИЧИНУ ошибки"""
    causes = []

    if gold['faj_xg_home'] and gold['actual_xg_home']:
        if gold['faj_xg_home'] > gold['actual_xg_home'] + 0.3:
            causes.append('overestimated_attack_home')
        elif gold['faj_xg_home'] < gold['actual_xg_home'] - 0.3:
            causes.append('underestimated_attack_home')

    if gold['faj_xg_away'] and gold['actual_xg_away']:
        if gold['faj_xg_away'] > gold['actual_xg_away'] + 0.3:
            causes.append('overestimated_attack_away')
        elif gold['faj_xg_away'] < gold['actual_xg_away'] - 0.3:
            causes.append('underestimated_attack_away')

    if gold['faj_rating_home'] and abs(gold['faj_rating_home'] - gold['faj_rating_away']) > 10:
        if error_type in ['score_error', 'xg_error']:
            causes.append('form_misjudgment')

    if error_type == 'market_error' and xg_error > 0.5:
        causes.append('tactical_mismatch')

    if not causes and error_type != 'correct':
        causes.append('random_variance')

    priority = [
        'overestimated_attack_home', 'overestimated_attack_away',
        'underestimated_attack_home', 'underestimated_attack_away',
        'form_misjudgment', 'tactical_mismatch', 'random_variance'
    ]
    for p in priority:
        if p in causes:
            return p

    return 'unknown'


def audit_match(gold_id):
    """Аудит одного матча с определением причины"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM gold_dataset WHERE id = ?", (gold_id,))
    gold = cursor.fetchone()

    if not gold:
        conn.close()
        return {'status': 'error', 'message': 'Запись не найдена'}

    if not gold['actual_score']:
        conn.close()
        return {'status': 'pending', 'message': 'Нет фактических данных'}

    # Сравнение счёта
    h1, a1 = parse_score(gold['faj_score'])
    h2, a2 = parse_score(gold['actual_score'])

    score_match = (h1 == h2 and a1 == a2) if (h1 is not None and h2 is not None) else False
    score_error = 0 if score_match else 1

    # Ошибка xG
    xg_error = 0.0
    if gold['faj_xg_home'] and gold['actual_xg_home']:
        xg_error += abs(gold['faj_xg_home'] - gold['actual_xg_home'])
    if gold['faj_xg_away'] and gold['actual_xg_away']:
        xg_error += abs(gold['faj_xg_away'] - gold['actual_xg_away'])

    # Ошибки рынков
    btts_error = 0
    if gold['faj_btts'] is not None and gold['actual_btts'] is not None:
        btts_error = 1 if gold['faj_btts'] != gold['actual_btts'] else 0

    total_25_error = 0
    total_35_error = 0
    if gold['faj_total_25'] is not None and gold['actual_total_25'] is not None:
        total_25_error = 1 if gold['faj_total_25'] != gold['actual_total_25'] else 0
    if gold['faj_total_35'] is not None and gold['actual_total_35'] is not None:
        total_35_error = 1 if gold['faj_total_35'] != gold['actual_total_35'] else 0

    # Тип ошибки
    if not score_match and xg_error > 0.5:
        error_type = "score_and_xg_error"
    elif not score_match:
        error_type = "score_error"
    elif xg_error > 0.5:
        error_type = "xg_error"
    elif btts_error or total_25_error or total_35_error:
        error_type = "market_error"
    else:
        error_type = "correct"

    # Причина
    cause_type = determine_cause(gold, error_type, xg_error)

    # Severity
    if error_type == "score_and_xg_error":
        error_severity = 5
    elif error_type == "score_error":
        error_severity = 4
    elif error_type == "xg_error":
        error_severity = 3
    elif error_type == "market_error":
        error_severity = 2
    else:
        error_severity = 1

    # Детали
    error_detail = []
    if not score_match:
        error_detail.append(f"Счёт: {gold['faj_score']} → {gold['actual_score']}")
    if xg_error > 0.5:
        error_detail.append(f"xG: {gold['faj_xg_home']:.2f}:{gold['faj_xg_away']:.2f} → {gold['actual_xg_home']:.2f}:{gold['actual_xg_away']:.2f}")
    if btts_error:
        error_detail.append(f"BTTS: {'ДА' if gold['faj_btts'] else 'НЕТ'} → {'ДА' if gold['actual_btts'] else 'НЕТ'}")
    if total_25_error:
        error_detail.append(f"ТБ 2.5: {'ДА' if gold['faj_total_25'] else 'НЕТ'} → {'ДА' if gold['actual_total_25'] else 'НЕТ'}")
    if total_35_error:
        error_detail.append(f"ТБ 3.5: {'ДА' if gold['faj_total_35'] else 'НЕТ'} → {'ДА' if gold['actual_total_35'] else 'НЕТ'}")

    db = FAJDatabase()

    # Сохранение через database.py
    record_id = db.add_learning_record({
        'gold_id': gold['id'],
        'match_id': gold['match_id'],
        'home_team': gold['home_team'],
        'away_team': gold['away_team'],
        'faj_score': gold['faj_score'],
        'actual_score': gold['actual_score'],
        'faj_xg_home': gold['faj_xg_home'],
        'faj_xg_away': gold['faj_xg_away'],
        'actual_xg_home': gold['actual_xg_home'],
        'actual_xg_away': gold['actual_xg_away'],
        'error_score': score_error,
        'error_xg': xg_error,
        'error_btts': btts_error,
        'error_total_25': total_25_error,
        'error_total_35': total_35_error,
        'error_type': error_type,
        'cause_type': cause_type,
        'error_severity': error_severity,
        'error_detail': '; '.join(error_detail) if error_detail else 'Ошибок нет',
        'status': 'new'
    })

    # Обновляем статус gold_dataset
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE gold_dataset SET status = 'audited', updated_at = ? WHERE id = ?",
        (datetime.now().isoformat(), gold['id'])
    )
    conn.commit()
    conn.close()

    return {
        'status': 'success',
        'match': f"{gold['home_team']} — {gold['away_team']}",
        'score_match': score_match,
        'error_type': error_type,
        'cause_type': cause_type,
        'severity': error_severity,
        'record_id': record_id
    }


def audit_all_pending():
    """Аудит всех матчей со статусом 'pending' или 'completed'"""
    db = FAJDatabase()
    pending = db.get_gold_pending()

    results = []
    for gold in pending:
        result = audit_match(gold['id'])
        if result and result['status'] == 'success':
            results.append(result)
            icon = "✅" if result['score_match'] else "❌"
            print(f"{icon} {result['match']} → {result['error_type']} (причина: {result['cause_type']}, severity: {result['severity']})")

    return results


if __name__ == "__main__":
    print("🔍 Запуск аудита...")
    results = audit_all_pending()
    print(f"\n📊 Аудировано {len(results)} матчей")
