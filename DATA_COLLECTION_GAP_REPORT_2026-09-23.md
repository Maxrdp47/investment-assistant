# DATA_COLLECTION_GAP_REPORT

As of: `2026-09-23T07:47:00+00:00`
Source report: `70a6f59462558019eb14b2a818f70b5e25c89c5a3a91bf2a042d5393bb20ee43`

1. **Are all strategically important data families collected?** No. Price/OHLCV and forecasts exist, while fundamentals, expectations, politics/regulation, yield/rate expectations and execution-quality data are not operational.
2. **Technically present but practically empty:** expectations=0; fundamentals=0; verified bid/ask=0.
3. **Collectors no longer producing current data:** the event sidecar is stale; COT actual forward availability is stale. The FX and forecast scheduled tasks themselves are present.
4. **Schedulers disabled or absent:** no independent fundamentals, company-event, macro/expectations, politics/regulation or crypto-regime scheduler exists. Disabled terminal research/scanner tasks are intentionally not data-collector defects.
5. **Current-only data that must be stored forward:** expectations/consensus, company guidance/events, macro and central-bank expectations, policy/regulatory/geopolitical events, COT first-seen evidence and reliable quotes/spreads if a lawful source becomes available.
6. **Historical PIT that cannot be reconstructed safely:** analyst/macro expectations, most event first-seen times, old issuer/listing validity and expected-rate vintages. These must remain UNKNOWN and be collected prospectively.
7. **Previously invisible collected data:** COT, FX source health, frozen OHLCV, identity mapping and event-sidecar coverage are now included centrally in the A–M report.
8. **Revision/version gaps:** COT, FX and event schemas support append-only/revisions; fundamentals, expectations, politics and risk-regime layers have no operational revision history because they have no collector.
9. **Missing by research theme:** fundamentals lack filing snapshots and historical issuer mapping; events lack published timestamps and breadth; macro/expectations lack PIT vintages; politics lacks a source; FX lacks rates/expectations/bid-ask; crypto lacks new dominance/breadth/liquidity/on-chain PIT data; relative strength is available only as a derived technical layer.
10. **Unnecessary duplication:** no duplicate canonical FX observation keys were detected. COT is stored both in its canonical report store and as deduplicated FX context observations by design; that is provenance linkage, not competing truth.

## Repairs made

- COT refresh now catches up after a missed configured weekday when actual source evidence exceeds the maximum age.
- Stale COT reports are no longer relabelled as current `AVAILABLE_PIT` context.
- `NO_RELIABLE_DATA` and `NOT_SCHEDULED` attempts no longer advance `last_success` in FX source health.
- The central read-only report exposes stale sources, empty families, provider failures, missing schedulers, repeated failures, DB-growth guard state and duplicate observations.

## Research decision

All new-information coverage gates fail or remain blocked. No technical negative claim was retested and no new Challenger was created.

`RESEARCH_BLOCKED_BY_INSUFFICIENT_PIT_DATA`
