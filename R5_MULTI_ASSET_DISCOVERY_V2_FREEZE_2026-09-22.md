# R5 – Multi-Asset Discovery v2 Contract Freeze

Stand: 2026-09-22. R5-Vertrag `multi-asset-discovery-v2-r5-freeze-2026.09.22-v1`, kanonischer Contract-Fingerprint `0e67967f5d26b0d6801270fea29188d71f6288ad8ca34a3003e384a81fccd241`.

## Freeze-Ergebnis

Der [vollständige maschinenlesbare Vertrag](config/multi_asset_discovery_v2_r5_freeze.json) ist **vor jeder Discovery-v2-Outcome-Betrachtung** eingefroren. Der Validator [`multi_asset_v2_r5_contract.py`](multi_asset_v2_r5_contract.py) prüft 19 eindeutige Featurefamilien, fünf zulässige Capability-Zustände, R4-Berichtsprüfsummen, R4-B-/R4-H-Featureverträge, eingefrorene Equity-/ETF- und Crypto-Dataset-Fingerprints, Parent-Verträge, Universe-/Input-Artefakte, Forschungs-Policy, Missingness-, Stage-, Kosten-, Quality-C- und Ausführungsschutz. Ergebnis: `PASS_R5_FREEZE_VALID`. Validation, Holdout, External, Forward, Paper und Shadow-Ausführung sind geschlossen; kein R6-Outcome wurde geöffnet.

Die v6-Parentdatei enthält für den Stage Split die 63-stellige Zeichenfolge `e86c880c780f1864387316a9229103615c5d80ee7be2bc92d3c17b1362d2c9e`. Sie wird unverändert als **Legacy-Referenz-ID**, nicht fälschlich als SHA-256 ausgegeben. Der v6-Contract selbst wird bytegenau über SHA-256 `8f67337c6e45eba6ebd8a749b38e4774503d7ead0b1a87253d2756a7595d7283` verankert; die Stage-Zeiträume und das Cross-Boundary-Verbot sind zusätzlich explizit im R5-Vertrag festgeschrieben.

## Eingefrorene Capability Matrix

| Status | Familien |
|---|---|
| `ACTIVE_PIT_LIMITED_SCOPE` | Preisrenditen; Momentum/Trend/Volatilität; bestätigte Struktur und Pullback/Breakout/Konsolidierung; globales, streng verzögertes ACWI-Relative-Strength-/Regime-Signal für Equity/ETF; relatives gemeldetes Volumen; rohe kausale Gap/Overnight/Intraday-Komponenten ohne R3-Retest; Support-/Resistance-Geometrie; Crypto-vs.-BTC-Kontext |
| `SHADOW` | SEC-Fundamentals, Firmenereignisse, COT, Politik/Geopolitik, historische Issuer-Abhängigkeit |
| `UNAVAILABLE` | Region-/Sektorbenchmark, Vintage-Makro/Rates/Expectations, FX-Historical-Discovery, Crypto-On-Chain/Dominanz, historische Universe-Mitgliedschaft/Delistings |
| `ACTIVE_PIT` | keine Familie – die belegten Quellen besitzen jeweils mindestens eine relevante Scope-/Provider-/Universe-Begrenzung |
| `STRUCTURAL_NOT_APPLICABLE` | derzeit keine ganze Familie; Nichtanwendbarkeit einzelner Asset-/Feature-Zellen bleibt dennoch ein eigener Missingness-Zustand |

`SHADOW` und `UNAVAILABLE` werden im R6-Feature-Store nicht als Werte materialisiert. Missing/Unknown wird nie zu `False` oder `0`; kein Cross-Segment-Fill, keine Imputation oder Interpolation. Der resultierende Scope ist das current-curated, eingefrorene Panel, nicht der damalige Gesamtmarkt. Historisches Issuer-Effective-N bleibt 0 und darf nicht durch Roh-N ersetzt werden.

## Outcome-, Seen-Data- und Kostenvertrag

Die wissenschaftlichen v7-r2-Outcome-, Safe-Zone-, Deterioration-, Next-Open-, Stage- und No-Intrabar-Invention-Wurzeln bleiben unverändert verankert. Neu präzisiert ist ausschließlich: 20/60/120/252 Sitzungen verwenden je eine eigene vollständig beobachtbare Grundgesamtheit. Ein an der Stage-/Segmentgrenze fehlender 252er-Pfad macht einen vollständig beobachteten 20er-Pfad nicht nachträglich unbrauchbar. Kein Outcome darf Segment oder Development-Ende überschreiten.

2016–2021 ist ausdrücklich `seen Development`; R6 darf daraus keine ungesehene Bestätigung ableiten. 2022–2023 Validation und Holdout ab 2024 bleiben geschlossen. R6 ist deskriptive Pfadforschung ohne vollständigen Exit-/Kostenvertrag: Nettorendite, Profitfaktor und Strategie-Expectancy sind verboten. Erst ein später separat eingefrorener R7-Challenger müsste vorher assetklassenspezifische Spread-, Slippage-, Gebühren- und Finanzierungskosten festlegen.

## Review- und Ausführungsvertrag

R6 prüft Einzelfeatures/-familien, keine automatische Kombination, keinen Gesamtscore, keine Schwellen-/Parameter-Grid-Search und keine Profitauswahl. Ein robuster C-Hinweis benötigt alle vorab genannten Dimensionen einschließlich PIT, Coverage, Missingness, Dependencies/Effective N, Zeit-, Asset-, Scope-, Regime- und Outcome-Stabilität, fehlender Jahresdominanz, Redundanz- und Multiple-Testing-Schutz. Ein gutes Aggregat allein genügt nicht; unbekannte Dependencies verhindern einen robusten Kandidatenstatus.

Der künftige R6-Lauf ist `mad2-development-v2-20260922-v1` mit drei neuen append-only Stores, einem SQLite-Writer, kontrolliertem Sechs-Worker-Pool, Asset×Quartal-Work-Units, Checkpoint/Resume, globalem Research-Lock und eigenem Prozess-Lock. Vor dem Full Run sind deterministischer Pilot und Integrity Gate verpflichtend. Reale aktive Produktionslocks blockieren den Start; alte starre Uhrzeitfenster steuern ihn nicht. Dieser R5-Abschluss startet R6 noch nicht.
