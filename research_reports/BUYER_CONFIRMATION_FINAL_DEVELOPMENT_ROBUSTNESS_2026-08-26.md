# Buyer Confirmation – finaler Development-Robustheitscheck

Stand: 2026-08-26

Status: abgeschlossen, ausschließlich Development

Finale Entscheidung: **C_RECOMMENDATION**

## Entscheidungsgrenze

Die Empfehlung bedeutet ausschließlich: Die Development-Evidenz ist robust genug, um in einem späteren getrennten Auftrag genau einen einfachen Challenger fest einzufrieren und erstmals gegen ungesehene Validation-Daten zu prüfen.

Sie bedeutet ausdrücklich nicht: bestätigte Strategie, bestandene Validation, Produktion, Live Trading oder automatische Aktivierung. Validation und Holdout blieben ungeöffnet. Es wurde kein Challenger erzeugt und kein Freeze geschrieben.

## 1. Verifizierte Baseline

Regel: `Close[t] > High[t-1]`

Scope: ausschließlich `objective_pullback`

| Gruppe | Raw N | Effective N | Ø R | Profit Factor | Trefferquote |
|---|---:|---:|---:|---:|---:|
| Buyer Confirmation | 64.459 | 49.438 | +0,08397 | 1,16772 | 46,39 % |
| Control | 317.181 | 104.407 | -0,12814 | 0,83255 | 36,93 % |

Unbereinigtes Delta: **+0,21211 R**.

Der frühere Audit-JSON wurde fingerprint-verifiziert. Dabei wurde zugleich ein reiner Berichtsfehler sichtbar: Der alte Markdowntext nannte für das frühere Regime-Matching `+0,1649 R`; der tatsächlich gespeicherte, reproduzierte JSON-Wert beträgt **+0,14264 R** bei 64.447 Fällen je Gruppe. Die alte Datei wurde nicht verändert; dieser Bericht ist das append-only Erratum.

## 2. Verbessertes outcome-blind Matching

Die alte Bezeichnung war zu weitgehend. Tatsächlich enthielt das frühere Matching nur Assettyp, Marktphase, Volatilitätsregime und Jahr – kein einzelnes Asset oder Symbol.

Neu geprüft wurden zusätzlich Region, Dependency Cluster und Symbol. Das strengste vorab definierte Matching mit ausreichender Abdeckung wurde über Fallzahlen, nicht Outcomes, gewählt:

- 36.772 Treatment und 36.772 Control
- 32.975 effektive Dependency Cluster je Gruppe
- 27.687 Treatment- und 280.409 Control-Fälle blieben unmatched
- keine künstliche Gleichgewichtung kleiner Segmente
- Auswahl ausschließlich über stabile Identitätshashes

Da ein einzelner Hash-Samen bei großen Control-Pools zufällige Ergebnisschwankungen erzeugen kann, wurden fünf feste outcome-blinde Wiederholungen vollständig berichtet. Das strukturelle Delta blieb in allen fünf positiv:

- Minimum: **+0,20221 R**
- Median: **+0,26181 R**
- Maximum: **+0,44245 R**

Kein Seed wurde anhand des Ergebnisses ausgewählt.

## 3. Risikogeometrie

Buyer Confirmation tritt tatsächlich später und weiter oberhalb des Pullback-Lows auf.

| Median | Buyer Confirmation | Control |
|---|---:|---:|
| Entry über Pullback-Low | 5,17 % / 1,94 ATR | 2,00 % / 0,79 ATR |
| Stopdistanz | 5,86 % / 2,19 ATR | 2,55 % / 0,99 ATR |
| 2R-Targetdistanz | 11,72 % / 4,38 ATR | 5,11 % / 1,98 ATR |

Damit ist der R-Nenner bei Buyer Confirmation größer. Er arbeitet gegen, nicht für eine mechanische Aufblähung des R-Ergebnisses. Der durchschnittliche reale Ergebnisunterschied in Prozent ist positiv (+0,486 Prozentpunkte), während Median-MFE und Median-MAE in Prozent praktisch gleich sind. Die Geometrie erklärt den Befund daher nicht ausschließlich, beweist aber auch keine kausale Verbesserung der Kursbewegung.

64.201 Treatment- und 293.130 Control-Fälle hatten vollständig gültige Risikogeometrie. Ungültige oder fehlende Geometrie wurde nicht als Nullwert behandelt und nicht zur Verbesserung der Performance entfernt.

## 4. MFE, MAE und Entry-Effizienz

| Kennzahl | Buyer Confirmation Ø / Median | Control Ø / Median |
|---|---:|---:|
| MFE | 8,96 % / 6,12 % | 9,09 % / 6,12 % |
| MAE | -7,59 % / -5,21 % | -7,42 % / -5,09 % |
| MFE in ATR | 3,03 / 2,40 | 3,13 / 2,46 |
| MAE in ATR | -2,69 / -1,94 | -2,74 / -1,96 |
| MFE in R | 1,73 / 1,06 | 7,81 / 2,32 |
| MAE in R | -1,45 / -0,87 | -6,42 / -1,87 |
| Giveback in R | 1,65 / 1,14 | 7,94 / 2,31 |
| Sitzungen bis MFE | 14,12 / 15 | 14,14 / 15 |
| Sitzungen bis Horizontende | 25 / 25 | 25 / 25 |

Der große Unterschied der R-normalisierten Control-Werte folgt vor allem aus deren deutlich kleinerer Stopdistanz. In Prozent und ATR ist die spätere Kursbewegung beider Gruppen ähnlich.

Buyer Confirmation erreichte:

- mindestens 0,5R MFE: **74,16 %**
- mindestens 1R MFE: **52,34 %**
- mindestens 1,5R MFE: **35,88 %**
- mindestens 2R MFE: **24,44 %**
- positives MFE: **98,39 %**

`time_to_first_positive` ist nicht gespeichert. Es wird nicht behauptet, dass Buyer Confirmation früher positiv läuft.

## 5. Sensitivity Stress

Diese pauschalen R-Abzüge sind ausschließlich `SENSITIVITY_STRESS`, keine Fill- oder Broker-Simulation:

| Szenario | Expectancy |
|---|---:|
| Basis | +0,08397 R |
| zusätzlicher Abzug 0,05R | +0,03397 R |
| zusätzlicher Abzug 0,10R | -0,01603 R |
| zusätzlicher Abzug 0,15R | -0,06603 R |
| bisheriger Gap-Abzug | -0,00646 R |

Die Hypothese bleibt damit gegenüber großen pauschalen R-Abzügen empfindlich. Diese Sensitivität wird als False-Positive-/Kostenrisiko beibehalten.

## 6. Realistischere Execution-Prüfung

Der vorhandene Vertrag ist bereits kausal und realistisch definiert:

- Signal erst nach abgeschlossener Kerze
- Einstieg am nächsten verfügbaren Open
- gespeicherte Einwegkosten
- Pullback-Low minus 0,25 ATR als Stop
- festes 2R-Target, maximal 25 Sitzungen
- Daily-Reihenfolge: Gap, dann Stop, dann Target

Die einzige vorab festgelegte konservativere Variante addierte 5 Basispunkte adverse Slippage je Seite zu den gespeicherten Kosten. Es wurde keine zweite Entry-Variante getestet oder ausgewählt.

| Gematchte Gruppe | Baseline Ø R / PF | konservativ Ø R / PF | Winrate konservativ |
|---|---:|---:|---:|
| Buyer Confirmation | +0,05245 / 1,10049 | **+0,03859 / 1,07397** | 44,69 % |
| Control | negativ | -0,25254 / 0,68404 | 34,67 % |

Konservatives Delta: **+0,29113 R**. Effective N: 32.975 je Gruppe. Keine realistischen Entry-Fills fehlten. 3.705 Treatment- und 3.943 Control-Fälle waren Gap-Fälle. 86 Treatment- und 1.078 Control-Fälle waren wegen ungültiger Ausführungsgeometrie nicht auswertbar; sie wurden nicht als Gewinner oder Nullergebnis behandelt.

Die rekonstruierte Baseline stimmte in allen auswertbaren Fällen exakt mit den gespeicherten Broad-v1-Ergebnissen überein: 0 Abweichungen, maximale Differenz 0 R. Es wird keine Intrabar-Reihenfolge behauptet.

## 7. Dependency- und Redundanzprüfung

Buyer Confirmation und `candle_quality.close_above_prior_high` waren in allen 381.640 verglichenen Pullback-Fällen identisch. Sie zählen exakt einmal.

Kontrolliert wurden ausschließlich die bekannten Strukturen: bearishe Kerzen >=3, Pullback-Tiefe, Pullback-Dauer, relatives Momentum, Close Location, EMA-Trend, BOS, Volatilitätsregime und Marktphase.

Das ausreichend große Dependency-Profil-Matching enthielt 50.254 Fälle je Gruppe und rund 40.000 effektive Cluster. Über fünf feste outcome-blinde Seeds blieb der inkrementelle Restvorteil immer positiv, aber klein:

- Minimum: **+0,01092 R**
- Median: **+0,01530 R**
- Maximum: **+0,02204 R**

Das streng kombinierte Symbol-/Cluster-/Dependency-Matching behielt nur 1.356 Fälle je Gruppe und wurde wegen der großen Fallzerstörung nicht erzwungen. Es zeigte ebenfalls ein positives Delta, wird aber nicht als belastbarer Hauptnachweis verwendet. Kein Kausalitätsclaim.

## 8. Zeit-, Regime- und Scope-Stabilität

- 7 von 9 beobachteten Jahren positiv
- negativ: 2011 (-0,056R) und 2018 (-0,074R)
- alle fünf Marktphasen positiv
- alle drei Volatilitätsregime positiv
- Aktien, ETF und Krypto positiv
- Europa leicht negativ (-0,011R; N=2.410)
- Südamerika negativ, aber nur N=27 und damit nicht interpretierbar
- USA dominiert mit 91,22 % der Fälle; der Ergebnisanteil von 93,05 % ist hierzu nicht stark überproportional
- stärkstes Ergebnisjahr 2017 trägt 28,95 % der absoluten Jahresergebnisse, also keine Ein-Jahres-Dominanz

Negative Regionen und Jahre wurden nicht ausgeschlossen und es wurden keine neuen Segmentfilter gebaut.

## 9. False-Positive-Risiken

Die C-Empfehlung bleibt belastet durch:

- acht vorab getestete Broad-Hypothesen
- stark überlappende Kandidaten; Raw N ist kein unabhängiges N
- unvollständige historische Constituents-/Delisting-/Bankruptcy-Abdeckung
- kein vollständig Point-in-Time- und survivorship-freies Universum
- semantisches Alias-Feature
- kleinen dependency-adjustierten Restnutzen
- negative pauschale 0,10R-/0,15R- und Gap-Sensitivitäten
- weiterhin vollständig ungesehene Validation- und Holdout-Splits

Es wurden keine naiven unabhängigen Kandidaten-p-Werte verwendet.

## 10. Finale Entscheidung

**C_RECOMMENDATION**

Alle harten Development-Mindestbedingungen wurden erfüllt. Ausschlaggebend sind nicht die unbereinigte Effektgröße, sondern:

1. positive Baseline mit PF > 1,
2. positiver struktureller Vorteil in allen fünf Matching-Seeds,
3. kleiner, aber positiver inkrementeller Restnutzen in allen fünf Dependency-Seeds,
4. keine ausschließliche Erklärung über einen günstigeren R-Nenner,
5. weiterhin positive realistischere Execution,
6. ausreichendes Raw/effective N,
7. keine dominierende Abhängigkeit von einem einzelnen Jahr oder Regime.

## 11. Challenger-Entwurf – noch nicht eingefroren

- Name: `buyer-confirmation-objective-pullback-v1-draft`
- Scope: `objective_pullback`
- einzige Regel: `Close[t] > High[t-1]`
- Entry: nächstes verfügbares Open nach abgeschlossener Signalkerze
- Stop: Pullback-Low minus 0,25 ATR14
- Exit: festes 2R-Target, maximal 25 Sitzungen
- Kosten: gespeicherter Broad-v1-Ausführungskostenvertrag
- Dataset-Fingerprint: `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`
- Feature-Contract: `c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd`
- Code-Contract: `77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946`
- keine Zusatzfilter oder Confluence

Insbesondere kein RSI, EMA, BOS, bearish-candle-, Fibonacci-, Volumen-, Volatilitäts- oder Regimefilter.

## 12. Schutz- und Artefaktstatus

- Broad-v1: unverändert
- Frozen Dataset: unverändert
- Manifest-Fingerprint: `7531b0b8411436b3bbaf31d1db4bab94e35ecb0360f094cdbb96baf0d6297bf5`
- Validation geöffnet: nein
- Holdout geöffnet: nein
- Long-v1 geöffnet: nein
- Challenger erzeugt: nein
- Freeze erzeugt: nein
- Produktion verändert: nein
- finaler Report-Fingerprint: `5400858a75aa4cb581e5af2552b0b78d7df3f7a10facdd2cb53a2baee4db1b74`

Die vorläufigen v1/v2/v3-reviewed/final-Exports bleiben append-only erhalten. Maßgeblich ist ausschließlich `buyer_confirmation_development_robustness_2026-08-26-v3-authoritative.json`.
