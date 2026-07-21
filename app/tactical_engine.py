class TacticalEngine:
    def analyze(self, home_passport, away_passport, home_stats, away_stats):
        # Определяем стиль на основе атаки, защиты и владения
        home_style = self._style(home_passport, home_stats)
        away_style = self._style(away_passport, away_stats)
        
        # Совместимость
        compatibility = 70 + abs(home_passport["attack"] - away_passport["defense"]) * 0.3
        compatibility = min(100, round(compatibility, 1))
        
        summary = f"Домашний стиль: {home_style}, гостевой: {away_style}. "
        if compatibility > 75:
            summary += "Стили совместимы, матч открытый."
        else:
            summary += "Стили конфликтуют, матч тактический."
        
        return {
            "home_style": home_style,
            "away_style": away_style,
            "compatibility": compatibility,
            "summary": summary
        }
    
    def _style(self, passport, stats):
        attack = passport["attack"]
        defense = passport["defense"]
        control = passport["control"]
        if attack > 80 and control > 70:
            return "Атакующий контроль"
        elif attack > 80 and defense < 60:
            return "Атакующий без баланса"
        elif defense > 80 and attack < 65:
            return "Обороняющийся"
        elif control > 75 and defense > 70:
            return "Контроль с балансом"
        elif stats.get("avg_possession", 50) > 55 and stats.get("avg_goals", 0) > 1.5:
            return "Владение с атакой"
        else:
            return "Сбалансированный"
