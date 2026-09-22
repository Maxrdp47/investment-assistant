# R4-H – begrenzte Crypto-OHLCV-Capability

Stand: 2026-09-22. Programm `finite-research-program-2026-09-15-v1`. Dieser Block nutzt ausschließlich eingefrorene aktive Crypto-OHLCV und prüft **keine** v2-Outcomes, Handelsregeln oder ungesehenen Teststufen.

## Eingefrorene Quelle und Qualität

Der read-only v6-Input-Precheck für `crypto-historical-pit-2026.09.05-v1` meldet Dataset-Fingerprint `475b78ee3dd0a45371b6dc0448b9d915d0a879dadabe4c2d385573fd1fe6bf91`, 30 im Scope geführte Symbole, davon 29 mit aktiven Balken und 1 ohne Daten, zusammen 33.675 aktive Balken für 2016–2021. Im aktiven Bestand sind 3 archivierte Invalid-Source-Grenzen und 1 belegte Kalendertagslücke enthalten; der Precheck meldet 0 aktive OHLC-Verletzungen, 0 doppelte aktive Sitzungen, 0 Überschneidungen mit archivierten ungültigen Sitzungen und `quick_check=ok`. Diese Zahlen sind reine Datenqualität, keine Performance. Der Crypto-Provider-Snapshot ist eingefroren, aber keine native bitemporale Markthistorie; frühere Provider-Korrekturen lassen sich nicht rekonstruieren.

BTC-USD hat 2.192 tägliche Balken 2016–2021. Ein vorhandener BTC-Benchmark ist also für viele, aber nicht alle Symboltage möglich; neue Coin-Listings haben kürzere Warmups. Es gibt keine belegte historisch zeitgültige Gesamtmarkt-/Dominanz- oder On-Chain-Quelle. Das heutige Crypto-Universum darf nicht als vollständige historische Marktpopulation verstanden werden; R4-I prüft diese Grenze separat.

## Beobachtender Featurevertrag

Der eigenständige [R4-H-Vertrag](config/crypto_r4h_features.json) hat Fingerprint `5020eab57a4c2b60f81677bacff0b905a50f79fa30144b75e508f61e9e02dd51`. Die [Berechnung](crypto_r4h_features.py) liefert segment-sichere, beobachtende 20/60-Tage-Renditen des Assets und von BTC, relative 20/60-Tage-Renditen, 20-Tage-Logrenditen-Volatilität, ein einheitenloses Verhältnis des gemeldeten Volumens zum vorherigen 20-Tage-Median sowie kontinuierliche Strukturwerte (Schlusskurs zum vorherigen 20-Tage-Hoch, Trend-Effizienz). Bei beiden relativen Renditebeinen endet der Vergleich **am Vortag** des Signals. Die BTC-Zeile muss exakt vom vorherigen UTC-Kalendertag stammen; fehlende Tage bleiben fehlend. Weder gleiche-Tages-BTC-Schlusskurse noch Bars aus einem vorherigen Continuity-Segment werden überbrückt.

„BTC-Regime“ bleibt ein kontinuierlicher, verzögerter BTC-Rendite-/Volatilitätskontext ohne nach Performance gewählte Schwelle. Gemeldetes Volumen wird nur relativ zu seiner eigenen Historie gelesen; Provider-Einheiten sind nicht als Liquidität oder Quote-Notional verifiziert. Null-Volumen ergibt ein fehlendes Ratio. Dominanz und On-Chain erhalten explizit `UNAVAILABLE_NO_PIT_SOURCE`. Kein Filter, Score, Entry, Exit oder Strategie-Challenger wurde aktiviert.

## Outcome-freier Pilot

Der [read-only Pilot](scripts/audit_r4h_crypto_features.py) wählt BTC und ETH **fest und ohne Ergebnisauswahl**. BTC: 2.192 Balken, 2.171 verfügbare 20-Tage-Relative-Zeilen und 2.131 60-Tage-Zeilen. ETH: 1.514 Balken, 1.493/1.453 verfügbare 20/60-Tage-Relative-Zeilen. BTC als Selbstvergleich ergibt erwartungsgemäß keinen eigenständigen Relative-Strength-Mehrwert; die BTC-Reihe dient als Benchmark für andere Coins. Beide Pilotserien liegen jeweils in einem Continuity-Segment und haben 0 gemeldete Null-Volumen-Balken. Drei gezielte Tests prüfen Zukunftsfreiheit, exakte Vortagszuordnung, fehlende BTC-Tage, Segmentgrenzen, unveränderte Eingangsdaten und fail-closed Source-/Vertragsfehler.

R5 darf die mechanischen Crypto-OHLCV-Merkmale höchstens als `ACTIVE_PIT_LIMITED_SCOPE` auf **dem vorhandenen eingefrorenen Universum** führen. Es darf nicht behaupten, On-Chain, Dominanz, alle historisch existierenden Coins oder native bitemporale Kurse seien getestet. R4-I Survivorship/Universe ist der nächste Schritt; R5-Outcomes bleiben geschlossen.
