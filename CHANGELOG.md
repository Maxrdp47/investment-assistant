# Investment Assistant – Changelog

Dieses Dokument nennt abgeschlossene Änderungen. Es ist keine Roadmap und enthält keine Startfreigabe.

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
