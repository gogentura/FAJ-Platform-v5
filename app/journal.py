from datetime import datetime
from app.database import get_db

class Journal:
    def save(self, match: str, prediction: dict, actual: dict = None):
        conn = get_db()
        conn.execute("""
            INSERT INTO journal (
                date, match, home_team, away_team,
                prediction, winner_prob, xg_home, xg_away,
                expected_score, actual_score, actual_winner,
                confidence, model_version, data_version, accuracy
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            match,
            match.split("—")[0].strip(),
            match.split("—")[1].strip(),
            prediction.get("winner", ""),
            prediction.get("winner_probability", 0),
            prediction.get("xg_home", 0),
            prediction.get("xg_away", 0),
            prediction.get("expected_score", ""),
            actual.get("score", "") if actual else "",
            actual.get("winner", "") if actual else "",
            prediction.get("confidence", 0),
            "5.1",
            datetime.now().strftime("%Y-%m-%d"),
            "pending"
        ))
        conn.commit()
        conn.close()

    def get_all(self, limit: int = 10):
        conn = get_db()
        # Получаем все записи, сортируем по убыванию id
        rows = conn.execute("SELECT * FROM journal ORDER BY id DESC").fetchall()
        conn.close()
        # Ограничиваем на уровне Python
        return [dict(r) for r in rows[:limit]]
