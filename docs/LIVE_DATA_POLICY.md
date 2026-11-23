# Live data policy

The scanner fetches current source data on demand. A permanent local archive is not required for the first production version.

## Runtime data flow

1. Fetch the NBA schedule, box scores and player game logs from live public data endpoints when a scan runs.
2. Fetch the latest injury report and lineup information. A current injury report must never be mistaken for a historical ACTIVE/OUT log.
3. Fetch pre-match NBA player-prop markets and prices from a verifiable provider. Prefer Superbet Poland and STS Poland when they actually quote the market, but do not reject other reputable sources if they provide a usable free feed. Always display the actual bookmaker/source; never relabel a foreign book as Superbet or STS.
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

## Odds provider research (2026-11-23)

### First candidate: PropLine API

- Public documentation describes a free tier with 1,000 requests/day and API-key authentication. The key is obtained through a signup form; no paid subscription is required for the advertised free tier.
- NBA player markets are explicitly documented: points, rebounds, assists, threes, steals, blocks, turnovers, steals + blocks, PRA, P+R, P+A, R+A and more.
- The documented bulk endpoint can return all upcoming NBA events and requested player markets in one request. It supports filtering by bookmaker, timestamps, and maximum market age.
- Odds responses contain the bookmaker key/title, market key, player name, Over/Under, line (point), price and update timestamp.
- Historical odds movement, closing-line data and some analytics are paid-tier features. The initial app does not need those features.
- This is the strongest documented integration candidate found so far, but live NBA response coverage and exact free-tier access to current prices still need an authenticated smoke test. Do not claim the integration works until tested.
- Documentation: https://prop-line.com/docs
- API: https://api.prop-line.com/v1

### Secondary candidate: Betwatch

- Public NBA game pages show current player-prop lines and prices from multiple books, including some pages that list Superbet for game markets.
- A current game page was inspected on 2026-11-23. Its displayed player-prop section included players whose teams did not match the event (for example, Naz Reid and Coby White on a Grizzlies–Hornets page). This is a material event/player mapping problem.
- Therefore Betwatch is useful for manual comparison and as a research lead, but must not be ingested automatically until event-to-player association is independently validated. A wrong match association would corrupt the model.
- Public pages: https://betwatch.io/odds/nba

### Other candidates

- WagerWise offers a free-to-browse player-prop comparison page, but its API is described as beta with no SLA and requires a bearer token. Treat it as a backup, not the primary production feed.
- Stat Pick advertises an unauthenticated public API, but its developer page returned 404 when checked. Do not integrate until the API is independently reachable and documented.
- Important bookmaker limitation: PropLine's own bookmaker catalog lists Superbet PL and STS as NBA game-lines sources, but does not list NBA player props for either. It lists player props for selected other operators (for example, Lottomatica, ePlay24, William Hill IT, Novig and ProphetX). Thus PropLine is a candidate for real NBA player-prop odds from other books, not a confirmed solution for Superbet/STS player props. Bookmaker coverage must be verified from actual returned rows, not inferred from a logo or marketing list.

## Integration rules

- Never fabricate odds or use sample/demo odds as live data.
- Do not scrape around authentication, CAPTCHAs, access controls or other technical restrictions.
- Direct Superbet/STS website scraping is a fallback only if the public market data is accessible without bypassing controls, permitted by applicable terms, and can be matched to the correct event/player/market.
- Store API keys only as server-side environment variables or GitHub Actions/hosting secrets. Never put keys in frontend JavaScript, committed files, or browser storage.
- The initial provider should be configurable with ODDS_PROVIDER and ODDS_API_KEY. Keep bookmaker allowlists configurable; show the real bookmaker for every price.
- Reject stale prices (default maximum age 900 seconds), suspended markets, live markets, duplicate outcomes, malformed lines and event/player mismatches.
- Do not produce picks if the odds feed has no verified player props for the slate.

## Required configuration

- ODDS_PROVIDER: prop_line, betwatch_web (only after validation), superbet_web, sts_web, or disabled
- ODDS_API_KEY: server-side provider key; never expose it to browser code
- ODDS_BOOKMAKERS: optional comma-separated bookmaker allowlist; do not assume Superbet/STS are available
- ODDS_MAX_AGE_SECONDS: default 900

The first implementation should prefer a documented, free, authenticated provider when available. Scraping is a fallback only when stable, permitted and verifiable.
