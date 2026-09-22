# R4-B – kausale Relative-Strength- und Strukturmerkmale

Stand: 2026-09-22. Programm `finite-research-program-2026-09-15-v1`. Dieser Capability-Pilot betrachtet **keine v2-Outcomes** und testet keine Tradingregel.

## Erreichter Stand

Ein eigener, outcome-freier [Featurevertrag](config/multi_asset_v2_r4b.json) und eine [kausale Berechnung](multi_asset_v2_r4b_features.py) sind implementiert. Contract-Fingerprint `aef8ec16c674f7284884caca3fb040480eba77fbacfc05a23fece5c75ad47901`. Der Baustein kann aus eingefrorenen, gültigen Equity-/ETF-OHLC zu jeder abgeschlossenen Kerze die 20/60/120-Sitzungs-Assetrenditen, ein bewusst **zeitverzögertes** Marktvergleichssignal, bestätigte HH/HL/LH/LL-Struktur, Trend-Effizienz, Konsolidierungsbreite, Breakout-/Pullback-Kontext und Abstände zum vorherigen 20-Sitzungs-Hoch/-Tief liefern. Kein neues Feature wird als Pflichtfilter oder Score aktiviert.

Da die historische Region-/Sektorzuordnung nicht belegt ist, ist ausschließlich ACWI als globaler Fallback erlaubt. Ein ACWI-Schlusskurs **vom selben Datum** ist für einen früher schließenden Markt potenziell Zukunftsinformation und wird ausdrücklich ausgeschlossen. Verwendet wird nur der letzte ACWI-Schluss eines **streng früheren** Kalendertags, höchstens fünf Kalendertage alt; sonst bleibt das Merkmal fehlend. Das ist ein konservativer, teils um eine Sitzung verzögerter Marktvergleich, **kein** perfekter regionaler Relative-Strength-Wert. Sektorbenchmark und historische Region bleiben `UNAVAILABLE` beziehungsweise `UNVERIFIED`.

Die Pivot-Sequenz verwendet zwei abgeschlossene Balken links und zwei rechts des Pivot-Kandidaten. Sie wird erst am Schluss des zweiten rechten Balkens sichtbar. Weniger als je zwei bestätigte Hochs/Tiefs ergeben `INSUFFICIENT_CONFIRMED_PIVOTS`, nicht eine erfundene Trendklasse. Konsolidierung ist ein kontinuierliches 20/60-Breitenverhältnis, keine nach Performance gewählte Schwelle. Unterstützung/Widerstand basieren auf vorangegangenen 20 Balken; Breakout wird nur beschreibend markiert.

## Quelle und Coverage-Pilot

Read-only Quelle ist die eingefrorene Equity-/ETF-Projektion mit Fingerprint `321531c482d844df4d5513b58646b3f41553f47a7b2276517cb8473886c298d6`: 3.025.873 gültige Quellbalken. Der ACWI-Benchmark enthält 1.508 historische Tagesbalken. Für 3.024.048 Asset-Balken (99,9397 %) ist ein streng früherer, höchstens fünf Tage alter ACWI-Schluss verfügbar. Nach zusätzlich 120 abgeschlossenen ACWI-Sitzungen bleiben höchstens 2.805.511 Asset-Balken (92,7174 %) übrig; individuelle Asset-Warmups reduzieren die tatsächliche 120er-Feature-Abdeckung weiter. Fehlende Benchmark-Tage werden nicht als gleichzeitige Information fingiert.

Der [read-only Pilot](scripts/audit_r4b_pit_features.py) wählte je die lexikografisch erste ausreichend lange Equity- und ETF-Asset-/Listing-Einheit, **nicht** nach Rendite. Beide besitzen 1.511 Quellbalken und jeweils 1.490 / 1.450 / 1.390 verfügbare relative 20/60/120-Werte; bestätigte Struktur ist für 1.490 (Equity) beziehungsweise 1.493 (ETF) Balken vorhanden. Das sind reine technische Coverage-Zahlen, kein Forward- oder Profit-Befund. Vier gezielte Tests einschließlich Präfix-Kausalität, Benchmark-Zeitversatz, fehlender/staler Quelle und ungültigem OHLC bestehen.

Der Quellsnapshot stammt aus `yfinance_auto_adjust_true`-OHLC, nicht aus einer nativen bitemporalen Vendor-Historie; Korrekturen der historischen Preisquelle können nicht rekonstruiert werden. Die Capability ist daher vorläufig `ACTIVE_PIT_LIMITED_SCOPE` **nur** für den kausalen globalen Fallback und die explizite Struktur auf der eingefrorenen Projektion. Der R5-Freeze muss diese Begrenzung, tatsächliche Missingness und die ungeklärte Issuer-Dependency aus [R4-A](R4_A_IDENTITY_DEPENDENCY_AUDIT_2026-09-22.md) übernehmen; er darf daraus keine volle globale/regional-sektorale PIT-Abdeckung machen.

Nach dem Pilot bestanden die vollständige Testsuite (1.165 Tests), `compileall .`, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Streamlit-Start und `git diff --check`.

Die erste Coverage-Probe mit gleichdatigem ACWI-Schluss wurde **vor Vertrags-Freeze und vor jeder Ergebnisbetrachtung** wegen des Zeitzonen-Leakage-Risikos verworfen. Nur die hier dokumentierte streng frühere Benchmark-Version ist gültig. Keine v7-/Frozen-Daten, Fälle oder Ergebnisse wurden geändert.
