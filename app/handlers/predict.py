from aiogram import types
from app.utils.formatter import format_prediction
from app.utils.explainer import explain_prediction
from app.database import get_db
from app.journal import Journal
from app.handlers.keyboard import get_main_keyboard

def load_passport(team):
    conn = get_db()
    row = conn.execute("SELECT * FROM passports WHERE team = ?", (team,)).fetchone()
    conn.close()
    return dict(row) if row else None

async def handle_predict(message: types.Message, core, journal):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Напиши две команды: Зенит Спартак", reply_markup=get_main_keyboard())
        return
    
    home, away = parts[0], parts[1]
    league = parts[2].upper() if len(parts) >= 3 and parts[2].upper() in ["EPL", "RPL", "UCL"] else "RPL"
    
    await message.answer(f"⏳ Анализирую {home} — {away} ({league})...", reply_markup=get_main_keyboard())
    
    try:
        result = core.predict_match(home, away, league)
        if "error" in result:
            await message.answer(f"❌ {result['error']}", reply_markup=get_main_keyboard())
            return
        
        home_pass = load_passport(home) or {}
        away_pass = load_passport(away) or {}
        factors = explain_prediction(home_pass, away_pass, result["xg"]["predicted"]["home"], result["xg"]["predicted"]["away"], league)
        
        text = format_prediction(
            home, away, league,
            result["xg"]["predicted"],
            result["decision"],
            result.get("top_scores", []),
            result.get("btts", 0.0),
            result.get("over25", 0.0),
            factors
        )
        
        journal.save(
            match=f"{home} — {away}",
            prediction={
                "winner": result["decision"]["winner_name"],
                "winner_probability": result["decision"]["winner_probability"],
                "xg_home": result["xg"]["predicted"]["home"],
                "xg_away": result["xg"]["predicted"]["away"],
                "expected_score": result["decision"]["expected_score"],
                "confidence": result["decision"]["confidence"]
            }
        )
        await message.answer(text, reply_markup=get_main_keyboard(), parse_mode="Markdown")
    except Exception as e:
        await message.answer("⚠️ Ошибка. Попробуйте позже.", reply_markup=get_main_keyboard())
