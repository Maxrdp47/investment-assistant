# R4-A – historische Identität und Abhängigkeiten

Stand: 2026-09-22. Programm `finite-research-program-2026-09-15-v1`. Dieser Audit ist outcome-unabhängige Daten-/Methodikarbeit vor Discovery v2; er ändert weder die Registry noch einen historischen Fall oder eine Strategie.

## Ergebnis

`AUDIT_COMPLETE_HISTORICAL_DEPENDENCY_GAP_UNRESOLVED`. Die aktuelle Registry ordnet viele heutige Listings zu, doch **keine** ihrer vorliegenden Gültigkeiten reicht in die historische Development-Periode 2016–2021 zurück. Die aktuellen CIK-/FIGI-/Issuer-Verknüpfungen dürfen daher nicht als damals nachgewiesene Beziehungen ausgegeben werden. Historisch verifizierte Issuer-Cluster bleiben in diesem Datenstand **0**, Dependency-Status für historische Inferenz bleibt `UNKNOWN`, und das nach bestehendem konservativem Vertrag anrechenbare Effective N bleibt **0**. Das ist kein Befund über die Güte einer Tradingregel.

## Quellen und Abdeckung

| Ebene | Belegter Stand | Interpretation |
|---|---:|---|
| gültige Equity-/ETF-Tagesbalken der eingefrorenen Projektion | 3.025.873 | Rohzeilen, keine unabhängige Stichprobe |
| Asset-/Listing-Einheiten mit mindestens einem gültigen Balken | 2.297 | beobachtete Identifier; keine historisch verifizierten Issuer-Cluster |
| Asset-/Listing-Jahr-Gruppen | 12.274 | Zeitdiagnostik, nicht Effective N |
| exakte Treffer dieser Einheiten in der neuesten Registry | 2.297 | heutige Identifier-Abdeckung |
| davon Registry-Status heute `VERIFIED` / `CANDIDATE_UNVERIFIED` / `UNRESOLVED` | 2.078 / 203 / 16 | nicht rückwirkend gültig |
| Registry-Mappings mit 2016–2021 überlappendem `valid_from`/`valid_to` | 0 | historischer Verknüpfungsnachweis fehlt |
| historisch verifizierte Issuer-Cluster / anrechenbares Effective N | 0 / 0 | bestehende Policy bleibt fail-closed |

Quellprojektion: `runtime/equity_etf_historical_pit_2026-09-03-v1.sqlite3`, Dataset-Fingerprint `321531c482d844df4d5513b58646b3f41553f47a7b2276517cb8473886c298d6`. Neueste Registry-Version `research-identity-registry-2026.08.30-multisource-v2`, Fingerprint `d8bd34a3bac724f6ff15f4d33a03efe7b517518b2a71208046be11bc1530387e`; alle 2.297 passenden Mappings haben `valid_from=2026-08-30`. Die [bestehende historische Dependency-Policy](runtime/research_exports/historical_dependency_policy_2026-09-01-v1.json) verbietet das Zurückdatieren einer heute bekannten Zuordnung. Der SEC-abgeleitete lokale CIK-/Ticker-Snapshot besitzt keinen jeweils zeitgenössischen Listing-Gültigkeitsnachweis für 2016–2021. Es wurden keine unsicheren Beziehungen ergänzt.

Reproduzierbar sind die Zähler durch `SELECT asset_id, listing_id, substr(session_date,1,4)` aus `active_bars` der read-only Projektion sowie exakten Schlüsselabgleich gegen `identity_mappings` der genannten Registry-Version. Die Registry-Mappings wurden nach ihrem gespeicherten Status und ihrer `valid_from`-/`valid_to`-Überschneidung mit 2016–2021 gezählt. Weder Ticker-Ähnlichkeit noch heutiger Firmenname wurden als historische Verbindung akzeptiert.

## Methodischer Effective-N-Vertrag

- **Raw N** zählt Beobachtungen oder Fälle; überlappende 20/60/120/252-Sitzungs-Outcomes, gleiche Issuer und gemeinsame Marktjahre sind damit nicht unabhängig.
- **Listing-Temporal-Cluster** benötigen belegte historische Gültigkeitsintervalle. Eine Asset-/Listing-ID allein ist nur eine Zähleinheit; ein Tickerwechsel, Spin-off, ADR/ADS oder mehrere Aktienklassen können sonst falsch getrennt oder zusammengelegt werden.
- **Verified Issuer-Cluster** zählen nur bei damals belegter Issuer-/Listing-Beziehung und eindeutigem nicht überlappendem Zeitfenster. Unbekannte Beziehungen tragen weiterhin 0 zum anrechenbaren Effective N bei; eine heutige CIK, ISIN, FIGI oder LEI ohne historischen Zuordnungszeitpunkt genügt nicht.
- **Equities** brauchen mindestens Issuer- und Zeitblock-Abhängigkeit; **ETFs** zusätzlich die geteilte Index-/Underlying-Exposition und gegebenenfalls Fondsgesellschaft, soweit historisch belegt. **FX-Paare** teilen Währungen und Makro-Schocks; **Crypto-Assets** teilen Markt-/BTC-/Chain-/Exchange-Regime. Ein Equity-Issuer-Zähler ist für diese Klassen nicht austauschbar.
- Multi-Way-/Block-Resampling kann künftig verifizierte Issuer × Zeitblöcke und bekannte sektorale/marktweite Schocks respektieren. Es schätzt keine unabhängige Evidenz herbei, solange die historische Zuordnung unbekannt ist. Kalenderjahre und beobachtete Listing-Einheiten sind Diagnostik, kein Ersatz für ein verifiziertes Effective N.

## Konsequenz für R4/R5

Deskriptives Development muss wegen dieser Lücke nicht automatisch ausfallen, aber ein robustes C-/Challenger-Gate darf nicht durch die Rohfallzahl, den heutigen 87,55-%-Registry-Coverage-Gate oder ein pauschales Asset-Bootstrap ersetzt werden. Für eine spätere historische Verbesserung wären zeitgenössische regulatorische Filings, offizielle Listing-Beziehungshistorie oder eine versionierte Corporate-Action-Kette mit `valid_from`/`valid_to`, Quelle und damaligem Bekanntheitszeitpunkt nötig. Bis dahin lautet die Capability für historische Issuer-Dependencies `SHADOW`/`UNKNOWN`, nicht `ACTIVE_PIT`.

R4-B bis R4-I werden unabhängig von dieser dokumentierten Grenze geprüft. Es wurden weder v2-Outcomes, Validation, Holdout, External, Forward, Paper, Shadow-Live, Broker noch Orders geöffnet.
