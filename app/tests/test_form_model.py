import unittest
from app.core.brain_contract import FormContext, PatternState
from app.core.form_model import FormModel

def ctx(results, difficulty=("средний",)*6, gf=1.5, ga=1.0, xg=1.5, xga=1.0,
        cw=0, ca=0, hu=2, awm=3, aw=1, awr=1):
    w, d, l = results.count("В"), results.count("Н"), results.count("П")
    return FormContext(
        team="TEST", matches_count=6, results=tuple(results),
        wins=w, draws=d, losses=l, points=w*3+d,
        home_matches=3, home_wins=2, home_draws=1, home_losses=0,
        away_matches=awm, away_wins=aw, away_draws=1, away_losses=max(0,awm-aw-1),
        goals_for_avg=gf, goals_against_avg=ga, xg_avg=xg, xga_avg=xga,
        difficulty=tuple(difficulty), consecutive_away_matches=ca,
        consecutive_wins=cw, home_unbeaten_count=hu, away_wins_recent=awr)

def pat(c):
    return PatternState(matches_count=6, wins=c.wins, draws=c.draws, losses=c.losses,
        points=c.points, consecutive_wins=c.consecutive_wins,
        consecutive_away_matches=c.consecutive_away_matches,
        home_matches=c.home_matches, home_wins=c.home_wins, home_draws=c.home_draws,
        home_losses=c.home_losses, home_unbeaten_count=c.home_unbeaten_count,
        away_matches=c.away_matches, away_wins=c.away_wins,
        away_draws=c.away_draws, away_losses=c.away_losses)

class TestFormModel(unittest.TestCase):
    def test_all_wins(self):
        c=ctx(["В"]*6,cw=6)
        r=FormModel().calculate(c,pat(c))
        self.assertEqual(r.form_score,1.0)
        self.assertEqual(r.consistency,1.0)
        self.assertEqual(r.gladiator_effect,1.0)

    def test_all_losses(self):
        c=ctx(["П"]*6)
        r=FormModel().calculate(c,pat(c))
        self.assertEqual(r.form_score,0.0)

    def test_trend(self):
        a=ctx(["П","П","П","В","В","В"])
        b=ctx(["В","В","В","П","П","П"])
        self.assertEqual(FormModel().calculate(a,pat(a)).trend,"improving")
        self.assertEqual(FormModel().calculate(b,pat(b)).trend,"declining")

    def test_lukaku(self):
        c=ctx(["Н"]*6,gf=.8,xg=1.8)
        self.assertGreater(FormModel().calculate(c,pat(c)).lukaku_effect,0)

    def test_dark_horse(self):
        c=ctx(["В"]*6,gf=1.6,xg=.9)
        self.assertGreater(FormModel().calculate(c,pat(c)).dark_horse_effect,0)

    def test_missing_xg(self):
        c=ctx(["В"]*6,xg=None)
        r=FormModel().calculate(c,pat(c))
        self.assertIsNone(r.xg_strength)
        self.assertIsNone(r.realization_strength)
        self.assertIsNone(r.dark_horse_effect)

if __name__=="__main__":
    unittest.main()
