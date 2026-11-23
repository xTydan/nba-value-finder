# Analysis methodology

## Candidate discovery
Start with actual pre-game player prop markets. Every line must include event, scheduled start, player, market, side, line, decimal odds, bookmaker/source and capture timestamp. Reject stale, suspended, mismatched or incomplete offers. Keep each bookmaker price attached to its source.

## Recent form
For each candidate calculate L5/L10 hit rates against the exact line, mean, median, dispersion, minutes and outcome margin. These are descriptive indicators, not model probabilities. Over and Under are evaluated independently; push settlement is market-specific.

## Teammate absence impact
For each relevant teammate, split target-player game logs into games where that teammate was confirmed OUT, ACTIVE, or UNKNOWN. Exclude UNKNOWN from the split. Compare per-game and per-minute production, minutes and available role/usage indicators. Account for multiple simultaneous absences and role changes. Report sample sizes and raw differences. Shrink small-sample estimates toward the player's overall baseline; never treat a tiny split as causal evidence.

A teammate's absence may change opportunities, but opponent, game script, other injuries and coaching decisions confound the comparison. Show sample counts and confidence/uncertainty, not just a single uplift.

## Context
Add projected minutes, confirmed injury status, pace, opponent role/position defense, rest, home/away and blowout risk only when supported by timestamped sources. Missing values reduce confidence; they are not silently replaced with favorable assumptions.

## Probability and value
Estimate a full outcome distribution and probability of the offered Over/Under. If both sides are available, remove vig proportionally to estimate market fair probability. Report model probability, market fair probability, edge and EV. For simple no-push settlement EV = p * decimal_odds - 1; integer lines and push rules require exact settlement treatment.

Never label a pick value solely because it hit in 8/10 recent games. Calibrate on out-of-sample historical predictions. Track Brier score, log loss, ROI, yield and closing-line value.

## Publication
Only publish a pick when the odds, line, player, event and timestamps are verified and fresh. If sources are unavailable, show no picks and explain why. The ranking has no fixed L5/L10 hit-rate cutoff.
