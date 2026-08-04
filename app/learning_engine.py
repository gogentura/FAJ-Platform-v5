#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FAJ Learning Engine
Анализ ошибок и формирование рекомендаций
"""

from datetime import datetime  # ← ДОБАВЛЕНО
from app.database import FAJDatabase


def get_learning_report():
    """Формирует полный Learning Report"""
    db = FAJDatabase()
    records = db.get_learning_records(status='new')

    if not records:
        return {
            'date': datetime.now().strftime('%d.%m.%Y %H:%M'),
            'total_errors': 0,
            'status': 'no_errors',
            'recommendations': []
        }

    # Статистика
    total = len(records)
    critical = sum(1 for r in records if r['error_severity'] >= 4)
    major = sum(1 for r in records if r['error_severity'] == 3)
    minor = sum(1 for r in records if r['error_severity'] < 3)
    avg_severity = sum(r['error_severity'] for r in records) / total if total > 0 else 0

    # Типы ошибок
    error_types = {}
    for r in records:
        et = r['error_type']
        if et not in error_types:
            error_types[et] = {'count': 0, 'total_severity': 0}
        error_types[et]['count'] += 1
        error_types[et]['total_severity'] += r['error_severity']

    # Причины ошибок
    causes = {}
    for r in records:
        cause = r['cause_type']
        if cause and cause != 'unknown':
            if cause not in causes:
                causes[cause] = {'count': 0, 'total_severity': 0}
            causes[cause]['count'] += 1
            causes[cause]['total_severity'] += r['error_severity']

    # Команды с ошибками
    team_errors = {}
    for r in records:
        team = r['home_team']
        if team not in team_errors:
            team_errors[team] = {'count': 0, 'total_severity': 0}
        team_errors[team]['count'] += 1
        team_errors[team]['total_severity'] += r['error_severity']

    # Рекомендации
    recommendations = []

    if critical > 0:
        recommendations.append({
            'priority': '🔴 HIGH',
            'title': f'Критические ошибки ({critical})',
            'action': 'Проверить паспорта команд с ошибками',
            'details': 'Атака и оборона требуют корректировки'
        })

    for cause, data in causes.items():
        if data['count'] >= 2 and (data['total_severity'] / data['count']) >= 3:
            action_map = {
                'overestimated_attack_home': 'Уменьшить вес атаки для домашних команд',
                'overestimated_attack_away': 'Уменьшить вес атаки для гостевых команд',
                'underestimated_attack_home': 'Увеличить вес атаки для домашних команд',
                'underestimated_attack_away': 'Увеличить вес атаки для гостевых команд',
                'form_misjudgment': 'Увеличить вес формы в модели',
                'tactical_mismatch': 'Добавить тактические коэффициенты',
                'random_variance': 'Увеличить размер выборки'
            }
            recommendations.append({
                'priority': '🟡 MEDIUM',
                'title': f'Причина: {cause} ({data["count"]} ошибок)',
                'action': action_map.get(cause, 'Анализировать паттерны'),
                'details': f'Средняя severity: {data["total_severity"] / data["count"]:.1f}'
            })

    return {
        'date': datetime.now().strftime('%d.%m.%Y %H:%M'),
        'total_errors': total,
        'avg_severity': avg_severity,
        'critical': critical,
        'major': major,
        'minor': minor,
        'error_types': error_types,
        'causes': causes,
        'team_errors': team_errors,
        'recommendations': recommendations,
        'status': 'success'
    }


if __name__ == "__main__":
    report = get_learning_report()

    print("\n" + "=" * 60)
    print("📋 LEARNING REPORT")
    print("=" * 60)
    print(f"📅 Дата: {report['date']}")
    print(f"📊 Всего ошибок: {report['total_errors']}")

    if report['status'] == 'no_errors':
        print("✅ Нет ошибок для анализа. Модель работает стабильно.")
    else:
        print(f"   🔴 Critical: {report['critical']}")
        print(f"   🟡 Major: {report['major']}")
        print(f"   🟢 Minor: {report['minor']}")
        print(f"   📈 Avg severity: {report['avg_severity']:.1f}")

        print("\n📌 ТИПЫ ОШИБОК:")
        for et, data in report['error_types'].items():
            print(f"  • {et}: {data['count']}")

        print("\n🔍 ПРИЧИНЫ ОШИБОК:")
        for cause, data in report['causes'].items():
            avg = data['total_severity'] / data['count']
            print(f"  • {cause}: {data['count']} (avg severity: {avg:.1f})")

        print("\n🔧 РЕКОМЕНДАЦИИ:")
        for rec in report['recommendations']:
            print(f"  {rec['priority']} {rec['title']}")
            print(f"    → {rec['action']}")

    print("=" * 60)
