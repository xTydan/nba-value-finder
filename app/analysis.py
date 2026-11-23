from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Iterable

@dataclass
class GameLog:
    game_id: str
    date: str
    stats: dict[str, float]
    minutes: float
    teammate_status: dict[str, str]  # player_id -> active/out/unknown

def summarize_recent(logs: Iterable[GameLog], market: str, line: float, side: str = "over") -> dict:
    rows = [g for g in logs if market in g.stats]
    vals = [float(g.stats[market]) for g in rows]
    if not vals:
        return {"sample": 0, "hit_rate": None, "mean": None, "median": None, "stddev": None, "values": []}
    if side not in ("over", "under"):
        raise ValueError("side must be 'over' or 'under'")
    hits = sum(v > line if side == "over" else v < line for v in vals)
    pushes = sum(v == line for v in vals)
    return {"sample": len(vals), "hit_rate": hits / len(vals), "push_rate": pushes / len(vals),
            "mean": mean(vals), "median": median(vals), "stddev": pstdev(vals) if len(vals)>1 else 0.0,
            "values": vals}

def teammate_absence_split(logs: Iterable[GameLog], market: str, teammate_id: str,
                           prior_games: float = 8.0) -> dict:
    rows = [g for g in logs if market in g.stats and g.minutes > 0]
    out = [g for g in rows if g.teammate_status.get(teammate_id) == "out"]
    active = [g for g in rows if g.teammate_status.get(teammate_id) == "active"]
    unknown = len(rows) - len(out) - len(active)
    def rate(group):
        mins = sum(g.minutes for g in group)
        return sum(float(g.stats[market]) for g in group) / mins if mins else None
    baseline, out_rate, active_rate = rate(rows), rate(out), rate(active)
    shrunk = ((len(out)*out_rate + prior_games*baseline)/(len(out)+prior_games)
              if out_rate is not None and baseline is not None else None)
    return {"teammate_id": teammate_id, "out_games": len(out), "active_games": len(active),
            "unknown_games_excluded": unknown, "baseline_per_min": baseline,
            "out_per_min": out_rate, "active_per_min": active_rate,
            "shrunk_out_per_min": shrunk,
            "raw_difference_per_min": out_rate-active_rate if out_rate is not None and active_rate is not None else None,
            "warning": "Descriptive split, not causal; small samples are unstable."}

def implied_probability(decimal_odds: float) -> float:
    if decimal_odds <= 1: raise ValueError("Decimal odds must be greater than 1")
    return 1 / decimal_odds

def no_vig_over_probability(over_odds: float, under_odds: float) -> float:
    over, under = implied_probability(over_odds), implied_probability(under_odds)
    return over / (over + under)

def expected_value(model_probability: float, decimal_odds: float) -> float:
    if not 0 <= model_probability <= 1: raise ValueError("Probability must be in [0,1]")
    if decimal_odds <= 1: raise ValueError("Decimal odds must be greater than 1")
    return model_probability * decimal_odds - 1
