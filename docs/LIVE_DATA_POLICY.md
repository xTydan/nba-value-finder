# Live data policy

The scanner is designed to fetch source data on demand. A permanent local archive is not required for the first production version.

## Runtime data flow

1. Fetch the NBA schedule, box scores and player game logs from live public data endpoints when a scan runs.
2. Fetch the latest injury report and lineup information. A current injury report must never be mistaken for a historical ACTIVE/OUT log.
3. Fetch pre-match player-prop markets and prices only from **Superbet Poland** and/or **STS Poland**. Do not silently substitute DraftKings, FanDuel or an unrelated bookmaker.
4. Normalize player, team, event, market, line, side, decimal odds and source timestamp into one internal representation.
5. Reject suspended, in-play, stale, incomplete or unmatchable odds. Do not infer missing lines or prices.
6. Run the value model only after matching a real bookmaker line to a real NBA player/event and current source data.
7. Display source and timestamp next to every price. If a source is unavailable, show that it is unavailable rather than displaying cached prices as current.

## Caching and historical context

- In-memory cache may be used to reduce repeated requests; target refresh is 15 min.
- Cache is temporary and is not a user-facing historical database.
- Historical game logs can be fetched from the provider at scan time and analyzed in memory (L5/L10, season, home/away, per-minute rates).
- Historical teammate-absence splits require trustworthy historical availability labels. If a provider does not expose those labels, the app must mark the split unavailable; it must not infer old OUT statuses from today's injury report.
- Do not persist a long-term odds archive unless the user later explicitly wants line-movement analysis or backtesting. Model evaluation can initially use available historical box scores and a separately sourced odds archive if one becomes available.

## Bookmaker integration decision

ArbiScan documents a JSON API covering Polish Superbet and STS pre-match odds. It is an independent third-party service, not an official bookmaker API. Its published documentation describes a 7-day test key limited to 100 requests/day; regular API access is paid. Before adopting it, verify that its live NBA feed actually contains the required player-prop markets, not merely game-level basketball markets. The provider's own documentation warns that listed brands and markets do not guarantee a particular event or market is present.

Superbet's public website visibly publishes NBA player markets including points, rebounds, assists, threes and combo markets. This confirms the bookmaker has the required product, but public search snippets/pages are not a reliable production data feed. A direct website integration must be validated against current publicly displayed prices and the site's applicable terms.

STS should be treated as a separate source. Do not assume its public PDF schedule contains player props; validate the actual online market feed.

## Required configuration

- ODDS_PROVIDER: arbiscan, superbet_web, sts_web, or disabled
- ARBISCAN_API_KEY: server-side secret only; never expose it to browser code
- ODDS_BOOKMAKERS: default superbet,sts
- ODDS_MAX_AGE_SECONDS: default 900

The first implementation should prefer an authenticated, documented provider when available. Scraping is a fallback only when stable, permitted and verifiable.
