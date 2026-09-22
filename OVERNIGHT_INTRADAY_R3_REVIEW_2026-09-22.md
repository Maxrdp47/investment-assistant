# R3 Overnight/Intraday – einmaliger Development-Review

Stand: 2026-09-22. Programm `finite-research-program-2026-09-15-v1`, R3-Versuch **1/1**. Vorheriger [Dedupe- und Freeze-Bericht](OVERNIGHT_INTRADAY_R3_DEDUPE_2026-09-22.md).

## Entscheidung

Der vorab festgelegte 20-Sitzungs-Overnight-Bias zeigt in dieser **bereits gesehenen Development-Population keinen stabilen inkrementellen Zusammenhang** mit späteren 1/5/20-Sitzungs-Renditen gegenüber der einfachen 20-Sitzungs-Close-to-Close-Baseline. R3 wird als `DEVELOPMENT_NEGATIVE_NO_ROBUST_INCREMENT` terminal geschlossen (Research-Einordnung A nur für diesen begrenzten Test). Es gibt keinen Challenger-Freeze und keine Validation- oder Holdout-Öffnung. Diese Entscheidung ist **kein allgemeiner Beweis**, dass Overnight-/Intraday-Merkmale nie nützlich sein können.

## Provenienz und Integrität

- Unveränderter Quell-Datensatz: Equity-/ETF-PIT-Projektion `equity-etf-historical-pit-2026.09.03-v1`, Fingerprint `321531c482d844df4d5513b58646b3f41553f47a7b2276517cb8473886c298d6`, Quelle eingefrorene `yfinance_auto_adjust_true`-OHLC. Keine Providerdownloads oder Änderungen am Frozen Dataset.
- Eingefrorener R3-Vertrag: `overnight-intraday-r3-2026.09.22-v1`, Fingerprint `b908c5803e17e95691a78fee60d9f47ac25b43675091f3fca249ff84f5adcb41`, Code-Freeze-Commit `f262ee01bdb9d59d0538725be6d496a5d2947e57`; [GitHub Smoke Test #50](https://github.com/Maxrdp47/investment-assistant/actions/runs/35753116626) bestanden.
- Separater append-only Ergebnis-Store `runtime/overnight_intraday_r3_v1.sqlite3`: 2.297 von 2.297 Asset-/Listing-Einheiten, 3.025.873 gültige Quellbalken, 36.822 Asset-Jahr-Horizont-Zusammenfassungen. 2.206 bereits als ungültig klassifizierte Quellbalken blieben ausgeschlossen. SQLite `quick_check=ok`, Fremdschlüsselprüfung ohne Befund, Review-Digest `0209d85b26e90a94c45a1448a9fecbde2c7d77212f63aac00adcde2e7bca4759`. Drei Pilot-Einheiten wurden aus der Quelle identisch reproduziert; Resume und Terminal-No-op erzeugten keine Dubletten.
- Knowledge-Base-Experiment `8389509b-dc70-41b6-9df9-e27c194f0a04` ist `COMPLETED`, ein einziges Resultat `3cc7e3a9-47a9-4e01-a20a-fd4e1e6f43d1` mit enger Einordnung `negative` und einer Ergebnis-Store-Referenz. Wiederholter Sync war idempotent.
- Abschließende Prüfungen nach R3: vollständige Suite **1.161 bestanden**, `compileall .` erfolgreich, Repository-Sicherheitscheck und Offline-Smoke einschließlich Streamlit-Start erfolgreich, `git diff --check` ohne Befund.

## Befund

Die Korrelation ist die je Asset-Jahr berechnete partielle Pearson-Korrelation von rollierendem Overnight-Bias und künftigem Close-to-Close-Return, bereinigt um die zum Signal bekannten vorherigen 20 Sitzungen. Berichtet wird der Median über Asset-Jahr-Gruppen mit mindestens 30 zulässigen Beobachtungen, **kein** gewichteter Trading-Return und **kein** unabhängiges Effective N.

| Horizont | zulässige Asset-Jahr-Gruppen | rohe Zeilen mit Label* | Median partielles r | Gruppen mit positivem r | Ø MFE / MAE ab Signal-Close** |
|---|---:|---:|---:|---:|---:|
| 1 Sitzung | 12.184 | 2.976.274 | +0,0041 | 52,1 % | +1,73 % / −1,58 % |
| 5 Sitzungen | 12.182 | 2.967.085 | +0,0012 | 50,4 % | +4,22 % / −3,63 % |
| 20 Sitzungen | 12.175 | 2.932.705 | −0,0103 | 48,3 % | +9,39 % / −7,05 % |

\* Wiederholte, überlappende historische Beobachtungen; keine unabhängigen Trades oder effektive Stichprobengröße. \** Reine hypothetische Pfadmaße ohne Entry, Spread, Slippage, Kosten oder Ausführung; nicht als Handelsergebnis interpretieren.

Der 1-Sitzungs-Median wechselt über die Jahre von negativ (2016/17) zu positiv (2018–20) und liegt 2021 wieder nahe null. Beim 20-Sitzungs-Horizont wechseln die Vorzeichen ebenfalls, mit einem deutlich negativen Jahr 2019. ETF-Gruppen liefern für 5 und 20 Sitzungen negative Mediane; die Gruppen sind kleiner als bei Aktien. Damit fehlt eine über Jahre und Assetklassen konsistente Richtung. Renditeanteil und Komponenten-Volatilität wurden nur als zuvor angekündigte Nebenmerkmale beobachtet, nicht zu einem zusätzlichen Filter oder zweiten Versuch kombiniert.

## Gate und nächste Stufe

Sämtliche Jahre 2016–2021 waren bereits Teil des v7-r2-Development-Reviews. Diese interne Zeitdiagnose ist **keine** neue ungesehene Out-of-Sample-/Walk-Forward-Validation. Historische Issuer-/Listing-Dependencies sind nicht vollständig geklärt; das vertragliche unabhängige Effective N ist `UNKNOWN`. Ein robustes C-Rating, Challenger oder neuer Pflichtfilter ist unzulässig. Ein handelbarer Variantentest wurde nicht definiert, daher ist ein Kosten-/Slippage-Ergebnis hier `NOT_APPLICABLE_NO_TRADABLE_VARIANT`.

Gemäß der freigegebenen endlichen Reihenfolge folgt **R4 Historical/PIT Capability Expansion** als Daten- und Messarbeit vor v2-Outcomes. R1 und R2 bleiben unverändert terminal beziehungsweise R2 datenblockiert. External, Forward, Paper, Shadow, Broker, Orders und Produktion bleiben geschlossen.
