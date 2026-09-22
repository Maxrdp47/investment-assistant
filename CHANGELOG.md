# Investment Assistant – Changelog

Dieses Dokument nennt abgeschlossene Änderungen. Es ist keine Roadmap und enthält keine Startfreigabe.

## 2026-09-23 – Endliches Research-Programm R0–R9 abgeschlossen

- R6 `mad2-development-v2-20260922-v1` wurde nach grünem CI sowie Pilot-/Replay-/Integrity-PASS vollständig mit 60.432/60.432 Receipts und 2.356.553 Fällen abgeschlossen. Der [Final Audit](R6_MULTI_ASSET_DISCOVERY_V2_FINAL_AUDIT_2026-09-22.md) ist `PASS`; der [Descriptive Development Report](R6_MULTI_ASSET_DISCOVERY_V2_DESCRIPTIVE_DEVELOPMENT_REPORT_2026-09-22.md) wertet alle 31 vorab benannten Einzelfeatures aus. Der [Completion Summary](R6_MULTI_ASSET_DISCOVERY_V2_COMPLETION_SUMMARY_2026-09-22.md) dokumentiert 0 robuste Kandidaten und ein ungeöffnetes R7.
- Das verpflichtende Dependency-Gate scheiterte an historisch verifizierten Issuer-Dependencies Effective N = 0. Es wurde keine Schwellen-, Ranking-, Kombinations- oder Rettungssuche durchgeführt. Validation, Holdout, External, Forward, Paper, Shadow-Ausführung, Broker und Orders blieben geschlossen.
- Der [R8 Trigger-Review](FINITE_RESEARCH_PROGRAM_R8_TRIGGER_REVIEW_2026-09-22.md) aktivierte 0 von maximal 2 Reserve-Hypothesen, weil technische Reserveindikatoren die belegte Provenienzlücke nicht schließen können. R9 setzte terminal `NO_ROBUST_EDGE_FOUND_IN_APPROVED_RESEARCH_PROGRAM`; automatische Strategiesuche ist bis zum Nutzerreview pausiert, Produktsoftware und Research-Infrastruktur bleiben aktiv.
- Der R6-Abschluss wurde idempotent in der Knowledge Base archiviert: Hypothese `3335b324-63d3-4f88-aa00-bccacdde761e` `REJECTED`, Experiment `b8d0072d-c05f-4eea-bebe-0fd5e39a33e6` `COMPLETED`, Resultat `043ac802-1712-4834-8d84-bdafcf230413` `inconclusive`.

## 2026-09-22 – R6-Ausführung vor Full Development implementiert

- Für `mad2-development-v2-20260922-v1` sind ein dünnes, append-only Delta-/Referenz-Speichermodell, 60.432 Asset×Quartal-Work-Units für 2.518 Equity-/ETF-/Crypto-Einheiten, sechs Rechenworker bei exakt einem SQLite-Schreiber, Checkpoint/Resume, Parent-Receipt-Prüfung, reale Produktions-/Research-Locks und ein deterministischer Drei-Asset-Pilot implementiert. Die zwei rund 10-GB-v7-r2-Elternstores bleiben unverändert und werden nicht blind dupliziert.
- Der outcome-blinde Review-Vertrag benennt vor dem Full Run 31 Einzelfeatures und die getrennten 20/60/120/252-Populationen. Schwellen-/Grid-/Kombinations-/Profit-Suche bleibt gesperrt; R3-Overnight/Intraday wird nicht erneut als Kandidat getestet. ACWI-Renditen dürfen ausdrücklich keine Kontinuitätssegmentgrenze überschreiten. R6 ist noch nicht gestartet und wartet auf vollständige lokale Prüfung, grünes CI sowie Pilot-/Replay-/Integrity-PASS.

## 2026-09-22 – R5 Discovery-v2-Vertrag vor Outcomes eingefroren

- Capability Matrix, Quellen, Fingerprints, Missingness, separate 20/60/120/252-Populationen, Seen-Data, Kostenstatus, Stage-Schutz, Quality-C-Gate und R6-Ausführungsschutz sind maschinenlesbar eingefroren. Der Validator prüft 19 Familien und sämtliche lokale Provenienz fail-closed. Contract `0e67967f5d26b0d6801270fea29188d71f6288ad8ca34a3003e384a81fccd241`; keine v2-Outcomes, Validation oder Holdout geöffnet. [R5-Freeze-Bericht](R5_MULTI_ASSET_DISCOVERY_V2_FREEZE_2026-09-22.md).

## 2026-09-22 – R4-I Survivorship-Grenze und R4-Abschluss

- Der aktuelle Frozen Scope wurde gegen seinen 2026er Auswahlzeitpunkt auditiert. Historische Index-Constituents, Delistings, Pleiten, Vorgängerbeziehungen und ausgeschiedene Crypto-Assets sind nicht versioniert vorhanden. Die 2016–2021-Kurse bilden deshalb nur ein current-curated Panel; Survivorship-Richtung und -Größe bleiben unbekannt. R4-A–I ist ohne v2-Outcomes abgeschlossen beziehungsweise ehrlich begrenzt. [R4-I-Audit](R4_I_SURVIVORSHIP_UNIVERSE_AUDIT_2026-09-22.md).

## 2026-09-22 – R4-H Crypto-Capability begrenzt vorbereitet

- Ein neuer outcome-freier, segment-sicherer Featurevertrag berechnet auf eingefrorenen Crypto-OHLCV ausschließlich kausale, um einen UTC-Tag verzögerte BTC-Relative-Renditen, Volatilität, gemeldetes Relative-Volume und einfache kontinuierliche Strukturwerte. Der read-only BTC/ETH-Pilot und gezielte Kausalitätstests bestehen. Dominanz und On-Chain bleiben `UNAVAILABLE`; keine Crypto-Regel oder neue Teststufe aktiviert. [Capability-Bericht](R4_H_CRYPTO_CAPABILITY_2026-09-22.md).

## 2026-09-22 – R4-G FX-Historiengrenze reproduziert

- Der eingefrorene FX-Precheck und der read-only Segment-Loader zeigen 4.508 gültige Balken, 93 archivierte Invalid-Source- und 165 Peer-Missing-Grenzen sowie maximal 194/148/75 Balken lange Kontinuitätssegmente je Paar. Damit gibt es 0 Gap-sichere 220er-Signale. Wochenenden wurden nicht als Sitzungen erfunden; ein Kalenderbug ist nicht belegt. FX wird ohne Daten-/Regel-Lockerung als historisch nicht testbar eingestuft. [R4-G-Audit](R4_G_FX_HISTORICAL_CAPABILITY_2026-09-22.md).

## 2026-09-22 – R4-D/E/F lokale PIT-Quellen auditiert

- Die vorhandenen Event- und COT-Stores wurden schreibgeschützt auf tatsächliche Verfügbarkeitszeitpunkte und Quellen geprüft. Nur 24 Forward-Firmenereignisse aus 2026, keine historisch verwendbaren Politikereignisse; COT-Reportdaten wurden lokal erst 2026 beobachtet. Für 2016–2021 sind Event/Politik/COT `SHADOW`, Makro-Vintages und vorab veröffentlichte Expectations `UNAVAILABLE`. Keine historischen Features oder Outcomes aktiviert. [Quellenaudit](R4_D_E_F_PIT_SOURCE_AUDIT_2026-09-22.md).

## 2026-09-22 – R4-C historisches Fundamentals-Gate

- Ein CIK-gebundener, rein offline arbeitender SEC-Company-Facts-Parser bewahrt jährliche Filings und Amendments getrennt und setzt ein konservatives As-of-Gate ab dem Folgetag des Einreichungsdatums. Synthetische Kausalitätstests bestehen. Da weder ein versionierter lokaler SEC-Quellsnapshot noch ein historisch gültiger Join zu den Frozen-Equities vorliegt, bleibt die Fundamentals-Familie `SHADOW` mit 0 belegter historischer Coverage. Keine v2-Outcomes oder Regeln wurden geöffnet. [Capability-Bericht](R4_C_FUNDAMENTALS_CAPABILITY_2026-09-22.md).

## 2026-09-22 – R4-B begrenzte PIT-Merkmale vorbereitet

- Ein getrennter, outcome-freier Featurepass für globales ACWI-Relative-Momentum und explizite bestätigte Preisstruktur wurde implementiert und mit kausalen Präfix-Tests geprüft. Vor dem Freeze wurde ein gleichdatiger ACWI-Schluss wegen möglicher Zeitzonen-Leakage durch einen streng früheren, höchstens fünf Tage alten Schluss ersetzt. Region und Sektor wurden nicht rückdatiert; kein Filter oder Strategy-Score aktiviert. [Capability-Bericht](R4_B_RELATIVE_STRUCTURE_CAPABILITY_2026-09-22.md).

## 2026-09-22 – R4-A Identity-/Dependency-Audit

- Die eingefrorene Equity-/ETF-Projektion und die neueste Identitäts-Registry wurden read-only zeitlich abgeglichen. Alle passenden aktuellen Registry-Mappings beginnen erst am 2026-08-30; für 2016–2021 sind 0 Issuer-Beziehungen zeitgenössisch verifiziert. Der [methodische Audit](R4_A_IDENTITY_DEPENDENCY_AUDIT_2026-09-22.md) trennt Roh-N, beobachtete Listing-/Zeitgruppen und echtes Effective N. Keine Identität wurde rückdatiert oder ein v7-/Frozen-Artefakt verändert.

## 2026-09-22 – Programm fortgesetzt; R3 einmalig abgeschlossen

- Der Nutzerauftrag „weiter“ führte zur erneuten Prüfung des Master-Vertrags. Dessen „Sonst R3“ erlaubt die Fortsetzung nach dem R2-Daten-Gate. Die frühere globale Stop-Einordnung ist als historischer Zwischenstand überholt; R2-Rohbefunde und Blocker bleiben unverändert.
- Der v7-r2-Review beantwortete den registrierten Overnight-/Intraday-Vertrag nicht vollständig. Ein einzelner [R3-Vertrag](OVERNIGHT_INTRADAY_R3_DEDUPE_2026-09-22.md) wurde vor Ergebnissichtung eingefroren und nach grünem CI über die unveränderte Equity-/ETF-PIT-Projektion mit Pilot, Resume, globalem Research-Lock und append-only Store ausgeführt.
- Der [R3-Review](OVERNIGHT_INTRADAY_R3_REVIEW_2026-09-22.md) fand keinen stabilen inkrementellen Development-Zusammenhang des rollierenden Overnight-Bias gegenüber der einfachen Baseline. KB-Ergebnis idempotent verknüpft; keine Handelsregel, Validation, Holdout oder Produktionsänderung. Nächster Programmblock ist R4 Capability Expansion.

## 2026-09-22 – Endliches Research-Programm am R2-Daten-Gate gestoppt

- R2 Gold/Silber wurde ausschließlich auf Quell- und Ausführbarkeit vorgeprüft. Die verfügbaren Yahoo-Futures-Proxies enthalten keine belegbare historische Kontrakt-/Roll-Provenienz; die getesteten alten Einzelkontrakte waren nicht verfügbar. Keine Strategieergebnisse, kein R2-Research-Freeze und kein späteres Datenfenster wurden erzeugt.
- Der R2-Work-Request ist mit konkretem Datenblocker `BLOCKED`; ein [Daten-Gate-Bericht](GOLD_SILVER_R2_DATA_GATE_2026-09-22.md) wurde mit dem DRAFT-Experiment referenziert. Der [technische Programmabschluss](FINITE_RESEARCH_PROGRAM_TECHNICAL_STOP_2026-09-22.md) hält R3–R9 geschlossen und kennzeichnet ausdrücklich, dass kein allgemeines No-Edge-Urteil möglich ist.

## 2026-09-22 – R1 Wasser-Research terminal dokumentiert

- Der isolierte, vor dem Ergebnis eingefrorene Wasser-Versuch wurde auf dem versionierten Fünf-Symbol-Datensnapshot ausgeführt. Development ist `DEVELOPMENT_INCONCLUSIVE` (`UNDERPOWERED`: 7 Primärfälle, Effective N 3/4). Es gab keinen Challenger, keine Validation und keinen Holdout.
- Der append-only Research-Review und die Knowledge-Base-Verknüpfung sind abgeschlossen. Ein numerisches Kostenfeld an der KB-Schnittstelle wurde nach einem Übergabeformatfehler korrigiert; der persistierte Forschungsbefund wurde nicht verändert oder neu berechnet.
- R2 Gold/Silber ist in der Roadmap ausschließlich zum Futures-Preflight geöffnet. Keine Strategie- oder Produktionsregel wurde geändert.

## 2026-09-15 – Endlicher Research-Programmzyklus aktiviert

- Der vollständig geprüfte v7-r2-Review-Stand wurde per normalem Fast-Forward auf `main` integriert; v7-r2 bleibt immutable und enthält 0 robuste Kandidaten.
- Die Roadmap enthält jetzt die ausdrücklich freigegebene, strikt sequenzielle und endliche Steuerkette R0 bis spätestens R9 einschließlich Attempt-Limits, Gates, Kill-Regeln und Early-Success-/No-Edge-Stop.
- R0 ist abgeschlossen. R1 Wasser befindet sich im Vertrags- und Daten-Preflight; es wurde noch kein neuer Research-Lauf gestartet, kein Resultat erzeugt und keine ungesehene Stufe geöffnet.
- External, True Forward, Paper, Shadow, Broker, Orders, Live und Produktionsintegration bleiben geschlossen.

## 2026-09-13 – Trading-Research-Backlog geordnet

- Wasser-Infrastruktur-Aktien wurden als erster später direkt ausführbarer Research-Auftrag nach Abschluss und Review des aktuellen Multi-Asset-Development-Pfads eingeordnet.
- Gold-/Silber-Nachzügler wurden mit isoliertem Runner als Voraussetzung an die zweite Stelle gesetzt.
- Die Overnight-/Intraday-Renditetrennung wurde ausschließlich als `CONDITIONAL_RESEARCH_RESERVE` dokumentiert.
- Buyer Confirmation v1, Fibonacci, Failed Seller Attempts und FX Carry PIT bleiben historische Evidenz und wurden nicht erneut geöffnet.
- Kein Experiment, Runner, Performance-Lauf, Validation- oder Holdout-Schritt wurde gestartet.

## 2026-09-06 – Dokumentation und Urlaubs-Workqueue konsolidiert

- Die vollständige bisherige `ROADMAP.md` wurde unverändert als `docs/archive/ROADMAP_LEGACY_THROUGH_2026-09-06.md` archiviert.
- Die vollständige bisherige `PROJECT_STATUS.md` wurde unverändert als `docs/archive/PROJECT_STATUS_LEGACY_THROUGH_2026-09-06.md` archiviert.
- `ROADMAP.md` enthält jetzt nur noch aktive Planung, Freigaben, Voraussetzungen, Abnahmekriterien, Stop-Bedingungen und spätere Arbeit.
- `PROJECT_STATUS.md` enthält genau einen datierten Current-Truth-Block.
- Dauerhafte Forschungs- und Validierungsregeln wurden ohne fachliche Änderung in `RESEARCH_POLICY.md` zusammengeführt.
- `SWINGTRADER_PRODUCT_ARCHITECTURE.md` wurde auf ein reines langfristiges Zielbild begrenzt; aktuelle Laufzahlen und Freigaben verweist es nun an die kanonischen Status- und Roadmap-Dateien.
- Die Queue `vacation-workqueue-2026-09-06-v1` und ihr Resume-Stand wurden gespeichert.
- Die v6-Runtime, Scheduler und KB-READY-Aufträge wurden nur lesend geprüft.
- Der separate ENTRY-Handoff-Importer-Commit `b1e3802b807649bc2cf871fa31ccf09fd8781cac` wurde als neuer Projekt-Ausgangsstand übernommen, aber nicht mit den Dokumentänderungen vermischt.
- Keine neue Funktion, kein Benchmark, kein Scan, kein Reprocessing-Lauf, kein Collector und keine Forschungsstufe wurde durch dieses Dokumentationspaket gestartet.
- Bestehende Prozesse, Scheduler, Stores, Nutzerdaten und Forschungsartefakte wurden nicht verändert.

Die vollständige frühere Änderungsgeschichte bleibt in den beiden Archivdateien und in Git erhalten.
