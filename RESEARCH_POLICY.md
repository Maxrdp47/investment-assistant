# Investment Assistant – Research Policy

Stand: 2026-09-06

Dieses Dokument enthält dauerhafte Forschungs-, Daten- und Freigaberegeln. Es erteilt keine konkrete Arbeits- oder Startfreigabe. Aktuelle Freigaben stehen ausschließlich in [`ROADMAP.md`](ROADMAP.md).

## 1. Grundsatz

`Research Baseline != Production Strategy`

Next-Open, fixer Stop, fixer 2R-Exit, feste Haltedauern und einzelne Candle-Regeln dürfen kontrollierte Forschungsbaselines sein. Sie sind nicht automatisch Produkt- oder Handelsregeln.

Ein interessantes Merkmal, eine positive Development-Auswertung oder eine große Zahl historischer Fälle ist keine Strategie- und keine Produktionsfreigabe.

## 2. Verbindliche Forschungsfolge

Neue Strategien und Regeländerungen durchlaufen grundsätzlich:

`Frozen Historical Data → Development → Fixed Challenger → Validation → Holdout → External Unseen Universe → True Forward → Autonomous Paper → Shadow Live → separates Echtgeld-Gate`

- Jede Stufe benötigt einen vorab festgelegten Vertrag und ihre eigene Freigabe.
- Ein Fehlschlag darf nicht durch stilles Retuning, neue Filter oder andere Zielwerte gerettet werden.
- Holdout-, External- oder spätere Ergebnisse bleiben geschlossen, bis alle vorgelagerten Gates bestanden und die nächste Stufe ausdrücklich geöffnet wurde.
- Eine neue Contract-ID macht bereits betrachtete Daten nicht wieder ungesehen.
- KI oder Lernlogik dürfen Produktionsregeln, Risikolimits oder Live-Parameter nie selbstständig ändern.

## 3. Point-in-Time und Zukunftswissen

- Ein Merkmal darf nur Informationen verwenden, die am Messzeitpunkt verfügbar waren.
- `published_at`, `first_seen_at`, `effective_at`, Messzeitpunkt, Beobachtungsende und tatsächlicher Exit bleiben getrennt.
- Heutige Stammdaten, Klassifikationen, Fundamentals oder Beziehungen werden nicht rückwirkend als historische Wahrheit ausgegeben.
- Nachträglich geladene Daten werden nur dann als historisch Point-in-Time bezeichnet, wenn ihr damaliger Verfügbarkeitszeitpunkt belastbar belegt ist.
- Revisionen ersetzen alte Stände nicht still. Sie erhalten Version, Zeit und Verweis auf den vorherigen Stand.
- Fehlende Meldung ist nicht automatisch „kein Ereignis“. Providerfehler und gültige leere Antworten bleiben getrennt.

## 4. Datenqualität und Missingness

- Keine Daten erfinden, schätzen oder aus späteren Informationen rückdatieren.
- Kein stilles Clipping, keine Imputation und keine Interpolation für eingefrorene Research-Inputs.
- Rohdaten und ausgeschlossene Quellbalken bleiben nachvollziehbar erhalten.
- Ungültige, fehlende und nicht anwendbare Werte sind verschiedene Zustände.
- Nichtpositive oder strukturell ungültige Risikobasen erzeugen keinen Ersatz-R-Wert.
- R-unabhängige Felder dürfen nur bei eigener erfüllter Datengültigkeit berechnet werden.
- Datenquelle, Quellzeit, lokales erstes Sehen, Coverage, Qualität und Missingness werden sichtbar gehalten.

## 5. Identity, Listings und Dependencies

- Unternehmen, Listing und Instrument sind getrennte Identitäten.
- Kurs, Chart, Volumen, Währung, Entry, Stop, Ziel und Prognose eines Listings dürfen nicht mit einem anderen Listing vermischt werden.
- ADR/ADS, Stammaktie, ETF, Depositary Receipt, Börse und Originalwährung bleiben sichtbar.
- Namen oder ähnliche Ticker allein beweisen keine Issuer-Beziehung.
- Heutige Identity ist ohne belastbares Gültigkeitsfenster keine historische Dependency.
- Unbekannte Beziehungen bleiben `UNKNOWN` und zählen nicht als unabhängige Evidenz.
- Clusterzahl und geschätztes Effective N sind nicht dasselbe.
- Assetklassen, überlappende Beobachtungsfenster und gemeinsame Issuer benötigen getrennte Abhängigkeitsprüfung.

## 6. Research-Design und Overfitting-Schutz

- Auswahl von Assets, Zeiträumen, Schwellen, Features, Baseline und Metriken erfolgt vor Ergebnissichtung.
- Keine freie Schwellen-, Parameter-, Feature- oder Kombinationssuche ohne neuen ausdrücklich freigegebenen Researchvertrag.
- Mehr korrelierte Rohfeatures zählen nicht mehrfach als unabhängige Bestätigung.
- Ein komplexerer Ansatz benötigt robusten inkrementellen Zusatznutzen gegenüber der einfacheren Baseline, Out-of-Sample und im Walk-Forward.
- Kleine, instabile oder nur in engen Parametern sichtbare Effekte werden verworfen oder nur dokumentiert.
- Negative und inkonklusive Ergebnisse bleiben gleichrangig sichtbar.
- MFE ist kein realisierter Gewinn. Eine Beobachtungsrendite ist ohne Exit- und Kostenvertrag keine Nettostrategierendite.
- Profitfaktor oder Strategie-Erwartungswert werden nur bei einem passenden vollständigen Handelsvertrag berechnet.

## 7. Datenstufen und Begriffe

- **Quellenbewertung A/B/C:** Qualität und Verlässlichkeit einer Quelle; keine Strategieentscheidung.
- **Development-Empfehlung:** Ergebnis innerhalb der Entwicklungsdaten; noch keine ungesehene Bestätigung.
- **Validation:** getrennte ungesehene Prüfung eines eingefrorenen Challengers.
- **Holdout:** besonders geschützte spätere Prüfung; bleibt bis zur Freigabe ungeöffnet.
- **Kampagnenrunde A/B/C:** fest getrennte historische Forschungsrunden; nicht mit Quellenklassen verwechseln.
- **Integrationsfreigabe:** separate Entscheidung nach den verlangten Evidenzgates.
- **Research/Shadow:** ohne aktive Signal-, Score-, Risiko- oder Orderwirkung.
- **Production:** ausdrücklich freigegebene aktive Produktlogik; technisch vorhanden allein reicht nicht.

Die früher verwendete Mindestfallzahl 20/50 bleibt höchstens eine Diagnose- oder Hinweisgrenze. Sie ist keine Strategie-, Wahrscheinlichkeits-, Integrations- oder Produktionsfreigabe.

## 8. Knowledge Base und Provenienz

- Sources, Claims, Hypothesen, Experimente, Resultate, Statusänderungen und Artefaktverweise bleiben append-only nachvollziehbar.
- Eine externe Quelle validiert keine Hypothese automatisch.
- Ein KB-Work-Request mit Status `READY` ist keine allgemeine oder Urlaubs-Ausführungsfreigabe.
- Frühere `REJECTED`, `NEGATIVE`, `INCONCLUSIVE` und nicht ausgeführte Stufen bleiben sichtbar.
- Hypothese und Resultat dürfen unterschiedliche Lifecycle-Stände besitzen; Reporting darf daraus keine unzulässige aktive Kandidatur ableiten.
- Run-ID, Daten-, Code-, Contract- und Artefaktfingerprints werden gespeichert, soweit vorhanden.
- Unbekannte Provenienz wird als unbekannt ausgewiesen und nicht ergänzt oder geraten.

## 9. Collector und Observer

- Datensammlung und Strategieentscheidung müssen technisch und fachlich getrennt sein.
- Ein signalunabhängiger Observer darf keine Buy-/Sell-Scores, Tradepläne, Paper-Trades oder Shadow-Orders erzeugen.
- Vor Aktivierung benötigt ein Collector einen Quellenvertrag mit Quelle, erlaubten Daten, Zweck, Kostenstatus, Rhythmus, Universe, Zeitsemantik, Revisionen, Aufbewahrung und Ressourcenbudget.
- Nur rechtmäßig vorhandene öffentliche Quellen und konfigurierte Adapter verwenden.
- Keine neuen Konten, kostenpflichtigen Anbieter, unfreigegebenen Scraper oder erfundenen Kontaktkennungen.
- Collector-Daten dürfen nicht nachträglich in einen bereits eingefrorenen laufenden Research-Run eingespeist werden.
- Unvollständige Coverage wird als `PARTIAL` beschrieben, nicht als vollständig.

## 10. Reproduzierbarkeit und Laufbetrieb

- Ein laufender Research-Prozess benötigt unveränderliche Inputs, Konfiguration, Code, Contracts und Fingerprints.
- Neue Versionen erhalten neue Stores und Parent-Bezug; alte Runs werden nicht in-place umgeschrieben.
- Checkpoints und Resume müssen idempotent sein.
- Ein Writer serialisiert SQLite-Schreibzugriffe, sofern der Vertrag nichts Strengeres verlangt.
- Prozess-Lock und Scheduler verhindern Doppelstarts. Eine vorhandene Lock-Datei allein beweist keinen aktiven Lock.
- Nur transiente Fehler dürfen automatisch wiederholt werden. Systematische Daten-, Contract- oder Semantikfehler verlangen Review.
- Nach terminalem Zustand keine wiederholten Heavy-Audits oder doppelten Abschlussereignisse.
- Backups aktiver SQLite-Datenbanken berücksichtigen WAL und Konsistenz. Wiederherstellung nur in getrennten Dateien testen.

## 11. Test- und Git-Regeln

Vor einem normalen Push mindestens passend zum Umfang:

- Projektcode kompilieren, ohne virtuelle Umgebung und große Runtime-Bestände,
- vollständige vorhandene Tests,
- relevante neue Tests,
- Repository-Sicherheitscheck,
- Offline-Smoke,
- tatsächlicher Streamlit-Start,
- `git diff --check`.

Schreibende Tests verwenden Test-Stores. Private Runtime-Daten, Portfolios, Thesen, Zugangsdaten und sensible Logs werden nicht committed.

Kein Force Push, `git reset --hard`, `git clean` oder Verlust fremder Änderungen. CI wird nur dann als grün bezeichnet, wenn ein echter Lauf für den exakten finalen Commit erfolgreich war.

## 12. Paper, Shadow, Broker und Echtgeld

- Historische Forschung, True Forward, Paper, Shadow und Echtgeld sind getrennte Evidenzstufen.
- Paper und Shadow sind keine Echtgeldfreigabe.
- Bis zum erfolgreichen Echtgeld-Gate bleiben Brokeranbindung und automatische Orderausführung strikt gesperrt.
- Danach wäre nur eine separate, ausdrücklich freizugebende Live-Bot-Phase zulässig.
- Eine unabhängige Risk Engine, Kill-Switches und harte Limits dürfen von Strategie oder KI niemals überschrieben werden.
- Diese Policy selbst aktiviert keine spätere Stufe.

## 13. Gesamtsystem

Discovery, Thesis, Entry, Risk, Position Management und Exit benötigen jeweils eigene Evidenz. Interessante Einzelkomponenten dürfen nicht still zu einer Gesamtstrategie verbunden werden.

Vor einer späteren Systemfreigabe muss die gemeinsame Wirkung unter Kapitalbindung, gleichzeitig offenen Positionen, Kosten, Slippage, Gaps, Liquidität und passenden Halte- beziehungsweise Finanzierungskosten geprüft werden.
