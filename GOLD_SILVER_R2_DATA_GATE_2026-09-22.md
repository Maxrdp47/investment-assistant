# R2 Gold/Silber – Daten- und Ausführungsgate

Stand: 2026-09-22. Programm `finite-research-program-2026-09-15-v1`, Block R2. Status: `BLOCKED_BY_DATA_SEMANTICS`, **0 Research-Versuche**, keine Performance-Ergebnisse.

## Eingefrorene Anforderung aus der Knowledge Base

Work Request `4fdfb983-ddbc-4178-bd36-7aa34267df0b`, Hypothese `f8e6a64b-1cf9-431f-9477-4a7a17ab5478`, Experiment `255532e0-3b54-412a-a29e-866bfe4bda82`. Der vorbestehende DRAFT-Vertrag verlangt `GC=F` und `SI=F`, gemeinsame abgeschlossene Tagesbalken, einen kausalen 60-Sitzungs-Z-Score des logarithmischen Preisverhältnisses, `|z| ≥ 2`, Einstieg frühestens am nächsten gemeinsam handelbaren Open, 5/10/20 Sitzungen sowie Long-Laggard-/Short-Leader- und weitere festgelegte Kontrollen. Roll-/Backadjustment, Sessions, Kosten und Slippage müssen vor Ergebnisbetrachtung nachvollziehbar sein.

## Read-only-Preflight, keine Strategieauswertung

- Yahoo/yfinance liefert für `GC=F` und `SI=F` im Development-Monat Januar 2015 jeweils 20 OHLCV-Tageszeilen. Die Antwort enthält jedoch weder den zugrunde liegenden Kontrakt je Zeile noch Rolltermin, Rollpreis oder Adjustierungsregel. Die aktuelle [Yahoo-Gold-Seite](https://finance.yahoo.com/quote/GC%3DF/) nennt einen konkreten aktuellen Kontrakt; daraus lässt sich die Historie nicht kausal rekonstruieren. Die [yfinance-History-Schnittstelle](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py) beschreibt `auto_adjust`/`back_adjust` für OHLC, aber keine Yahoo-spezifische Futures-Rollkette. Dies ist eine begrenzte Quellen-/Metadatenfeststellung, keine Behauptung, Yahoo habe niemals solche Daten.
- Stichprobenabfragen für `GCJ15.CMX`, `GCM15.CMX`, `GCZ15.CMX`, `SIH15.CMX`, `SIK15.CMX` und `SIZ15.CMX` für 2015-01-01 bis 2015-04-01 lieferten jeweils 0 Zeilen. Damit lässt sich die benötigte historische Kontraktkette aus der verfügbaren Yahoo-Quelle hier nicht ersatzweise selbst aufbauen.
- Die [offizielle CME Continuous Price Series](https://www.cmegroup.com/market-data/cme-group-continuous-price-series.html) definiert Active-/Front-Rollvarianten und listet Gold/Silber ab 2010. Sie ist ausdrücklich eine **Settlement**-Serie; Zugang zu historischen Dateien/MDP erfordert Lizenz/DataMine. Ein Settlement allein belegt keinen nachfolgenden handelbaren Open und genügt dem vorregistrierten Entry nicht. Es wurde kein bezahlter Zugang gebucht oder Konto erstellt.
- Lokale Research-Stores enthalten keinen separaten Gold-/Silber-Kontrakt-OHLC-/Roll-Datensatz. COT- oder andere Proxy-Daten ersetzen ihn nicht. Eine Rollregel nachträglich aus sichtbaren Kursverläufen abzuleiten oder Spreads/Funding zu raten, wäre keine zulässige Reparatur.

## Gate-Entscheidung

Kein isolierter Performance-Runner und kein Forschungs-Freeze mit unzureichender Quelle. Der R2-Work-Request wurde mit konkreter Begründung auf `BLOCKED` gesetzt; Experiment bleibt `DRAFT`, Result-ID fehlt. Development, Validation und Holdout für R2 sind **ungesehen/nicht gestartet**. Die streng sequenzielle R0–R9-Kette stoppt hier technisch; R3–R9 dürfen ohne neue Nutzerentscheidung oder belegbar geeignete, bereits zulässige Kontraktquelle nicht übersprungen oder gestartet werden.

Für eine spätere Freigabe nötig wären mindestens historisch identifizierte GC-/SI-Einzelkontrakte mit PIT-Zeitstempeln, dokumentierter Roll-/Adjustierungsregel, gemeinsamen Sessions, tatsächlich nutzbaren nächsten Opens sowie belastbaren Spread-/Slippage-/Rollkosten. Das ist eine Daten-/Methodikvoraussetzung, keine Aufforderung zum Kauf einer Quelle.
