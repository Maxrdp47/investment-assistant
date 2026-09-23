# RESEARCH_DATA_HEALTH_AND_COVERAGE

Version: `research-data-health-2026.09.23-v1`  
As of: `2026-09-23T07:47:00+00:00`  
Fingerprint: `70a6f59462558019eb14b2a818f70b5e25c89c5a3a91bf2a042d5393bb20ee43`  
Mode: read-only audit; no strategy, signal, trade, broker or order path.

## Data families

| ID | Family | Status | Collector | Scheduler | Last success | Last actual observation | Age days | N | PIT | Missingness | Blockers |
|---|---|---|---|---|---|---|---:|---:|---:|---|---|
| A | FX PIT Observer | PARTIAL | scripts/run_fx_pit_collector.py | InvestmentAssistant-FX-PIT-Observer (Ready) | 2026-09-23T07:45:05.150714+00:00 | 2026-09-23T07:31:22.473580+00:00 | 0.011 | 111 | 49.55% | 56 explicit missing/failure rows | policy-rate, expectations and bid/ask adapters not configured |
| B | Forecast / weekly universe | PARTIAL | scripts/run_forecasts.py + evening pipeline | InvestmentAssistantDailyForecasts (Ready) | 2026-09-22T22:44:53.534496+02:00 | 2026-09-22T22:44:44.499607+02:00 | 0.46 | 10874 | 82.113% | latest run failures=1; distinct assets=1725 | latest failed asset must remain explicit |
| C | COT positioning | HEALTHY | official CFTC forward collector via FX observer | InvestmentAssistant-FX-PIT-Observer (Ready) | 2026-09-23T07:31:22.473580+00:00 | 2026-09-23T07:31:22.473580+00:00 | 0.011 | 63439 | 100.0% | 194 report dates; first-seen evidence spans 31.342 days across 3 collection days | none |
| D | Fundamentals / SEC filings | NOT_CONFIGURED | parser/capability code only | not applicable | n/a | n/a | n/a | 0 | n/a | all required historical PIT fundamentals missing | SEC contact user-agent absent; SEC snapshot cache absent; historical issuer mapping absent |
| E | Company events / news | STALE | forward event sidecar only | not applicable | 2026-08-18T20:50:56.310331+00:00 | 2026-08-18T20:50:56.310331+00:00 | 35.456 | 24 | 100.0% | published_at absent in current records | no active scheduler; only 24 forward snapshots; published_at unavailable |
| F | Macro / rates / expectations | NOT_CONFIGURED | explicit missingness adapters in FX observer | InvestmentAssistant-FX-PIT-Observer (Ready) | n/a | n/a | n/a | 0 | n/a | expectations=0, macro=0, central_bank=0, carry=0 | no PIT expectation vintages; no actual policy-rate adapter |
| G | Politics / geopolitics / regulation | NOT_CONFIGURED | none | not applicable | n/a | n/a | n/a | 0 | n/a | no observations | no lawful approved PIT source or collector |
| H | Crypto market / regime | PARTIAL | frozen historical OHLCV projection only | not applicable | n/a | 2021-12-31 | n/a | 33675 | 100.0% | dominance, breadth, liquidity and on-chain PIT layers absent | no genuinely new PIT regime information layer |
| I | Price / OHLCV | HEALTHY | frozen historical projections + current forecast/FX collectors | InvestmentAssistantDailyForecasts (Ready) | 2026-09-22T22:44:53.534496+02:00 | 2026-09-22T22:44:44.499607+02:00 | 0.46 | 3070422 | 100.0% | source invalid bars retained separately | none |
| J | Identity / issuer / listing mapping | PARTIAL | versioned identity registry builder | not applicable | 2026-08-30T11:36:52.766800+00:00 | 2026-08-30 | n/a | 7560 | 100.0% | current mappings=7560; issuers=2153; pre-2026 history absent | historical issuer/listing validity before 2026-08-29 unavailable |
| K | Benchmark / relative strength inputs | PARTIAL | derived from PIT OHLCV | InvestmentAssistantDailyForecasts (Ready) | 2026-09-22T22:44:53.534496+02:00 | 2026-09-22T22:44:44.499607+02:00 | 0.46 | 3059548 | 100.0% | no independent benchmark collector | not a genuinely new information family |
| L | Volume / liquidity | PARTIAL | OHLCV collectors | InvestmentAssistantDailyForecasts (Ready) | 2026-09-22T22:44:53.534496+02:00 | 2026-09-22T22:44:44.499607+02:00 | 0.46 | 3040664 | 99.383% | positive-volume coverage=99.383%; bid/ask observations=0 | no reliable bid/ask or order-book adapter |
| M | Yield / dollar / risk regime | NOT_CONFIGURED | no dedicated reliable adapter | not applicable | n/a | n/a | n/a | 0 | n/a | yield/rate-expectation history absent | historical expectations unavailable; proxy reconstruction prohibited |

## Provenance, revision and research use

Scheduler query: `SUCCESS`.

| ID | Source | Period | published_at | first_seen_at | effective_at | Revision support | Provider errors / rate limits | Research use |
|---|---|---|---|---|---|---|---|---|
| A | Yahoo daily FX + official CFTC; unavailable adapters explicit | 2026-08-22T23:19:22.936215+00:00 → 2026-09-23T07:31:22.473580+00:00 | n/a | 2026-09-23T07:45:05.150714+00:00 | 2026-09-23T07:31:22.473580+00:00 | append-only revision table | 0 / NOT_REPORTED | forward FX price/context collection only; no strategy effect |
| B | existing market-data adapters and causal feature snapshots | 2026-08-02T22:30:20.764475+02:00 → 2026-09-22T22:44:44.499607+02:00 | n/a | 2026-09-22T22:44:44.499607+02:00 | 2026-09-22T22:44:44.499607+02:00 | immutable forecast snapshots | 1 / 0 | forecast evidence and current price collection; not a new challenger |
| C | official CFTC public reporting | 2026-08-04 → 2026-09-15 | n/a | 2026-09-23T07:31:22.473580+00:00 | 2026-09-23T07:31:22.473580+00:00 | append-only report and availability evidence | 0 / NOT_REPORTED | macro/futures context only after coverage gate |
| D | no configured SEC filing snapshot source | n/a → n/a | n/a | n/a | n/a | not operational | 0 / NOT_REPORTED | coverage gate only; no Development test |
| E | immutable forward signal snapshots; secondary aggregated | n/a → n/a | n/a | 2026-08-18T20:50:56.310331+00:00 | n/a | versioned append-only event records | 0 / NOT_REPORTED | diagnostic forward context only; insufficient for historical catalyst research |
| F | no reliable adapter configured | n/a → n/a | n/a | n/a | n/a | schema ready; no observations | 0 / NOT_REPORTED | coverage gate only; surprise remains UNKNOWN |
| G | none | n/a → n/a | n/a | n/a | n/a | none | 0 / NOT_REPORTED | not research-ready |
| H | frozen crypto OHLCV files | 2016-01-01 → 2021-12-31 | n/a | n/a | 2021-12-31 | frozen dataset fingerprint | 0 / NOT_REPORTED | capability audit only; old technical OHLCV claims must not be retested |
| I | frozen equity/ETF and crypto OHLCV plus current snapshots | 2016-01-01 → 2026-09-22T22:44:44.499607+02:00 | n/a | 2026-09-22T22:44:44.499607+02:00 | 2026-09-22T22:44:44.499607+02:00 | source-history and dataset fingerprints | 0 / NOT_REPORTED | baseline/measurement input; not permission for more technical mining |
| J | local canonical registry | 2026-08-29 → 2026-08-30 | n/a | n/a | 2026-08-30 | registry versions + mapping validity intervals | 0 / NOT_REPORTED | current mapping only; insufficient for historical SEC research |
| K | price/OHLCV inputs | 2016-01-01 → 2026-09-22T22:44:44.499607+02:00 | n/a | n/a | 2026-09-22T22:44:44.499607+02:00 | inherits input fingerprints | 0 / NOT_REPORTED | derived context only; already part of technical scope |
| L | OHLCV volume; no verified spread/depth source | 2016-01-01 → 2026-09-22T22:44:44.499607+02:00 | n/a | n/a | 2026-09-22T22:44:44.499607+02:00 | inherits input fingerprints | 0 / NOT_REPORTED | volume context only; execution liquidity not PIT-covered |
| M | none beyond existing price proxies | n/a → n/a | n/a | n/a | n/a | none | 0 / NOT_REPORTED | not research-ready |

## Coverage gates

- **fundamentals: FAIL** — No historical SEC filing snapshots and no historical issuer mapping.
- **expectations_surprise: FAIL** — No expected/actual PIT pairs; surprise remains UNKNOWN.
- **cot: FAIL** — The collector is current again, but historical rows have only recent first-observed availability evidence; independent forward PIT history remains insufficient.
- **crypto_regime: FAIL** — Only the already-tested technical OHLCV layer exists; no new PIT dominance, breadth, liquidity or on-chain layer.
- **gold_silver: BLOCKED** — Futures contract IDs, roll semantics, sessions, open provenance and cost contract remain unavailable.

No Development test was opened because every new-information gate failed or remained blocked. No Challenger, Validation or Holdout was created.

## Local health alerts

- `provider_failures`: family B
- `no_observations`: family D
- `stale_source`: family E
- `no_observations`: family F
- `no_observations`: family G
- `no_observations`: family M

## Terminal research status

`RESEARCH_BLOCKED_BY_INSUFFICIENT_PIT_DATA`
