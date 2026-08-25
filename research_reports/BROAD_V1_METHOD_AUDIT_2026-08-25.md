# Broad-v1 Methodik-Audit und Errata

Stand: 2026-08-25, ausschließlich Development. Validation und Holdout wurden nicht geöffnet.

## Unveränderliche Referenz

Der Audit hat Broad-v1 ausschließlich mit SQLite `mode=ro` gelesen. Größe und Änderungszeit von Broad-DB und Research-Quality-Ledger waren vor und nach dem vollständigen Lauf identisch.

- Assets: 2.520/2.520
- Kandidaten / Labels / Counterfactuals: jeweils 1.263.423
- Development: 631.811
- Validation: 304.389, nicht gelesen
- Holdout: 327.223, nicht gelesen
- Frozen Dataset: `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`
- Feature Contract: `c09d43e3c297b1685796db568b63c23c5878b2f246e69508c409fdbaa77f01dd`
- Broad-v1 Code: `77ab6ed29d8d08e32fabb8c2aee01c0a94953ded4b69092227f074273b12d946`
- Broad-v1 Manifest: `7531b0b8411436b3bbaf31d1db4bab94e35ecb0360f094cdbb96baf0d6297bf5`
- Finaler Auditvertrag: `swing-broad-v1-method-audit-2026.08.25-v3`
- Finaler manueller Review-Fingerprint: `1b1dc38b133ebefb6f4397200fdbc5158322ed3588946d0dea3751b023d61f96`

Die vorläufigen lokalen Auditexporte v1/v2 wurden nicht überschrieben. v3 ersetzt sie methodisch; Broad-v1 wurde zu keinem Zeitpunkt verändert.

## Auditbefunde

| Befund | Einordnung | Belegte Ursache | Korrektur für künftige Berichte |
| --- | --- | --- | --- |
| Kandidaten-, Label-, Counterfactual-, Split- und Manifestzahlen | korrekt | Finaler Manifest- und Abschlussledger-Abgleich stimmen; 0 ungültige Ledger-Fingerprints | unverändert beibehalten |
| COT als B | Klassifikationsfehler | 0 evaluierbare Fälle; die alte Defaultklasse blieb B, weil nur ausreichend große negative Treatments auf A gesetzt wurden | `NOT_TESTABLE`, niemals A/B/C |
| Opening Levels als A | Hypothesendesign- und Klassifikationsfehler | 631.809 Treatment gegen 2 Controls; die OR-Regel enthält den aktuellen Daily Open, der konstruktionsbedingt fast immer innerhalb der Tageskerze liegt | `NON_DISCRIMINATING`; keine Performanceklasse und keine nachträgliche Schwellsuche |
| Buyer Confirmation auf Breakouts | Feature-Applicability-Fehler | Pullback-Bestätigung wurde technisch für beide Setups ausgewertet | nur `objective_pullback`; Breakouts sind `structurally_not_applicable` |
| bearish candles auf Breakouts | Feature-Applicability-Fehler | Pullback-Dauer/-Kerzen wurden technisch auch auf Breakout-Kandidaten angewendet | nur `objective_pullback` |
| Fibonacci auf Breakouts | Feature-Applicability- und Reportingfehler | Pullback-Tiefe wurde über beide Setups aggregiert; gleich breite Kontrollen und kontinuierliche Tiefe waren im Ergebnis nicht gemeinsam entscheidungsfähig berichtet | nur Pullbacks; beide gleich breiten Zonen und kontinuierliche Tiefe verpflichtend |
| BOS auf Pullbacks | Feature-Applicability-Fehler | `close_break` wurde über beide Setups aggregiert | `bos_close_break` nur im Breakout-Scope bewerten |
| `Max Drawdown` | Reportingfehler | kumulierte R-Folge stark überlappender Broad-Kandidaten | ausschließlich `candidate_sequence_drawdown`; keine Portfolioaussage |
| Eine Ledger-Familie für acht Konzepte | Hypothesendesignproblem | alle acht Einträge wurden als `broad-development-single-feature` mit Versuch 1–8 gespeichert | sieben explizite Familien; EMA/RSI gemeinsam in Trend/Momentum, sonst getrennte Konzepte |
| COT-Abdeckung und historische Universumswahrheit | strukturelle Datenlücke | COT Coverage 0; historische Constituents, vollständige Delistings/Pleiten und PIT-Handelbarkeit fehlen | Missingness sichtbar halten; keine False/0- oder FX-/Equity-Übertragung |
| ursprünglicher Fibonacci-Quellmarkt | nicht entscheidbar | Broad-v1 speichert den fachlichen Quellmarkt der ursprünglichen Idee nicht | `source_scope=LEGACY_SOURCE_SCOPE_NOT_RECORDED`; Test-Scope getrennt speichern |

Der tatsächliche Broad-v1-Test-Scope ist `EQUITIES`, `ETF`, `CRYPTO`. Es wurden keine FX-, Futures- oder Commodity-Resultate erzeugt. `validated_scope` bleibt leer, weil nur Development gelesen wurde.

## Rangliste und Development-Entscheidung

| Rang | Hypothese | Validity | Treatment / Control | Expectancy R | PF | effective N | Stabilität / Robustheit | Review |
| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |
| 1 | Buyer Confirmation `Close[t] > High[t-1]` | PASS, Pullback-only | 64.459 / 317.181 | +0,0840 / -0,1281 | 1,168 / 0,833 | 49.438 / 104.407 | 7/9 Jahre positiv; regimegematchtes Δ +0,1649 R; dependency-adjustiertes Δ +0,0315 R; höhere Kosten, adverse Entry und Gap-Stress negativ | **B** |
| 2 | mindestens 3 bearishe Pullback-Kerzen | PASS, Pullback-only | 250.806 / 130.834 | +0,0224 / -0,3167 | 1,037 / 0,667 | 95.437 / 69.444 | 5/9 Jahre positiv; Stress bereits ab +0,05 R negativ; beobachtete Richtung ist das Gegenteil der ursprünglichen Hypothese | **B, post hoc** |
| 3 | Fibonacci 61,8–78,6 % | PASS, Pullback-only | 23.575 / 358.065 | +0,0446 / -0,1005 | 1,072 / 0,862 | 18.124 / 105.677 | gleich breite Zonen: unten +0,0264 R, oben -0,0705 R; Δ gegen deren Mittel +0,0667 R; depth-adjustiertes Residual-Δ +0,0232 R; 5/9 Jahre positiv; erhöhte Slippage negativ | **B** |
| 4 | EMA20 > EMA50 | PASS | 521.290 / 110.521 | -0,0793 / +0,0827 | 0,882 / 1,188 | 181.978 / 71.074 | alle drei festen EMA-Nachbarschaften negativ | **A** |
| 5 | RSI 40–70 | PASS | 524.364 / 107.447 | -0,0175 / -0,2246 | 0,970 / 0,739 | 208.848 / 71.590 | alle drei festen RSI-Nachbarschaften negativ | **A** |
| 6 | BOS Close Break | PASS, Breakout-only | 145.864 / 104.307 | -0,0186 / +0,0486 | 0,963 / 1,100 | 90.039 / 71.297 | alle drei festen BOS-ATR-Nachbarschaften negativ | **A** |
| 7 | Opening-Level-Kontakt | NON_DISCRIMINATING | 631.809 / 2 | nicht interpretierbar | nicht interpretierbar | 221.243 / 2 | praktisch keine Kontrollgruppe | **INVALID** |
| 8 | COT verfügbar | NOT_TESTABLE | 0 / 0 evaluierbar | nicht verfügbar | nicht verfügbar | 0 / 0 | Coverage 0, Status überall `unavailable_point_in_time` | **NOT_TESTABLE** |

## Priorität 1: Buyer Confirmation

Buyer Confirmation bleibt der stärkste isolierte Development-Hinweis. Der Effekt ist in allen drei Volatilitätsregimen und allen fünf gespeicherten Marktphasen positiv. Zwei von neun Jahren sowie Europa und Südamerika sind negativ; kleine regionale Gruppen werden nicht künstlich gleichgewichtet.

Die regimegematchte, outcome-blinde Kontrolle bestätigt einen Vorteil von +0,1649 R bei 64.447 Fällen je Gruppe. Nach deskriptiver Abhängigkeitskontrolle für Zeit, Marktphase, Volatilität, Momentum, Candle-Close-Location, BOS, EMA-Trend, Pullback-Tiefe und bearishe Kerzen bleiben +0,0315 R bei 53.967 gematchten Fällen je Gruppe. Das ist ein kleiner positiver Resthinweis, kein Kausalbeweis.

`pullback.buyer_confirmation_close_above_prior_high` und `candle_quality.close_above_prior_high` sind in allen geprüften Fällen dasselbe Boolean. Sie dürfen nicht als zwei unabhängige Bestätigungen gezählt werden.

Entry-Effizienz der Treatment-Kandidaten: Ø MFE 1,730 R, Ø MAE -1,455 R, Ø Giveback 1,646 R, Median bis maximalem MFE 15 Sitzungen und Median bis Exit 25 Sitzungen. Zeit bis zur ersten positiven Bewegung ist nicht gespeichert und wurde nicht erfunden. Daily-Daten liefern keine Intrabar-Reihenfolge.

Execution Stress: Basis +0,0840 R, zusätzliche Slippage +0,0340 R, adverse Entry -0,0160 R, höhere Gesamtkosten -0,0660 R und konservativer Gap-Stop -0,0065 R. Damit ist die Hypothese vollständig geprüft, aber nicht robust genug für C.

## Priorität 2: bearishe Kerzen

Die ursprüngliche Richtung lautete sinngemäß „drei bearishe Kerzen = eher kein Trade“. Development zeigt das Gegenteil. Deshalb gilt verbindlich `post_hoc_direction_reversal=true`.

Der rohe Vorteil gegenüber der Control ist groß, der absolute Treatment-Edge aber klein: +0,0224 R und PF 1,037. Nur fünf von neun Jahren sind positiv, ETF sowie mehrere Regionen sind negativ, und jeder vorab definierte Stress jenseits der Basis macht den Erwartungswert negativ. Eine spätere Fortsetzung wäre eine neue, vorab eingefrorene development-derived Hypothese; sie ist keine Bestätigung der ursprünglichen Regel. Es wurde keine Schwelle 2/3/4/5 gesucht und keine Kombination mit Buyer Confirmation gebaut.

## Priorität 3: Fibonacci

Die gespeicherten Zonen sind methodisch korrekt gleich breit: 0,450–0,618, 0,618–0,786 und 0,786–0,954. Extensions wurden in 0 Fällen getestet. Alle Vergleiche nutzen dieselbe Pullback-Grundgesamtheit, denselben Entry-, Kosten-, Label- und Ergebnisvertrag.

Der Fib-Bereich schlägt den Mittelwert der gleich breiten Nachbarzonen um +0,0667 R. Nach einem einzigen vorab festgelegten linearen Vergleich mit kontinuierlicher Pullback-Tiefe bleiben +0,0232 R Residualvorteil; die Tiefe selbst erklärt mit R² 0,000026 praktisch nichts linear. Der spezielle Effekt ist trotzdem zu klein und instabil für C: PF 1,072, nur fünf von neun Jahren positiv, negative Regionen sowie negative Krypto-Teilgruppe und bereits unter zusätzlicher Slippage negativer Erwartungswert. Keine neue Fib-Zone, kein Level und keine Extension wurde gesucht.

## Multiple Testing, False Positives und Metriksemantik

- Acht vorab deklarierte Hypothesen und sieben künftige fachliche Familien werden gezählt. Umbenennung oder identische Alias-Features erzeugen keine zusätzliche unabhängige Evidenz.
- Raw N bezeichnet Kandidaten, effective N die eindeutigen gespeicherten `dependency_cluster`. Wegen stark überlappender Kandidaten werden keine naiven unabhängigen p-Werte oder Portfolioaussagen behauptet.
- Placebos, Zeit, Regime, Asset/Region, natürliche Segmentkonzentration, Abhängigkeiten, Entry-Effizienz, Execution Stress und Survivorship-Limits sind im v3-JSON getrennt enthalten.
- RSI, EMA und BOS werden nicht durch Threshold-Suche gerettet: alle neun festen Nachbarschaften sind negativ.
- Es wurde keine Confluence aus Buyer Confirmation, bearish candles, Fibonacci, RSI, Volumen oder Volatilität gebaut.

## Nächste Entscheidung

Keine Hypothese erreicht C. Deshalb wird in diesem Audit weder eine Challenger-Spezifikation entworfen noch ein Freeze, Validation-, Holdout-, External-, Forward- oder Produktionslauf gestartet.

Buyer Confirmation bleibt Priorität 1 für eine spätere, ausdrücklich neu beauftragte Hypothese. Vor einem Freeze wäre eine fachlich vorab definierte einfachere Ausführungs-/Kostenrobustheit nötig; die aktuellen Development-Befunde allein reichen nicht.
