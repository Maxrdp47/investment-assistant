# Investment-Assistent

Lokale Streamlit-App zur Analyse von Aktien, ETFs und Kryptowährungen über Yahoo Finance.

Die App handelt nicht automatisch, hat keine Broker-Anbindung und gibt keine Finanzberatung. Sie ist eine technische Analysehilfe; die letzte Entscheidung trifft immer der Nutzer.

## Funktionen

- Startseite mit drei klar getrennten Bereichen: `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder`
- `Investment Opportunities` zeigt bis zur fachlichen Umsetzung bewusst einen ehrlichen Leerzustand statt erfundener Kandidaten oder provisorischer Scores
- der `Swing Trade Finder` durchsucht automatisch ein versioniertes Universum mit 2.520 liquiden Aktien, ETFs und großen Kryptowährungen; alle bestandenen Grobfilterkandidaten werden ohne feste Top-N-Grenze tief analysiert, bestehende Paper-Trades und lokale Historien bleiben erhalten
- Asset-Name oder Yahoo-Finance-Ticker eingeben
- automatische Yahoo-Finance-Suche mit auswählbaren Treffern für Firmennamen, ETFs und Kryptowährungen
- Speicherung der zuletzt erfolgreichen Suchanfragen in `search_history.json`
- priorisierte Anzeige der zuletzt erfolgreichen Suchen direkt in den Suchvorschlägen
- Währungsmanagement: Anzeige standardmäßig in EUR plus Originalwährung
- automatische Asset-Typ-Erkennung: Aktie, ETF, Krypto oder unbekannt
- manuelle Asset-Typ-Auswahl, falls die automatische Erkennung unsicher ist
- getrennte Bewertung von Asset-Qualität, Kaufsignal und Depot-Effekt
- zentrale Empfehlungsbox mit Kaufsignal, Research-Einordnung, Asset-Qualität, Depot-Effekt und Vertrauensscore
- klare Warnungen bei eingeschränkten Yahoo-Finance-Datenquellen wie Stammdaten, Wechselkursen, News oder Makro-Proxies
- technische Analyse mit RSI, MACD, Trend, Volumen, Volatilität, Unterstützungen, Widerständen und CRV
- entkoppelte Datenbasis: Der gewählte Chart-Zeitraum steuert nur die Visualisierung; die Analyse nutzt unabhängig davon die maximal verfügbare Historie
- professionelle Research-Ansicht mit Datenqualitäts-Ampel, Modul-Scores, Szenarien, Nachkaufzonen und Fazit
- Marktphase und Szenario-Wahrscheinlichkeiten
- Anfänger-Modus mit einfachen Erklärungen
- optionaler Portfolio-Modus mit `portfolio.json`

## Start

Per Desktop-Symbol **Investment-Assistent** oder manuell:

```powershell
cd C:\investment-assistent
.\.venv\Scripts\python.exe -m streamlit run app.py
```

## Smoke-Test

Für eine schnelle technische Prüfung:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

Zusätzlich gibt es einen Repository-Sicherheitscheck:

```powershell
.\.venv\Scripts\python.exe scripts\repo_safety_check.py
```

Der Check prüft, ob private Laufzeitdateien versehentlich versioniert sind, ob `portfolio.json` nur GitHub-kompatible Minimalfelder enthält und ob Secret-Dateien wie `.env` oder `.streamlit/secrets.toml` nicht getrackt werden.

Der Test kompiliert `app.py`, startet Streamlit kurz auf einem freien lokalen Port, prüft den Analysefluss mit `BTC-EUR`, `NVDA` und `1810.HK` und zeigt die Datenqualität lokaler Lernhistorien. Ohne Live-Daten:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py --skip-live-data
```

Für GitHub ist zusätzlich ein Workflow unter `.github/workflows/smoke.yml` vorbereitet. Er installiert die Laufzeit- und Testabhängigkeiten aus `requirements-dev.txt`, führt den Repository-Sicherheitscheck und alle Pytest-Regressionstests aus und startet danach den Offline-Smoke-Test ohne private Laufzeitdateien.

Die technische Indikator-, Unterstützungs-/Widerstands-, CRV- und Marktphasenlogik liegt getrennt in `technical_analysis.py`. `app.py` stellt die bisherigen Funktionsnamen weiterhin bereit. Eigene Regressionstests prüfen die ausgelagerte Logik unabhängig von der Streamlit-Oberfläche.

Das Laden und die reine Auswertung der optionalen Portfolio-Daten liegen getrennt in `portfolio_analysis.py`. Netzwerkzugriffe für fehlende aktuelle Kurse bleiben kontrolliert in `app.py`; die bisherigen App-Funktionsnamen und sämtliche Depot-Regeln bleiben kompatibel.

Deutsche Betragsformatierung, EUR-Umrechnung und die Umrechnung von Kursreihen und Chartmarken sind als reine Hilfslogik in `currency_utils.py` gebündelt. Die Anzeigeformate und bisherigen App-Funktionsnamen bleiben unverändert.

Die vorhandene Aktien- und ETF-Fundamentallogik liegt getrennt in `fundamental_analysis.py`. Snapshots, Datenlücken, Kennzahlgrenzen und Scores sind dadurch unabhängig von Streamlit und Yahoo-Netzwerkzugriffen testbar; die App verwendet weiterhin dieselben Funktionsnamen und Bewertungsregeln. Nicht endliche Zahlen wie `NaN` oder unendliche Werte werden zentral als nicht verfügbare Daten behandelt und erzeugen keine Extrem-Scores.

Die bestehende Quellenwarnungs- und Datenqualitätsprüfung liegt in `data_quality_analysis.py`. Yahoo-Stammdaten, Wechselkurs, News und Makroausfälle bleiben getrennt sichtbar; der Grün-/Gelb-/Rot-Status verwendet unverändert dieselben Schwellen. Ticker, Asset-Typ, Börse, Währung, Kurszeilen, Volumen sowie 50er-/200er-Durchschnitt werden defensiv geprüft, ohne fehlende Werte zu erfinden. Eine vollständig leere Kurstabelle wird jetzt sicher als Datenlücke gemeldet, statt nach der ersten Warnung noch auf eine nicht vorhandene `Close`-Spalte zuzugreifen.

Die vorhandene transparente Score-Zusammensetzung liegt in `score_composition.py`. Sie zeigt die konfigurierten Bausteingewichte in ihrer Reihenfolge, berechnet den bisherigen gewichteten Gesamtwert aus Technik, Fundamentaldaten, Makro, News und CRV und bildet optionale Teilwerte weiterhin neutral beziehungsweise als gerundeten Mittelwert. Standardgewichte, sichtbare Erklärungen und App-Funktionsnamen bleiben unverändert; Eingabegewichte werden nicht verändert.

Das vorhandene Bewertungsmodul liegt getrennt in `valuation_analysis.py`. Es verarbeitet die verfügbaren Gewinn-, Umsatz-, Cashflow-, Buchwert- und Enterprise-Value-Multiplikatoren weiterhin mit denselben Grenzen und legt fehlende historische Multiple-Reihen, Peer-Daten, ETF-Indexbewertung sowie Krypto-On-Chain-Daten offen, statt Ersatzwerte zu erfinden. Krypto nutzt in diesem Modul bei fehlenden Spezialdaten ausschließlich den vorhandenen Makrokontext.

Zukunftspotenzial und eingepreiste Erwartungen liegen getrennt in `future_potential_analysis.py`. Die vorhandene Logik verbindet Asset-Qualität mit verfügbaren Wachstums-, Margen- und News-Signalen beziehungsweise Bewertung, Momentum und Sentiment. Fehlende Produkt-, Netzwerk-, Adoptions-, IPO-, KI-, Kapitalfluss- oder Spezial-Sentimentdaten bleiben ausdrücklich nicht verfügbar und werden nicht durch Textannahmen ersetzt.

Szenario-Wahrscheinlichkeiten, numerische Kursbereiche, sichtbare Bull-/Basis-/Bear-Szenarien und Expected Value liegen getrennt in `scenario_analysis.py`. Bull-, Basis- und Bear-Gewichte verwenden weiterhin Kaufsignal, Asset-Qualität, CRV, Marktphase, Trendstruktur, Unterstützungen/Widerstände und Volatilität; die Summe bleibt 100 Prozent und der Basisfall erhält mindestens 20 Prozent. Sichtbare Szenarien und gespeicherte Prognosebereiche verwenden dieselbe zentrale Markenlogik. Der Expected Value nutzt reale technische Marken, wenn sie vorhanden sind, und ansonsten die bereits dokumentierten konservativen Fallback-Renditen.

Die bestehende zentrale Entscheidungssynthese liegt in `recommendation_synthesis.py`. Sie verbindet langfristige Attraktivität, Preisattraktivität, kurzfristiges Timing, Datenqualität und einen optionalen Depot-Effekt weiterhin mit denselben Schwellen zu einem konkreten Mehrpfad-Plan. Die Streamlit-App reexportiert die bisherigen Funktionsnamen; Kategorien, Tranchierung, Widerlegung, Gültigkeit und sichtbare Texte wurden bei der Trennung nicht verändert.

Konkrete Einstiegszonen, technische Aktionskategorien, Confidence-Bezeichnungen, Anlagehorizonte und Gültigkeit liegen getrennt in `entry_plan.py`. Kauf-, Bestätigungs- und Widerlegungsmarken werden weiterhin nur aus vorhandenen Unterstützungen, Widerständen oder einem geeigneten 50er-Durchschnitt gebildet. Vergangene Earnings-Termine verkürzen die Gültigkeit nicht; nur ein tatsächlich zukünftiger Termin kann die spätestens 30-tägige Neubewertung vorziehen.

Die Preisattraktivität und der bewusst unvollständige Fundamentalvergleich seit dem historischen Kurshoch liegen getrennt in `price_attractiveness.py`. Ein großer Kursrückgang verbessert die Preiseinordnung nur, wenn die verfügbaren aktuellen Umsatz-, Gewinn- und Cashflow-Signale nicht gleichzeitig eine deutliche Verschlechterung anzeigen. Der Abstand zum Hoch bleibt ausdrücklich Kontext und niemals ein automatisches Kaufsignal; mangels historischer Stichtagsfundamentaldaten wird kein exakter Vorher-/Nachher-Vergleich erfunden.

Die technische Quellenbasis für die geplante Long-Term-Analyse liegt in `long_term_analysis.py`. Das versionierte Modell prüft für zehn Pflichtbereiche, ob Aussagen mit vollständiger Herkunft, Abrufzeitpunkt und Verwendungszweck durch offizielle Primärquellen beziehungsweise unabhängige belastbare Quellen gedeckt sind. Fehlende, ungültige oder doppelte Quellen-IDs werden nicht still zusammengeführt. Seit Evidenzversion 2 gelten außerdem quellentypische Höchstalter: laufende Markt-/Börsendaten veralten schneller als Geschäftsberichte oder strukturelle Branchenstudien. Maßgeblich ist ein vorhandener Veröffentlichungszeitpunkt; ein alter Bericht wird durch erneutes Herunterladen nicht wieder aktuell. Abrufzeitpunkte benötigen eine Zeitzone und dürfen nicht in der Zukunft liegen. Yahoo Finance, allgemeine News und sonstige Kontextquellen reichen allein nicht für eine Long-Term-Freigabe. Kurzfristige Chart- und Einstiegssignale werden ausdrücklich außerhalb dieser Prüfung gehalten und können die langfristige Quellenabdeckung nicht verbessern. Das Quellenmodul selbst erzeugt keinen Score und ist bewusst noch nicht als auswählbarer UI-Modus freigeschaltet.

`long_term_research_cache.py` ergänzt dafür eine noch nicht produktiv befüllte lokale Quellenablage unter `runtime/long_term_research/`. Sie speichert ausschließlich öffentliche Quellenmetadaten und belegte Aussagen in einem versionierten JSON-Schema, schreibt atomar und lehnt ungültige, bereits bei Sammlung veraltete oder zeitlich widersprüchliche Quellen, unbekannte Referenzen, falsche Modellversionen sowie zukünftige Schemata ab. Ein später abgelaufener Cache bleibt zur Diagnose lesbar, gilt aber ausdrücklich als nicht verwendbar und wird niemals still als aktuelle Analysebasis genutzt. Ticker werden zu sicheren Dateinamen normalisiert, sodass Eingaben keinen Pfad außerhalb des Cache-Verzeichnisses erzeugen können.

`long_term_scoring.py` stellt darauf aufbauend eine noch nicht mit echten Quellenadaptern oder der Oberfläche verbundene, deterministische Long-Term-Bewertung bereit. Sie berechnet erst nach vollständiger Quellenfreigabe sieben getrennte Faktoren mit sichtbaren Gewichten sowie Bear-, Basis- und Bull-Szenarien über drei bis sieben Jahre. Wahrscheinlichkeiten müssen zusammen 100 Prozent ergeben, Zielwerte logisch geordnet und Bedingungen ausdrücklich vorhanden sein. Fehlende oder nicht endliche Werte werden nicht ergänzt. Technisches Einstiegstiming ist als Faktor verboten und kann weder Unternehmensqualität, Zukunftspotenzial, Bewertung noch Schutz vor dauerhaftem Kapitalverlust verbessern. Das Modul erzeugt bewusst noch keine Kauf- oder Verkaufsempfehlung.

`sec_filing_sources.py` ist der erste noch nicht in UI oder Hintergrundbetrieb aktivierte offizielle Quellenadapter. Er ordnet einen exakten US-Ticker über die öffentliche SEC-Tickerdatei einer CIK zu und entdeckt aktuelle 10-K-, 20-F-, 40-F- und 10-Q-Dokumente über die öffentliche EDGAR-Submissions-API. Dokument-URLs und Quellen-IDs werden defensiv aufgebaut; alte Berichte, unzulässige Pfade und unvollständige Antworten werden nicht übernommen. Gemäß den [SEC-EDGAR-Zugriffsregeln](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) verlangt jeder echte Abruf einen nur zur Laufzeit übergebenen deklarierten User-Agent mit Kontaktadresse; dieser wird weder in Quellenmetadaten noch im Cache gespeichert. Ein prozessweit wiederverwendbarer Fair-Access-Client serialisiert Anfragen mit mindestens 0,12 Sekunden Abstand und lädt die große Ticker-/CIK-Datei je Prozess nur einmal. Vorübergehende HTTP-Überlastungs-/Serverfehler und Verbindungsfehler erhalten höchstens drei begrenzte Versuche mit gedeckeltem Backoff; dauerhafte HTTP-Fehler und ungültiges JSON enden sofort sichtbar. Der Adapter liefert ausschließlich offizielle Quellenmetadaten und leitet noch keine Aussagen, Scores oder Empfehlungen daraus ab. Vor einer automatischen Aktivierung fehlen weiterhin prozessübergreifende Begrenzung sowie zusätzliche unabhängige Quellen für Markt und Wettbewerb.

`sec_json_cache.py` ergänzt einen atomaren persistenten Cache ausschließlich für die freigegebene öffentliche SEC-Tickerdatei sowie einzelne Submissions- und Company-Facts-Adressen. Die Ticker-/CIK-Datei gilt 24 Stunden, einzelne Unternehmensdateien sechs Stunden. Frische Einträge verhindern erneute Netzabrufe über Prozessneustarts hinweg; beschädigte, zu alte, zukünftig datierte, fremde oder aus einer neueren Schemaversion stammende Einträge werden niemals ausgeliefert. Der User-Agent wird nicht gespeichert. Ein fehlgeschlagener Dateiaustausch erhält den bisherigen Cache, und ein reiner Cachefehler macht einen erfolgreichen öffentlichen Abruf nicht unbrauchbar. Der Cache ist noch nicht mit dem normalen App- oder Hintergrundpfad verbunden.

`sec_financial_facts.py` verarbeitet aus SEC Company Facts ausschließlich klar definierte aktuelle US-GAAP-Jahreswerte für Umsatz, Nettoergebnis, operativen Cashflow, Vermögenswerte, Verbindlichkeiten und Zahlungsmittel. Quartalszeilen, Zukunftszeiträume, nicht endliche Werte, ungültige Accession Numbers und alternative Doppeltags werden nicht vermischt; je Kennzahl gilt eine feste transparente Konzeptpriorität. Eine Zahlenangabe wird erst dann zur Evidenz für `financial_quality`, wenn die exakt passende offizielle Filing-Dokumentquelle mit derselben Accession Number vorhanden ist. Sind zwei aufeinanderfolgende Jahreswerte und beide Filingquellen vorhanden, entsteht zusätzlich ein rein rechnerischer Vorjahresvergleich. Bei nicht positivem Vorjahreswert wird bewusst keine irreführende Prozentänderung berechnet. Ohne vollständige Quellenverbindung bleibt der Vergleich eine sichtbare Datenlücke. Das Modul erzeugt weder Qualitätsurteil noch Score oder Empfehlung und ist noch nicht automatisch aktiviert.

`sec_long_term_collection.py` verbindet SEC-Tickerauflösung, Filing-Discovery und Company Facts zu einem einzigen nicht schreibenden Sammelergebnis. Es liefert Quellen, exakt verknüpfte aktuelle Finanzwerte und belegte Jahresvergleiche, Warnungen sowie den normalen Long-Term-Bereitschaftsbericht. Auch ein technisch erfolgreicher SEC-Lauf bleibt erwartungsgemäß nicht freigegeben, solange insbesondere unabhängige Markt-/Wettbewerbsquellen und die übrigen Pflichtbereiche fehlen. Ein Company-Facts-Ausfall verwirft bereits entdeckte Filingquellen nicht, erzeugt daraus aber keine Finanzbehauptung. Der Standardweg kann Fair-Access-Taktung und öffentlichen persistenten Cache zusammensetzen; er ist nur über die nachfolgende bewusst manuelle CLI erreichbar und noch nicht in App oder Windows-Aufgabe aktiviert.

Der vorbereitete manuelle Einstiegspunkt `scripts/collect_long_term_sources.py` besitzt eine vollständig offline und nicht schreibende Vorprüfung:

```powershell
.\.venv\Scripts\python.exe scripts\collect_long_term_sources.py --preflight
```

Ein echter Abruf bleibt gesperrt, solange `INVESTMENT_ASSISTANT_SEC_USER_AGENT` nicht ausschließlich zur Laufzeit mit Projektname und erreichbarer Kontaktadresse gesetzt ist. Die Vorprüfung gibt nur aus, ob eine gültige Kennung vorhanden ist, niemals ihren Wert. Der Cachepfad muss innerhalb des privaten `runtime/`-Verzeichnisses liegen. Der Live-Weg ist nicht geplant oder automatisch aktiviert; er sammelt nur SEC-Teilquellen, erzeugt keine Long-Term-Empfehlung und kann das Gesamtgate allein nicht öffnen.

## Research Knowledge Base

Die App enthält einen bewusst von Trading-, Scanner- und Scoringlogik getrennten Bereich **Research Knowledge Base**. Die private, migrationsfähige SQLite-Datei unter `runtime/research_knowledge.sqlite3` ist die gemeinsame Single Source of Truth für DB-Chat und Work-Chat; `INVESTMENT_ASSISTANT_RESEARCH_KB_DB` kann einen anderen lokalen Pfad setzen. Runtime-Daten und lokale Sicherungen werden nicht versioniert.

Das Modul `research_knowledge/` trennt Quellen, Hypothesen, Experimente und Ergebnisse. Mehrere Quellen können eine Hypothese unterstützen, ihr widersprechen oder nur Kontext liefern; mehrere Experimente und Ergebnisse bleiben getrennt verknüpft. Statusänderungen, externe Prüfungen, Research-Referenzen und Ergebnisse landen chronologisch in einem append-only Evidence Ledger. Auch frühere `REJECTED`-Entscheidungen bleiben über die Statushistorie suchbar. Ein erneuter Test einer verworfenen Hypothese benötigt dokumentierte neue Evidenz, neue Daten oder eine materiell andere Hypothese.

Eine Source speichert append-only Provenienz mit Plattform, Creator, Titel, direkter und normalisierter URL, Content-ID, Profil-URL, Veröffentlichungsdatum, lokalem Dateinamen, Datei-SHA-256/-Größe und deterministischem Fingerprint, soweit diese Angaben tatsächlich verfügbar sind. Exakte Identität folgt der Reihenfolge Plattform+Content-ID, normalisierte URL und Datei-Hash. Trackingparameter und alternative YouTube-/TikTok-URLformen erzeugen keine zweite Source. Ähnliche Titel allein liefern nur `POSSIBLE_DUPLICATE`; ein bewusster Merge oder eine Bestätigung als eigenständige Source ist erforderlich. Ein eindeutig bekanntes Video wird immer als `DUPLICATE_SOURCE` angezeigt und nicht erneut aufgenommen. Nur ein bisher fehlender technischer Identitätsschlüssel, etwa der Datei-Hash zu einer bereits bekannten Content-ID, darf intern an der bestehenden Source ergänzt werden, damit spätere Uploads ebenfalls sicher als Duplikat erkannt werden. Claims, Hypothesen, Experimente und Work Requests werden dabei niemals dupliziert.

Video- und Audioquellen werden nicht pauschal transkribiert. Der DB-Chat prüft zuerst Source/Fingerprint und Duplikate, verwendet ein noch vorhandenes Source-Transcript wieder und beurteilt das Video zunächst direkt. Vollständig verständlicher Ton, lesbare Untertitel oder ein mitgeliefertes Transcript lösen keinen Speech-to-Text-Lauf aus. Nur wenn fachlich wesentliche gesprochene Aussagen sonst nicht zuverlässig verstanden werden, greift der lokale Fallback. Die Statuswerte `NOT_REQUIRED`, `EXISTING`, `GENERATED`, `FAILED` und `INSUFFICIENT_AUDIO` halten diese Entscheidung transparent fest.

Maschinell erzeugte Transkripte liegen standardmäßig privat unter `runtime/research-media/transcripts/`; die KB speichert Source-ID, Fingerprint, Content-ID/Datei-Hash, sicheren lokalen Pfad, Transcript-Hash, Sprache, Engine-/Modellversion, Zeit, Segmente und Qualitätshinweis. Ein Transcript ist ausschließlich ein abgeleitetes Artefakt seiner ursprünglichen Source, keine neue externe Quelle oder eigenständige Evidenz. Fehlende oder veränderte Dateien werden nicht als verfügbar gemeldet. Eigennamen, Ticker, Zahlen, Prozente, Kursniveaus, Daten und Fachbegriffe sind bei relevanten Claims gegen Video, Einblendungen oder externe Quellen zu prüfen.

Der optionale Fallback nutzt `faster-whisper` ohne LLM-Auswertung. `small`, CPU und INT8 sind die ressourcenschonenden Standards; Modell, Gerät, Compute-Typ und Sprache bleiben konfigurierbar. Die Hauptabhängigkeiten installieren Whisper bewusst nicht automatisch:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-transcription.txt
.\.venv\Scripts\python.exe scripts\transcribe_research_media.py <SOURCE_ID> <MEDIA_DATEI> --transcription-required --reason "Wesentliche Aussagen akustisch unklar"
.\.venv\Scripts\python.exe scripts\transcribe_research_media.py <SOURCE_ID> --direct-content-sufficient --reason "Vollständige lesbare Untertitel"
```

Die Mediendatei muss zuvor über den normalen Source-Intake und ihren SHA-256 mit der Source verknüpft sein. Ein bereits registriertes Transcript wird vor jedem Modelllauf wiederverwendet. Der erste Einsatz eines Modellnamens benötigt das Modell im lokalen Cache; alternativ akzeptiert `--model` einen vorhandenen lokalen Modellpfad.

Eine Hypothese kann weder aufgrund einer externen Quelle noch aufgrund irgendeines beliebigen internen Resultats `VALIDATED` werden. Erforderlich ist ein explizit ausgewähltes unterstützendes Resultat eines abgeschlossenen Experiments. Der versionierte Market-Scope-Vertrag aus `swing_research_market_scope.py` prüft Source-, Hypothesen-, Test- und validierten Scope ohne Cross-Market-Vererbung. OOS, Walk-Forward, Sample Size, Unsicherheit, Datenqualität, Point-in-Time-/Leakage-Status sowie je Researchvertrag External/Unseen, Forward, Paper und Kosten/Slippage müssen bestanden oder ausdrücklich nicht erforderlich sein. Das Gate ändert keine Strategie und erzeugt keine automatische Integration.

`ResearchWorkflow` ergänzt darauf einen append-only Intake-Prozess, ohne das Kernmodell zu duplizieren: Ein aus einer Quelle extrahierter Claim erhält zuerst einen Ähnlichkeits-Snapshot gegen vorhandene Hypothesen einschließlich früherer Quellen, Experimente, Ergebnisse und `REJECTED`-Begründungen. Ein gleicher Claim wird dem bestehenden Eintrag zugeordnet; eine neue Hypothese ist nur ohne passenden Eintrag oder als begründete materielle Variante zulässig. Evidenzstärke und Confidence besitzen eine eigene Historie. Verworfene Ideen werden durch eine neue Quelle nicht automatisch wieder geöffnet.

Der anschließende App-Abgleich verwendet ausschließlich `ALREADY_AVAILABLE`, `TESTABLE_NOW`, `CODE_EXTENSION_REQUIRED`, `NEW_DATA_REQUIRED`, `DEFERRED` oder `NO_ACTION`. Nur die drei tatsächlich actionable Outcomes erzeugen bei passendem Researchbedarf einen idempotenten `READY` Work Request; `NO_ACTION`, `DEFERRED`, bloßes `ALREADY_AVAILABLE` und ein unveränderter Duplicate-Upload dürfen keinen Request erzeugen. Quellen-, Experiment- und möglicher Integrationsscope werden getrennt gespeichert. Eine Übertragung zwischen FX, Aktien, Crypto oder anderen Märkten erzeugt eine neue Hypothese mit eigener Validierung.

`research_work_requests` bildet den persistenten DB-Chat↔Work-Chat-Handoff in derselben KB. Ein Work-Chat listet `READY`, übernimmt einen Request atomar als `IN_PROGRESS`, lädt Hypothese, Source, Evidence, Scope, Risiken, Experiment und frühere Results, und schreibt danach Experimentstatus, Resultat und Artefakt-/Run-/DB-Referenzen direkt zurück. Statushistorie und Ledger bleiben append-only; Claim-Token verhindern eine unbemerkte Doppelübernahme, Idempotency-Keys verhindern doppelte Requests und Resultate. Der frühere manuelle `KB-RESULT`-Copy/Paste-Rückkanal ist nicht erforderlich.

Der kleine CLI-Einstiegspunkt verwendet dieselben APIs und keine rohe SQLite-Manipulation:

```powershell
.\.venv\Scripts\python.exe scripts\research_work_handoff.py list --status READY
.\.venv\Scripts\python.exe scripts\research_work_handoff.py show <WORK_REQUEST_ID>
.\.venv\Scripts\python.exe scripts\research_work_handoff.py claim <WORK_REQUEST_ID> --worker <KONTEXT>
```

Ein unterstützendes Resultat kann höchstens einen unveränderbaren `INTEGRATION_CANDIDATE` erzeugen. Dafür werden inkrementeller Mehrwert gegenüber der unveränderten Baseline, OOS-/Walk-Forward- und Forward-/Paper-Evidenz, Sample Size, Kosten, Feature-Redundanz, Komplexität, Overfiltering, Tradezahl, Market Scope und die einfachste ähnlich wirksame Variante einzeln festgehalten. Pro Candidate sind höchstens fünf fachlich begründete Features zulässig. Eine Freigabe auf Datenbankebene ist nur möglich, wenn alle Gates bestanden sind; die tatsächliche externe Integration benötigt danach noch ein separates bewusstes Entscheidungs- und Integrationsereignis. Die Knowledge Base selbst ändert dabei weiterhin keinen Produktivcode.

Die Oberfläche bleibt eine einfache Lese- und Suchansicht für Quellenidentität und Transcript-Status, Wissensabgleich, App-Testbarkeit, Market Scopes, Work Requests, Experimente, Ergebnisse, Validierungsauswahl, Integration Candidates und Ledger. Befüllung erfolgt über die getesteten APIs `ResearchKnowledgeBase`, `ResearchWorkflow` und `ResearchMediaTranscription`; Vector-Datenbanken, Embeddings, ein externer LLM-/Transkriptionsdienst, Broker und Orderausführung sind nicht Teil dieser Ausbaustufe.

## Automatische Prognosen und Datenbank-Wartung

Der lokale Hintergrundprozess speichert unveränderbare Prognosen und spätere Auswertungen in `runtime/forecasts.sqlite3`. Diese private Datei wird nicht versioniert. Die Windows-Aufgabe startet täglich um 22:30 Uhr und prüft zuerst alle fälligen Ergebnisse. Neue Prognosen werden ab 2026-08-10 nur für die jeweils fällige Wochenkohorte erzeugt; es gibt keine Broker-Verbindung und keine Orderausführung.

Das versionierte Wochenuniversum enthält 1.726 eindeutige aktive Assets. Der kuratierte 325-Asset-Referenzkern wird montags erhoben; die übrigen 1.401 Assets sind deterministisch auf Dienstag bis Freitag verteilt. Vor dem Startdatum, an Wochenenden ohne Rückstand und nach vollständiger Wochenabdeckung bleibt der Prozess ein reiner Auswertungslauf. Eine innerhalb derselben Kalenderwoche verpasste Kohorte wird beim nächsten Termin mit dem tatsächlichen neuen Beobachtungszeitpunkt nachgeholt und niemals rückdatiert.

Neue Prognosezeiträume starten unabhängig voneinander: 1 Woche wöchentlich, 1 Monat alle zwei Wochen, 3 Monate monatlich, 6 Monate alle drei Monate und 12 Monate alle sechs Monate. 6M/12M werden nur bei ausreichender Historie, Datenqualität, Assetqualität und gültigem EUR-Preis angelegt. Bereits gespeicherte Prognosen und offene Auswertungen werden weder gelöscht noch rückwirkend verändert.

Nach jedem Lauf werden zusätzlich Dauer, verarbeitete Assets pro Minute, Fehlerquote, erkannte Yahoo-Rate-Limits und Wachstum der Datenbank ausgegeben und im rotierenden lokalen Laufprotokoll festgehalten. Dadurch kann der erste vollständige Lauf über das kuratierte Universum nachvollziehbar bewertet werden.

Das Laufprotokoll beginnt bereits mit einer Startvorprüfung von Konfiguration, Universum und Datenbankpfad. Vor jeder einzelnen Asset-Analyse wird Ticker, Position im Universum und Versuchszahl protokolliert. Der Windows-Wrapper schreibt zusätzlich Prozessstart, Prozessende und Rückgabecode nach `runtime/logs/forecast_task_wrapper.log`. Dadurch bleibt bei einem harten Windows-Abbruch erkennbar, ob der Wrapper beziehungsweise Python regulär endete und ob der Prozess vor dem Universum oder während eines bestimmten Assets beendet wurde; es werden dabei keine Portfolio- oder Nutzerdaten gespeichert.

Der tägliche Runner besitzt zusätzlich eine betriebssystemweite exklusive Prozesssperre neben der Windows-Einstellung `IgnoreNew`. Auch ein manueller oder anderweitig gestarteter zweiter Prozess wird dadurch vor Datenbank- oder Yahoo-Arbeit mit einer klaren Fehlermeldung beendet. Die Sperre wird vom Betriebssystem automatisch freigegeben, sobald der laufende Prozess regulär endet oder hart beendet wird; eine liegengebliebene Sperrdatei blockiert einen späteren Lauf nicht.

Vor einer neuen Wochenkohorte prüft der Runner außerdem die gemeinsam geladenen Marktbenchmarks. Sind sämtliche Referenzen gleichzeitig nicht verfügbar, wird die Neuprognose vor dem ersten Asset sicher pausiert, nicht als abgeschlossene Kohorte gespeichert und später über Windows-Wiederholung oder das normale Wochen-Nachholen erneut versucht. Ein einzelnes fehlendes Asset oder eine einzelne fehlende Referenz stoppt die übrige Kohorte nicht.

Diese Betriebskennzahlen werden seit Datenbankschema 3 zusätzlich direkt am Lauf gespeichert. Dadurch bleiben Laufzeit, Verarbeitungstempo, Fehlerquote, Rate-Limit-Anzahl, Datenbankwachstum und Integritätsstatus auch nach einem Neustart für die Prognosequalitätsansicht verfügbar.

Datenbankschema 4 kennzeichnet jede automatische Prognose zusätzlich mit ihrer Analyseart. Der bestehende Hintergrundlauf speichert ausschließlich `Einstiegsanalyse`; künftige Long-Term- und Swing-Modelle können dadurch getrennt ausgewertet werden, ohne ihre Trefferquoten zu einer irreführenden Gesamtzahl zu vermischen. Die Prognosequalitätsansicht zeigt und filtert diese Analyseart ausdrücklich. Sobald echte Auswertungen mehrerer Analysearten vorliegen, blendet die App die modellübergreifende Gesamtquote aus und zeigt nur die getrennten Quoten.

Seit Schema 9 speichern neue Prognosen zusätzlich einen L0-Point-in-Time-Vertrag: Beobachtungs-Cutoff, versionierte Feature-/Label-/Benchmark-/Kosten-/Qualitätsregeln, Leakage-Schutz und SHA-256-Fingerabdruck. Vor jedem Hintergrundlauf werden alle neuen Verträge erneut gegen ihren Fingerabdruck geprüft; eine beschädigte oder unvollständige Zeile stoppt den Prozess noch vor Auswertung und Marktabruf. Ältere Prognosen werden nicht rückwirkend ergänzt und bleiben getrennt als Legacy sichtbar. Fällige Kursdaten werden gebündelt abgerufen; Ergebniszeilen enthalten Bewertungstag, Rendite, beste und schlechteste Bewegung sowie Referenzen für `immer steigend`, `keine Änderung`, einen festen 20-Tage-Trend und einen assettyp-/regionsabhängigen Marktbenchmark. Neue Prognosezeiträume speichern außerdem eine ausdrücklich unkalibrierte Rohwahrscheinlichkeit für `Rendite > 0`, abgeleitet aus der zum Beobachtungszeitpunkt gespeicherten Bull-/Base-/Bear-Verteilung und ihren numerischen Zielen. Sobald diese neuen Fälle reifen, berechnet die Qualitätsansicht Brier Score, Log Loss, Kalibrierungsfehler und Bias; bis dahin bleibt die Anzeige ehrlich leer. Hinzu kommen Ergebnisabdeckung, Referenzvorsprung, Rendite, Drawdown, Überschussrendite, Wilson-Unsicherheitsbereich, Precision, Recall, Balanced Accuracy und getrennte Qualitätssegmente.

Nach jedem Hintergrundlauf wird außerdem `runtime/calibration_profile.json` atomar neu erzeugt. Das versionierte Profil fasst ausschließlich echte abgeschlossene Prognoseauswertungen nach Analyseart, Logikversion, Asset-Typ und Zeitraum zusammen. Unter 20 Fällen wird nur gesammelt, zwischen 20 und 50 Fällen gibt es höchstens vorsichtige Prüfhinweise, und ab 51 Fällen sind ausschließlich manuelle Kalibrierungsprüfungen erlaubt. Ein reproduzierbarer Datenfingerabdruck macht den zugrunde liegenden Auswertungsstand nachvollziehbar. Das Profil verändert niemals selbstständig Score-Gewichte oder Produktionsregeln.

Das Profil enthält zusätzlich ein strenges Lern-Gate. Nur gereifte Zeilen mit vollständig verifiziertem Point-in-Time-Vertrag dürfen in einen späteren Lernbestand gelangen; Legacy-Zeilen, offene Ergebnisse, unbrauchbare Labels und beschädigte Fingerabdrücke werden getrennt ausgeschlossen. Ein erster Shadow-Kandidat benötigt mindestens 1.000 Fälle, zwölf Beobachtungswochen, je 200 positive und negative Fälle sowie mindestens 90 Prozent Wahrscheinlichkeitsabdeckung; diese technischen Mindestwerte ersetzen keine spätere Power-Analyse. Die vorbereitete Walk-Forward-Aufteilung ist ausschließlich zeitlich, entfernt überlappende noch nicht bekannte Ergebniszeiträume vor Validierung und Test und erlaubt niemals zufälliges Zeilenmischen. Auch ein bestandenes Lern-Gate aktiviert kein Produktionsmodell automatisch.

Das Profil kann ohne neuen Marktabruf manuell aktualisiert werden mit:

```powershell
.\.venv\Scripts\python.exe scripts\run_forecasts.py --calibration-only
```

Eine sichere Vorprüfung ohne Yahoo-Abfrage und ohne neue Prognosen ist jederzeit möglich mit:

```powershell
.\.venv\Scripts\python.exe scripts\run_forecasts.py --preflight
```

Sie prüft die Konfiguration, Startzeit, Logikversion, Referenz- und Wochenuniversum einschließlich Kohortengrößen und Zuordnungsfingerabdruck, die Schreibbarkeit der lokalen Laufpfade, Schema und Integrität der SQLite-Datenbank sowie jeden vorhandenen neuen Point-in-Time-Messvertrag. Falls eine ältere unterstützte Datenbank vorliegt, dürfen dabei ausschließlich die getesteten, nicht löschenden Schema-Migrationen ausgeführt werden. Das Ergebnis weist ausdrücklich aus, dass keine Marktdaten abgefragt, keine Prognosen angelegt und keine Daten gelöscht wurden.

Unter `Prognosequalität` zeigt die App außerdem einen leicht verständlichen Betriebsstatus: letzter Lauf, verarbeitete Assets, Fehlerzahl und nächster geplanter Lauf. Ein seit mehr als neun Stunden nicht fortgeschriebener Lauf oder ein fehlender erwarteter Lauf wird sichtbar als Problem gemeldet. Beginnt ein neuer Tageslauf, werden ältere noch als `running` markierte Läufe automatisch als unterbrochen dokumentiert; Prognosen oder Historien werden dabei nicht gelöscht.

Ein abgeschlossener Tageslauf wird auch mit `--force` niemals überschrieben. Existiert für denselben Tag bereits ein Lauf mit einer anderen Logikversion, verweigert der Runner die Vermischung ausdrücklich. Dadurch bleiben Prognosezeitpunkt, Modellart und Logikversion nachvollziehbar und unverändert.

Die Datenbank besitzt eine feste Schema-Version. Fehlende ältere Schema-Schritte werden beim Start automatisch und ohne Löschen vorhandener Prognosen nachgeholt. Eine Datenbank aus einer neueren, nicht unterstützten App-Version wird sicher abgelehnt.

Eine rein technische, nicht löschende Prüfung und Optimierung kann manuell gestartet werden:

```powershell
.\.venv\Scripts\python.exe scripts\run_forecasts.py --maintenance-only
```

Nur wenn ungenutzter SQLite-Speicher bewusst zurückgewonnen werden soll:

```powershell
.\.venv\Scripts\python.exe scripts\run_forecasts.py --maintenance-only --compact
```

Auch `--compact` löscht keine Prognosen oder Auswertungen. Eine automatische Aufbewahrungs- oder Löschregel gibt es bewusst nicht.

Eine konsistente, integritätsgeprüfte Sicherung der privaten Prognosedatenbank wird ohne Löschen älterer Sicherungen erstellt mit:

```powershell
.\.venv\Scripts\python.exe scripts\manage_forecast_backups.py backup
```

Sicherungen liegen lokal unter `runtime/backups/` und werden nicht versioniert. `inspect` prüft eine SQLite-Datei nur lesend. `restore-copy` stellt eine Sicherung ausschließlich in eine neue, noch nicht vorhandene Datei wieder her und überschreibt niemals die produktive Datenbank. Der bewusste Austausch der produktiven Datei bleibt deshalb ein manueller Wartungsschritt bei gestopptem Hintergrundlauf.

## Deployment auf Streamlit Community Cloud

Die App ist für Streamlit Community Cloud vorbereitet und kann im Handy-Browser genutzt werden.

1. Repository zu GitHub pushen.
2. Auf [Streamlit Community Cloud](https://share.streamlit.io/) mit GitHub anmelden.
3. **New app** wählen.
4. Repository `investment-assistant` auswählen.
5. Branch `main` auswählen.
6. Main file path: `app.py`.
7. Deploy starten.

Streamlit installiert die Abhängigkeiten automatisch aus `requirements.txt`. Es werden keine Broker-Zugangsdaten, API-Keys oder Passwörter benötigt.

Nach dem Deploy zeigt Streamlit eine öffentliche App-URL an. Diese URL kannst du direkt im Handy-Browser öffnen und als Lesezeichen oder zum Home-Bildschirm hinzufügen. Die App läuft dann über Streamlit Cloud; auf dem Handy muss keine Python-Umgebung installiert werden.

Auf dem Handy gilt:

- Die App analysiert weiterhin nur und handelt nicht automatisch.
- Es gibt keine Broker-Anbindung.
- Wenn `search_history.json` auf Streamlit Cloud fehlt, startet die App trotzdem und beginnt mit leerer Suchhistorie.
- Änderungen an lokalen Laufzeitdateien sind auf Streamlit Cloud nicht als dauerhafte Datensicherung gedacht. Für dauerhaftes Lernen sollten die Historien lokal gesichert oder bewusst exportiert werden.

Für den Depot-Modus darf `portfolio.json` im Repository liegen, solange die Datei nur diese GitHub-kompatiblen Minimaldaten enthält:

- `cash`
- `ticker`
- `asset_type`
- `shares`
- `buy_price`

Nicht in das Repository gehören Kontonummern, Depotnummern, Broker-Zugangsdaten, API-Keys, Passwörter oder persönliche Identifikationsdaten.

Hinweis: Laufzeitdateien wie `search_history.json`, `trade_history.json`, `forward_tests.json`, `decision_history.json`, `prediction_history.json` und `backtest_history.json` sind auf Streamlit Cloud nicht als dauerhaftes Speichersystem gedacht. Sie bleiben lokale Analysehilfen und lösen niemals eine Order aus.

Diese Historien dürfen keine Broker-Zugangsdaten, API-Keys, Passwörter, Kontonummern oder persönlichen Identifikationsdaten enthalten. `trade_history.json` speichert nur vorgeschlagene Setups und spätere Auswertungen; `forward_tests.json`, `decision_history.json`, `prediction_history.json` und `backtest_history.json` speichern nur Analyse-, Entscheidungs- und Testergebnisse. Die Dateien sind in `.gitignore` eingetragen und sollen nicht versehentlich veröffentlicht werden.

Lokale JSON-Historien werden atomar gespeichert: Die neue Datei wird zuerst vollständig als temporäre Datei geschrieben und ersetzt erst danach den alten Stand. Scheitert dieser letzte Austausch, bleibt die bisherige Historie erhalten. Alte Hüllen wie `records`, `history` oder `entries` werden beim Lesen weiterhin defensiv akzeptiert. Gleichzeitige Schreibzugriffe mehrerer Prozesse werden jedoch nicht zusammengeführt.

## Asset-Suche

Du kannst entweder einen Namen oder direkt einen Yahoo-Finance-Ticker eingeben.

Beispiele für Namen:

- Xiaomi
- Nvidia
- Palantir
- Bitcoin
- MSCI World

Beispiele für Ticker:

- `NVDA`
- `PLTR`
- `BTC-EUR`
- `1810.HK`
- `EUNL.DE`

Die App sucht passende Yahoo-Finance-Treffer und zeigt Name, Ticker und Börse an. Wenn kein Treffer gefunden wird, kannst du weiterhin manuell einen Ticker eintragen. Erfolgreiche Suchen werden lokal in `search_history.json` gespeichert.

## Währungsanzeige

Die Analyse rechnet intern weiter mit den Originalkursen von Yahoo Finance. Dadurch bleiben RSI, MACD, Unterstützungen, Widerstände und CRV unverzerrt.

Für die Anzeige werden Kurse, Unterstützungen, Widerstände und der Hauptchart standardmäßig in EUR angezeigt. Wenn ein Asset in USD, HKD oder einer anderen Währung gehandelt wird, zeigt die App zusätzlich die Originalwährung und den verwendeten Wechselkurs.

In der Sidebar kannst du wählen:

- `EUR + Originalwährung`
- `Nur EUR`

Wenn kein Wechselkurs geladen werden kann, zeigt die App ehrlich an, dass die EUR-Umrechnung nicht verfügbar ist.

## Chart-Zeitraum und Analyse-Zeitraum

Der in der Sidebar gewählte Zeitraum steuert nur den sichtbaren Chart. Die eigentliche Analyse lädt unabhängig davon die maximal verfügbare Tageshistorie von Yahoo Finance.

Dadurch werden 50er- und 200er-Durchschnitt, Marktphase, Trend, Unterstützungen, Widerstände, Datenqualität und Research-Scores nicht schlechter, nur weil im Chart z. B. ein kurzer Zeitraum gewählt wurde.

Im Datenqualitätsbereich zeigt die App getrennt:

- Chart-Historie
- Analyse-Historie

Warnungen wie **Weniger als 200 Handelstage vorhanden** oder **200er-Durchschnitt nicht berechenbar** erscheinen nur, wenn die Analyse-Datenquelle wirklich nicht genug Historie liefert.

## Research-Modul

Das Research-Modul ist wie eine kompakte Equity-Research-Ansicht aufgebaut. Es verändert nicht automatisch Depotdaten, Asset-Qualität oder Kaufsignal, sondern zeigt zusätzliche Analyseblöcke.

Enthalten sind:

- Datenqualitäts-Check: Ticker, Asset-Typ, Börse, Währung, Kursdaten, Volumen, 200 Handelstage sowie 50er/200er-Durchschnitt
- Charttechnik-Score
- Momentum-Score
- Bewertungsscore oder bei Krypto Zyklus-/On-Chain-Score; bei Aktien werden KGV, Forward-KGV, Forward-KGV-Abstand, PEG, KUV, EV/Umsatz, EV/EBIT-Näherung, EV/FCF, Kurs/Buchwert, Free-Cashflow-Rendite, Wachstum, Margen, Verschuldung, Sektor-/Branchenkontext, historische Bewertung und Peer-Vergleich getrennt ausgewiesen. Fehlende Historien- oder Peer-Daten bleiben ausdrücklich `Daten nicht verfügbar`.
- Fundamentaldaten-Score oder bei Krypto Netzwerk-/Adoptionsscore
- Zukunftspotenzial: Wachstum, Margen, Qualität und verfügbares Sentiment, ohne fehlende Daten zu erfinden
- Eingepreiste Erwartungen: Bewertungsniveau, Momentum, News-/Analysten-Euphorie, IPO-/KI-Hype, Zuflüsse und Sentiment; hoher Wert bedeutet, dass bereits viel Optimismus im Kurs stecken kann
- Innovation / Hype: Hinweise auf Wachstum, Margen, Cashflow, Marktstellung, Technologiebezug und Hype-Risiko
- Blasenrisiko: Bewertung, Momentum, 3M-Kursanstieg, Volatilität und News-Sentiment; hoher Wert ist ein Warnsignal
- Expected Value: Bull-/Base-/Bear-Case, Wahrscheinlichkeiten, erwartete Rendite, erwarteter Verlustbeitrag und Expected-Value-Score
- Makro-Score: zeigt Datenabdeckung und Score-Neutralität; nutzt Nasdaq/Risikoappetit, US-Zinsen, Dollar-/Liquiditätsdruck und TIP als Inflations-/Realzinsproxy, sofern Yahoo-Daten verfügbar sind. Direkte Liquiditätsdaten werden ohne belastbare Quelle als `Daten nicht verfügbar` angezeigt.
- Marktregime mit Hinweisen, Gegenargumenten, Unsicherheiten, betroffenen Asset-Klassen und Vertrauensgrad
- Makro-Wirkung: Zinsen, Dollar, Risikoappetit und Inflations-/Realzinsproxy mit praktischer Wirkung auf Aktien, ETFs, Krypto und Rohstoffe
- Geopolitik-Score: nutzt nur verfügbare Yahoo-News-Titel als Hinweisquelle für Sanktionen, Zölle, Krieg, Lieferketten- oder Exportkontrollrisiken. Wenn keine belastbaren News vorliegen, steht `Daten nicht verfügbar`; fehlende Treffer sind keine vollständige Entwarnung.
- Rohstoff-Kontext: Öl, Gas, Kupfer, Gold und Uran-Proxy als Konjunktur-, Inflations-, Sicherheits- und Energiesignale, sofern Yahoo-Daten verfügbar sind
- Krypto-Zyklus: nur bei Krypto-Assets, mit Datenabdeckung, Bitcoin-Halving-Einordnung, Zyklusfortschritt, praktischer Anlegerbedeutung, Krypto-Volatilität, Volumen-/Liquiditätsvergleich und Marktstruktur über 50er/200er-Durchschnitt. Der Halving-Zyklus wird ausdrücklich als Kontextsignal und nicht als Kaufsignal erklärt. ETF-Flows, Fear & Greed, On-Chain-Daten, Orderbuch, Spread und Stablecoin-Liquidität bleiben `Daten nicht verfügbar`, wenn keine belastbare Quelle eingebunden ist.
- Institutionelle Research-Module: Analysten-Konsens, Earnings, Event-Risiko und institutionelle Daten zeigen Datenabdeckung und Score-Neutralität. Fehlende Analysten-, Earnings-, Event-, Insider-, Short-Interest- oder ETF-Flow-Daten werden nicht geschätzt.
- News-Score: zeigt Quelle, Datum, Relevanz und einfache Sentiment-Qualität je Nachricht; fehlende oder unklare News-Daten werden neutral behandelt und nicht erfunden.
- Risiko-Score: zeigt Datenabdeckung, Score-Neutralität, Asset-Typ-abhängige Volatilität, Risiko bis Unterstützung, Potenzial bis Widerstand und CRV-Einordnung.
- Liquiditäts-Score: zeigt Datenabdeckung, relatives Volumen zum 20er-Schnitt, Yahoo-Durchschnittsvolumen, 10T-Durchschnittsvolumen und fehlende Spread-/Orderbuchdaten transparent.
- Bull-/Base-/Bear-Szenarien mit Wahrscheinlichkeiten, die zusammen 100 % ergeben; Trend, Volatilität, Unterstützungen, Widerstände und CRV werden als Treiber ausgewiesen
- Nachkaufzonen: aggressiv, fair, sicher und ungültig bei Bruch der Unterstützung; fehlende Unterstützungen oder Widerstände werden als nicht berechenbar angezeigt
- Research-Fazit: was für Kauf spricht, was dagegen spricht, was die Analyse verbessern würde, welche Marke entscheidend ist und ein konkreter Plan
- Professionelle Kauf-/Nichtkauf-Entscheidung: trennt Asset-Qualität, Zukunftspotenzial, Bewertung, eingepreiste Erwartungen, Blasenrisiko, technischen Einstieg, Expected Value und Gesamtfazit. Bei vorsichtigen oder negativen Empfehlungen werden Hauptgrund und Nicht-Hauptgrund angezeigt.
- Analysten-Konsens, sofern Yahoo-Finance-Daten verfügbar sind
- Earnings-Modul für Aktien, sofern Quartalsdaten verfügbar sind
- Event-Risiko-Modul für bekannte oder verfügbare Ereignisdaten
- Institutionelle Daten wie Beteiligungen und Short Interest, sofern verfügbar
- Vertrauensscore zur Einschätzung, wie belastbar die Analyse aktuell ist
- Confidence-System für ähnliche historische Setups: zählt ausgewertete Fälle aus Trade-Journal, Forward-Tests, Decision-Tracking und Prognosen, zeigt Trefferquote erst ab mindestens 20 ähnlichen Fällen und ändert Gewichtungen niemals automatisch
- Unsicherheitsfaktoren: Was könnte diese Analyse widerlegen?

Wenn Daten fehlen, zeigt die App **Daten nicht verfügbar** oder **Datenqualität eingeschränkt**. Fehlende Kennzahlen werden nicht erfunden.

## Qualitätsmessung und automatischer Swing Trade Finder

Die ROADMAP sieht zusätzliche Module vor, die nicht nur neue Features liefern sollen, sondern die Analysequalität messbar machen:

- Swing Trade Finder: Der bewusst gestartete Scan lädt das intern gepflegte, versionierte Universum aus `config/swing_universe.csv`. Es enthält 2.520 aktive liquide Assets einschließlich ServiceNow: 2.431 Aktien, 59 ETFs und 30 große Kryptowährungen. Das breite Projektuniversum wird durch reguläre Aktien des offiziellen Nasdaq Global Select Market ergänzt. Penny Stocks, Hebelprodukte und inverse ETFs sind ausgeschlossen; ungültige Zeilen werden protokolliert und nicht still entfernt.
- Mehrstufiger Scan: Alle Assets durchlaufen einen binären Daten-, Volumenabdeckungs-, assettypischen Volatilitäts-, Trend- und ATR-normalisierten Strukturfilter. Absolute Stückzahlen sind kein klassenübergreifendes Liquiditäts-Hard-Gate; die tatsächliche Handelbarkeit wird erst in der Tiefenanalyse über den durchschnittlichen EUR-Umsatz geprüft. Jeder bestandene Kandidat erhält die vollständige Long-Swing-Prüfung für `Rücksetzer im intakten Aufwärtstrend` oder `Bestätigter Ausbruch`; es gibt keine feste 60er- oder andere Top-N-Grenze. Der Funnel misst Universum, geladene Daten, jeden Grob- und Finalfilter, Tiefenprüfung, Setup und Portfoliofreigabe getrennt für Aktien, ETFs und Krypto. Erfüllt nichts sämtliche Mindestregeln, erscheint bewusst `Aktuell kein hochwertiger Trade vorhanden.`
- Neutrale ETF-/Aktien-Auswahl: Feste Prozentzonen, die bei ruhigeren ETFs zu weit waren, werden relativ zur eigenen ATR begrenzt. Langfristige Asset-Qualität bleibt sichtbar, sperrt und priorisiert kurzfristige Swing-Setups aber nicht. Es gibt weder Aktienbonus noch ETF-Quote. Im nicht gespeicherten Nachher-Reallauf lagen die Grobfilterquoten bei 13,87 % für Aktien und 14,00 % für ETFs; echte Ergebniskennzahlen der neutralisierten Strategieversion werden erst ab mindestens 20 eindeutig ausgewerteten Forward-Fällen je Klasse verglichen.
- Trade-Republic-Ausrichtung: Der normale Nutzerbereich zeigt nur Signale, deren konkretes Analyse- und TR-Listing dauerhaft über Ticker, Börsenplatz, Währung und übereinstimmende ISIN verifiziert wurde. `TR nicht handelbar` und `unbekannt` bleiben vollständig als Paper-/Forward-Signale erhalten und erscheinen getrennt unter `Nur Paper / nicht bei Trade Republic handelbar`. Die lokale Zuordnung ist append-only; eine manuelle ISIN-Markierung ist möglich, wenn Metadaten fehlen.
- Strikte Kurstrennung: `Aktueller Preis` und sämtliche ausführbaren EUR-Marken stammen nur aus einem höchstens 15 Minuten alten, manuell für das verknüpfte TR-Listing erfassten Preis. Zusätzlich ist ein zeitgleich erfasster Vergleichskurs des analysierten Listings erforderlich, damit nur die Listing-Basis übertragen wird und ältere technische Marken nicht am aktuellen TR-Preis neu verankert werden. Fehlt einer der beiden Kurse, steht ausdrücklich `TR-Preis nicht verfügbar` beziehungsweise kein ausführbarer Plan; Yahoo wird niemals als TR-Ersatz ausgegeben. Yahoo-/andere Marktdaten bleiben ausschließlich Grundlage für Chart, technische Relationen und objektiven Forward-Test. Es gibt keine Broker-Anbindung und keine automatische Order.
- Risikomodell: Im Hauptbereich ist nur das verfügbare Tradingkapital einzugeben. Das zentrale, nur lesbare Modell begrenzt das rechnerische Risiko auf 0,50 % je Trade, 2,00 % offenes Gesamtrisiko, 50 % Gesamtbelastung und 20 % je Position. Eine feste Höchstzahl gleichzeitiger Trades existiert nicht mehr; das verbleibende Risiko- und Kapitalbudget bestimmt die dynamische Anzahl. Der Stop wird aus Struktur und Volatilität abgeleitet; zu große Abstände werden abgelehnt. Aus Einstieg und Stop entstehen automatisch Stückzahl, investierter Betrag, geplanter Verlust und mögliche Gewinne an Ziel 1/2. Ohne Kapital wird keine Stückzahl erfunden; Kurslücken können den tatsächlichen Verlust erhöhen.
- Order- und Stop-Vertrag: Jede Freigabe erhält einen versionierten fingerprinteten Plan mit abgeschlossener Signalkerze, Einstiegsmethode, frühestem Folgetag, Limit/Aktivierung/Maximalpreis, initialem Stop, Zielen, Gültigkeit, Löschbedingungen und finalen Positionswerten. Bei zwei Zielen gilt ein fester 50/50-Plan: Teilgewinn an Ziel 1, Rest an Ziel 2 oder späterem Stop; mögliche Gewinne werden entsprechend teilweise beziehungsweise kumuliert gezeigt. Es gibt keinen rückwirkenden Einstieg zum bestätigenden Schlusskurs. Der initiale Stop bleibt gespeichert; bei einem aktiven Long-Trade darf er nur enger und niemals weiter gesetzt werden. Die App sendet weiterhin keine Order.
- Risikohinweis: Vor der ersten Nutzung muss einmalig ein klarer Verlusthinweis bestätigt werden. Die Bestätigung wird ausschließlich lokal unter `runtime/` gespeichert.
- Trade Journal: Freigegebene Signale werden beim Scannerlauf automatisch als lokale Paper-Trades in `trade_history.json` dokumentiert und dedupliziert. Setup-Ablauf und Paper-Statistiken bleiben auswertbar. Es wird keine Order ausgeführt und keine Broker-Verbindung genutzt.
- Unveränderbarer Swing-Forward-Test: Echte manuelle und regionale Hintergrundscans werden getrennt unter `runtime/swing_forward.sqlite3` gespeichert. Scans einschließlich Null-Trade-Ergebnis, Signalsnapshots und spätere Ereignisse sind append-only und fingerprintet; die Datenbank sperrt Änderungen und Löschungen. Die automatische Auswertung nutzt nur vollständige spätere Balken, konservative Kosten und eigene Statuswerte für Gap, Verpassung, Ungültigkeit, Ablauf, Stop, Ziele, unklare Reihenfolge und fehlende Daten. Bei zwei Zielen werden Ziel 1 und Ziel 2/Stop als 50/50-Ausstiegsbeine aggregiert. Historische Ein- und Ausstiegswechselkurse werden je Teilereignis ohne Zukunftskurse als eigenes append-only Bewertungsereignis ergänzt; fehlen sie vorübergehend, kann ausschließlich diese Zusatzbewertung später nachgeholt werden.
- Shadow- und Kontrollsignale: Jeder fachlich vollständig freigegebene Setup-Plan wird als Forward-Signal gespeichert, auch wenn ihn das dynamische Gesamt-Risiko-, Expositions- oder Positionsbudget aus der Nutzerfreigabe zurückhält. Diese Fälle tragen eine eigene Evidenzart und werden getrennt von den tatsächlich für das Nutzerportfolio freigegebenen Signalen ausgewertet. Verpasste, vor Einstieg ungültige oder abgelaufene Signale erhalten nach 5 und 20 weiteren abgeschlossenen Sitzungen eine separate Kontrollrendite. Sie bleibt ausdrücklich `kein Trade-Ergebnis` und verändert niemals die Trefferquote.
- Ablehnungs-Kontrollgruppe: Aus den in der Tiefenanalyse abgelehnten Kandidaten werden je Scan bis zu fünf Fälle anhand eines stabilen SHA-256-Samplings reproduzierbar ausgewählt. Ausgangskurs, Marktphase, Datenqualität und Ablehnungsfilter werden append-only gespeichert; nach 5 und 20 Sitzungen folgen Rendite und MFE/MAE als reine Kontrollmessung. Diese Fälle besitzen keinen Orderplan, sind keine Signale und zählen niemals als Trade oder Lernfreigabe.
- Laufende aktive Messung: Aktive Papertrades speichern neben MFE/MAE nun auch aktuellen kostenbereinigten Zwischenstand in Prozent und R sowie Abstand zu Stop und nächstem Ziel. Marktphase, Volatilitätsregime, Evidenzart und Portfoliofreigabe sind im Archiv und in den Segmenten getrennt sichtbar.
- Gleichzeitige Risikocluster: Qualifizierte Kandidaten werden rein beobachtend nach Branche, Region und 60-Sitzungs-Korrelation geprüft. Stark gleichlaufende Paare und Branchenhäufungen werden angezeigt; es gibt keine heimliche Ablehnung oder Gewichtsänderung.
- Historischer Swing-Walk-Forward-Forschungsbetrieb: `scripts/run_swing_walk_forward.py` verwendet ohne Tickerangabe das vollständige aktive 2.520-Asset-Universum, lädt split-/dividendenbereinigte Tagesdaten in parallelen Batches, hält einen lokalen Parquet-Cache für schnelle Fortsetzung und isoliert einzelne Providerfehler. Indikatoren werden je Asset nur einmal kausal berechnet. Die begrenzten Fälle je Asset werden deterministisch über Kalenderjahre sowie feste Development-, Validation- und Holdout-Fenster verteilt; über die Fenstergrenze ragende Ergebniszeiträume und überlappende Fälle desselben Assets werden nicht als unabhängige Labels gezählt. Eine stabile logische Fall-ID und ein Fingerabdruck genau der bis zum Ergebnis verwendeten OHLCV-Daten halten korrigierte Providerdaten append-only als neue Revision fest, während Kennzahlen nur die neueste Revision desselben Falls zählen. Die globale Fallgrenze wird deterministisch über Strategien und Assets verteilt statt durch alphabetisch frühe Ticker belegt. Ergebnisse, vollständige Datenfingerabdrücke, Kosten, R, Profitfaktor, Drawdown, Wilson-Intervall, Marktphasen und versionierte Research-Profile liegen append-only in `runtime/swing_walk_forward.sqlite3`. Die Oberfläche zeigt Strategie- und Einzelfälle getrennt. Historische Fundamental-, News-, Makro- und TR-Ausführungsdaten fehlen weiterhin; daher dürfen diese Daten nur technische Shadow-Challenger begründen und werden niemals der echten Forward-Trefferquote zugeschlagen oder automatisch aktiviert. Beispiel: `python scripts/run_swing_walk_forward.py NVDA MSFT AAPL --step-sessions 5 --future-sessions 25`.
- Rotierende Swing-Forschungskampagne: `scripts/run_swing_walk_forward_campaign.py` verarbeitet die vier vorab festgelegten Schwellenprofile `current`, `balanced`, `precision` und `payoff` in acht diversifizierten Asset-Shards. Die festen historischen Tests sind vorab als drei abhängige Runden A, B und C registriert. Jede Runde nimmt je Asset und Strategie höchstens sechs nicht überlappende Fälle aus 2010–2015 und sechs aus 2016 bis heute, somit höchstens zwölf neue Fälle über den Gesamtzeitraum und höchstens 36 nach allen drei Runden. Runde B beginnt erst nach vollständiger Runde A, Runde C erst nach vollständiger Runde B. Frühere rundenberechtigte Signale werden deterministisch rekonstruiert und reserviert; Ergebnisse oder spätere Renditen beeinflussen die Datumsauswahl nicht. Die Profilversionen sind vor Kampagnenstart eingefroren, sodass eine zwischenzeitliche Regeländerung sichtbar abbricht statt Testreihen zu vermischen. Wöchentliche `recent_incremental`-Läufe bleiben eine getrennte aktuelle Ergänzung. Stabile Evidenz-IDs verhindern Doppelzählungen; der atomare Status setzt nach Unterbrechungen fort und rotiert fehlgeschlagene Jobs innerhalb der jeweils freigegebenen Stufe.
- Historisch/echte Forward-Verknüpfung: Die Forschungsdatenbank besitzt eine eigene append-only Cross-Store-Tabelle. Nach jedem historischen Kampagnenjob und nach jedem echten Hintergrundscan werden Asset/Listing, Signalkerzentag, Setup, Richtung und ein auf Originalwährung reduzierter Ausführungsplan verglichen. Bei exakt demselben Trade hat die tatsächlich vorher gespeicherte Forward-Evidenz Vorrang; die historische Rekonstruktion wird nicht nochmals im jüngsten Monitoring gezählt. Gleicher Asset-Tag mit anderer Strategie oder anderem Plan bleibt als verwandtes, aber eigenständiges Experiment erhalten. Beide Quelldatenbanken bleiben unverändert, historische Fälle werden nie als echte Forward-Fälle umgedeutet.
- Swing-Lern-Gate: Eine manuelle fachliche Regelprüfung benötigt standardmäßig mindestens 100 eindeutige echte Forward-Ergebnisse, zwölf Beobachtungswochen und jeweils mindestens 20 Fälle in vorhandenen Asset-, Marktphasen-, Volatilitäts- und Versionssegmenten. Auch danach werden Regeln oder Gewichte niemals automatisch geändert; historische Walk-Forward-Fälle zählen nicht zu diesem Gate.
- Bedienungsfreier Swing-Betrieb: Asien/Australien läuft um 10:30 Uhr und Europa um 18:15 Uhr. Um 22:30 Uhr startet eine feste Abendkette: zuerst Prognosen, danach Amerika/Global und danach Krypto. Der breite historische Basislauf läuft zusätzlich samstags um 11:00 Uhr. Die rotierende Forschungskampagne prüft tagsüber zwischen 11:05 und 22:05 Uhr im 15-Minuten-Raster, ob der nächste offene 1/8-Shard gestartet werden kann; ein laufender Shard blockiert alle Folgestarts. 17:15–18:45 Uhr sowie 21:30–23:59 Uhr sind zum Schutz der realen Scans und Prognosen gesperrt. Weil ein gebündelter Shard bis zu 90 Minuten benötigen darf, startet außerdem bereits in den 90 Minuten vor einem Schutzfenster kein neuer Forschungsjob. Beide Forschungswege teilen eine Betriebssperre, nutzen Cache/Wiederanlauf/Aufwecken und verändern keine Produktionsregel. Zwischen 00:00 und 10:00 Uhr bestehen weiterhin keine regulären Forschungsstarts. Es werden niemals Orders ausgeführt.
- Ehrliches Swing-Archiv: Eindeutige Paper-Ergebnisse werden in Trefferquote, Ergebnis in R, Profitfaktor und Drawdown sowie nach Setup, Einstiegsmethode, Asset-Typ, Region, Datenqualität und Version getrennt. Filter, unveränderbarer Systemplan, Ereignisverlauf, Segmenttabelle und scanübergreifende technische Asset-Fehler sind in den erweiterten Einblicken verfügbar. Offene, verpasste, abgelaufene, unklare und nicht auswertbare Fälle zählen nicht als Verluste. Unter 20 eindeutigen Fällen bleibt die Trefferwahrscheinlichkeit nicht belastbar.
- Getrennte TR-Statistik: Scannerqualität wird weiterhin über alle objektiven Signale gemessen. Zusätzlich weist die Oberfläche separat aus, wie viele Listings als `TR handelbar` verifiziert sind und für wie viele davon im jeweiligen Moment ein vollständiger Plan mit frischem TR-Preis vorliegt. Paper-only-Fälle verbessern oder verschlechtern dadurch nicht still die Statistik tatsächlich ausführbarer Nutzertrades.
- Doppelte Wochenendsignale werden verhindert: Die Signalidentität gehört zur abgeschlossenen Signalkerze und zur Logikversion, nicht zum späteren Scanzeitpunkt. Mehrere Scans derselben Freitagskerze erzeugen daher keine künstlich mehrfachen Forward-Fälle.
- Persönliche Nutzertrades: `Trade getätigt` bestätigt nur einen bereits selbst beim Broker ausgeführten Einstieg. Der persönliche Trade wird in `runtime/swing_user_trades.sqlite3` getrennt vom objektiven Paper-Signal append-only gespeichert. Ein Einstieg am oder vor dem gespeicherten Signalzeitpunkt ist als unzulässige Zeitreise technisch gesperrt; andere Abweichungen von Handelstag, Maximalpreis oder Stückzahl benötigen eine ausdrückliche Bestätigung. Stop-Nachzug ist nur enger möglich; Teilverkauf und Abschluss werden als neue Ereignisse angehängt. Die aktive Ansicht prüft Stop/Ziele sowie abgeschlossene Tagesstruktur, 20-Tage-Unterstützung, Trend, Gap und relatives Verkaufsvolumen. Noch nicht belastbar verfügbare Nachrichten-, Ereignis- und Branchenfaktoren werden ausdrücklich benannt. Die App sendet niemals eine Order.
- Performance Tracking: Gespeicherte Trading-Setups können nach 1 Woche, 1 Monat, 3 Monaten, 6 Monaten und 12 Monaten mit echten Kursdaten überprüft werden. Erfasst werden Treffer/Fehlschlag, Rendite, maximale positive Entwicklung, maximale negative Entwicklung, Ziel- und Stop-Berührung, beste Alternative, Opportunitätskosten, Historienkontext aus ähnlichen Setups sowie der ursprüngliche Kalibrierungskontext.
- Forward-Testing: Eine angezeigte Analyse wird für die spätere Auswertung automatisch einmal pro Symbol/Empfehlung/Tag lokal in `forward_tests.json` vorgemerkt und kann zusätzlich manuell gespeichert werden. Fällige Tests können in der Sidebar ausgewertet werden; gespeichert werden Rendite, maximale positive und negative Entwicklung sowie eine einfache Szenario-Lesart. Modul-Scores und Szenario-Lesarten fließen in die lokale Signalanalyse ein, ändern aber keine Gewichtungen automatisch. Die Datei wird nicht versioniert und löst niemals eine Order aus.
- Decision-Tracking: Nutzerentscheidungen wie gekauft, gehalten, verkauft oder beobachtet können optional mit Kommentar lokal in `decision_history.json` protokolliert und später gegen Long, Short und Beobachten verglichen werden. Die Auswertung speichert außerdem, ob die Entscheidung mit der App-Einschätzung übereinstimmte, welche Alternative besser gewesen wäre und welche Opportunitätskosten entstanden sind. Es wird keine Order ausgeführt.
- Prognose-Tracking: Bull/Base/Bear-Szenarien, Kursziele, Wahrscheinlichkeiten, entscheidende Marken und Research-Modul-Scores können lokal in `prediction_history.json` gespeichert werden. Fällige Prognosen können in der Sidebar nach 1 Woche, 1 Monat, 3 Monaten, 6 Monaten und 12 Monaten mit echten Kursdaten ausgewertet werden; danach zeigt die App Trefferquoten nach Asset-Typ, Szenario-Lesart, Modul-/Signalgruppen und möglichen Fehlursachen, aber erst ab ausreichender Datenbasis belastbar.
- Confidence-System: Chancen werden zusätzlich mit ähnlichen lokalen historischen Fällen eingeordnet. Unter 20 ausgewerteten Fällen zeigt die App bewusst `Datenbasis zu klein`; danach werden Trefferquoten ähnlicher Setups nur als Kontext angezeigt und verändern keine Scores automatisch. Zusätzlich zeigt die ähnliche-Setup-Auswertung den häufigsten Review-Kontext wie Szenario-Lesart, Fehlursache, Decision-Alignment, Historienstatus und Kalibrierungskontext, falls diese Felder in den lokalen Historien vorhanden sind.
- Sicheres künftiges Modellregister: Ein später trainierter Challenger kann nur als unveränderbarer `shadow_only`-Kandidat registriert werden. Dataset-, Walk-Forward-, Trainingscode- und Artefakt-Fingerabdrücke sind Pflicht. Ungesehene Fenster, Mindestfälle/-wochen, Brier-/Log-Loss-Vorteil, Drawdown, Segmentbreite, manuelle Prüfung, Canary und Rollback werden getrennt append-only dokumentiert. Auch vollständig bestandene Gates führen niemals automatisch zur Produktionsaktivierung.
- Signalbasierte Kalibrierung: Neue gespeicherte Analysen enthalten eine `signal_snapshot` mit RSI-, MACD-, Volatilitäts-, CRV-, News- und Makro-Einordnung. Ähnliche Setups werden nach diesen Signalen aufgeschlüsselt, fehlende historische Signalwerte bleiben `Daten nicht verfügbar`.
- Backtesting-Basis: Im Analyse-Detailbereich testet die App historische Signal-Kombinationen aus Kaufsignal, RSI, MACD und CRV gegen spätere Kursentwicklungen für 1, 3, 6 und 12 Monate. Eine Kompaktansicht zeigt die beste Trefferquote, die schwächste Rendite, den größten Drawdown, die größte Datenbasis und den Historienstatus; die Detailtabelle zeigt zusätzlich Asset-Typ, damalige Marktphase, maximalen Drawdown, Confidence-Kontext und Lernhinweis je Gruppe und kann lokal in `backtest_history.json` gespeichert werden. Das ist ein Signaltest, keine Strategieoptimierung und keine automatische Kauf-/Verkaufsfunktion.
- Kalibrierungs- und Lernmodul: Häufige Fehlprognosen sollen zeigen, welche Module verbessert werden müssen.

Diese Module dürfen keine Käufe oder Verkäufe ausführen. Sie dienen nur dazu, Chancen zu finden, Vorschläge zu dokumentieren, Trefferquoten zu messen, Fehlerquellen zu erkennen und Verbesserungsbedarf transparent zu machen.

Für das Lernsystem gilt:

- Unter 20 Fällen wird die Datenbasis als zu klein angezeigt.
- Zwischen 20 und 50 Fällen sind nur vorsichtige Hinweise erlaubt.
- Ab über 50 Fällen dürfen Kalibrierungsvorschläge angezeigt werden.
- Gewichtungen werden in Version 1 nicht automatisch geändert.
- Jeder Vorschlag muss Datenbasis, Anzahl Fälle, Trefferquote und Begründung nennen.

## Dynamische Entwicklungsprioritäten

Wenn später `Arbeite weiter` geschrieben wird, soll nicht starr die erste Aufgabe aus der ROADMAP bearbeitet werden. Stattdessen wird bewertet, welche offene Aufgabe den größten Nutzen für Analysequalität, Stabilität und Lernfähigkeit hat.

Priorität haben:

- PRIO A: Grundfähigkeit der Analyse, z. B. Datenqualität, Fehlerbehandlung, Bewertungslogik, Marktphasen, Wahrscheinlichkeiten, Fundamentaldaten, Krypto, Makro, News und Risikoanalyse
- PRIO B: Messung der Analysequalität, z. B. Opportunity Scanner, Trading-Modus, Trade Journal, Performance Tracking, Forward-Testing, Decision-Tracking, Prognose-Tracking, Confidence-System, Trefferquote, Kalibrierung und Lernmodul
- PRIO C: Architektur und Wartbarkeit, z. B. Refactoring, Modularisierung, Performance, Dokumentation und Testbarkeit
- PRIO D: Komfortfunktionen, z. B. Favoriten, Watchlists, Exporte oder reine UI-Verschönerungen

Komfortfunktionen dürfen nicht vor Analysequalität bearbeitet werden. Wenn Prioritäten geändert werden, muss die Begründung in `ROADMAP.md` dokumentiert werden.

## Die drei Scores

### Asset-Qualität

Bewertet nur die langfristige Qualität des Assets.

- Bei Aktien: Umsatz, Gewinn, Free Cashflow, Verschuldung, Margen, Kapitalrendite, Bewertung, Kurs-Umsatz-Verhältnis und Marktstellung, soweit verfügbar
- Bei ETFs: Diversifikation, TER/Kostenquote, Fondsvolumen, Region/Sektor, Performance und langfristige Stabilität aus realer Volatilität, soweit verfügbar
- Bei Krypto: Marktstellung, Liquidität, Volatilität und verfügbare Langfristdaten

Wenn Daten fehlen, zeigt die App **Daten nicht verfügbar** und erfindet keine Werte.

### Kaufsignal

Bewertet nur, ob **jetzt** ein guter Einstiegszeitpunkt sein könnte.

Einflussfaktoren:

- Marktphase
- Trend
- RSI
- MACD
- Volumen
- Unterstützungen
- Widerstände
- Chancen-Risiko-Verhältnis
- Volatilität

Portfolio-Daten verändern das Kaufsignal nicht. Asset-Qualität verändert das Kaufsignal ebenfalls nicht. Das Kaufsignal bewertet nur den aktuellen Einstiegszeitpunkt; MACD und Volatilität werden dabei je nach Asset-Typ eingeordnet, weil ein ETF, eine Aktie und Krypto unterschiedliche Schwankungsprofile haben.

### Gewichtungen

Die App zeigt die Gewichtungen im Bereich **Analyse-Details anzeigen**. Je nach Asset-Typ werden die Research-Bausteine unterschiedlich gewichtet:

- Aktie: Technik 30 %, Fundamentaldaten 30 %, Makro 20 %, News 10 %, CRV 10 %
- ETF: Technik 25 %, Fundamentaldaten 25 %, Makro 25 %, News 10 %, CRV 15 %
- Krypto: Technik 40 %, Fundamentaldaten/Krypto-Adoption 5 %, Makro 25 %, News 15 %, CRV 15 %
- Unbekannt: Technik 45 %, Fundamentaldaten 5 %, Makro 25 %, News 10 %, CRV 15 %

Das **Kaufsignal** bleibt separat: Es nutzt vor allem den Technik-Score, das CRV und begrenzte Zu- oder Abschläge für Marktphase, RSI und Volatilität.

### Research-Score-Einordnung

Die Research-Tabellen übersetzen jeden Score zusätzlich in einfache Bänder:

- `stark`: Der Baustein unterstützt die Analyse klar.
- `konstruktiv`: Der Baustein spricht eher für das Investment, braucht aber Bestätigung.
- `gemischt`: Der Baustein ist uneindeutig und sollte nicht allein entscheidend sein.
- `schwach`: Der Baustein bremst die Analyse und spricht für Vorsicht.
- `kritisch`: Der Baustein erhöht das Risiko deutlich.
- `Daten nicht verfügbar`: Es fehlen belastbare Daten; die App erfindet keine Werte.

### Kalibrierung

Die App zeigt im Bereich **Analyse-Details anzeigen** zusätzlich **Lernlogik-Guardrails**. Dieser Block trennt dokumentierte Fälle von tatsächlich ausgewerteten Fällen und zeigt klar, ab wann nur gezählt, vorsichtig hingewiesen oder manuell kalibriert werden darf. Direkt darunter fasst die App Kalibrierungskontexte aus Performance-Reviews einfach zusammen: Fallzahl, Fehlquote, Durchschnittsrendite und praktische Bedeutung. In Version 1 werden Gewichtungen nicht automatisch geändert.

Zusätzlich prüft die App die **Datenqualität lokaler Lernhistorien**. Dabei werden Trade Journal, Forward-Tests, Entscheidungen, Prognosen und gespeicherte Backtests darauf geprüft, ob sie lesbare Review-Strukturen und verwertbare Auswertungen enthalten. Defekte oder alte Einträge werden nicht geschätzt, sondern als eingeschränkt gekennzeichnet.
Die Tabelle zeigt außerdem einen Reparaturhinweis. Die App löscht oder verändert lokale Historien nicht automatisch; Bereinigung bleibt manuell.

Diese lokale Historienqualität fließt als Transparenzhinweis in Kalibrierungsstatus und Confidence-System ein. Wenn lokale Historien eingeschränkt sind, werden Trefferquoten und Lernhinweise vorsichtiger eingeordnet; automatische Gewichtungsänderungen gibt es weiterhin nicht.

Die Stabilitätstests nutzen gemeinsame Mock-Historien für Kalibrierungskontext, Confidence, Lernsystem und lokale Historienqualität. Dadurch bleiben neue Lernfelder testbar, ohne dass echte Portfolio-, Broker- oder Marktdaten benötigt werden.

- Unter 20 dokumentierten Fällen: `Datenbasis zu klein`
- 20 bis 50 Fälle: nur vorsichtige Hinweise
- Über 50 Fälle: Kalibrierungsvorschläge erlaubt

Der Kalibrierungsstatus zählt lokale Trade-, Forward-Test-, Decision- und Prognosehistorien. Für Trefferquoten werden nur Fälle mit echter Review-Auswertung und Rendite/Hit genutzt. Diese Dateien können persönliche Entscheidungen enthalten und werden nicht versioniert.

Die Signalanalyse wertet nur lokal bereits ausgewertete Forward-Tests, Trade-Journal-Setups, Entscheidungen und Prognosen aus. Neue Einträge speichern zusätzlich eine kompakte `signal_snapshot` für RSI, MACD, Volatilität, News, Makro und CRV. Unter 20 ähnlichen Fällen zeigt sie nur den Sammelstand; zwischen 20 und 50 Fällen nur vorsichtige Hinweise; ab über 50 Fällen dürfen transparente Kalibrierungsvorschläge angezeigt werden. Zusätzlich zeigt die App Trefferquoten nach Asset-Typ, Marktphase und Zeithorizont, damit sichtbar wird, wo die Analyse historisch stärker oder schwächer war. Fehlfälle werden zusätzlich nach möglicher Ursache gruppiert, zum Beispiel Marktphase, Kaufsignal, RSI, MACD, Volatilität, CRV, News, Makro, Szenario-Lesart, Fehlursache, Decision-Alignment und Kalibrierungskontext. Schwache gespeicherte Backtest-Gruppen aus `backtest_history.json` können ebenfalls als manuelle Kalibrierungshinweise erscheinen. Gewichtungen werden nie automatisch geändert.

Gespeicherte Backtests aus `backtest_history.json` werden zusätzlich als eigener Lernkontext angezeigt. Die App fasst dort gespeicherte Backtest-Gruppen nach Fallzahl, Trefferquote, Durchschnittsrendite und Drawdown zusammen. Unter 20 Fällen bleibt die Aussage `Datenbasis zu klein`; auch bei größerer Datenbasis werden keine Gewichtungen automatisch geändert.

### Depot-Effekt

Wird nur berechnet, wenn **Portfolio in Bewertung einbeziehen** aktiv ist.

Der Depot-Effekt bewertet:

- Cash-Reserve
- bestehende Positionsgröße
- Anteil am Gesamtportfolio
- Klumpenrisiko
- Auswirkung eines möglichen Nachkaufs

Der Depot-Effekt ist nur eine Ergänzung. Er verbessert oder verschlechtert nicht das Kaufsignal, sondern zeigt, ob ein Kauf für dein Depot verkraftbar wäre.

## Portfolio-Modus

Wenn der Schalter aus ist:

- nur Asset-Qualität und Kaufsignal
- keine Depotdaten
- keine Klumpenrisiko-Warnung
- keine Cash-Reserve-Bewertung

Wenn der Schalter an ist:

- zusätzlich Depot-Effekt
- Asset-Qualität und Kaufsignal bleiben unverändert

## portfolio.json

Die `portfolio.json` ist bewusst GitHub-kompatibel gehalten, damit der Depot-Modus auch auf anderen Geräten funktioniert. Sie darf nur einfache Depot-Strukturdaten enthalten:

- Cash-Bestand
- Ticker
- Asset-Typ
- Positionsgröße
- Kaufkurs

Nicht erlaubt sind:

- Name, Adresse oder persönliche Identifikationsdaten
- Kontonummern, Depotnummern oder Broker-IDs
- API-Keys, Passwörter oder Zugangsdaten
- geheime Konfigurationswerte

Zum Einrichten:

1. `portfolio.example.json` kopieren.
2. Die Kopie in `portfolio.json` umbenennen.
3. Nur die erlaubten Felder eintragen.

Beispiel:

```json
{
  "cash": 7000,
  "positions": [
    {
      "ticker": "BTC-EUR",
      "asset_type": "crypto",
      "shares": 0.014829,
      "buy_price": 100000
    },
    {
      "ticker": "EUNL.DE",
      "asset_type": "etf",
      "shares": 19.389571,
      "buy_price": 105.18
    }
  ]
}
```

Die App berechnet aktuelle Positionswerte im Depot-Modus über Yahoo Finance. Falls Kursdaten nicht verfügbar sind, wird das sauber angezeigt statt Werte zu erfinden.

- `cash`: freies Geld im Depot
- `ticker`: Yahoo-Finance-Ticker, z. B. `BTC-EUR`, `NVDA`, `EUNL.DE`
- `asset_type`: `stock`, `etf`, `crypto` oder `unknown`
- `shares`: Stückzahl oder Coin-Menge
- `buy_price`: durchschnittlicher Kaufkurs

Wichtig: Die Portfolio-Daten werden ausschließlich für den separaten Depot-Effekt verwendet. Sie verändern niemals Asset-Qualität oder Kaufsignal. Die App handelt niemals automatisch.

## Datenschutz und GitHub

Diese Dateien sind lokal/private Daten und werden nicht versioniert:

- `search_history.json`
- `trade_history.json`
- `forward_tests.json`
- `decision_history.json`
- `prediction_history.json`
- `backtest_history.json`
- `.streamlit/secrets.toml`
- `.env`
- `.venv/`
- `.yfinance-cache/`
- `__pycache__/`

Für GitHub gibt es anonymisierte Beispiele:

- `portfolio.example.json`
- `search_history.example.json`

`portfolio.json` darf versioniert werden, solange sie nur die erlaubten Felder enthält. Wenn `portfolio.json` fehlt, stürzt die App nicht ab. Im Portfolio-Modus zeigt sie dann den Hinweis: **Keine Portfolio-Datei gefunden.**

## Beispiele für Ticker

- Xiaomi: `3CP.DE` oder `1810.HK`
- Bitcoin: `BTC-EUR`
- Palantir: `PLTR`
- Nvidia: `NVDA`
- MSCI World ETF: `EUNL.DE`

## Hinweis

Dies ist keine Finanzberatung, sondern eine technische Analysehilfe. Die App enthält keine Broker-Anbindung und keine Kauf- oder Verkaufsautomatisierung.
