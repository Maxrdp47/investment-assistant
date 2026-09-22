# R4-D/E/F – Event-, Makro- und Politik-PIT-Quellenprüfung

Stand: 2026-09-22. Programm `finite-research-program-2026-09-15-v1`. Die Prüfung ist read-only und outcome-frei; sie aktiviert keine Research- oder Produktionsregel.

## R4-D – Unternehmensereignisse

Der bestehende [Eventvertrag](swing_event_research.py) unterscheidet `published_at`, `first_seen_at`, Quelle, Betroffenheit und Revision/Version und hält Events aus signalunabhängigen Quellen nur als Research-Sidecar. Der lokale Store `runtime/swing_event_research.sqlite3` enthält **24** Event-Datensätze, alle mit `acquisition_mode=forward`, `source_type=immutable_forward_signal_snapshot` und `event_type=company`. `first_seen_at` reicht vom 2026-08-11 bis 2026-08-18; bei **0/24** liegt `published_at` vor. `pit_eligible=1` bei 24/24 besagt nur: zum jeweiligen Forward-Beobachtungszeitpunkt nutzbar. Es macht sie nicht zu historisch verfügbaren Ereignissen.

Für die eingefrorenen Forschungsjahre 2016–2021 sind damit **0** Ereignisse mit belegter damaliger Veröffentlichung, Asset-Zuordnung und Revision verfügbar. Earnings/Filings, Guidance, Kapitalmaßnahmen, M&A, Management und klinische/regulatorische Events werden in Discovery v2 nicht als getestete historische Eventmerkmale ausgegeben. Historischer Status: `SHADOW`; der vorhandene Forward-Sidecar bleibt unverändert und wird nicht rückdatiert.

## R4-E – Makro, Zinsen, Expectations und COT

Im Repository ist kein versionierter historischer ALFRED/FRED-Vintage-, Policy-Rate-, Yield-, DXY- oder vor dem jeweiligen Ereignis veröffentlichter Consensus-/Surprise-Quellsnapshot vorhanden. Ein Kursproxy wie ACWI aus R4-B ist kein solcher Makro-Release. Makro-/Rates-/Expectations-Familie: `UNAVAILABLE` für 2016–2021. Weder heutige revidierte Makrowerte noch nachträglich rekonstruierte Erwartungen werden als damaliges Wissen ausgegeben.

Der getrennte COT-Store `runtime/cot_shadow.sqlite3` besitzt zwar **62.692** `cot_reports` mit Report-Daten vom 2023-01-03 bis 2026-09-01. Diese Report-Daten sind **keine** Verfügbarkeitsdaten. Die gespeicherten `available_at`-Zeitpunkte beginnen erst am 2026-08-18. Die **1.833** `cot_report_availability`-Belege haben ausschließlich `availability_basis=first_observed_publicly_available`, mit lokalen `first_seen_at` zwischen 2026-08-22 und 2026-09-04. Für 2016–2021 liegt kein reportierter COT-Tag und kein historisch belegter Release-Zeitpunkt vor. COT bleibt `SHADOW`, kein historisch aktives FX-/Makromerkmal. Der vorhandene Forward-Collector wird nicht verändert oder neu gestartet.

## R4-F – Politik und Geopolitik

Der Eventvertrag enthält Kategorien für Sanktionen, Zölle, Exportkontrollen und weitere offizielle Maßnahmen, aber der lokale Event-Store enthält **0** `geopolitics_policy`-Datensätze. Es gibt folglich keine historische, zugleich quellen-, publikationszeit-, Erstkenntnis- und Asset-/Sektor-belegte Coverage für die Forschungsjahre. Historischer Status: `SHADOW`; das ist kein negativer Effekt-Test und keine Aussage, Politik habe keinen Einfluss. Es werden keine nachträglichen subjektiven Ereignislisten gebaut.

## Reproduzierbarkeit und Grenzen

Die Zahlen stammen aus schreibgeschützten SQLite-Abfragen gegen `event_records`, `cot_reports` und `cot_report_availability`. Quell-DBs, eingefrorene Daten, v7-r2 und laufende Forward-Sidecars wurden nicht verändert. Die Zählungen belegen die **lokal vorhandene** Coverage zum Prüfzeitpunkt, nicht eine globale Unmöglichkeit, externe PIT-Daten zu beschaffen. Eine spätere Aktivierung wäre ein neuer, outcome-unabhängig versionierter Quellen-/Mapping-Vertrag mit belegter Veröffentlichung und Revision, nicht eine rückwirkende Aufwertung dieses Audits.

R4-G FX ist der nächste eigenständige Capability-Block. R5 und spätere Ergebnisphasen bleiben geschlossen.
