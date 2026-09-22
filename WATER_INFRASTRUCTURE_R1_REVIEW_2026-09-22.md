# R1 Wasser-Infrastruktur – Development-Abschluss

Stand: 2026-09-22. Programm `finite-research-program-2026-09-15-v1`, Versuch 1, Version `water-infrastructure-research-2026.09.15-v1`.

## Entscheidung

`DEVELOPMENT_INCONCLUSIVE` (kanonisches Validity Gate: `UNDERPOWERED`). Dies ist ein terminaler R1-Versuch, kein robuster Handelsvorteil und keine Erlaubnis zum Retuning. Es wurde keine Challenger-Version freigegeben. Validation und Holdout wurden nicht geöffnet; External, Forward, Paper, Shadow, Broker, Orders und Produktion blieben geschlossen.

## Eingefrorener Vertrag und Provenienz

- Universum: XYL, BMI, PNR; SPY und PHO als vorab festgelegte Vergleiche. Kein Titel wurde nach seinem Ergebnis ausgewählt oder entfernt.
- Primärsignal: Korrektur von mindestens 15 % gegenüber dem vorherigen 252-Sitzungs-Schlusshoch, danach erster Schluss über dem vorherigen 60-Sitzungs-Hoch; Eintritt am nächsten verfügbaren Open. Primärhorizont der Gate-Bewertung: 20 abgeschlossene Sitzungen. Sensitivitäten (10/20 % Korrektur, 40/120 Sitzungen) waren vor dem Ergebnis festgelegt.
- Outcome-unabhängige Splits: Development 2010–2017, Validation 2018–2021, Holdout 2022–2026-08-23. Ausschließlich Development wurde gesehen.
- Quelle: Yahoo Finance via yfinance, versionierter Retrieval-Snapshot vom 2026-09-22. Adjustierte Tages-OHLC sind keine native bitemporale Vendor-Historie; deshalb keine stärkere PIT-Behauptung. Fehlende/ungültige Zeilen wurden nicht imputiert. XYL beginnt 2011-10-13; die anderen vier Reihen beginnen 2010-01-04. Alle Reihen enden 2026-08-21.
- Dataset-Fingerprint `a12525a8a6b4c1165fe7cea2ee725d42ef6b6f858c49b4ccac9899abd4b2c78d`; Contract-Fingerprint `e34542275cefdb08683cbe61f1d26e8acb900cecbea1efdcd4552506163630f4`; Freeze-Fingerprint `de89a176b9b6f83ff20f213fd80cf0c1ebc9c528a77d389f50c16363fcd80d4b`; Review-Fingerprint `ed7439b8b4446d40428a0f6ec2eeb57bc22a4501c2ac18e208f3cf1593fdf5dc`.
- Der Append-only-Result-Store enthält 546 Fallzeilen über Primärhorizonte, Kontrollen und vorab fixierte Sensitivitäten. Das sind **nicht** 546 unabhängige Primärtrades. Dataset-, Result- und Knowledge-Base-Stores: `PRAGMA quick_check=ok`, keine Fremdschlüsselverletzungen.

## Deskriptiver Development-Befund

| Kennzahl (20 Sitzungen, netto) | Wert |
|---|---:|
| Primäre Aktien-Setups | 7 |
| Primäre Trefferquote | 5/7 (71,4 %) |
| Mittlere Primärrendite | +2,81 % |
| Profit Factor der Primärfälle | 3,28 |
| Mittlere matched Non-Signal-Kontrolle | +3,05 % |
| Mittlerer SPY-/PHO-Vergleich | +0,98 % / +1,98 % |
| Effective N, Treatment / Control | 3 / 4 |
| Erforderliches Raw / Effective N je Gruppe | 200 / 100 |
| Anteil positiver beobachteter Jahre | 1/3 |
| Größter Jahresanteil am absoluten Ergebnis | 76,6 % |

Diese Zahlen sind nur beschreibend. Das Mindest-N wird klar verfehlt, die matched Kontrolle liegt höher, die Jahre sind instabil, und eine vorab definierte Sensitivität hat gar keine Fälle. Der gleichgewichtete Wasser-Korb lieferte in Development kein eigenes Primärsignal (`n=0`); es gibt daher keine Korb- oder Portfolioaussage. Die 95-%-Cluster-Bootstrap-Spanne des Primärmittels reicht etwa von −5,26 % bis +5,66 % und ist ausdrücklich `DESCRIPTIVE_ONLY`.

## Abschluss und Fortsetzung

Knowledge-Base-Work-Request `3721453e-158f-42cb-8d76-a28f054b7d97` ist `COMPLETED`, Result-ID `99197886-6ff7-4e37-a811-73ee4abe9b1a`. Ein erneuter Runner-Aufruf ergab `TERMINAL_NO_OP`; keine doppelten Fälle oder Reviews. Ein reines Übergabeformatproblem beim ersten KB-Abschluss (Kostenobjekt statt numerischem Feld) wurde ohne Neuberechnung des Research-Ergebnisses behoben. Der unveränderte Research-Review blieb append-only.

Gemäß dem freigegebenen endlichen Programm folgt R2 Gold/Silber als getrennter Futures-Preflight. R1 darf nicht zur Optimierung eines weiteren Wasser-Versuchs verwendet werden.
