# R4-I – Survivorship- und Historical-Universe-Audit

Stand: 2026-09-22. Outcome-freier, schreibgeschützter Audit. Kein historischer Balken, Universe-Eintrag oder v7-r2-Artefakt wurde geändert.

## Auswahlzeitpunkt und historische Aussagegrenze

Das Quellmanifest [`config/swing_universe_sources.json`](config/swing_universe_sources.json) wurde am 2026-08-11 erzeugt. Es kombiniert ein kuratiertes Prognoseuniversum (1.726 Zeilen) mit damals abgerufenen Listen für S&P 500 (503), S&P MidCap 400 (400), S&P SmallCap 600 (603) und Nasdaq Global Select (1.293). Diese Listen belegen die Auswahl im Jahr 2026; sie sind **keine** historischen Constituents für 2016–2021. Auch der lokale Frozen Store enthält keine Tabelle für damalige Indexzugehörigkeit, Delisting, Insolvenz, Ticker-/Issuer-Vorgänger oder Corporate Actions.

Die eingefrorene Equity-/ETF-Projektion `equity-etf-historical-pit-2026.09.03-v1` mit Dataset-Fingerprint `321531c482d844df4d5513b58646b3f41553f47a7b2276517cb8473886c298d6` wurde am 2026-09-03 aus historischen OHLC-Reihen für dieses rückblickend kuratierte Universum gebaut. Eine alte Kursreihe für einen heute bekannten Titel macht dessen damalige Mitgliedschaft nicht PIT. Die Projektion ist daher ein **current-curated historical price panel**, kein zeitgenössisch rekonstruierter Marktquerschnitt.

## Reproduzierbare Coverage

Der read-only Store umfasst in `asset_coverage` 2.429 Equity- und 59 ETF-Einheiten. 2.238 Equities und alle 59 ETFs besitzen mindestens einen aktiven gültigen Balken; 191 Equity-Einheiten besitzen keinen aktiven Balken. Die aktiven 2.297 Asset-/Listing-Einheiten ergeben 3.025.873 gültige Balken. 479 aktive Equity- und 2 ETF-Reihen beginnen nach dem ersten gemeinsamen Handelstag 2016; ein später Start kann IPO/Listing, Provider-Coverage oder eine andere Ursache bedeuten und wird ohne historische Metadaten nicht klassifiziert.

Am Periodenende schließen 2.224 Reihen am 2021-12-31, 72 am 2021-12-30 und eine am 2021-12-28. Das sind austausch-/kalenderbedingte letzte Beobachtungen oder Quellenenden; daraus wird **kein** Delistingstatus abgeleitet. Insbesondere liefert der Umstand, dass keine Reihe deutlich vor Periodenende endet, keinen Beweis für Delisting-Abdeckung – im Gegenteil ist er mit einem überwiegend später ausgewählten Survivor-Panel vereinbar. Die 191 Reihen ohne aktive Daten werden ebenfalls nicht pauschal als Delistings bezeichnet.

Der [R4-A-Audit](R4_A_IDENTITY_DEPENDENCY_AUDIT_2026-09-22.md) verschärft die Grenze: Es gibt 0 für 2016–2021 historisch verifizierte Issuer-Cluster. Tickerwechsel, Fusionen, Spin-offs, Share Classes und ADR/ADS-Abhängigkeiten lassen sich daher nicht vollständig historisch rekonstruieren. Für Crypto gilt dasselbe Auswahlproblem: Die 30 im Scope geführten Coins stammen aus einem später definierten Universum; 29 besitzen aktive 2016–2021-Balken, aber verstorbene/entfernte Coins außerhalb des heutigen Scopes sind nicht inventarisiert.

## Nicht verfügbare Gegenprobe

Lokal liegt keine belastbare kostenlose, versionierte Historical-Constituent-/Delistingquelle mit Quellzeit, Gültigkeitsintervallen und verlässlichem OHLCV ausgeschiedener Titel vor. Eine Community-Liste, heutige Symbolsuche oder Wikipedia-Änderungshistorie wird nicht als PIT-Wahrheit importiert. Daher lassen sich Zahl, Eigenschaften und Ergebnisbeitrag fehlender Delistings, Insolvenzen oder ehemaliger Constituents **nicht quantifizieren**. Es ist unzulässig, die bestehenden Ergebnisse deshalb nach oben oder unten zu korrigieren.

## Capability-Entscheidung

- Preis-/Technikmerkmale: höchstens `ACTIVE_PIT_LIMITED_SCOPE` auf dem explizit eingefrorenen current-curated Panel.
- Historische Universe-Mitgliedschaft, Delisting-/Pleiteabdeckung und Issuer-Vorgänger: `UNAVAILABLE`/`UNKNOWN`.
- Discovery-v2-Berichte müssen Roh-N und den Frozen-Scope nennen, Survivorship als nicht quantifizierbare Einschränkung ausweisen und dürfen keine Repräsentativität für den damaligen Gesamtmarkt behaupten.
- Ein Robustheits-/Challenger-Gate darf diese Lücke weder mit heutiger Indexmitgliedschaft noch mit hoher Zeilenzahl ausgleichen. Unknown bleibt Unknown.

R4-A bis R4-I sind damit outcome-frei abgeschlossen beziehungsweise ehrlich begrenzt. Vor jeder v2-Outcome-Betrachtung folgt der separate R5-Capability-/Contract-Freeze; Validation, Holdout und weitere Stufen bleiben geschlossen.
