# Multi-Asset Discovery v1 – Development v5 Post-Run Integrity

Stand: 2026-09-04

## Zweck und unveränderliche Referenz

Dieser Bericht konsolidiert ausschließlich Scheduler-, Datenqualitäts-, Missingness-, Work-Unit- und Store-Integrität des historischen Runs `mad1-development-a073df9096023f1da079a494`. Er enthält keine Performanceanalyse und keine Auswahl von Features, Hypothesen, Regeln oder Strategien.

Der v5-Run bleibt unverändert `COMPLETED_WITH_FAILURES`. Seine Control-, Feature- und Outcome-Stores, das ursprüngliche Run-Manifest sowie Frozen Dataset, FX-v2 und Identity-/Dependency-Evidenz wurden nicht überschrieben. Der tatsächliche letzte Work-Unit-Abschluss war `2026-09-03 01:44:03 CEST`.

## A. Scheduler und terminaler Status – PASS

- Root Cause: Der Runner behandelte nur `COMPLETED` als terminal und deutete `COMPLETED_WITH_FAILURES` daher fälschlich als laufend. Wiederholte Scheduler-Aufrufe erzeugten historisch 54 `RUNNER_STARTED`- und 52 `RUN_COMPLETED`-Events und lösten unnötige Store-Audits aus.
- Fix: Alle vorhandenen kanonischen Terminalzustände werden zentral erkannt. Ein terminaler Run wird vor der schweren Contract-/Store-Prüfung read-only zurückgegeben; er erzeugt weder neue Start-/Abschluss-Events noch neue Completion-Zeitstempel.
- Terminale Work-Units: 60.504 von 60.504; 41.725 `COMPLETED`, 14.075 historisch `SKIPPED`, 4.704 `FAILED`, 0 `PENDING`, 0 `ACTIVE`.
- Der Windows-Task `InvestmentAssistant-MultiAssetDiscoveryV1-Development` ist `Disabled`. `InvestmentAssistant-FX-PIT-Observer` blieb unverändert `Ready`.
- Das immutable Startmanifest behält seinen historischen `STARTING`-Snapshot. Runtime-Wahrheit und Auditzeitpunkte werden getrennt dokumentiert.

Terminal-Truth-Fingerprint: `4a1a6505f2357fe90d73cab68daae4951cf421461c7064d1c4f0f35578af8c94`.

## B. Equity-/ETF-OHLC-Qualität – PASS

Die getrennte Projektion `equity-etf-historical-pit-2026.09.03-v1` wurde ausschließlich aus dem eingefrorenen lokalen Datensatz erzeugt. Es gab keine Provider-Neuladung, kein Clipping, keine Imputation, keine Interpolation und keine Ersatzwerte.

- Assets: 2.488, davon 2.429 Aktien und 59 ETFs.
- Rohbalken: 3.028.079; aktive gültige Balken: 3.025.873; Coverage: 99,92714853 %.
- `INVALID_SOURCE_BAR`: 2.206 über 551 Assets, davon 530 Aktien und 21 ETFs. 191 Aktien besitzen dadurch keine nutzbare Development-Abdeckung.
- Aktive Hüllenverletzungen: 0; aktive nichtpositive OHLC-Werte: 0; doppelte Sessions: 0.
- 2.203 ungültige Balken beeinflussten mindestens einen Fall, 3 keinen Fall. Von 613.676 historisch wegen OHLC invalidierten Cases sind 611.473 mit der sauberen Projektion grundsätzlich wieder auswertbar; 2.203 bleiben ohne neues Signal nicht wiederherstellbar.
- Root Cause: 2.205 eingefrorene Auto-Adjust-Balken bleiben mangels belastbarer Raw-Provider-/Transformationsbelege `UNKNOWN_NOT_PROVABLE_FROM_FROZEN_AUTO_ADJUSTED_BAR`; ein CNL-Balken enthält einen belegten nichtpositiven Low-Wert. Vermutungen wurden nicht als Ursache ausgegeben.
- Fehlende Sessions durch ausgeschlossene/duplizierte Quellzeilen: 2.206. Es wird bewusst keine börsenkalenderbasierte Vollständigkeit behauptet. Der längste beobachtete aktive-Bar-Lückenproxy betrifft `EQUITIES:SW` mit 39 Kalendertagen beziehungsweise 27 Wochentagen.

Dataset-Fingerprint: `321531c482d844df4d5513b58646b3f41553f47a7b2276517cb8473886c298d6`. Invalid-Bar-Manifest-Fingerprint: `783755d85e23b8e10e07d91e6aa5966d85070ce5207c0f9b29b39927e2b22f39`.

## C. Structural R – PASS

Alle 209.492 Fälle mit nicht definiertem Structural R sind deterministisch `NON_POSITIVE_STRUCTURAL_RISK`; es gibt 0 unklassifizierte Fälle und 0 technische Bugs. Verteilung: Aktien 202.620, ETF 3.961, Crypto 2.477, FX 434. Das entspricht 8,16788670 % aller v5-Cases.

Das betroffene Safe-Zone-Modell ist in allen Fällen `C_SUPPORT_ELSE_SWING_LOW_MINUS_0_5_ATR14`. Es wurde kein R-Wert und keine künstliche Safe Zone erzeugt. Die 209.492 Beobachtungen bleiben für R-unabhängige Outcomes wie Prozentbewegungen, Preisstruktur und Zeitmessungen reprozessierbar; R-abhängige Werte bleiben fehlend.

Klassifikations-Fingerprint: `8a6c981d312d5ee14b07e4d9e648a4ccb7cb796b0131e4c35566e56cb895e98e`.

## D. Failed Work Units – PASS

Alle 4.704 historischen `FAILED`-Units sind vollständig aufgelöst:

- 4.608 Units aus 192 Assets: `LEGITIMATE_SKIP_NO_DEVELOPMENT_COVERAGE`. Der erste vorhandene Balken liegt jeweils nach dem Development-Ende. Eine genauere IPO-/Listing-/Delisting-Ursache wird ohne belastbare Quellmetadaten nicht behauptet. Künftige Runs behandeln diesen Zustand als vorhandenes `SKIPPED` ohne Retry.
- 96 Units aus vier Assets: `SOURCE_DATA_FAILURE_NON_POSITIVE_OHLC`. Belegt sind CNL am 2021-10-08, ICP-USD am 2021-05-10, AAVE-USD am 2020-10-02 und SHIB-USD am 2021-04-16.
- Pipeline Bug: 0; Eligibility Bug: 0; unerwartete technische Failure: 0; sonstige/ungeklärte Ursache: 0.
- Deterministische Source-/Contractfehler werden künftig nicht erneut versucht. Retry bleibt auf transiente Timeout-, Verbindungs- und SQLite-Lock-/Busy-Zustände begrenzt. Die historische Drei-Versuche-Historie bleibt unangetastet.

Klassifikations-Fingerprint: `e4aa0b85a358954ae63b9a212f56e10aa530500d436a40ce885449a79b92a461`.

## E. Vollständiger Store-Audit – PASS

- Features: 2.564.825; Outcomes: 2.564.825; vollständig auditierte Paare: 2.564.825 in 513 checkpointbaren Batches.
- Case-ID-Mengen exakt gleich; Feature-only 0; Outcome-only 0; Duplikate 0; Orphans 0; Asset-/Listing-/Decision-Time-/Split-/Run-/Contract-/Stage-Mismatches 0.
- Alle Payloads wurden dekomprimiert. Feature-, Outcome- und Case-Identity-Fingerprints sind deterministisch gültig; Payload-/PIT-/Leakage-/Control-Linkage-Probleme: 0.
- `quick_check` und vollständiger `integrity_check`: für Control, Feature und Outcome jeweils `ok`; Foreign-Key-Probleme 0; WAL und `synchronous=2` belegt; Append-only-UPDATE-/DELETE-Trigger vollständig vorhanden.
- Das Feld `full_development_scan_started=false` ist in 2.564.825 historischen Payloads obsolete per-Case-Metadaten. Es wurde nicht verändert und wird nicht länger als operativer Runstatus ausgewertet.
- Store-SHA-256 vor/nach dem Audit identisch: Control `2bb1203307f47b032bc22dddc7a75a789798ae71adb831aeb42b9442ef6c0bfe`, Feature `6e7af0275c0fa260e09539a74bec84bfae269a201f58b4d787b256d3b37647e6`, Outcome `56ec64b823ea857c776fc4815189e2bfc28779ce0235b8f4097571a82475d87b`.

Voll-Audit-Fingerprint: `fca4a7b42b06ccf57d31a6383c65b7ae85b562c71ad9d5ed9a2f777573d5d56e`.

## F. Runtime- und Dokumentationswahrheit – PASS

`PROJECT_STATUS.md` und `ROADMAP.md` nennen Run-ID, `COMPLETED_WITH_FAILURES`, 60.504 terminale Units, den tatsächlichen Abschluss `2026-09-03 01:44:03 CEST`, den deaktivierten v5-Scheduler und den unveränderten FX-Observer. Startmanifest, Runtime-Status und finaler Audit sind ausdrücklich getrennt.

Der kombinierte Readiness-Gate besteht 6/6 Bereiche. Readiness-Fingerprint: `023e67b1e4aa23343384ca4e2ba519608f73d6f9cb7358d9684476dbe8f2e9b2`.

## Technische Abnahme und Sicherheitsgrenzen

Die reparaturspezifische Suite bestand 40/40 Tests; die vollständige Suite bestand 926/926 Tests. Python-Kompilierung, Repository-Sicherheitscheck, Offline-Smoke, separater lokaler Streamlit-Start mit HTTP 200 und `git diff --check` waren erfolgreich.

Es wurde kein großer Reprocessing-Run gestartet und keine Performanceanalyse durchgeführt. Validation, Holdout, External, Forward, Paper und Shadow blieben geschlossen; Broker und automatische Orders bleiben deaktiviert.

## Reprocessing-Empfehlung

`NEW_VERSIONED_FULL_DEVELOPMENT_RUN_REQUIRED`

Die saubere Projektion besitzt einen neuen globalen Dataset-Fingerprint, der in die Case-Identität eingeht. Selektives Ersetzen würde inkompatible Case-Identitäten und Lineage innerhalb eines Datensatzes mischen. Die Empfehlung ist keine Startfreigabe: Vor einem späteren neuen, versionierten Development-Lauf müssen Review, Freeze und der verbindliche kontrollierte Mehr-Worker-Benchmark abgeschlossen sein.

## Technischer Gesamtstatus

`DEVELOPMENT_V5_POST_RUN_INTEGRITY_READY_FOR_REPROCESSING_REVIEW`
