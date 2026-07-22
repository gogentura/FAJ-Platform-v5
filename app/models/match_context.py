from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime

@dataclass
class MatchContext:
    match_id: str
    home_team: str
    away_team: str
    tournament: str = "RPL"
    stage: str = "regular"
    match_date: str = field(default_factory=lambda: datetime.now().isoformat())

    home_passport: Dict = field(default_factory=dict)
    away_passport: Dict = field(default_factory=dict)
    home_stats: Dict = field(default_factory=dict)
    away_stats: Dict = field(default_factory=dict)

    xg_home: Optional[float] = None
    xg_away: Optional[float] = None
    faj_rating_home: Optional[float] = None
    faj_rating_away: Optional[float] = None
    simulation: Dict = field(default_factory=dict)
    decision: Dict = field(default_factory=dict)
    tactical: Dict = field(default_factory=dict)

    processing_time: Optional[float] = None
    version: str = "5.0.1"
    errors: List[str] = field(default_factory=list)
