# R4-C – Fundamentals Point-in-Time: begrenzter Capability-Stand

Stand: 2026-09-22. Programm `finite-research-program-2026-09-15-v1`. Keine v2-Outcomes, Strategieergebnisse oder ungesehenen Daten wurden ausgewertet.

## Implementiert und geprüft

Der neue, rein offline arbeitende Adapter [`sec_pit_fundamentals.py`](sec_pit_fundamentals.py) liest SEC-Company-Facts-JSON **pro CIK** und bewahrt jährliche, getrennt eingereichte Werte und Amendments als einzelne Revisionen. Er verwendet nur die sechs bereits definierten SEC-Metriken Umsatz, Nettoergebnis, operativer Cashflow, Aktiva, Passiva und Zahlungsmittel. Ein historischer Signal-Tag erhält ausschließlich Fakten, deren SEC-`filed`-Datum **vor** diesem Tag liegt. Da Company Facts hier nur ein Einreichungsdatum und keinen belastbaren `accepted_at`-Zeitpunkt liefert, wird jede Einreichung vorsichtshalber frühestens am folgenden Kalendertag nutzbar. Die Prüfung berücksichtigt `period_end`, Form, Accession, Einheit und endliche Werte. Die Quell-Snapshot-Prüfsumme muss mitgegeben werden; der Adapter selbst lädt keine Daten und erzeugt keine historische Ticker-/Issuer-Zuordnung.

Synthetische Tests belegen: keine Verfügbarkeit am selben Einreichungstag, spätere Amendments überschreiben einen früheren As-of-Stand nicht, zukünftige Filings sickern nicht zurück, Quell-/Datumsfehler schließen die Funktion. Die Tests prüfen den Parser, **nicht** historische Fundamentaldaten-Coverage oder einen wirtschaftlichen Effekt.

## Historisches Daten-Gate

Im lokalen Research-Kontext liegt kein versionierter SEC-Company-Facts-Snapshot vor; `runtime/sec_json_cache` fehlt. Für Live-SEC-Abfragen ist zudem der vom vorhandenen Adapter geforderte Kontakt-User-Agent nicht konfiguriert. Beides wird nicht durch erfundene Credentials, heutige Profilwerte oder einen unversionierten Download umgangen. Selbst bei vorhandenen CIK-Fakten wäre die Anbindung an die eingefrorenen Equity-Listings historisch noch unbelegt: Der [R4-A-Identitätsaudit](R4_A_IDENTITY_DEPENDENCY_AUDIT_2026-09-22.md) fand 0 im Zeitraum 2016–2021 wirksame, verifizierte Issuer-Mappings. Heutige CIK-/FIGI-Zuordnungen werden nicht zurückdatiert.

Die tatsächliche historische Coverage für v2-Fundamentals ist daher **0 belegte Asset-/Listing-Signalzeilen**. Der R5-Capability-Status für diese Familie ist `SHADOW` (Parser/Vertrag vorbereitet, keine aktive historische Feature-Befüllung). Weder `US_EQUITIES_PIT_FUNDAMENTALS` noch „globale Fundamentals“ werden als getesteter Scope behauptet. Revenue Growth, Operating Income, EPS, Margins, Debt, Free Cashflow, Shares/Dilution und Valuation sind nicht implementiert oder aktiviert. Ein späterer Scope müsste von echten versionierten Quellen, revisionssicheren Zeitstempeln und damals gültiger Issuer-Zuordnung outcome-unabhängig neu belegt werden.

R4-D wird als nächster, getrennter Capability-Block geprüft. Die fehlende R4-C-Coverage wird nicht als negativer Research-Befund oder zusätzlicher Strategie-Attempt gezählt.
