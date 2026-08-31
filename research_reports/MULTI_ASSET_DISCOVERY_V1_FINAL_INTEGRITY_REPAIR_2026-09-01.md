# Multi-Asset Discovery v1 – finaler Integrity-Repair und Development-Gate

Stand: 2026-09-01
Branch: `codex/swing-forward-diagnostics-status`
Start-HEAD: `95e24e071b7e130f7c458a372df44faa891d03a2`
Repair-Code-HEAD: `c4435929046eae01bd561c51bcef3ffc237dd208`

## Ergebnis

Der Daten- und Methodikteil ist vollständig repariert und grün. Der große Development-Scan wurde trotzdem nicht gestartet, weil der unveränderte, ausdrücklich zu schützende Discovery-v1-Vertrag ausschließlich einen technischen Integritätspilot autorisiert. Der finale Status lautet:

`NOT_READY_TO_START_MULTI_ASSET_DISCOVERY_V1_DEVELOPMENT`

## FX-Forensik und Remediation

Die 231 im v1-Store verbliebenen Hüllenverletzungen sind vollständig klassifiziert. Alle Fälle liegen auf der Unterseite: `Open` und/oder `Close` liegen unter `Low`. Der v1-Validator prüfte `High` gegen Open/Close/Low, nicht jedoch symmetrisch `Low` gegen Open/Close/High. Damit ist belegt, warum diese Fälle in den aktiven Store gelangten. Ob die widersprüchlichen Providerwerte ursprünglich durch Providerqualität, Sessiongrenzen oder eine Revision entstanden, ist aus dem konservierten v1-Material nicht belastbar beweisbar und bleibt `UNKNOWN`.

Die 229 bereits beim v1-Import verworfenen Providerbalken und die 231 später gefundenen aktiven Fälle sind getrennte Lineage-Gruppen: Die ersten waren nie aktiv gespeichert, die zweiten waren in v1 aktiv. Sie werden weder gleichgesetzt noch still vermischt.

| Paar | Raw Provider Rows | v1 bereits verworfen | v2 neu als invalid archiviert | v2 aktiv gültig | aktive Anomalien | Coverage |
|---|---:|---:|---:|---:|---:|---:|
| EUR/USD | 4.336 | 51 | 68 | 4.217 | 0 | 97,255535 % |
| GBP/USD | 4.336 | 48 | 42 | 4.246 | 0 | 97,924354 % |
| USD/JPY | 4.336 | 130 | 121 | 4.085 | 0 | 94,211255 % |
| Gesamt | 13.008 | 229 | 231 | 12.548 | 0 | 96,464483 % |

Jeder der 231 Datensätze enthält Pair, Session, OHLC, Verletzungsart, absolute Größe, Pips, relative Größe, Source Record, Release-/Availability-Zeit, Importzeit, Orientierung, Inversionsstatus, Session-Zeitzone, Rundungs-/Adjustment-Status, Import-/Store-Version und die belegte beziehungsweise unbekannte Ursachenklassifikation. Die Detailzeilen liegen append-only in `historical_fx_invalid_bars` der v2-Datenbank.

- v2 Dataset-Fingerprint: `a3c41cddd06d7b24596bac5f1e375868a86784ea5a6feeacd9b44f49598c5c91`
- Invalid-Manifest-Fingerprint: `ebd5d39baec124fcf30d2e944ad9fb60614f811dfff36aa3ff11bd6627230466`
- v1 SHA-256 unverändert: `f0b7af71cbf9d527027a7a095cc562116e68aed7a0bdc37465d818b3259ca73f`
- Kein Clipping, keine Imputation, keine Interpolation, keine externe Quelle als historische PIT-Wahrheit.
- Inversionsformel ist regressionsgetestet: `O'=1/O`, `C'=1/C`, `H'=1/L`, `L'=1/H`.

## Historische Identity/Dependency

Policy: `multi-asset-historical-dependency-policy-2026.09.01-v1`
Fingerprint: `706b0b9e438464405f18d0972d49d34c553538c1236c3e7adb8fe37157214393`

Die heutige Registry darf ausschließlich post hoc zur statistischen Dependency-Korrektur verwendet werden und niemals Feature, Candidate, Entry, Safe Zone oder Outcome verändern. Eine historische Beziehung wird nur `KNOWN`, wenn ein verifizierter Issuer, ein belastbares historisches `valid_from`, optional `valid_to` und eine zulässige zeitliche Evidenzquelle vorliegen. Spätere Fusionen werden nicht rückwirkend zusammengeführt; Spin-offs und unbekannte Relationen bleiben getrennt beziehungsweise unbekannt.

Die aktuelle Registry besitzt 0 historische Beziehungsdatensätze mit diesen Zeitbelegen. Deshalb bleiben alle 11 Pilotfälle `DEPENDENCY_UNKNOWN`. Raw N wird nicht als unabhängig behauptet, unbekannte Fälle tragen 0 zum issuer-adjustierten Effective N bei. Der technische Pilot verlangt bewusst kein künstliches Mindest-N.

## Erneuter Integrity-Pilot

- Feste Fälle unverändert: 11 über EQUITIES, ETF, FX, CRYPTO und einen Stage-Grenzfall.
- Gate Count: 20/20 `PASS`.
- `no_ohlc_envelope_anomalies`: `PASS`.
- PIT/Next-Open: `PASS`.
- Leakage/Stage-Censoring: `PASS`.
- Determinismus: `PASS`.
- Feature-/Outcome-Store-Trennung und SQLite-Integrität: `PASS`.
- Case-Digest: `b9aa3f5c4cf0097def4d4480e812d1bbec23f764543d36b59b91cb270014b859`.
- Pilot-Fingerprint: `65e3243726be47ee0c9a61bd5e8e35512dbe1a8453cecd1776cbbe0be2c3a6fe`.
- Freeze-Fingerprint: `a93f68ee3eec1fddb37ea7a19d5616cccba7d43ece6146b01f8789a9d98b4a8e`.
- Contract-Fingerprint unverändert: `68994e462f90e2a4f1ad4adbdc858cc43fb0ddb85b0c2662d0f647e1dfa6c05a`.

## Finaler Readiness-Gate

Gate: `multi-asset-final-development-readiness-2026.09.01-v1`
Fingerprint: `add32aced165a12a8ee76dcee54fd14ac81b222f1dae3ba8854ded4cd1f9385d`

| Gate-Gruppe | Ergebnis |
|---|---|
| A Research Identity | PASS |
| B Dependency Effective N | PASS |
| C Research Integrity | PASS |
| D FX Historical Data Quality | PASS |
| E FX Observer | PASS |
| F PIT, Leakage und Pilot | PASS |
| G Safety | PASS |
| H Development Execution Contract | **FAIL** |

Die fünf fehlgeschlagenen Contract-Checks sind sachlich dieselbe Ausführungssperre:

- `research_role` ist `technical_integrity_pilot_only`, nicht `development`.
- Candidate-Modus ist `fixed_representatives_for_integrity_pilot`, nicht Full Universe.
- `full_development_scan_allowed=false`.
- `pilot_contract.large_scan_allowed=false`.
- Store-Pfade sind ausschließlich Pilot-Feature-/Outcome-Stores; Development-Stores sind nicht eingefroren definiert.

Eine Änderung oder operative Umgehung dieser Felder würde den Contract-Fingerprint und die fachliche Contract-Semantik verändern. Genau dies verbietet der Auftrag. Daher wurden weder Development-Runner noch Scheduled Task, Lock oder Run-Manifest angelegt.

## Safety und Abnahme

- Validation, Holdout, External, True Forward, Paper, Shadow und Broker: geschlossen/nicht gestartet.
- FX Forward PIT Observer: unverändert, SHA-256 `1f97a80bd6376036ebe5e3dcbd6ecc3500f1139937d81da8088efbde0a85c5c7`.
- Identity Registry, FX-v1, alte r4-Pilot-/Freeze-Artefakte und Contract-Datei: hash-identisch.
- 47 gezielte Tests im Reparaturlauf: bestanden; die finale reparaturspezifische 46-Test-Teilmenge wurde zusätzlich erneut grün ausgeführt.
- Vollständige Suite: 878/878 bestanden.
- `compileall`, Repository Safety und Offline Smoke: bestanden.
- Separater lokaler Streamlit-Start: HTTP 200; der exakt dafür gestartete Prozess wurde danach wieder beendet.
- Der Push von `c443592` wurde durch die Ausführungs-Sicherheitsfreigabe blockiert; für diesen Commit liegt deshalb noch kein neuer CI-Nachweis vor.

Ein späterer Full-Development-Start benötigt einen ausdrücklich autorisierten, vor Ergebnissichtung eingefrorenen Development-Ausführungsvertrag beziehungsweise eine neue Contract-Version. Erst diese darf Full-Universe-Eligibility, Development-Stores, Checkpoint-/Resume-Work-Units und den persistenten Runner festlegen. Eine Validation darf auch danach nicht automatisch geöffnet werden.
