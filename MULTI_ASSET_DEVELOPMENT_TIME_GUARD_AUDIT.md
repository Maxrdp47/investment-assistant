# Multi-Asset Development: Schutzzeit-Inventur

Stand: 2. September 2026

## Ergebnis

Der Multi-Asset-Development-Runner besitzt ab Contract v3 eine explizite,
einmalige Startgrenze (`2026-09-02T00:00:00+02:00`). Nach dieser Grenze werden
reine Forward-/Produktions-Schutzfenster nicht mehr auf Historical Development
angewendet. Tatsächlich aktive Produktionsprozesse sperren Development weiterhin
über ihre bestehenden Lock-Dateien.

Die Research-Semantik, Point-in-Time-/Leakage-Gates, Stage-Sperren,
Append-only-Stores, Prozess-Lock, Checkpoints, Duplicate-Schutz,
SQLite-Serialisierung, Datenqualitäts-/FX-/Dependency-Gates und sämtliche
Broker-/Order-Sperren bleiben unverändert aktiv. Legacy Forward bleibt
eingefroren.

## Inventar

| Regel | Ort | Zweck / betroffene Komponente | Wirkung vor v3 | Einordnung und v3-Zustand |
| --- | --- | --- | --- | --- |
| Kampagnen-Schutzfenster 10:30-11:30, 17:15-18:45 und 21:30-23:59 sowie konservativer Vorlauf | `config/swing_walk_forward_campaign.json`, `swing_walk_forward_campaign.py` | Priorität für echte Forward-/Produktionsläufe und historische Swing-Kampagnen | Wurde pauschal auch vom Multi-Asset-Development-Runner abgefragt und verzögerte dadurch reines Historical Development | **Forward-only.** Für die bestehenden Forward-/Kampagnen-Kontexte unverändert erhalten; in v3 nicht auf Historical Development angewendet. |
| Explizite Development-Startgrenze | `config/multi_asset_discovery_development_v3.json`, `multi_asset_development_runner.py` | Verhindert jeden Start vor dem beauftragten Stichtag | In v1/v2 nicht als eigener Contract-Gate vorhanden | **Development-eigen.** Vor 02.09.2026 00:00 CEST geschlossen, ab exakt 00:00 offen. |
| Aktive Produktions-Locks `swing_forward.scan.lock` und `forecasts.sqlite3.run.lock` | `config/swing_walk_forward_campaign.json`, `swing_walk_forward_campaign.py`, `multi_asset_development_runner.py` | Verhindert reale Ressourcen-/Prozesskollision mit laufendem Forward-Scan oder Prognoseprozess | Sperrte den Runner bei einem tatsächlich aktiven Produktionsprozess | **Kein reines Zeitfenster.** Bleibt für Development unverändert wirksam. |
| Regionaler Marktschluss, abgeschlossene Signalkerze und frühester zulässiger Entry | `trading_assistant.py` | Kausalität und Handelbarkeit in Forward-/Paper-Signalpfaden | Nicht vom Multi-Asset-Development-Runner importiert oder aufgerufen | **Forward-/Paper-Kontext.** Unverändert und weiterhin getrennt vom Development-Runner. |
| Feste Uhrzeiten der Background-Scans (10:30, 18:15, 22:30) | `config/swing_background_settings.json` | Planung der echten regionalen Forward-/Prognose-Läufe | Kein direkter Development-Gate | **Forward-/Produktionsplanung.** Unverändert; tatsächliche aktive Locks bleiben relevant. |
| Candidate-Cooldown/Purging nach Sitzungen | `swing_broad_research.py` | Statistische Abhängigkeit und Stichprobenhygiene | Bestandteil der Research-Semantik, keine lokale Uhrzeitregel | **Research-Semantik.** Unverändert; keine zeitliche Scheduler-Ausnahme. |
| Stage-/Unseen-Sperren für Validation, Holdout, External und True Forward | `config/multi_asset_discovery_development_v3.json`, Contract- und Readiness-Gates | Verhindert vorzeitigen Zugriff auf ungesehene Stufen | Geschlossen | **Permanenter Forschungs-Gate.** Bleibt geschlossen. |
| Paper-/Shadow-/Broker-/Order-Sperren | `config/multi_asset_discovery_development_v3.json`, Contract- und Readiness-Gates | Verhindert Handels- oder Produktionsausgaben | Geschlossen | **Permanenter Sicherheits-Gate.** Bleibt geschlossen. |
| Development-Prozess-Lock, Scheduler `IgnoreNew`, Checkpoint und Duplicate-Schutz | v3-Contract, `multi_asset_development_runner.py`, `multi_asset_development_execution.py`, Windows-Aufgabe | Verhindert Doppelstarts und doppelte Work-Units; ermöglicht Resume | Aktiv | **Ausführungsschutz.** Unverändert aktiv. |
| Serielle SQLite-Schreibvorgänge und getrennte append-only v3-Stores | v3-Contract, `multi_asset_development_execution.py` | Konsistenz, Reproduzierbarkeit und Trennung von v1/v2 | Aktiv | **Datenschutz.** Unverändert aktiv; v1/v2-Stores werden nicht geöffnet oder verändert. |
| PIT-/Leakage-, Dataset-, Identity-, Dependency-, FX- und Readiness-Gates | Contract, Execution, Readiness und referenzierte eingefrorene Artefakte | Kausalität, Datenintegrität und reproduzierbare Zulassung | Aktiv | **Methodischer Schutz.** Unverändert aktiv. |

## Kontextregel

Die bestehende Funktion `campaign_is_protected_time(...)` und ihre Konfiguration
werden nicht gelöscht oder abgeschwächt. Contract v3 klassifiziert ihre
Uhrzeitfenster ausdrücklich als nicht für Historical Development zuständig.
Forward-, Paper- und Produktionskontexte behalten ihre vorhandenen Regeln. Der
Development-Runner prüft nach der einmaligen Startgrenze weiterhin vor jeder
Arbeitsaufnahme, ob ein geschützter Produktionsprozess tatsächlich aktiv ist.
