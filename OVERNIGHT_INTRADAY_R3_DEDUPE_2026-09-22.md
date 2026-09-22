# R3 Overnight/Intraday – Vertrags-Deduplizierung

Stand: 2026-09-22. Programm `finite-research-program-2026-09-15-v1`. Dieser Check ist **kein** neuer Performance-Test und verbraucht noch keinen R3-Research-Versuch.

## Entscheidung

Der v7-r2-Development-Review beantwortet den registrierten R3-Vertrag **nicht vollständig**. Gemäß R3 ist deshalb höchstens **ein** eigenständiger Versuch zulässig. Die zuvor als final bezeichnete R2-Datengrenze bleibt für Gold/Silber bestehen, beendet aber nach dem Wortlaut des Master-Auftrags („Sonst R3“) nicht die unabhängige R3-Prüfung. Der technische Abschlussbericht vom 2026-09-22 dokumentiert den damaligen Zwischenstand und ist als **überholt für den aktuellen Programmstatus** zu lesen; die R1-/R2-Rohbefunde werden nicht geändert.

## Abgleich gegen die vorhandene Evidenz

| Frage | v7-r2-Review | registrierter R3-Vertrag | Deduplizierung |
|---|---|---|---|
| Signalmerkmal | einzelner `overnight_return`/`intraday_return`, Vorzeichen bei 0 und kontinuierliche Korrelation | kausale Zerlegung plus rollierender 20-Sitzungs-Bias, Renditeanteil und Komponenten-Volatilität | nicht beantwortet |
| Outcome | Setup-Fälle, 20/60/120/252-Sitzungs-Pfadmetriken | vollständiges Aktien-/ETF-Research-Universum, Forward 1/5/20, MFE/MAE nur wo sinnvoll | nicht beantwortet |
| Zusatznutzen | je Feature allein; keine eingefrorene Baseline-plus-Feature-Prüfung | eigenständiger inkrementeller Wert gegenüber einfacher Close-to-Close-Baseline | nicht beantwortet |
| Evidenzstatus | rein deskriptives Development; 2021 stark zensiert, Dependencies `UNKNOWN`, Effective N 0 | mehrere Assets/Perioden, OOS und Walk-Forward für eine robuste C-Einstufung | keine Validierungs- oder Holdout-Freigabe aus v7-r2 |

Quelle: [v7-r2-Development-Review](MULTI_ASSET_DISCOVERY_V7_R2_DEVELOPMENT_REVIEW_2026-09-14.md), Evidenz-Fingerprint `a06961e0b7791b7d5a8f22869562af057393b5ac268f030a4f909d0824fd66fd`; KB-Experiment `8389509b-dc70-41b6-9df9-e27c194f0a04` bleibt `PLANNED`. Die bestehende reine Research-Implementierung hat Plan-Fingerprint `29afe357c56950572c0048cb42efa8bd0ecddeb652c21657f5b950030baee3d6`.

## Vor einem Versuch verbindlich

Die bereits vorhandene Equity-/ETF-Projektion umfasst 3.025.873 gültige Tagesbalken, 2.275 Asset-IDs (2016–2021) und hat Dataset-Fingerprint `321531c482d844df4d5513b58646b3f41553f47a7b2276517cb8473886c298d6`. Sie stammt aus eingefrorenen, `yfinance_auto_adjust_true`-OHLC und wird ausschließlich read-only verwendet. Die Zeiträume wurden im v7-r2-Development bereits betrachtet; ein neuer R3-Test darf sie **nicht** nachträglich „unseen Validation/Holdout“ nennen. Ein neuer R3-Vertrag muss vor Ergebnissichtung das Baseline-Vergleichsmaß, den einzelnen primären Feature-Vergleich, Population, Splits, Kostenstatus, Missingness, Fingerprints, Attempt Count und terminales Gate festlegen. Ohne echte unabhängige OOS-/Walk-Forward-Evidenz kann kein robuster C-/Challenger-/Holdout-Pfad behauptet werden.

Overnight-/Intraday-Merkmale bleiben beobachtend. Kein Pflichtfilter, keine Confluence, keine Retunes, keine Produktivregel und keine Öffnung von External/Forward/Paper/Shadow/Broker/Orders.

## Eingefrorener R3-Development-Vertrag vor Ergebnis

Der vor Ergebnissichtung festgelegte [Vertrag](config/overnight_intraday_r3_v1.json) hat Fingerprint `b908c5803e17e95691a78fee60d9f47ac25b43675091f3fca249ff84f5adcb41`. Es gibt genau einen Versuch. Primärmerkmal ist der kausale 20-Sitzungs-Overnight-Bias; Kontrolle ist die bis zur Signalkerze bekannte 20-Sitzungs-Close-to-Close-Rendite. Für 1/5/20 spätere abgeschlossene Sitzungen wird je Asset-Jahr die partielle Pearson-Korrelation des Primärmerkmals mit dem Forward Return bei Kontrolle der Baseline beschrieben. Renditeanteil sowie Overnight-/Intraday-Volatilität sind nur Nebenbeschreibungen, keine zusätzlichen Filter oder Auswahlvarianten. MFE/MAE sind Close-verankerte hypothetische Pfadmaße, keine handelbaren Outcomes. Kein Cutoff wird gesucht.

Alle Jahrgänge 2016–2021 bleiben als bereits gesehene Development-Daten gekennzeichnet. Wegen historisch ungeklärter Issuer-Dependencies ist ein robustes Effective N nicht belegt; deshalb kann dieser Versuch selbst bei interessanter deskriptiver Korrelation keinen Challenger oder Validation/Holdout freigeben. Der Runner nutzt einen separaten append-only Store, den globalen Research-Lock und echte Produktions-Lock-Gates; ein Pilot mit wenigen Assets muss vor dem Vollauf fehlerfrei fortsetzbar sein.
