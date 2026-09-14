# Multi-Asset Discovery v7-r2 – fachlicher Development-Review

Datum: 2026-09-14

Run: `mad1-development-v7-recovery-20260913-v2`

Review-Status: `V7_R2_DEVELOPMENT_REVIEW_COMPLETE_AWAITING_HYPOTHESIS_DECISION`

## 1. Executive Summary

Der technische v7-r2-Recovery-Lauf ist vollständig und sein Final Audit ist `PASS`. Der vorliegende Review hat alle 2.356.553 Feature-/Outcome-Paare ausschließlich lesend geprüft. 1.749.125 Fälle (74,2239 %) besitzen den vollständigen 252-Beobachtungs-Pfad; 607.428 Fälle (25,7761 %) sind zensiert und wurden nicht als Gewinn, Verlust, Nullrendite oder intakte Safe Zone interpretiert.

Das fachliche Ergebnis ist bewusst konservativ:

- Es gibt **0** Befunde der Klasse `ROBUST_CANDIDATE_FOR_NEW_HYPOTHESIS`.
- Volatilität, RSI/Mean-Reversion, Abstand zur bestätigten Sell-Zone A und Safe-Zone-Geometrie zeigen deskriptiv interessante Muster, aber jeweils auch mindestens eine harte Gegenanzeige: Risiko-/Upside-Konflikt, Asset-/Regimeinstabilität, starke Schiefe, Complete-Case-Selektion, mechanische Redundanz oder fehlende unabhängige Dependency-Evidenz.
- Positive Return-/EMA-Zustände reduzieren häufig die spätere MAE und erhöhen teilweise die Safe-Zone-Survival, gehen aber gleichzeitig mit niedrigerer mittlerer MFE und 252-Tage-Rendite einher. Das ist ein Pfad-Trade-off und kein eindeutiger Qualitätsfilter.
- Overnight, Gap, Intraday und Volumenverhältnis liefern keinen stabilen eigenständigen Zusatznutzen. `gap_atr` und `overnight_return` sind in der Vorzeichenbetrachtung vollständig redundant.
- Alle 2.356.553 Fälle besitzen `dependency_status = UNKNOWN`. Nach dem eingefrorenen Dependency-Vertrag tragen solche Fälle 0 zum effektiven N bei; das vertragliche effektive N dieses Reviews ist daher 0. Eine große Raw-N-Zahl darf diese Grenze nicht verdecken.

Der Review eröffnet keine neue Hypothese, keinen Runner und keine Research-Stufe. Validation, Holdout, External, Forward, Paper, Shadow, Broker und Orders bleiben geschlossen.

## 2. Daten-/Evidenzgrenzen

### 2.1 Geprüfter Bestand

| Bereich | Ergebnis |
|---|---:|
| Feature-Cases | 2.356.553 |
| Outcome-Cases | 2.356.553 |
| vollständig gepaarte und identische Case-IDs | 2.356.553 |
| `COMPLETE` | 1.749.125 |
| `CENSORED_AT_STAGE_BOUNDARY` | 486.312 |
| `CENSORED_AT_INPUT_GAP` | 106.954 |
| `CENSORED_AT_END_OF_AVAILABLE_DATA` | 14.162 |
| Structural R verfügbar, alle Cases | 2.110.648 (89,5651 %) |
| Structural R nicht verfügbar, alle Cases | 245.905 |
| Structural R verfügbar, nur `COMPLETE` | 1.559.024 (89,1317 %) |
| Structural R nicht verfügbar, nur `COMPLETE` | 190.101 |

Die vollständige Evidenz umfasst 1.968 Equity-, 58 ETF- und 23 Crypto-Symbole. FX besitzt 0 vollständige Development-Outcomes und kommt in den finalen Feature-/Outcome-Stores nicht als Case vor. Aus diesem Lauf ist daher keine FX-Edge-Aussage zulässig.

### 2.2 Censoring und Complete-Case-Selektion

Die Assetklassen besitzen ähnliche, aber nicht identische Complete-Anteile: Equities 1.680.491/2.263.068, ETF 48.123/66.192 und Crypto 20.511/27.293. Besonders kritisch ist das Signaljahr 2021: Nur 2.663 von 512.248 Fällen sind vollständig (0,5199 %); 486.241 enden an der Stage-Grenze. 2021 ist damit kein belastbares Stabilitätsjahr.

Die Selektion ist bei längerfristigen Trendmerkmalen sichtbar. Beispiele:

- `close_above_ema200`: Complete-Anteil 70,4827 % oberhalb gegenüber 81,4976 % unterhalb.
- `ema50_above_ema200`: 69,4881 % gegenüber 84,0759 %.
- `return_60_positive`: 73,0604 % gegenüber 76,0376 %.

Negative oder positive aggregierte Unterschiede dieser Gruppen können deshalb nicht ohne Weiteres als Featurewirkung gelesen werden.

### 2.3 Abhängigkeit, Raw N und Missingness

`dependency_status` ist für sämtliche 2.356.553 Fälle `UNKNOWN`; kein historischer Issuer ist nach dem eingefrorenen Dependency-Vertrag verifiziert. Der dort definierte Ansatz – maximale paarweise nicht überlappende 252-Beobachtungsfenster je verifiziertem Issuer, unbekannte Dependencies mit Beitrag 0 – ergibt:

- verifizierte Issuer: 0
- effektives N: 0

Die Symbolbreite widerlegt zwar eine Konzentration auf nur ein oder zwei Ticker, ersetzt aber keine verifizierte Issuer-/Listing-Abhängigkeit und keine unabhängige Stichprobe.

Technische PIT-Felder sind nahezu vollständig. `volume_ratio_20` fehlt bei 1.292 vollständigen Fällen. Safe Zones A/B/C sind vollständig vorhanden. Sell Zone A ist bei 1.632.512 und B bei 1.631.025 der vollständigen Fälle verfügbar; Sell Zone C ist vollständig vorhanden.

### 2.4 Methodik dieses Reviews

- Future-Pfadkennzahlen verwenden ausschließlich `COMPLETE`-Fälle.
- Zensierte Fälle werden nur für Coverage, Missingness und Complete-Case-Selektion verwendet.
- Merkmale werden einzeln betrachtet. Es gibt keine Kombination, keine Grid Search und keinen Gesamtscore.
- Binäre Vergleiche verwenden nur natürliche Zustände (positiv/nicht positiv, EMA-Reihenfolge, 20er- gegen 60er-Volatilität) oder bereits eingefrorene Deterioration-Grenzen (`RSI14 < 40`, `volume_ratio_20 < 0,5`).
- Kontinuierliche Merkmale werden ergänzend als lineare Richtungsbeziehung zu Return, MFE und MAE beschrieben; es wurde kein Cutoff gesucht.
- Prozent-Returns, MFE, MAE und Structural R sind reine Research-Outcomes. Es gibt keinen Entry-/Exit-/Kosten-/Portfoliovertrag und daher keine Strategie-Performance-Aussage.
- Die deskriptiven Mittelwerte sind bei einzelnen Gruppen stark schief. Sehr große Standardabweichungen und extreme Overshoots werden als Grenze, nicht als Evidenzverstärkung behandelt.

Das separate, nicht als neue Research-Stufe verstandene Review-Evidence-Artefakt besitzt den Fingerprint `a06961e0b7791b7d5a8f22869562af057393b5ac268f030a4f909d0824fd66fd`.

## 3. Safe-Zone Review

### 3.1 Availability und Breaches

Alle drei Safe Zones sind für alle vollständigen Fälle vorhanden. Über 252 verfügbare Beobachtungen ergibt sich:

| Safe Zone | Close-Breach | Intraday-Breach | bestätigte Invalidation-first-Rate* | gleiche Beobachtung, Reihenfolge unbekannt |
|---|---:|---:|---:|---:|
| A | 78,4852 % | 82,4453 % | 24,4065 % | 7,6697 % |
| B | 73,9040 % | 77,6846 % | 37,3260 % | 9,3942 % |
| C | 70,0992 % | 73,9151 % | 38,3913 % | 0,1297 % |

\* Close-Breach vor Sell-Zone-Hit oder Close-Breach ohne späteren Hit innerhalb des 252er-Fensters. Gleichzeitige Beobachtungen werden nicht geordnet.

Die niedrigere Breach-Rate von C gegenüber B und A zeigt sich in allen Assetklassen, Jahren und Marktregimen. Das ist aber wesentlich durch die Konstruktion erklärbar: C liegt tiefer als B, B typischerweise tiefer als A. Die stabile Reihenfolge beweist Daten-/Messkonsistenz, nicht die Überlegenheit eines Stops.

Die Breach-Niveaus variieren stark. Für C reichen die Close-Breach-Raten von 42,7029 % (2016) über 83,4431 % (2018) und 86,5031 % (2019) bis 52,4095 % (2020). Der 2021-Wert von 25,4976 % ist wegen nur 2.663 vollständiger Fälle und 99,48 % Censoring nicht als Regimestabilität verwertbar. Nach Assetklasse liegt C bei 59,4315 % Crypto, 70,4613 % Equities und 62,0036 % ETF; nach Marktregime bei 80,7599 % Downtrend, 71,8152 % Mixed und 63,0078 % Uptrend.

### 3.2 MFE/MAE und Structural R

Fälle ohne späteren Close-Breach besitzen erwartungsgemäß weniger negative MAE und höhere MFE/Endreturns als Fälle mit Breach. Diese Trennung konditioniert jedoch auf ein zukünftiges Ereignis und ist daher eine Diagnose des Pfads, kein PIT-Prädiktor.

Structural R ist bei 10,8683 % der vollständigen Fälle nicht verfügbar. Darüber hinaus entstehen bei sehr kleinen strukturellen Distanzen extreme R-Werte; die Mittelwerte nach Breach sind entsprechend instabil. Prozent-MFE/-MAE und Availability werden deshalb als primäre Diagnose berichtet. Ein Vergleich A/B/C als fertige Stopregel wäre ohne eigenen, vorab eingefrorenen Entry-/Exit-/Kostenvertrag unzulässig.

**Review-Klasse:** `INTERESTING_BUT_INSUFFICIENT` für die stabile geometrische Breach-Reihenfolge; `NOT_INTERPRETABLE` für eine Aussage zur Stop-Überlegenheit.

## 4. Technische Featurefamilien

### 4.1 Returns / Momentum / RSI

Positive kurzfristige und mittlere Returns zeigen im 252er-Pfad niedrigere mittlere Return- und MFE-Werte, aber meist weniger negative MAE und häufiger intakte Safe Zones. Beispiele für den Unterschied „positiv minus nicht positiv“:

| Merkmal | Δ Return % | Δ MFE % | Δ MAE % | Δ Safe-C-Survival |
|---|---:|---:|---:|---:|
| `return_5_positive` | -6,5852 | -10,9903 | +1,0940 | +14,3963 %-Pkt. |
| `return_20_positive` | -8,4375 | -13,9260 | +1,8215 | +17,1486 %-Pkt. |
| `return_60_positive` | -14,1816 | -21,1760 | +1,3867 | +8,4394 %-Pkt. |

Das ist kein einheitlicher „guter“ oder „schlechter“ Zustand: Upside und Pfadrisiko bewegen sich gegensinnig. Die kontinuierlichen Beziehungen von `return_20` und `return_60` zum 252er-Return sind nahe null (`r = 0,0016` beziehungsweise `0,0004`).

`RSI14 < 40` zeigt ein konträres Muster. Gegenüber RSI >= 40 liegen mittlerer 252er-Return um 17,2830 Prozentpunkte und MFE um 27,6564 Prozentpunkte höher. Gleichzeitig ist MAE um 3,2629 Prozentpunkte negativer und Safe-C-Survival um 24,7571 Prozentpunkte niedriger; die positive 252er-Close-Fraktion steigt nur um 0,5764 Prozentpunkte. Der Return-Unterschied ist in allen drei Assetklassen und in 2016–2020 positiv und innerhalb von 1.738 Symbolen positiv gegenüber 288 negativ, kippt aber im Mixed-Regime und im stark zensierten Jahr 2021. Das ist eine ausgeprägte Mean-Reversion-/Risiko-Asymmetrie, kein eindeutiger Zusatzfilter.

**Review-Klasse:** `INTERESTING_BUT_INSUFFICIENT`.

### 4.2 EMA / Trend

Die Zustände `close_above_ema20/50/200` und `ema20_above_ema50`/`ema50_above_ema200` liefern denselben Grundkonflikt: geringere mittlere 252er-Returns und MFE, aber oft weniger negative MAE und mehr Safe-Zone-Survival. Für `close_above_ema20` betragen die Differenzen -10,3144 Return-, -17,1619 MFE- und +1,9043 MAE-Prozentpunkte sowie +19,4889 Prozentpunkte Safe-C-Survival.

Die Return-Richtung ist für Equities und ETF überwiegend negativ, bei Crypto für mehrere längere EMA-Zustände positiv. Die langfristigen EMA-Gruppen besitzen außerdem die stärksten Complete-Case-Unterschiede. Marktregime und EMA-Zustände sind semantisch nicht unabhängig. Dadurch ist die scheinbare Mehrfachbestätigung innerhalb dieser Familie redundant.

**Review-Klasse:** `INTERESTING_BUT_INSUFFICIENT`, wegen Complete-Case-Selektion und Assetklassenwechsel teilweise `NOT_INTERPRETABLE`.

### 4.3 Higher High / Higher Low, Konsolidierung, Breakout/Pullback, Support/Resistance

Explizite PIT-Felder für Higher High/Higher Low, Konsolidierung, Breakout-/Pullback-Kontext oder Relative-Support/Resistance existieren nicht. Vorhanden sind die Safe-/Sell-Zonen und `confirmed_swing_low_count` als Konstruktionsmetadaten. Dessen lineare Beziehung zu 252er-Return/MFE ist gering (`r = 0,0228/0,0231`), während der Mittelwert zwischen vollständigen und zensierten Fällen stark abweicht (95,98 gegenüber 146,80 bestätigten Swing Lows). Der Zähler ist damit auch ein History-/Coverage-Proxy.

Der Abstand zur bestätigten Sell Zone A ist der interessanteste Support-/Resistance-nahe Befund: Seine Beziehung zu Return/MFE ist bei Equities (`r = 0,2243/0,2282`) und ETF (`0,1178/0,1368`), in allen Jahren und in allen Marktregimen positiv. Bei Crypto ist sie negativ; MAE wird überwiegend negativer, 6,67 % der vollständigen Fälle besitzen keine Zone A, und extreme Pfadwerte treiben die Mittelwerte. Das reicht nicht für eine robuste neue Hypothese.

**Review-Klasse:** Sell-Zone-A-Abstand `INTERESTING_BUT_INSUFFICIENT`; die nicht vorhandenen Strukturfelder `NOT_INTERPRETABLE`.

### 4.4 Relative Strength / Marktvergleich

Es existieren keine PIT-Felder für Benchmark-, Sektor- oder Cross-Sectional-Relative-Strength. Der vorhandene `market_regime` ist kein Ersatz für Relative Strength.

**Review-Klasse:** `NOT_INTERPRETABLE`.

## 5. Markt-/Regime-Stabilität

Der `market_regime`-Wert ist vollständig befüllt: 275.680 Downtrend-, 852.677 Mixed- und 620.768 Uptrend-Fälle sind `COMPLETE`. Nach 252 Beobachtungen liegen die deskriptiven Werte bei:

| Marktregime | Mittel Return % | Mittel MFE % | Mittel MAE % | positive 252er-Close-Fraktion | Return-Standardabweichung % |
|---|---:|---:|---:|---:|---:|
| Downtrend | 51,9907 | 99,9637 | -26,4325 | 67,8617 % | 1.543,3107 |
| Mixed | 29,7072 | 63,5700 | -23,5092 | 65,9849 % | 184,2053 |
| Uptrend | 20,9334 | 48,3997 | -21,8987 | 64,7144 % | 104,9554 |

Der höhere mittlere Downtrend-Return steht zusammen mit höherer MFE, tieferer MAE und extremer Schiefe. Er ist ein möglicher Mean-Reversion-/Volatilitätseffekt, keine Marktregime-Edge. EMA-/Momentum-Effekte wechseln innerhalb der Regime teilweise das Vorzeichen; ein separates `volatility_regime`-Feld existiert nicht.

**Review-Klasse:** `INTERESTING_BUT_INSUFFICIENT`; Volatilitätsregime `NOT_INTERPRETABLE`.

## 6. Sell-Zonen

Sell Zones sind Messreferenzen, keine Exitregeln.

| Sell Zone | Availability in `COMPLETE` | Hit-Rate bei Availability | mittlerer max. Overshoot bei Hit | maximaler Overshoot |
|---|---:|---:|---:|---:|
| A | 93,3331 % | 97,8018 % | 61,3805 % | 50.600,0000 % |
| B | 93,2481 % | 89,3872 % | 63,2312 % | 174.765,2701 % |
| C | 100,0000 % | 92,1421 % | 54,6985 % | 64.775,3823 % |

Die langen 252er-Fenster und die breite Assetmischung erklären einen Teil der hohen Hit-Raten. Die Overshoots sind extrem rechtsschief; insbesondere Crypto-Mittelwerte liegen weit über Equity/ETF. Ein Mittelwertvergleich darf daher keine Exitentscheidung begründen.

Fälle mit Hit besitzen erwartungsgemäß andere Gesamtpfade als Fälle ohne Hit. Diese Trennung verwendet jedoch den künftigen Hit selbst. Das Outcome-Schema enthält keinen eindeutig zone-spezifischen, zeitlich geordneten Rejection-/Reversal-Pfad; `final_giveback_pct` bezieht sich auf den Gesamtpfad. Rejection/Reversal nach einem bestimmten Zone-Hit ist deshalb `NOT_INTERPRETABLE`.

**Review-Klasse:** Hit/Overshoot `INTERESTING_BUT_INSUFFICIENT`; Exitnutzen und zone-spezifische Rejection `NOT_INTERPRETABLE`.

## 7. Deterioration / Protective Zones

Deterioration-Zähler werden erst im zukünftigen Beobachtungsfenster gebildet. Sie sind wertvolle Diagnosen, aber keine PIT-Eingangsmerkmale dieses Reviews.

| künftige Deterioration über 252 Beobachtungen | positive Endrendite: mittlere Anzahl | nicht positive Endrendite: mittlere Anzahl |
|---|---:|---:|
| Close unter Signal-EMA20 | 52,1428 | 171,7071 |
| RSI14 unter 40 | 28,3187 | 61,2516 |
| Volume Ratio unter 0,5 | 18,9573 | 21,4386 |
| ATR14 über 1,5 × Signal-ATR | 54,8121 | 37,3306 |

Preisstruktur und Momentum trennen die späteren Pfade deskriptiv deutlich. Das ist wegen der nach Signalzeit liegenden Messung keine Freigabe, daraus rückwirkend eine Entry- oder Exitregel zu bauen. Event-Deterioration ist in sämtlichen Fällen `UNKNOWN`.

Die Protective-Ratchet-Messung ist in allen 1.749.125 vollständigen Fällen vorhanden; 1.713.989 Fälle besitzen mindestens ein Update, im Mittel 31,63. Es gibt 0 Verletzungen von `never_lowered`. Die prozentuale Änderung der Lower-Grenze ist bei kleinen Preisniveaus extrem schief und nicht als Effektgröße geeignet. Belegt ist die technische Schutzinvariante, nicht eine Handelswirkung.

**Review-Klasse:** Deterioration als Diagnose `INTERESTING_BUT_INSUFFICIENT`; als PIT-Signal `NOT_INTERPRETABLE`. Protective-Ratchet-Wirkung `NOT_INTERPRETABLE`.

## 8. Zeitverlauf

| Horizont | Mittel Return % | Mittel MFE % | Mittel MAE % | positive Close-Fraktion |
|---|---:|---:|---:|---:|
| 20 | 1,8136 | 9,5484 | -7,4305 | 57,4586 % |
| 60 | 5,9597 | 19,6823 | -12,3870 | 60,8252 % |
| 120 | 12,6112 | 32,6421 | -16,9984 | 62,8024 % |
| 252 | 30,1055 | 63,9220 | -23,3984 | 65,8298 % |

Mit längerer Beobachtung wachsen MFE und MAE erwartungsgemäß. Die mittlere Zeit bis MFE beträgt 156,72 Beobachtungen. Fälle mit positiver 252er-Endrendite erreichen ihr späteres Maximum im Mittel nach 197,67, Fälle mit nicht positiver Endrendite nach 77,83 Beobachtungen. Diese Gruppen sind mit dem zukünftigen Endzustand definiert und können keine neue Zeitexit-Regel begründen.

Die zunehmenden Mittelwerte sind stark durch lange Aufwärtsausreißer beeinflusst; beim 252er-Return beträgt die Standardabweichung 629,25 %. Ohne Exit-/Kosten-/Portfoliovertrag sind dies keine Strategieerträge.

**Review-Klasse:** `INTERESTING_BUT_INSUFFICIENT`; Zeitexit-Aussage `NOT_INTERPRETABLE`.

## 9. Positive Befunde

1. **Messkonsistenz der Safe-Zone-Geometrie – `INTERESTING_BUT_INSUFFICIENT`:** C wird in jeder geprüften Asset-/Jahr-/Regimegruppe seltener gebrochen als B, B seltener als A. Das bestätigt die erwartete Tiefenordnung, aber keine Stop-Überlegenheit.
2. **Volatilitätsfamilie – `INTERESTING_BUT_INSUFFICIENT`:** `atr_pct` korreliert über die Gesamtmenge mit 252er-Return/MFE jeweils rund `r = 0,36`; die Richtung ist in allen Jahren, Assetklassen und Marktregimen positiv. Die 20er-über-60er-Volatilität zeigt +5,7855 Return- und +8,1003 MFE-Prozentpunkte. Gleichzeitig vertieft sich MAE, Crypto zeigt kaum Return-Zusammenhang und die Ergebnisse sind stark schief: eher Bewegungsamplitude als Richtungsqualität.
3. **RSI-Mean-Reversion – `INTERESTING_BUT_INSUFFICIENT`:** RSI14 < 40 zeigt höhere spätere MFE und mittlere Returnwerte in drei Assetklassen und 2016–2020, aber deutlich schlechtere Safe-Zone-Survival und MAE sowie Regimeinstabilität.
4. **Bestätigte Sell-Zone-A-Distanz – `INTERESTING_BUT_INSUFFICIENT`:** positive Return-/MFE-Richtung in Equities, ETF, allen Jahren und Regimen; Gegenbefunde sind Crypto, tiefere MAE, Missingness und Ausreißerdominanz.
5. **Outcome-Diagnostik – `INTERESTING_BUT_INSUFFICIENT`:** künftige Preisstruktur-/Momentum-Deterioration trennt spätere positive und nicht positive Endpfade sichtbar. Der Zähler ist aber post-signal und kein zulässiger Eingangsfilter.

## 10. Negative Befunde

1. **Volume Ratio – `NO_USEFUL_SIGNAL`:** kontinuierlich praktisch keine Beziehung (`r = -0,00055` zum 252er-Return). `volume_ratio_20 < 0,5` erzeugt höhere Mittelwerte, aber eine niedrigere positive Close-Fraktion, tiefere MAE und innerhalb von mehr Symbolen eine negative als positive Return-Differenz (1.160 gegenüber 884). Das Aggregat wird nicht breit getragen.
2. **Overnight / Gap / Intraday – `NO_USEFUL_SIGNAL`:** kontinuierliche Beziehungen sind klein (`overnight_return r = 0,0074`, `intraday_return r = -0,0126`). Positive Overnight-Gaps zeigen -5,7641 Return- und -11,3625 MFE-Prozentpunkte, wechseln aber nach Assetklasse/Jahr. `gap_atr` und `overnight_return` besitzen identische Vorzeichen-Gruppen und dürfen nicht doppelt gezählt werden.
3. **Positive Momentum-/EMA-Zustände – `INTERESTING_BUT_INSUFFICIENT`:** Upside-Mittelwerte und MAE/Safe-Zone-Qualität bewegen sich in entgegengesetzte Richtungen. Längere EMA-Zustände wechseln zudem bei Crypto gegenüber Equity/ETF die Richtung und sind von Complete-Case-Selektion betroffen.
4. **Safe-Zone-Distanz – `INTERESTING_BUT_INSUFFICIENT`:** starke aggregierte Beziehungen sind vor allem Equity-/2019-/Downtrend-getrieben; bei ETF, Crypto und anderen Regimen kippt die Richtung. R-Normalisierung ist zusätzlich mechanisch vom C-Abstand abhängig.
5. **Confirmed-Swing-Low-Zähler – `NO_USEFUL_SIGNAL`:** geringe Return-/MFE-Beziehung und große Complete-/Censored-Abweichung; überwiegend Coverage-/Historienlängeninformation statt belastbarer Strukturqualität.

## 11. Nicht interpretierbare Bereiche

- FX: keine vollständigen Outcomes.
- Relative Strength, Benchmark- und Sektorvergleich: keine Felder.
- Higher High/Higher Low, Konsolidierung, Breakout/Pullback: keine expliziten PIT-Felder.
- Volatilitätsregime: kein eigenes Feld.
- Roh-ATR und Roh-Dollarvolumen: über Währungen, Preisniveaus und Assetklassen nicht direkt vergleichbar; es fehlen ein eingefrorener Normalisierungs-/Größenvertrag und verlässliche Sektor-/Marktkapitalisierungsfelder.
- Sell-Zone-spezifische Rejection/Reversal: keine eindeutig zeitlich geordnete Messung nach dem jeweiligen Hit.
- Event-Nähe: bei 2.356.553/2.356.553 Fällen `UNKNOWN` mit `NO_PIT_EVENT_FACT_AVAILABLE_FOR_PILOT_SNAPSHOT`.
- Fundamentals: bei 2.356.553/2.356.553 Fällen `UNAVAILABLE` mit `NOT_COLLECTED_FOR_TECHNICAL_PILOT`.
- Makro und Politik/Geopolitik: keine entsprechenden PIT-Felder.
- Dependency-adjustierte Inferenz: effektives N 0 nach eingefrorenem Vertrag.

Für Fundamentals, Events, Makro und Politik gilt zusammenfassend ausdrücklich:

`IN_DIESEM DEVELOPMENT-LAUF NICHT AUSREICHEND GETESTET`

## 12. Höchstens 1–3 mögliche neue Hypothesen

**Anzahl `ROBUST_CANDIDATE_FOR_NEW_HYPOTHESIS`: 0.**

Kein Befund erfüllt gleichzeitig mehrere Jahre, mehrere Assets, mehrere Assetklassen, verschiedene Regime, geringe Missingness-/Censoring-Sensitivität, gleiche Richtung in mehreren Outcome-Dimensionen und eine belastbare Dependency-Basis.

Insbesondere werden RSI14 < 40, Volatilitätsexpansion und Sell-Zone-A-Distanz **nicht** als neue Hypothesen vorgeschlagen. Sie bleiben lediglich priorisierte `INTERESTING_BUT_INSUFFICIENT`-Beobachtungen. Ein späterer Planungsentscheid dürfte sie nur nach einem neuen, vor Ergebniskenntnis eingefrorenen Vertrag aufgreifen; dieser Review formuliert oder startet diesen Test nicht.

## 13. Ausdrücklich nicht getestete Themen

- keine Featurekombination und keine Confluence
- kein Cutoff und keine neue Schwelle
- keine Parameteroptimierung oder Grid Search
- kein Entry, Exit, Stop, Ziel, Kostenmodell oder Portfolio
- keine Strategie-Expectancy, Profit Factor, Sharpe, Nettorendite oder Drawdown
- keine Validation, kein Holdout und keine External-Evidenz
- kein neuer Wasser-, Gold-/Silber- oder Overnight-Test
- kein Forward, Paper, Shadow, Broker oder Orderpfad
- keine Wirkung von Fundamentals, Events, Makro oder Politik

## 14. Empfohlene nächste Planungsentscheidung

Der Planungs-Chat sollte **keine neue v7-r2-abgeleitete Hypothese freigeben**. Vor einer späteren Neubewertung wären mindestens verifizierte historische Issuer-/Listing-Dependencies und eine Coverage-Lösung für die nahezu vollständig zensierte 2021-Kohorte nötig; neue PIT-Datenfamilien müssten separat und vorab vertraglich eingefroren werden.

Die bereits dokumentierte Reihenfolge Wasser → Gold/Silber → conditional Overnight bleibt unverändert. Dieser Review startet keinen dieser Schritte und verdrängt sie nicht. Er schließt ausschließlich den fachlichen v7-r2-Development-Review ab und wartet auf eine neue Planungsentscheidung.

Finaler Status: `V7_R2_DEVELOPMENT_REVIEW_COMPLETE_AWAITING_HYPOTHESIS_DECISION`
