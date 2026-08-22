# Investment-Assistent Master-Roadmap

## Projektziel

Der Investment-Assistent ist eine lokale Python-Streamlit-App, die Aktien, ETFs und Kryptowährungen analysiert und verständliche Einschätzungen liefert. Die App soll langfristig wie ein professionelles Research-Werkzeug funktionieren: technisch sauber, transparent, nachvollziehbar und auch für Anfänger verständlich.

Aktuell ist die App ausschließlich Analyse-, Forschungs-, Paper- und Entscheidungshilfe. Verbindliche Sperrregel: `Bis zum erfolgreichen Echtgeld-Gate bleiben Broker-Anbindung und automatische Orderausführung strikt gesperrt. Danach darf eine separate, ausdrücklich freizugebende Live-Bot-Phase entwickelt werden.` Die bestehende Anwendung erhält dadurch noch keine Handelsfreigabe; bis zum späteren Gate trifft der Nutzer jede reale Entscheidung und führt jede reale Order selbst aus.

Zentrale Bewertungsregel:

- Asset-Qualität bewertet nur das Asset selbst.
- Kaufsignal bewertet nur Marktdaten und den aktuellen Einstiegszeitpunkt.
- Depot-Effekt bewertet nur Portfolio-Daten.
- Portfolio-Daten dürfen Asset-Qualität und Kaufsignal niemals beeinflussen.

Langfristige Qualitätsorientierung:

- Equity-Research-Analyst
- Hedgefonds-Analyst
- Portfoliomanager
- Makro-Research
- Krypto-Research

Die App soll transparent, nachvollziehbar, datenbasiert und anfängerfreundlich sein.

Schutz vor erfundenen Daten:

- Keine Daten erfinden.
- Fehlende Daten immer als `Daten nicht verfügbar` anzeigen.
- Schätzwerte niemals als Fakten darstellen.
- Analystenziele niemals erfinden.
- ETF-Flows niemals erfinden.
- Makrodaten niemals erfinden.

## PRIO 0 – Stabilisierung

Neue ROADMAP-Funktionen bleiben pausiert, bis die bestehende Anwendung die Stabilitätskriterien erfüllt.

- Anwendung startet fehlerfrei: am 2026-07-31 mit `compileall`, Pytest, Streamlit-AppTest und headless Streamlit-Start geprüft.
- Bestehende Funktionen reparieren: History-Lader und Auswertungsdaten tolerieren fehlende, leere und ältere lokale Datenformate.
- Signaturen und Datenmodelle vereinheitlichen: `evaluated_history_cases()` erhält Trade-History, Forward-Tests und Predictions konsistent als getrennte Eingaben; alle Kompatibilitätsaufrufe verwenden dieselbe Reihenfolge.
- Smoke-Tests ergänzen: Startseite, Hauptbedienelemente, leere Histories und unvollständige ältere JSON-Daten werden automatisiert geprüft.
- Logo entfernen: eigenes Browser-Tab-Symbol entfernt; im Repository bestehen keine weiteren Logo-Einbindungen.
- Keine neuen Funktionen entwickeln, bis Start, Hauptanalyse, Portfolio, Trading/Scanner und lokale Historien bei den verfügbaren Tests stabil bleiben.

Stabilitätskriterien:

- Streamlit startet ohne Traceback und zeigt die Startseite.
- Analyse wird erst nach bewusster Betätigung von `Analysieren` gestartet; externe Datenquellen blockieren nicht mehr den initialen Seitenaufbau.
- Fehlende oder ungültige optionale History-Dateien führen zu leeren Ansichten statt zu einem App-Absturz.
- Regressionstests für History-Signaturen und ältere `review_after`-Formate laufen erfolgreich.
- Keine Portfolio-, Analyse-, Trade-History- oder Konfigurationsdaten werden für die Stabilisierung gelöscht.

## Verbindliche Produktarchitektur

Status am 2026-08-02: Zielbild beschlossen und als erste sichere Navigationsbasis umgesetzt. Die Startseite trennt jetzt `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder`. Die bestehende Einzelanalyse deckt große Teile der künftigen Einstiegsanalyse ab; der bisherige `Opportunity Scanner` wird in der Oberfläche als `Swing Trade Finder` weitergeführt. `Investment Opportunities` besitzt zunächst nur einen ehrlichen Leer-/Planungszustand ohne erfundene Kandidaten. Der fachliche Feed, seine beiden Scores und die wählbare Long-Term-Analyse bleiben geplant.

Die Anwendung erhält drei fachlich und in der Navigation klar getrennte Hauptbereiche:

1. `Asset-Analyse` – ein bereits bekanntes oder bewusst ausgewähltes Asset bewerten.
2. `Investment Opportunities` – neue oder aktuell übersehene Investmentchancen entdecken.
3. `Swing Trade Finder` – kurzfristige, konkret umsetzbare Swing-Setups finden.

Jeder Hauptbereich beantwortet eine andere Frage und verwendet eine dafür passende Bewertungslogik. Langfristige Investmentqualität, aktuelle Investmentchance und kurzfristige Trade-Qualität dürfen nicht zu einem einzigen undurchsichtigen Gesamtscore vermischt werden.

Namens- und Migrationsregel:

- Der bisherige UI-Bereich `Opportunity Scanner` ist in der Hauptnavigation und sichtbaren Bereichsüberschrift in `Swing Trade Finder` umbenannt; die bestehende Logik und lokale Historien bleiben unverändert angebunden.
- Der neue Name `Investment Opportunities` ist ausschließlich für mittel- bis langfristige Investmentideen bestimmt und darf nicht für Swing-Trades verwendet werden.
- Historische Daten, Paper-Trades und bestehende Scanner-Logik bleiben bei einer Umbenennung erhalten.

### 1. Asset-Analyse

Zweck: Aktien, ETFs und Kryptowährungen bewerten, die bereits bekannt, auf einer Watchlist, im Depot oder aus `Investment Opportunities` übernommen worden sind.

Die Asset-Analyse erhält zwei klar wählbare Analysearten. Beide nutzen gemeinsame Stammdaten, trennen aber Fragestellung, Gewichtung, Ergebnis und Prognosehistorie.

#### 1.1 Einstiegsanalyse

Leitfrage: `Ist dieses Asset attraktiv und wann sollte ich konkret einsteigen oder nachkaufen?`

Status: fachliche Basis weitgehend umgesetzt. Langfristige Attraktivität, Preisattraktivität, kurzfristiges Timing, optionaler Depot-Effekt, Empfehlung, Kaufzonen, relative Tranchen, Bestätigungsweg, Alternative ohne Rücksetzer, Widerlegung und Gültigkeit sind vorhanden. Die explizite Auswahl der Analyseart und die Übergaben aus dem künftigen Opportunity-Feed bleiben offen.

Geeignet für:

- Watchlist-Assets
- bestehende Positionen
- konkrete Kauf- und Nachkaufentscheidungen
- Kandidaten aus `Aktuell attraktiv`

Verbindliche Trennung:

- langfristige Attraktivität
- Preisattraktivität
- kurzfristiges Timing
- optionaler Depot-Effekt
- daraus abgeleitete Handlungsempfehlung

Jede Empfehlung enthält einen vollständigen Handlungsplan mit Kaufzone als Bereich, aktueller Tranche, Rücksetzer-Tranche, Bestätigungseinstieg, Vorgehen ohne Rücksetzer, Widerlegungsbedingung und Gültigkeitsdauer. Vage Aussagen wie nur `Warten` oder `Später kaufen` sind unzulässig. Ein gutes, attraktiv bewertetes Asset darf trotz noch fehlender Bodenbildung begründet als `Erste Tranche kaufen` eingestuft werden; kurzfristige Technik darf die langfristige Qualität nicht umdefinieren.

#### 1.2 Intelligente Einstiegs-Watchlist

Leitfrage: `Ist meine Investmentthese noch intakt, ist das Asset noch attraktiv und welcher Einstieg ist heute vernünftig?`

Status: als priorisierte Erweiterung der `Asset-Analyse` geplant. Die bestehende Einstiegsanalyse, Long-Term-Grundlagen, Preisattraktivität, technische Zonen, Szenarien und Hintergrundläufe liefern Bausteine, bilden aber noch keine dauerhaft gepflegte intelligente Einstiegs-Watchlist. Die Watchlist darf erst dann als automatisch aktuell bezeichnet werden, wenn Datenzeitpunkte, Quellenstatus, Neubewertungsregeln und Fehlerzustände sichtbar und getestet sind.

Minimale Nutzereingaben:

- eindeutig ausgewähltes Asset beziehungsweise Listing
- geplantes Gesamtbudget in Euro
- eigene Investmentthese als frei formulierter Ausgangspunkt

Das Budget beeinflusst ausschließlich Tranchierung, Positionsplanung und Risikodarstellung. Es darf langfristige Attraktivität, Zukunftspotenzial, fairen Wert oder das Kaufsignal nicht verbessern oder verschlechtern. Die persönliche These ist eine zu prüfende Hypothese und keine Datenquelle oder bestätigte Tatsache.

Automatischer Analyseauftrag:

- Die These in überprüfbare Kernaussagen, Voraussetzungen, erwartete Treiber, Risiken und Widerlegungsbedingungen zerlegen.
- Jede Kernaussage kritisch mit belegbaren Unternehmens-, Branchen-, Bewertungs-, Markt- und Kursdaten prüfen; Gegenargumente aktiv suchen und Unsicherheit sichtbar halten.
- Langfristige Attraktivität, Zukunftspotenzial, Geschäftsmodellqualität, Wettbewerbsvorteile, Skalierbarkeit, Bilanz, Verwässerungsrisiko und Gefahr eines dauerhaften Kapitalverlusts getrennt bewerten.
- Ermitteln, welches Umsatz-, Margen-, Gewinn- oder Cashflow-Wachstum der aktuelle Preis ungefähr voraussetzt und wie viel der Investmentthese bereits eingepreist erscheint. Nicht belastbare Annahmen bleiben ausdrücklich unbekannt.
- Einen probabilistischen fairen Preisbereich mit Bear-, Basis- und Bull-Annahmen ableiten. Ein einzelner scheinpräziser fairer Wert ist unzulässig.
- Eine bevorzugte Einstiegszone und einen maximal noch sinnvollen Kaufpreis bestimmen. Der Maximalpreis ist die Grenze, oberhalb der das erwartete Verhältnis aus Rendite und Risiko für die These nicht mehr ausreicht; er ist kein Stop und keine Kursprognose.
- Eine konkrete Alternative für den Fall liefern, dass das Asset ohne Rücksetzer weiter steigt, zum Beispiel kleine Bestätigungstranche, Einstieg erst nach tragfähiger Konsolidierung oder bewusst nicht hinterherlaufen. Es darf kein Kaufzwang entstehen.
- Eine zum Budget passende Tranchierung mit Betrag und Anteil je Tranche vorschlagen. Rundung, Restbudget und Bedingungen für jede weitere Tranche müssen sichtbar sein; ohne belastbare Zonen wird keine scheinpräzise Stückzahl erfunden.
- Listing-spezifische Unterstützungen, Widerstände, Volatilität, Liquidität, bevorzugte Zone, Bestätigung, Maximalpreis und technische Widerlegung bestimmen. Fundamentale These und technische Einstiegslage bleiben getrennt.
- Einen klaren aktuellen Zustand ausgeben: `Jetzt kaufen`, `Erste Tranche`, `Weiter beobachten`, `Nicht mehr hinterherlaufen` oder `These nicht mehr attraktiv`. Jede Einstufung benötigt nachvollziehbare Bedingungen und einen sichtbaren Datenstand.

Szenarien statt falscher Zeitversprechen:

- Keine Behauptung, dass zu einem bestimmten zukünftigen Datum sicher ein Boden, Rücksetzer oder Ausbruch eintritt.
- Wahrscheinlichkeiten nur als unsichere, versionierte Szenarien für `Rücksetzer`, `Konsolidierung` und `Rally ohne Rücksetzer` ausgeben.
- Jede Wahrscheinlichkeit benötigt Datenstand, Horizont, Stichprobengröße beziehungsweise Kalibrierungsstatus und eine verständliche Unsicherheitswarnung. Ohne ausreichende Evidenz nur qualitative Szenarien oder breite Bandbreiten anzeigen.
- Szenarien dürfen keine erfundenen Kurse, Nachrichten, Fundamentaldaten oder Wahrscheinlichkeiten enthalten und keine automatische Order auslösen.

Unternehmens- und Reifegradlogik:

- Spekulative Wachstums-, KI-, Biotech- und andere frühe Unternehmen nicht mit denselben Bewertungsmaßstäben wie reife Standardunternehmen beurteilen.
- Bewertungsmodell und Pflichtkennzahlen an Geschäftsmodell, Reifegrad und Werttreiber anpassen, zum Beispiel wiederkehrender Umsatz, Wachstum, Bruttomarge, Cash-Burn, Finanzierungsspielraum, Verwässerung, Kundenkonzentration, Auftragsbestand oder regulatorische Meilensteine.
- Auch bei ungeeigneten klassischen Multiplikatoren bleiben Bewertung, eingepreiste Erwartungen und Verlustpotenzial verpflichtend; fehlende Daten führen zu geringerer Confidence oder Enthaltung, nicht zu einer erfundenen Ersatzbewertung.
- Die verwendete Unternehmensklasse, das Bewertungsmodell und seine Grenzen werden sichtbar und versioniert gespeichert.

Automatische Aktualisierung:

- Täglich nur günstige listing-spezifische Markt- und Technikdaten prüfen: Kurs, abgeschlossene OHLCV-Daten, Volatilität, Unterstützungen/Widerstände, Abstand zu Einstiegszone und Maximalpreis sowie technische Widerlegung.
- Vollständige Neubewertung in einem versionierten, lastkontrollierten Rhythmus durchführen; Zielbild zunächst häufiger für spekulative beziehungsweise schnell veränderliche Unternehmen und seltener für stabile Unternehmen.
- Eine außerplanmäßige vollständige Neubewertung nur bei belegten wesentlichen Änderungen auslösen: starke Kurs-/Bewertungsbewegung, neue Fundamentaldaten, Earnings, belastbare Unternehmensnachricht, These-relevantes Branchenereignis oder verändertes Marktregime.
- Nachrichtenmenge allein ist kein Auslöser. Deduplizierung, Quellenqualität, Relevanz zur These und tatsächliche Neuigkeit müssen geprüft werden.
- Bei fehlenden oder veralteten Daten den bisherigen Plan nicht still als aktuell weiterführen. Status stattdessen auf `Neubewertung nötig` beziehungsweise `Daten nicht ausreichend aktuell` setzen.
- Verpasste Hintergrundprüfungen sicher nachholen, ohne rückwirkend vorzutäuschen, die Information sei früher bekannt gewesen.

Alterung und Neubau von Einstiegsplänen:

- Jeder Plan speichert Erstellungszeitpunkt, verwendeten Daten-Cutoff, Listing, Logikversion, Annahmen, fairen Preisbereich, Einstiegszone, Maximalpreis, Tranchierung, Szenarien und Widerlegungsbedingungen.
- Bei wesentlicher Kursbewegung, abgelaufener Gültigkeit, geänderter Bewertung oder veränderter These einen neuen versionierten Plan erzeugen. Alte Pläne bleiben unverändert nachvollziehbar und werden als ersetzt, abgelaufen oder widerlegt markiert.
- Eine frühere Einstiegszone darf nicht mechanisch beibehalten werden, wenn der Kursverlauf oder neue Unternehmensdaten sie unrealistisch gemacht haben.
- Änderungen zwischen zwei Bewertungen erklären: neue Fakten, geänderte Annahmen, verschobener fairer Bereich, veränderte Zone, andere Tranchierung und neuer Handlungsstatus.

Kompakte Oberfläche:

Die geschlossene Watchlist-Karte zeigt zunächst ausschließlich:

- `These intakt?`
- `Asset noch attraktiv?`
- `Jetzt kaufen?`
- `Wo einsteigen?`
- `Was hat sich seit der letzten Analyse verändert?`

Zusätzlich bleiben Asset/Listing, Datenstand und ein Warnstatus bei Datenlücken sichtbar. Fairer Preisbereich, Maximalpreis, Szenarien, Tranchierung, Belege, Gegenargumente, Bewertungsmodell, technische Marken und vollständiger Änderungsverlauf erscheinen erst nach Klick. Die Hauptansicht darf nicht mit Rohdaten, langen Begründungen oder zahlreichen Scores überladen werden.

Hybridarchitektur:

- Deterministische Python-Logik berechnet Kurse, Renditen, Multiplikatoren, eingepreiste Erwartungen, faire Bandbreiten, technische Marken, Zonen, Maximalpreis, Tranchierung, Risiko, Zeitstempel und Änderungsvergleiche.
- KI darf qualitative Unternehmensentwicklung, Nutzerthese, Geschäftsmodell, relevante belegte Nachrichten und Gegenargumente strukturieren und neu bewerten.
- KI-Ausgaben müssen ausschließlich auf mitgelieferten Quellen und strukturierten Fakten beruhen, Aussagen mit Belegen verbinden, Unsicherheit kennzeichnen und fehlende Informationen offenlassen.
- Die KI darf keine Kurse, Kennzahlen, Ereignisse, Quellen, Wahrscheinlichkeiten oder Unternehmensfakten erfinden und keine deterministisch berechneten Zahlen überschreiben.
- Fällt die KI aus oder fehlt ausreichende Evidenz, bleibt die numerische Watchlist funktionsfähig und zeigt die qualitative Neubewertung als nicht verfügbar.

Daten-, Historien- und Sicherheitsvertrag:

- Watchlist, These und Budget lokal speichern; sensible Freitexte nicht an externe KI-Dienste senden, bevor Datenfluss, Einwilligung und Anbieter ausdrücklich geklärt sind.
- Neue Bewertungen und Planversionen append-only beziehungsweise revisionssicher speichern. Bestehende Analyse-, Prognose-, Forward-, Paper- und Nutzertrade-Daten weder löschen noch rückwirkend verändern.
- Unternehmen und konkretes Listing sauber trennen. Kurs, Technik, Zonen und Maximalpreis bleiben immer listing-spezifisch; qualitative Unternehmensfakten dürfen nur über eine belegte Emittentenzuordnung geteilt werden.
- Keine Broker-Anbindung, keine automatische Kauf- oder Verkaufsfunktion und keine automatische Orderausführung.

Akzeptanzkriterien und Regressionstests:

- Eine optimistische Nutzerthese wird nicht bestätigt, wenn belastbare Gegenbelege oder nicht erfüllte Voraussetzungen vorliegen.
- Derselbe Analysezustand liefert unabhängig vom Budget dieselbe Attraktivität, denselben fairen Preisbereich und denselben Handlungsstatus; nur Tranchierung und Beträge ändern sich.
- Ein Kurs oberhalb des Maximalpreises kann nicht als `Jetzt kaufen` erscheinen, nur weil Momentum positiv ist.
- Rücksetzer-, Konsolidierungs- und Rally-Szenario funktionieren ohne fest versprochenes Datum und enthalten einen sichtbaren Unsicherheitsstatus.
- Reife Qualitätsaktie und spekulative KI-/Wachstumsaktie verwenden unterschiedliche, ausdrücklich ausgewiesene Bewertungsmodelle.
- Ein veralteter Plan wird bei wesentlicher Kurs- oder Fundamentaldatenänderung nicht weiter als aktuell angezeigt, sondern versioniert neu bewertet oder sichtbar zurückgestellt.
- Direkter Ticker, Unternehmensname mit mehreren Listings, ADR/GDR, EUR- und Fremdwährungslisting sowie fehlende Daten werden ohne Vermischung getestet.
- Die geschlossene Karte enthält nur die fünf vereinbarten Nutzerfragen plus Identität, Datenstand und nötige Warnung; Details werden erst nach bewusster Aktion geladen.

#### 1.3 Long-Term-Analyse

Leitfrage: `Warum könnte dieses Unternehmen über mindestens drei Jahre deutlich an Wert gewinnen?`

Status: als eigenständige Analyseart geplant. Einzelne Research-Bausteine wie Zukunftspotenzial, Qualität, Fundamentaldaten, Bewertung, Szenarien und Risiken existieren bereits. Seit 2026-08-02 ist zusätzlich eine noch nicht in der UI freigeschaltete, versionierte Quellen- und Bereitschaftsgrundlage vorhanden: Zehn Pflichtbereiche werden auf belegte Aussagen, Herkunft, Abrufzeitpunkt, Verwendungszweck, quellentypisches Höchstalter sowie erforderliche Primär- und unabhängige Quellen geprüft. Ein neuer Abruf kann einen alten Bericht nicht verjüngen; Abrufzeitpunkte benötigen eine Zeitzone und Zukunftszeitpunkte werden abgelehnt. Yahoo Finance oder allgemeine Kontextquellen allein reichen nicht; technische Einstiegssignale zählen nicht zur Long-Term-Abdeckung. Eine atomare, schema- und modellversionierte lokale Quellenablage bewahrt öffentliche Provenienz und Evidenz, lehnt beschädigte, widersprüchliche oder bereits bei Sammlung veraltete Daten ab und sperrt später veraltete Stände für die Analyse. Eine getrennte deterministische Bewertungsgrundlage berechnet nach erfolgreichem Quellengate sieben sichtbare Faktoren sowie Bear-, Basis- und Bull-Szenarien für drei bis sieben Jahre; technisches Timing ist dort als Faktor ausgeschlossen. Eine noch inaktive nicht schreibende SEC-Teilkollektion kann offizielle aktuelle US-Jahres-/Quartalsfilings entdecken, sechs strukturierte Jahreswerte und sachliche Vorjahresvergleiche nur bei exakt passenden Filing-Accessions in Finanzqualitäts-Evidenz überführen und das weiterhin geschlossene Gesamtgate ehrlich melden. Eine manuelle CLI mit vollständig offline Vorprüfung ist vorbereitet, bleibt aber ohne gültige Fair-Access-Laufzeitkennung gesperrt. Automatische batchfähige Beschaffung, weitere Geschäftsmodell-/Risiko-Ableitung, unabhängige Markt-/Wettbewerbsquellen, vollständige Faktorableitung, Ergebnistext, Langfrist-Empfehlung, separater Einstieg und UI-Modus fehlen weiterhin.

Die Long-Term-Analyse wird automatisch vorausgewählt, wenn ein Kandidat aus `Zukunftschancen 3+ Jahre` übernommen wird. Sie bewertet die langfristige Investmentthese unabhängig vom kurzfristigen Chart. Technische Analyse bestimmt nur den Einstiegsplan, nicht die langfristige Unternehmensqualität.

Verbindliche Inhalte:

- verständliches Geschäftsmodell, Produkte, Dienstleistungen und Kundengruppen
- Umsatz- und Gewinnquellen sowie wiederkehrende und einmalige Umsätze
- Marktgröße, Marktwachstum und strukturelle Zukunftstrends
- Wettbewerbsvorteile, Marktstellung, Konkurrenz und Skalierbarkeit
- Management, Kapitalverwendung, Verwässerung und Bilanzqualität
- Umsatz-, Gewinn- und Cashflow-Entwicklung
- Bewertung im Verhältnis zum zukünftigen Wachstum und bereits eingepreiste Erwartungen
- langfristige Chancen, Risiken und Gefahr eines dauerhaften Kapitalverlusts
- Bull-, Basis- und Bear-Szenario für drei bis sieben Jahre
- konkrete Bedingungen für das Eintreten und Scheitern der Investmentthese
- erwartete Renditespanne mit sichtbarer Unsicherheit
- anschließend ein separat berechneter Einstiegsplan

Ergebnisstruktur:

- langfristige Investmentthese
- Zukunftspotenzial
- Unternehmensqualität
- Bewertung
- langfristige Risiken
- erwartete Renditespanne
- notwendige Bedingungen
- Widerlegungsbedingungen
- separater Einstiegsplan

Daten- und Quellenabhängigkeit:

- Yahoo Finance allein reicht für Geschäftsmodell, Strategie und Wettbewerbsvorteile nicht aus.
- Langfristig sind Geschäftsberichte, Quartalsberichte, Investor-Präsentationen, Earnings Calls, offizielle Unternehmensinformationen sowie belastbare Branchen- und Marktdaten vorzusehen.
- Quellen müssen mit Zeitpunkt und Verwendungszweck nachvollziehbar sein.
- Fehlende Quellen oder nicht prüfbare Aussagen werden sichtbar als Datenlücke gekennzeichnet und niemals ergänzt oder erfunden.

#### 1.4 Unternehmen, Börsenlisting, ADR/ADS und Primärnotierung trennen

Status: geplant als querschnittliche Identitätsgrundlage für Suche, Asset-Analyse, Long-Term-Analyse, Prognosesystem und Swing Trade Finder. Die vorhandene Ticker-/Asset-Erkennung bleibt als Basis erhalten, unterscheidet Unternehmen und mehrere handelbare Listings aber noch nicht durchgängig mit einem gemeinsamen verbindlichen Datenmodell. Es darf keine XPeng-Sonderregel entstehen.

Fachliches Identitätsmodell:

- `company_id` beziehungsweise `issuer_id` bezeichnet das wirtschaftliche Unternehmen. Geschäftsmodell, Umsatz, Gewinn, Cashflow, Verschuldung, Management, Wettbewerb, Marktstellung, langfristige Risiken, langfristige Qualität und langfristige Attraktivität liegen auf dieser Ebene.
- `listing_id` bezeichnet das konkret handelbare Instrument. Ticker, Börsenplatz, Originalwährung, ISIN, Instrumenttyp, Stammaktie/Anteilsklasse/ADR/ADS/Depositary Receipt, Primär- oder Sekundärlisting, Handelszeiten, Kurs, Chart, Liquidität, Volumen, Spread, technische Marken, Timing, Einstieg, Stop und Ziele liegen auf dieser Ebene.
- Eine stabile Zuordnung verbindet mehrere Listings mit demselben Emittenten. Tickerwechsel, Börsenwechsel, Anteilsklassen, Delistings und zeitlich veränderte ADR-/ADS-Verhältnisse werden versioniert und mit Gültigkeitszeitraum gespeichert.
- Ein ADR-/ADS-Umrechnungsverhältnis darf nur verwendet werden, wenn es belastbar belegt und zeitlich passend ist. Es kann Identitäts- und Bewertungsnormalisierung unterstützen, ersetzt aber niemals den listing-spezifischen Chart oder technische Handelsmarken.

Verbindliches Suchverhalten:

- Eine direkte eindeutige Tickereingabe analysiert genau dieses Listing und zeigt vor Beginn Name, Ticker, Börsenplatz, Originalwährung und Instrumenttyp.
- Eine Unternehmensnamensuche gruppiert Treffer zunächst nach Emittent. Existieren mehrere relevante Listings, zeigt die App eine verständliche Auswahl statt still den ersten Yahoo-Treffer zu verwenden.
- Beispiel: `XPeng Inc.` → `9868.HK – Hongkong-Aktie – HKEX – HKD` und `XPEV – US-ADS/ADR – NYSE – USD`. Dasselbe Verfahren gilt allgemein für asiatische oder europäische Unternehmen mit US-ADR/ADS, mehrere europäische Listings, Dual Listings, Anteilsklassen und Depositary Receipts.
- Jede Auswahl zeigt mindestens Name, Ticker, Börsenplatz, Originalwährung, Instrumenttyp, Primärlisting ja/nein und ISIN, sofern belastbar vorhanden.
- Falls eine automatische Vorauswahl fachlich vertretbar ist, muss `Analysiertes Listing: …` vor dem Analysestart klar sichtbar und änderbar bleiben. Eine unsichere Primärnotierung wird als unbekannt markiert und nicht erfunden.
- Doppelte Yahoo-Suchergebnisse desselben Emittenten werden nicht still zusammengeführt. Die App prüft Instrumenttyp, Börse, Währung, Handelszeiten und Identitätsbelege, bevor sie Listings gruppiert.

Strikte Datentrennung:

- Kurs, Chart, Volumen, Spread, Renditehistorie, Unterstützungen, Widerstände, Einstieg, Stop, Ziele, technische Scores und kurzfristige Prognosen stammen vollständig vom ausgewählten `listing_id`.
- Nie Kurs von Listing A mit Chart oder Volumen von Listing B verbinden; nie Stop, Ziel oder technische Marke zwischen ADR/ADS und Stammaktie übertragen; nie Wechselkurse oder unterschiedliche Handelszeiten ignorieren.
- Technisches Timing und Preisattraktivität dürfen zwischen Listings desselben Unternehmens unterschiedlich sein. Die langfristige Unternehmensqualität wird dagegen aus derselben normalisierten und belegten Unternehmensebene abgeleitet und darf nicht allein wegen unterschiedlich vollständiger Yahoo-Felder widersprüchlich werden.
- Jede Analyse und Ergebnisansicht hält das tatsächlich verwendete Listing sichtbar. Ein Wechsel des Listings erfordert eine neue listing-spezifische technische Analyse.

Prognose- und Lernvertrag:

- Neue Prognose-Snapshots speichern `company_id`/`issuer_id`, `listing_id`, Ticker, Börsenplatz, Instrumenttyp, Originalwährung, ISIN falls vorhanden, Primärlistingstatus und ein belegtes ADR-/ADS-Verhältnis falls relevant.
- Bestehende echte Point-in-Time-Snapshots und Forward-Ergebnisse bleiben unverändert. Neue Identitätsfelder werden bei Altdaten als unbekannt beziehungsweise Legacy markiert und niemals rückwirkend als damals bekannt ausgegeben.
- Unternehmens-/Long-Term-Statistiken zählen wirtschaftlich gleiche Listings standardmäßig einmal auf Emittentenebene oder über ein versioniertes kanonisches Listing. Alternative Listings zählen nur getrennt, wenn ausdrücklich die Listing-/Handelsplatzwirkung untersucht wird.
- Kurzfristiges Timing darf Listings getrennt auswerten, weil Handelszeiten, Liquidität, Währung und Chartstruktur tatsächlich verschieden sind. Statistische Auswertungen kennzeichnen die Abhängigkeit desselben Emittenten und behandeln die Listings nicht automatisch als unabhängige Unternehmen.

Vorgesehene Regressionstests:

- XPeng mit `9868.HK` und `XPEV`
- europäisches Unternehmen mit US-ADR
- Unternehmen mit mehreren europäischen Listings
- eindeutige Einzelnotierung ohne ADR/ADS
- direkte Suche per Ticker
- Suche per Unternehmensname mit bewusster Listing-Auswahl
- Negativtests gegen Vermischung von Kurs, Chart, Volumen, Stop, Ziel, Währung oder Prognose zwischen Listings

### 2. Investment Opportunities

Zweck: Wenige hochwertige Aktienideen entdecken, die der Nutzer möglicherweise noch nicht kennt oder aktuell nicht betrachtet. Bekannte Unternehmen dürfen erscheinen, wenn sie objektiv eine besonders attraktive Gelegenheit bieten.

Status: als eigener Navigationsbereich mit erklärtem Leerzustand vorhanden, fachlich aber noch nicht umgesetzt. Es werden bewusst keine scheinbaren Kandidaten oder provisorischen Scores angezeigt. Der bestehende Swing-Scanner ist kein Vorläufer dieses Bereichs und darf nicht fachlich wiederverwendet werden. Verwendbare Grundlagen sind das kuratierte 325-Asset-Universum, bestehende Qualitäts-, Bewertungs- und Zukunftsmodule sowie die lokale Prognosehaltung; vor einer Nutzung müssen Datenabdeckung, Last und eigene Score-Logik geklärt werden.

Der Bereich erhält zwei wählbare Modi mit getrennten Scores.

#### 2.1 Aktuell attraktiv

Leitfrage: `Welche guten Unternehmen bieten aktuell ein besonders attraktives Verhältnis aus Preis, Potenzial und Risiko?`

Horizont: mehrere Monate bis ungefähr drei Jahre.

Stärkere Gewichtung:

- aktuelle Preisattraktivität und Unternehmensqualität
- realistische erwartete Rendite
- Kursrückgang und Abstand zu historischen Hochs nur als Kontext
- Ursache des Kursrückgangs und Entwicklung der Fundamentaldaten seit dem Hoch
- Gewinn- und Umsatzrevisionen
- aktuelle Katalysatoren und mittelfristige Risiken
- aktuelles Einstiegspotenzial

Ein Kursrückgang ist nur attraktiv, wenn die fundamentale Investmentthese weiterhin intakt ist. Übergang: `Aktuell attraktiv` → `Einstiegsanalyse`.

#### 2.2 Zukunftschancen 3+ Jahre

Leitfrage: `Welche Unternehmen könnten in drei bis sieben Jahren deutlich größer oder wertvoller sein, obwohl dieses Potenzial noch nicht vollständig eingepreist ist?`

Stärkere Gewichtung:

- langfristiges Marktpotenzial und strukturelle Zukunftstrends
- Unternehmensqualität, Wettbewerbsvorteile und Skalierbarkeit
- Umsatz-, Gewinn- und Cashflow-Potenzial sowie Bilanz
- Bewertung im Verhältnis zum zukünftigen Wachstum
- realistische langfristige Rendite
- Risiko eines dauerhaften Kapitalverlustes

Gesucht werden weniger bekannte Wachstumsunternehmen, spezialisierte Marktführer, indirekte Trendprofiteure, Zulieferer und Infrastrukturunternehmen, Qualitätsunternehmen nach vorübergehender Schwäche sowie bekannte größere Unternehmen mit neu attraktiver Bewertung. Relevante Suchfelder umfassen unter anderem Halbleiter und Ausrüstung, Rechenzentren, Stromversorgung und Kühlung, Elektrifizierung, Stromnetze, Automatisierung, Robotik, Cybersecurity, Cloud-Software, Medizintechnik, Wasserinfrastruktur, Kernenergie und digitale Zahlungen.

Übergang: `Zukunftschancen 3+ Jahre` → `Long-Term-Analyse`.

#### 2.3 Opportunity-Feed und Nutzeraktionen

Der Feed zeigt gleichzeitig nur wenige hochwertige Kandidaten, als Zielwert ungefähr zehn. Er lädt keine mittelmäßigen Ideen nach, nur um freie Plätze zu füllen. Ohne ausreichend guten Kandidaten erscheint `Aktuell keine überzeugende Investmentchance gefunden.`

Jede kompakte Opportunity-Fläche zeigt:

- Unternehmen, Ticker, Branche und Region
- Modus und Anlagehorizont
- warum die Chance interessant und möglicherweise noch nicht vollständig eingepreist ist
- Unternehmensqualität
- Zukunftspotenzial oder aktuelle Attraktivität
- Preisattraktivität und Risiko
- grobe Szenarien und wichtigste Unsicherheit

Verbindliche Aktionen:

- `Zur Watchlist`: dauerhaft in eine Investment-Watchlist übernehmen und Kaufzonen, These sowie wichtige Veränderungen weiter beobachten.
- `Jetzt analysieren`: abhängig vom Modus Einstiegsanalyse oder Long-Term-Analyse mit übernommenem Asset und Kontext öffnen.
- `Schon bekannt`: zunächst ausblenden, aber im Universum behalten; erneute Anzeige nur bei wesentlicher Verbesserung von Bewertung, Opportunity Score oder Investmentthese.
- `Später erneut zeigen`: für einen wählbaren Zeitraum wie 30, 90 oder 180 Tage ausblenden.
- `Nicht interessant`: optional mit Grund wie Branche, Risiko, Geschäftsmodell, vorhandene Depotabdeckung oder dauerhaftes Ausblenden.

Nutzerentscheidungen verändern nur Auswahl und Anzeige des Feeds, niemals die objektive fachliche Bewertung. Alle Ausblendungen sind unter Einstellungen einsehbar und rückgängig zu machen. Private Präferenzen und Historien bleiben lokal und dürfen nicht automatisch gelöscht werden.

#### 2.4 Getrennte Opportunity-Scores und Vielfalt

Score `Aktuelle Attraktivität` bewertet insbesondere Preisattraktivität, Unternehmensqualität, erwartete Rendite, aktuelle Katalysatoren, mittelfristige Risiken und Einstiegssituation.

Score `Zukunftschance` bewertet insbesondere Zukunftspotenzial, Unternehmensqualität, Marktgröße, strukturelles Wachstum, Wettbewerbsvorteile, Bewertung zum zukünftigen Wachstum, erwartete langfristige Rendite und langfristige Risiken. Kurzfristige Technik beeinflusst nur den Einstieg und nicht diesen Zukunftschancen-Score.

Gewichtungen liegen zentral, sind versioniert, dokumentiert und anhand echter Ergebnisse überprüfbar. Es gibt keine heimliche automatische Änderung.

Der Feed mischt bewusst bekannte Qualitätsunternehmen, mittelgroße Wachstumsunternehmen, weniger bekannte Marktführer, indirekte Trendprofiteure, attraktive Rücksetzer, Branchen, Regionen und Unternehmensgrößen. Vielfalt ist eine Auswahlregel nach erfüllter Mindestqualität und darf schwache Kandidaten niemals künstlich aufwerten.

### 3. Swing Trade Finder

Zweck: kurzfristige, umsetzbare Trades für mehrere Tage bis wenige Wochen finden. Dieser Bereich bleibt vollständig von langfristigen Investments und dem Opportunity-Feed getrennt.

Status: automatische Long-v1-Marktsuche seit 2026-08-02 umgesetzt und am 2026-08-11 auf 2.520 aktive liquide Aktien, ETFs und große Kryptowährungen erweitert. Der binäre Gesamtmarkt-Grobfilter analysiert nun jeden bestandenen Kandidaten vollständig; die frühere feste 60er-Grenze ist entfernt. Ein versionierter Funnel misst Universum, geladene Daten, Grobfilter, Tiefenprüfung, Setup-Freigabe und Portfoliofreigabe getrennt nach Aktien, ETFs und Krypto. In der Hauptoberfläche verbleiben nur Tradingkapital und Scan-Aktion. Weitere Setup-Arten bleiben bis zu einer belastbaren echten Forward-Historie gesperrt.

Verbindliche Regeln:

- zunächst nur Long-Trades in liquiden Aktien, ETFs und großen Kryptowährungen
- keine Hebelprodukte und kein Scalping; Broker-Anbindung und automatische Orderausführung bleiben bis zum erfolgreichen Echtgeld-Gate strikt gesperrt
- keine sichtbare Kategorie `Beobachten` und kein erzwungener relativ bester Trade
- ohne freigegebenes Setup: `Aktuell kein hochwertiger Trade vorhanden.`
- Einstieg, Stop, Ziele, CRV, Haltedauer, Gültigkeit, Ereignisrisiken, Nichteinstiegsbedingungen, Positionsgröße, Gründe und größtes Risiko vollständig und messbar anzeigen
- Nutzer führt Kauf und Verkauf selbst aus; die Finder-Hauptansicht enthält keine Order- oder manuelle Ausführungssteuerung
- alle Setups zunächst als Paper-Trades dokumentieren und nach Trefferquote, Gewinn, Verlust, Expected Value, Profitfaktor, Drawdown, Setup, Marktphase, Ziel-/Stop-Treffern und Opportunitätskosten auswerten

Spätere Erweiterungen wie Bodenbildungs-/Erholungssetup sowie Short-/Absicherungssetups beginnen erst nach belastbarer Long-Validierung.

### Zusammenspiel der drei Hauptbereiche

- Langfristige Chancen: `Investment Opportunities` → `Zukunftschancen 3+ Jahre` → `Long-Term-Analyse` → Investment-Watchlist → späterer Einstieg über `Einstiegsanalyse`.
- Aktuell attraktive Investments: `Investment Opportunities` → `Aktuell attraktiv` → `Einstiegsanalyse` → Kaufentscheidung oder Investment-Watchlist.
- Bereits bekannte Assets: `Asset-Analyse` → Analyseart manuell wählen → konkrete Bewertung und Plan.
- Kurzfristige Trades: `Swing Trade Finder` → Einstieg, Stop, Ziel und Positionsgröße → manuelle Ausführung → Trade-Begleitung und Auswertung.

## Verbindliche Design- und Informationsarchitektur

Status: Zielbild verbindlich aufgenommen am 2026-08-02. Die dreistufige bestehende Analyse, vollständiger Textumbruch, responsive Grundregeln und die Navigation mit drei klar getrennten Hauptbereichen sind umgesetzt und durch Streamlit-AppTests regressionsgeprüft. Erste zentrale Design-Tokens für Radien, Rahmen, Oberflächen und Schaltflächen sind vorhanden. Die vollständige optische Vereinheitlichung von Asset-Analyse, Investment Opportunities, Swing Trade Finder, Prognosequalität und Einstellungen sowie eine erneute sichtbare Desktop-/390-Pixel-Prüfung bleiben offen; der lokale Browserzugriff wurde in diesem Arbeitslauf durch die Browser-Sicherheitsrichtlinie blockiert.

### Übergreifende Designrichtung

Die App erhält ein ruhiges, hochwertiges Premium-Design nach allgemeinen Apple-typischen Gestaltungsprinzipien, ohne Apple direkt zu kopieren.

Verbindliche Prinzipien:

- wenige Farben und visuelle Reize
- großzügige, konsistente Abstände
- klare Typografie-Hierarchie
- große, verständliche Hauptaktionen
- wenige hochwertige Komponenten statt vieler kleiner Karten
- dezente Rahmen, Schatten und abgerundete Flächen
- möglichst native und stabile Streamlit-Komponenten
- keine verspielten Animationen
- keine Gestaltung wie ein hektisches Trading-Terminal
- keine überladene Sidebar; seltene Einstellungen gehören in klar benannte erweiterte Bereiche
- Fachparameter, Methodik und Rohdaten erst in erweiterten Ansichten zeigen
- wichtige Texte vollständig anzeigen und niemals mit `...` abschneiden
- auf schmalen Ansichten Elemente untereinander statt gequetscht nebeneinander anordnen

Geplante Designsystem-Bausteine:

- zentrale Regeln für Farben, Schriftgrößen, Abstände, Radien, Rahmen und Schatten
- einheitliche Hauptaktionen, Statusflächen, Tabellen, Tabs und Expander
- konsistente Zustände für Laden, leer, Erfolg, Warnung, Fehler und `Daten nicht verfügbar`
- gemeinsame responsive Regeln für Desktop und schmale Ansichten
- optische Vereinheitlichung von Startseite, Asset-Analyse, Investment Opportunities, Swing Trade Finder, Prognosequalität und Einstellungen
- visuelle Regressionstests mindestens für breite Desktop- und 390-Pixel-Ansicht

Abhängigkeiten:

- Stabilität, Datenqualität und vollständige Texte bleiben Voraussetzung.
- Das Designsystem darf keine Bewertungslogik verändern und keine Informationen verstecken, die für eine Entscheidung notwendig sind.
- Zuerst gemeinsame Regeln und Kernkomponenten festlegen, danach einzelne Seiten angleichen.

### Gemeinsame dreistufige Informationshierarchie

Status: für die bestehende Einstiegsanalyse weitgehend umgesetzt und bis 2026-08-02 regressionsgeprüft. Die Übertragung auf Long-Term-Analyse, Investment Opportunities und den umbenannten Swing Trade Finder ist geplant. Die Struktur ist verbindlicher Vertrag für alle drei Hauptbereiche.

Ebene 1 – Empfehlung und Plan, direkt sichtbar:

- klare Einordnung oder Handlungsempfehlung
- kurze Begründung und wichtigste Risiken
- Anlagehorizont und Confidence beziehungsweise Datenbelastbarkeit
- konkreter Plan
- Widerlegungsbedingung und Gültigkeit
- in der Einstiegsanalyse zusätzlich getrennte Langfrist-, Preis- und Timing-Sicht, höchstens drei Gründe, höchstens zwei Risiken, Kaufzonen, relative Tranchen, Bestätigungseinstieg und Vorgehen ohne Rücksetzer
- im Swing Trade Finder zusätzlich exakter Einstieg, Stop, Ziele, CRV, Positionsgröße und Nichteinstiegsbedingungen

Diese Ebene beantwortet ausschließlich: Was ist die Einordnung? Was soll ich tun? Warum? Wann genau? Was widerlegt die Idee?

Ebene 2 – Analyse im Detail:

- Geschäftsmodell oder Investmentthese
- Qualität, Bewertung und Zukunftspotenzial
- Einstieg und Vorgehen
- Chancen
- Risiken
- Szenarien
- Markt und Umfeld
- Portfolio-Effekt nur bei aktivem Portfolio-Modus
- jede Facette beginnt mit einer kurzen verständlichen Zusammenfassung; keine unnötige Kennzahlenwand

Ebene 3 – Erweiterte Analyse:

- technische Kennzahlen und Fundamentalkennzahlen
- Rohdaten
- Datenqualität, Quellen und Proxies
- Score-Gewichtungen, Methodik und Modellversion
- Prognosehistorie, Prognosequalität und historische Tests

Grundregel:

- Hauptansicht: Was ist die Einordnung und was soll ich tun?
- Detailanalyse: Warum?
- Erweiterte Analyse: Wie wurde es berechnet?

### Verbindliches Empfehlungssystem

Status: fachliche Basis umgesetzt am 2026-08-02; anhand wachsender realer Historie weiter zu validieren.

Die Empfehlung trennt immer:

1. langfristige Attraktivität
2. Preisattraktivität
3. kurzfristiges Einstiegstiming
4. optionalen Depot-Effekt
5. daraus abgeleitete Handlungsempfehlung

Regeln:

- Der Abstand zum Allzeithoch ist Kontext und niemals allein ein Kaufsignal.
- Ein hochwertiges Asset kann langfristig preislich attraktiv sein, obwohl kurzfristig noch keine Bodenbildung vorliegt.
- In solchen Fällen ist eine begründete erste Tranche möglich; pauschales vollständiges Warten ist nicht die einzige Antwort.
- Erlaubte Kategorien sind `Jetzt kaufen`, `Erste Tranche kaufen`, `Bei Bestätigung kaufen`, `Auf konkrete Kaufzone warten`, `Halten`, `Teilweise reduzieren` sowie `Verkaufen oder vermeiden`.
- Eine vage Empfehlung wie nur `Warten` ist nicht ausreichend.
- Jede bedingte Empfehlung nennt messbare Bedingungen, Zonen, Alternativen, Widerlegung und Gültigkeit.
- Depotdaten dürfen Asset-Qualität und Kaufsignal niemals verändern.

## Aktueller Projektstand

Der folgende Dateibestand beschreibt den historischen Ausgangsstand vom 2026-06-14. Der nachweisbare aktuelle Ist-Stand wird in `PROJECT_STATUS.md` geführt; die Roadmap unterscheidet den jeweils belegten Umsetzungsstand von den bis 2026-08-11 fortgeschriebenen Prioritäten und Zielbildern. Historischer Ausgangsstand, belegter Ist-Stand und zukünftiges Zielbild sind bewusst getrennt.

Vorhandene Dateien:

- `app.py`: Hauptanwendung mit Streamlit-Oberfläche, Kursdaten, Analyse, Research-Modul, Portfolio-Modus und Charts.
- `README.md`: Startanleitung und Erklärung der wichtigsten Funktionen.
- `requirements.txt`: Python-Abhängigkeiten.
- `portfolio.example.json`: anonymisierte Beispiel-Datei für den optionalen Portfolio-Modus.
- `search_history.example.json`: anonymisierte Beispiel-Datei für den Suchverlauf.
- `portfolio.json`: portable Depot-Datei im GitHub-kompatiblen Minimalformat; nur Cash, Ticker, Asset-Typ, Positionsgröße und Kaufkurs.
- `search_history.json`: lokale private Suchhistorie, nicht versionieren.
- `start_investment_assistent.bat`: lokales Startskript für die Desktop-Verknüpfung.
- `.streamlit/`: Streamlit-Konfiguration.
- `.yfinance-cache/`: lokaler yfinance-Cache.
- `.venv/`: lokale Python-Umgebung.
- `.git/`: lokales Git-Repository.

Die App ist funktional und startet lokal über Streamlit. Sie nutzt Yahoo Finance über `yfinance`, arbeitet ohne Broker-Anbindung und enthält bereits viele Research-Bausteine.

## Aktuelle Funktionen

- Eingabe von Asset-Name oder Yahoo-Finance-Ticker.
- Automatische Yahoo-Finance-Suche mit auswählbaren Treffern.
- Fallback-Ticker für bekannte Beispiele wie Xiaomi, Nvidia, Palantir, Bitcoin und MSCI World.
- Speicherung erfolgreicher Suchanfragen in `search_history.json`.
- Anzeige von Firmenname, Ticker, Börse und Währung.
- Automatische Asset-Typ-Erkennung für Aktie, ETF, Krypto und unbekannt.
- Manuelle Asset-Typ-Auswahl, falls die automatische Erkennung unsicher ist.
- Historische Kursdaten über `yfinance`.
- Auswahl von Zeitraum und Intervall.
- Währungsmanagement mit EUR-Anzeige plus Originalwährung.
- Wechselkursanzeige, wenn das Asset nicht in EUR gehandelt wird.
- Technische Indikatoren: RSI 14, MACD, Signal-Linie, 50er Durchschnitt, 200er Durchschnitt, Volumenentwicklung, Volatilität.
- Unterstützungen und Widerstände aus lokalen Tiefs und Hochs.
- CRV, Risiko bis Unterstützung und Potenzial bis Widerstand.
- Marktphasen-Erkennung: Bullenmarkt, Bärenmarkt, Korrektur innerhalb eines Aufwärtstrends, Bodenbildungsphase, Seitwärtsmarkt.
- Wahrscheinlichkeiten für verschiedene Szenarien.
- Getrennte Scores für Asset-Qualität, Kaufsignal und Depot-Effekt.
- Portfolio-Modus per Toggle.
- Depot-Effekt mit Cash, Positionsgröße, Portfolioanteil, Klumpenrisiko, geplantem Nachkauf und Cash-Reserve.
- Anfänger-Modus mit einfachen Erklärungen.
- Research-Modul mit Datenqualitäts-Check.
- Research-Modul-Scores: Charttechnik, Momentum, Bewertung oder Zyklus/On-Chain, Fundamentaldaten oder Krypto-Adoption, Makro, News, Risiko, Liquidität.
- Institutionelle Research-Module: Analysten-Konsens, Earnings, Event-Risiko und institutionelle Daten, sofern Daten verfügbar sind.
- Vertrauensscore zur Belastbarkeit der Analyse.
- Unsicherheitsfaktoren: Was könnte diese Analyse widerlegen?
- Bull/Base/Bear-Szenarien.
- Nachkaufzonen.
- Research-Fazit mit Pro/Kontra, entscheidender Marke und konkretem Plan.
- News-Modul über Yahoo-Finance-News mit einfachem Sentiment.
- Makro-Modul mit Nasdaq, US-Zinsen, Dollar-Index und TIP-Proxy.
- Keine automatische Kauf- oder Verkaufsfunktion.

## Offene Aufgaben

### Priorität 1: Klarheit und Stabilität

- Haupt-Dashboard und Research-Modul vereinheitlichen, damit Empfehlungen nicht doppelt oder widersprüchlich wirken. Status: umgesetzt am 2026-06-15.
- Sichtbare Empfehlung klar trennen in Asset-Qualität, Kaufsignal, Research-Handlungsempfehlung und Depot-Effekt. Status: umgesetzt am 2026-06-15.
- Fehlerbehandlung bei Yahoo-Finance-Ausfällen verbessern. Status: umgesetzt am 2026-06-15.
- Datenqualitäts-Check kompakter und sichtbarer machen. Status: umgesetzt am 2026-06-15.
- Analyse-Daten vollständig von Chart-Daten entkoppeln. Status: umgesetzt am 2026-06-15; Chart-Zeitraum steuert nur Visualisierung, Analyse nutzt maximal verfügbare Tageshistorie.
- Suchhistorie in der Sidebar als auswählbare Schnellwahl nutzbar machen. Status: umgesetzt am 2026-06-15.
- Umlaute und sichtbare deutsche Texte prüfen. Status: umgesetzt am 2026-06-15.
- App-Start und Analysefluss regelmäßig testen. Status: umgesetzt am 2026-06-15.
- Laufzeit des vollständigen Analyseaufrufs weiter optimieren. Status: umgesetzt am 2026-08-01; unabhängige externe Research-Abrufe laufen parallel, tägliche Charts verwenden die bereits geladene Langfristhistorie und historische Signal-Backtests werden 30 Minuten zwischengespeichert. Reale ServiceNow-Gegenmessung: 9,31 Sekunden beim ersten und 2,51 Sekunden beim wiederholten Analyseabruf, ohne Änderung der Bewertungslogik oder des Ergebnisumfangs.

### Priorität 2: Score-Qualität

- Gewichtungen der Scores transparent dokumentieren. Status: umgesetzt am 2026-06-15.
- Score-Logik kalibrieren. Status: Basis umgesetzt am 2026-06-15; echte Gewichtungsänderungen erst mit ausreichender Historie.
- Asset-Qualität je Asset-Typ verbessern. Status: umgesetzt am 2026-06-15.
- Kaufsignal weiter von Asset-Qualität abgrenzen. Status: umgesetzt am 2026-06-15.
- Research-Scores stärker erklären: Was bedeutet hoch, mittel oder niedrig? Status: umgesetzt am 2026-06-15.
- Nachkaufzonen robuster machen, wenn keine klaren Kurszonen erkannt werden. Status: umgesetzt am 2026-06-15.
- Bull/Base/Bear-Szenarien stärker aus Trend, Volatilität, Unterstützungen und Widerständen ableiten. Status: umgesetzt am 2026-06-15.

### Priorität 3: Profi-Research

- Fundamentaldaten für Aktien erweitern: Umsatzwachstum, Gewinnwachstum, Margen, Verschuldung, Free Cashflow, Cashbestand, Bewertung. Status: erweitert am 2026-07-01; zusätzliche strukturierte Kennzahlen und transparente Detailausgabe eingebaut.
- ETF-Daten erweitern: TER, Fondsvolumen, Region, Sektor, Diversifikation, langfristige Performance. Status: erweitert am 2026-07-01; strukturierter ETF-Snapshot, YTD/1J/3J/5J, Beta und transparente Detailausgabe eingebaut.
- Bewertungsmodelle ausbauen: historische Bewertung, relative Bewertung und Peer-Vergleich, falls Daten verfügbar sind. Status: erweitert am 2026-07-31; zusätzliche Multiples, Forward-KGV-Abstand, Sektor-/Branchenkontext und klare Nichtverfügbarkeit für Historien-/Peer-Daten eingebaut.
- Analysten-, Earnings-, Event- und institutionelle Module weiter validieren und auf zusätzliche Datenquellen erweitern. Status: validiert am 2026-07-31; Datenabdeckung und Score-Neutralität je Modul ergänzt, fehlende Daten bleiben `Daten nicht verfügbar`.
- News-Modul verbessern: Quelle, Datum, Relevanz, Sentiment-Qualität. Status: erweitert am 2026-07-31; Yahoo-News werden normalisiert und Quelle, Datum, Relevanz sowie Sentiment-Qualität transparent angezeigt.
- Makro-Modul erweitern: Inflation, Realzinsen, Liquidität, Risikoappetit. Status: erweitert am 2026-07-31; Datenabdeckung, Score-Neutralität, Risikoappetit/Nasdaq, Zinsdruck, Dollar-/Liquiditätsdruck und TIP als Inflations-/Realzinsproxy werden transparent ausgewiesen. Direkte Liquiditätsdaten bleiben ohne Quelle `Daten nicht verfügbar`.
- Geopolitik-Modul prüfen, ohne Daten zu erfinden. Status: umgesetzt am 2026-07-31; nutzt nur verfügbare Yahoo-News-Titel als Hinweisquelle, zeigt Datenabdeckung und Score-Neutralität und kennzeichnet fehlende geopolitische Daten klar.
- Risiko- und Liquiditätsmodul verfeinern. Status: erweitert am 2026-07-31; Datenabdeckung, Score-Neutralität, Asset-Typ-Volatilität, CRV-Einordnung, Volumenqualität und fehlende Spread-/Orderbuchdaten werden transparent angezeigt.

### PRIO A: Marktregime-, Innovations-, Blasen- und Makro-Wirkungsmodul

Ziel: Die App soll nicht nur Daten anzeigen, sondern nachvollziehbar erklären, in welchem Marktumfeld ein Asset analysiert wird und wie Makrofaktoren verschiedene Asset-Klassen beeinflussen. Dieses Modul ist PRIO A, weil es zur Grundfähigkeit der Analyse gehört.

Status: Basis umgesetzt und bis 2026-08-02 regressionsgeprüft. Marktregime, Innovations-/Hype-Kontext, Blasenrisiko, Makro-Wirkung und Rohstoff-Kontext sind vorhanden. Zusätzliche belastbare Quellen bleiben ein späterer Ausbau; fehlende Direktdaten werden weiterhin als `Daten nicht verfügbar` angezeigt.

Marktregime-Modul:

- Liquiditätsboom
- Liquiditätsentzug
- Risk-On
- Risk-Off
- Rezessionsangst
- Wachstumsphase
- Defensivphase
- Technologie-Hype
- KI-Hype
- Spekulationsphase

Für jedes erkannte Marktregime anzeigen:

- erkannte Hinweise aus verfügbaren Daten
- Gegenargumente und Unsicherheiten
- betroffene Asset-Klassen
- praktische Bedeutung für Aktien, ETFs, Krypto und Rohstoffe
- Vertrauensgrad der Einordnung

Innovations-Modul:

- echte Innovationsführer erkennen, wenn belastbare Hinweise auf Marktführerschaft, Wachstum, Margen, Produktvorsprung oder strukturelle Nachfrage vorhanden sind
- indirekte Profiteure erkennen, wenn Unternehmen über Infrastruktur, Zulieferung, Plattformen, Energie, Rechenzentren, Halbleiter, Software oder Finanzierung vom Trend profitieren
- reine Hype-Aktien erkennen, wenn Kurs, Medieninteresse oder Story stark sind, aber Fundamentaldaten, Cashflows oder Wettbewerbsvorteile nicht belastbar belegt sind
- fehlende Belege immer als `Daten nicht verfügbar` kennzeichnen

Blasenrisiko-Modul:

- Bewertung
- Medienaufmerksamkeit
- Zuflüsse
- Momentum
- Sentiment

Ausgabe:

- Blasenrisiko 0-10
- kurze Begründung je Teilfaktor
- Datenqualität je Teilfaktor
- Warnhinweis, wenn der Score wegen fehlender Daten nur eingeschränkt belastbar ist

Makro-Wirkungsmodul:

- Zinsen erklären
- Inflation erklären
- Realzinsen erklären
- Dollar erklären
- Liquidität erklären

Auswirkungen erklären auf:

- Aktien
- ETFs
- Krypto
- Rohstoffe

Rohstoff-Modul:

- Öl
- Gas
- Kupfer
- Gold
- Uran

Für Rohstoffe berücksichtigen:

- Angebots- und Nachfragesignale, sofern Daten verfügbar sind
- Konjunkturabhängigkeit
- geopolitische Risiken
- Dollar- und Realzinswirkung
- Inflations- und Liquiditätsumfeld
- asset-spezifische Besonderheiten, z. B. Kupfer als Wachstumsindikator, Gold als Realzins- und Sicherheitsasset, Öl und Gas als Energie- und Geopolitik-Sensitivität, Uran als struktureller Energie- und Angebotsmarkt

Transparenzregeln:

- Keine Daten erfinden.
- Zusammenhänge erklären.
- Korrelationen nicht als sichere Kausalitäten darstellen.
- Makro-Wirkungen als Wahrscheinlichkeiten, Belastungen oder Rückenwind formulieren, nicht als Garantien.
- Bei fehlenden Makro-, Flow-, Sentiment- oder Rohstoffdaten sichtbar `Daten nicht verfügbar` anzeigen.
- Datenquellen, Proxies und Unsicherheiten offenlegen.

### Priorität 4: Krypto-Modul

- Bitcoin-Halving-Zyklus integrieren. Status: Basis umgesetzt am 2026-06-15; erweitert am 2026-08-01 um deterministische Zyklusphase, Zyklusfortschritt, praktische Anlegerbedeutung und klare Unsicherheitsregel.
- Fear & Greed Index prüfen und integrieren, falls zuverlässig verfügbar. Status: geprüft am 2026-07-31; keine belastbare Quelle eingebunden, daher weiterhin `Daten nicht verfügbar`.
- ETF-Flows integrieren, falls eine belastbare Datenquelle verfügbar ist. Status: geprüft am 2026-07-31; keine belastbare Quelle eingebunden, daher weiterhin `Daten nicht verfügbar`.
- On-Chain-Daten integrieren, falls verfügbar. Status: geprüft am 2026-07-31; keine belastbare Quelle eingebunden, daher weiterhin `Daten nicht verfügbar`.
- Krypto-Liquidität und Marktstruktur besser erklären. Status: erweitert am 2026-07-31; Volumenvergleich, Volatilität, 50er/200er-Struktur sowie fehlende Orderbuch-, Spread-, Börsentiefe- und Stablecoin-Liquiditätsdaten werden transparent angezeigt.
- Bei fehlenden Krypto-Daten immer `Daten nicht verfügbar` anzeigen. Status: umgesetzt am 2026-07-31; Krypto-Spezialdaten zeigen Datenabdeckung und Score-Neutralität.

### Priorität 5: Backtesting

- Backtesting-Modul planen. Status: Basis umgesetzt am 2026-07-20.
- Historische Signale speichern. Status: erste In-App-Auswertung historischer Kaufsignal-Buckets umgesetzt am 2026-07-20; lokale Speicherung in `backtest_history.json` umgesetzt am 2026-07-20.
- Trefferquoten berechnen. Status: Basis umgesetzt am 2026-07-20 für Kaufsignal-Buckets über 1, 3, 6 und 12 Monate.
- Renditeanalyse durchführen. Status: Basis umgesetzt am 2026-07-20 über Durchschnittsrendite und Kompaktansicht.
- Drawdown-Analyse ergänzen. Status: Basis umgesetzt am 2026-07-20 als maximaler Drawdown je Backtest-Gruppe.
- Verschiedene Signal-Kombinationen vergleichen. Status: Basis umgesetzt am 2026-07-20 für Kaufsignal, RSI, MACD und CRV.
- Backtesting-Tabelle verdichten und interpretieren. Status: umgesetzt am 2026-07-20 mit Kompaktansicht für beste Trefferquote, schwächste Rendite, größten Drawdown und größte Datenbasis.
- Backtesting-Ausgabe gegen Lern-/Confidence-Kontext prüfen. Status: umgesetzt am 2026-08-01; Backtest-Gruppen zeigen jetzt Historienstatus und Lernhinweis nach Mindestdatenregeln, gespeicherte Backtests zeigen zusätzlich einen Confidence-Kontext.

### Priorität 6: Prognose-Tracking

- Prognosen speichern. Status: umgesetzt am 2026-06-15; neue Prognosen speichern zusätzlich Modul-Scores seit 2026-07-31.
- Szenarien und Kursziele später mit echten Ergebnissen vergleichen. Status: umgesetzt am 2026-07-20 für 1 Woche, 1 Monat, 3 Monate, 6 Monate und 12 Monate.
- Trefferquote je Asset und Modul ausweisen. Status: erweitert am 2026-07-31; Prognose-Tracking zeigt Asset-Typ- und Modul-/Signalgruppen aus ausgewerteten Prognosen, mit Mindestdatenlogik.
- Szenario-Lesart und Fehlursachen ausweisen. Status: erweitert am 2026-08-01; Prognoseauswertungen speichern `scenario_read` und `miss_reason`, Trefferquoten gruppieren zusätzlich nach Szenario-Lesart und Fehlursache.
- Grundlage für ein späteres Lernsystem vorbereiten. Status: umgesetzt; Prognosen fließen in Confidence, Signalanalyse, Segmentanalyse, Fehlmuster und Kalibrierungsvorschläge ein.

### PRIO B: Bedienungsfreier Daten- und Lernbetrieb

Ziel: Die Anwendung soll Markt- und Analysedaten selbstständig sammeln, fällige Prognosen auswerten und ihre historische Qualität fortlaufend messen. Dafür darf weder die Streamlit-Oberfläche geöffnet noch ein Knopf gedrückt werden müssen. Der lokale Rechner muss zum Ausführungszeitpunkt eingeschaltet sein und eine Internetverbindung haben.

Status: technische Basis und erster vollständiger planmäßiger Lauf umgesetzt. Der Lauf vom 2026-08-02 startete selbstständig um 22:30 Uhr, verarbeitete alle 325 vorgesehenen Positionen, speicherte 322 Prognosen, isolierte drei Assets ohne belastbare Kursdaten und endete nach rund 23 Minuten mit Windows-Rückgabecode 0. Wiederholter Dauerbetrieb, wöchentliche Rotation eines größeren Universums und echte ausgereifte Ergebnisfälle bleiben offen.

Bereits vorhanden:

- Separater Hintergrund-Runner außerhalb der Streamlit-Oberfläche sammelt Prognosen und wertet fällige Horizonte aus.
- Definiertes lokales Analyseuniversum mit derzeit 325 Assets aus mehreren Regionen und Größenklassen; ServiceNow (`NOW`) ist ausdrücklich enthalten. Batch-Größe, Pausen, Wiederholungsversuche und Auswertungslimit sind konfigurierbar.
- Lokale SQLite-Datenbank speichert Läufe, unveränderbare Prognose-Snapshots, Zeithorizonte, echte spätere Ergebnisse und dokumentierte Auswertungsfehler.
- Unterbrochene Tagesläufe können fortgesetzt werden; bereits erfolgreich verarbeitete Assets werden nicht unnötig erneut verarbeitet.
- Fehlgeschlagene Einzelassets stoppen nicht den gesamten Lauf; Rate-Limit-Hinweise und fehlende Marktdaten werden protokolliert.
- Rotierendes lokales Protokoll und Betriebskennzahlen für Laufzeit, Verarbeitungsgeschwindigkeit, Fehlerquote, Rate-Limits, Datenbankwachstum und Integrität sind vorhanden. Seit Datenbankschema 3 werden sie zusätzlich am Laufdatensatz gespeichert und in der Prognosequalität angezeigt.
- Die Windows-Aufgabe ist am 2026-08-02 für einen täglichen Lauf um 22:30 Uhr registriert. `StartWhenAvailable` und `WakeToRun` sind aktiv; Windows-Aufwecktimer sind im Netz- und Akkubetrieb freigegeben.
- Automatische Prozess-Neustarts sind auf drei Versuche im Abstand von 15 Minuten begrenzt; parallele Doppelläufe werden verhindert.
- Fällige, bisher nicht ausgewertete Prognosehorizonte werden bei jedem Hintergrundlauf erneut gesucht und können damit später automatisch nachgeholt werden.
- Ausgewertete Fälle fließen bereits automatisch in Trefferquoten, Signalanalyse, Confidence, Fehlmuster und Kalibrierungsvorschläge ein.

Noch offen:

- Status umgesetzt am 2026-08-02: Erster vollständiger planmäßiger Produktionslauf über 325 Assets; 322 erfolgreich, drei Datenfehler (`SO`, `BK`, `ROG.SW`), keine Rate-Limit-Fehler, Fehlerquote 0,92 %, Laufzeit 1.416,73 Sekunden, Datenbankintegrität `ok` und reguläres Wrapper-Ende mit Code 0.
- Wiederkehrendes Wochenuniversum mit festem 325-Referenzkern und kontrolliert erweiterten Wochengruppen aufbauen; jedes reguläre Asset muss jede Woche erneut prognostiziert werden, nicht nur einmalig.
- Den Dauerbetrieb über mehrere Wochen beobachten und Soll-/Ist-Abdeckung, Laufzeit, Rate Limits, Fehlerquote, Datenbankwachstum, Nachholverhalten und erste fällige Auswertungen auswerten.
- Nachweisen, dass der Lauf ohne geöffnete App und ohne Nutzereingriff startet, nach einer Unterbrechung fortsetzt und nach einem verpassten Ausführungszeitpunkt beim nächsten verfügbaren Zeitpunkt anläuft.
- Status umgesetzt am 2026-08-02: Die Prognosequalitätsansicht zeigt letzten Lauf, verarbeitete/fehlgeschlagene Assets, nächsten geplanten Termin und eine verständliche Zustandsmeldung. Die Startseite warnt kompakt bei einem Betriebsfehler.
- Status umgesetzt am 2026-08-02: Fehlende erwartete Läufe, Unterbrechungen, Einzelfehler und mehr als neun Stunden alte `running`-Zustände werden sichtbar gemeldet. Aufeinanderfolgende Problemläufe lösen eine verstärkte Warnung aus.
- Datenlücken transparent dokumentieren. Verpasste historische Prognose-Snapshots dürfen nicht nachträglich so erzeugt werden, als hätten sie zum damaligen Zeitpunkt existiert.
- Status umgesetzt am 2026-08-02: `manage_forecast_backups.py` erstellt geprüfte zeitgestempelte SQLite-Sicherungen ohne automatische Löschung. Wiederherstellung erfolgt nur in eine neue Datei mit Überschreibschutz; der produktive Austausch bleibt bewusst manuell.
- Status umgesetzt am 2026-08-02: Nach jedem Hintergrundlauf wird ein versioniertes, atomar gespeichertes Kalibrierungsprofil aus echten abgeschlossenen Prognoseauswertungen erzeugt. Es segmentiert nach Analyseart, Logikversion, Asset-Typ und Zeitraum, besitzt einen reproduzierbaren Datenfingerabdruck und erzeugt nur manuelle Prüfhinweise gemäß Mindestdatenregeln. Produktionsgewichte und -regeln werden nie automatisch verändert.
- Eine spätere automatische Aktivierung geänderter Bewertungsregeln nur nach ausreichender Datenbasis, Out-of-Sample-Prüfung, dokumentierter Verbesserung, Versionswechsel und sicherer Rückfallmöglichkeit untersuchen.

### PRIO B: Forward-Testing-Modul

- Jede neue Analyse optional als Forward-Test speichern.
  - Status: Basis umgesetzt am 2026-06-15 (`forward_tests.json`, lokal und nicht versioniert).
- Startzeitpunkt, Asset, Ticker, Asset-Typ, Marktphase, Kaufsignal, Asset-Qualität, Depot-Effekt, Vertrauensscore und relevante Modul-Scores erfassen.
  - Status: konsolidiert am 2026-08-01; neue Forward-Tests speichern Modul-Scores, Signal-Snapshot, Szenarien, Kaufzonen und Review-Plan.
- Bull/Base/Bear-Szenarien, Kursziele, Wahrscheinlichkeiten und entscheidende Marken speichern.
  - Status: konsolidiert am 2026-08-01; gespeicherte Szenarien bleiben im Forward-Test-Datensatz erhalten.
- Nach festgelegten Zeiträumen prüfen: 1 Woche, 1 Monat, 3 Monate, 6 Monate und 12 Monate.
  - Status: Basis umgesetzt am 2026-06-15 für 1 Woche, 1 Monat und 3 Monate.
  - Status: Erweiterte Zeiträume umgesetzt am 2026-07-20 für 6 Monate und 12 Monate; alte Historien bleiben kompatibel.
- Tatsächliche Kursentwicklung, maximalen Drawdown, maximale positive Bewegung und Treffer der Szenarien auswerten.
  - Status: erweitert am 2026-08-01; Forward-Test-Auswertungen speichern Rendite, maximale positive/negative Bewegung und Szenario-Lesart.
- Keine Performance-Werte erfinden, wenn Kursdaten fehlen.
- Ergebnisse getrennt nach Asset-Typ, Marktphase und Signalart ausweisen.
  - Status: erweitert am 2026-08-01; Signalanalyse zählt Forward-Test-Ergebnisse zusätzlich nach Asset-Typ, Szenario-Lesart und Modulgruppen.

### PRIO B: Decision-Tracking-Modul

- Nutzerentscheidungen optional protokollieren: gekauft, nicht gekauft, gehalten, verkauft, beobachtet.
  - Status: Basis umgesetzt am 2026-06-15 (`decision_history.json`, lokal und nicht versioniert).
- Zeitpunkt, Entscheidungsgrund, angezeigte Empfehlung und relevante Scores speichern.
  - Status: konsolidiert am 2026-08-01; Decision-Tracking speichert App-Aktion, Professional-Decision-Kontext, Asset-Qualität, Kaufsignal, Confidence, Marktphase, Signal-Snapshot und Modul-Scores.
- Optionalen Nutzerkommentar ermöglichen.
  - Status: umgesetzt; `user_note` bleibt im lokalen Decision-Datensatz erhalten.
- Später vergleichen, ob die Entscheidung gegen oder mit der App-Einschätzung getroffen wurde.
  - Status: erweitert am 2026-08-01; Auswertungen speichern Entscheidungsexposure, App-Exposure und Alignment `mit/gegen App-Einschätzung`.
- Keine Broker-Anbindung und keine automatische Ausführung.
- Daten lokal und transparent speichern.

### PRIO B: Prognose-Tracking-Modul

- Prognosen aus Bull/Base/Bear-Szenarien dauerhaft speichern.
  - Status: Basis umgesetzt am 2026-06-15 (`prediction_history.json`, lokal und nicht versioniert).
- Kursziele, Wahrscheinlichkeiten, Zeithorizont und entscheidende Widerlegungsmarken erfassen.
  - Status: umgesetzt; neue Prognosen speichern Szenarien, Wahrscheinlichkeiten, Kursziele, Zeithorizonte und entscheidende Marken. Fehlende Ziele bleiben `Daten nicht verfügbar`.
- Später prüfen, welches Szenario am besten getroffen hat.
  - Status: Basis umgesetzt am 2026-06-15 für 1 Woche, 1 Monat und 3 Monate.
  - Status: Erweiterte Zeiträume umgesetzt am 2026-07-20 für 6 Monate und 12 Monate; alte Prognosehistorien werden beim Auswerten ergänzt.
- Trefferquote je Modul, Signalart, Asset-Typ und Marktphase berechnen.
  - Status: erweitert am 2026-08-01; Prognoseauswertungen werden nach Asset-Typ, Marktphase, Szenario-Lesart sowie Modul- und Signalgruppen zusammengefasst und beachten die Mindestdatenregeln.
- Fehlprognosen sichtbar machen und Ursachen kategorisieren.
  - Status: Basis umgesetzt am 2026-07-20: verfehlte Historienfälle werden nach Asset-Typ, Marktphase, Kaufsignal, RSI, MACD, Volatilität, CRV, News und Makro gruppiert.
  - Status: erweitert am 2026-08-01; einzelne Prognose-Reviews speichern eine einfache Fehlursache aus Marktphase, Signal-Snapshot, Modul-Scores oder Kursentwicklung.
- Nur echte nachträgliche Kursdaten verwenden; fehlende Daten als `Daten nicht verfügbar` kennzeichnen.

### PRIO B: Kalibrierungs- und Lernmodul

Status: funktionale Basis umgesetzt und bis 2026-08-02 regressionsgeprüft. Weitere fachliche Kalibrierung wartet auf ausreichend viele echte spätere Auswertungen; Gewichtungen werden nicht automatisch geändert.

- Aus Forward-Testing, Decision-Tracking und Prognose-Tracking lernen, welche Signale zuverlässig sind.
- Score-Gewichtungen nicht automatisch ändern, sondern Anpassungsvorschläge erzeugen.
- Häufige Fehlerquellen erkennen, z. B. schwache Marktphasen-Erkennung, schlechte Krypto-Bewertung, unbrauchbare News-Signale oder übergewichtete technische Signale.
- Kalibrierungsbericht anzeigen: Was funktioniert gut? Was funktioniert schlecht? Welche Module brauchen Verbesserung?
  - Status: Basis umgesetzt am 2026-06-15: lokaler Kalibrierungsstatus zählt Forward-Tests, Entscheidungen, Prognosen und ausgewertete Zeiträume.
  - Status: Signalbasierte Kalibrierung umgesetzt am 2026-07-19: ähnliche Setups werden nach RSI, MACD, Marktphase, Volatilität, News, Makro und CRV aufgeschlüsselt; Hinweise bleiben ab Mindestfallzahlen transparent und verändern keine Gewichtungen automatisch.
  - Status: Backtest-Historie integriert am 2026-07-20: gespeicherte Backtest-Gruppen werden als separater Lernkontext mit Fallzahl, Trefferquote, Rendite und Drawdown angezeigt.
  - Status: Kalibrierungsvorschläge aus Fehlmustern umgesetzt am 2026-07-31: häufige Fehlmuster erzeugen manuelle Prüfhinweise mit Datenbasis, Fehlquote und Begründung; Gewichtungen werden nicht automatisch geändert.
  - Status: konsolidiert am 2026-08-01; Lern- und Kalibrierungsansichten nutzen zusätzlich Szenario-Lesart, Fehlursache und Decision-Alignment aus den neuen Review-Feldern.
- Lernlogik transparent machen und keine Blackbox-Entscheidungen treffen. Status: konsolidiert am 2026-07-31; `Lernlogik-Guardrails` zeigen dokumentierte Fälle, ausgewertete Fälle, Mindestdatenlogik und das Verbot automatischer Gewichtungsänderungen.
- Änderungen an Bewertungslogik erst nach Dokumentation und Tests übernehmen.

### PRIO B: Kontrolliertes echtes Lernsystem und wiederkehrendes Wochenuniversum

Ziel: Aus unveränderbaren, später mit echten Ergebnissen geprüften Prognosen soll schrittweise ein kontrolliert lernendes System entstehen. Es soll nachweislich zuverlässigere und besser kalibrierte Empfehlungen liefern als die heutige Regelbasis und als einfache Vergleichsstrategien. Eine hohe angezeigte Wahrscheinlichkeit ist nur zulässig, wenn sie auf ungesehenen Daten tatsächlich entsprechend häufig eingetreten ist. Es gibt keine Treffer- oder Renditegarantie; bei unzureichender Evidenz muss das System ausdrücklich auf eine Empfehlung verzichten.

Status: noch nicht als lernendes System umgesetzt. Vorhanden sind ein versioniertes Wochenuniversum mit 1.726 Assets, fünf deterministische Kohorten, tägliche Fälligkeitsprüfung, unveränderbare Prognose-Snapshots, ein vor jedem Lauf erneut geprüfter L0-Point-in-Time-Messvertrag, fünf spätere Auswertungszeiträume, feste Trend-/Marktbenchmarks, eine ausdrücklich unkalibrierte Rohwahrscheinlichkeit samt Brier-/Log-Loss-Messung, SQLite-Persistenz, ein rein beobachtendes Kalibrierungsprofil, ein append-only Shadow-Modellregister und eine rollierende beobachtende Drift-/Qualitätsüberwachung. Der 325-Asset-Referenzkern ist der Montagskohorte zugeordnet; die Erweiterung verteilt sich auf vier weitere Wochentage. Seit 2026-08-07 existiert zusätzlich eine strikt getrennte, fingerprintete Recovery-Grundlage für historische OHLCV-Daten mit explizitem Cutoff, die technisch von Forward-Prognosen und Trefferquoten ausgeschlossen bleibt. Reale mehrwöchige Validierung des neuen Wochenbetriebs, gereifte Benchmark- und Wahrscheinlichkeitsfälle, eigene Horizontmodelle, Trainingspipeline, tatsächlich laufende Shadow-Challenger und kontrollierte Modellfreigabe fehlen weiterhin.

Der L2-Lernbestand ist technisch vorbereitet, aber noch leer: Er akzeptiert ausschließlich gereifte, verifizierte Point-in-Time-Verträge, fingerprintet den berechtigten Bestand und trennt Legacy, offene, unbrauchbare sowie ungültige Zeilen. Ein erstes Shadow-Forschungsgate verlangt konservativ mindestens 1.000 Fälle, zwölf Beobachtungswochen, je 200 positive und negative Fälle und 90 % Wahrscheinlichkeitsabdeckung; eine spätere Power-Analyse bleibt zusätzlich Pflicht. Walk-Forward-Fenster verwenden ausschließlich Zeitreihenfolge und Purging noch nicht bekannter überlappender Labels. Produktionsaktivierung bleibt unabhängig vom Gate verboten.

#### A. Wiederkehrendes Wochenuniversum statt einmaliger Breite

- Das bestehende 325-Asset-Universum als festen Referenzkern erhalten. Die am 2026-08-02 erfolgreich prognostizierten 322 Assets werden nicht nur einmalig, sondern in einem festen wöchentlichen Rhythmus erneut prognostiziert; vorübergehend fehlgeschlagene Assets bleiben mit begrenzten Wiederholungen im Universum.
- Das umgesetzte Gesamtuniversum von 1.726 liquiden und eindeutig identifizierten Aktien, ETFs und großen Kryptowährungen ist die erste Betriebsstufe, nicht die langfristige Obergrenze. Die nächste kontrollierte Zielstufe liegt bei ungefähr 2.500 bis 3.500 regelmäßig prognostizierten Assets.
- Das Gesamtuniversum in fünf stabile Wochengruppen mit ungefähr 300 bis 500 Assets aufteilen: Montag Gruppe A, Dienstag Gruppe B, Mittwoch Gruppe C, Donnerstag Gruppe D, Freitag Gruppe E; in der Folgewoche beginnt dieselbe Rotation erneut.
- Jedes reguläre Asset genau einmal pro Kalenderwoche neu prognostizieren. Depotwerte, Favoriten oder aktive Swing-Setups dürfen in einer getrennt gekennzeichneten Prioritätsgruppe häufiger geprüft werden, dürfen dadurch aber die allgemeine Qualitätsstatistik nicht unbemerkt übergewichten.
- Gruppenzuordnung deterministisch, versioniert und nachvollziehbar speichern. Änderungen am Universum, Tickerwechsel, Fusionen, Delistings, Klassenaktien und zeitweise Datenlücken mit Gültigkeitszeitraum dokumentieren, damit kein Survivorship Bias entsteht.
- Region, Börsenkalender, Zeitzone, Währung, Asset-Typ, Branche, Liquidität und Datenabdeckung bei der Gruppierung berücksichtigen. Börsengeschlossene Assets werden nicht mit veralteten Kursen als neue Prognose ausgegeben.
- Laufzeit, Yahoo-Fehlerquote, Rate Limits, Datenbankwachstum und Erfolgsquote zunächst mit kleinen zusätzlichen Gruppen messen. Erweiterung stufenweise freigeben und bei Überlastung automatisch pausieren, nicht durch aggressivere Requests erzwingen.
- Verpasste Gruppen beim nächsten sicheren Termin nachholen, aber niemals historische Prognosen rückwirkend erzeugen. Dashboard und Protokoll zeigen Soll-/Ist-Abdeckung je Woche, ausgelassene Gruppen, Fehlassets und frühesten Nachholtermin.

#### A.1 Mehrstufige Universumsarchitektur statt fester Obergrenze

Status: geplant als Erweiterung des umgesetzten 1.726-Asset-Wochenuniversums. Jede Skalierungsstufe benötigt vor der nächsten Erweiterung reale Laufzeit-, Abdeckungs-, Datenqualitäts- und Providerlast-Nachweise.

- **Ebene A – Discovery/Monitoring:** perspektivisch ungefähr 5.000 bis 10.000 beobachtbare liquide Assets, soweit Datenrechte, Datenqualität, Laufzeit und Providerlast dies zuverlässig erlauben. Enthalten sind liquide Aktien aus USA, Europa, Asien/Pazifik und weiteren relevanten Märkten, Large Caps, Mid Caps, ausgewählte liquide Small Caps, wichtige breite und sektorale ETFs sowie große liquide Kryptowährungen.
- **Ebene B – reguläres Prognoseuniversum:** zunächst ungefähr 2.500 bis 3.500 qualitätsgeprüfte, regelmäßig prognostizierte Assets. Die genaue Größe entsteht aus realer Kapazität und Qualität; sie ist weder künstliches Mindestziel noch dauerhafte Obergrenze.
- Penny Stocks, extrem illiquide Werte, sehr große Spreads, dauerhaft unzuverlässige Daten, tote/delistete Listings, exotische Kleinstprodukte sowie Hebel-/Inverse-Produkte bleiben im normalen Prognosesystem ausgeschlossen oder hart gesperrt.
- Das Discovery-Universum erhält eine günstige Daten-/Liquiditäts-/Identitätsprüfung. Nicht jedes beobachtete Asset wird jede Woche vollständig analysiert.
- Ein Vorfilter darf Laufzeit priorisieren, aber keine unbemerkte Auswahlverzerrung erzeugen. Zusätzlich wird regelmäßig eine kleine, vorab definierte und reproduzierbare Kontrollstichprobe aus unauffälligen beziehungsweise abgelehnten Assets vollständig analysiert.
- Kontrollstichprobe und reguläre Auswahl werden nach Region, Branche, Größenklasse, Asset-Typ, Liquidität und Datenqualität verglichen. So wird sichtbar, ob der Vorfilter Chancen oder Marktgruppen systematisch übersieht.
- Nicht nur US-Mega-Caps aufnehmen. Regionen, Branchen, große Marktführer, etablierte Mid Caps, qualitätsgeprüfte Wachstumsunternehmen und relevante breite/segmentbezogene ETFs bleiben ausreichend vertreten.
- Universumszugehörigkeit, Auswahlgrund, Ausschlussgrund, Vorfilterversion, Kontrollstichprobenstatus und Gültigkeitszeitraum Point-in-Time speichern. Alte Universumsstände und Prognosen niemals rückwirkend umdeuten.

#### A.2 Analysefrequenz und Prognosehorizont entkoppeln

Status: am 2026-08-11 umgesetzt. Der Runner filtert jeden neuen Analysesnapshot vor der append-only Speicherung durch den versionierten Horizontkalender `forecast-horizon-calendar-2026.08.11-v1`. Bestehende Snapshots und ihre offenen Auswertungen bleiben unverändert; die produktive Vorprüfung bestätigt weiterhin 2.270 Prognosen, 523 Auswertungen, null ungültige Messverträge und SQLite-Integrität `ok`.

| Prognosehorizont | Neuer Snapshot | Zieluniversum | Auswertung |
|---|---:|---|---:|
| 1 Woche | jede Woche | sehr breit | exakt nach 1 Woche |
| 1 Monat | alle 2 Wochen | breit | exakt nach 1 Monat |
| 3 Monate | einmal pro Monat | stärker qualitätsgeprüft | exakt nach 3 Monaten |
| 6 Monate | einmal alle 3 Monate | nur `long_horizon_eligible` | exakt nach 6 Monaten |
| 12 Monate | einmal alle 6 Monate | besonders geeignete `long_horizon_eligible` Assets | exakt nach 12 Monaten |

Verbindliche Regeln:

- Eine wöchentliche Analyse startet künftig nicht automatisch fünf neue Horizonte. Fälligkeitsprüfung und spätere Auswertung bleiben täglich beziehungsweise zum tatsächlichen Zielzeitpunkt aktiv, unabhängig davon, wann ein neuer Horizont gestartet wird.
- Horizontkalender, Startfrequenz, Auswahluniversum und Eignungslogik werden versioniert. Ein verpasster Start wird nicht rückdatiert; er bleibt Lücke oder beginnt mit dem tatsächlichen späteren Beobachtungszeitpunkt.
- Die Anzahl je Horizont wird nicht starr fest verdrahtet. Sie ergibt sich aus Datenqualität, Eignung, diversifizierter Abdeckung und real gemessener Laufzeitkapazität.
- Neues Feld `long_horizon_eligible` mit versionierter Begründung. Kriterien sind ausreichend lange Historie, eindeutige Unternehmens-/Listing-Identität, Liquidität, hohe Datenqualität, vollständige und zuverlässige Unternehmens-/Finanzdaten, langfristig analysierbares Geschäftsmodell sowie keine extreme Sondersituation oder dauerhaft problematische Abdeckung.
- `long_horizon_eligible = false` erzwingt keine 6M-/12M-Prognose. Fehlende Eignung ist kein negatives Unternehmensurteil, sondern eine dokumentierte Grenze der verfügbaren langfristigen Evidenz.
- Das Long-Horizon-Universum umfasst nicht nur Mega Caps, sondern diversifiziert große Marktführer, etablierte Mid Caps, geeignete Wachstumsunternehmen, Regionen, Branchen sowie breite und sektorale ETFs als Markt-/Vergleichsinstrumente.
- Überlappende Fälle dürfen gespeichert werden, gelten bei Signifikanztests aber nicht automatisch als unabhängig. Walk-Forward, Purging und zeitliche beziehungsweise Emittenten-/Markt-Cluster berücksichtigen die Abhängigkeit.
- Reine Fallzahl und geschätzte effektive Stichprobengröße getrennt ausweisen, wenn Überlappung oder gemeinsame Marktbewegung die statistische Information reduziert.
- Neue Felder und Rhythmen nur nicht löschend einführen. Bei historischen Daten bleibt unbekannt, ob eine heutige Eignungs- oder Identitätsinformation damals vorlag; keine rückwirkende Anreicherung als scheinbarer Point-in-Time-Fakt.

#### B. Unveränderbarer Point-in-Time-Datenvertrag

- Für jede Prognose ausschließlich Informationen speichern, die zum tatsächlichen Erstellungszeitpunkt verfügbar waren: bereinigter Kursstand, Quellen- und Veröffentlichungszeitpunkte, Datenalter, fehlende Felder, Marktphase, Asset-Metadaten, alle verwendeten Merkmale, Modul-Scores, Szenarien, Empfehlung, Confidence, Zielhorizont, Logik- und Feature-Schema-Version.
- Rohdatenherkunft, Transformationen und Verfügbarkeitsflags so dokumentieren, dass ein Training später reproduzierbar ist. Nachträglich korrigierte Daten dürfen den alten Eingabesnapshot nicht still überschreiben.
- Prognosen append-only speichern. Eine neue Wochenprognose überschreibt weder die Vorwoche noch deren offene 1-Wochen-, 1-Monats-, 3-Monats-, 6-Monats- oder 12-Monats-Prüfung.
- Eindeutige Schlüssel aus Asset-ID, Prognosezeitpunkt, Analyseart, Horizont, Logikversion und Feature-Schema verwenden. Doppelte oder widersprüchliche Snapshots ablehnen.
- Historische Datenlücken, Quellenausfälle und eingeschränkte Abdeckung als Merkmale und Qualitätsstatus behalten; fehlende Werte niemals nachträglich mit Zukunftswissen auffüllen.
- Trainingsdaten, Auswertungsdaten, Modellartefakte und Produktionsprognosen schema- und versionssicher trennen. Jede Schemaänderung benötigt eine nicht löschende Migration und Regressionstests.

#### C. Fachlich passende Ergebnisdefinitionen

- Jede fällige Prognose mit echten späteren, nach Möglichkeit um Splits und Ausschüttungen bereinigten Marktdaten auswerten; Unternehmensereignisse und Tickerwechsel nachvollziehbar behandeln.
- Die 1-Wochen-Auswertung beurteilt nur den 1-Wochen-Horizont. Sie darf eine noch offene 1-, 3-, 6- oder 12-Monats-Empfehlung nicht pauschal als richtig oder falsch markieren.
- Einstiegsanalyse, Long-Term-Analyse und Swing Trade Finder getrennte Zielgrößen geben:
  - Einstiegsanalyse: Richtung, erwarteter Kursbereich, Ziel-/Risikomarken, Rendite und Abweichung je Horizont.
  - Swing: Eintrittsbedingung, Ziel-vor-Stop, Rendite nach realistischen Kosten, Expected Value, Drawdown und Ablauf.
  - Long-Term: Gesamtrendite und Überschussrendite gegen passenden Benchmark, Drawdown, These/Widerlegung und Kapitalverlust über den vorgesehenen Mehrjahreshorizont.
- Empfehlungskategorien zusätzlich als Handlungsentscheidung bewerten: Qualität der positiven Empfehlungen, vermiedene Fehlkäufe, verpasste Chancen, Abdeckung und Nutzen der bewussten Kategorie `keine Empfehlung`.
- Fehlende oder nicht belastbare spätere Marktdaten als offen/fehlend behandeln, niemals als Treffer oder Fehler. Benutzerentscheidungen und spätere Käufe sind keine objektiven Trainingslabels.
- Bei handelbaren Strategiemetriken realistische Gebühren, Spread und Slippage als versionierte Annahmen einbeziehen; Bruttorendite und Nettorendite getrennt zeigen.

#### D. Vergleichsmaßstäbe und belastbare Qualitätsmetriken

- Jede lernende Variante exakt auf denselben Assets, Zeitpunkten, Horizonten und Kosten gegen mindestens folgende Referenzen prüfen: bestehende Regelversion, immer steigende Richtung, keine Änderung, einfaches Momentum beziehungsweise Trendregel und passender Markt-/Sektor-/Asset-Benchmark.
- Nicht nur Richtungstrefferquote verwenden. Mindestens auswerten: Balanced Accuracy, Precision und Recall der freigegebenen Empfehlungen, Brier Score, Log Loss, Kalibrierungsfehler, Abdeckung, Enthaltungsquote, Rendite, Überschussrendite, Expected Value, Profitfaktor, Drawdown und Opportunitätskosten.
- Angezeigte Wahrscheinlichkeiten über Reliability-Diagramme und Wahrscheinlichkeitsgruppen prüfen: Aussagen mit beispielsweise 70 % müssen auf ungesehenen Fällen langfristig ungefähr in dieser Größenordnung eintreten.
- Unsicherheit mit Konfidenzintervallen ausweisen. Abhängige Assets derselben Woche, Branche oder Marktbewegung gemeinsam clustern; 2.000 korrelierte Prognosen derselben Woche dürfen nicht wie 2.000 unabhängige Experimente behandelt werden.
- Ergebnisse nach Analyseart, Modellversion, Horizont, Asset-Typ, Region, Branche, Liquidität, Marktphase und Datenqualität segmentieren. Kleine Segmente klar als nicht belastbar kennzeichnen und nicht durch eine gute Gesamtzahl verdecken.
- Mehrfachtests und wiederholte Modellauswahl berücksichtigen. Eine zufällig beste von vielen Varianten darf nicht ohne Korrektur und erneute ungesehene Prüfung freigegeben werden.

#### E. Trainings- und Validierungsarchitektur ohne Zukunftswissen

- Pro Analyseart und Prognosehorizont getrennte Kandidaten trainieren; fachlich unterschiedliche Ziele nicht in eine einzige undurchsichtige Gesamtvorhersage mischen.
- Mit transparenten Basismodellen beginnen, danach höchstens kontrolliert komplexere Kandidaten ergänzen. Komplexität ist nur zulässig, wenn sie auf ungesehenen Daten einen stabilen Zusatznutzen liefert.
- Daten ausschließlich zeitlich teilen: älteste Perioden zum Trainieren, spätere zur Validierung und die jüngste, bis dahin unangetastete Periode als Test. Kein zufälliges Mischen von Zeilen über die Zeit.
- Walk-Forward-Validierung mit mehreren aufeinanderfolgenden Prüfperioden verwenden. Überlappende Prognosehorizonte durch zeitliche Sperrbereiche/Purging trennen, damit zukünftige Kursbewegungen nicht indirekt in Training oder Merkmalsauswahl gelangen.
- Feature-Auswahl, Normalisierung, Umgang mit fehlenden Werten, Klassenbalance, Hyperparameterwahl und Wahrscheinlichkeitskalibrierung ausschließlich innerhalb der jeweiligen Trainings-/Validierungsperiode anpassen.
- Eine endgültige Testperiode nur einmal für die Freigabeentscheidung verwenden. Nach Einsicht in ihr Ergebnis gilt sie für die nächste Modellrunde nicht mehr als unangetastet.
- Wahrscheinlichkeiten auf getrennten Kalibrierungsdaten kalibrieren. Wenn Kalibrierung, Datenabdeckung oder Verteilungsnähe nicht ausreichen, nur eine qualitative Einschätzung oder `keine belastbare Prognose` ausgeben.
- Data Leakage, Look-ahead Bias, Survivorship Bias, Auswahlbias, Datenrevisionsbias und Regimeüberanpassung mit automatisierten Prüfungen und dokumentierten Negativtests absichern.

#### F. Datenreife und Freigabeschwellen

- Die bisherigen Grenzen 20/50 bleiben ausschließlich frühe Diagnose- und manuelle Hinweisstufen. Sie reichen weder für echtes Training noch für eine produktive Modellfreigabe.
- Vor jeder Lernstufe eine Ziel- und Segment-spezifische Mindestfallzahl durch Power-/Unsicherheitsanalyse festlegen. Zusätzlich sind ausreichend viele getrennte Wochen, unterschiedliche Marktbedingungen und vollständige Point-in-Time-Merkmale erforderlich.
- Für einen ersten 1-Wochen-Kandidaten mindestens mehrere Monate wiederkehrender Wochenkohorten verlangen; für 1-, 3-, 6- und 12-Monats-Modelle jeweils warten, bis deren eigene Horizonte in ausreichender Zahl tatsächlich ausgereift sind.
- Keine Modellfreigabe allein wegen hoher Trefferquote. Der Kandidat muss auf mehreren aufeinanderfolgenden Walk-Forward-Fenstern mindestens die bestehende Regelbasis und relevante einfache Referenzen bei vorab festgelegten Hauptmetriken schlagen.
- Der Vorteil muss nach Kosten, mit Konfidenzintervall und ohne kritische Verschlechterung wichtiger Asset-/Regime-Segmente bestehen. Wenn die Evidenz nicht reicht, bleibt die bisherige Regelversion aktiv.
- Eine Bezeichnung wie `hohe Wahrscheinlichkeit` nur zulassen, wenn die entsprechende Wahrscheinlichkeitsgruppe auf ungesehenen Daten ausreichend groß, kalibriert und stabil ist. Fallzahl, Prüfzeitraum und Unsicherheit müssen sichtbar sein.

#### G. Champion-Challenger-, Shadow- und Freigabebetrieb

- Die aktuelle versionierte Regelbasis bleibt zunächst `Champion`. Lernende Kandidaten laufen als `Challenger` parallel im Shadow-Modus und beeinflussen weder sichtbare Empfehlung noch Produktionsscore.
- Training, Auswertung und Produktionsfreigabe als getrennte Prozesse ausführen. Ein Hintergrundlauf darf nicht aus einem einzelnen neuen Fehler unmittelbar Gewichte oder Modell austauschen.
- Ein lokales Modellregister führen: Modell-ID, Analyseart, Horizont, Code-/Logikversion, Feature-Schema, Trainingszeitraum, Datenfingerabdruck, Hyperparameter, Kalibrierung, Referenzmodelle, Prüfmetriken, bekannte Grenzen und Artefakt-Hash.
- Jede Freigabe benötigt einen reproduzierbaren Bericht, bestandene Sicherheits-/Leakage-/Regressionstests, dokumentierten Mehrwert, manuelle Zustimmung und eine neue Produktionsversion.
- Neue Version zunächst begrenzt als Canary oder parallele Empfehlung testen. Alte Version und Rollback-Anweisung unverändert aufbewahren; bei Qualitätsabfall, Datenfehler oder Drift sofort auf die letzte freigegebene Version zurückfallen.
- Später darf Training regelmäßig automatisiert werden. Die Aktivierung eines neuen Produktionsmodells bleibt so lange manuell, bis ein eigener, streng getesteter Freigabeautomat mit denselben Gates ausdrücklich beschlossen wurde.

#### H. Laufende Überwachung und kontrolliertes Nachlernen

Technischer Stand 2026-08-09: `forecast_monitoring.py` vergleicht je Analyseart und Horizont ein 28-Tage-Fenster mit den vorherigen 84 Tagen. Es überwacht Richtungstreffer, Trendregel-Vorsprung, Überschussrendite, Brier Score, Log Loss, Wahrscheinlichkeitsabdeckung, Eingabe-/Segmentverteilungen, numerische Scoreverschiebungen, Auswertungsrückstand, technische Auswertungsfehler, Asset-Erfolgsquote und Rate-Limits. Mindestens 50 Ergebnis-/Wahrscheinlichkeitsfälle beziehungsweise 100 Eingabefälle je Vergleich verhindern Fehlalarme aus Kleinstichproben; sonntags nur kalendarisch fällige Fälle werden erst nach drei Tagen als überfällige Abdeckung gewarnt. Der Bericht wird automatisch in das Kalibrierungsprofil aufgenommen und in der Prognosequalität angezeigt. Er ist ausschließlich beobachtend und kann weder Regeln noch Modelle oder Produktion ändern. Reale Driftbewertung ist mangels gereifter Vergleichsfenster noch nicht möglich; ein explizites Out-of-Distribution-Enthaltungsgate für lernende Modelle bleibt offen.

- Daten-, Feature-, Prognose-, Kalibrierungs- und Ergebnisdrift je Modell/Horizont messen. Änderungen von Datenquellen, stark steigende Fehlraten oder unbekannte Eingabeverteilungen als Betriebsfehler behandeln.
- Qualitätskennzahlen über rollierende Zeitfenster und getrennte Marktphasen überwachen. Eine gute Langzeitzahl darf einen aktuellen Modellverfall nicht verdecken.
- Automatische Warnungen für zu geringe Abdeckung, verschlechterten Brier Score/Log Loss, sinkenden Referenzvorteil, Segmentausfälle, ungewöhnliche Enthaltungsquote und Datenlücken vorsehen.
- Nachtraining nur nach festem Zeitplan oder dokumentiertem Drift-Auslöser, niemals nach einer einzelnen Fehlprognose. Jede Runde verwendet eine neue Modellversion und durchläuft erneut alle Validierungs- und Freigabegates.
- Historische Produktionsprognosen, Ergebnisse und Modellartefakte nicht automatisch löschen. Sicherungen, Integritätsprüfung, Speichergrenzen und nachvollziehbare Aufbewahrungsentscheidungen vor automatischem Training ergänzen.

#### I. Transparente Empfehlungen und sichere Enthaltung

- Jede lernende Empfehlung zeigt Analyseart, Horizont, Modellversion, Datenstand, Abdeckung, kalibrierte Wahrscheinlichkeit, Unsicherheit und die wichtigsten nachvollziehbaren Einflussfaktoren.
- Historische Modellqualität klar von der aktuellen Einzelprognose trennen. Eine historische Trefferquote ist keine Garantie für dieses Asset.
- Harte Datenqualitäts-, Liquiditäts-, Ereignis-, Unsicherheits- und Out-of-Distribution-Gates vor jede Empfehlung setzen. Bei Verletzung lautet das Ergebnis `keine belastbare Empfehlung` statt einer erzwungenen Richtung.
- Confidence nicht aus Modellwahrscheinlichkeit allein ableiten. Kalibrierung, Datenabdeckung, Verteilungsnähe, Segmentreife und Modellstabilität müssen gemeinsam berücksichtigt werden.
- Keine automatische Order, kein verborgenes persönliches Risikoprofil und keine Optimierung auf Nutzerreaktionen. Lernen optimiert nach vorab dokumentierten fachlichen Ergebnisgrößen.

#### J. Umsetzungsetappen

1. **L0 – Messvertrag:** Point-in-Time-Feature-Schema, eindeutige Labels, Benchmarks, Kostenannahmen, Qualitätsflags und Leakage-Tests verbindlich definieren.
2. **L1 – Wochenuniversum:** festen 325-Referenzkern und kontrolliert erweiterte Gruppen wiederkehrend einmal pro Woche betreiben; Abdeckung, Last und Datenqualität sichtbar machen.
3. **L2 – Evaluationsdatensatz:** ausgereifte Ergebnisse reproduzierbar exportieren, segmentieren und gegen einfache Referenzen mit Unsicherheit auswerten; noch kein lernendes Produktionsmodell.
4. **L3 – Shadow-Lernen:** erste transparente Kandidaten je Horizont mit zeitlicher Walk-Forward-Prüfung und kalibrierten Wahrscheinlichkeiten parallel zur Regelbasis laufen lassen.
5. **L4 – Kontrollierte Freigabe:** nach nachgewiesenem ungesehenem Mehrwert, manueller Freigabe, Canary-Betrieb und Rollback erstmals eine versionierte lernende Empfehlung zulassen.
6. **L5 – Sicheres Nachlernen:** Drift-Überwachung und reproduzierbares periodisches Training automatisieren; Produktionsaktivierung weiterhin durch formale Freigabegates schützen.

Abhängigkeiten: stabiler wiederkehrender Hintergrundbetrieb, ausreichend große und ausgereifte Point-in-Time-Historie, geklärte Datenrechte und Quellenqualität, modelltypische Ergebnisdefinitionen, getestete Migrationen, Backups sowie eine von der normalen App getrennte Trainings- und Modellregister-Architektur.

### PRIO B: Swing Trade Finder

Ziel: Die App soll objektiv handelbare Chancen identifizieren, ohne einen relativ besten, aber fachlich schwachen Kandidaten zu erzwingen.
Status: automatischer Long-Swing-v1-Scanner am 2026-08-02 umgesetzt, am 2026-08-09 um den append-only Forward-Betrieb und am 2026-08-11 um die vollständige Tiefenanalyse aller Grobfiltertreffer, einen 2.520-Asset-Bestand sowie den Assetklassen-Funnel erweitert. Die vier regionalen Echtläufe wurden mit der neuen Pipeline erfolgreich belegt; 2.517 von 2.520 Bereichszuordnungen lieferten Kursdaten, null Rate-Limits traten auf. Neben EWL wurde LT.NS als zweites echtes Forward-Signal gespeichert. Offen sind vor allem genügend gereifte echte Forward-Ergebnisse, vollständige historische Exit-Währungskurse und weitere reale Marktphasen.

Kritische Kursbasis-Korrektur am 2026-08-11: Der konkrete Fall `USY5217N1183` wurde auf eine Listing-Verwechslung plus veraltete Tageskerze zurückgeführt. Der Scanner hatte `LT.NS`, die indische Stammaktie in INR, analysiert und den Schlusskurs nur in Euro umgerechnet; die genannte ISIN bezeichnet dagegen ein anderes GDR-Listing. Neue Setups werden nun vor jeder CRV-Berechnung abgelehnt, wenn die letzte abgeschlossene Tageskerze für Börsenregion beziehungsweise bekannte Tickersuffixe veraltet ist oder OHLC-Werte Tageshoch/-tief widersprechen. Die Oberfläche nennt den Wert nicht mehr `Aktueller Kurs`, sondern `Signalkurs (Schluss)`, zeigt analysiertes Listing, Börse, Originalwährung, Kursquelle und Signaltag und warnt bei Fremdwährungen ausdrücklich, dass die Euro-Umrechnung kein Trade-Republic-/LS-Exchange-Livekurs ist. Bei der manuellen Trade-Bestätigung muss Ticker oder ISIN zum analysierten Listing passen; ein Einstieg auf oder unter dem System-Stop ist nicht übersteuerbar gesperrt. Eine direkte Trade-Republic-/LS-Exchange-Kursquelle und allgemeine vollständige Emittenten-/Listing-Auflösung bleiben offen und werden nicht vorgetäuscht.

Version 1 unterstützt ausschließlich:

- Rücksetzer in einem intakten Aufwärtstrend.
- Bestätigten Ausbruch über einen relevanten Widerstand.
- Long-Trades in liquiden Aktien, ETFs und großen Kryptowährungen mit einer Haltedauer von mehreren Tagen bis einigen Wochen.
- Keine Hebelprodukte, kein Scalping, keine Short-/Absicherungs- oder sichtbare Beobachtungskategorie.

Zwingende Freigabefilter:

- Datenqualität und ausreichende Historie.
- Asset-typische Mindestliquidität.
- Kaufsignal, Asset-Qualität, Confidence und Marktumfeld über zentralen Mindestwerten.
- Messbarer Einstieg, Long-geometrisch gültiger Stop, strukturell realistisches Ziel und CRV von mindestens 2,0.
- Einstieg noch nicht verpasst, keine gebrochene Struktur und keine widersprüchlichen Signale.
- Kein unvertretbares Ereignisrisiko.
- Positiver historischer Expected Value, sobald mindestens 20 vergleichbare ausgewertete Fälle vorliegen; vorher keine scheinpräzise Trefferwahrscheinlichkeit.

Hauptausgabe:

- Marktlage, Scanzeitpunkt, Universumsgröße, geladene Assets, Vorfilterauswahl, Tiefenprüfungen, Freigaben und Datenfehler.
- Ausschließlich freigegebene Trades; andernfalls `Aktuell kein hochwertiger Trade vorhanden.` mit kurzer Ablehnungszusammenfassung.
- Asset/Ticker, Long, Setup-Typ, EUR-Kurs, Einstiegszone und exakte Eintrittsbedingung.
- Stop, Ziel 1/2, Chance und Risiko in Euro/Prozent, zentral berechnetes CRV, Haltedauer, Gültigkeit und maximaler Einstieg.
- Wichtigste Gründe, größtes Risiko und eindeutige Nichteinstiegsbedingungen.
- Abgelehnte Kandidaten, Gründe, Methodik, Grenzwerte und Statistiken nur unter `Erweiterte Einblicke`.

Regeln:

- Der Scanner macht nur Vorschläge und erzeugt niemals zwanghaft einen Trade.
- Einziger fachlicher Nutzereingabewert im Hauptbereich ist das Tradingkapital. Die zentrale Risikopolitik ist nur lesbar: 0,50 % Risiko je Trade, 2,00 % offenes Gesamtrisiko, 50 % Gesamtbelastung und 20 % je Position. Eine feste Drei-Trade-Grenze besteht nicht mehr; die zulässige Zahl wird dynamisch aus verbleibendem Risiko und Kapitalbindung abgeleitet.
- Vor der ersten Nutzung ist der lokal gespeicherte Verlusthinweis einmalig zu bestätigen.
- Keine automatische Kauf- oder Verkaufsfunktion vor bestandenem Echtgeld-Gate.
- Keine Broker-Anbindung vor bestandenem Echtgeld-Gate.
- Grenzwerte liegen zentral und versionierbar in `trading_assistant.py`.
- CRV wird nur aus derselben Einstiegs-, Stop- und Zielstruktur berechnet; für Long gilt zwingend `0 < Stop < Einstieg < Ziel`.
- Zielabstand ist auf 18 % begrenzt; Standardgültigkeit sieben Tage, Ereignissperre drei Tage.
- Keine belastbare Trefferwahrscheinlichkeit unter 20 ausgewerteten vergleichbaren Fällen.

#### Verbindliches Zielbild: bedienungsarmer regelbasierter Trading-Assistent

Der normale Swing Trade Finder verlangt dauerhaft nur `Verfügbares Tradingkapital in Euro`. Das System übernimmt Marktuniversum, Suche, Auswahl, Orderplan, Stop, Ziele, Positionsgröße, Hintergrund-Scans, unveränderbare Paper-Signale, spätere Auswertung, Archiv und regelbasierte Begleitung. Der Nutzer setzt eine Order ausschließlich selbst beim Broker um und bestätigt seine tatsächlichen Handlungen in der App.

Statusabgrenzung:

- **Umgesetzt:** 2.520 aktive gültige Assets, ServiceNow, Ausschluss bekannter Hebel-/Inverse-Produkte, mehrstufiger Scan ohne Top-N-Abbruch, Assetklassen-Funnel und Bias-Hinweis, harte Kein-Trade-Regel, zwei Long-Setups, Kapital als einzige normale Eingabe, zentrale konservative Risikoregeln, konkrete Orderpläne, regionale Hintergrundaufgaben, unveränderbare Forward-Signale, konservative Intraday-/Tages-Auswertung, Archivkennzahlen und strikt getrennte Nutzertrades.
- **Teilweise umgesetzt:** technische historische Ein-/Ausstiegs-FX-Bewertung, vollständige Zeit-/Text-/Status-/Setup-/Einstiegs-/Asset-/Ergebnis-/Qualitäts-/Region-/Version-/Quellen-/Nutzertrade-Archivfilter und Detailansicht, stabile interne Asset-Identität sowie Struktur-/Trend-/Volumen-/Ereignisbegleitung. Reale abgeschlossene Signale, echte Exit-FX-Belege, belastbare News-/Branchenquellen und ausgereifte Ergebnisse fehlen noch für die fachliche Validierung.
- **Weiterzuführen:** Restpunkte der Phasen A bis F sowie Phase G mit realen planmäßigen Läufen und einer belastbaren mehrwöchigen Forward-Historie.
- **Später:** weitere Setup-Arten, Short/Absicherung und ein vollständig separater Hebelmodus erst nach Phase G und ausdrücklicher späterer Produktentscheidung.

#### Phase A – bestehende Swing-Logik und Orderplan stabilisieren

Status: sicherer Kern des Order- und Stop-Vertrags seit 2026-08-09 umgesetzt und bei 1.440 sowie 390 Pixel sichtbar geprüft. Die historische Ein-/Ausstiegs-FX-Architektur ist Point-in-Time-sicher und append-only umgesetzt. Reale Orderkarten, echte FX-Belege und reale Scanner-Stichproben können erst mit planmäßigen Signalen abgenommen werden.

Stand 2026-08-09:

- Eine gleichdatierte Tageskerze darf erst nach der konservativen regionalen Schlusszeit verwendet werden; Krypto bleibt bis zum nächsten UTC-Tag gesperrt. Eine möglicherweise noch laufende Tageskerze kann kein freigegebenes Signal erzeugen.
- Pullback und Ausbruch speichern eine explizite Einstiegsmethode. Ein bestätigter Ausbruch darf frühestens in der nächsten Handelssitzung innerhalb des Maximalpreises als möglicher Einstieg gelten; es gibt keinen rückwirkenden Kauf zum Signalkerzen-Schlusskurs.
- Der versionierte Orderplan speichert denselben FX-Snapshot und dieselben Original-/EUR-Marken wie die Karte. Nach der Positionsfreigabe enthält sein endgültiger Fingerabdruck auch Stückzahl, Kapitaleinsatz, geplanten Verlust und mögliche Gewinne.
- Bei zwei Zielen ist die Ausstiegsverteilung fest versioniert: 50 % an Ziel 1 und 50 % an Ziel 2 oder einem späteren Stop. Kartenwerte zeigen Teilgewinn und kumulierten Gewinn; der Forward-Test aggregiert beide Beine ohne Doppelzählung und mit eigenem historischen FX-Beleg je Ausstieg.
- Der initiale Stop wird beim manuellen Öffnen unveränderbar erhalten. Ein aktiver Long-Stop kann nur angehoben, niemals abgesenkt beziehungsweise erweitert werden.
- Die Hauptkarte zeigt den konkreten Orderplan vor der technischen Herleitung und weist ausdrücklich auf fehlende Broker-Ausführung hin.
- Offen bleiben insbesondere eine belegte reale Scanner-Stichprobe unter normalen Yahoo-Bedingungen, die sichtbare Abnahme einer echten freigegebenen Orderkarte und reale historische FX-Belege. Desktop-/390-Pixel-Grundlayout, Point-in-Time-FX-Vertrag und unveränderbarer Swing-Forward-Test sind umgesetzt.

1. **Normale Eingaben und Risikomodell**
   - In der normalen Oberfläche bleibt ausschließlich `Verfügbares Tradingkapital in Euro` editierbar.
   - Manuelle Ticker, Scanner-Watchlist, Asset-Typ-Auswahl, Risiko pro Trade, Stop-Abstand, Wunsch-CRV, Positionsgröße, maximale Positionsgewichtung, Gesamtbelastung, Volatilitätsparameter und Setup-Grenzwerte bleiben entfernt.
   - Das zentrale konservative Risikomodell bleibt dokumentiert, versioniert, getestet und unter `Erweiterte Einblicke` nur lesbar.
   - Änderungen an der Risikopolitik benötigen eine neue Logikversion, Tests und dokumentierte Freigabe; keine heimliche automatische Anpassung.

2. **Konkreter Orderplan**
   - Jede Freigabe nennt zuerst einen emotionsarmen ausführbaren Plan statt einer abstrakten technischen Bedingung.
   - Pflichtfelder: Ordertyp, konkreter Kaufpreis, optionaler Aktivierungskurs, maximaler Kaufpreis, Stop-Loss, Ziel 1, optional Ziel 2, Stückzahl, Kapitaleinsatz, geplanter Verlust, möglicher Gewinn, Ordergültigkeit und genaue Löschbedingung.
   - Pullback-Setup bevorzugt als Limit-Orderplan mit Limitpreis, Stop, Zielen, Gültigkeit und Ungültigkeitsbedingung darstellen.
   - Breakout-Setup entweder als klar erklärte Stop-Limit-Logik mit Aktivierung und Maximalpreis oder als Schlusskursbestätigung mit Einstieg frühestens in der nächsten Handelssitzung darstellen.
   - Technische Herleitung bleibt intern beziehungsweise unter `Warum dieser Trade?`; die Hauptkarte erklärt nur verständlich, welche Order der Nutzer selbst beim Broker einstellen müsste.

3. **Einstiegsmethoden fachlich trennen**
   - `Schlusskursbestätigung`: erst nach abgeschlossenem regulären Handelstag erfüllt; niemals rückwirkend zum selben Schlusskurs kaufen. Frühester realistischer Einstieg ist der erste handelbare Kurs der nächsten Sitzung innerhalb des Maximalpreises; ein Gap darüber bedeutet `Einstieg verpasst`.
   - `Intraday-Einstieg`: am selben Tag nur bei vollständig messbarer Bedingung, ausreichender Liquidität/Volumen, Preis innerhalb des Maximalwerts und Schutz vor einem einzelnen fehlerhaften Tick.
   - `Pullback-Limit`: Ausführung innerhalb der definierten Unterstützungszone nur solange die Setup-Struktur intakt ist.
   - Einstiegsmethoden als eigenes versioniertes Feld speichern und später getrennt auswerten.

4. **Stop-Vertrag**
   - Stop aus relevanter Unterstützung, Swing-Tief, überwundener Widerstandszone, Setup-Struktur, Volatilitätspuffer sowie Markt- und Asset-Typ ableiten.
   - Stop niemals verschieben, um eine größere Position, ein gewünschtes CRV oder längeres Hoffen im Verlust zu ermöglichen.
   - Nach Trade-Eröffnung darf der bestätigte Stop niemals weiter vom Einstieg entfernt werden. Er bleibt gleich, wird nach vorher definierten Regeln enger gesetzt oder durch einen klar begründeten vorzeitigen Ausstieg ersetzt.

5. **Währungs- und Markenvertrag**
   - Alle sichtbaren Kurs-, Stop-, Ziel-, Gewinn-, Verlust- und Erklärungstexte eines Trades verwenden denselben EUR-Wechselkurs-Snapshot.
   - Originalwährung, genauer damaliger Wechselkurs, Wechselkurszeitpunkt und Quelle intern speichern; historische Ergebnisse verwenden den zeitlich passenden Wechselkurs und niemals rückwirkend den heutigen Kurs.
   - Intern mit voller Genauigkeit rechnen, sichtbar sinnvoll auf zwei Nachkommastellen runden.
   - Vor Freigabe automatisch prüfen: `Stop < Einstieg < Ziel`, passende Aktivierungsmarke, konsistenter Maximalpreis, CRV aus denselben sichtbaren Werten und identische Marken in Karte und Erklärung.
   - Jede Währungs- oder Markenkollision blockiert die Freigabe statt widersprüchliche Angaben zu zeigen.

6. **Ruhige Hauptkarte und Risikohinweis**
   - Kompakte Karte zeigt nur vollständigen Assetnamen, Ticker, ISIN falls vorhanden, Setup, Handlungsstatus, aktuellen EUR-Kurs, Kauforder, Stop, Ziel, Stückzahl, Kapitaleinsatz, geplanten Verlust, möglichen Gewinn, Gültigkeit, kurze Begründung und `Trade getätigt`.
   - SMA 50/200, MACD, RSI, Volumenrechnung, CRV-Herleitung, Expected Value, Stop-Herleitung, Methodik, Rohdaten und Historienstatistik liegen unter `Warum dieser Trade?`, `Details anzeigen` oder `Erweiterte Einblicke`.
   - Wichtige Pflichttexte werden nie mit `...` abgeschnitten; Desktop und ungefähr 390 Pixel Breite werden sichtbar geprüft.
   - Einmalig vor der ersten Nutzung anzeigen: `Trading kann zum vollständigen Verlust des eingesetzten Tradingkapitals führen. Automatisch berechnete Stops und Positionsgrößen sollen Verluste begrenzen, können sie aber nicht garantieren. Die App führt keine Orders aus.`
   - Auf jeder Karte bleibt der kurze Gap-Hinweis: `Geplanter Verlust bei Ausführung nahe dem Stop. Bei Kurslücken kann der tatsächliche Verlust höher sein.`

#### Phase B – großes automatisches Swing-Universum vervollständigen

Status: am 2026-08-11 mit 2.520 eindeutigen Assets umgesetzt. Das Universum kombiniert das bestehende breite Projektuniversum mit regulären Aktien des offiziellen Nasdaq Global Select Market. Die feste Obergrenze von 60 Tiefenanalysen ist entfernt; im realen Amerika/Global-Lauf wurden alle 362 Grobfiltertreffer vollständig geprüft.

- Das versionierte Universum enthält 2.520 aktive gültige Assets: 2.431 Aktien, 59 ETFs und 30 Kryptowährungen. ServiceNow bleibt enthalten.
- Der erste vollständige neue Amerika/Global-Lauf lud 2.350 von 2.352 Assets in 327,36 Sekunden; zwei Tickerfehler blieben sichtbar, null Rate-Limits traten auf.
- Ausbauquellen USA: S&P 500, Nasdaq 100, S&P MidCap 400, weitere liquide Large-/Mid-Caps und nach strenger Liquiditätsprüfung größere liquide Teile geeigneter Russell-Universen.
- Ausbauquellen Europa: STOXX Europe 600, DAX, MDAX, SDAX, CAC, FTSE, Schweiz, Skandinavien und weitere liquide europäische Hauptmärkte.
- Ausbauquellen Asien/Pazifik: Japan, Südkorea, Hongkong, ausgewählte liquide chinesische Titel, Australien und weitere große liquide Märkte.
- ServiceNow bleibt verbindlich enthalten. Branchen, Regionen und Unternehmensgrößen werden nachvollziehbar gemischt, ohne Mindestqualität abzusenken.
- Penny Stocks, extrem illiquide Werte, sehr große Spreads, tote/delistete Listings, dauerhaft unzuverlässige Marktdaten, exotische oder sehr kleine ETFs, Hebelprodukte, inverse ETFs, Knock-outs und Optionsscheine sperren.
- Metadaten je Asset vervollständigen: stabile Asset-ID, Name, Ticker, ISIN sofern vorhanden, Börsenplatz, Asset-Typ, Originalwährung, Region, Branche/Kategorie, Aktivstatus, Liquiditätsklasse, Universumsversion und Gültigkeitszeitraum.
- Tickerwechsel, Delistings und Ausschlüsse versioniert dokumentieren. Nie still aus historischen Signalen oder Universumsständen löschen.
- Reale Abdeckung, Laufzeit, Fehlerquote, Batchfehler und Rate Limits wiederholt messen; dauerhaft fehlerhafte Assets in einem technischen, scanübergreifenden Protokoll sichtbar machen.

Mehrstufige Suche:

- **Stufe 1 – schneller binärer Grobfilter:** gesamtes Universum günstig auf Historie, Liquidität, Handelsumsatz, Datenqualität, sinnvolle Volatilität, grundsätzlich passende Trend-/Pullback-/Breakout-Struktur, nicht offensichtlich verpassten Einstieg und klar ungeeignete Marktstruktur prüfen. Ergebnis nur `offensichtlich kein sinnvoller Trade-Kandidat` oder `möglicherweise relevanter Trade`.
- **Stufe 2 – genaue Setup-Prüfung aller ernsthaften Kandidaten:** Jeder Kandidat der zweiten Gruppe wird vollständig auf Pullback/Ausbruch, Orderpreis, Struktur-Stop, Ziele, CRV, Expected Value, Volumenbestätigung, Markt-/Branchenlage, Ereignisrisiken, Datenqualität und realistische Handelbarkeit geprüft. Es gibt keine feste fachliche Obergrenze von 60; 18, 72 oder 140 ernsthafte Kandidaten bedeuten entsprechend 18, 72 oder 140 Tiefenanalysen.
- **Stufe 3 – harte Freigabe:** nur vollständig bestandene Setups zeigen; keine relative Rangliste schwacher Trades. Ohne Freigabe exakt `Aktuell kein hochwertiger Trade vorhanden.`
- Der Vorfilter entscheidet nur, ob eine teure Prüfung grundsätzlich sinnvoll ist. Er ist keine versteckte Rangliste und darf keinen ernsthaften Kandidaten allein wegen eines künstlichen Top-N-Cutoffs entfernen.
- Abgelehnte Kandidaten und Gründe ausschließlich erweitert zeigen. Es bleibt zulässig, dass kein Trade freigegeben wird; es gibt keine Mindestzahl an Trades.

Technische Lastkontrolle ohne fachlichen Kandidatenverlust:

- Batch-Verarbeitung, Caching, kontrollierte Parallelisierung, Provider-Schonung und Wiederverwendung bereits geladener Kursdaten vorsehen.
- Fehler pro Asset isolieren, unterbrochene Läufe sicher fortsetzen und Zahl/Dauer der Tiefenanalysen dokumentieren.
- Einzelne Datenfehler stoppen den übrigen Scan nicht. Bei einem globalen Provider-Ausfall sicher abbrechen und den Lauf nicht als gültigen Null-Trade-Scan ausgeben.
- Wenn außergewöhnlich viele Kandidaten den Grobfilter bestehen, darf der Lauf länger dauern oder sicher in fortsetzbare Batches geteilt werden. Fachlich relevante Kandidaten dürfen nicht nur zur Einhaltung einer festen Laufzeitgrenze verworfen werden.

Assetklassen-Bias messen statt vorzugeben:

- Pro Scan für Aktien, ETFs und Krypto getrennt speichern: Universumszahl, erfolgreich geladen, Grobfilter bestanden, tief analysiert und freigegeben.
- Zusätzlich je Assetklasse echte Forward-Ergebnisse vergleichen: Trefferquote, durchschnittliches R, Profitfaktor, Drawdown, Durchschnittsgewinn/-verlust, Haltedauer, Gap-Risiko, verpasste Einstiege und Nettoergebnis nach Kosten.
- Prüfen, ob gleichmäßigere ETF-Trends den Vorfilter systematisch leichter passieren lassen oder Aktien durch Earnings-, Volatilitäts-, CRV-, Stop-, Confidence- oder Datenregeln unverhältnismäßig früh ausscheiden.
- ETFs, Aktien und Krypto weder positiv noch negativ pauschal gewichten. Freigabe basiert auf dem erwarteten risikobereinigten Ergebnis des konkreten Setups.
- Änderungen an Vorfilter, Tiefenanalyse, Grenzwerten oder Risikoregeln versionieren und ausschließlich gegen echte Forward-Daten sowie eine kleine Kontrollstichprobe abgelehnter/unauffälliger Assets prüfen.

#### Phase C – regelmäßige bedienungsfreie Hintergrund-Scans

Status: technische Grundlage am 2026-08-09 umgesetzt und im Windows-Aufgabenplaner aktiviert; am 2026-08-11 wurden alle vier Bereiche mit der neuen 2.520-Asset-/Vollanalyse-Pipeline real ausgeführt. Amerika/Global lud 2.350/2.352, Asien/Australien 65/65, Europa 73/73 und Krypto 29/30 Assets; alle Läufe endeten mit Status `ok`, null Rate-Limits und intakter append-only Datenbank. Dauerstabilität über weitere Wochen bleibt zu belegen.

Aktueller Zeitplan und noch zu validierender Produktvertrag:

- Die produktiven Windows-Zeitpunkte sind unverändert lokale Rechnerzeit `Europe/Berlin`: Asien/Australien 10:30 Uhr, Europa 18:15 Uhr und die sequenzielle Abendkette ab 22:30 Uhr. In dieser Kette laufen zuerst Prognosen, nach deren Ende Amerika/Global und danach Krypto. Ausschließlich die getrennte historische Swing-Forschung darf außerhalb ihrer Schutz- und Vorlaufzeiten nun auch zwischen 00:00 und 10:00 Uhr laufen.
- Der historische Kampagnentask prüft täglich durchgehend alle fünf Minuten auf genau einen offenen Job. Starts sind ab 09:00 Uhr vor dem 10:30-Asienlauf, ab 15:45 Uhr vor dem Europa-Schutzfenster 17:15–18:45 sowie ab 20:00 Uhr vor dem Abendfenster 21:30–23:59 gesperrt. Zusätzlich verhindern die aktiven Forecast- und Swing-Forward-Prozesslocks einen Forschungsstart; bei gleichzeitigem Aufwachen erhalten die Produktionsprozesse vor der Lockprüfung fünf Sekunden Startvorrang. Ein bereits laufender Forschungsjob wird nicht hart beendet.
- Aktien-/ETF-Scans verwenden ausschließlich abgeschlossene Tageskerzen und liegen grundsätzlich nach der maßgeblichen regulären Handelssitzung ihrer Region. Börsenkalender, regionale Feiertage, Sommerzeit und einzelne abweichende Handelsplätze müssen pro Listing geprüft werden; eine feste lokale Uhrzeit allein gilt nicht als Beweis für einen abgeschlossenen Handelstag.
- Für jede Region werden kanonische Börsensitzung, erwarteter Schluss, verwendete Zeitzone, tatsächlicher Scanzeitpunkt und frühester nächster Termin versioniert gespeichert. Ein Signal darf nicht aktueller wirken als sein echter Scan.
- Krypto bleibt fachlich am kanonischen UTC-Tagesabschluss ausgerichtet, wird aber technisch direkt nach dem Amerika/Global-Lauf innerhalb der 22:30-Abendkette ausgeführt. Die Tageskerzenprüfung darf deshalb weiterhin nur vollständig abgeschlossene UTC-Tage verwenden.
- Wochenenden und Börsenfeiertage erzeugen bei Aktien/ETFs keine neue Tageskerze und damit kein neues gleichlautendes Signal. Ein Scan kann den Marktstatus dokumentieren, darf veraltete Daten aber nicht als frische Sitzung ausgeben.
- Verpasste Läufe werden nach `StartWhenAvailable` mit tatsächlichem späterem Zeitpunkt nachgeholt. Kein Signal wird auf den verpassten Termin zurückdatiert; außerhalb einer noch fachlich gültigen abgeschlossenen Sitzung bleibt der Lauf als verpasst oder verspätet gekennzeichnet.

- Swing-Finder regelmäßig zu festen Zeiten ohne geöffnete Streamlit-App und ohne Nutzerklick starten.
- Aktien und ETFs nach der jeweils relevanten regulären Börsensitzung scannen; Region, Börsenkalender, Feiertage und Zeitzone berücksichtigen.
- Kryptowährungen in einem eigenen festen UTC-basierten Lauf prüfen. Zusätzliche Intraday-Scans erst nach belegtem fachlichem Nutzen und tragbarer Datenlast erwägen.
- Sperrmechanismus, Fehlerisolierung, SQLite, Wiederaufnahme, Protokollierung und Windows-Aufgabenplanung des Prognosebetriebs soweit sinnvoll als technische Muster wiederverwenden, jedoch mit getrenntem Lauf-/Signalmodell, getrennten Sperren und getrennten Statistiken.
- Swing-Scans niemals mit Einstiegs-/Long-Term-Prognoseläufen oder deren Trefferquoten vermischen.
- Unterbrochene Scans sicher fortsetzen oder als unterbrochen abschließen; keine doppelten Signal-Snapshots bei Wiederaufnahme und keine aggressiven Parallelabfragen.
- Manueller Gesamtmarkt-Scan und regionale Hintergrundscans verwenden dieselbe versionierte fachliche Pipeline. Zulässige Unterschiede sind ausschließlich Zeitpunkt, regionale Asset-Auswahl und Quellentyp `manual` oder `scheduled`; Order-, Strategie-, Stop-, Ziel-, Forward- und Datenqualitätsvertrag bleiben identisch.
- Die Swing-Oberfläche zeigt je Region letzten offiziellen Scan, tatsächlichen Zeitpunkt/Zeitzone, Status `erfolgreich`, `eingeschränkt` oder `fehlgeschlagen`, Datenabdeckung und nächsten vorgesehenen Scan. Sie behauptet keine Echtzeit- oder 24/7-Aktienüberwachung.

Jeder Hintergrund-Scan speichert unveränderbar:

- Scan-ID, Zeitpunkt und Zeitzone
- Universums-, Strategie-, Logik- und Datenschema-Version
- Zahl konfigurierter, erfolgreich geprüfter und fehlgeschlagener Assets
- Zahl der Vorfilter-Kandidaten, vollständig geprüften Setups und freigegebenen Trades
- Laufzeit, Datenqualitätsübersicht, Quellen und verwendete Intervalle
- Laufstatus, Fehlerklassen und Wiederaufnahmeinformationen
- auch einen vollständigen Null-Trade-Scan, damit die spätere Statistik nicht nur erfolgreiche Signalzeitpunkte enthält

#### Phase D – präziser unveränderbarer Paper-Forward-Test

Status: append-only Kern am 2026-08-09 umgesetzt; reale Signale und mehrtägiger Betrieb fehlen noch. Echte manuelle und regionale Hintergrundscans werden getrennt unter `runtime/swing_forward.sqlite3` gespeichert. Datenbank-Trigger verbieten Änderungen und Löschungen an Scans, Signalsnapshots und Ereignissen; Wiederholungen sind idempotent und abweichende Wiederverwendung derselben Identität wird abgelehnt. Bestehende `trade_history.json`-Daten bleiben erhalten und werden nicht verlustbehaftet überschrieben.

Die erste automatische Auswertung verwendet nur vollständige Kursbalken nach dem Signal, bevorzugt 5-Minuten-, danach Stunden- und erst zuletzt klar eingeschränkte Tagesdaten. Versionierte konservative Spread-, Slippage- und Gebührenannahmen, Gap-Verpassung, Gap unter Stop, Maximalpreis, Ablauf und Stop-/Ziel-Reihenfolge sind umgesetzt. Liegen Einstieg und Ziel oder Stop und Ziel in derselben Kerze, wird kein Gewinn behauptet, sondern `Reihenfolge nicht eindeutig` gespeichert. Historische Ein- und Ausstiegs-FX-Belege werden getrennt append-only ergänzt: bevorzugt Intraday nur bis zum Ereignis, sonst der bereits bekannte vorherige Tagesabschluss. Fehlen Belege, bleibt die vorläufige Signal-FX-Vergleichsgröße sichtbar und die Nachbewertung retry-fähig.

Bei zwei Zielen gilt im versionierten Papervertrag eine feste 50/50-Verteilung. Ziel 1 realisiert die erste Hälfte; Ziel 2 oder ein späterer Stop bewertet ausschließlich die Resthälfte. Ergebnis in Originalwährung, R und Euro wird aus beiden Beinen aggregiert, wobei jedes Ausstiegsbein seinen eigenen Point-in-Time-FX-Beleg erhält.

Verbindliche Ergebnisdefinition: Ein Swing-Signal ist kein Erfolg, nur weil der Kurs nach einer Woche oder einem anderen festen Zeitraum höher steht. Maßgeblich ist ausschließlich der unveränderbare Systemplan zum Signalzeitpunkt und sein vollständiger regelbasierter Lebenszyklus: Eintrittsbedingung, tatsächlicher Aktivierungszeitpunkt, realistischer Einstieg innerhalb des Maximalpreises, Gap-Verpassung, Ungültigkeit vor Einstieg, Ziel 1/2, Stop, Ereignisreihenfolge, maximaler Zwischengewinn/-verlust, aktive Haltedauer, Kosten, endgültiges Ergebnis in Euro/Prozent/R und Datenqualität. Horizont-Reviews dürfen ergänzend existieren, ersetzen aber niemals diese Trade-Auswertung.

1. **Echten Forward-Test und Simulation trennen**
   - `Echter Forward-Test`: Signal wurde zu diesem Zeitpunkt durch einen manuellen oder automatischen realen Scan erzeugt und sofort unveränderbar gespeichert.
   - `Historische Scanner-Simulation`: rückwirkend aus damaligen Kursdaten rekonstruierter Lauf; getrennte ID, Herkunft und Statistik.
   - Rückwirkende Simulationen dürfen weder echte Forward-Fallzahlen noch das Datum einer realen Freigabe vortäuschen.
   - Der echte Hintergrund-Scan ist langfristig die wichtigste Qualitätsgrundlage; Simulationen dienen nur als ergänzende frühe Forschung.

2. **Append-only Signal-Snapshot**
   - Jedes freigegebene Setup wird sofort als unabhängiges Paper-Signal gespeichert, unabhängig davon, ob der Nutzer handelt.
   - Pflichtfelder: Signal-ID, Signalzeitpunkt/Zeitzone, Asset-ID, Name, Ticker, ISIN, Börsenplatz, Asset-Typ, Originalwährung, EUR-Kurs, damaliger FX-Snapshot, Ordertyp, Kaufpreis, optionaler Aktivierungskurs, Maximalpreis, Stop, Ziel 1/2, Gültigkeit, Löschbedingung, Einstiegsmethode, Setup, Marktphase, Qualitätswerte, Quellen/Intervalle sowie Universums-, Strategie-, Logik- und Schemasversion.
   - Der ursprüngliche Snapshot ist nach Speicherung unveränderbar. Aktivierung, Paper-Einstieg, Nutzerhandlung, Stop-/Zielereignisse, Anpassungen und Abschluss werden ausschließlich als neue Ereignisse angehängt.
   - Migrationen sind nur nicht löschend und idempotent. Alte JSON-Felder defensiv lesen; fehlende alte Informationen als unbekannt markieren statt erfinden.

3. **Realistische automatische Auswertung**
   - Offene Signale regelmäßig und bedienungsfrei prüfen; bevorzugte Datenauflösung: kleine belastbare Intraday-Intervalle, danach größere Intraday-Intervalle, Stundenkerzen, Tagesdaten nur als klar gekennzeichneter Rückfall.
   - Keine Kursdaten vor Signalzeitpunkt verwenden. Börsenzeiten, Zeitzonen und 24/7-Kryptologik beachten.
   - Prüfen: Aktivierung, erster realistischer handelbarer Einstieg, Kostenkurs, Maximalpreis, Gap-Verpassung, Stop/Ziel-Reihenfolge, maximales Zwischenhoch/-tief, Haltedauer, Ablauf, Aktivstatus und Datenqualität.
   - Spread, Gebühren und konservative Slippage als versionierte Annahmen berücksichtigen; niemals idealisierte Bestkurse verwenden.
   - Gap über Maximalpreis eröffnet keinen Trade. Gap unter Stop verwendet den ersten realistisch handelbaren Kurs und weist den größeren Verlust aus.
   - Liegen Stop und Ziel in derselben Kerze, kleinere Intervalle nachladen. Bleibt die Reihenfolge unklar, Status `Reihenfolge nicht eindeutig` setzen und zusätzlich eine konservative Nebenrechnung mit ungünstigerem Ausgang zeigen; niemals automatisch Ziel zuerst annehmen.

4. **Signalstatus**
   - `gespeichert`
   - `Eintritt noch nicht aktiviert`
   - `aktiviert`
   - `Paper-Trade eröffnet`
   - `Einstieg verpasst`
   - `vor Einstieg ungültig`
   - `ohne Einstieg abgelaufen`
   - `Ziel 1 erreicht`
   - `Ziel 2 erreicht`
   - `Stop erreicht`
   - `noch aktiv`
   - `Reihenfolge nicht eindeutig`
   - `nicht auswertbar`

`Abgelaufen` bedeutet ausschließlich, dass innerhalb der Signalgültigkeit kein Einstieg ausgelöst wurde. Ein eröffneter Trade endet nur durch Stop, Ziel, vorher definierte Zeitregel, regelbasierten vorzeitigen Ausstieg oder beim Nutzertrade durch bestätigten Verkauf.

5. **Datenqualitätsstufen**
   - `hoch`: vollständige Intraday-Daten, eindeutige Ereignisreihenfolge, konsistente Zeit- und Währungsbasis.
   - `mittel`: gröberes Intervall, Reihenfolge dennoch eindeutig.
   - `eingeschränkt`: Datenlücken oder nur konservative Annäherung; Volumen-/Ereignisabdeckung begrenzt.
   - `nicht auswertbar`: keine belastbaren Kursdaten, unauflösbare Reihenfolge oder fehlerhafte Zeit-/Währungsbasis.
   - Nicht auswertbare Fälle sowie Signale ohne eröffneten Trade zählen weder als Gewinner noch als Verlierer.

#### Phase E – Trade-Archiv und ehrliche Statistik

Status: technische Archiv- und Statistikbasis, kombinierbare Filter-/Suchoberfläche und Detailansicht am 2026-08-09 umgesetzt; reale Datenfüllung und der optionale kompakte Chart bleiben offen. Die erweiterte Swing-Ansicht zeigt unveränderbare echte Scans, Signale, Paper-Einstiege/-Ausstiege, Haltedauer, maximalen Zwischengewinn/-verlust, eindeutige Ergebnisse, verpasste/ungültige/abgelaufene/unklare Fälle, Systemplan, Ereignisverlauf, Segmente und scanübergreifende technische Asset-Fehler. Suche nach Asset, Ticker, ISIN oder Signal-ID sowie Filter nach Zeitraum, Status, Setup, Einstiegsmethode, Asset-Typ, Gewinn/Verlust, Datenqualität, Region, Strategieversion, Quellentyp, FX-Status und dokumentiertem Nutzertrade sind umgesetzt. Eindeutige Ergebnisse werden in Trefferquote, R, Profitfaktor und Drawdown ausgewertet. Offene, verpasste, unklare und nicht auswertbare Fälle zählen nicht als Verluste.

- Neuer Bereich `Trade-Archiv` für ausgelöste/aktive Paper-Trades, Stop-/Zielabschlüsse, nicht ausgelöste/abgelaufene Signale, verpasste Einstiege, unklare/nicht auswertbare Fälle und persönliche Nutzertrades.
- Kompakttabelle mit Signal-ID, Assetname, Ticker, Setup, Signalzeitpunkt, theoretischem Einstieg oder `Kein Einstieg`, theoretischem Kaufdatum, Ergebnisstatus, Prozentergebnis, Ergebnis in R, Haltedauer, Datenqualität, Paper-/Nutzerart und Logikversion.
- Filter nach Zeitraum, Status, Setup, Einstiegsmethode, Asset-Typ, Gewinn/Verlust, Datenqualität, Region, Logikversion sowie echtem Forward-Test/historischer Simulation/Paper-/Nutzertrade.
- Suche nach Assetname, Ticker und ISIN.

Detailansicht:

- `Ursprünglicher Plan`: Signalzeit, Assetidentität, Ordertyp, Kauf-/Aktivierungs-/Maximalpreis, Stop, Ziele, Gültigkeit, Löschbedingung sowie Setup-/Logikversion.
- `Theoretischer Ablauf`: Aktivierung, realistischer Einstieg einschließlich Kosten, Stop-/Ziel-/Ablauf-/Verpassungsereignisse und angenommener Ausstieg.
- `Ergebnis`: Euro, Prozent, R, maximaler Zwischengewinn/-verlust, Haltedauer, Kostenannahmen und Datenqualität.
- `Ereignisverlauf`: chronologisch append-only von Signal bis Abschluss beziehungsweise Ablauf.
- Optionaler kompakter Chart mit Signal, Einstieg, Stop, Ziel 1/2 und Ausstieg.

Archiv-Kennzahlen:

- gespeicherte Signale, ausgelöste Einstiege, Gewinner, Verlierer, aktive Trades, ohne Einstieg abgelaufene Signale, verpasste Einstiege, unklare und nicht auswertbare Fälle
- Trefferquote, Durchschnittsgewinn/-verlust, durchschnittliches R, Expected Value, Profitfaktor und maximaler Drawdown
- getrennt nach Setup, Einstiegsmethode, Asset-Typ, Marktphase, Region, Datenqualität, Logikversion, echtem Forward-Test, historischer Simulation und Nutzertrade
- offene, nicht ausgelöste, nicht eindeutige und nicht auswertbare Fälle nicht als Verlust zählen
- unter 20 eindeutig ausgewerteten vergleichbaren Fällen exakt `Trefferwahrscheinlichkeit noch nicht belastbar.` anzeigen
- keine automatische Anpassung von Scores, Schwellen, Stops oder Gewichten aus Archivzahlen

#### Phase F – Nutzertrade und regelgebundene Trade-Begleitung

Status: sicherer Kern am 2026-08-09 umgesetzt; reale Nutzung und fachlich breitere Begleitregeln bleiben zu validieren. `Trade getätigt` erscheint ausschließlich an einem unveränderbar gespeicherten objektiven Signal. Der persönliche Einstieg wird in einer zweiten privaten append-only SQLite-Datenbank gespeichert und verändert weder Paper-Signal noch Paper-Auswertung. Abweichungen bei Zeitpunkt, Maximalpreis oder Stückzahl verlangen eine ausdrückliche lokale Bestätigung und bleiben dauerhaft sichtbar. Stop-Nachzug, Teilverkauf und Abschluss werden als neue Nutzerereignisse angehängt; ein Long-Stop darf nur enger werden.

Die Ansicht `Meine aktiven Trades` zeigt Einstieg, Restmenge, initialen und aktuellen Stop, Ziele, realisiertes Ergebnis und eine erste regelbasierte Bewertung. Zustände `Plan intakt`, `Erhöhte Aufmerksamkeit`, `Regelbasierte Anpassung empfohlen`, `Notausstieg empfohlen` und `Daten derzeit nicht belastbar` werden nur aus gespeicherten Marken und aktuellen Kursdaten abgeleitet. Sie senden oder ändern niemals eine Order. Volumen-, Struktur-, Nachrichten- und Ereignisregeln sind noch nicht vollständig in diese laufende Begleitung integriert.

1. **`Trade getätigt`**
   - Primärer Button auf jeder noch gültigen freigegebenen Karte.
   - Kompaktes Formular: tatsächlicher Einstieg, tatsächliche Stückzahl, Datum/Uhrzeit und optionale Notiz; Systemwerte sind vorausgewählt.
   - Vor Bestätigung sichtbar warnen bei noch nicht erfüllter Eintrittsbedingung, Preis über Maximalwert, abweichender Stückzahl oder verspätetem Einstieg.
   - Abweichende Handlung bleibt nach ausdrücklicher Bestätigung speicherbar, wird aber unveränderbar als Abweichung vom Systemplan markiert.
   - Danach erscheint der Nutzertrade unter `Meine aktiven Trades`.

2. **Paper- und Nutzertrade strikt trennen**
   - Jede Freigabe erzeugt genau ein objektives Paper-Signal. `Trade getätigt` erzeugt zusätzlich einen persönlichen Nutzertrade mit eigener ID und eigenem Lebenszyklus.
   - Nutzerhandlungen verändern niemals den Paper-Snapshot oder dessen objektive Auswertung.
   - Später System-/Nutzer-Einstieg, -Ausstieg und -Ergebnis sowie Abweichungen durch Preis, Zeitpunkt, Stückzahl, Stop-Anpassung und Verkauf getrennt vergleichen.

3. **Aktive Trade-Ansicht**
   - Asset/Ticker, tatsächlicher Einstieg, Stückzahl, investierter Betrag, aktueller Kurs, Gewinn/Verlust in Euro und Prozent, ursprünglicher und bestätigter Stop, nächstes Ziel, Abstände, Haltedauer, aktuelle Bewertung, klare Handlung, letzte Aktualisierung und Datenqualität.
   - Nutzeraktionen: `Stop nachgezogen`, `Teilverkauf erfasst`, `Trade geschlossen`, `Details`.
   - Keine automatische Änderung und keine Orderausführung.

4. **Regelbasierte Begleitung ohne spontane Entscheidungen**
   - Fortlaufend Kursstruktur, Volumen/relatives Volumen, Stop-/Zielabstand, Unterstützungen/Widerstände, Trend, Momentum, Fehlausbruch, neue Hochs/Tiefs, Markt-/Branchenlage, Gaps, kommende Quartalszahlen, belastbare schwere Nachrichten sowie Datenalter/-qualität prüfen.
   - Zustände: `Plan intakt`, `Erhöhte Aufmerksamkeit`, `Regelbasierte Anpassung empfohlen`, `Notausstieg empfohlen`, `Daten derzeit nicht belastbar`.
   - Vor Einstieg sind messbare Regeln festgeschrieben für Stop unverändert, Stop auf Einstand, Stop unter höheres Tief, Teilgewinn an Ziel 1, Rest bis Ziel 2 und vorzeitigen Ausstieg.
   - Nie Stop weiter weg, Verlustgrenze erhöhen, Ziel ohne Regel aus Gier verschieben, schwache Position aus Hoffnung verlängern oder auf jede kleine Schwankung reagieren.
   - Notausstieg nur bei dokumentiertem Fehlausbruch, Bruch entscheidender Unterstützung, starker Gegenbewegung mit Verkaufsvolumen, belastbarer Änderung des Trade-Grunds, außergewöhnlicher Illiquidität oder klarem Strukturbruch.
   - Die App empfiehlt nur. Der Nutzer verkauft selbst und bestätigt danach `Trade geschlossen`.

#### Phase G – langfristige Validierung und spätere Erweiterungen

Status: beginnt mit den ersten echten append-only Hintergrundsignalen; eine belastbare Fallbasis ist noch nicht vorhanden.

- Echte Forward-Ergebnisse nach Einstiegsmethode, Setup, Asset-Typ, Marktphase, Region, Datenqualität und Logikversion vergleichen.
- Trefferquote nie allein verwenden; Expected Value, Ergebnis in R, Profitfaktor, Drawdown, Verpassungs-/Ablaufrate, Kosten und Opportunitätskosten berücksichtigen.
- Historische Simulation, Paper-Forward-Test und Nutzerergebnis getrennt halten.
- Keine automatische Regel- oder Gewichtsänderung. Verbesserungen nur versioniert, dokumentiert, getestet, mit ungesehenen Fällen und Rückfallmöglichkeit.
- Weitere Long-Setups, Bodenbildung/Erholung sowie Short-/Absicherung erst nach ausreichender stabiler Long-Forward-Historie untersuchen.

#### Phase G1 – COT-/Positionierungsdaten als Shadow-Layer

Status: am 2026-08-18 priorisiert aufgenommen und als sichere Shadow-Grundlage umgesetzt. Offizieller CFTC-Abruf für TFF Futures Only und Disaggregated Futures Only, paginierte Sammlung, explizites Markt-/Assetgruppen-Mapping, kausale 1W-/4W-/Perzentil-/Z-Score-Merkmale, Divergenzen, append-only SQLite-Speicher, breite Asset-Kontextzuordnung und getrennte Vergleichsmetriken sind vorhanden. Der erste reale Bestand umfasst 60.859 fehlerfrei geprüfte CFTC-Beobachtungen ab 2023. Alle Rückfülldaten gelten erst ab ihrem tatsächlichen lokalen Erstabruf als verfügbar; sie werden ohne extern belegten historischen Veröffentlichungszeitpunkt nicht rückwirkend an alte Trades gehängt. Die automatische Verknüpfung künftiger Swing-Signale, ein belastbarer historischer Veröffentlichungszeitkalender, gereifte echte Forward-Vergleiche und jede mögliche Produktionsentscheidung bleiben offen. Der gesamte Layer ist strikt `shadow_only`; bestehende Swing-Signale, Freigaben, Scores, Gewichte und Regeln bleiben unverändert.

- Offizielle CFTC-Positionierungsdaten explizit passenden Terminmärkten und breiteren Assetgruppen zuordnen. Ein Aktienindex-Future ist nur Marktkontext für eine Einzelaktie und niemals emittentenspezifische Positionierung.
- Berichtsstichtag, tatsächlicher beziehungsweise verifizierter Veröffentlichungszeitpunkt, Abrufzeitpunkt, Quelle, CFTC-Marktcode, Reporttyp und Datenfingerabdruck append-only speichern. Historische Daten ohne belastbaren Veröffentlichungszeitpunkt bleiben für Point-in-Time-Tests gesperrt.
- Je unverändertem CFTC-Markt und originaler Teilnehmerklasse Net Position, Open Interest, Veränderung gegenüber einer und vier Berichtswochen sowie ausschließlich aus damals verfügbaren Werten berechnete historische Perzentile und Z-Scores ableiten.
- Teilnehmerklassen exakt nach CFTC-Report führen. `Non-Reportables` niemals mit Retail und `Commercials`, Dealer, Asset Manager oder Producer/Merchant niemals pauschal mit Smart Money gleichsetzen.
- Divergenzen zwischen den tatsächlichen CFTC-Klassen transparent beschreiben, aber weder Richtung noch Güte aus einer vermeintlich privilegierten Gruppe behaupten.
- COT-Kontext an historische Walk-Forward- und echte Forward-Fälle nur über den letzten zum Signalzeitpunkt bereits veröffentlichten Report anhängen. Später veröffentlichte oder rückwirkend ergänzte Werte dürfen niemals in frühere Entscheidungen gelangen.
- Forschungslabels getrennt speichern: technische Long-Lage durch Positionierung bestätigt, widersprochen, neutral oder extreme Contrarian-Konstellation. Diese Labels sind Beobachtungen und verändern keine Trade-Auswahl.
- Bestehende Strategie gegen eine rein simulierte Variante `Strategie + Positionierung` vergleichen: Trefferquote, Ergebnis in R, Profitfaktor, Drawdown, MFE und MAE; Fallzahl, Marktphase, Assetgruppe und Unsicherheit sichtbar halten.
- Produktionsnutzung erst nach belastbarem historischem und echtem Forward-Mehrwert gesondert entscheiden. Keine automatische Gewichtung, Regeländerung, Freigabe oder Aktivierung.

Akzeptanzkriterien:

- Ein COT-Wert ist für ein Swing-Signal nur sichtbar, wenn sein verifizierter Veröffentlichungszeitpunkt nicht nach dem Signalzeitpunkt liegt.
- Mapping, Teilnehmerklasse und Reporttyp bleiben nachvollziehbar; unklare Zuordnungen führen zu `nicht zugeordnet` statt zu einer geratenen Verbindung.
- Wiederholtes Einlesen verändert oder löscht keine ältere Beobachtung; Korrekturen werden als neue Revision gespeichert.
- Der Shadow-Vergleich kann keine produktive Swing-Regel, keinen Score, kein Gewicht und keine Freigabe verändern.
- Tests decken Point-in-Time-Sperre, 1W-/4W-Merkmale, Perzentil/Z-Score ohne Zukunftsdaten, Teilnehmerklassen, Divergenzen, unklare Zuordnung, append-only Speicherung und die getrennten Vergleichsmetriken ab.

Ergänzender begrenzter COT-Research-Test:

- Net Position zusätzlich relativ zum damaligen Open Interest sowie ein vorab festgelegtes 52-Wochen-Perzentil beziehungsweise einen 52-Wochen-Z-Score getrennt von längeren Normalisierungen führen.
- Extrempositionierung, Umkehr aus dem Extrem und Spread/Divergenz zwischen den originalen Teilnehmerklassen als eigene Features speichern.
- Bei Finanz-Futures Dealer, Asset Manager, Leveraged Money, Other Reportables und Non-Reportables einzeln untersuchen; keine Klasse vorab als richtungsweisend festlegen.
- Prognosekraft für 5, 10 und 20 Handelstage beziehungsweise 1 bis 4 Wochen anhand Forward Return, MFE, MAE, Trefferquote und Expectancy prüfen.
- Den 52-Wochen-Ansatz nur gegen wenige vorab festgelegte einfache Normalisierungen vergleichen; keine nachträgliche Fenstersuche.
- Technische Baseline gegen `Baseline + COT als Research-/Regime-Feature` nach Kosten, Assetgruppe, Marktphase und ungesehenem Zeitraum vergleichen. Kein direkter Entry-/Exit-Filter ohne robusten Zusatznutzen.

#### Phase G2 – standardisierte quantitative Research-Pipeline

Ziel: Neue Strategien, Indikatoren, externe Daten, Videos, Trader-Regeln, Marktthesen und spätere ML-Ideen dürfen nicht direkt in die aktive Swing-Strategie gelangen. Jede Idee beginnt als klar abgegrenzte, versionierte Hypothese und muss robusten zusätzlichen Nutzen gegenüber der unveränderten Baseline zeigen.

Status: am 2026-08-22 als verbindlicher Research-Vertrag und priorisierter Folgepfad der laufenden Swing-Datensammlung aufgenommen. Vorhandene COT- sowie RSI-/EMA-Sidecars werden eingeordnet, nicht doppelt angelegt. Die getrennte rein lesende Verlust-/Edge-Diagnose umfasst jetzt alle abgeschlossenen echten Forward-Paper-Trades einschließlich künftiger Gewinner. Ein fester Pflichtfeldvertrag liefert je Trade Einstieg/Stop/Ausstieg, Stopweite, R, MFE/MAE in R und Prozent, vier MFE-Schwellen, Zeit bis MFE/Exit, Gap/Slippage, RSI-/EMA-/Käufer-/BOS-/Regimekontext und eine konkrete A–G-Begründung. Der reproduzierbare Markdown-Export ist bei jedem relevanten Swing-Work-/PLDatei-Stand in `PROJECT_STATUS.md` zu erneuern; reine Klassenaggregate reichen nicht mehr. Gespeicherte oder aus dem unveränderten Frozen-Datensatz ableitbare 5-/20-Sitzungs-Fenster, Pullback-/ATR-Stops und Zielschwellen bleiben strikt als Counterfactuals gekennzeichnet. Fehlende Werte, Preis unmittelbar vor dem Exit, Intrabar-Reihenfolge und Korrelationscluster bleiben sichtbar unbekannt. Baseline, historische Verluste, Freigaben, Stops, Targets und Produktionsparameter bleiben unverändert.

Verbindlicher Ablauf und Schutzregeln:

1. Hypothese und vermuteten Marktmechanismus vor Ergebnissichtung schriftlich definieren.
2. Rohdaten, Features, Einheiten, Zeitpunkte, Assetbezug, fehlende Daten und wenige fachlich begründete Varianten vorab festlegen.
3. Alle getesteten Features, Regeln, Parameter, Kombinationen, Stops, Exits und Modelle append-only protokollieren. Je mehr Versuche, desto stärker muss die unabhängige Bestätigung sein.
4. Nur Informationen verwenden, die am historischen Entscheidungszeitpunkt tatsächlich veröffentlicht und verfügbar waren. Nachträglich revidierte Fundamentals/Makrodaten, spätere Indexmitglieder, zukünftige Highs/Lows, nicht abgeschlossene Kerzen sowie zukünftige Volumen-/Indikatorwerte sind ausgeschlossen.
5. Featurezeitpunkt strikt von späteren Returns, MFE/MAE und Trade-Ergebnissen trennen.
6. Neue Ideen zuerst als Research-Features erfassen. Keine sofortige Logik `Feature erfüllt → Trade erlauben/verwerfen`.
7. Korrelation, Regression und passende einfache Statistik als erste Analyse nutzen; p-Wert, R² oder Z-Score allein beweisen keinen Edge. Fachlich plausible Wechselwirkungen dürfen vorab begrenzt getestet werden.
8. Immer unveränderte Baseline gegen genau bezeichnete Zusatzvariante vergleichen. Keine neue Regel entwickeln, nur weil bekannte Verlusttrades damit verschwunden wären.
9. Entwicklung/In-Sample, Validation, endgültiges Out-of-Sample, purged Walk-Forward, echter Forward-/Shadow-Test und Papertrade strikt trennen. Betrachtete Testdaten sind nie wieder unberührt.
10. Multiple Testing, Data-Snooping, Overfitting, abhängige Fälle und wirtschaftlich identische Listings berücksichtigen. Keine breite nachträgliche Schwellenwert- oder Hyperparametersuche.
11. Ergebnisse mindestens mit Fällen/Trades, Gewinnern/Verlierern, Forward Returns, Expectancy/R, Profitfaktor, Drawdown, MFE/MAE und Unsicherheit nach Assetgruppe, Marktphase und Zeitraum zeigen.
12. Spread, Slippage, Gebühren, Liquidität und realistische Entry-Ausführung berücksichtigen, sobald handelbare Entries, Stops oder Exits verglichen werden.
13. Robustheit ist wichtiger als das beste historische Ergebnis. Breite stabile Bereiche, mehrere Zeiten/Regime/Assets und kleine sinnvolle Parameteränderungen sind Pflicht; ein schmales Optimum ist Warnsignal.
14. Komplexität muss sich verdienen. Bei ähnlicher Evidenz bleibt die einfachere Variante. Schwache Filter dürfen nicht kombiniert werden, bis der Backtest positiv wird; redundante Merkmale zählen nicht als mehrere Bestätigungen.
15. Misserfolg ist erlaubt. Ohne robusten Zusatznutzen wird die Idee verworfen und nicht so lange verändert, bis sie historisch funktioniert.
16. Kill-Regel: Scheitert eine Idee trotz angemessener Stichprobe wiederholt Out-of-Sample oder im Forward-Test beziehungsweise lässt sie sich nur durch weitere Filter retten, wird sie eingestellt oder grundlegend neu formuliert.
17. ML unterliegt denselben Regeln und darf keine Schutz-, Risiko- oder Freigabestufe umgehen.

Einordnung externer Ideen vor einem Test:

- `A – nicht übernehmen/nicht sinnvoll testen`: kein plausibler Mechanismus, keine kausalen Daten oder kein sauberer Test.
- `B – begrenzte Research-Hypothese`: plausibel und testbar, aber ohne robuste Evidenz; nur Research/Shadow.
- `C – starke externe Vorabevidenz`: gezielt unabhängig validieren; ebenfalls keine direkte Produktionsregel.

Ergebnis jeder tatsächlich geprüften Hypothese:

- `A – kein robuster Mehrwert`: verwerfen und negative Evidenz dokumentieren.
- `B – interessant, aber unzureichend/uneinheitlich`: nur weiter beobachten oder einen vorab festgelegten Folgetest durchführen.
- `C – robuster Out-of-Sample-Zusatznutzen`: Kandidat für eine gezielte neue Strategieversion und danach vollständige Forward-/Shadow-/Paper-Validierung; keine automatische Integration.

Integration erfordert gemeinsam: vorher definierte Hypothese, angemessene effektiv unabhängige Fallzahl, relevanten Baseline-Zusatznutzen, stabile Validation und endgültiges Out-of-Sample, bestandenen Walk-Forward, positiven Nutzen nach Kosten sowie anschließende echte Forward-/Shadow- und Paper-Bestätigung. Die Entscheidung bleibt versioniert und manuell.

##### G2.1 – Pullback-/Trendfortsetzungs-Hypothese

Status 2026-08-22: Die technische Datensatzstufe ist umgesetzt. Der neue getrennte Pass erkennt aus dem vollständigen Frozen-OHLCV-Strom breite objektive Pullback- und Breakout-Situationen, ohne spätere Rendite, MFE/MAE oder Long-v1-Auswahl zu verwenden. Impulsstärke/-dauer, kontinuierliche Pullback-Tiefe/-dauer, bearish Kerzen/Serien, ATR-Geschwindigkeit, Käuferbestätigung, Key-Level-Abstände und die bestehende RSI-/EMA-/ATR-/Volumen-/Marktphasenlogik werden Point-in-Time gespeichert. Labels und konservative Stop-/Exit-Experimente liegen getrennt append-only. Der reale 2.520-Asset-Pass wartet unverändert auf den Abschluss der bestehenden Kampagne; es gibt noch kein Development-Ergebnis und keine Regeländerung.

Leitfrage: Liefert nach einem starken Aufwärtsimpuls die objektive Struktur des Pullbacks zusammen mit erneuter Käuferbestätigung einen stabilen zusätzlichen Edge?

Als eigener Point-in-Time-Research-Sidecar ohne Baseline-Filter erfassen:

- Stärke und Dauer des vorherigen objektiven Aufwärtsimpulses
- kontinuierliche Pullback-Tiefe relativ zur vorherigen Bewegung
- Pullback-Dauer in abgeschlossenen Handelssitzungen
- Anzahl bearish Kerzen und längste ununterbrochene bearish Serie
- Pullback-Stärke/-Geschwindigkeit ATR-normalisiert
- Käuferbestätigung `Close[t] > High[t-1]` nach abgeschlossener Signalkerze
- vorhandene RSI14-, EMA20-/EMA50-, Volumen-, ATR-/Volatilitäts- und Marktregimewerte am Featurezeitpunkt
- Forward Returns sowie MFE/MAE ausschließlich als spätere getrennte Zielvariablen

Vorab begrenzte Hypothesen:

- Wenige breite Pullback-Tiefenbereiche vergleichen; 50 Prozent oder eine andere Tiefe nicht voraussetzen.
- Anzahl/Serien bearish Kerzen prüfen. Die TikTok-Regel `drei bearish Kerzen = kein Trade` bleibt eine Hypothese, kein Filter.
- `Close[t] > High[t-1]` gegen Baseline und eine Variante ohne Bestätigung vergleichen.
- Bei Bestätigung frühester Entry zum nächsten tatsächlich handelbaren Kurs nach Abschluss der Signalkerze, nie rückwirkend zu ihrem Schlusskurs.

Vorab begrenzte Stops: Pullback-Low, Pullback-Low plus ATR-Puffer, ATR-basierter Stop und bestehende Pullback-Längen-/Strukturregel.

Vorab begrenzte Exits: vollständiger Exit bei 1R, 1,5R, 2R oder 3R, bestehender/trendbasierter Exit, Break-even nach vorab festem MFE sowie vorab definierter Teilgewinn plus Restposition. Jede Variante verwendet denselben realistischen Entry, Kosten/Slippage und eine konservative Reihenfolge bei Stop und Ziel in derselben Kerze.

Ergebnisse werden nach Asset, Assetgruppe, Marktphase, Zeitraum und Development/Validation/Holdout gezeigt. Erst nach In-Sample → Out-of-Sample/Walk-Forward → Forward/Shadow → Paper darf A/B/C vergeben werden; nur C darf eine neue Strategieversion vorbereiten.

##### G2.2 – begrenzter Fibonacci-Vergleich

Status 2026-08-22: Die Feature- und Experimentgrundlage ist umgesetzt. 0,618 sowie 61,8–78,6 Prozent werden auf derselben vorher objektiv bestimmten Impulsstruktur berechnet und gegen zwei gleich breite Kontrollzonen markiert. Pullback-Low, ATR-Puffer, ATR-Stop und vorhandener Struktur-Stop sowie 1R/1,5R/2R/3R, Break-even und Teilgewinn/Rest werden vom gleichen nächsten handelbaren Einstieg mit denselben Kosten und konservativer Intrabar-Reihenfolge simuliert. Extensions bleiben gesperrt. Die echte Development-Auswertung steht bis zum Vollpass aus.

- Kontinuierliche Pullback-Tiefe aus G2.1 wiederverwenden; keine zweite abweichende Berechnung.
- Zone 61,8 bis 78,6 Prozent gegen ähnlich breite Nicht-Fibonacci-Zonen und kontinuierliche Tiefe prüfen.
- Exakten Entry bei 0,618 nur als vorab definierte Vergleichshypothese einschließlich Lage zum vorher objektiv bestimmten Key-Level untersuchen.
- Trefferquote, Expectancy, Forward Returns, MFE/MAE, R, Profitfaktor und Drawdown nach Assetgruppe, Marktphase und ungesehenem Zeitraum vergleichen.
- Keine Suche nach weiteren Retracement-Leveln, wenn 61,8 bis 78,6 Prozent schlecht abschneidet.
- Extensions `-0,27`, `-0,62`, `-1` nur nach positivem Ergebnis in einem neuen separaten Exit-Test untersuchen und Nutzen von Managementprinzip versus Fibonacci-Level trennen.

##### G2.3 – weitere einzeln zu testende Framework-Bausteine

Status 2026-08-22: Algorithmischer bestätigter Swing-/BOS-Zustand, Daily-/Weekly-/Monthly-/Quarterly-/Yearly-Open einschließlich Abstand/Kontakt/Retest/Alter, abgeschlossene historische Kalenderperioden und Point-in-Time-COT einschließlich 52-Wochen-Normalisierung, Extrem-/Umkehrmerkmalen und Teilnehmer-Spreads sind technisch umgesetzt. Daily-OHLCV ist für belastbare POC/VAH/VAL-Werte unzureichend; Volume Profile bleibt deshalb explizit `nicht verfügbar` und wird nicht approximiert. Confluence bleibt gesperrt. Reale Feature-Abdeckung und Development-Evidenz entstehen erst nach dem geschützten Vollpass.

1. **Saisonalität:** Kalenderwoche, Monat, Monats-/Quartalsanfang und -ende sowie historische Forward-Performance vergleichbarer Kalenderperioden Point-in-Time erfassen. Saisonale Winrate, Durchschnittsrendite und risikoadjustierte Kennzahl über rollierende Fenster prüfen. Keine freie Start-/Enddatensuche; `Winrate ≥ 65 %` und `Sharpe > 1` nur als Vergleichshypothese.
2. **Opening Levels:** Daily-, Weekly-, Monthly-, Quarterly- und Yearly-Open erfassen. ATR-normalisierten Abstand, Kontakt, ersten/wiederholten Retest, Alter und Reaktion untersuchen; keine nachträgliche Wahl des besten Levels.
3. **Fixed Range Volume Profile:** POC, VAH und VAL nur aus vorab je Timeframe definierten Fenstern berechnen. Abstand, Kontakt/Retest, Alter, Reaktion und Datenqualität erfassen; ohne geeignete granulare Volumendaten kein scheinpräzises Profil.
4. **Break of Structure:** HH/HL/LH/LL und Swing-Punkte algorithmisch für Long/Short definieren. Intrabar-/High-Low-Bruch, Candle-Close-Bruch und höchstens eine vorab festgelegte ATR-Mindestüberschreitung vergleichen. Entry nach Bestätigung frühestens im nächsten handelbaren Kurs. BOS erst allein, danach bei eigenem Nutzen mit Opening-/Volume-Level testen.
5. **Trade-Management:** feste R-Exits, Break-even nach MFE, Teilgewinn plus Rest und bestehenden Trendexit getrennt vergleichen. Video-Variante `BE bei -0,27`, `50 % bei -0,62`, `Rest bei -1` bleibt Hypothese; Netto-Expectancy nach Teilverkäufen, Gebühren und Slippage.
6. **Confluence erst in Stufe zwei:** Nur unabhängig nützliche Komponenten gezielt als Opening+BOS, Volume Profile+BOS, Opening+Volume Profile oder Technik plus validiertes Makro/COT/Saisonalität testen. Zusätzlichen Out-of-Sample-Nutzen gegenüber Einzelkomponenten verlangen.
7. **Gesamtframework zuletzt:** `Bias → Zone → Bestätigung → Entry → Risiko → Exit` erst aus zuvor unabhängig validierten Bausteinen bilden und erneut gegen die einfache Baseline testen.

##### G2.4 – ML-tauglicher Datenvertrag und Surprise-Research

Status: Der erste reine Datenvertrag ist am 2026-08-22 umgesetzt. Er erzeugt reproduzierbar fingerprintete, ausschließlich `shadow_only` nutzbare Kandidatenzeilen aus vorhandenen Swing-Fällen, trennt Identität, Strategie, Features, Quellen und spätere Zielvariablen technisch voneinander, bewahrt fehlende Werte und sperrt nach dem Featurezeitpunkt verfügbare Quellen sowie Zielvariablen im Featurebereich fail-closed. Das Manifest erlaubt nur zeitbasierte purged Walk-Forward-Splits und besitzt keine Modell-, Trade-, Regel- oder Produktionswirkung. Ein Training, eine Modellauswahl und eine produktive Nutzung sind damit ausdrücklich noch nicht umgesetzt.

Je Fall ML-tauglich, append-only und Point-in-Time speichern:

- stabile Fall-, Asset-, Issuer-, Listing-, Strategie-, Daten- und Featureversion
- Featurezeitpunkt sowie Quellen- und Veröffentlichungszeitpunkte
- RSI14, EMA20/EMA50, Pullback-Tiefe/-Struktur, Volumen, ATR/Volatilität, Marktregime und später einzeln validierte Features
- fehlende Werte/Datenqualität statt erfundener oder rückwirkend aufgefüllter Werte
- Zielvariablen getrennt: Forward Returns, MFE, MAE, Entry-/Stop-/Exit-Ereignisse und R
- keine spätere Revision, Zielvariable oder Information aus einem zukünftigen Balken im Featurebereich

Surprise-/Expectation-Research darf mit einfachen Methoden beginnen, wenn Erwartung, tatsächlicher Wert und Veröffentlichungszeitpunkt belastbar vorliegen: Earnings Surprise, Revenue Surprise, Guidance-Änderung, Makro-/Inflations-Surprise und Zinsentscheidung relativ zur damals dokumentierten Markterwartung. Ohne damalige Konsenserwartung keine rückwirkend konstruierte Surprise; zunächst keine Filterwirkung.

Späterer Shadow-ML-Pfad erst bei ausreichender Datenreife:

- wenige einfache interpretierbare/robuste Modelle zuerst; komplexere müssen sie stabil schlagen
- nur zeitbasierte Train-/Validation-/Test-Splits und purged Walk-Forward, kein Random-Split
- Featurezahl und Hyperparametersuche begrenzen, alle Versuche protokollieren
- Kombinationen gegen Einzelmerkmale und regelbasierte Baseline vergleichen
- ML darf Shadow-Scores/Wahrscheinlichkeiten speichern, aber keine Trades erzeugen/blockieren, Positionen/Risikolimits ändern, Regeln ersetzen oder Produktion aktivieren

Aktiver Einfluss bleibt gesperrt, bis Baseline und Datenbasis reif sind, ML mehrere ungesehene Walk-Forward-Zeiträume nach Kosten robust schlägt und echte Shadow-/Paper-Ergebnisse den Vorteil bestätigen. Danach ist weiterhin eine eigene manuelle Freigabe Pflicht.

##### G2.5 – vorbereitender Short-Readiness-Layer

Status 2026-08-22: Vor dem ersten realen Broad-Vollpass technisch umgesetzt. Verbindliche Reihenfolge: `Broad Research → shared direction-neutral historical features → Long research first → later separate Short research`. Der aktuelle Broad-Pass erzeugt und speichert weiterhin ausschließlich Long-Kandidaten. Bearishe Merkmale sind nur kausale, nicht ausgewertete Infrastruktur; sie erzeugen weder Short-Signale noch Short-Challenger, Rankings, Confluence, Paper-/Shadow-Entwürfe oder eine Produktionsfreigabe.

- Richtungsneutrales Research-Modell unterstützt intern `long | short`; der reale Kandidatenstrom bleibt fest `long`. Broad-Speicher Schema 3 hält die Richtung explizit und migriert den noch leeren Vorpass-Speicher nicht löschend.
- Der gemeinsame OHLCV-Pass speichert zusätzlich objektiven Abwärtsimpuls, Stärke und Dauer, anschließende Rally, kontinuierliche Retracement-Tiefe, Rallydauer, bullische Kerzen und längste Serie sowie ATR-normalisierte Rallygeschwindigkeit.
- Bearishe Bestätigung `Close[t] < Low[t-1]`, bestätigte Lower Highs/Lows, High-/Low- und Close-Break, bearish BOS, ATR-normalisierte Überschreitung und Bestätigungszeitpunkt werden ausschließlich aus Daten bis zur abgeschlossenen Featurekerze erzeugt.
- Der vorhandene RSI-/EMA-/ATR-/Volumen-/Volatilitäts-/Marktphasen-, Opening-Level-, Saisonalitäts- und COT-Kontext wird referenziert statt doppelt berechnet. Ergänzt sind Kurs unter EMA20/EMA50 und EMA20 unter EMA50.
- Die gespiegelte Fibonacci-Geometrie speichert Rally-Retracement, Abstand zu 0,618, Lage in 61,8–78,6 Prozent und ATR-Abstand. Es wird keine Short-Fibonacci-Regel oder Optimierung abgeleitet.
- Getrennte Labels enthalten für 5/10/20/25 Sitzungen Forward Return, zukünftiges Maximum/Minimum, maximale Auf-/Abwärtsbewegung in Prozent und ATR, Zeit bis Hoch/Tief sowie die Rohwerte, aus denen spätere Long- und Short-MFE/MAE eindeutig ableitbar sind. Kein Label beeinflusst Kandidatenauswahl oder Features.
- Richtungsneutrale Preisordnungsprüfung kennt `Stop < Entry < Target` für Long und `Target < Entry < Stop` als späteren Short-Vertrag. Aktuelle Order-, Risiko-, Scanner-, Paper- und Shadow-Pfade akzeptieren weiterhin nur Long und sperren explizite Short-Kandidaten fail-closed.
- Borrow-Verfügbarkeit, Borrow Fees, Finanzierung, Broker-Shortkosten und reale Short-Spreads bleiben sichtbar `nicht erhoben / nicht approximiert`.
- Feature-Schema: `swing-broad-pit-features-short-readiness-2026.08.22-v2`; Label-Schema: `swing-broad-direction-neutral-labels-2026.08.22-v2`. Der Frozen-Dataset-Fingerprint bleibt unverändert. Eine spätere Short-Forschung benötigt weiterhin eigene Hypothesen, Strategieversion sowie Validation-, Holdout-, External-, Forward-, Paper- und Shadow-Gates nach stabiler Long-Validierung.

##### G2.6 – spätere technische Research-Reserve

Status 2026-08-22: Ausschließlich als späterer verbindlicher Prüfauftrag dokumentiert. Die folgenden Indikatoren sind weder im ersten Broad-Research-Pass enthalten noch dafür implementiert, getestet oder automatisch optimiert. Broad-Feature-Vertrag, Fingerprints, Queue, Laufzeit und laufende Forschung bleiben unverändert.

Research-Reserve:

- Stochastic
- Williams %R
- CCI
- zusätzliche ROC-Varianten
- weitere MACD-Parametersets
- zusätzliche Moving-Average-Kombinationen
- Ichimoku
- Supertrend
- größere Candlestick-Pattern-Bibliotheken
- weitere vergleichbare technische Indikatoren nur bei später klar begründetem, nicht bereits abgedecktem Zusatznutzen

Nach Abschluss **und Auswertung** des ersten Broad Research muss die Reserve aktiv erneut berücksichtigt werden. Das System soll einen Reserve-Indikator später von sich aus zur fachlichen Prüfung vorschlagen, wenn vorhandene Research-Ergebnisse eine konkrete Informationslücke erkennen lassen oder belastbar darauf hindeuten, dass dieser Indikator zusätzliche, nicht bereits durch vorhandene Features abgedeckte Information messen könnte. Ein Vorschlag ist noch keine Aufnahme, Optimierung, Strategieänderung oder Freigabe.

Mindestens eine der folgenden Bedingungen muss für einen aktiven Vorschlag nachweisbar erfüllt sein:

1. Bestehende Features erklären einen relevanten Teil der Gewinner-/Verlierer-Trennung nicht.
2. Development-Ergebnisse zeigen eine konkrete wiederkehrende Struktur, die der Reserve-Indikator fachlich messen könnte.
3. Forward-Fehlerdiagnosen zeigen wiederholt ein Muster, das mit den bisherigen Features nicht ausreichend erfasst wird.
4. Ein vorhandener Research-Baustein weist eine klar definierte Messlücke auf.

Beispiele für zulässige begrenzte Hypothesen:

- Trennen vorhandene Momentum-Features gute und schlechte Setups nicht ausreichend, Stochastic, Williams %R oder CCI einzeln als mögliche zusätzliche Momentummessung prüfen.
- Bleibt Trendqualität trotz EMA-/Slope-Features unklar, Supertrend oder Ichimoku einzeln als mögliche Messung dieser konkreten Lücke prüfen.
- Scheint die Änderungsdynamik des Momentums relevant, genau eine fachlich begründete ROC-Variante mit vorab festgelegtem Parameter untersuchen.
- Reichen Candle-Rohmerkmale für bestimmte wiederkehrende Reversal-Situationen nicht aus, eine kleine vorab definierte Candlestick-Pattern-Gruppe prüfen.

Nicht zulässig:

- alle Reserve-Indikatoren pauschal testen
- große Grid Search oder Parameter-Mining
- Aufnahme nur wegen Bekanntheit oder Popularität eines Indikators
- Holdout-Ergebnisse nachträglich zur Auswahl eines Reserve-Indikators verwenden
- mehrere Reserve-Indikatoren gleichzeitig als neue Confluence hinzufügen
- den ersten Broad-Research-Pass, seinen Featurevertrag oder seine Ergebnisse rückwirkend erweitern oder umdeuten

Verbindlicher Ablauf für jeden später vorgeschlagenen Reserve-Indikator:

1. Konkrete Hypothese und die zu schließende bestehende Informationslücke dokumentieren.
2. Redundanz gegenüber vorhandenen Features prüfen und möglichst wenige Parameter vorab festlegen.
3. Ausschließlich Development für die erste Zusatznutzenbewertung verwenden.
4. Bei ausreichendem, nicht redundantem Mehrwert Regel beziehungsweise Feature eindeutig versioniert einfrieren.
5. Erst danach dieselbe eingefrorene Version auf Validation/Holdout beziehungsweise neuer ungesehener Evidenz prüfen.
6. Bei fehlendem Zusatznutzen die Hypothese verwerfen; keine stille Parameteränderung oder Kombination mit weiteren Reserve-Indikatoren.

Zielbild:

`Current Broad Feature Set → Broad Research Results → identify unresolved information gaps → actively reconsider Research Reserve → test only justified reserve hypotheses → freeze → Validation / Holdout`

##### Verbindlicher G2-Validierungspfad

`Frozen Historical Data → Broad Research Candidates → Point-in-Time Features → Development Pattern Discovery → Fixed Challenger → Validation → Holdout → External Unseen Asset Universe → True Forward → Autonomous Paper → Shadow Live → Echtgeld-Gate`

- `Frozen Historical Data` ist mit dem unveränderlichen Dataset-Fingerprint `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed` vorhanden. Der neue Pfad lädt daraus ausschließlich lokal und löst keine unnötigen Providerabrufe aus.
- `Broad Research Candidates`, `Point-in-Time Features`, getrennte spätere Labels, Stop-/Exit-Kontrafakten, append-only Resume-Speicher, Code-/Feature-Fingerprints und der Development-only A/B/C-Vergleich sind technisch umgesetzt. Der Development-Bericht zeigt zusätzlich ungefilterte Basis, Expectancy, verlorene Tradezahl und drei kleine vorab festgelegte Nachbarschaften für RSI, EMA20/50 und BOS. Der reale Vollpass startet erst nach 248/248 der bestehenden Kampagne; beim zuletzt geprüften relevanten Stand 243/248 sind deshalb weiterhin 0 breite Kandidaten gespeichert.
- Der automatische Übergang ist fail-closed umgesetzt: Exakt 248/248, ein vollständiger gültiger Walk-Forward-Audit, identischer finalisierter Frozen-Dataset-Fingerprint sowie Code-/Feature-Fingerprints sind Pflicht. Ein einmaliger append-only Nachweis öffnet anschließend nur kleine 16-Asset-Researchblöcke; Schutzfenster, Produktionslocks, reguläre Scans und Resume werden zwischen den Blöcken erneut geprüft. Der alte Kampagnenbestand wird weder geändert noch neu gestartet, zusätzliche Downloads sind verboten.
- Ein `C`-Hinweis darf nur aus vorab festgelegten Development-Mindestwerten entstehen und bedeutet ausschließlich: nach expliziter manueller Bestätigung als neue unveränderliche Challenger-Regel einfrieren. Keine Regel wird automatisch erzeugt, aktiviert oder in Long-v1 übernommen.
- Für einen bestätigten C-Challenger ist der Ground-up-Handoff technisch umgesetzt: fester Regel-/Code-/Daten-/Kostenfingerprint, vollständiger Rescan des Frozen-Bestands, zuerst Validation, danach nur nach manueller Stufenprüfung Holdout, anschließend External und True Forward. Development darf nicht nachträglich filtern; jede Parameteränderung erzeugt eine neue Version und beginnt den Pfad neu.
- ML-Datensatzadapter ist um das breite Feature-Schema erweitert. Features und Labels bleiben physisch/logisch getrennt; Random Split, Modelltraining, automatische Featureauswahl, Regeländerung und Produktionsaktivierung sind weiterhin gesperrt.

##### External Unseen Asset Universe

Status 2026-08-22: Der outcome-blinde append-only Auswahl-, Freeze- und Ergebnisvertrag ist technisch umgesetzt. External-Ergebnisse sind zusätzlich bis zum manuell bestandenen Holdout-Gate exakt derselben Challenger-Version gesperrt. Ein reales externes Universum ist noch nicht zusammengestellt oder getestet; aktuell bleibt diese Stufe reine Infrastrukturprüfung.

- Erst nach bestandenem ursprünglichem Development-/Validation-/Holdout-Pfad ein neues liquides Universum vor Ergebnissichtung zusammenstellen und fingerprinten. Zielgröße sind mehrere hundert bis etwa 1.000 brauchbare Assets, jedoch niemals auf Kosten von Identität, Liquidität, Historie oder Datenqualität.
- Ticker aus den ursprünglichen 2.520 Assets, derselbe Emittent sowie wirtschaftlich identische Instrumente/Mehrfachlistings ausschließen. Unklare Emittentenabhängigkeit bleibt fail-closed statt als unabhängig behauptet zu werden.
- Auswahlquelle, Qualitäts-/Liquiditätsvertrag, Regionen, Assetgruppen, Listing-/Issuer-/Instrumentidentität und vollständige Assetliste vor Strategieergebnissen einfrieren.
- Exakt dieselbe bereits eingefrorene Strategie ohne Parameteränderung mit gleichen Kosten-, Purging-, Abhängigkeits- und Auswertungsregeln prüfen. Expectancy, Profitfaktor, Drawdown, Trefferquote, Verlustserien, Marktphasen, Regionen und Zeitstabilität getrennt ausweisen.
- Ergebnisse dürfen niemals zur Optimierung derselben Strategieversion zurückfließen. Ein Kollaps sperrt diese Version; jede Änderung erzeugt eine neue Version und benötigt später eine neue ungesehene Prüfung.
- Auch ein bestandenes External Gate ist keine Produktionsfreigabe. Danach bleiben True Forward, autonomer Paper-Bot, Shadow Live und ein ausdrücklich manuelles Echtgeld-Gate verpflichtend.

#### Langfristiges Endziel: vollständig regelbasierter autonomer Swing-Trading-Bot

Wirtschaftliches Langfristziel ist ein möglicher regelmäßiger monatlicher Zusatzverdienst. Es gibt keine Renditegarantie und keine Anforderung, jeden Monat Gewinn zu erzielen. Optimiert wird auf einen robusten positiven Erwartungswert nach realistischen Kosten bei kontrolliertem Risiko, nicht auf maximalen historischen Gewinn.

Verbindliche Entwicklungsfolge:

`bestehende Validierung → Strategie-Freeze → autonomer Paper-Bot → Shadow-Live → Echtgeld-Gate → begrenzter Live-Bot → kontrollierte Skalierung`

Keine Stufe darf übersprungen werden. Gute historische Walk-Forward-Ergebnisse allein erlauben weder Brokerintegration noch Echtgeldbetrieb. Die derzeit laufenden historischen Swing-Walk-Forward-Tests bleiben priorisiert; aktuell werden keine Brokerintegration und keine Echtgeldfunktion entwickelt.

##### Strategie-Freeze

Status: Die technische Freeze-Infrastruktur ist umgesetzt. Baseline und acht vorab deklarierte technische Challenger besitzen neun getrennte unveränderbare Artefakte mit Strategie-, Parameter-, Filter-, Risiko-, Order-, Positions-, Exit-, Kosten- und Datenvertrag sowie Code-, Konfigurations-, Komponenten- und Datenfingerabdrücken. Die Historie ist append-only; kein Freeze ist aufgrund bisheriger Performance freigegeben oder automatisch produktiv aktiviert.

- Vor autonomem Paper-, Shadow-Live- oder Live-Betrieb eine konkrete Strategieversion mit Signalen, Filtern, Risikoregeln, Orderlogik, Positionsmanagement, Exitregeln, Kostenmodell und Datenvertrag unveränderbar einfrieren.
- Jede fachliche oder parametrische Änderung erzeugt eine neue Strategieversion und muss die für ihre Zielstufe erforderliche Validierung erneut durchlaufen.
- Kein nachträgliches Anpassen wegen einzelner schlechter Trades, aktueller Marktereignisse oder kurzfristiger Ergebnisverschlechterung.
- Eingefrorene Version, Datenbestand, Code, Parameter und Freigabeentscheidung reproduzierbar fingerprinten und append-only dokumentieren.

##### Autonomer Paper-Bot

Status: Die brokerlose technische Grundlage ist umgesetzt und in den bedienungsfreien Swing-Hintergrundlauf eingebunden. Eigene append-only Evidenz, idempotente Zyklen und Ereignisse, persistenter Wiederanlauf, kausale virtuelle Fills, Stop/Ziele/Teilverkauf/Exit sowie fail-closed Verhalten bei fehlenden Daten sind vorhanden. `paper_only` ist technisch erzwungen; die reale Stichprobe ist noch unreif und erlaubt keine Strategieänderung.

Der autonome Paper-Bot simuliert ohne Nutzereingriff den vollständigen Zyklus:

`Marktdaten → Signal → Risk Check → virtuelle Order → Ausführung → Positionsmanagement → Exit → Auswertung`

- Virtuelle Orders und Fills kausal aus den damals verfügbaren Daten erzeugen; keine nachträglich günstigere Ausführung annehmen.
- Dieselbe eingefrorene Strategie-, Risiko-, Order- und Positionslogik verwenden, die später im Shadow-Live-Betrieb geprüft werden soll.
- Ausfälle, Neustarts, doppelte Ereignisse, Teilzustände und fehlende Daten sicher behandeln und vollständig auditieren.
- Ergebnisse getrennt von historischen Walk-Forward-, bestehenden Forward-/Paper- und persönlichen Nutzertrade-Daten speichern; nichts rückwirkend umdeuten.

##### Shadow-Live

Status: Die brokerlose Grundlage ist umgesetzt. Aktuelle Signale erzeugen append-only Orderentwürfe mit Listing, Zeitstempel, Datenquelle, Risk-Entscheidung, Limit, Stop, Zielen und Positionszustand, werden aber niemals übertragen. Reale Bid-/Ask-, Spread-, Slippage- oder Fill-Beobachtungen werden nur gespeichert, wenn sie tatsächlich belastbar vorliegen; fehlende Ausführungsdaten bleiben unbekannt und werden nicht geschätzt.

- Mit echten aktuellen Marktdaten exakt die Orders erzeugen, die ein Live-Bot real senden würde, sie aber nicht an einen Broker übermitteln.
- Tatsächliche Handelbarkeit, Bid/Ask-Spread, Slippage, Limit- und Stop-Verhalten, Gaps, Teilfüllungswahrscheinlichkeit, Ablehnungen, verpasste Ausführungen und Abweichung zwischen simulierter und real ausführbarer Preisbasis messen.
- Daten-, Entscheidungs-, Orderentwurfs- und Positionszustände mit Zeitstempel und Quelle append-only speichern.
- Shadow-Live darf keine Brokerorder erzeugen und benötigt noch keine produktiven Broker-Zugangsdaten.

##### Gemeinsame Bot-Architektur

Status: Strategie, unabhängige gemeinsame Risk Engine, Ausführungssimulation, Positionszustand und Append-only Audit sind technisch getrennt. Scanner, Paper-Bot und Shadow-Live verwenden denselben versionierten Risiko- und Orderplan; die Risk Engine kann von keinem Research-Challenger umgangen werden. Es existiert weder Broker-Adapter noch Echtgeldpfad.

##### Echtgeld-Gate

- Historische Walk-Forward-Ergebnisse sind nur ein Teil der Evidenz und reichen allein niemals aus.
- Das Gate berücksichtigt die bereits vorhandene echte Forward-/Paper-Evidenz sowie anschließend autonome Paper-Bot- und Shadow-Live-Ergebnisse, jeweils nach Strategieversion, Marktphase, Assetklasse, Datenqualität und Kostenlage getrennt.
- Erwartungswert nach Kosten, Profitfaktor, Drawdown, Verlustserien, Tail-/Gap-Risiko, Slippage, Fill-Qualität, Betriebsstabilität, Abdeckung und Abweichung zwischen Simulation und Shadow-Live gemeinsam bewerten.
- Konkrete quantitative Freigabeschwellen erst anhand der dann vorhandenen realen Daten fachlich herleiten, vor der Prüfung versioniert festlegen und dokumentieren. Keine willkürlichen Rendite- oder Monatsgewinnziele vorab erfinden.
- Freigabe erfordert eine ausdrückliche dokumentierte Nutzerentscheidung. Ein bestandenes technisches oder statistisches Gate aktiviert niemals selbstständig Echtgeldhandel.

##### Begrenzter Live-Bot

Erst nach bestandenem Echtgeld-Gate darf eine getrennte Live-Bot-Phase mit folgender Architektur entwickelt und ausdrücklich freigegeben werden:

`Strategy Engine → unabhängige Risk Engine → Execution Engine → Position Management → Monitoring/Audit`

- Der Nutzer legt ein separates maximales `Bot-Tradingkapital` fest. Ausschließlich dieses ausdrücklich freigegebene Kapital darf verwendet werden; anderes Vermögen, Portfolio- oder Swing-Nutzerkapital ist technisch unerreichbar.
- Risk-Limits sind außerhalb der Strategy Engine verbindlich durchzusetzen und können weder von Strategie noch KI überschrieben werden.
- Kill-Switch und sofortige manuelle Abschaltung bereitstellen.
- Bei Verlust-, Drawdown-, Positions-, Kapital-, Datenqualitäts- oder Systemgrenzen automatisch weitere Orders sperren.
- Bei unklaren Markt-, Daten-, Broker-, Order- oder Positionszuständen fail-closed handeln.
- Doppelorders verhindern und Orderübermittlung idempotent gestalten.
- Bot-Positionen fortlaufend gegen Broker-Positionen abgleichen; Abweichungen sperren neue Aktivität und verlangen Klärung.
- Teilfüllungen, Ablehnungen, Stornos, abgelaufene Orders und unerwartete Brokerzustände explizit behandeln.
- API-, Netzwerk-, Marktdaten-, Broker- und Prozessfehler absichern; nach Neustart oder Abbruch ausschließlich aus geprüftem persistentem Zustand sicher fortsetzen.
- Jede Entscheidung, Risikoprüfung, Order, Brokerantwort, Positionsänderung, Sperre und manuelle Aktion vollständig append-only auditieren.

##### Kontrollierte Live-Skalierung

- Echtgeldbetrieb mit kleinem, fest begrenztem Bot-Tradingkapital beginnen.
- Kapital niemals automatisch wegen kurzfristiger Gewinne oder einer kleinen positiven Stichprobe erhöhen.
- Jede Erhöhung benötigt eine neue dokumentierte Prüfung der realen Live-Ergebnisse gegen autonome Paper- und Shadow-Live-Ergebnisse einschließlich Kosten, Slippage, Drawdown, Betriebsfehlern und Verhaltensabweichungen.
- Skalierungsstufen, Rückstufungsbedingungen und maximale Kapitalgrenzen vor Aktivierung versioniert festlegen; bei verschlechterter Evidenz reduzieren oder sperren.

##### Lernende Systeme und KI im Trading-Betrieb

- KI oder Lernlogik dürfen Live-Tradingregeln, Risikolimits, Strategieparameter oder Produktionskonfiguration niemals selbstständig ändern.
- Neue Strategien, Modelle, Merkmale oder Regeländerungen beginnen wieder im vollständigen Forschungs-, Walk-Forward-, Forward-, Strategie-Freeze-, Paper-, Shadow- und Freigabeprozess.
- KI darf keine unabhängige Risk Engine umgehen, keine Orderfreigabe erteilen und keine Produktionsversion aktivieren.
- Jede spätere lernende Produktionskomponente benötigt weiterhin Modellregister, reproduzierbare Daten, manuelle Freigabe, Canary, Rollback und vollständiges Audit.

Späterer separater Hebelmodus:

- in der aktuellen Entwicklungsstufe nicht umsetzen und aus normalem Finder/Universum ausgeschlossen halten
- erst nach großer echter Forward-Historie, positivem Expected Value, stabilen Ergebnissen über mehrere Marktphasen, akzeptablem Drawdown und verlässlicher Stop-/Ausstiegslogik neu entscheiden
- zunächst ausschließlich Paper Trading, eigene Risiko-/Produktlogik und deutliche Totalverlustwarnung
- moderate Hebel, Finanzierungskosten, Knock-out-Schwellen, täglichen Reset gehebelter ETFs sowie Liquiditäts-/Gap-Risiken produktspezifisch bewerten
- eine mögliche Live-Freigabe des normalen ungehebelten Bots gilt niemals automatisch für Hebelprodukte; ein Hebelmodus benötigt ein eigenes, noch strengeres Echtgeld-Gate und bleibt bis dahin ohne Broker-Anbindung und automatische Orderausführung

### PRIO B: Trading-Modus

Die aktuelle Finder-Hauptansicht zeigt ausschließlich automatisch berechnete Vorschläge und handelt nicht. Die ältere lokale manuelle Trade-Lebenszykluslogik bleibt zur Datenkompatibilität im Code erhalten, wird im vereinfachten Finder aber nicht als zusätzliche Eingabestrecke angezeigt. Der sichere Kern von Phase F stellt den kompakten Ablauf `Trade getätigt` und `Meine aktiven Trades` bereit: Er erscheint erst nach einer ausdrücklichen Nutzeraktion an einem unveränderbar gespeicherten objektiven Signal, verändert die Kapital-als-einzige-Normaleingabe-Regel des Scanners nicht und erzeugt niemals eine Brokerorder.

Umgesetzt am 2026-08-02:

- Einzige sichtbare Eingabe ist das Tradingkapital; alle übrigen Risikogrenzen werden zentral und konservativ festgelegt.
- Risikobasierte Stückzahl aus geplantem Einstieg und automatisch berechnetem Stop; ohne Kapital keine erfundene Stückzahl.
- Geplanter Verlust, investierter Betrag und mögliche Gewinne an Ziel 1/2 werden automatisch berechnet, ohne einen garantierten Maximalverlust zu behaupten.
- Keine Eingabe für Risiko, Stop, CRV, Volatilität, Positionsgewichtung, manuelles Eröffnen oder Ausstieg in der Finder-Hauptansicht.

Sicherer Kern von Phase F umgesetzt; fachlich breitere Begleitung und reale Nutzung bleiben zu validieren:

- Der Nutzer bestätigt ausschließlich eine bereits selbst beim Broker ausgeführte Handlung; die App eröffnet, ändert oder schließt keine Order.
- Tatsächlicher Einstieg, Stückzahl, Zeitpunkt, Abweichungen, Stop-Nachzug, Teilverkauf und Abschluss werden als zusätzliche Nutzerereignisse gespeichert und niemals in den objektiven Paper-Verlauf zurückgeschrieben.
- Aktive Nutzertrades erhalten nur regelbasierte Hinweise aus dem vorab gespeicherten Plan. Der Nutzer bestätigt jede tatsächliche Änderung selbst.

### PRIO B: Trade Journal

Jeder freigegebene Scanner-Trade wird automatisch als Paper-Trade dokumentiert, aber niemals automatisch ausgeführt.
Status: Paper-Lebenszyklus am 2026-08-02 erweitert. Neue Signale werden lokal dedupliziert, nicht eröffnete abgelaufene Setups werden markiert statt gelöscht, und tatsächliche manuelle Einstiegs-/Ausstiegsdaten können ergänzt werden. Ältere Feldnamen bleiben defensiv normalisiert.

Statusgrenze: Die ältere kompatible JSON-Journal-Basis bleibt erhalten. Neue objektive Forward-Scans, Signalsnapshots und Ereignisse werden getrennt append-only in SQLite gespeichert; persönliche Nutzertrades besitzen wiederum eine eigene append-only Datenbank. Echte Forward-Fälle, historische Simulationen, objektive Paper-Ergebnisse und persönliche Resultate werden nicht vermischt. Die technische Intraday-Auswertung, Archivstatistik sowie Zeit-/Text-/Ergebnis-/Versions-/Quellen-/Nutzertrade-Filter sind vorhanden; historischer Exit-FX-Nachweis und eine belastbare reale Fallbasis bleiben offen. Fehlende historische Felder werden als unbekannt markiert und nicht erfunden.

Auswertung, soweit genügend abgeschlossene Fälle vorliegen:

- Trefferquote, durchschnittlicher Gewinn und Verlust, Expected Value und Profitfaktor.
- Maximaler Drawdown, Ziel-/Stop-Treffer und abgelaufene Setups.
- Ergebnisse nach Setup und Marktphase sowie Opportunitätskosten.
- Keine automatische Änderung von Scores oder Gewichten.

Datei:

- `trade_history.json`

Speichern:

- Datum
- Asset
- Richtung
- Einstiegskurs
- Ziel
- Stop
- Chance
- Confidence
- Asset-Typ
- Marktphase
- verwendete Scores
- Begründung

### PRIO B: Performance Tracking

Der vorhandene Review-Pfad misst ältere Setups auf festen Wochen-/Monatshorizonten. Er ist nicht mit der geplanten exakten Paper-Trade-Auswertung zu verwechseln. Phase D muss zusätzlich ab Signalzeitpunkt Aktivierung, realistischen Einstieg, Gap, Maximalpreis, Stop-/Zielreihenfolge, Kosten, Slippage, Ablauf und Datenqualität mit geeigneten Intraday-Daten prüfen.

Für jeden vorgeschlagenen Trade prüfen:

- nach 1 Woche
- nach 1 Monat
- nach 3 Monaten
- nach 6 Monaten
- nach 12 Monaten

Bewerten:

- Treffer oder Fehlschlag
- maximale positive Entwicklung
- maximale negative Entwicklung
- Ziel erreicht?
- Stop erreicht?
- beste Alternative?
- Status: Basis umgesetzt am 2026-06-15. Gespeicherte Trading-Setups werden nach 1 Woche, 1 Monat und 3 Monaten mit echten Kursdaten ausgewertet; Ziel/Stop, Rendite sowie maximale positive und negative Entwicklung werden gespeichert.
- Status: Erweiterte Zeiträume umgesetzt am 2026-07-20. Trade-Journal, Forward-Tests, Prognosen und Entscheidungen unterstützen 6- und 12-Monats-Reviews kompatibel zu alten Historien.
- Status: Beste Alternative umgesetzt am 2026-08-01. Trade-Journal-Auswertungen speichern zusätzlich gewählte Aktion, beste Alternative und Opportunitätskosten.
- Status: Historienkontext umgesetzt am 2026-08-01. Trade-Journal-Auswertungen normalisieren ältere Setup-Felder vor der Auswertung und speichern ähnliche Setups, Treffer, Trefferquote, Historienstatus und Historienhinweis im Review-Ergebnis.

### PRIO B: Erweitertes Decision Tracking

Nicht nur prüfen: `Hatte der Bot recht?`

Sondern zusätzlich prüfen: `War dies die beste Entscheidung?`

Vergleichen:

- Long
- Short
- Halten
- Beobachten

Berechnen:

- Rendite der Empfehlung
- Rendite der besten Alternative
- Opportunitätskosten
- Status: Basis umgesetzt am 2026-06-15. Gespeicherte Nutzerentscheidungen werden gegen Long, Short und Halten/Beobachten ausgewertet; beste Alternative und Opportunitätskosten werden gespeichert.

### PRIO B: Confidence-System

Status: ähnliche historische Setups und Trefferquoten aus `trade_history.json`, `forward_tests.json` und `prediction_history.json` umgesetzt am 2026-07-01. Unter 20 ähnlichen Fällen zeigt die App `Datenbasis zu klein`; Gewichtungen werden nicht automatisch geändert.

Status: konsolidiert am 2026-08-01; ähnliche Setup-Auswertungen zeigen zusätzlich häufigste Szenario-Lesart, Fehlursache, Decision-Alignment und Historienstatus aus Review-Daten, sofern vorhanden. Diese Felder dienen nur als Transparenzkontext und verändern keine Scores automatisch.

Zusätzlich zur Chance immer einen Confidence Score anzeigen.

Beispiel:

- Chance: 72 %
- Confidence: 9/10
- Ähnliche Setups: 183
- Historische Trefferquote: 71 %

Der Confidence Score soll berücksichtigen:

- Datenqualität
- Anzahl ähnlicher historischer Fälle
- Trefferquote ähnlicher Setups
- Stabilität der Signale
- Klarheit der Marktphase
- Liquidität und Volatilität
- Status: Basis umgesetzt am 2026-06-15. Die App zählt ähnliche lokale Historienfälle nach Asset-Typ oder Marktphase und zeigt Trefferquote erst ab ausreichender Datenbasis.

### PRIO B: Signalanalyse

Auswerten, welche Signale historisch nützlich waren:

- RSI
- MACD
- Marktphase
- Volatilität
- Trend
- News
- Makro
- Asset-Typ
- CRV
- Opportunity Score
- Confidence Score
  - Status: Basis umgesetzt am 2026-06-15: Signalanalyse zählt ausgewertete Forward-Tests und Prognosen und zeigt Trefferquoten nach Asset-Typ erst ab ausreichender Datenbasis.
  - Status: Signal-Snapshots umgesetzt am 2026-07-19: neue Historieneinträge speichern RSI-, MACD-, Volatilitäts-, News-, Makro- und CRV-Buckets; fehlende alte Signalwerte bleiben `Daten nicht verfügbar`.
  - Status: Segment-Auswertung umgesetzt am 2026-07-19: Trefferquote, Durchschnittsrendite und Fallzahl werden nach Asset-Typ, Marktphase und Zeithorizont gruppiert; unter 20 Fällen bleibt die Aussage `Datenbasis zu klein`.

### PRIO B: Kalibrierungsvorschläge

Der Bot darf Vorschläge machen, aber Gewichtungen in Version 1 nicht automatisch ändern.

- Backtest-Historie in Kalibrierungsvorschläge einbeziehen. Status: umgesetzt am 2026-08-01; schwache gespeicherte Backtest-Gruppen mit ausreichender Datenbasis werden als `Backtest-Signal` in manuellen Kalibrierungshinweisen angezeigt.

Beispiele:

- RSI bei Krypto stärker gewichten
- Marktphase stärker gewichten
- News schwächer gewichten

Für jeden Vorschlag anzeigen:

- Datenbasis
- Anzahl Fälle
- Trefferquote
- Begründung

Mindestdatenmenge:

- Unter 20 Fällen: `Datenbasis zu klein`
- 20-50 Fälle: vorsichtige Hinweise
- Über 50 Fälle: Kalibrierungsvorschläge erlaubt
  - Status: Basis umgesetzt am 2026-07-19: ähnliche Setups zeigen Signal-Buckets, Fallzahl, Trefferquote, Durchschnittsrendite und ob nur gezählt, vorsichtig hingewiesen oder ein manueller Vorschlag erlaubt ist.

Langfristig soll der Bot erkennen:

- welche Signale funktionieren
- welche Signale nicht funktionieren
- bei welchen Asset-Typen er besonders gut ist
- bei welchen Asset-Typen er schwächer ist
- wann er zu optimistisch ist
- wann er zu vorsichtig ist

Ziel ist nicht eine Blackbox-KI. Ziel ist ein transparentes, nachvollziehbares System, das seine eigene historische Leistung misst und daraus begründete Verbesserungen ableitet.

## Verbindliche Umsetzungsphasen

Die Phasen beschreiben Abhängigkeiten und Zielreihenfolge. Innerhalb einer Phase entscheidet der tatsächliche Nutzen. Stabilitäts- oder Datenqualitätsprobleme dürfen jederzeit vorgezogen werden.

### Phase 1 – Stabilität und Datenqualität

Status: laufende Grundanforderung; lokale Tests, Sicherheitscheck, Startprüfungen und ein verständlicher Betriebsstatus sind vorhanden. Der reale Lauf vom 2026-08-01 blieb nach dem Start bei 0 von 325 Assets stehen und wird korrekt als veraltet erkannt. Am 2026-08-02 verarbeitete der nächste Lauf alle 325 Positionen in rund 23 Minuten, speicherte 322 Prognosen und isolierte drei Datenfehler. Der zweite vollständige planmäßige Lauf vom 2026-08-03 verarbeitete erneut alle 325 Positionen, speicherte 323 Prognosen, isolierte nur noch zwei Datenfehler, benötigte 887,17 Sekunden und endete bei null Rate-Limits mit Wrapper-Exit 0 sowie Datenbankstatus `ok`. Die beiden dauerhaft nicht mehr auflösbaren Yahoo-Symbole wurden danach für künftige Läufe belegt von `BK` auf `BNY` und von `ROG.SW` auf `ROP.SW` korrigiert. Der dritte vollständige planmäßige Lauf vom 2026-08-04 bestätigte diese Korrektur: alle 325 Assets einschließlich `BNY` und `ROP.SW` wurden erfolgreich gespeichert, ohne Fehler oder Rate-Limits, in 803,26 Sekunden bei Datenbankstatus und Integrität `ok` sowie Wrapper-Exit 0. Startvorprüfung, Asset-Fortschritt und Prozessgrenze sind protokolliert; eine betriebssystemweite Sperre verhindert parallele Runner. Mehrwöchiger Dauerbetrieb, Wiederanlauf nach echter Unterbrechung und ein erweitertes wiederkehrendes Wochenuniversum bleiben zu validieren.

- bestehende Fehler beheben
- Datenqualität und ehrliche Fehlermeldungen sichern
- Tests, Streamlit-Start, Historien und Datenbankintegrität stabil halten
- keine Nutzerdaten oder privaten Historien verlieren
- bestehende Bewertungslogik nachvollziehbar und versionierbar halten
- Hintergrundbetrieb, Wiederanlauf und Ausfallwarnungen praktisch validieren

### Phase 2 – Gemeinsames Designsystem und Navigation

Status: Die Navigation besitzt jetzt die drei geplanten Hauptbereiche. Der bisherige Scanner ist sichtbar als `Swing Trade Finder` benannt, alte Session-Zustände werden kompatibel übernommen, und `Investment Opportunities` zeigt einen sicheren Leerzustand ohne erfundene Daten. Erste zentrale Oberflächen-Tokens sind umgesetzt. Die vollständige app-weite optische Vereinheitlichung sowie die sichtbare Desktop-/390-Pixel-Prüfung bleiben offen; die funktionalen Navigationspfade sind mit Streamlit-AppTest geprüft.

- die drei Hauptbereiche `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder` klar im Hauptmenü anlegen
- den heutigen `Opportunity Scanner` ohne Verlust seiner Historien in `Swing Trade Finder` überführen
- gemeinsame Regeln für Abstände, Typografie, Farben und Oberflächen definieren
- responsive Komponenten und vollständigen Textumbruch absichern
- Karten, Statusflächen, Tabs, Tabellen und Expander vereinheitlichen
- Asset-Analyse, Investment Opportunities, Swing Trade Finder, Prognosequalität und Einstellungen optisch zusammenführen
- Einstellungen und erweiterte Ansichten konsistent ordnen
- native, stabile Streamlit-Komponenten bevorzugen

Abhängigkeit: Phase 1 muss stabil bleiben. Session-State, Rücknavigation und der kompatible Erhalt des bisherigen Scanner-Pfads sind für die neue Navigation umgesetzt. Weitere Designänderungen benötigen weiterhin visuelle Desktop- und Mobiltests.

### Phase 3 – Asset-Analyse

Status: Die künftige Einstiegsanalyse ist mit dreistufiger Informationshierarchie, Preisattraktivität, konkreten Kaufzonen, relativen Tranchen und Empfehlungssynthese weitgehend umgesetzt. Die intelligente Einstiegs-Watchlist ist seit 2026-08-17 als priorisierte Asset-Analyse-Erweiterung vollständig fachlich spezifiziert, aber noch nicht implementiert. Für die Long-Term-Analyse bestehen jetzt ein isoliert getesteter Quellenvertrag mit strikter Freigabe erst bei vollständiger Pflichtabdeckung, sichere lokale Caches, eine getrennte versionierte Bewertungs-/Szenariorechnung und eine inaktive SEC-Teilkollektion mit Filing-Discovery plus begrenzter XBRL-Finanzfakten-Evidenz. Eine explizite Auswahl zwischen Einstiegs- und Long-Term-Analyse, batchfähige sichere Quellenbeschaffung, unabhängige Gegenquellen, vollständige quellengebundene Faktorableitung sowie Ergebnistext und Langfrist-Empfehlung fehlen.

- Einstiegsanalyse als eigenen Modus stabilisieren und ihren kompakten konkreten Plan erhalten
- intelligente Einstiegs-Watchlist aus Asset, Budget und kritisch zu prüfender Nutzerthese aufbauen; Budget darf nur die Tranchierung beeinflussen
- tägliche günstige Technikprüfung, ereignisgesteuerte beziehungsweise regelmäßige vollständige Neubewertung und versionierte Ablösung unrealistischer alter Einstiegspläne umsetzen
- kompakte Fünf-Fragen-Karte mit Details erst nach Klick sowie deterministische Zahlenlogik und streng beleggebundene qualitative KI-Auswertung entwickeln
- Long-Term-Analyse mit eigener Leitfrage, Gewichtung, Ergebnisstruktur und Drei- bis Sieben-Jahres-Szenarien aufbauen
- verständliche Geschäftsmodell- und Investmentthesen aus nachweisbaren Quellen ermöglichen
- offizielle Unternehmens- und belastbare Branchendaten vorbereiten; Yahoo Finance nicht als alleinige Quelle für Strategie und Wettbewerb verwenden
- Langfristigkeit, Preis, Timing und optionalen Depot-Effekt getrennt halten
- technische Analyse in der Long-Term-Analyse ausschließlich für den Einstieg verwenden
- reale Ergebnisse beider Analysearten getrennt sammeln und erst danach kontrolliert kalibrieren

Abhängigkeit: Phase 2 liefert Navigation und gemeinsame Ergebnisbausteine. Neue Quellen benötigen klare Herkunft, Aktualität, Fehlerbehandlung und Caching, bevor daraus Aussagen entstehen.

### Phase 4 – Investment Opportunities

Status: als eigener Produktbereich geplant und noch nicht umgesetzt. Das vorhandene 325-Asset-Prognoseuniversum ist eine mögliche technische Grundlage, aber noch kein geprüftes Opportunity-Universum und kein fertiger Feed.

- die Modi `Aktuell attraktiv` und `Zukunftschancen 3+ Jahre` mit getrennten, zentral konfigurierten Scores entwickeln
- Mindestqualität, Datenabdeckung und Kein-Kandidat-Zustand verbindlich umsetzen
- ein größeres nachvollziehbares Marktuniversum mit kontrollierter Last, Regionen-, Branchen- und Größenabdeckung definieren
- ungefähr zehn hochwertige Kandidaten kompakt anzeigen, ohne schwache Ideen nachzuladen
- Feed-Aktionen, lokale Ausblendungen, Wiederanzeige-Regeln und rückgängig machbare Einstellungen umsetzen
- hochwertige Feed-Kandidaten mit übernommenem Kontext an die unter `Asset-Analyse` geführte intelligente Einstiegs-Watchlist übergeben
- je Modus automatisch die richtige Analyseart mit übernommenem Kontext öffnen
- Vielfalt erst nach Mindestqualität anwenden und große US-Technologiewerte nicht künstlich bevorzugen

Abhängigkeit: Phasen 1 bis 3. Der Feed benötigt stabile Asset-Identität, eigene Scores, ausreichende Fundamentaldaten, kontrollierbare Datenquellen, lokale Präferenzspeicherung und belastbare Übergaben an beide Analysearten.

### Phase 5 – Swing Trade Finder

Status: Die sichere Scanner-Basis und die Kerne der Phasen A bis F sind umgesetzt. Das intern gepflegte Universum enthält seit 2026-08-11 2.520 aktive Assets mit stabiler interner ID. Jeder Grobfiltertreffer wird ohne feste Top-N-Grenze tief geprüft; ATR-normalisierte Setupzonen, vollständige Grob-/Finalfilterzählung, ein neutralisierter ETF-/Aktien-Funnel und vier reale Regionalnachweise sind vorhanden. Offen bleiben gereifte Ergebnisse der echten bisherigen und der neutralisierten v3-Forward-Signale, reale FX-Belege aus abgeschlossenen Trades, belastbare News-/Ereignis-/Branchenquellen und eine mehrwöchige bis mehrmonatige Forward-Historie.

Verbindliche Swing-Unterreihenfolge:

1. **Phase A – Stabilität und Orderplan:** Einstiegsmethoden, Ordertypen, Marken-/Währungskonsistenz, Stop-Vertrag, Karten und Risikohinweise vollständig absichern.
2. **Phase B – Universum und Datenqualität:** 2.520-Asset-Ausbau und erster vollständiger Echtlauf sind erreicht; Metadaten und scanübergreifende Fehlerpflege weiter vervollständigen.
3. **Phase C – Hintergrundbetrieb:** regionale Aktien-/ETF-Läufe und getrennte Kryptowährungsläufe ohne geöffnete App zuverlässig betreiben.
4. **Phase D – ehrlicher Forward-Test:** echte Signale unveränderbar speichern und realistisch ab Signalzeitpunkt auswerten; historische Simulation strikt trennen.
5. **Phase E – Archiv und Messbarkeit:** vollständige Signal-/Trade-Historie, Datenqualität, Ergebnis in R und segmentierte Statistiken bereitstellen.
6. **Phase F – Nutzertrade und Begleitung:** sicherer Kern mit `Trade getätigt`, getrennten persönlichen Trades und regelbasierten aktiven Hinweisen ohne Orderausführung umgesetzt; reale Nutzung und zusätzliche Struktur-/Volumen-/Ereignisregeln weiter validieren.
7. **Phase G – Validierung und spätere Erweiterungen:** erst nach belastbarer echter Historie Regeln kontrolliert verbessern und weitere Setups prüfen.
8. **Strategie-Freeze:** technische Infrastruktur und getrennte Baseline-/Challenger-Freezes umgesetzt; keine Performancefreigabe. Jede fachliche Änderung erzeugt eine neue Version und beginnt erneut im erforderlichen Validierungspfad.
9. **Autonomer Paper-Bot:** brokerlosen vollständigen Handelszyklus ohne Nutzereingriff technisch umgesetzt; nun über ausreichend viele aktuelle Marktphasen betreiben und auditieren.
10. **Shadow-Live:** brokerlose Orderentwürfe und strikt echte Beobachtungsfelder umgesetzt; belastbare aktuelle Bid-/Ask-/Ausführungsdaten weiter sammeln, aber keine Order senden.
11. **Echtgeld-Gate:** historische, echte Forward-/Paper-, autonome Paper-Bot- und Shadow-Live-Evidenz gemeinsam prüfen; keine automatische Freigabe.
12. **Begrenzter Live-Bot:** nur nach ausdrücklicher Freigabe und mit separatem fest begrenztem Bot-Tradingkapital entwickeln.
13. **Kontrollierte Skalierung:** reales Kapital nur nach erneuter dokumentierter Prüfung stufenweise erhöhen.

Aktuelle Priorität: Die laufenden historischen Swing-Walk-Forward-Tests, die bestehende echte Forward-/Paper-Validierung sowie die nun technisch vorhandenen autonomen Paper- und Shadow-Live-Pfade werden weitergeführt. Strategie-Freeze, gemeinsamer Risk-Pfad, autonomer Paper-Bot und brokerlose Shadow-Grundlage sind umgesetzt, aber noch nicht durch ausreichend gereifte aktuelle Evidenz freigegeben. Echtgeld-Gate, Brokerintegration und Live-Bot bleiben Zukunftsarbeit und gesperrt.

- klare fachliche und visuelle Trennung von `Investment Opportunities` beibehalten
- bestehende Kein-Trade-Regel und absolute Mindestfilter beibehalten
- keine sichtbare Kategorie `Beobachten` und keinen erzwungenen relativ besten Trade wieder einführen
- reale Datenabrufquote, Laufzeit und Yahoo-Schonung des gebündelten 2.520-Asset-Scans weiter messen; erster großer Bereichsnachweis 2.350/2.352 geladen, null Rate-Limits
- Paper-Trades und spätere Ergebnisse weiter messen
- später erst Bodenbildungs-/Erholungssetup prüfen
- Short- und Absicherungssetups erst nach belastbarer Long-Validierung untersuchen
- keine Hebelprodukte und kein Scalping in Version 1
- normaler Nutzereingang bleibt ausschließlich `Verfügbares Tradingkapital in Euro`; alle weiteren Systemparameter sind zentral und nur lesbar
- jede Freigabe muss einen konkreten, intern konsistenten Orderplan liefern; bis dieser Vertrag vollständig umgesetzt ist, darf der bisherige Vorschlag nicht als vollständige Broker-Anweisung dargestellt werden
- echter Forward-Test, historische Scanner-Simulation, objektiver Paper-Trade und persönlicher Nutzertrade bleiben getrennte Datenarten
- vollständige Prüfung aller möglicherweise relevanten Kandidaten beibehalten und Assetklassen-Bias über rechnerisch zerlegte Grob-/Finalfilter sowie ausschließlich echte, versionsgleiche Forward-Ergebnisse messen; keine Klassenquote oder automatische Gewichtung

Noch offen aus dem Automatisierungsauftrag (Stand 2026-08-03):

- Den vollständigen realen 2.520-Asset-Betrieb über weitere Wochen wiederholt dokumentieren. Erster Nachweis: alle vier Bereiche Status `ok`, insgesamt 2.517/2.520 geladen, drei sichtbare Tickerfehler, null Rate-Limits; Amerika/Global benötigte 327,36 Sekunden.
- Ungültige beziehungsweise dauerhaft nicht auflösbare reale Ticker zusätzlich in einem persistenten technischen Scanprotokoll festhalten. Aktuell bleiben sie im jeweiligen Scanergebnis und unter den erweiterten Ablehnungen sichtbar, werden aber noch nicht scanübergreifend protokolliert; sie dürfen weiterhin niemals still aus dem versionierten Universum gelöscht werden.
- Den nach der vollständigen Pytest-/Kompilierungsprüfung abgebrochenen Abschlussblock erneut vollständig ausführen: Repository-Sicherheitscheck, Offline-Smoke-Test und ausdrücklich dokumentierter lokaler Streamlit-Start. Abgebrochene oder nur teilweise gelaufene Prüfungen nicht als bestanden werten.
- Den vereinfachten Finder sichtbar im lokalen Browser prüfen: einmaliger Risikohinweis und persistierte Fortsetzung, ausschließlich eine Kapital-Eingabe, kein Ticker-/Watchlistfeld, keine Kategorie `Beobachten`, keine Hebelsteuerung, nur lesbare interne Einstellungen, vollständige Scan-Zähler, Kein-Trade-Zustand und kompakte Trade-Karten ohne abgeschnittene Pflichttexte.
- Die sichtbare Prüfung mindestens in einer breiten Desktopansicht und bei ungefähr 390 Pixel Breite durchführen. Horizontalen Überlauf, gequetschte Kennzahlen, unerwartete Eingabefelder und Browserfehler dokumentieren und gegebenenfalls beheben.
- Nach diesen Prüfungen `PROJECT_STATUS.md` mit realer Scan-Abdeckung, finalen Sicherheits-/Smoke-/Start-/Browserergebnissen und bekannten externen Yahoo-Einschränkungen nachziehen; anschließend `git diff --check` und den finalen Git-Status prüfen. Commit und Push bleiben ausdrücklich außerhalb dieses Auftrags.

Abhängigkeit: stabiler Betrieb aus Phase 1. Die bereits vorhandene Swing-Kernfunktion darf fachlich weiterentwickelt werden, ohne zuerst das allgemeine Designsystem oder die gesamte Navigation aus Phase 2 fertigzustellen. Neue Setup-Arten hängen weiterhin von ausreichend vielen abgeschlossenen und sauber ausgewerteten Paper-Trades ab.

### Phase 6 – Automatische Prognosequalität

Status: Hintergrundprozess, SQLite-Speicherung, automatische spätere Auswertung und Qualitätsansicht sind technisch vorhanden. Sieben dokumentierte Laufzeilen bis 2026-08-08 enthalten 1.945 Einstiegsanalysen und 9.725 Prognosezeiträume; die produktive Datenbank ist integer. Die ersten 322 Ein-Wochen-Ergebnisse sind am 2026-08-09 fällig und werden im planmäßigen Lauf um 22:30 Uhr erstmals real geprüft. Für diesen Massenfall verwendet der Runner gebündelte Kursabrufe mit gemeinsamem historischem FX-Cache. Datenbankschema 9 ergänzt L0-Messvertrag, Snapshot-Fingerabdruck, Wochenkohorten-Metadaten, tatsächlichen Bewertungstag, beste/schlechteste Bewegung, Referenzen für immer steigend, keine Änderung, 20-Tage-Trend und einen assettyp-/regionsabhängigen Marktbenchmark sowie eine versionierte unkalibrierte Rohwahrscheinlichkeit je Prognosezeitraum. Vor jedem Tageslauf werden sämtliche neuen Messverträge vollständig verifiziert; beschädigte Zeilen stoppen den Prozess vor Auswertung und Marktabruf. Neue Wochenberichte halten Soll-/Ist-Kohorten, Nachholen, Fehler, Rate-Limits, Laufzeit, Datenbankwachstum und Auswertungsstand fest. Die Qualitätsansicht zeigt zusätzlich Ergebnisabdeckung, Rendite, Drawdown, Überschussrendite, Wilson-Intervall, Precision, Recall, Balanced Accuracy, Brier Score, Log Loss, Kalibrierungsfehler und Segmente nach Region, Marktphase, Datenqualität und Logikversion. Die 1.945 älteren Datensätze werden nicht rückwirkend mit angeblichen Point-in-Time-Feldern ergänzt. Ab 2026-08-10 startet das versionierte 1.726-Asset-Wochenuniversum mit festem 325er Montagskern und vier deterministischen Erweiterungskohorten. Der verpasste Termin vom 2026-08-06 bleibt eine sichtbare Lücke; Recovery-Daten sind getrennt. Mehrwöchiger Realbetrieb, gereifte Wahrscheinlichkeitsfälle, eigene Horizontmodelle, echte Kalibrierung sowie Long-Term- und Swing-Prognosemodelle fehlen weiterhin.

- täglichen Hintergrundbetrieb ohne geöffnete Streamlit-App zuverlässig betreiben
- skalierbare Speicherung und automatische Fälligkeitsauswertung erhalten
- Gesamt-Trefferquote kompakt im Hauptmenü und Details nur in erweiterten Einblicken zeigen
- Zustände klar unterscheiden: keine Prognosen, offen, noch nicht fällig, ausgewertet, Hintergrundbetrieb nicht aktiv und Auswertung wegen fehlender Daten nicht möglich
- unklare technische Legacy-Bezeichnungen in der normalen Oberfläche vermeiden; verständliche Bezeichnung ist `Prognosequalität`
- Prognosen und Richtungstrefferquote getrennt nach Analyseart speichern, filtern und zusammenfassen. Status: technische Modelltrennung für Einstiegsanalyse umgesetzt am 2026-08-02; Long-Term- und Swing-Prognosen sowie deren passende Rendite-, Drawdown- und Opportunitätskosten-Maße bleiben offen.
- unterschiedliche Horizonte und Benchmarks je Modelltyp verwenden; Ergebnisse nicht zu einer irreführenden Gesamtzahl vermischen
- den 325-Referenzkern und das umgesetzte 1.726-Asset-Universum real validieren; anschließend das reguläre Prognoseuniversum kontrolliert Richtung 2.500 bis 3.500 Assets und später ein günstiges Discovery-/Monitoring-Universum Richtung 5.000 bis 10.000 beobachtbare Assets skalieren
- Analysefrequenz und Horizontstart entkoppeln: 1W wöchentlich, 1M zweiwöchentlich, 3M monatlich, 6M vierteljährlich und 12M halbjährlich; 6M/12M nur für nachvollziehbar `long_horizon_eligible` Assets
- Unternehmens-/Listing-Identität in neuen Snapshots trennen und Mehrfachlistings in Long-Term-Statistiken nicht als unabhängige Unternehmen doppelt zählen
- alte Prognosen unabhängig von neuen Wochenprognosen über alle fünf Horizonte weiterführen und niemals überschreiben
- Point-in-Time-Merkmale, Benchmark und Ergebnisdefinitionen für ein späteres echtes Lernsystem vollständig und versionssicher speichern

Abhängigkeit: verlässlicher Betrieb aus Phase 1, stabile versionierte Einstiegsanalyse-Ausgaben und ein vollständiger Point-in-Time-Messvertrag; keine rückwirkend erfundenen Prognosen. Der allgemeine Wochen-Scan läuft als zweiter Prioritätsblock unabhängig im Hintergrund weiter. Swing-spezifische Datensammlung, Walk-Forward-, Forward-, Paper- und spätere Shadow-Evidenz gehören dagegen unmittelbar zur höchsten Bot-Priorität. Spätere Long-Term- beziehungsweise Swing-Prognosemodelle benötigen jeweils die ausgereifte Logik ihres eigenen Bereichs.

### Phase 7 – Validierung und kontrollierte Verbesserung

Status: Mess- und Lernbasis vorhanden; ein vollständiger realer Erhebungslauf ist belegt. Für belastbare fachliche Änderungen fehlen noch ein wiederkehrendes breites Wochenuniversum, ausgereifte echte Fälle, Point-in-Time-Trainingsdaten, Vergleichsmodelle, zeitliche Walk-Forward-Prüfung und ein kontrollierter Shadow-/Freigabeprozess.

- Long-Term-Empfehlungen, Einstiegsempfehlungen, Opportunity-Scores und Swing-Setups getrennt über ausreichend viele Fälle messen
- Rendite, Trefferquote, Profitfaktor, Drawdown und Opportunitätskosten vergleichen
- Ergebnisse nach Modell, Asset-Typ, Setup, Marktphase, Zeitraum und Datenqualität trennen
- Ergebnisse mit passenden Vergleichsindizes und einfachen transparenten Strategien vergleichen
- unterschiedliche Marktphasen in Entwicklung und Bewertung berücksichtigen
- keine heimliche automatische Änderung von Gewichten oder Produktionsregeln
- Verbesserungen nur versioniert, transparent, testbar und mit Rückfallmöglichkeit übernehmen
- 20/50 Fälle weiterhin nur als frühe Hinweisgrenzen behandeln; Trainings- und Freigabereife separat und deutlich strenger nach Unsicherheit, Zeitabdeckung und Segmentbreite bestimmen
- Kandidaten ausschließlich zeitbasiert und ohne Zukunftswissen trainieren, Wahrscheinlichkeiten auf getrennten Daten kalibrieren und gegen einfache Referenzen prüfen
- aktuelle Regelbasis als Champion behalten; lernende Challenger zunächst ausschließlich im Shadow-Modus bewerten
- eine sichtbare Enthaltung `keine belastbare Empfehlung` als reguläres und messbares Ergebnis zulassen
- erst nach dokumentiertem Vorteil auf mehreren ungesehenen Zeitfenstern, manueller Freigabe, Canary-Test und vorbereitetem Rollback eine neue Produktionsversion aktivieren

Abhängigkeit: ausreichend viele echte, fällige und nach Modellversion eindeutig zuordenbare Fälle aus den Phasen 3 bis 6.

## Prioritäten

Verbindliche Hauptreihenfolge seit 2026-08-17:

1. **SwingTrading-Bot fertigstellen und nach Evidenz verbessern.** Die gesamte verbindliche Stufenkette von laufender Swing-Forschung und Datensammlung über Strategie-Freeze, autonomen Paper-Bot, Shadow-Live und Echtgeld-Gate bis zum begrenzten Live-Bot und kontrollierter Skalierung ist die höchste Projektpriorität. Bearbeitet wird stets nur die nächste zulässige Stufe; Broker- und Echtgeldarbeit bleibt bis zu ihrem Gate gesperrt.
2. **Effiziente Prognosedatensammlung.** Horizonte werden unabhängig gestartet; Auswertung, Point-in-Time-Schutz, Wochenabdeckung und bestehende Prognosen bleiben erhalten.
3. **Andere Produktbereiche erst danach.** Allgemeines Designsystem, Navigationsumbau, Investment-Opportunity-Feed und weitere Komfortfunktionen dürfen die ersten beiden Prioritätsblöcke nicht verdrängen.

Diese Hauptreihenfolge überschreibt für die Auswahl der nächsten Arbeit ältere lokale Überschriften wie `PRIO A`, `PRIO B` oder frühere Phasennummern. Solche Bezeichnungen bleiben teilweise als fachliche Gruppierung erhalten, bestimmen aber nicht mehr, was als Nächstes bearbeitet wird.

Ausnahme: Kritische Fehler bei Stabilität, Datenschutz, Datenintegrität oder falschen Ergebnissen werden weiterhin sofort behoben. Diese Ausnahme darf nicht genutzt werden, um reine Komfortarbeit vorzuziehen.

### Prioritätsblock 2 – allgemeiner wöchentlicher Markt-Scan, Forward-Test und präzisere Vorhersagen

Höchste offene Aufgabe innerhalb dieses zweiten Blocks:

1. Den erfolgreichen bedienungsfreien Prognosebetrieb in eine wiederkehrende, statistisch saubere Wochenstichprobe überführen und dabei den vollständigen Point-in-Time-Messvertrag für ein späteres echtes Lernsystem schaffen.

Status der Vorbereitung:

- Hintergrund-Runner, SQLite-Speicherung, Auswertung fälliger Prognosen, Wiederholungslogik, Fortsetzung unterbrochener Läufe, Betriebsprotokoll und Windows-Installationsskript sind vorhanden.
- Das Betriebsprotokoll hält Startvorprüfung, Analysebeginn je Ticker, Position und Versuch fest. Auch Fehler beim Laden eines ungültigen oder leeren Universums werden vor Prozessende protokolliert. Der Windows-Wrapper hält zusätzlich Start, Ende und Rückgabecode des Python-Prozesses in einem getrennten lokalen Log fest.
- Eine plattformübergreifende exklusive Prozesssperre schützt zusätzlich zur Task-Scheduler-Regel `IgnoreNew` gegen manuelle oder anderweitig gestartete parallele Runner. Die Sperre wird bei Prozessende automatisch vom Betriebssystem freigegeben.
- Der Windows-Prozess bleibt täglich um 22:30 Uhr vorgesehen. Er prüft jeden Tag zuerst fällige Ergebnisse; neue Snapshots entstehen ab 2026-08-10 nur für die jeweils fällige Wochenkohorte.
- Die Windows-Aufgabe ist registriert und bereit. Aufwecken, verspäteter Start, drei begrenzte Neustartversuche und Schutz vor parallelen Doppelläufen sind konfiguriert.
- Der erste vollständige reale Lauf am 2026-08-02 ist betrieblich validiert: 325 verarbeitet, 322 erfolgreich, drei isolierte Datenfehler, keine Rate-Limit-Fehler, Datenbankintegrität `ok` und Wrapper-Rückgabecode 0.
- Bis zum 2026-08-08 wurden in sechs erfolgreichen beziehungsweise teilweise erfolgreichen Real-Läufen 1.945 Prognosen und 9.725 Zeiträume gespeichert. Die ersten 322 Ein-Wochen-Auswertungen sind am 2026-08-09 fällig; vor dem planmäßigen 22:30-Lauf liegen noch keine ausgewerteten Ergebnisse vor.
- Ein getrenntes versioniertes Wochenuniversum mit 1.726 eindeutigen aktiven Assets ist umgesetzt. Der 325er Referenzkern läuft montags; 1.401 Erweiterungsassets sind deterministisch auf Dienstag bis Freitag verteilt (362/354/340/345). Die Zuordnung besitzt einen SHA-256-Fingerabdruck.
- Verpasste Kohorten werden innerhalb derselben Kalenderwoche am nächsten verfügbaren Termin mit dem tatsächlichen neuen Beobachtungszeitpunkt nachgeholt, niemals rückdatiert. Vor dem Startdatum 2026-08-10 und nach vollständig absolvierter Woche läuft nur die Fälligkeitsauswertung.
- Neue Snapshots speichern einen L0-Point-in-Time-Vertrag mit Beobachtungs-Cutoff, Feature- und Labelschema, Benchmark- und Kostenregeln, Qualitätsflags, Leakage-Schutz und Datenfingerabdruck. Die 1.945 älteren Snapshots bleiben ehrlich als Legacy ohne diesen Vertrag markiert.
- Fällige Marktdaten werden für große Kohorten in begrenzten Batches geladen; FX-Kurse werden je Währung und Bewertungstag geteilt. Ergebnisfelder umfassen nun Bewertungstag, tatsächliche Rendite, beste und schlechteste Bewegung sowie `immer steigend` und `keine Änderung` als erste einfache Referenzen.
- Mehrwöchiger Dauerbetrieb sowie das Verhalten nach echter Unterbrechung oder verpasstem Termin bleiben betrieblich zu validieren.
- Der erste GitHub-Actions-Remote-Lauf bleibt als nachgeordnete, durch fehlende Commit-/Push-Freigabe blockierte Stabilitätsaufgabe offen.

Warum diese Aufgabe zuerst:

- Ein eigenständiger Nutzen gegenüber einer einzelnen KI-Anfrage entsteht erst durch fortlaufend gesammelte, zeitlich unveränderbare und später automatisch ausgewertete Daten.
- Die Lern- und Kalibrierungsmodule benötigen ausreichend viele echte Fälle; manuelle App-Nutzung baut diese Datenbasis zu langsam und unregelmäßig auf.
- Derselbe stark korrelierte Tagesbestand allein beweist keine allgemeine Prognosequalität. Ein fester Referenzkern plus wiederkehrende breite Wochenkohorten liefert Zeit-, Asset- und Regimevariation, ohne historische Prognosen zu überschreiben.
- Mehr Daten erzeugen nicht automatisch Lernen. Point-in-Time-Merkmale, ehrliche Labels, Vergleichsmodelle, zeitliche Validierung, kalibrierte Wahrscheinlichkeiten, Shadow-Betrieb und Rollback müssen vor jeder produktiven Selbstanpassung vorhanden sein.

Nächste konkrete Umsetzung:

1. **Technisch umgesetzt, realer Nachweis heute 22:30:** tatsächlicher Datenbankstand geprüft; 322 fällige Ein-Wochen-Fälle werden nur mit echten späteren Kursdaten ausgewertet. Fehlende Ergebnisse bleiben offen.
2. **Umgesetzt:** L0-Messvertrag für neue Point-in-Time-Snapshots einschließlich Ergebnislabels, expliziter Kostenabgrenzung, Datenqualität, Fingerabdruck und Leakage-Schutz. L2-Snapshots enthalten zusätzlich eine feste 20-Tage-Trendregel und einen assettyp-/regionsabhängigen Marktbenchmark. Vor jedem Tageslauf werden alle neuen Verträge vollständig verifiziert; ein Integritätsfehler stoppt Auswertung und Marktabruf.
3. **Umgesetzt, Realbetrieb ab 2026-08-10 zu belegen:** tägliche Fälligkeitsauswertung läuft vor der wöchentlichen Neuprognose; jeder Termin erzeugt höchstens eine fällige Kohorte.
4. **Umgesetzt, Datenqualität im Realbetrieb weiter zu prüfen:** 325-Referenzkern und 1.401 Erweiterungsassets bilden ein versioniertes 1.726-Asset-Universum in fünf deterministischen Wochengruppen. Delistings und dauerhaft fehlerhafte Ticker bleiben als laufende Pflegeaufgabe sichtbar.
5. **Umgesetzt, Realbefüllung ab 22:30 beziehungsweise 2026-08-10:** atomare private Wochenberichte dokumentieren Soll-/Ist-Abdeckung, Laufzeit, Fehler, Rate-Limits, Datenbankwachstum, Nachholen und fällige Ergebnisse. Ein verpasster Forward-Lauf bleibt sichtbar.
6. **Teilweise umgesetzt:** Ergebnisabdeckung, Richtungstrefferquote, Wilson-Unsicherheitsbereich, Precision/Recall, Balanced Accuracy, Rendite, beste/schlechteste Bewegung, Drawdown und Überschussrendite sind vorhanden. Neue Prognosezeiträume speichern eine ausdrücklich unkalibrierte Rohwahrscheinlichkeit; Brier Score, Log Loss, Kalibrierungsfehler und Bias werden nach Reifung automatisch berechnet. Echte zeitlich getrennte Kalibrierung, eigene Horizontwahrscheinlichkeiten und Opportunitätskosten bleiben offen.
7. **Technisch umgesetzt, reale Reifung offen:** bestehende Regelprognose wird getrennt gegen immer-steigend, keine-Änderung, eine unveränderbare 20-Tage-Trendregel und assettyp-/regionsabhängige Marktbenchmarks ausgewertet. Fehlende Benchmarkdaten verwerfen niemals das eigentliche Forward-Ergebnis.
8. **Umgesetzt:** Ergebnisse werden nach Analyseart, Horizont, Asset-Typ, Region, Marktphase, Datenqualität und Logikversion getrennt. Schwache oder fehlende Daten bleiben sichtbar; eine produktive Wahrscheinlichkeitsaussage wird daraus noch nicht erzeugt.
9. **Technisch vorbereitet, reale Daten fehlen:** verifizierten L2-Lernbestand reproduzierbar fingerprinten, konservative Mindestfälle/-wochen/-klassen prüfen und zeitliche Walk-Forward-Fenster mit Purging statt zufälligem Zeilenmischen bilden. Ein append-only Modellregister nimmt spätere Kandidaten ausschließlich als `shadow_only` mit Dataset-, Walk-Forward-, Code- und Artefakt-Fingerabdruck auf. Eine rollierende beobachtende Drift-/Qualitätsschicht vergleicht Ergebnis-, Wahrscheinlichkeits-, Referenz-, Eingabe-, Segment- und Betriebslage nur oberhalb fester Mindestfallzahlen. Ungesehene Qualitäts-, manuelle Review-, Canary- und Rollback-Gates sind vorbereitet; selbst vollständig bestandene Gates aktivieren niemals automatisch eine Produktionsversion. Erst nach bestandenem Datengate und zusätzlicher Power-Analyse dürfen transparente Challenger je Analyseart und Horizont trainiert werden.
10. Keine automatische Kauf-/Verkaufsfunktion und keine unkontrollierte Selbständerung einbauen; Freigaben benötigen dokumentierten ungesehenen Mehrwert, manuelle Zustimmung, neue Version und Rollback.
11. Nach jeder Einheit Tests sowie ROADMAP und PROJECT_STATUS aktualisieren. Nach ausdrücklich erlaubtem Commit und Push bleibt der vorbereitete GitHub-Actions-Lauf eine nachgeordnete Stabilitätsprüfung.

Prognose-Erweiterung innerhalb dieses Prioritätsblocks:

1. **Umgesetzt:** Analysefrequenz und Prognosehorizonte sind entkoppelt; ein Wochenlauf startet nicht mehr automatisch alle fünf Horizonte.
2. **Umgesetzt:** 1W wöchentlich, 1M alle zwei Wochen, 3M monatlich, 6M alle drei Monate und 12M alle sechs Monate; die Auswertung bleibt unabhängig am jeweiligen Zielhorizont aktiv.
3. **Umgesetzt:** versioniertes `long_horizon_eligible`-Evidenzgate mit nachvollziehbaren Gründen; ungeeignete Assets erzwingen keine 6M-/12M-Prognose.
4. Gemeinsames Unternehmens-/Listing-Identitätsmodell mit `company_id`/`issuer_id` und `listing_id` aufbauen.
5. Mehrfachlisting-Suche mit sichtbarer Auswahl von Primärlisting, ADR/ADS oder weiterer handelbarer Variante ergänzen.
6. Neue Identitäts- und Horizontfelder nicht löschend einführen; bestehende Point-in-Time- und Forward-Daten bleiben unverändert und unbekannte Altfelder werden nicht erfunden.
7. Reguläres Prognoseuniversum erst nach realer Kapazitätsprüfung von 1.726 in Richtung 2.500 bis 3.500 regelmäßig prognostizierte Assets erweitern.
8. Danach ein günstiges Discovery-/Monitoring-Universum für perspektivisch 5.000 bis 10.000 beobachtbare Assets vorbereiten, ohne jedes Asset teuer zu analysieren.
9. Vor jeder weiteren Skalierung Laufzeit, Abdeckung, Datenqualität, Rate-Limits, Vorfilter-Bias, Kontrollstichprobe, Branchen-/Regionsvielfalt und effektive Stichprobengröße real messen.

Dieser Block läuft nach dem priorisierten Swing-Ausbau weiter. Der Wochenbetrieb muss wiederkehrend laufen, echte Forward-Snapshots unverändert speichern, fällige Ergebnisse automatisch auswerten und seine Abdeckung sowie Fehler verständlich zeigen.

### Prioritätsblock 1 – Swing Trade Finder

Dieser Block ist die höchste Gesamtpriorität des Projekts. Er umfasst nicht nur die sichtbare Finder-Funktion, sondern die vollständige Fertigstellung und evidenzbasierte Verbesserung des SwingTrading-Bots. Swing-spezifische Datensammlung ist Kernarbeit dieses Blocks: Sie erzeugt ehrliche Trainings-, Validierungs- und Vergleichsdaten, verbessert die Genauigkeit aber nicht automatisch. Änderungen werden nur bei belegtem Vorteil auf zeitlich ungesehenen Daten und nach dem jeweils erforderlichen Gate übernommen.

Aktuell zuerst – Trade-Republic-Ausrichtung:

1. **Technisch umgesetzt:** Trade Republic ist die verbindliche Ausführungs-/Referenzebene für persönliche Swing-Trades. Der normale Nutzerbereich zeigt nur konkret als `TR handelbar` verifizierte Listings. `TR nicht handelbar` und `unbekannt` bleiben vollständig im Paper-/Forward-Test und erscheinen separat unter `Nur Paper / nicht bei Trade Republic handelbar`.
2. **Technisch umgesetzt:** listing-spezifische append-only Referenz mit Ticker, Börsenplatz, Währung und ISIN sowie den drei Statuswerten `TR handelbar`, `TR nicht handelbar` und `unbekannt`. Fehlende Metadaten können dauerhaft manuell verifiziert werden; andere ISINs beziehungsweise ADR-/GDR-/Instrumentvermischungen sind gesperrt.
3. **Technisch umgesetzt, derzeit manuelle Preisquelle:** `Aktueller Preis` sowie Einstieg, Limit, Maximalpreis, Stop, Ziele, Stückzahl und EUR-Beträge werden nur für dasselbe verifizierte TR-Listing ausgegeben. Dafür sind ein höchstens 15 Minuten alter, ausdrücklich aus Trade Republic erfasster EUR-Preis und ein zeitgleich erfasster Vergleichskurs des analysierten Listings erforderlich. Ihr Quotient bildet nur die Listing-Basis und verankert ältere technische Marken nicht neu; andernfalls steht `TR-Preis nicht verfügbar` beziehungsweise kein ausführbarer Plan. Yahoo darf niemals Ersatz- oder TR-Preis sein.
4. **Technisch umgesetzt:** Yahoo und andere Marktdaten bleiben getrennte Analyse-, Chart- und Forward-Test-Quellen. Der Analyseplan bleibt unveränderbar; der TR-Ausführungsplan dokumentiert Listing, Ausführungspreisquelle und technische Übertragungsrelation getrennt. Keine Broker-Verbindung und keine automatische Order.
5. **Technisch umgesetzt, reale Daten reifen:** Statistiken trennen Scannerqualität über alle objektiven Signale, TR-handelbare Listings, aktuell vollständig ausführbare TR-Pläne und Paper-only-Fälle.
6. **Als Nächstes real validieren:** konkrete TR-Listings schrittweise verifizieren und echte Forward-Ergebnisse der gesamten Scannerstichprobe mit der tatsächlich TR-ausführbaren Teilmenge vergleichen. Keine künstliche TR-, ETF- oder Aktienquote und keine neue Setup-Art vor ausreichender Reifung.

Nächste Swing-spezifische Umsetzung:

1. **Realen Betrieb zuerst beobachten:** Das vorhandene EWL-Forward-Signal und alle folgenden echten Signale über Eintritt, Gap/Verpassung, Ungültigkeit, Ziel 1/2, Stop, Reihenfolge, MFE/MAE, Haltedauer, Kosten, FX und Ergebnis in Euro/Prozent/R vollständig append-only verfolgen. Kein fester Nachher-Kurs ersetzt den Systemplan.
2. **Umgesetzt, Dauerbeobachtung läuft:** alle vier Regionalbereiche real mit Börsensitzungs-/Tageskerzenregeln, sichtbarer Abdeckung, Fehlern und Rate-Limits geprüft.
3. **Umgesetzt:** 2.520 liquide, zuverlässig handelbare Assets mit Schwerpunkt Einzelaktien; Prognose- und Swing-Universum bleiben getrennt.
4. **Umgesetzt:** binärer Grobfilter ohne versteckte Top-N-Ranggrenze; Ablehnungsgründe werden künftig je Assetklasse mitgeführt.
5. **Umgesetzt:** feste 60er-Grenze entfernt; alle 362 realen Amerika/Global-Grobfiltertreffer wurden vollständig analysiert.
6. **Technisch neutralisiert, Forward-Auswertung reift:** Der ursprüngliche Lauf mit 58,0 % ETF- gegenüber 14,48 % Aktien-Grobfilterquote wurde vollständig zerlegt. Zu breite feste Prozentzonen erzeugten viele ETF-False-Positives; Rohvolumen war nicht die Ursache. ATR-normalisierte Setupzonen, Volumenabdeckung statt Rohstückzahl-Hard-Gate und die Entfernung der nicht vergleichbaren Langfristqualität aus Freigabe und Rangfolge ergaben im Nachher-Reallauf 14,00 % ETF gegenüber 13,87 % Aktien – ohne Zielquote. Ab jetzt ausschließlich echte v3-Forward-Ergebnisse je Klasse sammeln; Vergleich erst ab mindestens 20 eindeutigen Ergebnissen je Aktie und ETF.
7. **Einheitliche Pipeline absichern:** manuelle und regionale Scans dürfen sich nur in Zeitpunkt, Region und Quellentyp unterscheiden. Order-, Strategie-, Stop-, Ziel-, Forward- und Datenqualitätsvertrag bleiben identisch.
8. **Spätere Erweiterungen sperren:** Weitere Setups und besonders ein Hebelmodus bleiben bis zu einer ausreichend großen, über mehrere Marktphasen stabilen echten Forward-Historie außerhalb von Swing-v1.

Projektweite PRIO-A-Aufgaben zu Stabilität, Datenschutz, Datenintegrität oder fehlerhaften Ergebnissen dürfen diese Swing-Reihenfolge jederzeit unterbrechen. Reiner Komfort und optische Erweiterungen kommen erst nach Stabilität, Datenqualität, Tests und Messbarkeit.

### Prioritätsblock 3 – spätere Produktarbeit

Erst nach den beiden Blöcken oben gilt folgende Reihenfolge:

1. Gemeinsame Navigation und Designsystem für die drei Hauptbereiche vervollständigen.
2. Asset-Analyse weiter in Einstiegsanalyse und quellenbasierte Long-Term-Analyse trennen.
3. Den Bereich `Investment Opportunities` mit zwei eigenen Scores, hochwertigem Feed und sicheren Übergaben aufbauen.
4. Weitere Komfortfunktionen und fachlich noch nicht validierte Erweiterungen umsetzen.

## Akzeptanzkriterien

Allgemeine Akzeptanzkriterien:

- Die App startet lokal ohne Python-Syntaxfehler.
- Streamlit kann die App laden.
- Vor bestandenem Echtgeld-Gate wird keine automatische Kauf- oder Verkaufsfunktion eingebaut.
- Vor bestandenem Echtgeld-Gate wird keine Broker-Anbindung eingebaut; eine spätere Live-Phase benötigt eine eigene ausdrückliche Freigabe.
- Fehlende Daten werden nicht geschätzt oder erfunden.
- Bei fehlenden Daten wird sichtbar `Daten nicht verfügbar` oder ein klarer Hinweis angezeigt.
- Asset-Qualität, Kaufsignal und Depot-Effekt bleiben getrennt.
- Portfolio-Daten beeinflussen niemals Asset-Qualität oder Kaufsignal.
- README wird aktualisiert, wenn sich Bedienung, Struktur oder wichtige Funktionen ändern.
- ROADMAP wird nach jeder Arbeitseinheit aktualisiert.

Akzeptanzkriterien für Designsystem und responsive Darstellung:

- Startseite, Asset-Analyse, Investment Opportunities, Swing Trade Finder, Prognosequalität und Einstellungen wirken wie Teile derselben ruhigen professionellen Finanzanwendung.
- Farben, Typografie, Abstände, Radien, Rahmen, Schatten und Hauptaktionen folgen gemeinsamen Regeln.
- Die Hauptansicht verwendet wenige hochwertige Flächen statt vieler gleichgewichteter Kleinkarten.
- Wichtige Texte werden vollständig angezeigt; es gibt kein abschneidendes `...` für Entscheidungs-, Risiko-, Bedingungs- oder Plantexte.
- Bei 390 Pixel Breite gibt es keinen horizontalen Seitenüberlauf; nebeneinanderliegende Kernelemente stapeln sich sinnvoll.
- Fachparameter, Rohdaten und Methodik erscheinen nicht in der normalen Hauptansicht.
- Seltene Einstellungen überladen weder Startseite noch Sidebar.
- Designänderungen verwenden bevorzugt native Streamlit-Komponenten und erhalten alle stabilen Bedienpfade.

Akzeptanzkriterien für die drei Hauptbereiche und Navigation:

- Das Hauptmenü trennt sichtbar `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder`.
- Jeder Bereich nennt seine eigene Leitfrage, seinen Horizont und die Grenzen seiner Bewertungslogik.
- Der bisherige `Opportunity Scanner` wird ohne Verlust vorhandener Paper-Trades oder Historien in `Swing Trade Finder` überführt.
- `Investment Opportunities` enthält keine kurzfristigen Swing-Setups; der Swing Trade Finder gibt keine langfristigen Investmentempfehlungen aus.
- Übergaben übernehmen Asset-Identität, Modus und erforderlichen Kontext, berechnen die Zielanalyse aber mit deren eigener Logik neu.
- Rücknavigation, direkte Asset-Suche und bestehende stabile Bedienpfade bleiben erhalten.

Akzeptanzkriterien für die gemeinsame dreistufige Informationshierarchie:

- Ebene 1 enthält nur klare Einordnung, kurze Begründung, wichtigste Risiken, konkreten Plan und Widerlegungsbedingung; bereichsspezifische Pflichtdaten bleiben vollständig.
- Ebene 2 erscheint erst auf Wunsch, beginnt je Facette mit einem Kurzfazit und zeigt Geschäftsmodell oder These, Qualität, Bewertung, Zukunftspotenzial, Einstieg, Chancen, Risiken, Szenarien, Marktumfeld sowie den Portfolio-Effekt nur bei aktivem Portfolio-Modus.
- Ebene 3 ist standardmäßig geschlossen und enthält technische und fundamentale Kennzahlen, Rohdaten, Datenqualität, Quellen, Proxies, Gewichte, Methodik, Modellversion und Prognosehistorie.
- Die Einstiegsanalyse zeigt in Ebene 1 zusätzlich getrennte Langfrist-/Preis-/Timing-Sicht, Horizont, Confidence, höchstens drei Gründe, höchstens zwei Risiken und einen vollständigen Handlungsplan.
- Empfehlung, Zonen, Tranchen, Bestätigungsweg, Alternative ohne Rücksetzer, Widerlegung und Gültigkeit widersprechen sich nicht.
- Der Abstand zum Allzeithoch wird nie allein als Kaufsignal verwendet.
- Vage Einzelwörter wie nur `Warten` werden nicht als vollständiger Plan ausgegeben.

Akzeptanzkriterien für Asset-Analyse und Long-Term-Analyse:

- Nutzer können Einstiegsanalyse und Long-Term-Analyse bewusst auswählen; Übergaben aus Investment Opportunities wählen den passenden Modus automatisch vor.
- Die Einstiegsanalyse beantwortet Preis, Timing und konkrete Handlung, ohne langfristige Qualität mit kurzfristiger Technik zu vermischen.
- Die Long-Term-Analyse erklärt Geschäftsmodell, Markt, Wettbewerb, Skalierbarkeit, Management, Kapitalverwendung, Fundamentaldaten, Bilanz, Verwässerung, Bewertung und Risiken über einen Horizont von drei bis sieben Jahren.
- Bull-, Basis- und Bear-Szenario nennen Voraussetzungen, Renditespanne, Unsicherheit und konkrete Widerlegungsbedingungen.
- Kurzfristige Charttechnik verändert in der Long-Term-Analyse nur den separaten Einstiegsplan, nicht Zukunftspotenzial oder Unternehmensqualität.
- Aussagen zu Strategie, Wettbewerb und Markt beruhen auf ausgewiesenen offiziellen oder belastbaren Quellen; Yahoo Finance allein gilt dafür nicht als ausreichend.
- Fehlende Quellen führen zu einer sichtbaren Datenlücke und niemals zu erfundenen Geschäftsmodell-, Markt- oder Strategieaussagen.

Akzeptanzkriterien für Mehrfachlistings, ADR/ADS und Primärnotierungen:

- Eine Unternehmensnamensuche mit mehreren relevanten Listings startet keine Analyse, bevor das konkrete Listing sichtbar gewählt oder eine klar sichtbare, änderbare Vorauswahl bestätigt wurde.
- Während der Analyse bleibt `Analysiertes Listing: …` mit Ticker, Börsenplatz, Originalwährung und Instrumenttyp sichtbar; ISIN und Primärlistingstatus erscheinen, sofern belastbar bekannt.
- XPeng zeigt mindestens `9868.HK` als Hongkong-Aktie und `XPEV` als US-ADS/ADR getrennt, sofern beide vom aktuellen Anbieter belastbar gefunden werden. Die Lösung ist emittentenbasiert und enthält keine XPeng-Sonderregel.
- Unternehmensdaten und Listingdaten besitzen getrennte stabile Identitäten. Langfristige Unternehmensqualität wird auf Emittentenebene normalisiert; Preis, Chart, Liquidität, Timing, Einstieg, Stop und Ziele bleiben vollständig listing-spezifisch.
- Kein Kurs, Chart, Volumen, Spread, Stop, Ziel, technische Marke, Rendite- oder Prognoseverlauf eines Listings wird für ein anderes Listing verwendet oder über ein ADR-Verhältnis technisch umgerechnet.
- ADR/ADS, Depositary Receipt, Stammaktie, Anteilsklasse, ETF und andere handelbare Varianten werden ausdrücklich gekennzeichnet. Unbekannte Primärnotierung, ISIN oder Umrechnungsrelation wird nicht erfunden.
- Neue Prognosesnapshots speichern Emittenten- und Listingidentität. Long-Term-Statistik zählt wirtschaftlich gleiche Listings nicht automatisch als unabhängige Unternehmen; kurzfristige Listingunterschiede dürfen getrennt untersucht werden.
- Bestehende Snapshots bleiben unverändert. Regressionstests decken XPeng, europäisches Unternehmen mit US-ADR, mehrere europäische Listings, eindeutige Einzelnotierung, direkte Tickereingabe, Unternehmensnamensuche und Vermischungs-Negativfälle ab.

Akzeptanzkriterien für Investment Opportunities:

- Die Modi `Aktuell attraktiv` und `Zukunftschancen 3+ Jahre` besitzen getrennte, dokumentierte und versionierte Scores.
- Ohne ausreichend hochwertigen Kandidaten erscheint `Aktuell keine überzeugende Investmentchance gefunden.`; freie Feed-Plätze werden nicht mit schwachen Ideen gefüllt.
- Der Feed zeigt ungefähr zehn kompakte Kandidaten mit Unternehmen, Ticker, Branche, Region, Modus, Horizont, Begründung, Einpreisung, Qualität, Potenzial beziehungsweise aktueller Attraktivität, Preis, Risiko, Szenarien und wichtigster Unsicherheit.
- `Jetzt analysieren` öffnet aus `Aktuell attraktiv` die Einstiegsanalyse und aus `Zukunftschancen 3+ Jahre` die Long-Term-Analyse.
- `Zur Watchlist`, `Schon bekannt`, `Später erneut zeigen` und `Nicht interessant` funktionieren lokal, nachvollziehbar und rückgängig machbar.
- Nutzerpräferenzen verändern ausschließlich Feed-Auswahl und Wiederanzeige, niemals den objektiven Score.
- Vielfalt nach Branche, Region, Größe und Bekanntheit wird erst unter bereits ausreichend guten Kandidaten angewendet.
- Ein starker Kursrückgang oder großer Abstand zum Allzeithoch reicht niemals allein für die Aufnahme.

Akzeptanzkriterien für Priorität 1:

- Oben im Dashboard gibt es keine widersprüchlichen Empfehlungen.
- Der Nutzer sieht klar:
  - Was ist das Asset?
  - Wie gut ist die Asset-Qualität?
  - Wie stark ist das aktuelle Kaufsignal?
  - Was sagt das Research-Modul?
  - Was sagt der Depot-Effekt, falls Portfolio-Modus aktiv ist?
- Anfänger-Erklärung beschreibt die praktische Bedeutung der Einschätzung.
- Fehler bei Yahoo Finance führen nicht zu App-Abstürzen.
- Suchhistorie ist einfacher nutzbar.

Akzeptanzkriterien für Research-Module:

- Jeder Score zeigt eine kurze Begründung.
- Jeder Score zeigt bei fehlenden Daten ehrlich `Daten nicht verfügbar`.
- Bull/Base/Bear-Wahrscheinlichkeiten ergeben zusammen 100 %.
- Nachkaufzonen zeigen keine erfundenen Marken.
- Wenn keine Marke berechenbar ist, wird `Daten nicht verfügbar` angezeigt.

Akzeptanzkriterien für Marktregime-, Innovations-, Blasen- und Makro-Wirkungsmodule:

- Marktregime werden nur aus vorhandenen Daten, Proxies oder klar gekennzeichneten qualitativen Hinweisen abgeleitet.
- Jede Marktregime-Einordnung nennt Hinweise, Gegenargumente, Unsicherheiten und einen Vertrauensgrad.
- Innovationsführer, indirekte Profiteure und Hype-Aktien werden getrennt ausgewiesen.
- Das Blasenrisiko wird als Score 0-10 angezeigt und nach Bewertung, Medienaufmerksamkeit, Zuflüssen, Momentum und Sentiment begründet.
- Fehlende Bewertungs-, Flow-, Medien- oder Sentimentdaten senken die Belastbarkeit und werden nicht geschätzt.
- Das Makro-Wirkungsmodul erklärt Zinsen, Inflation, Realzinsen, Dollar und Liquidität verständlich.
- Auswirkungen auf Aktien, ETFs, Krypto und Rohstoffe werden getrennt erklärt.
- Öl, Gas, Kupfer, Gold und Uran werden als eigene Rohstoffgruppen berücksichtigt, sofern Daten verfügbar sind.
- Korrelationen werden nicht als sichere Kausalitäten dargestellt.
- Jede Makro-Aussage enthält einen Hinweis auf Unsicherheit, Datenlage oder mögliche Gegenbewegungen.

Akzeptanzkriterien für Portfolio-Modus:

- Portfolio-Modus AUS: keine Depotdaten, keine Klumpenrisiko-Warnung, keine Cash-Bewertung.
- Portfolio-Modus AN: Depot-Effekt wird zusätzlich angezeigt.
- Depot-Effekt verändert Asset-Qualität und Kaufsignal nicht.

Akzeptanzkriterien für Forward-Testing, Decision-Tracking und Prognose-Tracking:

- Tracking ist optional und transparent.
- Keine Broker-Anbindung und keine automatische Kauf- oder Verkaufsfunktion.
- Gespeichert werden nur Analysezeitpunkt, Scores, Szenarien, Wahrscheinlichkeiten, Marken, Nutzerentscheidung und spätere echte Ergebnisdaten.
- Trefferquoten werden nur aus vorhandenen echten Daten berechnet.
- Fehlende Ergebnisdaten werden als `Daten nicht verfügbar` angezeigt.
- Ergebnisse sind nach Asset-Typ, Marktphase, Signalart und Modul auswertbar.

Akzeptanzkriterien für Kalibrierungs- und Lernmodul:

- Das Modul zeigt Verbesserungsvorschläge, ändert Score-Gewichtungen aber nicht heimlich automatisch.
- Jede vorgeschlagene Gewichtungs- oder Logikänderung nennt Auslöser, Datenbasis und erwartete Wirkung.
- Häufige Fehlprognosen erhöhen nachvollziehbar die Priorität des betroffenen Moduls.
- Prioritätsänderungen werden mit ursprünglicher Priorität, neuer Priorität und Begründung im Änderungsprotokoll dokumentiert.

Akzeptanzkriterien für bedienungsfreien Daten- und Lernbetrieb:

- Bei eingeschaltetem Rechner und verfügbarer Internetverbindung startet der geplante Lauf ohne geöffnete Streamlit-App und ohne Klick des Nutzers.
- Neue Prognosen werden je Handelstag, Asset und Logikversion eindeutig sowie mit Erstellungszeitpunkt gespeichert.
- Fällige Prognosen werden automatisch mit echten späteren Marktdaten ausgewertet; fehlende Daten bleiben offen und werden bei späteren Läufen erneut versucht.
- Einzelne Datenfehler stoppen nicht den Gesamtlauf; Wiederholungsversuche, Fehler und Rate Limits werden nachvollziehbar protokolliert.
- Unterbrochene Läufe werden sicher fortgesetzt und bereits erfolgreiche Assets nicht doppelt verarbeitet.
- Ein verpasster Termin startet beim nächsten verfügbaren Zeitpunkt. Nicht erfasste historische Echtzeit-Prognosen werden als Datenlücke dokumentiert und niemals rückwirkend erfunden.
- Letzter Lauf, Laufstatus, Fehlerzahl, fällige Auswertungen und Datenbankzustand sind ohne technische Logsuche verständlich einsehbar.
- Trefferquoten, Fehlmuster, Confidence und Kalibrierungsvorschläge aktualisieren sich aus den gesammelten Ergebnissen automatisch.
- Long-Term-, Einstiegs- und Swing-Prognosen bleiben nach Modell, Version, Horizont und passendem Vergleichsmaßstab getrennt auswertbar.
- Produktionsregeln und Score-Gewichtungen ändern sich in Version 1 nicht heimlich. Jede spätere automatische Kalibrierung benötigt Versionierung, Mindestdaten, Out-of-Sample-Test, dokumentierten Vorteil und Rollback.
- In allen aktuellen Forschungs-, Forward-, Paper- und Shadow-Stufen werden keine Orders ausgeführt und keine produktiven Brokerdaten benötigt; lokale Lernhistorien werden niemals automatisch gelöscht.

Akzeptanzkriterien für Swing Trade Finder und Trading-Modus:

- Der Scanner durchsucht das intern gepflegte, versionierte Universum aus `config/swing_universe.csv` mit mindestens 1.000 aktiven gültigen Assets; ServiceNow ist enthalten, ungültige Zeilen werden protokolliert und Hebel-/Inverse-Produkte abgelehnt.
- Alle Assets erhalten eine schnelle Prüfung von Datenverfügbarkeit, Liquidität, Volumen, Volatilität, Trend und Setup-Struktur. Jeder als möglicherweise relevant eingestufte Kandidat wird vollständig analysiert; es gibt nach der geplanten Umstellung keine feste 60er- oder andere Top-N-Grenze. Zählwerte für Universum, geladene Daten, Vorfilter, Tiefenanalyse, Freigaben und Ausfälle bleiben sichtbar.
- Version 1 gibt ausschließlich Long-Rücksetzer im intakten Aufwärtstrend und bestätigte Long-Ausbrüche für liquide Aktien, ETFs und große Kryptowährungen frei.
- Alle zentralen Qualitäts-, Liquiditäts-, Signal-, Markt-, Ereignis-, Struktur-, Einstiegs-, CRV- und Expected-Value-Grenzen müssen erfüllt sein; es gibt keinen erzwungenen relativ besten Trade.
- Ohne gültiges Setup erscheint `Aktuell kein hochwertiger Trade vorhanden.` mit Zahl geprüfter Assets, Scanzeit und Ablehnungszusammenfassung.
- Die Hauptansicht zeigt nur freigegebene Trades; es gibt dort weder `Beobachten`, schwache Watchlist-Kandidaten noch eine lange Ablehnungsrangliste.
- Jedes Setup zeigt konkrete Eintrittsbedingung, Einstieg, Stop, strukturelle Ziele, Chance/Risiko, CRV, Gültigkeit, maximalen Einstieg und Nichteinstiegsbedingungen ohne abgeschnittene Pflichttexte.
- Das CRV folgt für Long exakt `(Ziel - Einstieg) / (Einstieg - Stop)`; ungültige Geometrie, zu niedriges CRV, verpasster Einstieg, Strukturbruch, Ablauf und hohes Ereignisrisiko verhindern die Freigabe.
- Trefferwahrscheinlichkeiten werden unter 20 ausgewerteten vergleichbaren Fällen nicht als belastbare Zahl ausgegeben.
- In der Hauptansicht ist ausschließlich das Tradingkapital fachlich einzugeben. Risiko-, Stop-, CRV-, Volatilitäts- und Positionsgrenzen liegen zentral, versioniert, getestet und nur lesbar unter den erweiterten Einstellungen.
- Stops liegen bei Long immer unter dem Einstieg, folgen Struktur und Volatilität und werden niemals passend zur gewünschten Stückzahl verschoben. Zu große Stop-Abstände oder ein ungültiges Setup verhindern die Freigabe.
- Positionsgrößen berücksichtigen Tradingkapital, 0,50 % maximales Risiko je Trade, 2,00 % offenes Gesamtrisiko, 50 % Gesamtbelastung und 20 % je Position; die Anzahl gleichzeitiger Trades ist dynamisch. Ohne Kapital wird keine Stückzahl erfunden. Geplanter Verlust und mögliche Gewinne an Ziel 1/2 werden in Euro und Prozent gezeigt, einschließlich Gap-Risikohinweis.
- Vor der ersten Finder-Nutzung ist einmalig ein lokal gespeicherter Verlusthinweis zu bestätigen. Kein Setup löst automatisch Kauf, Verkauf oder Order aus.

Zusätzliche Akzeptanzkriterien für Orderplan, Einstieg und Währung:

- Jede Freigabe enthält einen tatsächlich ausführbaren Plan mit Ordertyp, Kaufpreis, gegebenenfalls Aktivierungskurs, Maximalpreis, Stop, Ziel 1/2, Stückzahl, Kapitaleinsatz, geplantem Verlust, möglichem Gewinn, Gültigkeit und Löschbedingung.
- Ein Pullback-Plan ist als konkrete Limit-Logik formuliert. Ein Ausbruch verwendet entweder eine eindeutige Stop-Limit-Logik oder eine Schlusskursbestätigung mit frühestem Einstieg in der nächsten Sitzung.
- Schlusskurs-, Intraday- und Pullback-Einstieg besitzen getrennte, versionierte Regeln. Kein Schlusskurssignal erhält rückwirkend einen unrealistischen Einstieg zum selben Schlusskurs.
- Der bestätigte Stop wird nach Eröffnung niemals weiter vom Einstieg entfernt. Jede spätere Anpassung folgt einer bereits beim Signal gespeicherten Regel.
- Alle sichtbaren Preise und Euro-Ergebnisse eines Trades beruhen auf demselben FX-Snapshot. Originalwährung, FX-Kurs, FX-Zeitpunkt und Quelle bleiben gespeichert; historische Ergebnisse verwenden keinen heutigen Wechselkurs.
- Eine automatische Konsistenzprüfung blockiert jeden Plan mit widersprüchlichen Marken, Währungen, CRV-Werten, Aktivierungs- oder Maximalpreisen.
- Die normale Karte bleibt vollständig bei etwa 390 Pixel Breite lesbar. Technische Herleitung und Rohdaten liegen hinter Details; Pflichtplan, Nichteinstiegsbedingungen und Gap-Hinweis werden nicht abgeschnitten.

Zusätzliche Akzeptanzkriterien für Universum und Hintergrundbetrieb:

- Jedes Universumsasset besitzt eine stabile Identität und soweit verfügbar Name, Ticker, ISIN, Börsenplatz, Asset-Typ, Originalwährung, Region, Branche/Kategorie, Aktivstatus, Liquiditätsklasse, Version und Gültigkeitszeitraum.
- Tickerwechsel, Delistings, Ausschlüsse und dauerhaft fehlerhafte Datenquellen werden versioniert und scanübergreifend dokumentiert. Historische Signale werden dabei weder gelöscht noch umgedeutet.
- Der reale 2.520-Asset-Betrieb dokumentiert je Bereich Auswahl, geladene Assets, Dauer, Fehler und Rate-Limits; der erste vollständige Nachweis erreicht 2.517/2.520 geladene Assets ohne Rate-Limit.
- Swing-Scans laufen zu dokumentierten regional passenden Zeiten ohne geöffnete App. Kryptowährungen besitzen einen getrennten UTC-basierten Zeitplan; Börsenkalender und Feiertage werden berücksichtigt.
- Prognoserunner und Swing-Runner besitzen getrennte Lauf-, Sperr-, Signal- und Statistikmodelle. Ein Fehler eines Assets stoppt nicht den Gesamtlauf; Wiederaufnahme erzeugt keine doppelten Signale.
- Jeder Lauf speichert auch dann einen vollständigen unveränderbaren Scan-Datensatz, wenn kein Trade freigegeben wurde.
- Das Swing-Universum liegt versioniert bei 2.520 liquiden Assets; Einzelaktien bleiben Schwerpunkt, ETFs und große Kryptowährungen Ergänzung. Prognose- und Swing-Universum bleiben getrennt.
- Der Grobfilter liefert nur `offensichtlich ungeeignet` oder `möglicherweise relevant`. Er bildet keine versteckte Rangliste; alle möglicherweise relevanten Kandidaten gehen in die Tiefenanalyse.
- Eine außergewöhnlich hohe Zahl an Tiefenanalysen wird über fortsetzbare Batches, Cache, kontrollierte Parallelisierung, Provider-Schonung und Fehlerisolierung verarbeitet, nicht durch stilles Abschneiden auf 60.
- Für Aktien, ETFs und Krypto werden Universum, geladene Assets, Grobfilterfälle, Tiefenanalysen und Freigaben getrennt gezählt. Forward-Statistiken vergleichen R, Profitfaktor, Drawdown, Gewinn/Verlust, Haltedauer, Gap-Risiko, verpasste Einstiege und Kosten je Assetklasse.
- Eine reproduzierbare Kontrollstichprobe aus ausgeschiedenen/unauffälligen Assets wird vollständig analysiert, damit Vorfilter-Bias und übersehene Chancen messbar werden. Keine Assetklasse erhält pauschalen Bonus oder Malus.
- Je Region sind maßgebliche Börsensitzung, Zeitzone, offizieller letzter Scan, Status, Datenabdeckung, nächster Termin, Feiertags-/Wochenendbehandlung und Nachholregel sichtbar. Krypto verwendet einen kanonischen UTC-Cutoff; Aktien-/ETF-Signale beruhen auf abgeschlossenen regionalen Tageskerzen.
- Manueller und geplanter Swing-Scan verwenden dieselbe fachliche Pipeline und dieselben versionierten Order-, Stop-, Ziel-, Forward- und Datenqualitätsverträge.

Zusätzliche Akzeptanzkriterien für Forward-Test, Archiv und Statistik:

- Ein echter Forward-Fall entsteht nur durch ein zum damaligen Zeitpunkt tatsächlich erzeugtes und sofort gespeichertes Signal. Rückwirkende Scanner-Simulationen bleiben klar getrennt und erhöhen keine echte Forward-Fallzahl.
- Ein Signal gilt nur nach seinem gespeicherten Trade-Plan als Gewinn oder Verlust. Ein später lediglich höherer Kurs reicht nicht; Eintritt, realistischer Kauf, Maximalpreis, Gap, Ungültigkeit, Ziel-/Stopreihenfolge, MFE/MAE, Haltedauer, Kosten und Ergebnis in Euro/Prozent/R entscheiden.
- Der ursprüngliche Signal-Snapshot ist append-only. Spätere Aktivierung, Einstieg, Stop, Ziel, Änderung oder Abschluss werden als neue zeitlich geordnete Ereignisse gespeichert.
- Die automatische Auswertung verwendet keine Daten vor dem Signalzeitpunkt und prüft realistischen Einstieg, Maximalpreis, Gaps, Kosten, Slippage, Ablauf, Stop-/Zielreihenfolge und Datenqualität mit der besten belastbaren zeitlichen Auflösung.
- Liegen Stop und Ziel in derselben Kerze, werden kleinere Intervalle versucht. Bleibt die Reihenfolge unklar, lautet der Status `Reihenfolge nicht eindeutig`; Ziel zuerst darf nicht unterstellt werden.
- Signale ohne Einstieg, offene, nicht eindeutige und nicht auswertbare Fälle zählen weder als Gewinner noch als Verlierer. Datenqualität ist mindestens als `hoch`, `mittel`, `eingeschränkt` oder `nicht auswertbar` sichtbar.
- Das Trade-Archiv enthält Suche, Filter, ursprünglichen Plan, theoretischen Ablauf, Ergebnis in Euro/Prozent/R, Haltedauer, Kostenannahmen, Datenqualität und chronologischen Ereignisverlauf.
- Statistik trennt mindestens Setup, Einstiegsmethode, Asset-Typ, Marktphase, Region, Datenqualität, Logikversion, echten Forward-Test, historische Simulation, Paper- und Nutzertrade.
- Unter 20 eindeutig ausgewerteten vergleichbaren Fällen erscheint exakt `Trefferwahrscheinlichkeit noch nicht belastbar.`; es wird keine scheinpräzise Quote gezeigt.

Zusätzliche Akzeptanzkriterien für Nutzertrade und aktive Begleitung:

- `Trade getätigt` speichert erst nach ausdrücklicher Bestätigung tatsächlichen Einstieg, Stückzahl und Zeitpunkt. Abweichungen vom Systemplan werden vorab gewarnt und dauerhaft markiert.
- Ein Nutzertrade besitzt eine eigene ID und einen eigenen Lebenszyklus. Er verändert weder den objektiven Paper-Snapshot noch dessen Ergebnis.
- `Meine aktiven Trades` zeigt Plan, tatsächliche Position, aktuellen Stand, Stop, nächstes Ziel, Haltedauer, klare regelbasierte Handlung, Aktualität und Datenqualität.
- Stop-Nachzug, Teilverkauf und Schließen werden nur nach Nutzerbestätigung als Ereignis erfasst. Die App empfiehlt, aber kauft, verkauft oder ändert niemals eine Brokerorder.
- Aktive Hinweise folgen den vor Einstieg versioniert gespeicherten Regeln. Ein Stop wird nie weiter weg gesetzt; Hoffnung, Gier oder kleine normale Schwankungen sind keine Regeländerung.
- Bei veralteten, widersprüchlichen oder unzureichenden Daten lautet der Zustand `Daten derzeit nicht belastbar`; es wird keine konkrete dringende Handlung erfunden.

Akzeptanzkriterien für Trade Journal und Performance Tracking:

- Vorgeschlagene Trades werden in `trade_history.json` gespeichert.
- Gespeichert werden nur Analyse- und Setupdaten, keine Broker-Zugangsdaten.
- Der vorhandene Legacy-Review prüft 1 Woche, 1 Monat, 3 Monate sowie kompatibel 6 und 12 Monate. Diese Horizontprüfung bleibt als ergänzende Langzeitbetrachtung erhalten.
- Der neue Swing-Forward-Test bewertet zusätzlich den tatsächlichen Signal- und Trade-Verlauf nach den Regeln aus Phase D; erst diese Auswertung bestimmt Aktivierung, Einstieg, Ziel-/Stopreihenfolge, Ablauf und Ergebnis in R.
- Treffer, Fehlschlag, Ziel erreicht, Stop erreicht, maximale positive und negative Entwicklung werden ausschließlich aus echten zeitlich passenden Kursdaten berechnet.
- Fehlende Kursdaten erzeugen keinen geschätzten Treffer, sondern einen klaren Datenhinweis.

Akzeptanzkriterien für Confidence-System, Signalanalyse und Lernsystem:

- Jede Chance wird zusammen mit einem Confidence Score angezeigt.
- Wenn historische Daten vorhanden sind, zeigt die App Anzahl ähnlicher Setups und Trefferquote ähnlicher Setups.
- Unter 20 Fällen erscheint `Datenbasis zu klein`.
- Zwischen 20 und 50 Fällen werden nur vorsichtige Hinweise angezeigt.
- Über 50 Fällen sind Kalibrierungsvorschläge erlaubt.
- Kalibrierungsvorschläge nennen Datenbasis, Anzahl Fälle, Trefferquote und Begründung.
- Das Lernsystem analysiert, ändert aber in Version 1 keine Gewichtungen automatisch.

Akzeptanzkriterien für das kontrollierte echte Lernsystem:

- Das erweiterte Universum ist keine Einmalsammlung: Jedes reguläre Asset besitzt eine feste Wochengruppe und wird wiederkehrend analysiert; Soll-/Ist-Abdeckung und Ausnahmen sind nachvollziehbar. Nicht jede Analyse startet dabei automatisch alle fünf Horizonte.
- Der bestehende 325-Asset-Kern bleibt als stabile Referenz erhalten. Das umgesetzte 1.726-Asset-Universum wird erst nach realer Kapazitätsprüfung Richtung 2.500 bis 3.500 regelmäßig prognostizierte Assets erweitert; ein späteres Discovery-/Monitoring-Universum kann bei tragbarer Last ungefähr 5.000 bis 10.000 beobachtbare Assets umfassen.
- Neue Horizontstarts folgen dem versionierten Rhythmus: 1W wöchentlich, 1M alle zwei Wochen, 3M monatlich, 6M höchstens alle drei Monate und 12M höchstens alle sechs Monate. Die Ergebnisprüfung erfolgt weiterhin exakt nach dem jeweiligen Horizont.
- 6M und 12M werden nur für nachvollziehbar `long_horizon_eligible` Assets erzeugt. Eignungsgrund, Datenqualität und Auswahlversion sind gespeichert; ungeeignete Assets erhalten keine erzwungene langfristige Prognose.
- Horizontuniversen bleiben nach Region, Branche, Größe und Asset-Typ diversifiziert und sind nicht auf US-Mega-Caps beschränkt. Die genaue Zahl entsteht aus Eignung, Datenqualität und gemessener Laufzeit.
- Discovery-Vorfilter werden mit einer reproduzierbaren Kontrollstichprobe unauffälliger beziehungsweise abgelehnter Assets auf Auswahlbias geprüft.
- Neue Wochenprognosen überschreiben keine alten Snapshots oder offenen Horizonte. Jede Prognose ist eindeutig nach Asset, Zeitpunkt, Analyseart, Horizont, Logik- und Feature-Version identifizierbar.
- Neue Prognosen speichern `company_id`/`issuer_id` und `listing_id` sowie Ticker, Börse, Instrumenttyp, Währung, Primärlistingstatus, ISIN und gegebenenfalls belegtes ADR-/ADS-Verhältnis. Legacy-Snapshots bleiben unverändert und erhalten keine erfundenen historischen Identitätsfelder.
- Jeder Trainingsdatensatz enthält nur Point-in-Time-Merkmale, die zum Prognosezeitpunkt tatsächlich verfügbar waren, einschließlich Quellenzeit, Datenalter, Datenlücken und Qualitätsstatus.
- Automatische Tests erkennen mindestens Zukunftswissen, überlappende Zeitfenster, doppelte Snapshots, Ticker-/Unternehmenswechsel, Survivorship Bias und nicht reproduzierbare Transformationen.
- Jede Analyseart und jeder Horizont besitzt eine eigene fachliche Zieldefinition; ein Ein-Wochen-Fehler bewertet keine noch offene Mehrmonats- oder Long-Term-Prognose vorzeitig.
- Alle Modelle werden auf denselben Assets und Zeitpunkten gegen die bisherige Regelbasis, einfache Richtungs-/Trendregeln und passende Marktbenchmarks geprüft.
- Modellbewertung umfasst neben Trefferquote mindestens Wahrscheinlichkeitskalibrierung, Brier Score oder Log Loss, Abdeckung/Enthaltung sowie die für die Analyseart passenden Rendite-, Risiko- und Opportunitätskostenmaße.
- Statistische Unsicherheit berücksichtigt gemeinsame Wochen-/Marktbewegungen, überlappende Horizonte und mehrere Listings desselben Emittenten; korrelierte Prognosen werden nicht als vollständig unabhängige Fälle ausgegeben. Reine Fallzahl und effektive Stichprobengröße werden bei Bedarf getrennt gezeigt.
- Die bestehenden Stufen 20/50 erlauben weiterhin nur frühe Hinweise. Training, Wahrscheinlichkeitsanzeige und Produktionsfreigabe besitzen strengere, vorab definierte Reifeanforderungen nach Fallzahl, Zahl getrennter Zeitperioden, Segmentabdeckung und Unsicherheit.
- Training, Validierung und Test werden ausschließlich zeitlich getrennt. Overlapping-Horizon-Leakage wird durch Purging beziehungsweise zeitliche Sperrbereiche verhindert; zufälliges Zeilenmischen ist nicht zulässig.
- Feature-Auswahl, Hyperparameter und Wahrscheinlichkeitskalibrierung sehen die endgültige Testperiode nicht. Nach ihrer Nutzung wird für die nächste Runde eine neue spätere Testperiode benötigt.
- Ein Challenger muss die vorhandene Regelbasis und vorab benannte einfache Referenzen in mehreren aufeinanderfolgenden Walk-Forward-Fenstern nach Kosten schlagen; eine einzelne gute Periode oder Gesamtmetrik genügt nicht.
- Kritische Verschlechterungen nach Asset-Typ, Marktphase, Region, Datenqualität oder Empfehlungskategorie verhindern die Freigabe, auch wenn der Gesamtwert besser aussieht.
- `Hohe Wahrscheinlichkeit` erscheint nur für ausreichend große, auf ungesehenen Daten kalibrierte Wahrscheinlichkeitsgruppen. Fallzahl, Zeitraum, Unsicherheit, Modellversion und Datenstand werden daneben sichtbar.
- Unsichere, schlecht abgedeckte oder außerhalb der bekannten Datenverteilung liegende Fälle führen zu `keine belastbare Empfehlung`; die Enthaltung wird als Qualitätsfunktion gemessen und nicht als Fehler versteckt.
- Lernende Kandidaten laufen zunächst im Shadow-Modus. Ihre Prognosen werden gespeichert und ausgewertet, verändern aber weder sichtbare Empfehlung noch Produktionsscore.
- Jede Produktionsfreigabe besitzt Modellregistereintrag, Datenfingerabdruck, Feature-Schema, Trainings-/Prüfzeitraum, Referenzvergleich, Kalibrierungsbericht, bestandene Tests, manuelle Zustimmung und neue Modellversion.
- Canary-Prüfung und getesteter Rollback auf die letzte freigegebene Version sind vor einer breiten Aktivierung verpflichtend.
- Ein einzelnes falsches Ergebnis löst keine Gewichts- oder Modelländerung aus. Nachtraining erfolgt nur nach definiertem Zeitplan oder dokumentiertem Drift-Auslöser und durchläuft erneut alle Gates.
- Daten-, Vorhersage-, Kalibrierungs- und Ergebnisdrift werden laufend überwacht. Bei Datenbruch oder Qualitätsverlust wird das lernende Modell deaktiviert oder zurückgesetzt, statt weiter selbstständig Empfehlungen zu erzeugen.
- Historische Snapshots, Ergebnisse und Modellartefakte bleiben lokal, integritätsgeprüft, gesichert und ohne automatische Löschung nachvollziehbar. Sensible Nutzer- oder Brokerdaten sind kein Trainingsbestandteil.
- Das System führt keine Orders aus und verspricht keine sichere Rendite. Sein nachweisbares Ziel ist bessere Kalibrierung, stabiler Vorteil gegenüber Referenzen und ehrliche Enthaltung bei fehlender Evidenz.

## Arbeitsmodus

Wenn der Nutzer später schreibt:

- `Arbeite weiter`
- `Weiter`
- `Setze die Entwicklung fort`
- `Arbeite bis zum Limit`

dann soll automatisch folgender Arbeitsmodus gelten:

1. `ROADMAP.md` lesen.
2. Zuerst den aktiven verbindlichen Hauptblock bestimmen: SwingTrading-Bot einschließlich seiner Daten-, Forschungs- und Validierungsstufen vor allgemeinem Wochen-/Prognosebetrieb vor späterer Produktarbeit.
3. Nur innerhalb dieses Blocks alle offenen Aufgaben nach Analysequalität, Stabilität, Datenqualität, Messbarkeit und Lernfähigkeit bewerten.
4. Die höchste sichere Aufgabe des aktiven Blocks auswählen. Nur ein kritischer Fehler bei Stabilität, Datenschutz, Datenintegrität oder falschen Ergebnissen darf blockübergreifend vorgezogen werden.
5. Die ausgewählte Aufgabe implementieren.
6. Die App testen.
7. Fehler beheben.
8. `README.md` aktualisieren, wenn sich Bedienung, Funktionen oder Struktur ändern.
9. `ROADMAP.md` aktualisieren.
10. Prioritätsänderungen im Änderungsprotokoll dokumentieren.
11. `git status` prüfen und geänderte Dateien identifizieren.
12. Ohne ausdrückliche Anweisung keinen Commit erstellen und keinen Push ausführen.
13. Nur wenn der Nutzer Commit oder Push ausdrücklich beauftragt: Änderungen noch einmal prüfen, den Auftrag ausführen und das Ergebnis melden.
14. Wenn ein ausdrücklich beauftragter Commit oder Push fehlschlägt: Fehler dokumentieren, Nutzer informieren und Änderungen lokal behalten.
15. Danach die nächste offene Aufgabe bearbeiten.
16. Wiederholen, bis keine offene Aufgabe mehr sinnvoll bearbeitbar ist oder kein Arbeitsbudget mehr vorhanden ist.

Während dieses Arbeitsmodus gilt:

- Bestehende App nicht unnötig neu bauen.
- Keine vorhandenen Funktionen entfernen.
- Änderungen klein, nachvollziehbar und testbar halten.
- Keine automatische Kauf- oder Verkaufsfunktion vor bestandenem Echtgeld-Gate einbauen.
- Keine Broker-Anbindung vor bestandenem Echtgeld-Gate einbauen; selbst danach nur im ausdrücklich beauftragten Live-Bot-Arbeitsblock.
- Keine Daten erfinden.
- Bei fehlenden Daten ehrlich bleiben.
- Portfolio-Daten nur im Depot-Effekt verwenden.
- Wenn für eine offene Aufgabe kein genauer Implementierungs-Prompt vorhanden ist, wird die Aufgabe selbstständig analysiert, ein Umsetzungsplan erstellt, die Lösung implementiert, getestet und dokumentiert.
- Wenn eine kleine Architekturarbeit den aktiven Hauptblock sicherer oder zuverlässig umsetzbar macht, darf sie innerhalb dieses Blocks vorgezogen werden. Die verbindliche Reihenfolge SwingTrading-Bot einschließlich Datensammlung vor allgemeinem Wochen-/Prognosebetrieb vor späterer Produktarbeit bleibt bestehen, bis der Nutzer sie ändert oder ein kritischer Fehler sie vorübergehend unterbricht.
- Änderungen an der ROADMAP-Reihenfolge müssen im Änderungsprotokoll dokumentiert werden.
- Ziel ist nicht starres Abarbeiten, sondern die beste technische Lösung für die bestehende App.

Langzeit-Ziel des Arbeitsmodus:

- Der Nutzer soll langfristig meist nur noch `Arbeite weiter` schreiben müssen.
- Danach werden Planung, Umsetzung, Tests und Dokumentation autonom ausgeführt, soweit dies sicher möglich ist.
- `git status` und die geänderten Dateien werden geprüft. Commit, Push und externe Veröffentlichung erfolgen nur nach ausdrücklichem Auftrag.

## Dynamische Priorisierung

Die dynamische Priorisierung folgt seit 2026-08-17 dieser Hauptreihenfolge: zuerst den SwingTrading-Bot fertigstellen und evidenzbasiert verbessern, einschließlich historischer Walk-Forward-Forschung, echter Forward-/Paper-Daten, später autonomer Paper- und Shadow-Live-Daten sowie aller erforderlichen Sicherheitsgates. Danach folgt der allgemeine Wochen-/Prognosebetrieb als eigener Produktzweig, anschließend andere Produkt- und Komfortbereiche. Innerhalb der jeweils zulässigen Bot-Stufe wird nicht blind die erste Aufgabe gewählt, sondern die tatsächliche Wirkung auf Erwartungswert nach Kosten, Risiko, Stabilität, Datenqualität, Messbarkeit und Lernfähigkeit bewertet.

### PRIO A: Grundfähigkeit der Analyse

Innerhalb des aktiven Hauptblocks höchste Priorität; blockübergreifend nur bei einem kritischen Fehler:

- Datenqualität
- Fehlerbehandlung
- Stabilität
- Asset-Erkennung
- Asset-Analyse und Quellenqualität
- Bewertungslogik
- Marktphasen-Erkennung
- Wahrscheinlichkeiten
- Vertrauensscore
- Fundamentaldaten
- Krypto-Analyse
- Makro
- Marktregime
- Makro-Wirkungsanalyse
- Innovationsanalyse
- Blasenrisiko
- Rohstoffe
- News
- Geopolitik
- Risikoanalyse

Diese Aufgaben dürfen immer vorgezogen werden, wenn sie die Analyse belastbarer, ehrlicher oder stabiler machen.

### PRIO B: Messung der Analysequalität

- SwingTrading-Bot einschließlich Swing-Walk-Forward-, Forward-/Paper-Datensammlung, Strategieverbesserung und der jeweils nächsten zulässigen Bot-Stufe
- automatische Swing-Fälligkeitsauswertung, Kosten-/Ausführungsanalyse, Kalibrierung und Benchmark-Vergleich
- wiederkehrender allgemeiner wöchentlicher Markt-Scan und unveränderbare Prognose-Snapshots als zweiter Prioritätsblock
- allgemeines Prognose-Tracking und allgemeine Kalibrierung
- Trading-Modus
- Trade Journal
- Performance Tracking
- Confidence-System
- Signalanalyse
- Trefferquote
- Kalibrierung
- Lernmodul
- Decision-Tracking
- Investment Opportunities erst nach den beiden Hauptprioritätsblöcken

Diese Aufgaben dürfen vorgezogen werden, wenn sie die Analysequalität messbar verbessern oder sichtbar machen, welche Module falsche Signale liefern. Wenn genügend historische Daten vorhanden sind, dürfen Lernsystem und Kalibrierung vor neuen Komfortfunktionen bearbeitet werden.

### PRIO C: Architektur und Wartbarkeit

- Refactoring
- Modularisierung
- Performance
- Dokumentation
- Testbarkeit

Diese Aufgaben dürfen vorgezogen werden, wenn sie mehrere spätere Aufgaben erleichtern, Risiken senken oder Tests zuverlässiger machen.

### PRIO D: Komfortfunktionen

Niedrigste Priorität:

- Suchkomfort
- Favoriten
- allgemeine Komfort-Watchlists außerhalb der verbindlichen Investment-Watchlist
- Exporte
- UI-Verschönerungen
- sonstige Komfortfunktionen

Diese Aufgaben dürfen niemals vor Analysequalität bearbeitet werden.

### Selbstständige Prioritätsentscheidung

Wenn der Nutzer `Arbeite weiter`, `Weiter`, `Setze die Entwicklung fort` oder `Arbeite bis zum Limit` schreibt:

1. `ROADMAP.md` lesen.
2. Den ersten noch nicht abgeschlossenen Hauptblock bestimmen: SwingTrading-Bot einschließlich seiner Datensammlung und zulässigen Validierungsstufe, danach allgemeiner Wochen-/Prognosebetrieb, danach übrige Produktarbeit.
3. Die offenen Aufgaben dieses Blocks analysieren.
4. Geschätzten Nutzen für Analysequalität und Datenqualität bewerten.
5. Geschätzten Nutzen für Stabilität und Messbarkeit bewerten.
6. Geschätzten Nutzen für Lernfähigkeit bewerten.
7. Daraus innerhalb des aktiven Blocks die aktuelle Priorität ableiten und bearbeiten.
8. Nur einen kritischen blockübergreifenden Fehler vorziehen und danach zum aktiven Hauptblock zurückkehren.

Nicht automatisch die erste Einzelaufgabe der Liste wählen, aber die verbindliche Reihenfolge der Hauptblöcke einhalten.

### Lernmodul und Prioritäten

Wenn Forward-Testing oder Prognose-Tracking zeigt, dass bestimmte Signalarten schlecht funktionieren, bestimmte Module wenig Nutzen liefern oder bestimmte Fehler häufig auftreten, dürfen passende Verbesserungen höher priorisiert werden.

Solche Verbesserungen werden während Prioritätsblock 1 direkt bearbeitet, wenn sie die Swing-Datengrundlage, Ausführungsrealität, Ergebnisqualität oder Sicherheit wesentlich beeinflussen. Datensammlung läuft dauerhaft als Teil des SwingTrading-Bots weiter; mehr Daten führen nur dann zu einer Strategieänderung, wenn eine neue versionierte Variante den vollständigen Forschungs-, Validierungs- und Freigabepfad erfolgreich durchläuft.

Beispiele:

- Häufige Fehlprognosen durch schlechte Marktphasen-Erkennung -> Marktphasen-Modul priorisieren.
- Häufige Fehlprognosen durch schlechte Krypto-Bewertung -> Krypto-Modul priorisieren.
- Häufig falsche News-Impulse -> News-Modul und Sentiment-Qualität priorisieren.
- Niedriger Vertrauensscore wegen Datenlücken -> Datenqualität und Fehlerbehandlung priorisieren.

### Keine Blackbox

Wenn Prioritäten angepasst werden, muss im Änderungsprotokoll dokumentiert werden:

- ursprüngliche Priorität
- neue Priorität
- Begründung

Damit jederzeit nachvollziehbar bleibt, warum eine Aufgabe vorgezogen wurde.

Ziel ist nicht, möglichst viele Features zu bauen. Ziel ist, die tatsächliche Qualität der Investment-Analysen langfristig zu maximieren. Die Verbesserung der Grundfähigkeit des Bots hat immer Vorrang vor Komfortfunktionen.

Wenn eine Aufgabe unklar ist:

1. `ROADMAP.md` analysieren.
2. Teilaufgaben erzeugen.
3. Teilaufgaben priorisieren.
4. Schrittweise umsetzen.
5. Nicht auf weitere Anweisungen warten, sofern keine riskante Produktentscheidung nötig ist.

## Versionskontrolle und optionale GitHub-Synchronisation

Nach jeder erfolgreichen Arbeitseinheit:

1. `git status` prüfen.
2. Geänderte Dateien identifizieren.
3. Fremde, private und nicht zum Auftrag gehörende Änderungen unangetastet lassen.
4. Ohne ausdrücklichen Auftrag nichts stagen, committen oder pushen.
5. Nur bei ausdrücklichem Auftrag den vereinbarten Umfang stagen, erneut prüfen und anschließend Commit beziehungsweise Push ausführen.

Wenn ein ausdrücklich beauftragter `git push` fehlschlägt:

- Fehler im Abschlussbericht dokumentieren.
- Nutzer informieren.
- Änderungen lokal behalten.
- Keine funktionierenden lokalen Änderungen verwerfen.

Vor einem ausdrücklich beauftragten Commit prüfen:

- Keine geheimen Schlüssel oder Zugangsdaten committen.
- `portfolio.json` darf nur im erlaubten Minimalformat committed werden: Cash, Ticker, Asset-Typ, Positionsgröße und Kaufkurs.
- Keine Kontonummern, Depotnummern, Broker-Zugangsdaten, API-Keys, Passwörter, Namen, Adressen oder persönlichen Identifikationsdaten committen.
- Keine Suchhistorien-Daten committen.
- Keine bewusst kaputten Zwischenstände committen.
- Keine automatisch generierten Dateien committen, wenn sie nicht sinnvoll zum Projekt gehören.

## Rollback-System

Vor größeren Änderungen:

1. `git status` prüfen.
2. Bestehende fremde und nutzerseitige Änderungen identifizieren und schützen.
3. Den stabilen Ausgangsstand mit passenden Tests dokumentieren.
4. Einen Sicherheits-Commit nur nach ausdrücklichem Auftrag erstellen.
5. Danach erst größere Refactorings oder Modulumbauten beginnen.

Bei schwerem Fehler:

- Ursache dokumentieren.
- Wenn möglich, den Fehler vorwärts beheben.
- Nur wenn der Stand nicht sinnvoll reparierbar ist, auf den letzten funktionierenden Stand zurückgehen.
- Nie absichtlich funktionierenden Code zerstören.
- Nie fremde oder nutzerseitige Änderungen verwerfen, ohne dass der Nutzer es ausdrücklich verlangt.

## Autonome Architekturpflege

Wenn während der Arbeit sichtbar wird, dass eine kleine strukturelle Vorarbeit den aktiven Hauptblock sicherer oder einfacher macht, darf diese Vorarbeit innerhalb dieses Blocks vorgezogen werden. Eine allgemeine Architekturverbesserung ohne unmittelbaren Nutzen für Wochen-/Forward-Betrieb oder anschließend Swing verschiebt die beiden Hauptprioritäten nicht.

Erlaubt sind:

- kleine Extraktionen von Hilfsfunktionen,
- bessere Trennung von UI, Datenbeschaffung und Bewertung,
- klarere Datenstrukturen für Research-Module,
- robustere Fehlerbehandlung,
- bessere Dokumentation,
- Aufräumen doppelter oder widersprüchlicher Anzeige-Logik.

Nicht erlaubt sind:

- vollständiger Neubau der App ohne ausdrückliche Anweisung,
- Entfernen vorhandener Funktionen ohne Ersatz,
- automatische Kauf- oder Verkaufsfunktionen vor bestandenem Echtgeld-Gate beziehungsweise außerhalb einer ausdrücklich freigegebenen Live-Bot-Phase,
- Broker-Anbindung vor bestandenem Echtgeld-Gate beziehungsweise außerhalb einer ausdrücklich freigegebenen Live-Bot-Phase,
- erfundene Daten oder versteckte Annahmen.

## Wachsende ROADMAP

Wenn während der Entwicklung neue sinnvolle Aufgaben entdeckt werden, dürfen und sollen sie in die ROADMAP aufgenommen werden.

Für jede neu entdeckte Aufgabe dokumentieren:

- kurze Beschreibung
- vermuteter Nutzen
- Zuordnung zu Hauptblock 1, Hauptblock 2 oder späterer Produktarbeit sowie ergänzend zu PRIO A, PRIO B, PRIO C oder PRIO D
- Begründung der Priorität
- mögliche Abhängigkeiten zu bestehenden Aufgaben

Neue Aufgaben dürfen die ROADMAP erweitern. Sie dürfen aber nicht automatisch Komfortfunktionen vor Analysequalität schieben. Wenn eine neu entdeckte Aufgabe wichtiger ist als die bisherige Reihenfolge, muss die Prioritätsänderung im Änderungsprotokoll begründet werden.

## Teststrategie

Nach relevanten Änderungen mindestens:

- `python -m py_compile app.py`
- Streamlit-Starttest, wenn möglich
- Analyse-Test mit `BTC-EUR`
- Analyse-Test mit `NVDA`
- Analyse-Test mit `Xiaomi`

Wenn externe Daten wegen Netzwerk oder Yahoo Finance nicht verfügbar sind:

- Fehler sauber anzeigen.
- Keine falschen Daten erzeugen.
- ROADMAP oder Abschlussbericht entsprechend notieren.

Wenn ein Test wegen Netzwerk, Yahoo Finance, GitHub-Authentifizierung oder Nutzungslimit nicht möglich ist:

- Test als nicht ausgeführt dokumentieren.
- Grund nennen.
- Keine Testergebnisse behaupten.

## Änderungsprotokoll

### 2026-08-22

- Vorbereitenden Short-Readiness-Layer in den noch nicht real gestarteten Broad-Research-Pass integriert. Bearishe Abwärtsimpuls-/Rally-, Bestätigungs-, Marktstruktur-, EMA- und Fibonacci-Merkmale werden Point-in-Time gemeinsam mit den vorhandenen Long-Features erzeugt, aber weder ausgewertet noch als Signal oder Challenger verwendet. Die Labelseite speichert richtungsneutrale Rohbewegungen für 5/10/20/25 Sitzungen; Short-Ausführungsdaten werden nicht erfunden.
- Broad-Feature-Schema auf `swing-broad-pit-features-short-readiness-2026.08.22-v2`, Label-Schema auf `swing-broad-direction-neutral-labels-2026.08.22-v2` und den leeren Broad-Speichervertrag nicht löschend auf Schema 3 erweitert. Aktueller Code-Fingerprint `b7020db164445369b39cbbef619f965d71b8012b325439dc2fab79bc2e6f8811`, Feature-Vertragsfingerprint `46acb6e82b0feaaf0809b4b665944e1171189025e97d842cbcf846fa31de2e5e`; Frozen-Dataset-Fingerprint unverändert `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`.
- Explizite Short-Kandidaten werden von gemeinsamer Risk Engine sowie Paper-/Shadow-Pfaden fail-closed abgewiesen. Long-v1-Strategie, Kandidatenauswahl, Stops, Ziele, Kosten, Kampagnenqueue und bestehende Evidenz blieben unverändert. Relevanter Kampagnenstand lesend 243/248; Broad-Vollpass weiterhin gesperrt und produktiver Broad-Speicher weiterhin ohne Kandidaten.
- Forward-Statusbericht auf alle abgeschlossenen echten Paper-Trades einschließlich künftiger Gewinner erweitert. Garantierte Tradefelder, Median- und vier MFE-Schwellen, Zeit bis MFE/Exit, konkrete Slippage, Signalzustände, sachliche A–G-Begründung, deskriptive Setup-/Regimesegmente und strikt getrennte 5-/20-Sitzungs-Counterfactuals werden als JSON und direkt kopierbarer Markdown-Block ausgegeben. Aktuell: 0 Gewinne/14 Verluste, Ø -1,0867 R, PF 0, Drawdown 15,2143 R, Ø MFE 0,6676 R, Median 0,6187 R, Ø MAE -1,0444 R; 8/4/1/1 Trades erreichten mindestens 0,5/1/1,5/2 R. Vollständige 5-/20-Sitzungsfenster sind noch für keinen Trade vorhanden und bleiben `n/v`. Keine Forward-Evidenz oder Strategie wurde verändert.
- Pflichtfelder und PROJECT_STATUS-Block durch Regressionstests gegen versehentliches Entfernen geschützt. 45/45 gezielte Diagnose-/Forward-Tests und 556/556 Gesamttests erfolgreich; `compileall`, Repository-Sicherheitscheck und Git-Diff-Prüfung bestanden. Forward-SQLite vor/nach JSON- und Markdown-Bericht byteidentisch mit SHA-256 `455F55F3FB8676BE8C123E22CE559CA6DA2948078D12E317914ED996139E543A`.
- Automatischen fail-closed Übergang nach 248/248 ergänzt: vollständiger Walk-Forward-/Fingerprint-Audit, identischer finalisierter Frozen-Datensatz, append-only Übergangsnachweis und höchstens 16 Assets je sicherem Resume-Block. Bei aktuell 243/248 bleibt Broad mit 0 Kandidaten gesperrt; die alte Queue und Evidenz wurden nicht verändert oder neu gestartet.
- Development-Bericht um ungefilterte Basis, Expectancy, Tradeverlust/-retention und kleine feste RSI-/EMA-/BOS-Nachbarschaften ergänzt. Manueller C-Freeze und Ground-up-Handoff Validation → Holdout → External → True Forward sind technisch sequenziell gesperrt; keine automatische Stufenentscheidung oder Produktion.
- External-Resultate bis zum manuell bestandenen Holdout derselben festen Challenger-Version technisch gesperrt; ohne diesen Gate-Nachweis ist ausschließlich die outcome-blinde Infrastrukturprüfung möglich.
- Aktueller Broad-Code-Fingerprint `a1fb7490b377500d55a10ae08b9b5056fffc4493fb6adaa183b91ba603198b67`, Feature-Vertragsfingerprint `b2705b847881f5c70e16539fb1de51065d35e7c250bf6c0c79313cf2b2f3496f`; Frozen-Dataset-Fingerprint unverändert `e2310023e5c83fc19ce8316b55514e9694c882e546277487ed75319e560be1ed`.
- Abschließende vollständige Regression 547/547 in 82,24 Sekunden, 24 gezielte Diagnose-/Broad-/Transition-/Challenger-/External-Gate-Tests, Python-Kompilierung, App-Import und headless Streamlit-Start erfolgreich. Kein Commit und kein Push.
- Rein lesendes Modul `swing_edge_diagnostics.py` für die priorisierte Verlust-/Edge-Diagnose ergänzt. Es berechnet aus bereits gespeicherter Evidenz R-, MFE-/MAE-, Drawdown-, Profitfaktor-, Gap-, Verlustserien- und Segmentkennzahlen, trennt Diagnosekandidaten und kann weder Baseline noch Produktionsregeln verändern. Zeitlich nicht beweisbare Intrabar-Reihenfolgen und nicht gespeicherte ATR-/Sitzungs-/Sektorwerte bleiben sichtbar unbekannt.
- Technischen ML-Datenvertrag `swing_ml_dataset_contract.py` ergänzt: Features und spätere Labels sind getrennte Bereiche, externe Quellen benötigen einen Point-in-Time-gültigen Verfügbarkeitszeitpunkt, Zielvariablen im Featurebereich werden abgelehnt, fehlende Werte bleiben erhalten und Zeilen sowie Dataset-Manifest sind reproduzierbar fingerprintet. Der Vertrag ist strikt Shadow-only und kann weder Modelltraining noch Trades, Regeln oder Produktion auslösen.
- Sieben gezielte Diagnose-/Dataset-Vertragstests sowie die vollständige Regression mit 526/526 Tests bestanden. Python-Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Streamlit-Start und Git-Diff-Prüfung waren ebenfalls erfolgreich. Die produktive historische Forschungsdatenbank wurde für diese Entwicklungseinheit nicht geladen oder verändert; kein Commit und kein Push.
- Strategie-Freeze technisch umgesetzt: neun getrennte append-only Artefakte für unveränderte Long-v1-Baseline und acht vorab festgelegte RSI-, EMA20/EMA50-, EMA+RSI- sowie Pullback-/Breakout-Challenger. Vollständige Fachverträge und reproduzierbare Code-/Konfigurations-/Datenfingerabdrücke werden gespeichert; Performancefreigabe und automatische Produktionsaktivierung bleiben verboten.
- Die Long-v1-Baseline bleibt unverändert. Technische Challenger laufen ausschließlich als getrennte Forschungsstrategien mit kausalen Indikatoren, identischen Kosten-, Purging-, Development-/Validation-/Holdout-Regeln und sichtbaren Kennzahlen für R/Expectancy, Profitfaktor, Drawdown, Trefferquote, Fallzahl, Verlustserien, Markt-/Volatilitätsregime, zeitliche Stabilität und Parameterrobustheit. Kein Challenger ersetzt die Produktion.
- Laufende historische Kampagne sicher fortgesetzt: 226/248 Jobs abgeschlossen (91,13 %), 22 offen; Runde A vollständig, Runde B 74/80 und Runde C 64/80. Forschungsdatenbank mit 5.507 Läufen und 392.273 Fällen geprüft: SQLite-Quick-Check `ok`, null ungültige Einträge. Bestehende Baseline, Kampagne, Fälle und Forward-Historien wurden nicht überschrieben oder zurückgesetzt.
- Gemeinsame Bot-Architektur ergänzt: Strategie, unabhängige Risk Engine, Ausführungssimulation, Positionsverwaltung und Audit sind modular getrennt. Scanner, autonomer Paper-Bot und Shadow-Live nutzen denselben versionierten Risiko-/Orderpfad; nur `analysis_only`, `paper_only` und `shadow_only` sind erlaubt. Brokeradapter, Orderübertragung und Echtgeldpfad existieren nicht.
- Autonomen Paper-Bot in den regionalen Hintergrundbetrieb integriert: vollständiger kausaler Zyklus von Signal und Risk Check über virtuelle Order, Fill/kein Fill, Position, Stop, Ziele, Teilverkauf und Exit; append-only, idempotent, restartfähig und bei Datenfehlern fail-closed. Walk-Forward-, echtes Forward-, autonomes Paper-, Shadow- und Nutzertrade-Evidenz bleiben getrennt.
- Shadow-Live-Grundlage umgesetzt: reale aktuelle Signale erzeugen exakt den brokerlosen Orderentwurf mit Listing, Zeitstempel, Datenquelle, Risk-Entscheidung und Positionszustand. Bid/Ask, Spread, Slippage, Gaps und Ausführbarkeit werden nur bei echter Quelle gespeichert; fehlende Ausführungsdaten werden nicht geschätzt.
- Streamlit-Start gegen den gemeldeten `refresh_swing_walk_forward_forward_links`-Importfehler abgesichert und die sehr große historische Detailaggregation auf explizites Laden verschoben. Modulimport, App-Import und lokaler Streamlit-Start sind wieder erfolgreich.
- Vollständige Regression 519/519 erfolgreich; zusätzlich Python-Kompilierung, Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Streamlit-Start bestanden. Keine bestehende Kampagne, Baseline, Forward-/Paper-Historie oder Produktionsregel zurückgesetzt beziehungsweise überschrieben; kein Commit und kein Push.
- Verbindliche quantitative Research-Pipeline für alle neuen Swing-Strategien, Indikatoren, externen Daten, Videos, Marktthesen und späteren ML-Ideen ergänzt. Baseline, Versuchszähler, Point-in-Time-Vertrag, zeitliche Datentrennung, Multiple-Testing-/Overfitting-Schutz, Kosten, Einfachheitsprinzip, Misserfolgsrecht und Kill-Regel festgeschrieben.
- Einheitliche A/B/C-Entscheidung je getesteter Hypothese aufgenommen: A verwerfen, B nur weiterforschen, C lediglich Kandidat für eine neue gezielte Strategieversion mit anschließender Forward-/Shadow-/Paper-Validierung. Keine automatische Regelübernahme.
- Regelbasierten Pullback-/Trendfortsetzungstest geplant: Impuls, kontinuierliche Pullback-Tiefe, Dauer, bearish Kerzen/Serien, ATR-normalisierte Geschwindigkeit, Käuferbestätigung `Close[t] > High[t-1]`, Forward Returns und MFE/MAE. TikTok-Regel `drei bearish Kerzen = kein Trade` bleibt nur Hypothese.
- Wenige Stop-/Exit-Varianten vorab begrenzt: Pullback-Low, ATR-Puffer, ATR-Stop, bestehende Strukturregel sowie 1R/1,5R/2R/3R, Trendexit, Break-even und Teilgewinn. Entry nach Bestätigung frühestens in der folgenden handelbaren Sitzung; Kosten und Slippage verpflichtend.
- Fibonacci-Vergleich in denselben kontinuierlichen Pullback-Datensatz integriert: 0,618 sowie 61,8–78,6 Prozent gegen ähnlich breite Nicht-Fibonacci-Zonen. Keine Suche nach weiteren Leveln bei Misserfolg; Extensions -0,27/-0,62/-1 nur als späterer separater Exit-Test nach positivem Ergebnis.
- Weitere Framework-Bausteine einzeln eingeordnet: Saisonalität, objektive Daily-/Weekly-/Monthly-/Quarterly-/Yearly-Opens, Fixed Range Volume Profile mit POC/VAH/VAL, algorithmischer Break of Structure und Trade-Management. Confluence und Gesamtmodell `Bias → Zone → Bestätigung → Entry → Risiko → Exit` bleiben bis zur unabhängigen Evidenz der Einzelteile gesperrt.
- ML-tauglichen Point-in-Time-Datenvertrag und späteren Shadow-ML-Pfad geplant. RSI/EMA, Pullback, Volumen, ATR/Volatilität, Marktregime, Surprise-/Expectation-Features und strikt getrennte Labels werden wiederverwendbar gespeichert; kein Random-Split und kein aktiver Tradingeinfluss ohne vollständige ungesehene sowie Forward-/Paper-Bestätigung.
- Bestehenden COT-Shadow-Punkt ohne Duplikat ergänzt: Net Position relativ zum Open Interest, 52-Wochen-Normalisierung, Extrem-Umkehr, Teilnehmer-Spreads, 5/10/20-Tage-Ziele und begrenzter Vergleich alternativer Normalisierungen. COT bleibt Research-/Regime-Feature.
- Reine Roadmap-Änderung. Keine Strategie, kein Filter, kein RSI-/EMA-Grenzwert, kein Stop, kein Target, keine Produktionsfreigabe und keine bestehende Historie verändert. Kein Commit und kein Push.
- Getrennten breiten Frozen-Research-Pfad umgesetzt: outcome-unabhängige objektive Pullback-/Breakout-Kandidaten, gemeinsame kausale Featureberechnung, strikt spätere Labels, konservative Stop-/Exit-Kontrafakten, append-only SQLite, serielle Persistenz, Resume/Prozess-Pool und Baseline-Verknüpfung ohne Auswahlwirkung. Code-Fingerprint `1c70ed5458a8554ca81bbeebfd5d9fc57afc611de55b85fca2b7b6fed8d52774`, Feature-Vertragsfingerprint `a14cfda4b1c6669e4af51b3699859f780573266e10005b4de306d24449f9aa67`.
- G2.1/G2.2/G2.3 technisch umgesetzt: Impuls/Pullback, bestehende RSI-/EMA-/ATR-/Volumen-/Regimelogik, Fibonacci samt Kontrollzonen, bestätigte Swing-/BOS-Struktur, fünf Opening-Level, Point-in-Time-Saisonalität, Point-in-Time-COT mit 52-Wochen-Kontext sowie konservative Trade-Management-Experimente. Daily-OHLCV wird nicht zu POC/VAH/VAL umgedeutet; Confluence und Extensions bleiben gesperrt.
- Development-Musterprüfung auf acht vorab begrenzte Hypothesen umgestellt. Sie streamt auch einen großen Bestand speicherschonend, protokolliert Fallzahl, effektive Unabhängigkeit, R, Profitfaktor, Trefferquote, Drawdown, Verlustserien, MFE/MAE, Asset/Region/Setup/Regime und Zeitstabilität append-only und öffnet weder Validation noch Holdout. C ist nur ein manueller Freeze-Kandidat, nie Produktionsfreigabe.
- `External Unseen Asset Universe` als verbindliches zusätzliches Gate und append-only technischer Auswahl-/Freeze-/Ergebnisvertrag ergänzt. Ursprüngliche Ticker, Emittenten und wirtschaftlich identische Instrumente sind ausgeschlossen; ein echtes externes Universum und Ergebnisse existieren noch nicht.
- Bestehende Kampagne unverändert bei 238/248 (A 80/80, B 80/80, C 70/80) geprüft: 5.792 Läufe, 397.764 Fälle, SQLite `ok` und 0 ungültige Fingerabdrücke. Der neue Runner verweigert den Start bis 248/248; separater Broad-Speicher Integrität `ok`, 0 Kandidaten, External-Speicher Integrität `ok`, 0 Manifeste/Ergebnisse. Vollständige Regression 538/538 und 26 gezielte Research-/External-/ML-/COT-Tests erfolgreich. Kein ML-Training, keine Regel-/Produktionsänderung, kein Commit und kein Push.

### 2026-08-19

- Wiederkehrenden Stillstand der historischen Kampagne bei Legacy-Shards auf einen Fingerprintfehler eingegrenzt: Manifest, Frozen-Parquet und lokaler Cache enthielten dieselben Kurszeilen und Werte; ausschließlich die verlustfreie Parquet-Darstellung des DatetimeIndex wechselte zwischen Sekunden und Millisekunden. Dies war keine Kurskorrektur und keine Dataset-Beschädigung.
- Research-Historienfingerprint für neue Daten auf Nanosekunden kanonisiert und die bestehende finalisierte V1-Epoch abwärtskompatibel gemacht. Beim Laden werden ausschließlich die vier verlustfreien Datetime-Auflösungen `s/ms/us/ns` als äquivalent akzeptiert; OHLCV-Werte, Zeilen, Ticker, Spaltendtypen und Manifestvertrag müssen weiterhin exakt übereinstimmen. Manifest, Dataset-Fingerprint und eingefrorene Dateien werden dabei nicht verändert.
- Automatischer Resume real belegt: Der vor dem Fix um 11:50 Uhr gestartete Retry scheiterte noch mit dem alten Prozessstand; der reguläre 11:55-Uhr-Trigger lud anschließend den unveränderten Frozen-Datensatz erfolgreich, startete den kontrollierten Sechs-Prozess-Pool und setzte denselben offenen Legacy-Shard ohne manuellen Queue-Eingriff fort. Echte Wertänderungen bleiben fail-closed; bereits +0,01 im Schlusskurs wird im Regressionstest abgelehnt.
- Sichere automatische Dateiwiederherstellung ergänzt: Eine fehlende, unlesbare oder inhaltlich abweichende Frozen-Parquet-Datei darf nur aus dem lokalen Kampagnencache ersetzt werden, wenn dessen vollständiger OHLCV-Fingerprint mit dem unveränderten Manifestvertrag kompatibel ist. Vor dem atomaren Ersatz wird die defekte Originaldatei deterministisch unter `.recovery` gesichert; Providerzugriff, Manifeständerung und stille Datenrevision bleiben ausgeschlossen. Fehlt ein exakter Cachebeleg, bricht der Job weiterhin fail-closed ab und wird durch den vorhandenen Scheduler später erneut versucht.
- Gezielte Dataset-/Walk-Forward-/Campaign-Prüfung 46/46 und vollständige Regression 519/519 bestanden. Keine Strategie, Fallauswahl, Queue, Research-Epoch, Datenbank, Forward-Logik oder Produktionsregel verändert.

### 2026-08-18

- COT-/Positionierungsdaten als priorisierte Swing-Shadow-Phase G1 mit Point-in-Time-, Mapping-, Teilnehmerklassen-, Vergleichs- und Freigaberegeln aufgenommen.
- Neue getrennte Grundlage `cot_positioning.py`: offizielle CFTC-Datensätze TFF Futures Only und Disaggregated Futures Only, sichere HTTPS-Prüfung, API-Paginierung, Normalisierung der originalen CFTC-Klassen, Net Position, Open Interest, 1W/4W, historische Perzentile/Z-Scores und klassenbezogene Divergenzen.
- Historische Leakage-Sperre umgesetzt: Rückfülldaten ohne verifizierten Veröffentlichungszeitpunkt sind für damalige Entscheidungen gesperrt; aktuelle Abrufe gelten frühestens ab ihrem echten Erstabruf. Korrekturen erzeugen neue Inhaltsrevisionen.
- Explizites Mapping in `config/cot_market_mapping.json` ergänzt. US-/Europa-Einzelaktien erhalten nur breiten Markt-Kontext, nie eine emittentenspezifische COT-Behauptung; unbekannte oder mehrdeutige Zuordnungen bleiben gesperrt.
- Append-only COT-Speicher, getrennte Shadow-Verknüpfungen und Vergleich bestehende Strategie gegen den deklarierten Kontrafaktualfall `Widersprüche ausschließen` anhand Trefferquote, R, Profitfaktor, Drawdown, MFE und MAE umgesetzt. Keine Produktionswirkung und keine automatische Regel-/Gewichtsänderung.
- Offiziellen Bestand ab 2023 geladen: 60.859 Beobachtungen, Datenbankintegrität `ok`, 0 produktive Verknüpfungen, 0 rückwirkend als historisch verfügbar behauptete Zeilen.
- Zehn gezielte COT-Tests sowie Kompilierung erfolgreich. Kein Commit und kein Push.
- Dokumentierten Walk-Forward-Identitätsabbruch ursächlich geklärt: Ein älterer Pilotfall und eine später um Forschungsmetadaten erweiterte Fallstruktur teilten dieselbe logische `case_id`, besaßen aber unterschiedliche vollständige Fall-Fingerabdrücke. Der Append-only-Schutz verhinderte jede Änderung, der reine Versionssprung beseitigte jedoch nicht den allgemeinen Retry-Fehlerpfad.
- Allgemeine append-only Konfliktrevision in Walk-Forward-Schema 3 umgesetzt. Bei valider `case_id`-/Fingerprint-Kollision bleiben bestehende Fälle unverändert; der neue Inhalt erhält deterministisch eine eigene Revisions-ID und eine separate unveränderbare Konfliktspur. Derselbe Retry/Resume ist idempotent und kann einen Kampagnenjob nicht dauerhaft an derselben Fallkollision festhalten.
- Unternehmens- und Listingidentität für die Swing-Forschung getrennt: Neue Fälle speichern Listing-, Issuer-/Company-, ISIN-/Instrument-, Anteilsklassen- und Depositary-Receipt-Kontext. Explizite Identitäten werden bevorzugt; allgemeine Namensnormalisierung deckt unter anderem LLYVA/LLYVK, ADR/Stammaktie und Mehrfachlistings ab. Legacy-Fälle werden nicht umgeschrieben, sondern bei der Auswertung konservativ aus dem Universum ergänzt.
- Abhängige Evidenz statistisch ergänzt: Einzeltrades und rohe Trefferquote/R/Profitfaktor/Drawdown bleiben unverändert. Überlappende Ergebnisfenster desselben Emittenten oder wirtschaftlich identischen Instruments bilden für Unsicherheit, Robustheit, Mindestfälle, Segmentabdeckung, Validation/Holdout und Pareto-Reife gemeinsame Evidenzcluster. UI, Zusammenfassung und Archiv zeigen rohe und effektiv unabhängige Fallzahl sowie Issuer-/Listingcluster getrennt.
- Reparaturpfad isoliert gegen eine Alt-/Neu-Kollision und sofortigen Resume geprüft: erster Lauf genau eine append-only Revision und ein Konfliktprotokoll, zweiter Lauf null Doppelungen, alter Datensatz bytegleich, Audit `ok`. Der reale Problemshard blieb während eines bereits aktiven anderen Kampagnenshards unverändert in der atomaren Queue und wurde nicht parallel erzwungen.
- Fünf neue Datenqualitätsfälle und vollständige Testsuite 497/497 erfolgreich. Keine Strategieparameter, Entry-/Exit-Regeln, Stops, Targets, RSI/EMA, Produktionslogik, Broker- oder Echtgeldfunktion verändert.
- Rein beobachtenden RSI-/EMA-Research-Layer ergänzt. Für neue historische Fälle werden RSI14, EMA20, EMA50, Kurs/EMA20, Kurs/EMA50, EMA20/EMA50, normalisierte Abstände und die zugehörigen Lagebeziehungen aus dem bereits vorhandenen kausalen Indikatorpass als eigener versionierter Sidecar gespeichert. Der Baseline-Fallpayload einschließlich Fall-ID, Fingerabdruck, Auswahl, Tradeplan und Ergebnis bleibt bytegleich; bereits gespeicherte oder beim Rollout schon laufende Fälle werden nicht rückwirkend aufgefüllt und bleiben sichtbar `legacy_feature_not_recorded`.
- Die append-only Featuretabelle ist eine additive, mit dem bereits laufenden Schema-3-Prozess kompatible Erweiterung und wird ausschließlich zusammen mit tatsächlich neu eingefügten Fällen durch den seriellen Hauptprozess beschrieben. Resume eines bestehenden Falls erzeugt weder ein Feature noch ein Duplikat. Eingefrorener Datensatz, Cache, Providerzugriff, Worker-Pool, Kampagnenqueue und 248 Jobidentitäten bleiben unverändert.
- Beobachtende Auswertung nach festen RSI-Bereichen, EMA20/EMA50-Lage, Kurslage zu beiden EMAs, vollständigem Kurs-/EMA-Stack sowie den Kreuzungen mit Pullback/Breakout, Marktphase und Volatilitätsregime umgesetzt. Jedes Segment weist Fälle, Durchschnitts-R, Profitfaktor, Trefferquote und maximalen Drawdown insgesamt sowie getrennt für Development, Validation und Holdout aus; unter 50 effektiv unabhängigen Ergebnissen bleibt es als kleine Stichprobe markiert.
- Keine Schwellenwertsuche, automatische Regelableitung oder Holdout-Auswahl ergänzt. Ein späterer manuell gewählter Challenger benötigt weiterhin eine vorab eingefrorene RSI-/EMA-Regel, eigenen Strategie-Fingerprint, neue hypothetische Trades, getrennte Speicherung und eine neue Research-Epoch beziehungsweise frische Walk-Forward-Prüfung. Die aktuellen Beobachtungen gelten dafür ausdrücklich nicht als Bestätigungsevidenz.

### 2026-08-17

- Höchste Gesamtpriorität auf ausdrücklichen Nutzerwunsch festgelegt: Den SwingTrading-Bot fertigstellen und evidenzbasiert verbessern. Dazu gehören alle Swing-spezifischen Daten-, Forschungs-, Walk-Forward-, Forward-/Paper-, späteren autonomen Paper-, Shadow-Live-, Sicherheits- und Freigabestufen bis zum langfristigen kontrollierten Zielbetrieb.
- Frühere Reihenfolge `allgemeiner Wochen-/Prognosebetrieb vor Swing` aufgehoben. Der allgemeine Prognosebetrieb läuft als zweiter Block zuverlässig weiter, darf die Bot-Fertigstellung aber nicht mehr verdrängen. Kritische Stabilitäts-, Datenschutz-, Datenintegritäts- und Falschergebnisfehler bleiben sofortige Ausnahmen.
- Datensammlung ausdrücklich als Teil der Bot-Entwicklung eingeordnet: Mehr saubere Point-in-Time-Fälle ermöglichen Messung, Training und Vergleich, erhöhen die Genauigkeit jedoch nicht automatisch. Strategieänderungen benötigen weiterhin versionierte ungesehene Validierung und das passende Gate; kein selbstständiges Nachregeln anhand einzelner Trades.
- Swing-Endziel erweitert: Nach erfolgreicher bestehender Validierung führt der verbindliche Langfristpfad über Strategie-Freeze, autonomen Paper-Bot, Shadow-Live und ein ausdrücklich zu bestehendes Echtgeld-Gate zu einem zunächst begrenzten autonomen Live-Bot und erst danach zu kontrollierter Skalierung.
- Die bisher absolute Handelssperre für den aktuellen und zukünftigen Plan präzisiert, ohne historische Statusangaben umzuschreiben: Bis zum bestandenen Echtgeld-Gate bleiben Broker-Anbindung und automatische Orderausführung strikt gesperrt; auch danach entsteht keine automatische Freigabe, sondern nur die Möglichkeit einer getrennten ausdrücklich beauftragten Live-Phase.
- Wirtschaftliches Ziel als möglicher regelmäßiger monatlicher Zusatzverdienst ohne Renditegarantie dokumentiert. Maßstab ist robuster positiver Erwartungswert nach realistischen Kosten bei kontrolliertem Risiko, nicht maximaler Backtest-Gewinn oder erzwungener Monatsgewinn.
- Live-Sicherheitsarchitektur, separates Bot-Tradingkapital, unabhängige nicht übersteuerbare Risk Engine, Kill-Switch, Fail-closed-Verhalten, Order-/Positionsabgleich, Fehlerwiederaufnahme und append-only Audit als spätere Pflicht aufgenommen. KI und Lernlogik dürfen keine Live-Regeln, Risikolimits oder Produktionsparameter selbst ändern.
- Aktuelle Priorität unverändert gehalten: historische Swing-Walk-Forward-Tests und echte Forward-/Paper-Evidenz weiter aufbauen; jetzt keine Brokerintegration und keine Echtgeldfunktion entwickeln.
- Intelligente Einstiegs-Watchlist als priorisierte Erweiterung unter `Asset-Analyse` geplant. Minimale Eingaben sind Asset/Listing, Budget und persönliche Investmentthese; das System prüft die These kritisch, bewertet Attraktivität und eingepreistes Wachstum, leitet faire Bandbreite, Einstiegszone, Maximalpreis, Rally-Alternative, Tranchierung und klare Handlungsstufe ab.
- Automatische Pflege verbindlich beschrieben: tägliche günstige Technikprüfung, regelmäßige und ereignisgesteuerte vollständige Neubewertung, sichtbarer Datenstand sowie versionierte Ablösung veralteter oder unrealistischer Pläne. Keine rückwirkende Veränderung bestehender Analyse-, Forward-, Paper- oder Prognosedaten.
- Oberfläche auf fünf Kernfragen begrenzt; Details erst nach Klick. Probabilistische Rücksetzer-, Konsolidierungs- und Rally-Szenarien ersetzen falsche Zeitversprechen. Reife Unternehmen und spekulative Wachstums-/KI-Werte erhalten passend ausgewiesene Bewertungsmodelle.
- Hybridziel festgelegt: Python bleibt verbindlich für Zahlen, Bewertung, Technik, Zonen, Tranchierung und Risiko; KI darf nur belegte qualitative These-, Unternehmens-, News- und Gegenargumentanalyse liefern, keine Fakten oder Kurse erfinden und keine deterministischen Werte überschreiben. Keine Broker-Anbindung und keine automatische Orderausführung.
- Ersten vollständigen V3-Basislauf abgeschlossen: 2.518/2.520 Assets geladen, nur `CWEN-A` und `SVA` isoliert fehlgeschlagen, 21.179 neue Fälle gespeichert. Aktueller eindeutiger V3-Bestand: 21.299 Fälle, davon 11.158 mit R-Ergebnis, 18,63 % positive Abschlüsse, durchschnittlich +0,027 R, Profitfaktor 1,029 und maximaler sequenzieller Forschungs-Drawdown 814,05 R. Validation blieb mit -0,118 R negativ, Holdout lag bei +0,145 R; deshalb keine Freigabe oder Regeländerung. SQLite: 21.595 append-only Revisionen, Quick-Check `ok`, null ungültige Fingerabdrücke.
- V5-Forschungskampagne für schnellstmögliche saubere Datensammlung umgesetzt: zwölf vorab versionierte Forschungsvarianten werden in drei gemeinsamen Datenverträgen mit je vier Schwellenprofilen und acht diversifizierten Shards verarbeitet. Kursabruf und technische Indikatoren werden dadurch pro Asset/Zeitraum nur einmal statt viermal ausgeführt. Zwei nicht überlappende historische Epochen und wöchentliche jüngste vollständig gereifte Fälle bleiben vollständig enthalten. Ein neuer Abrufstichtag ändert die Evidenz-ID vorhandener Fälle nicht mehr; Samplingvarianten und Datenrevisionen werden append-only erhalten, aber in Kennzahlen nicht doppelt gewichtet.
- Historische Folgeevidenz als drei bereits vor Ergebnissichtung festgelegte Runden A/B/C umgesetzt. Pro Runde werden je Asset und Strategie höchstens sechs disjunkte Fälle aus 2010–2015 und sechs aus 2016 bis heute gespeichert, insgesamt somit höchstens zwölf pro Runde und 36 nach allen drei Runden. B ist technisch von der vollständigen A-Runde abhängig, C von der vollständigen B-Runde. Der Auswahlstrom verwendet weder spätere Rendite noch Stop-/Zielergebnis; frühere Rundensignale werden rekonstruiert, für das 25-Sitzungs-Purging reserviert und nicht erneut gespeichert. A bleibt Exploration, B gelockte Validierung und C finale Bestätigung; keine Runde aktiviert automatisch Produktionsregeln.
- Windows-Aufgabe `InvestmentAssistantSwingResearchCampaign` mit 45 täglichen 15-Minuten-Triggern von 11:05 bis 22:05 Uhr registriert. `IgnoreNew`, gemeinsame Forschungssperre, atomarer Resume-Status, Aufwecken, verspäteter Start und 90-Minuten-Laufgrenze sind aktiv. Schutzfenster 17:15–18:45 und 21:30–23:59 verhindern Konkurrenz zu Europa-Scan und Abendkette; zusätzlich startet in den jeweils 90 Minuten davor kein neuer Forschungsjob. Der erste V1-Pilotshard wurde am 2026-08-17 von 15:32 bis 15:52 Uhr erfolgreich abgeschlossen: 313 Historien geladen, nur `CWEN-A` und `SVA` isoliert fehlgeschlagen und 2.540 neue V4-Fälle append-only gespeichert. Anschließend wurde die inhaltlich gleiche Warteschlange ohne Datenverlust auf 24 gebündelte V2-Jobs verkürzt; bereits gespeicherte Current-Fälle werden durch ihre stabile Evidenz-ID nicht doppelt gezählt.
- Kampagnenlaufzeit weiter reduziert: Jeder Shard meldet nur seine eigenen Summen; der mit wachsender Datenbank teure globale Summary-/Integritätsscan läuft erst nach dem achten und damit letzten Shard eines Forschungsvertrags. Das fachliche Audit wird nicht entfernt, sondern gebündelt.
- Die vier Strategieprofile eines Zeit-/Samplingvertrags laufen jetzt im selben Assetdurchgang. Damit sinkt die Startwarteschlange von 96 auf 24 Jobs, während alle zwölf Strategie-/Zeitraumkombinationen erhalten bleiben.
- Gebündelten Vier-Profil-Pfad mit zwei echten Cache-Historien separat geprüft: 2/2 Assets geladen, null Fehler, 16 Fälle gespeichert, SQLite-Quick-Check `ok`. Der erste große V2-Job über 315 Assets wurde anschließend um 15:59 Uhr über die registrierte Windows-Aufgabe gestartet. Dabei deckte der append-only Schutz einen Versionskonflikt zwischen älteren V4-Pilotfällen und der erweiterten Fallstruktur auf und brach vor jeder Datenänderung sicher ab. Engine und Forschungsvertrag wurden auf V5/V4 angehoben; derselbe Alt-/Neu-Datenbankpfad speicherte danach 16/16 neue V5-Fälle fehlerfrei. Produktive Forschungsdatenbank weiterhin 128 Läufe, 24.135 Fälle, Quick-Check `ok`, null ungültige Datensätze.
- Append-only Brücke zwischen historischen und echten Forward-Fällen umgesetzt. Exakter Match verlangt denselben Ticker beziehungsweise kompatibles Listing, denselben abgeschlossenen Signaltag, Setup, Richtung und denselben normalisierten Ausführungsplan. Echte Forward-Evidenz erhält dann Vorrang und der historische `recent_incremental`-Fall wird nicht nochmals im aktuellen Monitoring gezählt. Andere Strategie oder anderer Plan bleibt sichtbar als `related_same_asset_day` und wird nicht fälschlich zusammengeführt.
- Brücke automatisch an beide Entstehungswege angeschlossen: Nach jedem historischen Kampagnen-Shard, jedem regionalen Hintergrundscan und jedem manuellen Scan werden neue unveränderbare Verweise ergänzt. Die Oberfläche zeigt exakte, verwandte und aus dem historischen Monitoring ausgeschlossene Doppelungen; keine Produktionsregel wird automatisch verändert.
- Walk-Forward-Datenbank vor Schemaänderung per SQLite-Online-Backup gesichert und nicht löschend von Schema 1 auf Schema 2 migriert. Vorher/Nachher: 128 Läufe und 24.135 Fallrevisionen mit identischen Fall-/Lauf-Fingerabdrucksummen, Quick-Check `ok`, null ungültige Datensätze. Aktuell 24.039 eindeutige historische Fälle und 19 echte Forward-Signale, aber erwartungsgemäß noch null gemeinsame Signaltage, weil die historische Reifekante im Juli und der echte Forward-Beginn im August liegt.
- Oberste Swing-Priorität präzisiert: Trefferquote und durchschnittliche Rendite werden gemeinsam untersucht; Profitfaktor, Drawdown, Kosten, Signalabdeckung und ungesehene Zeitfenster bleiben zwingende Schutzgrößen. Eine scheinbar hohe Trefferquote durch kleine Gewinne oder überangepasste Regeln ist kein Verbesserungsnachweis.
- Historischen Swing-Walk-Forward-Test zum breiten Forschungsbetrieb V3 ausgebaut. Ohne einzelne Tickerangabe verarbeitet die CLI das aktive 2.520-Asset-Universum in parallelen 100er-Datenbatches, isoliert Einzelfehler, speichert bereinigte Tageshistorien in einem lokalen Parquet-Cache und kann nach Unterbrechung ohne erneuten Vollabruf fortsetzen.
- Laufzeitpfad beschleunigt: technische Indikatoren werden pro Asset nur einmal kausal berechnet und anschließend über begrenzte reine Vergangenheitsfenster wiederverwendet. Der frühere globale 500-Fall-Abbruch ist durch bis zu 25.000 deterministisch über Strategie/Asset verteilte Fälle sowie ein konfiguriertes Maximum von zwölf nicht überlappenden Fällen je Asset ersetzt.
- Analysepfad zusätzlich auf vier getrennte Worker je 100er-Batch parallelisiert. Im Windows-Aufgabenkontext laufen sie als stabile Threads über disjunkte Assetgruppen; ein optionaler manueller Prozessmodus bleibt getrennt. Nur der Hauptpfad schreibt die append-only SQLite-Datenbank. Ein identischer Zehn-Asset-Wiederholungstest speicherte zuerst 120 und danach exakt null neue Fälle.
- Forschungsqualität gehärtet: feste chronologische Development-/Validation-/Holdout-Fenster, kalenderjahr- und splitbalancierte Fallauswahl je Asset, technisch erzwungenes letztes Signaldatum, Purging aller über eine Zeitgrenze ragenden Labels, Ausschluss überlappender 25-Sitzungs-Ergebnisfenster desselben Assets, vollständige OHLCV-Datenfingerabdrücke, split-/dividendenbereinigte Yahoo-Kurse und versionierte Schwellenprofile. Spätere Kursbalken bleiben bei der Signalerzeugung unsichtbar.
- V3-Fallidentität gegen nachträgliche Providerkorrekturen gehärtet: Eine logische Fall-ID bleibt über spätere neue Börsentage stabil; die konkrete append-only Fall-ID enthält zusätzlich den Fingerabdruck exakt der bis zum Ergebnis verwendeten Kursbalken. Korrigierte Historien bleiben als Revision erhalten, werden in Kennzahlen aber nicht doppelt gewichtet.
- OHLCV-Fingerabdrücke normalisieren Datumsindex und Zahlenformate. Dadurch erzeugt ein Parquet-Roundtrip mit inhaltlich identischem ganzzahligem beziehungsweise dezimalem Volumen keine falsche Datenrevision; echte Wertkorrekturen bleiben sichtbar.
- Forschungskennzahlen erweitert: Trefferquote mit Wilson-Intervall, durchschnittliches und medianes R, Profitfaktor, Drawdown, Symbol-/Signaltagsabdeckung, Marktphasen sowie Development-/Validation-/Holdout-Ergebnisse. `current`, `balanced`, `precision` und `payoff` werden als getrennte Hypothesen beziehungsweise explizit gelockte Research-Versionen verglichen; die Holdout-Paretofront aktiviert nie automatisch Produktion.
- Technisches Research-Gate festgelegt: mindestens 1.000 eindeutige bereinigte Ergebnisse, 200 Assets, je 200 Validation-/Holdout-Ergebnisse, mindestens 50 Fälle je vorhandener Marktphase und verifizierte angepasste Kurse. Auch bei bestandenem Gate ist nur eine manuelle Prüfung eines technischen Shadow-Challengers erlaubt. Die vollständige Swing-Strategie bleibt wegen fehlender historischer Point-in-Time-Fundamental-, News-, Makro- und TR-Daten gesperrt.
- Historische Forschung in der Swing-Oberfläche dauerhaft zugänglich gemacht: Gesamtmetriken, Strategievergleich, Marktphasen und die neuesten 500 Einzelfälle mit Datum, Ticker, Setup, Einstieg, Stop, Ziel und R sind ohne neuen manuellen Marktscan einsehbar.
- Reale V2-Echtprobe mit zehn breit gestreuten Assets erfolgreich: 10/10 Historien geladen, null Providerfehler, 120 neue nicht überlappende V2-Fälle append-only gespeichert, davon 64 eindeutig bewertet. Kleine Stichprobe: 18,75 % positive Ergebnisse, durchschnittlich +0,010 R, Profitfaktor 1,011 und Drawdown 26,52 R; ausdrücklich nicht freigabereif. Gesamtdatenbank danach zwei Läufe, 200 Fälle, Integrität und Fingerabdrücke `ok`.
- Reale V3-Echtprobe nach der Härtung: 10/10 Historien geladen, null Providerfehler und 120 aktuelle Fälle über Development, Validation und Holdout. 61 Fälle sind eindeutig bewertet: 16,39 % positive Ergebnisse, durchschnittlich +0,074 R, Profitfaktor 1,080 und Drawdown 15,79 R. Die kleine Stichprobe zeigt weiterhin keinen belastbaren Verbesserungsnachweis und aktiviert keine Regel.
- Wöchentliche Windows-Aufgabe `InvestmentAssistantSwingWalkForward` für Samstag 11:00 Uhr registriert. Status `Ready`, aktiviert, `WakeToRun` und `StartWhenAvailable` aktiv, nächster planmäßiger Termin 2026-08-22 um 11:00 Uhr; keine automatische Regeländerung und keine Orderausführung.
- Ersten vollständigen V3-Lauf über 2.520 Assets am 2026-08-17 um 13:09 Uhr außerplanmäßig gestartet. Der Windows-sichere Vier-Thread-Modus überschritt den vorherigen Prozesspool-Abbruchpunkt und rechnet kontrolliert im Hintergrund weiter; der nächste Wochenstart bleibt unverändert.
- Feste Drei-Trade-Grenze entfernt. Das versionierte Risikomodell verwendet nun 0,50 % Risiko je Trade, 2,00 % offenes Gesamtrisiko, 50 % gesamte Kapitalbindung und 20 % je Position. Aktive Stops reduzieren das belegte Risikobudget; ein Stop oberhalb des Einstiegs zählt nicht als neues Verlustrisiko. Paper-/Forward-Evidenz bleibt unabhängig vom Nutzerbudget vollständig.
- Abschlussprüfung nach V5-Kampagnenausbau, Profilbündelung, Versionskorrektur und Cross-Store-Verknüpfung: 469/469 Tests bestanden; Repository-Sicherheitscheck `OK`; Kompilierung und Offline-Smoke-Test erfolgreich. Die Forschungsdatenbank enthält 128 Läufe und 24.135 append-only Fallrevisionen; Schema 2, Quick-Check `ok`, null ungültige Fingerabdrücke. Der nächste große V2-Folgelauf startet erst im nächsten sicheren Zeitfenster.
- Bestehende echte Forward-, Paper- und historische Legacy-Daten wurden nicht gelöscht oder rückwirkend verändert. Kein Commit und kein Push.

### 2026-08-16

- Swing-Forward-Betrieb auf den aktuellen realen Stand gebracht: 41 unveränderbare Scans, 14 Signale und nach der erweiterten Aktivmessung 37 Ereignisse; SQLite-Quick-Check `ok`, null ungültige Fingerabdrücke.
- Aktueller Ergebnisstand: sechs Paper-Einstiege, fünf aktive Trades, drei verpasste Einstiege, ein vor Einstieg ungültiges Signal, vier noch gespeicherte/nicht aktivierte Signale und ein eindeutig abgeschlossener Verlust. Damit sind 0 von 1 abgeschlossenen Fällen Gewinne; die Stichprobe ist ausdrücklich noch nicht belastbar.
- Direkten Forward-Evaluator gegen einen bislang nur im App-Start abgefangenen Betriebsfehler gehärtet: yfinance verwendet nun auch im Hintergrundrunner den lokalen Projektcache mit sicherem temporärem Fallback.
- Temporäre Providerfehler bleiben append-only nachvollziehbar, ersetzen aber nicht mehr den bereits belegten fachlichen Lebenszyklusstatus eines Signals. Ein aktiver Trade bleibt bei einem späteren Abruffehler aktiv; ein noch nicht aktiviertes Signal bleibt gespeichert. Echte, nicht wiederholbare `not_evaluable`-Bewertungen bleiben davon unberührt.
- Mehrere unterschiedliche Abruffehler desselben Signals am selben Tag erhalten nun einen inhaltlich fingerprinteten Ereignisschlüssel. Gleiche Wiederholungen bleiben idempotent; unterschiedliche Fehlerbelege kollidieren nicht mehr.
- Der reguläre Europa-Scan vom 2026-08-16 um 18:15 Uhr endete nach 73/73 geladenen Assets, null Datenfehlern, null Rate-Limits und null neuen Freigaben mit Status `ok`. Der anschließende reale Forward-Nachlauf fand keine neuen abgeschlossenen Marktbalken beziehungsweise Lebenszyklusänderungen und schrieb deshalb korrekt kein neues Handelsergebnis.
- Neun beim isolierten Netzwerk-/Cache-Fehlversuch entstandene retry-fähige Datenhinweise bleiben aus Transparenzgründen unverändert gespeichert. Der erfolgreiche Wiederholungslauf bestätigte null Datenfehler und null Auswertungsfehler; keine Historie wurde gelöscht oder umgeschrieben.
- Gezielte Forward-Runner-/Statistiktests: 12/12 bestanden. Vollständige Suite: 439/439 bestanden; Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Kompilierung und Streamlit-Start erfolgreich. Kein Commit und kein Push.
- Schnellere, aber ehrliche Datensammlung umgesetzt: Alle fachlich qualifizierten Setups werden ab künftigen Scans als Forward-Signal gespeichert. Vom Nutzerportfolio freigegebene Signale und nur wegen Portfoliolimit/Positionsberechnung zurückgehaltene Shadow-Signale besitzen getrennte Evidenzarten und getrennte Ergebnisstatistiken; die Nutzeransicht erhält dadurch nicht mehr Trades.
- Verpasste, vor Einstieg ungültige und abgelaufene Signale bleiben fachlich terminal, erhalten aber nach 5 und 20 weiteren abgeschlossenen Sitzungen getrennte Kontrollrenditen mit MFE/MAE. Diese Ereignisse sind ausdrücklich `kein Trade-Ergebnis` und fließen weder in Trefferquote noch Gewinn/Verlust ein. Die vier vorhandenen Fälle sind noch nicht fällig.
- Aktive Papertrades speichern jetzt versioniert den kostenbereinigten Zwischenstand in Prozent und R, MFE/MAE sowie Abstand zu Stop und nächstem Ziel. Der reale Nachlauf schrieb fünf neue aktive Messereignisse konfliktfrei append-only; BANR, ASB, UMBF und BATRK lagen am letzten abgeschlossenen Balken im Plus, HOPE leicht im Minus und rund 0,79 % über dem System-Stop. Das ist eine Messung, keine Handelsempfehlung.
- Marktphase, Volatilitätsregime, Evidenzart und Portfoliofreigabe sind im Archiv filterbar und in Ergebnisgruppen getrennt. Qualifizierte Kandidaten erhalten zusätzlich einen rein beobachtenden 60-Sitzungs-Korrelations-, Branchen- und Regionsaudit; er lehnt nichts automatisch ab und ändert keine Gewichte.
- Historischen technischen Swing-Walk-Forward-Test als eigene append-only Datenbank `runtime/swing_walk_forward.sqlite3` umgesetzt. Jedes Signal sieht nur das wachsende Vergangenheitsfenster; spätere Balken werden erst danach ausgewertet. Historische Fundamental-, News-, Makro- und TR-Daten fehlen bewusst, daher bleiben diese Fälle `historical_technical_shadow`, nicht produktionsvergleichbar und strikt außerhalb der echten Forward-Trefferquote.
- Erste reale historische Stichprobe über fünf Jahre für zehn liquide Aktien: 80 getrennte technische Shadow-Fälle, 47 eindeutig mit R bewertet, 10 positive und 37 nicht positive Ergebnisse, 21,28 % positive Quote und durchschnittlich +0,378 R. Die Kombination aus niedriger positiver Quote und positivem Durchschnitt zeigt asymmetrische Einzelgewinne; wegen der fehlenden Point-in-Time-Kontexte und kleinen Segmente darf daraus keine Produktionsänderung abgeleitet werden. Datenbank-Quick-Check `ok`, null ungültige Fingerabdrücke.
- Swing-Lern-Gate auf mindestens 100 eindeutige echte Forward-Ergebnisse, zwölf Beobachtungswochen und mindestens 20 Ergebnisse je vorhandener Asset-, Marktphasen-, Volatilitäts- und Versionsgruppe festgelegt. Der aktuelle Stand bleibt 1/100 und sechs Beobachtungstage; historische Fälle zählen nicht. Jede Regel- oder Gewichtsänderung bleibt manuell, versioniert und gesperrt, solange das Gate nicht erfüllt ist.
- Letzte Kontrollgruppen-Lücke geschlossen: Je realem Scan werden bis zu fünf in der Tiefenanalyse abgelehnte Kandidaten über einen stabilen SHA-256-Samplingschlüssel reproduzierbar ausgewählt. Ausgangskurs, Marktphase, Volatilität, Datenqualität und exakte Ablehnungsfilter liegen append-only in eigenen Schema-2-Tabellen; 5-/20-Sitzungs-Rendite und MFE/MAE bleiben reine Kontrollergebnisse ohne Orderplan, Trade-Status, Trefferquotenwirkung oder automatische Regeländerung. Der aktuelle Bestand ist null, weil seit der Einführung noch kein neuer realer Scan gespeichert wurde.
- Abschlussprüfung des Gesamtpakets: 453/453 Tests bestanden; Repository-Sicherheitscheck und Offline-Smoke-Test mit Kompilierung, Historienqualität und Streamlit-Start erfolgreich. Produktive Swing-Forward-Datenbank Schema 2 mit 41 Scans, 14 Signalen, 37 Ereignissen und noch null neuen Ablehnungsproben, Integrität `ok`; historische Walk-Forward-Datenbank ein Lauf, 80 Fälle, Integrität `ok`. Kein Commit und kein Push.

### 2026-08-11

- Hintergrundzeitplanung auf das gewünschte Ausschaltfenster umgestellt: Asien/Australien bleibt 10:30 Uhr, Europa bleibt 18:15 Uhr. Die Prognose-Aufgabe startet weiterhin 22:30 Uhr, führt nun aber anschließend zwingend Amerika/Global und danach Krypto aus.
- Separate Windows-Aufgaben um 00:30 Uhr und 02:15 Uhr entfernt. Die neue Abendkette protokolliert jede Stufe getrennt, führt nach einem Fehler auch die späteren Stufen aus und gibt am Ende einen Fehlercode zurück. `StartWhenAvailable` bleibt aktiv, sodass ein verpasster Abendtermin bei der nächsten Verfügbarkeit nachgeholt wird.
- Zielzustand: keine regulären Hintergrundaufgaben zwischen 00:00 und 10:00 Uhr, keine unnötige parallele Yahoo-Last der drei Abendläufe und bei bisherigen Laufzeiten ein reguläres Ende ungefähr bis 23:30 Uhr. Dies ist ein Betriebsziel und keine harte Garantie.
- Trade-Republic-Ausrichtung als höchste aktuelle Swing-Unterpriorität umgesetzt: Normalbereich nur für verifizierte TR-Listings, getrennte Paper-only-Anzeige bei `TR nicht handelbar` oder `unbekannt`, vollständige unveränderte Forward-/Lernspeicherung für beide Gruppen.
- Neue append-only TR-Referenz ergänzt. Analyse- und TR-Listing werden anhand Ticker, Handelsplatz, Währung und identischer ISIN getrennt gespeichert; dauerhafte manuelle Markierung ist möglich. Abweichende Instrumente sowie ein stilles Ticker-/Unternehmens-Matching ohne Listingbeleg sind gesperrt.
- Ausführungspreisvertrag umgesetzt: Ein höchstens 15 Minuten alter manueller TR-EUR-Preis und ein zeitgleich erfasster Analyse-Vergleichskurs sind Voraussetzung für `Aktueller Preis` und den gesamten TR-Ausführungsplan. Ihr Quotient bildet nur die Listing-Basis; ältere technische Marken werden nicht neu verankert. Ohne vollständige Basis erscheint `TR-Preis nicht verfügbar` beziehungsweise kein ausführbarer Plan; Yahoo bleibt ausschließlich Analyse-/Chart-/Forward-Quelle und wird nie als TR-Preis verwendet.
- Persönliche Nutzertrade-Erfassung und laufende Preis-/Gewinn-Verlust-Bewertung auf den verifizierten TR-Plan begrenzt. Keine Broker-Anbindung, keine automatische Status- oder Preiserkennung und keine Orderausführung ergänzt.
- Forward- und Archivstatistik trennt nun Scannerqualität gesamt, TR-handelbare Listings, tatsächlich vollständige TR-Ausführungspläne und Paper-only-Fälle. Bestehende Signale, Ereignisse und Nutzerhistorien wurden nicht gelöscht oder rückwirkend geändert.
- Roadmap ausschließlich dokumentarisch um zwei zusammengehörige Ausbaupakete ergänzt: skalierbares Prognoseuniversum mit entkoppelten Horizontfrequenzen und robuste Unternehmens-/Listing-Identität einschließlich ADR/ADS und Primärnotierung sowie die nächste Swing-Scanner-Skalierung.
- Prognose-Rhythmus verbindlich geplant: 1W wöchentlich, 1M alle zwei Wochen, 3M monatlich, 6M alle drei Monate und 12M alle sechs Monate. Eine Wochenanalyse soll nicht mehr automatisch alle fünf Horizonte starten; bestehende Snapshots und offene Auswertungen bleiben unverändert.
- `long_horizon_eligible` mit versioniertem Eignungsgrund aufgenommen. Lange Horizonte verlangen ausreichende Historie, eindeutige Identität, Liquidität, hohe Datenqualität und belastbare Unternehmens-/Finanzdaten; Regionen, Branchen, Mid Caps, geeignete Wachstumsunternehmen und ETFs bleiben diversifiziert vertreten.
- Mehrstufige Prognoseuniversen geplant: das umgesetzte 1.726-Asset-Universum zunächst real validieren, danach ungefähr 2.500 bis 3.500 regelmäßig prognostizierte Assets und perspektivisch ein günstiges Discovery-/Monitoring-Universum mit ungefähr 5.000 bis 10.000 beobachtbaren Assets. Kontrollstichproben prüfen Vorfilter-Bias.
- Unternehmens- und Listingebene getrennt geplant: `company_id`/`issuer_id` für gemeinsame Fundamentaldaten und langfristige Qualität, `listing_id` für Ticker, Börse, Währung, Instrumenttyp, Handelszeiten, Kurs, Chart, Liquidität und technische Marken. Neue Prognosen speichern beide Identitäten; Legacy-Daten werden nicht rückwirkend angereichert.
- Mehrfachlisting-Suche ohne Sonderregel festgelegt: Bei Unternehmensnamen werden relevante Listings sichtbar zur Auswahl angeboten; `Analysiertes Listing: …` bleibt sichtbar und änderbar. XPeng `9868.HK` und `XPEV`, europäische ADRs, mehrere europäische Listings, Einzelnotierung sowie Ticker-/Namensuche sind als Regressionstestfälle vorgesehen.
- Striktes Vermischungsverbot ergänzt: Kurs, Chart, Volumen, Spread, Stop, Ziel, technische Marken und kurzfristige Prognosen bleiben listing-spezifisch. ADR-Verhältnisse dürfen nur belegt zur Identitäts-/Bewertungsnormalisierung dienen und nie technische Charts oder Marken übertragen. Long-Term-Statistik zählt wirtschaftlich gleiche Listings nicht als unabhängige Unternehmen doppelt.
- Swing-Universum auf 2.520 liquide Assets erweitert. Die feste 60er-Tiefenanalysegrenze wurde entfernt; alle bestandenen Grobfilterkandidaten werden vollständig geprüft.
- Regionale Swing-Planung präzisiert: aktuelle Windows-Termine in `Europe/Berlin`, abgeschlossene regionale Tageskerzen, Börsenkalender/Feiertage, echtes Nachholen ohne Rückdatierung, kanonischer UTC-Cutoff für Krypto und sichtbarer letzter/nächster offizieller Scan. Manueller und geplanter Scan verwenden dieselbe fachliche Pipeline.
- ETF-/Aktien-/Krypto-Funnel technisch umgesetzt. Der erste große Echtlauf zeigt eine ETF-Grobfilterquote von 58,0 % gegenüber 14,48 % bei Aktien; das System kennzeichnet den Unterschied ohne Kausalbehauptung und ohne automatischen Bonus oder Malus. Forward-Metriken reifen weiter.
- ETF-/Aktien-Bias mit zwei vollständigen, nicht speichernden Amerika/Global-Kontrollläufen untersucht. Baseline-Finalfilter: 321 Aktien und 29 ETFs abgelehnt, zwei Aktien und kein ETF freigegeben. Kaufsignal löste bei 237 Aktien/7 ETFs aus, Langfristqualität bei 50/1, präzise Setup-Struktur bei 41/20; EUR-Umsatzminimum bei 7/0. Der ursprüngliche 58-%-Wert war damit überwiegend ein ETF-False-Positive-Problem des schnellen Strukturfilters, kein finaler ETF-Freigabevorteil.
- Assettypneutrale Filterpolitik `swing-filter-neutrality-2026.08.11-v1` umgesetzt: feste Setup-Prozentzonen durch ATR-normalisierte Grenzen ersetzt, Rohstückzahl-Liquiditätsgate entfernt, positive Volumenabdeckung geprüft und finaler EUR-Umsatz beibehalten. Langfristige Asset-Qualität bleibt Diagnose, ist aber weder Swing-Hard-Gate noch Rangfaktor. Keine Aktienbevorzugung, ETF-Quote oder automatische Gewichtung.
- Nachher-Reallauf: Aktien 319/2.300 beziehungsweise 13,87 %, ETFs 7/50 beziehungsweise 14,00 % im Grobfilter; alle 326 Kandidaten tief geprüft, zwei Aktien und kein ETF final bestanden. Die Differenz von 0,13 Prozentpunkten ist vollständig je Filter sichtbar und nicht als Zielwert codiert.
- Strategieversion `swing-long-pullback-breakout-2026.08.11-v3` und Orderplan zuletzt `swing-order-plan-2026.08.11-v3`. Die neue Orderplanversion speichert eine ausdrücklich nicht als TR-Kurs geltende Analysepreisreferenz für die getrennte TR-Übertragung. ETF/Aktie werden innerhalb dieser Version erst ab jeweils 20 eindeutigen echten Forward-Ergebnissen nach Trefferquote, Durchschnitt R, Profitfaktor und Drawdown verglichen; aktuell null gereifte v3-Ergebnisse je Klasse, daher keine fachliche Siegerbehauptung.
- Privaten Forward-Stand nach parallelem `manual_full`-v2-Lauf um 22:21 Uhr erneut geprüft: 21 gespeicherte Scans, vier alte v1/v2-Signale EWL, LT.NS, BANR und JBL, drei Ereignisse, Integrität `ok`. Die drei Bias-Diagnoseläufe wurden nicht gespeichert und erzeugten keine v3-Fälle; der versionsgleiche ETF-/Aktien-Vergleich beginnt mit künftigen real gespeicherten v3-Scans.
- Echten Swing-Forward-Trade als vollständigen Systemplan-Lebenszyklus klargestellt. Ein später höherer Kurs allein ist kein Erfolg; Aktivierung, realistischer Einstieg, Gap, Ungültigkeit, Ziel-/Stopreihenfolge, MFE/MAE, Haltedauer, Kosten, FX, Euro-/Prozent-/R-Ergebnis und Datenqualität sind maßgeblich.
- Versionierten Horizontkalender umgesetzt: 1W wöchentlich, 1M alle zwei Wochen, 3M monatlich, 6M alle drei Monate und 12M alle sechs Monate. 6M/12M verlangen ein versioniertes Langfrist-Evidenzgate; bestehende Prognosen wurden weder gelöscht noch verändert.
- Offizielles Nasdaq-Global-Select-Verzeichnis mit dem vorhandenen breiten Projektuniversum zusammengeführt: 2.520 eindeutige Swing-Assets, davon 2.431 Aktien, 59 ETFs und 30 Kryptowährungen. ServiceNow bleibt enthalten; bekannte Hebel-/Inverse-Produkte sind gesperrt.
- Reale Regionalvalidierung mit neuer Pipeline: Amerika/Global 2.350/2.352, Asien/Australien 65/65, Europa 73/73 und Krypto 29/30 geladen; alle vier Läufe `ok`, null Rate-Limits, SQLite-Quick-Check `ok`.
- Alle 362 Amerika/Global-Grobfiltertreffer vollständig tief analysiert; keine feste 60er- oder andere Top-N-Grenze mehr. LT.NS wurde als zweites echtes append-only Forward-Signal gespeichert.
- Kritischen Regionalrandfall behoben: Neue Orderpläne können keinen sichtbaren frühesten Einstieg mehr vor dem tatsächlichen Scanzeitpunkt ausweisen. Der bestehende LT.NS-Snapshot bleibt unverändert; die Forward-Auswertung verwendete bereits ausschließlich Balken nach dem Signal.
- Kritische Zeitreise-Lücke im getrennten Nutzertrade-Pfad geschlossen: Ein tatsächlicher Einstieg am oder vor dem gespeicherten Signalzeitpunkt ist nun nicht übersteuerbar gesperrt. Planabweichungsbestätigung kann diese Point-in-Time-Grenze nicht umgehen; vorhandene Signal- und Trade-Snapshots bleiben unverändert.
- Prognosedatenbank nach der Erweiterung rein lesend geprüft: 2.270 Prognosen, 523 Auswertungen, 325 gültige neue Messverträge, 1.945 Legacy-Datensätze, null ungültige Verträge, Schema 9 und Integrität `ok`.
- TR-Kern mit 28 gezielten Referenz-, Nutzertrade- und Forward-Statistiktests geprüft; anschließend vollständige Suite 437/437 bestanden. Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Kompilierung und Headless-Streamlit-Start erfolgreich.
- Kein Commit und kein Push. Keine Broker-Verbindung und keine Order.

### 2026-08-09

- Hauptpriorität auf ausdrücklichen Nutzerwunsch neu festgelegt: zuerst wöchentliche breite Markt-Scans, echte Forward-Snapshots, automatische Fälligkeitsauswertung und alle sicher messbaren Verbesserungen der Analyse- und Prognosepräzision; direkt danach der Swing Trade Finder als wichtigste Nutzerfunktion.
- Frühere Reihenfolge mit allgemeinem Designsystem, Navigationsumbau, Long-Term-Ausbau und `Investment Opportunities` vor dem Swing-Bereich aufgehoben. Diese Arbeiten folgen nun erst nach dem stabilen Wochen-/Forward-Betrieb und dem priorisierten Swing-Ausbau.
- Ersten Prioritätsblock konkretisiert: ab 2026-08-09 fällige Ein-Wochen-Ergebnisse zunächst gegen den tatsächlichen Datenbankstand prüfen, Point-in-Time-Messvertrag absichern, tägliche Fälligkeitsprüfung von wöchentlicher Neuprognose trennen, 325-Referenzkern erhalten und ein ungefähr 1.500- bis 2.500-Asset-Universum in festen Wochengruppen kontrolliert aufbauen.
- Prognosepräzision ausdrücklich breiter als Trefferquote definiert: Kalibrierung, Brier Score oder Log Loss, Abdeckung/Enthaltung, Rendite, Drawdown, Opportunitätskosten, Datenqualität, Marktphase, Asset-Typ, Region, Horizont und Modellversion müssen getrennt messbar sein.
- Wechsel zum Swing-Ausbau benötigt noch kein fertiges lernendes Modell. Voraussetzung sind jedoch wiederkehrende unveränderbare Forward-Daten, automatische echte Ergebnisprüfung sowie sichtbare Wochenabdeckung und Fehler. Kritische Stabilitäts-, Datenschutz-, Datenintegritäts- und Falschergebnisfehler behalten jederzeit Vorrang.
- Produktionsstand vor dem ersten Fälligkeitstermin geprüft: Windows-Aufgabe `Ready`, letzter Lauf 2026-08-08 erfolgreich mit 325/325, null Fehlern und null Rate-Limits; nächster Termin 2026-08-09 um 22:30 Uhr. SQLite-Integrität `ok`, 1.945 Prognosen, 9.725 Zeiträume und vor dem Termin null Auswertungen.
- Fällige Marktdatenabfrage auf begrenzte Yahoo-Batches umgestellt und historischen FX-Cache je Währung/Bewertungstag geteilt. Dadurch benötigen die ersten 322 fälligen Fälle nicht mehr je Asset einen getrennten Hauptabruf; Fehler und Rate-Limits bleiben je Ergebnis sichtbar.
- L0-Point-in-Time-Messvertrag in `forecast_measurement.py` umgesetzt. Neue Snapshots speichern Beobachtungs-Cutoff, Feature-/Label-/Benchmark-/Kosten-/Qualitätsvertrag, Leakage-Regeln und SHA-256-Fingerabdruck. Alte 1.945 Snapshots bleiben unverändert und als Legacy ohne Vertrag gezählt.
- Getrenntes Forecast-Wochenuniversum mit 1.726 gültigen, eindeutigen Assets erzeugt und versioniert. Der 325er Referenzkern ist Montag zugeordnet; die Erweiterung verteilt sich deterministisch auf Dienstag bis Freitag mit 362, 354, 340 und 345 Assets.
- Tagesprozess getrennt: zuerst fällige Ergebnisse, danach höchstens eine fällige Wochenkohorte. Wochenend-/Vorlauf-Termine sind reine Auswertungsläufe; verpasste Kohorten werden innerhalb derselben Woche ohne Rückdatierung nachgeholt. Realer Wochenstart ist 2026-08-10.
- SQLite schrittweise und nach drei geprüften Sicherungen nicht löschend auf Schema 7 migriert. Neue Ergebnisfelder speichern tatsächlichen Bewertungstag, beste/schlechteste Bewegung sowie `immer steigend` und `keine Änderung` als erste Referenzen. Die Qualitätsansicht zeigt Referenzvorsprung, Rendite, Drawdown und Ergebnisabdeckung.
- Vollständige Prüfung bestanden: 329 Pytest-Tests, Repository-Sicherheitscheck, Kompilierung und Offline-Smoke-Test einschließlich Headless-Streamlit-Start. Drei zuvor datumsabhängige Long-Term-Tests verwenden nun einen festen Prüfzeitpunkt; die fachlichen Altersregeln wurden nicht gelockert.
- L2-Referenzschicht ergänzt: neue Snapshots speichern eine einfache 20-Tage-Trendrichtung und einen passenden Marktbenchmark (`SPY`, `EXSA.DE`, `AAXJ`, `ACWI` oder für Krypto direkt `BTC-EUR`). Alle fünf Benchmarkpfade wurden live erfolgreich geprüft; die direkte Euro-Referenz verhindert eine künstliche Wochenend-FX-Lücke bei Krypto.
- Automatische Wochenberichte unter `runtime/weekly_reports/` ergänzt. Sie werden je ISO-Woche atomar fortgeschrieben, niemals automatisch gelöscht und zeigen Kohortenstatus, Nachholtage, Assets, Fehler, Rate-Limits, Laufzeit, Datenbankwachstum, fällige Auswertungen und Integrität. Der vorbereitende Bericht für Kalenderwoche 32 zeigt korrekt null überfällige Kohorten vor Start, 322 fällige offene Ergebnisse und Integrität `ok`.
- Prognosequalität erweitert: Wilson-Konfidenzintervall, steigende Precision/Recall, Balanced Accuracy, Ergebnisabdeckung, Referenzvorsprung, Rendite, Drawdown, Marktüberschuss sowie getrennte Segmente nach Region, Marktphase, Datenqualität und Logikversion. Einseitige Stichproben erzeugen bewusst keine Balanced Accuracy.
- Produktive SQLite-Datenbank nach zusätzlicher geprüfter Sicherung nicht löschend auf Schema 8 migriert; weiterhin 1.945 unveränderte Prognosen, null Auswertungen und Integrität `ok`.
- Vollständige Messvertragsprüfung vor jedem Tageslauf ergänzt. Sie trennt Legacy-Zeilen von gültigen neuen Verträgen, erkennt Fingerabdruck-, JSON-, Schema- und Cutoff-Abweichungen und stoppt bei einem Fehler noch vor Auswertung oder Marktabruf. Die produktive Vorprüfung bestätigt 1.945 Legacy-Zeilen und null ungültige Verträge.
- Rohwahrscheinlichkeit für `tatsächliche Rendite > 0` ergänzt. Sie wird versioniert aus der unveränderbaren Bull-/Base-/Bear-Verteilung und ihren numerischen Zielen gebildet, bleibt klar als unkalibriert gekennzeichnet und interpretiert den Confidence-Score nicht als Wahrscheinlichkeit. Brier Score, Log Loss, Kalibrierungsfehler und Bias sind insgesamt, nach Modell und nach Zeitraum vorbereitet.
- Produktive Datenbank nach neuer geprüfter Schema-8-Sicherung nicht löschend auf Schema 9 migriert; 1.945 Prognosen und null Auswertungen blieben unverändert, Integrität `ok`. Kalibrierungsprofil v2 enthält erwartungsgemäß null gereifte Wahrscheinlichkeitsfälle und ändert keine Regel.
- L2-Lern-Gate ergänzt: Nur verifizierte gereifte Point-in-Time-Fälle sind zugelassen; Legacy, offene, unbrauchbare und ungültige Zeilen bleiben getrennt. Produktiver Bericht: 9.725 Legacy-Zeiträume, null berechtigte Fälle, null ungültige Verträge, `collect_only` und Produktionsaktivierung gesperrt. Purged Walk-Forward-Fenster verhindern, dass am Stufenbeginn noch unbekannte Labels in Training oder Validierung gelangen.
- Reale nicht speichernde Yahoo-Probe für NVDA war um 15:59 Uhr vollständig leer. Globaler Provider-Schutz ergänzt: Sind alle vorbereiteten Marktbenchmarks leer, wird eine neue Wochenkohorte vor dem ersten Asset pausiert, nicht als abgeschlossen markiert und später erneut versucht. Einzelne Lücken bleiben isoliert.
- Vollständiger aktueller Prüfstand nach Swing-Order-, Forward-, Hintergrund-, historischer FX-, Archiv-, Nutzertrade- und Modellregister-Erweiterung: 401 Pytest-Tests bestanden; Repository-Sicherheitscheck, Kompilierung und Offline-Smoke-Test mit Headless-Streamlit-Start waren im selben Arbeitslauf erfolgreich.
- Swing-Phase-A-Kern ergänzt: versionierter und fingerprinteter Orderplan für Pullback-/Ausbruchsetups, ausschließlich abgeschlossene Tageskerzen, frühester Einstieg in einer späteren Sitzung, konservative Lücken-/Widerlegungsprüfung, endgültige Positions-/Risiko-/Gewinnwerte und ausdrücklicher Ausschluss jeder Broker-Ausführung.
- Manueller Trade-Lebenszyklus verschärft: Einstieg vor dem erlaubten Folgetag wird abgewiesen, initialer Stop und Stop-Vertragsversion bleiben erhalten, und ein aktiver Long-Stop kann nur enger, niemals weiter gesetzt werden. Die Orderkarte zeigt den ausführbaren Plan vor den technischen Details.
- Sichtbare Browserprüfung nach Playwright-Arbeitsregel versucht, aber mangels lokalem Node.js/`npx` nicht gestartet. Es wurde nichts installiert; Desktop-/390-Pixel-Abnahme bleibt offen.
- Sichtbare Prüfung anschließend über den vorhandenen In-App-Browser erfolgreich nachgeholt und nach dem Nutzertrade-Ausbau wiederholt: Swing-Einstieg bei 1.440 Pixel und 390 Pixel ohne horizontalen Überlauf, ohne Startfehler, ohne unerwartete Normaleingaben, mit genau einem Tradingkapital-Feld und sichtbarem Bereich `Meine aktiven Trades`. Eine echte freigegebene Orderkarte bleibt bis zum ersten realen Signal sichtbar zu prüfen.
- Append-only Swing-Forward-Datenbank ergänzt: reale Scans einschließlich Null-Trade-Läufen, unveränderbare Signalsnapshots und ausschließlich angehängte Ereignisse besitzen Schema-/Strategieversionen und SHA-256-Fingerabdrücke; Datenbank-Trigger sperren Update und Delete. Die ältere JSON-Historie bleibt unverändert getrennt.
- Konservative Swing-Auswertung ergänzt: nur vollständige Kursbalken nach Signal, 5-Minuten-/Stunden-/Tages-Fallback, versionierte Kosten, realistischer Gap unter Stop, verpasster Gap über Maximalpreis und keine Gewinnannahme bei unklarer Ereignisreihenfolge. Archivwerte trennen offene, verpasste, abgelaufene, unklare und nicht auswertbare Fälle von eindeutigen Gewinnern/Verlierern.
- Historischer Stand vom 2026-08-09: Vier regionale Windows-Aufgaben waren damals für Europa um 18:15, Amerika/Global um 00:30, Krypto um 02:15 und Asien/Australien um 10:30 registriert. Dieser Nachtplan wurde am 2026-08-11 durch die sequenzielle 22:30-Abendkette ersetzt; die frühere Messung bleibt nur zur Nachvollziehbarkeit erhalten.
- Erster planmäßiger Europa-Lauf am 2026-08-09 um 18:15 real belegt: Windows-Rückgabecode 0, 73 ausgewählte und 72 geladene Assets, ein isolierter Symbolfehler, keine Rate-Limits, 22,921 Sekunden Laufzeit, ein freigegebenes unveränderbares EWL-Ausbruchssignal und SQLite-Integrität `ok`; Orders waren deaktiviert.
- Den isolierten Roche-Fehler sicher auf `ROG.SW` eingegrenzt und den künftigen Swing-Universums-Eintrag auf das beim Datenanbieter erfolgreiche `ROP.SW` korrigiert. Zwei append-only Nachläufe luden anschließend jeweils 73/73 Assets ohne Fehler oder Rate-Limits. Drei Scanbeobachtungen derselben Freitagskerze enthalten dank der Deduplizierung weiterhin genau ein EWL-Forward-Signal und keine doppelten Ereignisse; der historische Fehlerdatensatz bleibt erhalten.
- Bedienungsfreie Übergabe in die Oberfläche geschlossen: Eine frisch geöffnete Swing-Seite zeigt nun den letzten automatischen Regional-Scan und offene/aktive Hintergrundsignale ohne erneuten manuellen Vollscan. Der unveränderbare EWL-Plan ist mit Ordertyp, Limit, frühestem Einstieg, Stop, Zielen, Gültigkeit und getrenntem optionalem Nutzertrade sichtbar; keine Order wird ausgelöst.
- Echte EWL-Karte im In-App-Browser bei 1.280 und 390 Pixel geprüft: vollständige Kernwerte, kein horizontaler Überlauf und keine Browserkonsolenfehler. Testpfad für die Swing-Forward-Datenbank zusätzlich per Umgebungsvariable isolierbar gemacht, damit UI-Tests niemals produktive Forward-Daten lesen.
- Vollständige Regression nach der UI-Übergabe: 401 Pytest-Tests bestanden. Die Long-Term-Scoring-Tests verwenden nun einen festen Prüfzeitpunkt; produktive Quellenalter- und Bereitschaftsregeln blieben unverändert.
- Persönliche Nutzertrades strikt vom objektiven Paper-Verlauf getrennt. Eine eigene append-only SQLite-Datenbank speichert extern ausgeführte Einstiege und ausschließlich angehängte Stop-, Teilverkaufs- und Abschlussereignisse. Abweichungen vom Systemplan benötigen Bestätigung; initialer Stop bleibt unverändert und ein Long-Stop darf nur enger werden.
- `Meine aktiven Trades` und erste regelbasierte Begleitung ergänzt: Plan intakt, erhöhte Aufmerksamkeit, regelbasierte Anpassung, Notausstieg oder nicht belastbare Daten. Jede Meldung bleibt Empfehlung; Brokerorder und automatische Ausführung sind fest ausgeschlossen.
- Regionale Schlusskursfreigabe präzisiert: eine gleichdatierte Aktien-/ETF-Tageskerze ist erst nach konservativem Handelsschluss in Amerika, Europa oder Asien zulässig; Krypto bleibt bis zum nächsten UTC-Tag gesperrt. Dadurch entstehen weder Intraday-Leakage noch unnötig einen Tag verspätete Nachbörsensignale.
- Historische Swing-Währungsbewertung append-only ergänzt: getrennte Ein-/Ausstiegs-FX-Belege verwenden bevorzugt Intraday-Kurse nur bis zum Ereignis und sonst ausschließlich den bereits bekannten früheren Tagesabschluss. Fehlende Belege bleiben nachholbar; kein Terminalereignis wird überschrieben.
- Nutzertrade-Begleitung um abgeschlossene 20-Tage-Struktur, Trend, Gap und relatives Verkaufsvolumen erweitert. Noch nicht belastbar automatisierte Nachrichten-, Ereignis- und Branchenfaktoren bleiben explizit unbekannt.
- Alle 1.124 Swing-Assets erhalten eine stabile versionierte interne ID; Börse und ISIN werden nur bei tatsächlich gelieferter Quelle gespeichert und niemals erfunden.
- Sicheres append-only Modellregister für spätere Prognose-Challenger ergänzt. Es verlangt reproduzierbare Fingerabdrücke, dokumentiert Shadow-/Review-/Canary-/Rollback-Nachweise und besitzt absichtlich keine Funktion zur automatischen Produktionsaktivierung.
- Rollierende Prognoseüberwachung ergänzt: 28 jüngste Tage werden je Modell/Horizont mit den vorherigen 84 Tagen auf Richtungstreffer, Trendregel-Vorsprung, Überschussrendite, Brier Score, Log Loss und Wahrscheinlichkeitsabdeckung verglichen. Zusätzlich werden Eingabe-/Segmentverschiebungen, Auswertungsrückstand, technische Fehler, Asset-Erfolgsquote, Enthaltungsquote und Rate-Limits beobachtet.
- Fehlalarm- und Sicherheitsgrenzen fest verankert: unter 50 Ergebnis-/Wahrscheinlichkeitsfällen beziehungsweise 100 Eingabefällen wird kein Drift behauptet; kalendarisch fällige Fälle besitzen drei Tage Handelskalender-Puffer. Der Monitoring-Bericht ist Teil des atomaren Kalibrierungsprofils v3, erscheint in der Prognosequalität und kann weder nachtrainieren noch Regeln, Scores oder Produktionsmodelle ändern.
- Produktives Profil nach der Erweiterung markt- und prognosefrei erzeugt: Status `collect_only`, 322 kalendarisch fällige, aber null mehr als drei Tage überfällige Fälle, jüngste Asset-Erfolgsabdeckung 99,7 %, null Rate-Limits und keine Driftwarnung mangels belastbarem Referenzfenster.
- Vollständige Regression nach der Monitoring-Einheit: 404 Pytest-Tests bestanden; Kompilierung, Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Headless-Streamlit-Start erfolgreich. `git diff --check` meldete keine Fehler außer vorhandenen Zeilenende-Hinweisen.
- Swing-Archivfilter vervollständigt: freie Suche über Assetname, Ticker, ISIN und Signal-ID sowie kombinierbare Filter nach Signalzeitraum, Status, Setup, Einstiegsmethode, Asset-Typ, Paper-Gewinn/-Verlust/offenem Ergebnis, Datenqualität, Region, historischem FX, Strategieversion, Quellentyp und getrennt dokumentiertem Nutzertrade. Objektive Paper-Zeilen werden dadurch weder verändert noch mit persönlichen Resultaten vermischt.
- Reales EWL-Archiv read-only gegen die neue Filterlogik geprüft: genau ein Treffer mit vollständigen neuen Archivfeldern; `Nutzertrade = Nein`, weil keine persönliche Handlung dokumentiert wurde. 68 gezielte Swing-/UI-/Stabilitätstests und anschließend die vollständige Suite mit 404/404 Tests bestanden.
- Begonnene Archiv-Detailmetriken abgeschlossen: Terminale Paper-Ereignisse speichern maximalen günstigen und ungünstigen Kursausschlag ab der Einstiegskerze. Das Archiv zeigt Paper-Einstiegs-/Ausstiegszeit, Haltedauer, Ergebnisstatus sowie maximalen Zwischengewinn/-verlust. Gap-Ausstiege berücksichtigen den ersten real handelbaren Kurs; grobe Balken bleiben ausdrücklich als eingeschränkte Quelle gekennzeichnet.
- Append-only-Kompatibilität bewahrt: Die bestehende Ereignisversion und stabile Quellschlüssel bleiben unverändert, bereits gespeicherte aktive oder terminale Ereignisse werden nicht umgeschrieben. 16 gezielte Swing-Auswertungs-, Archiv- und Runner-Tests bestanden.
- Kein Commit, kein Push, keine Broker-Verbindung und keine Order. Der reale Nachweis der ersten 322 Auswertungen um 22:30 Uhr und der fünf Wochenkohorten ab 2026-08-10 bleibt offen; das aktive Goal ist deshalb nicht abgeschlossen.

### 2026-08-07

- Verpassten Lauf vom 2026-08-06 bewusst nicht als nachträgliche Forward-Prognose rekonstruiert. Echte Trefferquoten und die produktive Prognosedatenbank bleiben frei von Rückschaufehlern.
- Getrennte Recovery-Architektur ergänzt: `forecast_recovery.py` speichert ausschließlich historische OHLCV-Balken in `runtime/forecast_recovery.sqlite3`, markiert jeden Lauf unveränderbar als nicht Forward-Test-berechtigt und hält Cutoff, Abrufzeit, Quelle, Abdeckung, Fehler und SHA-256-Datenfingerabdruck fest.
- CLI `scripts/recover_forecast_market_data.py` lädt tägliche Balken nur vor dem Zieldatum und 5-Minuten-Balken am Zieldatum nur, wenn ihr Intervall spätestens am Cutoff endet. Aktuelle Fundamentaldaten, Nachrichten, Metadaten und nachträgliche Empfehlungen werden nicht gespeichert.
- Reale Datenrettung für `2026-08-06T22:30:00+02:00`: 116.517 Balken für 324 von 325 Assets, davon 85.336 Tages- und 31.181 Fünf-Minuten-Balken. Tagesdaten enden am 2026-08-05; kein Intraday-Balken endet nach 20:30 UTC. SQLite-Integrität `ok`, Fingerabdruck `783a8023e54a1a701d60d09df9600ddd4d7c684972e24d330b0203787d596424`.
- `MATIC-USD` blieb als einzige transparente Lücke ohne Yahoo-Historie; auch `POL-USD` lieferte keine belegbaren Daten. Es wurde kein Ersatzwert erfunden.
- Statusdarstellung korrigiert: Ein einzelner verpasster Datenlauf ist eine Warnung statt einer roten Fehlermeldung; echte Datenbankfehler sowie festhängende oder unterbrochene Läufe bleiben rot. Offene Werte heißen nun korrekt `Prognosezeiträume`.
- 29 gezielte Recovery- und Prognosesystemtests bestanden; produktive SQLite-Integrität `ok`, weiterhin 1.295 echte Prognosen und 6.475 echte Prognosezeiträume. Kein Commit, kein Push und keine Order.

### 2026-08-04

- Dritten vollständigen planmäßigen Prognoselauf live und ausschließlich lesend bis zum regulären Ende überwacht. Wrapper-Start 22:30:02 Uhr, SQLite-Start 22:30:07 Uhr, Ende 22:43:30 Uhr und Wrapper-Exit 0 sind konsistent dokumentiert.
- Alle 325 Assets wurden erfolgreich gespeichert; es gab keine fehlgeschlagenen Assets und keine Rate-Limits. Laufzeit 803,26 Sekunden, 24,28 Assets pro Minute, 0,00 % Fehlerquote, 3.510.272 Byte Datenbankwachstum sowie Datenbankstatus und Integrität `ok`.
- Die am Vortag korrigierten Symbole wurden im vollständigen Lauf praktisch bestätigt: `BNY` an Position 99 und `ROP.SW` an Position 149 wurden jeweils beim ersten Versuch erfolgreich gespeichert.
- Nach drei vollständigen Läufen liegen 970 Prognosen und 4.850 Horizontzeilen vor. Noch keine Auswertung ist fällig; das automatisch erneuerte Kalibrierungsprofil bleibt deshalb bei null Fällen, Reifegrad `collect_only`, null Vorschlägen und unveränderten Produktionsregeln beziehungsweise -gewichten.
- Abschlussprüfung erfolgreich: marktfreie Vorprüfung mit 325 eindeutigen Assets, Schema 4, Datenbank-Quick-Check `ok`, 970 Prognosen, null Auswertungen, keinem Marktabruf und keinem Schreib- oder Löschvorgang; alle 25 Prognosesystemtests und der Repository-Sicherheitscheck bestanden, `git diff --check` meldete keine Fehler.
- Der direkte lesende Aufgabenplanerabruf bleibt in dieser Sitzung wegen Windows-Fehler `0x80070003` nicht verfügbar. Der planmäßige Start und Abschluss sind unabhängig über Wrapper-Marker, Runner-Log und SQLite vollständig belegt.
- Roadmap ausschließlich dokumentarisch um das verbindliche Zielbild eines bedienungsarmen regelbasierten Swing-Trade-Assistenten erweitert; kein Programmcode, keine Historie und keine Produktionsdaten geändert.
- Bereits umgesetzte Grundlage ausdrücklich übernommen: 1.124 aktive Assets einschließlich ServiceNow, mehrstufiger Scan, höchstens 60 Tiefenanalysen, harte Kein-Trade-Regel, zwei Long-Setups, Tradingkapital als einzige Normaleingabe, konservatives Risikomodell, Struktur-/Volatilitäts-Stop, Positionsgröße, einmaliger Verlusthinweis und lokale Paper-Basis.
- Offene Arbeit in Phasen A bis G geordnet: Order-/Währungs-/Stop-Stabilität, Universum und Datenqualität, eigener Swing-Hintergrundbetrieb, append-only Forward-Test, Trade-Archiv und Statistik, persönlicher Nutzertrade mit regelbasierter Begleitung sowie langfristige Validierung.
- Widersprüche geklärt: Der heutige Nutzerstart ist nicht mit dem geplanten Hintergrundscan gleichgesetzt; die bestehende Journal-Basis ist noch kein vollständiges unveränderbares Archiv; feste 1-/3-/6-/12-Monats-Reviews ersetzen keine genaue Intraday-Trade-Auswertung; `Trade getätigt` bestätigt künftig nur eine externe Nutzerhandlung und löst keine Order aus.
- Verbindliche Reihenfolge und prüfbare Abnahmekriterien für Orderplan, Einstiegsmethoden, FX-Snapshots, responsive Karten, Metadaten, Scanbetrieb, Signalstatus, Datenqualität, realistische Ereignisreihenfolge, Archiv, Statistik, Paper-/Nutzertrennung und aktive Begleitung ergänzt.
- Hebelprodukte, Short-/Absicherungssetups, Broker-Anbindung und automatische Orderausführung bleiben ausgeschlossen. Ein separater Hebelmodus darf erst nach großer belastbarer echter Forward-Historie neu entschieden und zunächst nur im Paper-Betrieb untersucht werden.
- Keine Tests des Programmcodes ausgeführt, da diese Einheit ausschließlich `ROADMAP.md` ändert. Dokumentations- und Git-Diff-Prüfungen erfolgen als Abschluss dieser Einheit; kein Commit und kein Push.

### 2026-08-03

- Zweiten vollständigen planmäßigen Hintergrundlauf live und ausschließlich lesend bis zum regulären Ende überwacht. Wrapper-Start 22:30:02 Uhr, SQLite-Start 22:30:13 Uhr, Ende 22:45:00 Uhr und Wrapper-Exit 0 sind konsistent dokumentiert.
- Alle 325 Assets verarbeitet: 323 Prognosen gespeichert, zwei isolierte Fehler (`BK`, `ROG.SW`), keine Rate-Limits, 0,62 % Fehlerquote, 887,17 Sekunden Laufzeit, 21,98 Assets pro Minute, 3.502.080 Byte Datenbankwachstum und Datenbankstatus/Integrität `ok`.
- Gegenüber dem Vortag wurde `SO` erfolgreich verarbeitet; die wiederkehrenden Fehler wurden anschließend über die öffentliche Yahoo-Suche diagnostiziert. Yahoo führt Bank of New York Mellon als `BNY` und Roche Zürich als `ROP.SW`; beide Ersatzsymbole lieferten jeweils ungefähr 250 aktuelle Tageszeilen.
- Versionierte Prognosekonfiguration für künftige Läufe sicher von `BK` auf `BNY` und von `ROG.SW` auf `ROP.SW` korrigiert. Historische SQLite-Läufe und Fehlereinträge blieben unverändert erhalten; keine Prognose oder Auswertung wurde gelöscht.
- Regressionstest hält die beiden neuen Symbole fest und sperrt die alten im 325-Asset-Prognoseuniversum. Marktfreie Vorprüfung danach: 325 eindeutige Assets, 236 Aktien, 59 ETFs, 30 Kryptowährungen, Schema 4, Datenbank-Quick-Check `ok`, 645 Prognosen, null Auswertungen, kein Marktabruf, kein Schreibvorgang und keine Datenlöschung. Alle 25 Prognosesystemtests bestanden.
- Kalibrierungsprofil nach dem Lauf automatisch und atomar aktualisiert: weiterhin null fällige ausgewertete Fälle, Reifegrad `collect_only`, keine Vorschläge und keine automatische Änderung von Produktionsgewichten oder Regeln.
- Der direkte lesende Aufgabenplanerabruf war in dieser Sitzung wegen Windows-Fehler `0x80070003` nicht verfügbar. Tatsächlicher Start und Abschluss sind jedoch unabhängig über Wrapper-Marker, laufenden Prozess, Runner-Log und SQLite vollständig belegt.
- Kein Commit, kein Push, keine Broker-Verbindung und keine Order ausgeführt.

### 2026-08-02

- Ersten vollständigen planmäßigen Hintergrundlauf nachträglich als neue Betriebsbasis dokumentiert: Start 22:30 Uhr ohne geöffnete App, 325 Positionen verarbeitet, 322 Prognosen gespeichert, drei isolierte Datenfehler (`SO`, `BK`, `ROG.SW`), keine Rate-Limit-Fehler, 0,92 % Fehlerquote, rund 23 Minuten Laufzeit, SQLite-Integrität `ok` und reguläres Windows-Ende mit Code 0.
- Aus den 322 erfolgreichen Snapshots sind 1.610 offene Forward-Auswertungen über fünf Horizonte entstanden; sie werden nicht als zusätzliche Assets missverstanden. Die ersten 322 Ein-Wochen-Fälle werden ab 2026-08-09 fällig.
- Roadmap für ein echtes kontrolliertes Lernsystem vollständig erweitert: wiederkehrender 325-Referenzkern, ungefähr 1.500 bis 2.500 Assets in fünf festen Wochenkohorten, tägliche Fälligkeitsprüfung bei nur wöchentlicher Neuprognose je regulärem Asset, Point-in-Time-Datenvertrag, modelltypische Labels, Benchmarks, Kosten, statistische Unsicherheit und Bias-/Leakage-Schutz.
- Trainings- und Freigabepfad als L0 bis L5 definiert: zeitliche Walk-Forward-Prüfung, horizon-spezifische Modelle, Wahrscheinlichkeitskalibrierung, Champion-Challenger-/Shadow-Betrieb, Modellregister, manuelle Freigabe, Canary, Rollback, Drift-Überwachung und kontrolliertes Nachtraining.
- Verbindlich klargestellt: 20/50 Fälle bleiben frühe Hinweisgrenzen und reichen nicht für produktives Lernen. `Hohe Wahrscheinlichkeit` benötigt ausreichend große kalibrierte ungesehene Stichproben; unzureichende Evidenz führt zu `keine belastbare Empfehlung`. Mehr Daten allein und eine einzelne gute Trefferquote gelten nicht als Lernnachweis.
- Tatsächliche Priorität nach dem erfolgreichen Erstlauf angepasst: statt nochmals denselben Erstlauf zu planen, sind nun wiederkehrende Wochenstichprobe und Point-in-Time-Messvertrag die nächste Grundlage für belastbare Lernfähigkeit. Keine Code-, Score-, Zeitplan- oder Produktionsmodelländerung wurde in dieser Dokumentationseinheit vorgenommen.
- Dokumentationsprüfung bestanden: alle neuen Lernsystem-Abschnitte und Akzeptanzkriterien vorhanden, UTF-8-Inhalt ohne Mojibake, `git diff --check` ohne Fehler. Keine Code-Tests ausgeführt, weil ausschließlich `ROADMAP.md` und `PROJECT_STATUS.md` in dieser Einheit inhaltlich geändert wurden.
- Phase-3-Grundlage vorgezogen, während der zeitgebundene 325-Asset-Produktionslauf auf 22:30 Uhr wartet: `long_term_analysis.py` definiert eine eigenständige Modellart und -version sowie einen reinen Quellen-, Evidenz- und Bereitschaftsvertrag für die geplante Long-Term-Analyse.
- Zehn verbindliche Long-Term-Bereiche werden getrennt geprüft. Geschäftsmodell, Umsatzmodell, Management/Kapitalverwendung, Finanzqualität und Risiken verlangen offizielle Primärquellen; Markt und Wettbewerb benötigen unabhängige belastbare Belege, und Wettbewerb, Szenarien sowie These/Widerlegung benötigen mehrere Quellen.
- Fehlende, ungültige, doppelte oder nicht auflösbare Quellen bleiben sichtbare Lücken. URL, Herausgeber, Abrufzeitpunkt und Verwendungszweck sind Pflicht; Yahoo Finance, allgemeine News und sonstige Kontextquellen können keine Long-Term-Freigabe erzeugen.
- Technische Einstiegsevidenz ist ausdrücklich vom Long-Term-Gate ausgeschlossen und kann weder Pflichtabdeckung noch Quellenkennzahlen verbessern. Das Modul erzeugt noch keinen Score, keine Empfehlung und keine UI-Freigabe.
- Neun isolierte Long-Term-Tests sichern Leerzustand, Yahoo-only-Ablehnung, vollständige Primär-/Unabhängigen-Abdeckung, strengere Wettbewerbsanforderung, fehlende Referenzen, Quellenmetadaten, doppelte Quellen-IDs, Techniktrennung, Provenienz und Nicht-Mutation ab.
- Vollständige lokale Prüfkette nach der Long-Term-Quellengrundlage erfolgreich: 186 Pytest-Tests, Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung bestanden.
- Sichere lokale Ablage für künftige Long-Term-Quellen ergänzt: `long_term_research_cache.py` verwendet ein festes Schema, Modellart/-version, zeitzonenbehaftete Sammel- und Ablaufzeitpunkte sowie atomaren Dateiaustausch unter dem bereits privaten `runtime/`-Pfad.
- Ungültige oder doppelte Quellen, leere Aussagen, unbekannte Quellreferenzen, falsche Modellversionen und neuere unbekannte Schemata werden vor Verwendung abgelehnt. Ein gescheiterter atomarer Austausch erhält den bisherigen Cache unverändert.
- Veraltete Cache-Daten werden nicht gelöscht und bleiben diagnostizierbar, gelten aber ausdrücklich als nicht verwendbar. Unsichere Tickerzeichen werden in einen stabilen, pfadsicheren Dateinamen mit Hashzusatz überführt.
- Acht isolierte Cache-Tests sichern Pfadsicherheit, frischen Roundtrip mit Provenienz, Stale-Sperre ohne Mutation, fehlende/beschädigte Dateien, Zukunftsschema, Validierung, atomaren Austauschschutz und Zeitzonen-/Ablaufregeln ab.
- Vollständige lokale Prüfkette nach Quellenvertrag und Cache-Grundlage: 194 Pytest-Tests bestanden.
- Weitere Phase-3-/PRIO-C-Trennung umgesetzt: Preisattraktivität und der transparente aktuelle Fundamentalvergleich seit dem historischen Kurshoch aus `app.py` nach `price_attractiveness.py` extrahiert. Die App reexportiert beide bisherigen Funktionsnamen; Gewichtung, Grenzwerte und sichtbare Texte bleiben unverändert.
- Fünf direkte Tests sichern App-Kompatibilität, positive/negative/fehlende Fundamentalsignale, den nur bei intakter aktueller Datenlage erlaubten Kursrückgangsbonus, die Regel gegen ein automatisches Kaufsignal aus dem Hochabstand, Asset-Typ-Kontext und Nicht-Mutation ab.
- Vollständiger Pytest-Stand nach der Preisattraktivitäts-Extraktion: 199 Tests bestanden; `app.py` sank ohne Funktionsverlust auf 9.329 Zeilen und 231 eigene Top-Level-Funktionen.
- Bewertungsmodul als nächste Phase-3-/PRIO-C-Grundlage nach `valuation_analysis.py` extrahiert. Aktien-, ETF- und Krypto-Pfade, alle bisherigen Multiple-Grenzen, neutrale Leerzustände und Transparenztexte bleiben unverändert; `app.py` reexportiert die Funktion kompatibel.
- Fünf direkte Bewertungstests sichern vollständige Aktien-Multiple-Beiträge, Nicht-Mutation, neutrale nicht endliche oder fehlende Werte, Krypto-Makrokontext ohne erfundene On-Chain-Daten und fehlende ETF-Indexbewertung ab.
- Vollständiger Pytest-Stand nach der Bewertungsextraktion: 204 Tests bestanden; `app.py` umfasst nun 9.179 Zeilen und 230 eigene Top-Level-Funktionen.
- Zukunftspotenzial und eingepreiste Erwartungen als weitere Phase-3-/PRIO-C-Einheit nach `future_potential_analysis.py` extrahiert. Bestehende Qualitäts-, Wachstums-, Margen-, Bewertungs-, Momentum- und News-Beiträge sowie alle Datenlückentexte bleiben unverändert; beide App-Schnittstellen werden kompatibel reexportiert.
- Fünf direkte Tests sichern Beitragsrechnung, positive/negative News-Wirkung, nicht endliche Wachstumsdaten, Krypto-Datenlücken, hohe/niedrige eingepreiste Erwartungen, fehlende Spezial-Sentimentdaten und Nicht-Mutation ab.
- Vollständiger Pytest-Stand nach dieser Extraktion: 209 Tests bestanden; `app.py` umfasst 9.096 Zeilen und 228 eigene Top-Level-Funktionen.
- Szenario-Wahrscheinlichkeiten und Expected-Value-Modul als weitere Analyse-Domain nach `scenario_analysis.py` extrahiert. Kaufsignal-, Qualitäts-, CRV-, Marktphasen-, Trend-, Marken- und Volatilitätsbeiträge sowie konservative Fallback-Renditen bleiben unverändert; App-Schnittstellen werden kompatibel reexportiert.
- Fünf direkte Tests sichern App-Kompatibilität, 100-Prozent-Summe, Mindest-Basisfall, starke/schwache Marktstruktur, reale Unterstützungs-/Widerstandsgeometrie, konservative Fallbacks und Nicht-Mutation ab.
- Vollständiger Pytest-Stand nach der Szenarioextraktion: 214 Tests bestanden; `app.py` umfasst 8.987 Zeilen und 226 eigene Top-Level-Funktionen.
- Szenario-Domain vervollständigt: numerische Bull-/Basis-/Bear-Marken und die sichtbaren Szenariozeilen ebenfalls nach `scenario_analysis.py` verschoben. Sichtbare Analyse und Hintergrundprognose verwenden damit weiterhin dieselbe zentrale Zielstruktur, nun außerhalb des UI-Monolithen.
- Zwei zusätzliche Tests sichern Filterung von Marken auf der falschen Kursseite, Score-abhängiges Basisziel, Nicht-Mutation, identische sichtbare Kursziele und vollständige 100-Prozent-Wahrscheinlichkeiten ab.
- Vollständiger Pytest-Stand nach der vollständigen Szenarioextraktion: 216 Tests bestanden; `app.py` umfasst 8.921 Zeilen und 224 eigene Top-Level-Funktionen.
- Entry-Plan-Domain als klare Phase-3-Trennung nach `entry_plan.py` extrahiert: Kaufzonen, technische Aktionskategorien, Confidence-Bezeichnung, asset-typischer Horizont und Gültigkeitslogik liegen nun außerhalb der UI. Bestehende Marken, Schwellen und Texte bleiben unverändert.
- Elf direkte Tests sichern App-Reexporte, reale Kauf-/Bestätigungs-/Widerlegungsmarken, ehrliche Leerzustände, alle Aktionsschwellen, Confidence/Horizont und die Regel, dass nur zukünftige Earnings die maximal 30-tägige Gültigkeit verkürzen, ab.
- Vollständiger Pytest-Stand nach der Entry-Plan-Extraktion: 227 Tests bestanden; `app.py` umfasst 8.824 Zeilen und 219 eigene Top-Level-Funktionen.
- Deterministische Long-Term-Bewertungs- und Szenariogrundlage in `long_term_scoring.py` ergänzt. Ein Score ist nur nach vollständigem, versionskompatiblem Quellengate möglich; sieben getrennte Faktoren behalten sichtbare Gewichte und müssen ihre jeweils erforderlichen freigegebenen Evidenzbereiche nennen.
- Bear-, Basis- und Bull-Szenario verlangen vollständige Bedingungen, zusammen 100 Prozent Wahrscheinlichkeit, logisch geordnete positive Zielwerte und einen ganzzahligen Horizont von drei bis sieben Jahren. Erwarteter Zielwert, Gesamtrendite und annualisierte Rendite werden rein mathematisch berechnet; fehlende oder nicht endliche Werte werden abgelehnt.
- Technisches Einstiegstiming ist in der Long-Term-Bewertung ausdrücklich verboten und kann Unternehmensqualität, Zukunftspotenzial, Bewertung oder Schutz vor dauerhaftem Kapitalverlust nicht verbessern. Das Modul erzeugt noch keine Kauf-/Verkaufsempfehlung und ist nicht mit UI oder echten Quellenadaptern verbunden.
- Vierzehn neue Scoring-Fälle sichern Quellengate, Teil-/Gesamtscores, Renditerechnung, Techniktrennung, Pflichtfaktoren, Zahlenbereiche, Horizont, Szenarioregeln und Nicht-Mutation. 31 gezielte Long-Term-Tests sowie der vollständige lokale Stand mit 241 Pytest-Tests bestanden.
- Bestehende Empfehlungssynthese als weitere Phase-3-/PRIO-C-Domain unverändert aus `app.py` nach `recommendation_synthesis.py` verschoben. Langfristigkeit, Preisattraktivität, Timing, Datenqualität und optionaler Depot-Effekt werden weiterhin mit identischen Kategorien, Schwellen, Texten, Tranchierungen und Widerlegungsregeln verbunden; die App reexportiert beide bisherigen Entscheidungsfunktionen.
- Zwei zusätzliche Tests sichern die kompatiblen App-Schnittstellen und den älteren professionellen Entscheidungsvertrag. Alle 21 Empfehlungssynthese-Tests sowie der vollständige lokale Stand mit 243 Pytest-Tests bestanden; `app.py` umfasst nun 8.336 Zeilen und 217 eigene Top-Level-Funktionen.
- Long-Term-Evidenzvertrag auf Modellversion 2 erweitert: je Quellentyp gelten nachvollziehbare Höchstalter, aktuelle Markt-/Börsendaten veralten schneller als Jahresberichte und strukturelle Branchenstudien. Ein vorhandener Veröffentlichungszeitpunkt ist für das Alter maßgeblich, sodass erneuter Download ein altes Dokument nicht künstlich aktualisiert.
- Zeitlich widersprüchliche Abrufe werden abgelehnt: Abrufzeitpunkte benötigen eine Zeitzone und dürfen höchstens innerhalb einer kleinen Uhrtoleranz in der Zukunft liegen. Veraltete und zukünftige Quellen-IDs bleiben im Bereitschaftsbericht getrennt sichtbar und können keine Pflichtabdeckung erzeugen.
- Der Long-Term-Cache prüft dieselben Altersregeln bereits beim Schreiben. Ein später abgelaufener, ursprünglich gültiger Cache bleibt weiterhin diagnostizierbar, ist aber nicht verwendbar; bereits veraltete Quellen gelangen gar nicht erst in einen neuen Cache.
- Drei neue Quellenaktualitätsfälle und ein Cache-Fall sichern alte Veröffentlichung trotz frischem Abruf, unterschiedliche Alter je Quellentyp, Zukunfts-/Zeitzonenfehler und Schreibablehnung veralteter Quellen. 35 gezielte Long-Term-Tests sowie der vollständige lokale Stand mit 247 Pytest-Tests bestanden.
- Ersten echten Primärquellenadapter als sichere, noch inaktive Phase-3-Grundlage ergänzt: `sec_filing_sources.py` löst exakte US-Ticker über die offizielle SEC-Ticker-/CIK-Datei auf und entdeckt über die öffentliche Submissions-API aktuelle 10-K-, 20-F-, 40-F- und 10-Q-Dokumente.
- EDGAR-Dokumentadressen und stabile Quellen-IDs werden nur aus streng validierter CIK, Accession Number und einfachem Dokumentnamen gebildet. Alte Dokumente, unvollständige SEC-Spalten, unbekannte Ticker und Pfadmanipulationen erzeugen keine scheinbare Quelle.
- SEC-Fair-Access ist technischer Vertrag: ein echter Abruf verlangt einen nur zur Laufzeit übergebenen Namen plus Kontaktadresse; diese Kennung wird nicht in `LongTermSource`, Cache oder Statusobjekt aufgenommen. Ein prozesslokaler Client serialisiert Anfragen mit mindestens 0,12 Sekunden Abstand und lädt die Ticker-/CIK-Datei je Prozess nur einmal. Ein atomarer öffentlicher JSON-Cache bewahrt die Tickerdatei 24 Stunden und einzelne Submissionsdateien sechs Stunden über Prozessneustarts. Begrenztes Retry/Backoff ist vorhanden; bis zu einer prozessübergreifenden Begrenzung bleibt der Adapter dennoch außerhalb von Batch- und Hintergrundbetrieb.
- Der Adapter liefert ausschließlich überprüfbare Quellenmetadaten. Er formuliert keine Belegaussage und kann daher allein weder das Long-Term-Gate öffnen noch einen Score oder eine Empfehlung erzeugen; unabhängige Markt-/Wettbewerbsquellen fehlen weiterhin.
- Zehn isolierte SEC-Adapterfälle sichern Ticker-/CIK-Zuordnung, offizielle Archiv-URLs, unterstützte Jahres-/Quartalsformulare, Klassen- und unbekannte Ticker, Stale-Filter, Fair-Access-Headervertrag, defekte Antworten, Pfadsicherheit und Nicht-Mutation. Vollständiger lokaler Stand: 257 Pytest-Tests bestanden.
- Vier zusätzliche Fair-Access-Client-Fälle sichern den Mindestabstand, einmalige Tickerdatei je Prozess, kopierte Cache-Ausgabe, erneuten Versuch nach Fehler und unveränderliche Kontaktkennung. Alle 14 SEC-Tests sowie der vollständige lokale Stand mit 261 Pytest-Tests bestanden.
- Persistenten SEC-JSON-Cache in `sec_json_cache.py` ergänzt. Nur die feste offizielle Ticker-/CIK-Datei und streng formatierte einzelne Submissions-URLs erhalten pfadsichere Cache-Dateien; die Fair-Access-Kontaktkennung ist kein Bestandteil des Dokuments.
- Tickerzuordnung gilt 24 Stunden, einzelne Submissionsdaten sechs Stunden. Beschädigte, zu alte, zukünftig datierte, fremde oder aus einer neueren Schemaversion stammende Dateien werden nie ausgeliefert; ein fehlgeschlagener atomarer Austausch erhält die bisherige Datei, während ein erfolgreicher Netzabruf trotz Cache-Schreibfehler nutzbar bleibt.
- Sieben isolierte Persistenztests sichern URL-/Pfad-Whitelist, öffentlichen Roundtrip ohne Kontaktkennung, Netzvermeidung über Prozessgrenzen, Kopierschutz, getrennte TTLs, Defekt-/Zukunfts-/Schemaregeln und Austauschschutz. Zusammen 21 SEC-Fälle und vollständiger lokaler Stand mit 268 Pytest-Tests bestanden.
- Strukturierte SEC-Company-Facts-Grundlage in `sec_financial_facts.py` ergänzt. Sie liest ausschließlich sechs klar definierte US-GAAP-Jahreswerte: Umsatz, Nettoergebnis, operativer Cashflow, Vermögenswerte, Verbindlichkeiten und Zahlungsmittel. Je Kennzahl gilt eine feste dokumentierte Konzeptpriorität, damit alternative Tags nicht addiert oder beliebig vermischt werden.
- Nur abgeschlossene Jahreszeilen aus 10-K/20-F/40-F einschließlich Amendments mit gültigem Zeitraum, Filing-Datum, endlicher Zahl und streng formatierter Accession Number werden akzeptiert. Quartalsdaten, Zukunftswerte, `NaN`/Unendlich und ungültige Referenzen bleiben Lücken; es werden noch keine Wachstumsraten oder Qualitätsurteile abgeleitet.
- Ein strukturierter Zahlenwert wird nur dann zu `financial_quality`-Evidenz, wenn eine zuvor entdeckte offizielle SEC-Jahresberichtquelle exakt dieselbe Accession Number im Dokumentpfad trägt. Ohne passende Filing-Provenienz entsteht keine Aussage und das offene Aktenzeichen bleibt sichtbar.
- Company-Facts-JSON ist als dritte fest freigegebene SEC-Adresse im atomaren sechs-Stunden-Cache aufgenommen. Sechs isolierte Finanzfaktenfälle sichern neueste Jahreswerte, Konzeptpriorität, Filter, Leerzustand, exakte Quellenverknüpfung und Nicht-Mutation. Zusammen 27 SEC-Fälle und vollständiger lokaler Stand mit 274 Pytest-Tests bestanden.
- Nicht schreibende SEC-Teilkollektion in `sec_long_term_collection.py` ergänzt. Sie verbindet exakte Tickerauflösung, Filing-Discovery, Company Facts, Accession-verknüpfte Finanz-Evidenz und den normalen Long-Term-Bereitschaftsbericht in einem Ergebnis, ohne Cache/Evidenzdatei, Score oder UI zu verändern.
- Ein fehlender SEC-Tickertreffer beendet die Kette vor weiteren Unternehmensabrufen. Ein Company-Facts-Fehler erhält bereits entdeckte offizielle Quellen, erzeugt jedoch keine Finanzbehauptung; eine abweichende Accession Number bleibt sichtbar unverbunden. Auch korrekt belegte Finanzqualität öffnet das Gesamtgate nicht, solange die neun übrigen Pflichtbereiche fehlen.
- Vier isolierte Integrationsfälle sichern vollständige Teilkollektion, weiterhin geschlossenes Gate, frühen Stopp, Teilausfall, falsche Accession und Nicht-Mutation. Zusammen 31 SEC-Fälle und vollständiger lokaler Stand mit 278 Pytest-Tests bestanden.
- SEC-Finanzfakten um rein sachliche Zwei-Jahres-Vergleiche erweitert. Je Kennzahl werden die zwei neuesten gültigen Jahreswerte desselben priorisierten XBRL-Konzepts verwendet; Doppelte derselben Periode/Accession werden nicht mehrfach gezählt.
- Vergleichsevidenz verlangt beide exakt passenden offiziellen Jahresberichtquellen und nennt beide Perioden und Werte. Eine Prozentänderung wird nur bei positivem Vorjahreswert berechnet; bei null oder negativem Basiswert bleibt es beim absoluten Vergleich, ohne irreführende Wachstumszahl und ohne Qualitätsurteil.
- Drei neue Vergleichsfälle sichern vollständige Zwei-Filing-Provenienz, rechnerische Änderung ohne wertende Sprache, nicht positive Basis und fehlende Vorjahresquelle. Zusammen 34 SEC-Fälle und vollständiger lokaler Stand mit 281 Pytest-Tests bestanden.
- Sicheren manuellen Einstiegspunkt `scripts/collect_long_term_sources.py` ergänzt. `--preflight` prüft ausschließlich, ob der SEC-Fair-Access-Kontakt zur Laufzeit gültig konfiguriert und der Cachepfad innerhalb des privaten `runtime/`-Verzeichnisses liegt; dabei erfolgen weder Netzwerk- noch Schreibzugriffe.
- Der Live-Weg verlangt weiterhin einen exakten Ticker und `INVESTMENT_ASSISTANT_SEC_USER_AGENT` mit Projektname/Kontaktadresse. Die Kontaktkennung wird weder in JSON-Ausgabe noch Cache, Quelle oder Status aufgenommen. Ohne Konfiguration endet die CLI vor jedem Netzabruf; kein Standardzeitplan oder Windows-Task wurde angelegt.
- Vier isolierte CLI-Fälle sichern offline Vorprüfung, fehlende/gültige Kontaktkonfiguration ohne Wertausgabe, privaten Cachepfad und kontaktfreie Live-Ausgabe. Reale Vorprüfung bestätigte `configuration_required`, `network_requested: false`, `data_written: false`; zusammen 38 SEC-Fälle und vollständiger lokaler Stand mit 285 Pytest-Tests bestanden.
- Bestehende Datenqualitäts-Domain als weitere PRIO-A/PRIO-C-Einheit aus `app.py` nach `data_quality_analysis.py` verschoben. Externe Stammdaten-/FX-/News-/Makrowarnungen, Grün-/Gelb-/Rot-Schwellen sowie Ticker-, Typ-, Börsen-, Währungs-, Historien-, Volumen- und Durchschnittsprüfung bleiben über identische App-Schnittstellen erhalten.
- Direkter Leerzustandstest deckte einen realen Stabilitätsfehler auf: Nach korrekt gemeldeter fehlender Kurstabelle griff die Funktion für die 200-Tage-Prüfung dennoch auf die nicht vorhandene `Close`-Spalte zu. Der Pfad prüft die Spalte jetzt vor `dropna` und liefert stattdessen die vorhandenen transparenten Datenlücken.
- Sechs direkte Datenqualitätstests sichern App-Reexporte, vollständige/fehlende externe Quellen, Ampelschwellen, vollständige Historie, Nicht-Mutation und leere Kurstabellen. Informationshierarchie-/Empfehlungstests sowie der vollständige lokale Stand mit 291 Pytest-Tests bestanden; `app.py` umfasst nun 8.238 Zeilen und 214 eigene Top-Level-Funktionen.
- Transparente Score-Zusammensetzung als nächste kleine PRIO-C-Einheit nach `score_composition.py` extrahiert. Gewichtstabellen, Beschreibungen, Standardbeiträge aus Technik/Fundamentaldaten/Makro/News/CRV, Rundung und neutrale optionale Mittelwerte bleiben unverändert; `app.py` reexportiert die drei bisherigen Schnittstellen.
- Fünf direkte Tests sichern Reihenfolge und Prozentanzeige, den exakten bisherigen Standardgesamtwert, benutzerdefinierte Gewichte ohne Mutation sowie leere und gerundete optionale Werte. Stabilitätsteilmenge und vollständiger lokaler Stand mit 296 Pytest-Tests bestanden; `app.py` umfasst nun 8.195 Zeilen und 211 eigene Top-Level-Funktionen.
- SEC-Transportfehlerbehandlung vervollständigt: HTTP 429 sowie vorübergehende 5xx- und Verbindungsfehler erhalten höchstens drei Gesamtversuche mit 0,5-/1,0-Sekunden-Backoff beziehungsweise einem auf 0,1 bis 5 Sekunden begrenzten `Retry-After`. Es gibt keine Endlosschleife.
- Dauerhafte HTTP-Fehler werden sofort mit Statuscode beendet; ungültiges UTF-8-/JSON wird nicht erneut angefragt. Keine Fehlermeldung enthält die Fair-Access-Kontaktkennung. Drei direkte Transportfälle sichern Retry-Erfolg, sofortiges HTTP-404-Ende und JSON-Ablehnung; zusammen 41 SEC-Fälle und vollständiger Stand mit 299 Pytest-Tests bestanden.
- Priorität begründet: Die Quellenqualität ist PRIO-A-Grundfähigkeit und zugleich eine sichere Voraussetzung für Phase 3; der unverändert höher priorisierte reale Hintergrundlauf kann erst zum geplanten Termin betrieblich validiert werden.
- Diagnose vor dem nächsten 325-Asset-Lauf verschärft: Der Hintergrund-Runner protokolliert Konfigurations-/Pfadprüfung vor dem Laden des Universums und jeden begonnenen Asset-Versuch mit Ticker, Position und Versuchszahl.
- Ungültige Universen ohne verwendbaren Ticker werden jetzt ausdrücklich abgelehnt. Startfehler werden im rotierenden Laufprotokoll festgehalten und der Logger wird weiterhin auch bei Fehlern zuverlässig geschlossen.
- Drei Regressionstests für leeres Universum, protokollierten Startfehler und Fortschrittsprotokoll vor einem harten simulierten Abbruch ergänzt; alle 22 Prognosesystemtests bestanden.
- Vollständige lokale Prüfkette nach Runner-, Wrapper-, Vorprüfungs- und Doppellaufschutz-Ausbau erfolgreich: 150 Pytest-Tests, Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung bestanden.
- Kleine PRIO-C-Architekturpflege während der Wartezeit auf den Produktionslauf: Laden, Normalisieren und reine Bewertung optionaler Portfolio-Daten aus `app.py` nach `portfolio_analysis.py` extrahiert. Streamlit, Yahoo-Kursfallback und alle bisherigen App-Schnittstellen bleiben unverändert angebunden.
- Fünf isolierte Portfolio-Tests belegen read-only Laden, ungültige Dokumente, defensive Positionsauswahl, gespeicherte beziehungsweise injizierte Kurswerte, Klumpen-/Kryptoabschläge und App-Kompatibilität. Vollständige Prüfkette danach: 155 Pytest-Tests, Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung bestanden.
- Zweite kleine PRIO-C-Architektureinheit umgesetzt: deutsche Geldformatierung, EUR-Umrechnung sowie Kursreihen- und Chartmarkenumrechnung aus `app.py` nach `currency_utils.py` extrahiert. Bestehende App-Funktionsnamen, Texte und Umrechnungsregeln bleiben kompatibel.
- Vier isolierte Währungs-/Umrechnungstests ergänzen Format-, Fehlkurs-, Kopie-/Nicht-Mutations- und App-Kompatibilitätsfälle. Vollständige Prüfkette danach: 159 Pytest-Tests, Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung bestanden.
- Phase-3-/PRIO-C-Vorarbeit umgesetzt: vorhandene Aktien- und ETF-Snapshots, Datenlückentexte, Kennzahlgrenzen, Übersichten und Fundamentalscores aus `app.py` nach `fundamental_analysis.py` extrahiert. App-Schnittstellen, Score-Beiträge und sichtbare Texte bleiben kompatibel; Yahoo-Zugriff bleibt außerhalb des reinen Bewertungsmoduls.
- Grenztests deckten einen Datenqualitätsfehler auf: positive und negative unendliche Zahlen wurden bisher als gültige Marktwerte angenommen. Die zentrale Normalisierung behandelt jetzt `NaN`, `+∞` und `−∞` einheitlich als nicht verfügbar, damit daraus keine künstlichen Extrem-Scores entstehen.
- 18 direkte Fundamentaltests sichern Snapshot-Normalisierung, sämtliche Profitabilitäts- und Bewertungsgrenzen, neutrale Leerzustände, vollständige Aktien-/ETF-Scorebeiträge, ETF-Feldvarianten, Nicht-Mutation und App-Kompatibilität ab. Vollständige Prüfkette danach: 177 Pytest-Tests, Kompilierung, Repository-Sicherheitscheck, Offline-Smoke-Test einschließlich Headless-Streamlit-Start und Git-Diff-Prüfung bestanden.
- Den echten Windows-Wrapper nach den Moduländerungen erneut markt- und prognosefrei geprüft: Exit 0, 325 eindeutige Assets, Schema 4, SQLite-Integrität `ok`, 0 Prognosen/0 Auswertungen, keine Marktabfrage, kein Datenschreib- oder Löschvorgang. Die Aufgabe blieb `Ready`, aktiviert und für 22:30 Uhr mit Aufwecken, verspätetem Start, drei Neustarts sowie `IgnoreNew` konfiguriert.
- Vollständigen Hintergrund-Snapshot-Pfad nach der Fundamental-Extraktion einmalig mit echten NVDA-Daten geprüft, ohne Datenbank- oder Prognoseschreibvorgang: Aktie korrekt erkannt, Modelltyp `entry_analysis`, Logikversion `2026.08.01-v1`, fünf Horizonte, 17 Modulwerte, verfügbarer Kurs und grüne Datenqualität. Der erste Versuch war nur durch den eingeschränkten Netzwerkmodus blockiert; mit freigegebenem Yahoo-Zugriff war derselbe Pfad erfolgreich.
- Äußere Betriebsbedingungen vor dem 22:30-Lauf rein lesend geprüft: benötigter Wrapper, lokale Python-Umgebung, Konfiguration, Universum und Laufzeitverzeichnis vorhanden; ausreichend freier Speicher; Netzbetrieb aktiv; automatischer Standby im aktuellen Energieplan für Netz- und Akkubetrieb deaktiviert und Aufwecktimer für beide Betriebsarten aktiviert. Die detaillierte Aufwecktimer-Liste selbst verlangt Administratorrechte, die bereits geprüfte Aufgabenoption `WakeToRun` bleibt aktiv.
- Windows-Wrapper-Diagnose ergänzt: `scripts/run_forecasts.cmd` schreibt Prozessgrenzen und den unveränderten Python-Rückgabecode nach `runtime/logs/forecast_task_wrapper.log`; Kommandozeilenargumente werden für kontrollierte Wartungsprüfungen weitergereicht.
- Wrapper mit der nicht löschenden Datenbankwartung real geprüft: Start und Ende wurden protokolliert, Rückgabecode 0, Datenbankintegrität `ok`, 0 Prognosen/0 Auswertungen und `data_deleted: false`.
- Windows-Systemereignisse rund um den alten Abbruch nur lesend geprüft: Modern-Standby-Wechsel waren kurz vor 22:30 Uhr vorhanden, aber kein Anwendungsabsturz oder eindeutiger Beleg für die Ursache von `0xC000013A`. Der nächste echte Lauf bleibt deshalb entscheidend.
- Neuer Wrapper-Vertragstest ergänzt; alle 23 Prognosesystemtests bestanden.
- Marktfreie Laufzeit-Vorprüfung `--preflight` ergänzt: validiert Konfiguration, Startzeit, numerische Laufparameter, Logikversion, Universum, Schreibpfade und SQLite-Integrität, ohne Yahoo aufzurufen oder Prognosen anzulegen.
- Reale Vorprüfung über denselben Windows-Wrapper erfolgreich: 325 eindeutige Ticker, Schema 4, `quick_check: ok`, 0 Prognosen/0 Auswertungen, keine Marktabfrage, kein Prognoseschreibvorgang, keine Löschung und Rückgabecode 0.
- Zwei neue Vorprüfungstests für einen sicheren gültigen Lauf und die Ablehnung defekter JSON-Konfiguration ergänzt; alle 25 Prognosesystemtests bestanden.
- Doppellaufschutz auf Prozessebene ergänzt: `forecast_lock.py` verwendet unter Windows und Unix eine nicht blockierende Betriebssystem-Dateisperre. Ein zweiter Runner endet vor Datenbank- oder Marktarbeit mit klarer Meldung; ein regulär oder hart beendeter Besitzer hinterlässt keine aktive Sperre.
- Zwei isolierte Sperrtests belegen Ablehnung in einem echten zweiten Python-Prozess, erneute Nutzbarkeit nach Freigabe und Integration vor Datenbank-/Marktarbeit; gemeinsam mit den 25 Prognosesystemtests bestanden 27 Tests.
- Priorität vorgezogen: Der zusätzliche Doppellaufschutz ist PRIO-A-Stabilitätsarbeit, weil die Windows-Regel nur neue Instanzen derselben geplanten Aufgabe verhindert, nicht jedoch einen parallelen manuellen oder extern gestarteten Runner.
- Priorität bleibt unverändert: Der nächste planmäßige vollständige 325-Asset-Lauf muss betrieblich beobachtet werden. Die zusätzliche Diagnose wurde als PRIO-A-Stabilitätsarbeit vorgezogen, weil der vorherige 0-von-325-Abbruch ohne letzten Asset-Hinweis nicht eindeutig lokalisierbar war.
- Automatischen Prognosebetrieb besser beobachtbar gemacht: Prognosequalität zeigt Betriebszustand, letzten Lauf, verarbeiteten Anteil, Fehler und nächsten geplanten Termin; die Startseite warnt kompakt bei einem Fehler.
- Stille Ausfälle werden erkannt: Läufe ohne Aktivität seit mehr als neun Stunden sowie fehlende erwartete Läufe erhalten eine klare Fehlermeldung; mehrere aufeinanderfolgende Problemläufe werden hervorgehoben.
- Neue Tagesläufe bereinigen veraltete Betriebsmetadaten sicher: ältere noch als `running` markierte Läufe werden als `interrupted` dokumentiert, ohne Prognosen, Auswertungen oder private Historien zu löschen.
- Prognosedatenbank-Sicherung umgesetzt: konsistente SQLite-Online-Sicherung mit Integritäts-/Schemacheck und ohne automatische Aufbewahrungs- oder Löschregel. Wiederherstellung schreibt nur in eine neue Datei und verweigert jedes Überschreiben.
- Erste lokale Sicherung der aktuellen Prognosedatenbank erfolgreich erstellt und geprüft; Schema 2, Integrität `ok`, 0 Prognosen, keine Daten gelöscht.
- Zwei neue Sicherungstests und 15 Prognosesystemtests gemeinsam bestanden; Sicherungsmodul und CLI kompiliert.
- Datenbankschema 3 ergänzt: Laufzeit, Assets pro Minute, Fehlerquote, Rate-Limit-Anzahl, Datenbankgröße/-wachstum und Integritätsstatus werden nach jedem Lauf dauerhaft gespeichert statt nur in der Logdatei zu stehen.
- Prognosequalitätsansicht zeigt die gespeicherten Betriebskennzahlen verständlich an. Migration ist idempotent und bewahrt vorhandene Läufe; reales SQLite-Schema erfolgreich von 2 auf 3 migriert.
- Neuer Persistenztest ergänzt; Prognosesystem- und Sicherungstests gemeinsam mit 18 bestandenen Tests geprüft.
- Reale Diagnose zum damaligen Zwischenstand: Der planmäßige Lauf vom 2026-08-01 startete um 22:30 Uhr, blieb aber vor dem ersten Asset bei 0 von 325 stehen. Der neue Status erkannte dies. Der darauffolgende vollständige Lauf vom 2026-08-02 ist inzwischen erfolgreich belegt und oben separat dokumentiert.
- Drei isolierte Betriebstests ergänzt; Prognose- und Stabilitätsteilmenge mit 71 bestandenen Tests geprüft.
- Verbindliche Produktarchitektur auf drei getrennte Hauptbereiche erweitert: `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder`, jeweils mit eigener Leitfrage, eigenem Horizont und eigener Bewertungslogik.
- Ist-Stand ehrlich zugeordnet: Die bestehende Aktienanalyse bildet große Teile der Einstiegsanalyse ab; der heutige `Opportunity Scanner` ist die umzusetzende UI-Vorstufe des `Swing Trade Finder`. Eigenständige Long-Term-Analyse und Investment-Opportunity-Feed bleiben geplant.
- Asset-Analyse in zwei Analysearten gegliedert: konkrete Einstiegsanalyse sowie quellenbasierte Long-Term-Analyse für drei bis sieben Jahre. Technische Analyse darf im Long-Term-Modus nur den Einstieg beeinflussen.
- `Investment Opportunities` mit den getrennten Modi und Scores `Aktuell attraktiv` und `Zukunftschancen 3+ Jahre`, strengem Mindestqualitätsfilter, vielfältigem Feed, lokaler Investment-Watchlist und rückgängig machbaren Nutzeraktionen geplant.
- Übergaben verbindlich festgelegt: aktuelle Chancen öffnen die Einstiegsanalyse, Zukunftschancen die Long-Term-Analyse; Nutzerpräferenzen verändern nur den Feed und nie den objektiven Score.
- Gemeinsame dreistufige Informationshierarchie von der bestehenden Einstiegsanalyse auf alle Hauptbereiche erweitert.
- Umsetzungsplan auf sieben Phasen erweitert und Abhängigkeiten ergänzt: Stabilität, Design/Navigation, Asset-Analyse, Investment Opportunities, Swing Trade Finder, automatische Prognosequalität sowie Validierung.
- Nächste Priorität bleibt zuerst die betriebliche Stabilisierung des 325-Asset-Hintergrundlaufs. Danach folgen Navigation/Designsystem und die Trennung der Asset-Analyse, bevor der Investment-Opportunity-Feed gebaut wird.
- Reine Roadmap-Erweiterung; kein Anwendungscode, kein Commit und kein Push.
- Navigationsbasis umgesetzt: Die Startseite trennt jetzt `Asset-Analyse`, `Investment Opportunities` und `Swing Trade Finder`; der bisherige Scannername bleibt nur als kompatibler Session-State-Migrationspfad erhalten.
- `Investment Opportunities` besitzt einen klaren Platzhalter für `Aktuell attraktiv` und `Zukunftschancen 3+ Jahre`, zeigt aber ausdrücklich keine scheinbaren Kandidaten und führt noch keine fachliche Bewertung aus.
- Erste gemeinsame Design-Tokens für Radien, Rahmen, Oberflächen, Schatten und Hauptaktionen ergänzt, ohne Bewertungslogik oder bestehende Funktionen zu verändern.
- Streamlit-AppTest um alle drei Navigationswege, Rücknavigation und den ehrlichen Opportunity-Leerzustand erweitert; vollständiger Testlauf mit 136 bestandenen Tests, Kompilierung, Repository-Sicherheitscheck und Offline-Smoke-Test erfolgreich.
- Sichtbare Browserprüfung begonnen, aber der Zugriff auf die lokale Streamlit-URL wurde durch die Browser-Sicherheitsrichtlinie blockiert. Es wurde kein alternativer Browserweg erzwungen; die sichtbare Desktop-/390-Pixel-Prüfung bleibt deshalb offen.
- PRIO-B-Messgrundlage vorgezogen, während der planmäßige 325-Asset-Lauf noch auf 22:30 Uhr wartet: Datenbankschema 4 ergänzt eine explizite Analyseart pro Prognose, damit Einstiegs-, Long-Term- und Swing-Ergebnisse künftig nicht vermischt werden.
- Bestehende Prognosen werden bei der idempotenten Migration verlustfrei als `Einstiegsanalyse` gekennzeichnet. Die Prognosequalität zeigt eine zusätzliche Auswertung und einen Filter nach Analyseart; der aktuelle Runner speichert ausdrücklich nur `Einstiegsanalyse`.
- Reale Prognosedatenbank erfolgreich auf Schema 4 migriert und mit `quick_check: ok` geprüft; zusätzliche lokale Sicherung unter `runtime/backups/` erstellt, keine Prognose oder Auswertung gelöscht.
- Neuer Migrationstest für Bestandszeilen und Modellindex ergänzt; Prognose- und Stabilitätsteilmenge mit 73 bestandenen Tests geprüft.
- Bedienungsfreie Lernbasis ergänzt: `forecast_calibration.py` erzeugt nach jedem Hintergrundlauf ein versioniertes Profil aus ausschließlich echten Prognoseauswertungen, segmentiert nach Analyseart, Logikversion, Asset-Typ und Zeitraum.
- Mindestdaten- und Sicherheitsregeln fest im Profil verankert: unter 20 Fällen nur sammeln, 20 bis 50 vorsichtige Prüfung, ab 51 manuelle Prüfung erlaubt; keine automatische Regelaktivierung und keine Änderung produktiver Gewichte.
- Atomare Speicherung unter `runtime/calibration_profile.json`, reproduzierbarer SHA-256-Datenfingerabdruck und manueller, marktfreier Aktualisierungsweg `--calibration-only` ergänzt. Prognosequalität zeigt Reifegrad und manuelle Prüfhinweise verständlich an.
- Reales leeres Profil erfolgreich erzeugt: 0 ausgewertete Fälle, 0 Prüfhinweise, Produktionsregeln unverändert. Zwei neue Profiltests sowie Prognose- und Stabilitätstests gemeinsam mit 75 bestandenen Tests geprüft.
- Integrationsprüfung des automatischen Profils deckte einen offenen Windows-Logdatei-Handle auf. Der Runner schließt und entfernt seine Logger-Handler jetzt auch bei Fehlern zuverlässig; isolierter Tagesprozess und alle 20 Prognose-/Kalibrierungstests bestanden.
- Datenintegrität bei Wiederaufnahme verschärft: Abgeschlossene Tagesläufe werden auch mit `--force` nie überschrieben; eine andere Logikversion am selben Tag wird mit klarer Fehlermeldung abgelehnt, statt erfolgreiche Assets still zu überspringen oder Versionen zu vermischen.
- Neuer Regressionstest belegt unveränderte Logikversion, genau einen gespeicherten Forecast und sichere Tages-Deduplizierung; alle 21 Prognose-/Kalibrierungstests bestanden.
- Modellübergreifende Scheingenauigkeit verhindert: Sobald ausgewertete Prognosen mehrerer Analysearten vorhanden sind, wird keine gemeinsame Trefferquote mehr berechnet oder auf der Startseite gezeigt. Die Qualitätsansicht verweist stattdessen auf die getrennten Modellwerte.
- Neuer Regressionstest mit Einstiegs- und Swing-Auswertungen belegt zwei getrennte Modellgruppen und unterdrückte Gesamtquote; Prognose-, Kalibrierungs- und Stabilitätsteilmenge mit 78 bestandenen Tests geprüft.
- Schemaaktualisierung in allen Prognose-Lesewegen abgesichert: Zusammenfassung, gefilterte Qualitätsliste und letzter Lauf führen fehlende idempotente Migrationen vor der Abfrage aus. Damit zeigt die App nach einem Update nicht vorübergehend einen falschen Leerstand. Alle 22 Prognose-/Kalibrierungstests bestanden.
- Vollständige lokale Prüfkette nach Schema-, Modell- und Kalibrierungsausbau erfolgreich: 142 Pytest-Tests, Kompilierung, Repository-Sicherheitscheck und Offline-Smoke-Test einschließlich Headless-Streamlit-Start bestanden.
- Reale Betriebsprüfung um 17:28 Uhr: SQLite-Schema 4 und Integrität `ok`, 0 Prognosen/0 Auswertungen, Kalibrierungsprofil korrekt im Sammelstatus. Windows-Aufgabe `Ready`, aktiviert, nächster Lauf 2026-08-02 um 22:30 Uhr, `WakeToRun`, `StartWhenAvailable`, drei Neustarts und Doppellaufschutz aktiv. Der alte Lauf bleibt bis dahin korrekt als veraltet sichtbar.
- Widerspruch im dauerhaften Arbeitsmodus bereinigt: Roadmap-Arbeit erstellt ohne ausdrücklichen Auftrag weder Commit noch Push.
- Vorhandenes Prognoseuniversum genauer dokumentiert: 325 Assets aus mehreren Regionen und Größenklassen; ServiceNow (`NOW`) ist ausdrücklich enthalten.
- Roadmap um eine verbindliche app-weite Design- und Informationsarchitektur erweitert: ruhiges Premium-Design, wenige hochwertige Komponenten, gemeinsame Typografie-/Abstands-/Farbregeln, native Streamlit-Komponenten und klare responsive Vorgaben.
- Dreistufige Aktienanalyse als dauerhafter Informationsvertrag konsolidiert: Ebene 1 beantwortet Handlung und Plan, Ebene 2 die verständliche Begründung, Ebene 3 Methodik und Berechnung.
- Empfehlungssystem verbindlich auf Langfristigkeit, Preisattraktivität, Timing, optionalen Depot-Effekt und konkrete Handlungskategorien festgelegt; Allzeithoch-Abstand bleibt reiner Kontext.
- Früherer Zwischenstand zunächst in sechs Phasen geordnet; durch die spätere klare Trennung von Asset-Analyse, Investment Opportunities und Swing Trade Finder auf sieben verbindliche Phasen erweitert.
- Bereits umgesetzte Aktienanalyse-, Scanner- und Prognosebausteine nicht erneut als offen eingetragen. Offene Design-, Betriebs- und Historienvalidierung klar vom aktuellen Ist-Stand getrennt.
- Nächste tatsächliche Priorität bleibt die praktische Validierung des bedienungsfreien 325-Asset-Hintergrundlaufs. Danach folgt das gemeinsame app-weite Designsystem vor weiteren Komfortfunktionen.
- Reine Roadmap-Änderung aus diesem Auftrag; kein Anwendungscode, kein Commit und kein Push.
- Manuellen Opportunity Scanner zu einem strikten Long-Swing-v1-Assistenten ausgebaut; zwei Setup-Arten: Rücksetzer im intakten Aufwärtstrend und bestätigter Ausbruch.
- Hauptansicht zeigt nur objektiv freigegebene Trades und andernfalls die klare Kein-Trade-Meldung; sichtbare Beobachtungskategorie und erzwungene Rangliste schwacher Kandidaten entfernt.
- Zentrale Mindestgrenzen, exakte Schlusskurs-/Strukturbedingungen, realistische Stop-/Zielableitung, konsistente CRV-/Expected-Value-Rechnung und Ablehnungen bei verpasstem Einstieg, Ereignisrisiko oder Datenmangel umgesetzt.
- Trading-Einstellungen und risikobasierte Positionsgröße ergänzt; ohne hinterlegtes Kapital wird keine Stückzahl erfunden.
- Manuellen Trade-Lebenszyklus und Paper-Auswertung ergänzt: Einstieg, aktive Begleitung, Stop-Anpassung, Ausstieg, abgelaufene Setups und Kennzahlen ohne automatische Order oder Score-Änderung.
- 21 neue isolierte Trading-Tests ergänzt; vollständiger lokaler Lauf mit 130 bestandenen Pytest-Tests, Kompilierung, Repository-Sicherheit, Offline-/Live-Smoke und sichtbare Desktop-/390-Pixel-Prüfung dokumentiert.
- Windows-Hintergrundaufgabe `InvestmentAssistantDailyForecasts` registriert: täglich 22:30 Uhr, `StartWhenAvailable`, `WakeToRun`, Ausführung im Netz- und Akkubetrieb sowie maximal acht Stunden Laufzeit.
- Windows-Aufwecktimer im aktuellen Energieplan für Netz- und Akkubetrieb aktiviert.
- Betriebsschutz ergänzt: maximal drei automatische Neustartversuche im Abstand von 15 Minuten und keine parallelen Doppelläufe.
- Vorheriger Lauf vom 2026-08-01 war vor dem ersten gespeicherten Asset unterbrochen; Datenbankintegrität und Schema-Version 2 sind intakt, der nächste reale Lauf bleibt zu beobachten.
- Roadmap um den bedienungsfreien Daten- und Lernbetrieb als höchste offene PRIO-B-Aufgabe ergänzt.
- Vorhandenen Stand dokumentiert: Hintergrund-Runner, 325-Asset-Universum, SQLite-Prognosehistorie, automatische Fälligkeitsauswertung, Wiederholungs-/Fortsetzungslogik, Betriebsprotokoll und Windows-Installationsskript sind vorbereitet.
- Offenen Stand dokumentiert: tatsächliche Registrierung der Windows-Aufgabe, kompletter Produktionslauf, Wiederanlauf nach verpasstem Termin, leicht verständlicher Betriebsstatus, Ausfallwarnung, Datensicherung und versionierte Kalibrierungsprofile müssen noch validiert oder umgesetzt werden.
- Lernziel präzisiert: Datensammlung und Qualitätsauswertung laufen ohne Klick; produktive Bewertungsregeln dürfen sich in Version 1 nicht unkontrolliert selbst verändern.
- Ergebnisdarstellung aus dem Work-Task konsolidiert: langfristige Attraktivität, Preisattraktivität und kurzfristiges Timing sind sichtbar getrennt und führen zu einem gemeinsamen relativen Tranchenplan.
- Prognosestatus erweitert: leerer Bestand, noch nicht fällige Prognosen, ausgewertete Prognosen und dokumentiert fehlende Marktdaten werden getrennt erklärt.
- Veraltete Yahoo-Earnings-Termine werden nicht mehr als zukünftige Gültigkeitsgrenze verwendet.
- Roadmap-Status bereinigt: bereits vorhandene PRIO-A-Analysebausteine sowie Prognose- und Lernmodule klar als umgesetzt markiert; daten- oder historienabhängige Ausbauten bleiben offen.
- Priorität angepasst: Der remote blockierte Punkt `Ersten GitHub-Actions-Lauf auswerten` bleibt offen; als lokal ausführbare Vorbereitung wurde der vollständige Pytest-Lauf in den Workflow aufgenommen.
- GitHub-Workflow erweitert: installiert `requirements-dev.txt` und führt vor dem Offline-Smoke-Test `python -m pytest -q` aus.
- Prognose-Datenbank stabilisiert: formale Schema-Version 2 und schrittweise, idempotente Migrationen ergänzt. Vorhandene Daten bleiben erhalten; Datenbanken einer neueren nicht unterstützten App-Version werden vor Schreibzugriffen abgelehnt.
- Nicht löschende Datenbank-Wartung ergänzt: Integritäts-, Größen-, WAL- und Wachstumsinformationen, SQLite-Optimierung und optional ausdrücklich angeforderte Komprimierung. Es gibt keine automatische Aufbewahrungs- oder Löschregel.
- Wartungsbefehl ergänzt: `scripts/run_forecasts.py --maintenance-only`; `--compact` muss bewusst angegeben werden und löscht keine Prognosen.
- Beobachtbarkeit des ersten 325-Asset-Laufs vorbereitet: Runner-Ausgabe und rotierendes Log enthalten nun Laufzeit, Assets pro Minute, Fehlerquote, erkannte Rate-Limit-Fehler und Datenbankwachstum sowie Schema- und Integritätsstatus.
- Der vollständige Produktionslauf war zu diesem Zwischenstand bis zum nächsten planmäßigen Ausführungszeitpunkt offen; es wurden keine massenhaften Yahoo-Abfragen vorgezogen. Der planmäßige Lauf vom 2026-08-02 ist inzwischen erfolgreich belegt und oben separat dokumentiert.
- Schrittweise Modularisierung begonnen: Asset-Suche, bekannte Ticker, Deduplizierung, Yahoo-Treffernormalisierung und Tippfehler-Vorschläge aus `app.py` nach `asset_search.py` extrahiert. Die bisherigen App-Schnittstellen bleiben kompatibel.
- Fachlich getrennte Suchtests ergänzt; bekannte Beispiele funktionieren auch bei Yahoo-Ausfall, direkte Ticker bleiben priorisiert und Dubletten oder ungeeignete Ergebnistypen werden abgefangen.
- Lokale JSON-Historien stabilisiert: gemeinsame defensive Lese- und atomare Schreiblogik nach `json_history_store.py` extrahiert. Such-, Trade-, Decision-, Prognose-, Forward- und Backtest-Dateien werden erst nach vollständig geschriebenem temporären Stand ersetzt.
- Schreibfehler-Schutz getestet: Scheitert der atomare Austausch, bleibt die bestehende Historie unverändert und temporäre Dateien werden entfernt. Es findet keine automatische Bereinigung oder Löschung statt.
- Gemeinsame Analyse-Datenmodelle nach `analysis_models.py` extrahiert. Die App exportiert dieselben Klassen weiterhin kompatibel; Bewertungswerte, Standardfelder und Nutzeroberfläche bleiben unverändert.
- Technische Analyse aus dem Monolithen gelöst: Indikatoren, Unterstützungen/Widerstände, numerische Hilfsfunktionen, CRV und Marktphasenerkennung liegen in `technical_analysis.py`; `app.py` exportiert die bisherigen Schnittstellen kompatibel weiter.
- Fünf isolierte Regressionstests für die ausgelagerte technische Analyse ergänzt. Die Extraktion verändert weder Scores noch Marktphasenregeln oder sichtbare Ergebnisse.
- Tests dokumentiert: 108 Pytest-Tests bestanden; Repository-Sicherheitscheck, Offline-Smoke-Test, Streamlit-Start und Kompilierung erfolgreich.
- Kein Commit und kein Push; der echte Remote-Lauf ist weiterhin nicht ausgeführt.

### 2026-06-15

- ROADMAP um PRIO-A-Paket für Marktregime-, Innovations-, Blasenrisiko-, Makro-Wirkungs- und Rohstoffanalyse erweitert.
- Neue Analyseziele dokumentiert: Marktregime wie Liquiditätsboom, Liquiditätsentzug, Risk-On, Risk-Off, Rezessionsangst, Wachstumsphase, Defensivphase, Technologie-Hype, KI-Hype und Spekulationsphase sollen nachvollziehbar erklärt werden.
- Innovations-Modul geplant: Trennung zwischen echten Innovationsführern, indirekten Profiteuren und reinen Hype-Aktien.
- Blasenrisiko-Modul geplant: Score 0-10 auf Basis von Bewertung, Medienaufmerksamkeit, Zuflüssen, Momentum und Sentiment, ohne fehlende Daten zu schätzen.
- Makro-Wirkungsmodul geplant: Erklärung von Zinsen, Inflation, Realzinsen, Dollar und Liquidität sowie deren Auswirkungen auf Aktien, ETFs, Krypto und Rohstoffe.
- Rohstoff-Modul geplant: Öl, Gas, Kupfer, Gold und Uran mit Konjunktur-, Dollar-, Realzins-, Liquiditäts- und geopolitischer Sensitivität.
- Prioritätsentscheidung nach dynamischer Logik: PRIO A vorgezogen, weil widersprüchliche Empfehlungen direkt Analysequalität und Verständlichkeit beeinträchtigen.
- Haupt-Dashboard und Research-Modul vereinheitlicht: zentrale Empfehlungsbox zeigt Kaufsignal, Research-Einordnung, Asset-Qualität, Depot-Effekt, Vertrauensscore, Marktphase, CRV und Wahrscheinlichkeiten.
- Separate obere `Research-Handlungsempfehlung` entfernt, damit keine zweite Empfehlung neben der zentralen Entscheidung konkurriert.
- Analyse-Details verbessert: `Konkreter Plan` zeigt jetzt den Research-Plan statt nur den Empfehlungstitel.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Analysepfade mit `BTC-EUR`, `NVDA` und `1810.HK` erfolgreich; Streamlit-Start gab einen lokalen URL-Hinweis, Browser-/HTTP-Sichtprüfung war durch die Sandbox blockiert.
- Yahoo-Finance-Fehlerbehandlung verbessert: eingeschränkte Stammdaten, FX-Umrechnung, News und Makro-Proxies werden oben im Dashboard und im Research-Modul als externe Datenquellen-Warnungen gebündelt.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Warnungsfunktion mit simulierten Ausfällen und Normalfall erfolgreich; Live-Analysepfade mit `BTC-EUR`, `NVDA` und `1810.HK` erfolgreich.
- Datenqualitäts-Check kompakter und sichtbarer gemacht: Dashboard zeigt jetzt eine Datenqualitäts-Ampel mit Score, kurzer Statuszeile, wichtigsten Datenhinweisen und Details im Expander.
- Anfänger-Modus um einfache Datenqualitäts-Erklärung ergänzt.
- Umlaute und sichtbare deutsche Texte geprüft: `app.py` und `README.md` enthalten keine Mojibake-Treffer; ROADMAP-Treffer sind nur absichtlich dokumentierte Beispiele.
- Suchhistorie in der Sidebar als auswählbare Schnellwahl umgesetzt.
- Wiederholbaren Smoke-Test ergänzt: `scripts/smoke_test.py` kompiliert `app.py`, startet Streamlit kurz auf einem freien Port und prüft den Analysefluss mit `BTC-EUR`, `NVDA` und `1810.HK`.
- Smoke-Test erfolgreich ausgeführt: py_compile OK, Streamlit-Start OK, Live-Analysepfade OK.
- Score-Gewichtungen transparent gemacht: Analyse-Details zeigen jetzt Gewichtungen nach Asset-Typ und die separate Kaufsignal-Gewichtung; README dokumentiert die Gewichtungen.
- Kalibrierungsstatus ergänzt: Die App zeigt Anzahl dokumentierter Fälle, Mindestdatenmenge und ob Hinweise oder Kalibrierungsvorschläge erlaubt sind; Gewichtungen werden nicht automatisch geändert.
- `trade_history.json` als lokale, nicht versionierte Datei für spätere Trade-/Prognosehistorie vorbereitet.
- Nächste tatsächliche Priorität gesetzt: Asset-Qualität je Asset-Typ verbessern.
- Asset-Qualität je Asset-Typ verbessert: Aktien bewerten zusätzlich Margen, Kapitalrendite und Kurs-Umsatz-Verhältnis; ETFs bewerten langfristige Stabilität aus berechneter Volatilität; fehlende Daten bleiben sichtbar als `Daten nicht verfügbar`.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; erster Smoke-Test ohne Netzwerk scheiterte erwartbar am Yahoo-Datenabruf für `BTC-EUR`; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Aufgabe ist die weitere Abgrenzung und Präzisierung des Kaufsignals, weil die langfristige Asset-Qualität nun besser getrennt abgebildet ist.
- Kaufsignal weiter von Asset-Qualität abgegrenzt: MACD-Bestätigung, Bodenbildungs-Hinweis und asset-typische Volatilitätsschwellen ergänzt; App zeigt ausdrücklich, dass Asset-Qualität und Depot-Effekt nicht in das Kaufsignal einfließen.
- Smoke-Test aktualisiert und erfolgreich ausgeführt: `score_buy_signal` nutzt jetzt den Asset-Typ; `BTC-EUR`, `NVDA` und `1810.HK` liefen mit Netzwerkfreigabe erfolgreich durch.
- Priorität angepasst: Nächste PRIO-A-Aufgabe ist die stärkere Erklärung der Research-Scores, weil die Score-Bedeutung unmittelbar die Nutzbarkeit der Analyse verbessert.
- Research-Scores stärker erklärt: Modul- und institutionelle Tabellen zeigen jetzt Score-Bänder (`stark`, `konstruktiv`, `gemischt`, `schwach`, `kritisch`, `Daten nicht verfügbar`) plus praktische Bedeutung; Anfänger-Modus nutzt dieselbe Interpretation.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Aufgabe sind robustere Nachkaufzonen, damit fehlende Kurszonen nicht als präzise Kaufmarken missverstanden werden.
- Nachkaufzonen robuster gemacht: faire Kaufzone nutzt nur Unterstützungen unter dem Kurs, Sicherheits-Kaufzone nur Widerstand oder SMA50 oberhalb des Kurses; fehlende Marken erhalten Statushinweise statt erfundener Kursziele.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Aufgabe sind stärkere Bull/Base/Bear-Szenarien aus Trend, Volatilität, Unterstützungen, Widerständen und CRV.
- Bull/Base/Bear-Szenarien verbessert: Wahrscheinlichkeiten berücksichtigen jetzt zusätzlich SMA-Trendstruktur, Abstand zu Unterstützung/Widerstand, Volatilität und CRV; Kursziele bleiben bei fehlenden Marken `Daten nicht verfügbar`.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Aufgabe ist der Einstieg in das Marktregime-, Innovations-, Blasen- und Makro-Wirkungsmodul.
- Erstes Marktregime-Modul umgesetzt: nutzt vorhandene Nasdaq-, US-Zins-, Dollar-, TIP-, Trend- und Volatilitätsdaten; zeigt Hinweise, Gegenargumente, Unsicherheiten, betroffene Asset-Klassen und Vertrauensgrad.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist das Makro-Wirkungsmodul mit getrennten Auswirkungen auf Aktien, ETFs, Krypto und Rohstoffe.
- Makro-Wirkungsmodul ergänzt: erklärt Zinsen, Dollar, Risikoappetit und Inflations-/Realzinsproxy mit praktischer Wirkung auf Aktien, ETFs, Krypto und Rohstoffe; Aussagen bleiben als Wahrscheinlichkeitszusammenhänge gekennzeichnet.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist ein erstes Blasenrisiko-Modul aus verfügbaren Bewertungs-, Momentum-, Sentiment- und Volatilitätsdaten.
- Blasenrisiko-Modul umgesetzt: nutzt vorhandene Bewertungsdaten, RSI, 3M-Kursanstieg, Volatilität und News-Sentiment; Medienaufmerksamkeit und Zuflüsse werden als `Daten nicht verfügbar` gekennzeichnet; hoher Score wird als Warnsignal interpretiert.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist das Innovations-Modul zur Trennung von Innovationsführern, indirekten Profiteuren und Hype-Aktien.
- Innovations-/Hype-Modul umgesetzt: nutzt vorhandene Wachstums-, Margen-, Free-Cashflow-, Marktstellungs-, Beschreibungs- und News-Daten; Produktvorsprung, Patente, Entwickleraktivität und Marktanteile bleiben `Daten nicht verfügbar`, wenn sie nicht vorliegen.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist ein Rohstoff-Kontextmodul mit Öl, Gas, Kupfer, Gold und Uran als Makro-/Rohstoff-Wirkungskategorien.
- Rohstoff-Kontextmodul umgesetzt: nutzt Yahoo-Proxies für Öl, Gas, Kupfer, Gold und Uran/URA, sofern verfügbar; zeigt 3M-Trends, Asset-Typ-Kontext und Unsicherheit statt sichere Kausalitäten zu behaupten.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-A-Teilaufgabe ist die Erweiterung des Krypto-Moduls mit Bitcoin-Halving-Zyklus und transparenter Krypto-Marktstruktur.
- Krypto-Zyklusmodul umgesetzt: bei Krypto-Assets werden Bitcoin-Halving-Zyklus, geschätzte Zyklusphase, Krypto-Volatilität und Volumen/Liquidität angezeigt; ETF-Flows, Fear & Greed und On-Chain-Daten bleiben ohne Quelle `Daten nicht verfügbar`.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste Aufgabe ist PRIO B Forward-Testing, weil Messung der Analysequalität jetzt mehr Nutzen bringt als weitere unbelegte Datenquellen.
- Forward-Test-Basisspeicherung umgesetzt: Nutzer können die aktuell angezeigte Analyse optional lokal in `forward_tests.json` speichern; gespeichert werden Analysezeitpunkt, Symbol, Asset-Typ, Einstiegskurs, Scores, Szenarien, Kaufzonen, Modul-Scores und Review-Felder; keine Orderfunktion.
- `forward_tests.json` in `.gitignore` und README-Datenschutzliste aufgenommen.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist die Auswertung gespeicherter Forward-Tests mit echten Kursdaten.
- Forward-Test-Auswertung umgesetzt: Sidebar kann fällige gespeicherte Analysen nach 1 Woche, 1 Monat und 3 Monaten mit echten Kursdaten auswerten; gespeichert werden aktuelle Rendite, maximale positive Entwicklung und maximale negative Entwicklung.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist Decision Tracking, damit Nutzerentscheidungen später mit App-Einschätzungen verglichen werden können.
- Decision-Tracking-Basis umgesetzt: Nutzer können Kaufen, Nicht kaufen, Halten, Verkaufen oder Beobachten mit optionalem Kommentar lokal in `decision_history.json` speichern; App-Einschätzung und Modul-Scores werden mitgespeichert; keine Orderfunktion.
- `decision_history.json` in `.gitignore` und README-Datenschutzliste aufgenommen.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist Prognose-Tracking für Bull/Base/Bear-Szenarien.
- Prognose-Tracking-Basisspeicherung umgesetzt: Bull/Base/Bear-Szenarien, Wahrscheinlichkeiten, Kursziele, entscheidende Marke und Kaufzonen können lokal in `prediction_history.json` gespeichert werden; keine Orderfunktion.
- `prediction_history.json` in `.gitignore` und README-Datenschutzliste aufgenommen.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist die Prognose-Auswertung mit echten Kursdaten.
- Prognose-Auswertung umgesetzt: Sidebar kann fällige gespeicherte Prognosen nach 1 Woche, 1 Monat und 3 Monaten mit echten Kursdaten auswerten; gespeichert werden Rendite, maximale positive/negative Entwicklung und eine einfache Szenario-Lesart.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist ein Kalibrierungs- und Lernmodul, das lokale Historien zusammenfasst und Datenbasis/Mindestfallzahl transparent macht.
- Kalibrierungs- und Lernstatus erweitert: Analyse-Details zählen jetzt Trade-Historie, Forward-Tests, Nutzerentscheidungen, Prognosen und ausgewertete Zeiträume gemeinsam; Gewichtungen werden weiterhin nicht automatisch geändert.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist eine erste Signalanalyse aus lokalen Historien, sobald ausreichend Fälle vorliegen.
- Signalanalyse-Basis umgesetzt: Analyse-Details zeigen ausgewertete Fälle, positive/negative Ausgänge und ab ausreichender Datenbasis Trefferquoten nach Asset-Typ; Gewichtungen bleiben unverändert.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist ein erster Opportunity Scanner auf Basis der bestehenden Analysefunktionen.
- Opportunity-Scanner-Basis umgesetzt: Sidebar-Watchlist mit Standardwerten `BTC-EUR`, `NVDA`, `PLTR`, `1810.HK` und `EUNL.DE`; Scan nutzt bestehende Kurs-, Asset-Typ-, Kaufsignal-, Asset-Qualitäts-, CRV- und Vertrauenslogik; einzelne Tickerfehler werden abgefangen und fehlende Daten nicht erfunden.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`; Scanner-Direkttest mit `BTC-EUR` und `NVDA` erfolgreich.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist der Trading-Modus auf Basis der Scanner-Kandidaten.
- Streamlit-Community-Cloud-Vorbereitung umgesetzt: `app.py` nutzt keine Windows-Pfade, yfinance-Cache fällt bei Schreibproblemen auf ein temporäres Verzeichnis zurück, `.streamlit/config.toml` ist vorhanden, `portfolio.json` enthält nur GitHub-kompatible Minimaldaten und README erklärt das Cloud-Deployment.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich.
- Trading-Modus-Basis umgesetzt: Aus Opportunity-Scanner-Kandidaten werden Setups mit Richtung, Chance, Confidence, Zielzone, Stop-Zone, CRV, Zeithorizont, Risiken und Chancen erzeugt; Setups können lokal in `trade_history.json` gespeichert werden und lösen keine Order aus.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Trading-Setup-Direkttest mit `NVDA` erfolgreich; Smoke-Test mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Priorität angepasst: Nächste PRIO-B-Aufgabe ist Performance-Tracking für gespeicherte Trade-Journal-Setups.
- Neue PRIO-A-Aufgabe vorgezogen: Analyse-Daten vollständig von Chart-Daten entkoppeln, weil der gewählte Chart-Zeitraum die Analysequalität nicht verschlechtern darf.
- Entkopplung umgesetzt: Einzelanalyse lädt Chart-Daten separat für die Visualisierung und Analyse-Daten separat mit maximal verfügbarer Tageshistorie; Datenqualitätsbereich zeigt Chart-Historie und Analyse-Historie; langfristige und kurzfristige Unterstützungen/Widerstände werden getrennt angezeigt.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; aktualisierter Smoke-Test prüft getrennte Chart- und Analyse-Daten und lief mit Netzwerkfreigabe erfolgreich für `BTC-EUR`, `NVDA` und `1810.HK`.
- Streamlit-Community-Cloud-Check erneut durchgeführt: keine lokalen Windows-Pfade in `app.py`, Requirements vollständig, `portfolio.json` im erlaubten Minimalformat, keine Secrets/Brokerdaten gefunden, `.streamlit/config.toml` vorhanden und README um Mobile-Hinweise erweitert.
- Performance-Tracking für Trade-Journal umgesetzt: Fällige Setups in `trade_history.json` können über die Sidebar mit echten Kursdaten ausgewertet werden; gespeichert werden Rendite, maximale positive/negative Entwicklung, Ziel erreicht, Stop erreicht und Ergebnis.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Trade-History-Auswertung mit gemockten Kursdaten erfolgreich. Live-Test mit Yahoo-Finance-Daten bleibt optional.
- Erweitertes Decision Tracking umgesetzt: Fällige Entscheidungen in `decision_history.json` können über die Sidebar gegen Long, Short und Halten/Beobachten ausgewertet werden; gespeichert werden Entscheidungsrendite, beste Alternative und Opportunitätskosten.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Decision-Tracking-Auswertung mit gemockten Kursdaten erfolgreich.
- Confidence-System erweitert: Im Research-Modul zeigt die App ähnliche lokale Historienfälle nach Asset-Typ oder Marktphase, historische Trefferquote erst ab ausreichender Datenbasis und die Regel, dass keine automatische Gewichtungsänderung erfolgt.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; Confidence-Historienauswertung mit gemockten Fällen erfolgreich.

### 2026-08-01

- Zentrale Empfehlungssynthese umgesetzt: Asset-Qualität, Timing, CRV, Marktphase, Bewertung, Risiken, Datenlage und optionaler Depot-Effekt werden ohne Änderung bestehender Einzel-Scores in sieben eindeutige Handlungskategorien übersetzt.
- Bedingte Einstiege konkretisiert: Rücksetzerweg, Bestätigungsweg und technische Widerlegungsmarke werden gemeinsam ausgewiesen; exakte Positionsgrößen bleiben ohne vollständiges Risikobudget bewusst offen.
- Analyseoberfläche in einen kompakten Ergebniskopf und sieben fachliche Bereiche gegliedert; tiefe Methodik-, Daten- und Technikdetails bleiben eingeklappt.
- Laufzeit-Roadmap abgeschlossen: unabhängige Stamm-, Makro-, News-, Rohstoff- und Earnings-Abrufe parallelisiert, doppelter Yahoo-Abruf für tägliche Chartdaten entfernt und historischer Signal-Backtest gezielt zwischengespeichert.
- Reale ServiceNow-Gegenmessung: vollständiger erster Analyseabruf 9,31 Sekunden, wiederholter Abruf 2,51 Sekunden, keine Exception; Zielbereich 5–10 Sekunden beim ersten Abruf erreicht.
- Tests dokumentiert: 71 Pytests bestanden, `compileall` erfolgreich, Repository-Sicherheitscheck und Offline-/Live-Smoke-Test erfolgreich, sichtbare Browserprüfung von ServiceNow und Scanner erfolgreich.
- Neue offene PRIO-A-/Stabilitätsaufgabe aufgenommen: vollständigen Analyseaufruf durch parallele externe Datenabrufe und Backtest-Zwischenspeicherung von aktuell etwa 15 Sekunden auf 5–10 Sekunden reduzieren; Bewertungslogik und Ergebnisumfang müssen unverändert bleiben.
- Repository-Sicherheitscheck ergänzt: `scripts/repo_safety_check.py` prüft getrackte private Laufzeitdateien, Secret-Dateien und das Minimalformat von `portfolio.json` sowie `portfolio.example.json`.
- GitHub-Smoke-Workflow erweitert: Vor dem Offline-Smoke-Test läuft jetzt der Repository-Sicherheitscheck.
- README aktualisiert: Smoke-Test-Abschnitt dokumentiert den neuen Sicherheitscheck.
- Tests dokumentiert: `scripts\repo_safety_check.py` erfolgreich; `python -m py_compile app.py scripts\smoke_test.py scripts\repo_safety_check.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `git diff --check` ohne Whitespace-Fehler; Korruptions-/Merge-Marker-Suche ohne Treffer; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: `GitHub-Workflow nach erstem Remote-Lauf auswerten` bleibt offen, ist lokal aber bis zum Push blockiert; der Sicherheitscheck wurde als PRIO-C/Datenschutz-Schutzschritt vorgezogen, weil er GitHub-Deployment und CI stabiler macht.

- Lokale Historienqualität in CI-/GitHub-Check vorbereitet: neuer Workflow `.github/workflows/smoke.yml` installiert Dependencies und führt `python scripts/smoke_test.py --skip-live-data` aus.
- Datenschutz beibehalten: Der Workflow benötigt keine `portfolio.json`, keine Lernhistorien, keine Secrets, keine Brokerdaten und keine API-Keys.
- README aktualisiert: Smoke-Test-Abschnitt nennt den GitHub-Workflow.
- Tests dokumentiert: lokaler `scripts\smoke_test.py --skip-live-data` vorgesehen vor Commit; Remote-Auswertung folgt nach Push.
- Priorität angepasst: ursprüngliche Priorität `Lokale Historienqualität in CI-/GitHub-Check vorbereiten` ist umgesetzt; neue Priorität ist `GitHub-Workflow nach erstem Remote-Lauf auswerten`, weil CI-Ergebnisse erst nach Push sichtbar sind.

- Historienqualität in Smoke-Test sichtbar gemacht: `scripts/smoke_test.py` ruft jetzt `local_history_quality_rows()` auf und gibt Status sowie eingeschränkte Historien aus.
- README aktualisiert: Smoke-Test-Beschreibung nennt lokale Historienqualität.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich inklusive Historienqualitätsausgabe.
- Priorität angepasst: ursprüngliche Priorität `Historienqualität in Smoke-Test oder Testskript sichtbar machen` ist umgesetzt; neue Priorität ist `Lokale Historienqualität in CI-/GitHub-Check vorbereiten`, weil der Smoke-Test jetzt ohne private Historien laufen kann.

- Lernhistorien-Dateien mit Datenschutz-/Cloud-Hinweisen in README präzisiert: `backtest_history.json` ergänzt und Rollen der Historien erklärt.
- Datenschutz klargestellt: Lernhistorien dürfen keine Broker-Zugangsdaten, API-Keys, Passwörter, Kontonummern oder persönlichen Identifikationsdaten enthalten.
- Streamlit-Cloud-Einschränkung präzisiert: Laufzeitdateien sind keine dauerhafte Datensicherung; lokale Sicherung oder bewusster Export bleibt Nutzerentscheidung.
- Tests dokumentiert: reine README/ROADMAP-Änderung; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erneut vorgesehen vor Commit.
- Priorität angepasst: ursprüngliche Priorität `Lernhistorien-Dateien mit Datenschutz-/Cloud-Hinweisen in README präzisieren` ist umgesetzt; neue Priorität ist `Historienqualität in Smoke-Test oder Testskript sichtbar machen`, weil Qualität lokaler JSON-Historien nun zentraler Analysekontext ist.

- Defekte lokale Historien in Lernansicht mit Reparaturhinweisen ergänzt: `local_history_quality_rows()` zeigt jetzt eine Spalte `Reparaturhinweis`.
- Sicherheitsregel beibehalten: Die App löscht oder verändert lokale Historien nicht automatisch; defekte Einträge werden nur erklärt und ignoriert.
- README aktualisiert: lokale Lernhistorienqualität beschreibt jetzt manuelle Reparaturhinweise.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; direkte Mock-Tests für defekte und gültige Historien erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Defekte lokale Historien in Lernansicht mit Reparaturhinweisen ergänzen` ist umgesetzt; neue Priorität ist `Lernhistorien-Dateien mit Datenschutz-/Cloud-Hinweisen in README präzisieren`, weil die App inzwischen mehrere lokale Historien nutzt.

- Lernhistorien-Datenqualität in Confidence-/Kalibrierungsstatus eingebunden: `calibration_status_rows()` und `similar_setup_rows()` zeigen jetzt den Qualitätsstatus lokaler Historien als Kontext.
- Eingeschränkte Historien relativieren Lernhinweise: Bei eingeschränkter lokaler Historienqualität ergänzt der Kalibrierungsstatus einen Warnhinweis; Confidence-Tabellen zeigen die Qualitätszeile separat.
- README aktualisiert: lokale Historienqualität als Transparenzhinweis für Kalibrierung und Confidence dokumentiert.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter History-Quality-Status-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Lernhistorien-Datenqualität in Confidence-/Kalibrierungsstatus einfließen lassen` ist umgesetzt; neue Priorität ist `Defekte lokale Historien in Lernansicht mit Reparaturhinweisen ergänzen`, weil die App jetzt Einschränkungen erkennt, aber noch keine praktischen nächsten Schritte anbietet.

- Datenqualitäts-Check für Lern-/Backtest-Historien ausgebaut: neue `local_history_quality_rows()` prüft Review-Strukturen, abgeschlossene Auswertungen und belastbare Backtest-Zeilen.
- Analyse-Details erweitert: Die App zeigt `Datenqualität lokaler Lernhistorien` vor den Lernlogik-Guardrails.
- README aktualisiert: lokale Lernhistorienqualität und Teststrategie ergänzt.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Local-History-Quality-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Datenqualitäts-Check für Lern-/Backtest-Historien ausbauen` ist umgesetzt; neue Priorität ist `Lernhistorien-Datenqualität in Confidence-/Kalibrierungsstatus einfließen lassen`, weil eingeschränkte Historien die Belastbarkeit von Lernhinweisen reduzieren sollten.

- Testbarkeit der neuen Lern-/Confidence-Kontextfunktionen gebündelt: `tests/test_stability.py` nutzt jetzt gemeinsame Konstanten und `reviewed_case()` für Kalibrierungskontext-Mocks.
- Wartbarkeit verbessert: Mehrere Tests für Kalibrierungsvorschläge, Fehlmuster, Kalibrierungskontext-Zusammenfassung und ähnliche Setups verwenden dieselbe Mock-Historie.
- README aktualisiert: Teststrategie für Lern-/Confidence-Kontexte ergänzt.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Testbarkeit der neuen Lern-/Confidence-Kontextfunktionen bündeln` ist umgesetzt; neue Priorität ist `Datenqualitäts-Check für Lern-/Backtest-Historien ausbauen`, weil belastbare Historien die Grundlage der Lernmodule sind.

- Lernsystem-Ausgabe für Kalibrierungskontext verständlicher zusammengefasst: neue `calibration_context_summary_rows()` erzeugt eine kompakte Tabelle mit Fallzahl, Fehlquote, Durchschnittsrendite und praktischer Bedeutung.
- Analyse-Details erweitert: Direkt nach den Lernlogik-Guardrails zeigt die App `Kalibrierungskontext kurz erklärt`.
- README aktualisiert: Lernlogik-Guardrails beschreiben die neue Kalibrierungskontext-Zusammenfassung.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Kalibrierungskontext-Zusammenfassungs-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Lernsystem-Ausgabe für Kalibrierungskontext verständlicher zusammenfassen` ist umgesetzt; neue Priorität ist `Testbarkeit der neuen Lern-/Confidence-Kontextfunktionen bündeln`, weil mehrere neue Kontextfunktionen ähnliche Mock-Daten nutzen.

- Confidence-System gegen Kalibrierungskontext aus Performance-Reviews geprüft: `similar_setup_rows()` zeigt jetzt häufigsten `Kalibrierungskontext` und `Kalibrierungshinweis` aus ähnlichen lokalen Fällen.
- Score-Trennung beibehalten: Die neuen Confidence-Kontexte sind reine Transparenzhinweise und verändern keine Gewichtungen.
- README aktualisiert: Confidence-System nennt Kalibrierungskontext als zusätzlichen Review-Kontext.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Confidence-Kalibrierungskontext-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Confidence-System gegen Kalibrierungskontext aus Performance-Reviews prüfen` ist umgesetzt; neue Priorität ist `Lernsystem-Ausgabe für Kalibrierungskontext verständlicher zusammenfassen`, weil die neuen Kontexte jetzt über mehrere Tabellen verteilt sind.

- Lern-/Signalanalyse gegen Performance-Kalibrierungskontext geprüft: `evaluated_history_cases()` übernimmt jetzt `calibration_context` und `calibration_hint` aus Review oder Setup.
- Fehlmuster und Kalibrierung erweitert: `negative_case_cause_rows()` und `calibration_suggestion_rows()` können Kalibrierungskontext und Kalibrierungshinweis gruppieren.
- README aktualisiert: Signalanalyse nennt Kalibrierungskontext als Fehlmuster-Dimension.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Lern-Kalibrierungskontext-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Lern-/Signalanalyse gegen Performance-Kalibrierungskontext prüfen` ist umgesetzt; neue Priorität ist `Confidence-System gegen Kalibrierungskontext aus Performance-Reviews prüfen`, weil ähnliche Setup-Ausgaben diese Warnkontexte ebenfalls anzeigen sollten.

- Performance-Tracking-Auswertung gegen Kalibrierungskontext-Felder geprüft: Trade-Journal-Reviews speichern jetzt `calibration_context` und `calibration_hint` aus dem ursprünglichen Setup.
- Setup-Kontext bleibt erhalten: Performance Reviews überschreiben die ursprünglichen Kalibrierungshinweise nicht, sondern führen sie als Auswertungskontext mit.
- README aktualisiert: Performance Tracking beschreibt jetzt den ursprünglichen Kalibrierungskontext.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Performance-Kalibrierungskontext-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Performance-Tracking-Auswertung gegen Kalibrierungskontext-Felder prüfen` ist umgesetzt; neue Priorität ist `Lern-/Signalanalyse gegen Performance-Kalibrierungskontext prüfen`, weil diese Review-Felder für spätere Signalqualität relevant sind.

- Trade-Journal-Speicherung gegen neue Kalibrierungskontext-Felder geprüft: `normalize_trade_record()` übernimmt `calibration_context` und `calibration_hint` in `Kalibrierungskontext` und `Kalibrierungshinweis`.
- Default-Verhalten ergänzt: Fehlen die Felder, zeigt das Trade Journal `Daten nicht verfügbar` und verändert keine Einschätzung.
- README aktualisiert: Trade Journal beschreibt jetzt den erhaltenen Kalibrierungskontext.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Trade-Journal-Kalibrierungsfeld-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Trade-Journal-Speicherung gegen neue Kalibrierungskontext-Felder prüfen` ist umgesetzt; neue Priorität ist `Performance-Tracking-Auswertung gegen Kalibrierungskontext-Felder prüfen`, weil Review-Auswertungen diese Setup-Kontexte erhalten müssen.

- Scanner- und Trading-Ausgaben mit Backtest-/Kalibrierungskontext verbunden: Opportunity Scanner und Trading-Setups zeigen jetzt `Kalibrierungskontext` und `Kalibrierungshinweis` aus schwachen gespeicherten Backtest-Mustern.
- Score-Trennung beibehalten: Opportunity Score, Chance, Confidence und Kaufsignal werden dadurch nicht automatisch verändert.
- README aktualisiert: Opportunity Scanner und Trading-Modus beschreiben die neuen Kalibrierungskontext-Felder.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Scanner-/Trading-Kalibrierungskontext-Mock-Test erfolgreich.
- Priorität angepasst: ursprüngliche Priorität `Scanner- und Trading-Ausgaben mit Backtest-/Kalibrierungskontext verbinden` ist umgesetzt; neue Priorität ist `Trade-Journal-Speicherung gegen neue Kalibrierungskontext-Felder prüfen`, weil diese Felder in späteren Performance-Auswertungen erhalten bleiben sollten.

- Kalibrierungsvorschläge mit Backtest-Historie verbunden: schwache gespeicherte Backtest-Gruppen mit ausreichender Datenbasis erscheinen jetzt als Bereich `Backtest-Signal`.
- Keine automatische Kalibrierung: Backtest-Hinweise bleiben manuelle Vorschläge mit Datenbasis, Fehlquote, Begründung und Umsetzungshinweis.
- README aktualisiert: Signalanalyse beschreibt Backtest-basierte manuelle Kalibrierungshinweise.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Backtest-Kalibrierungs-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Kalibrierungsvorschläge mit Backtest-Historie verbinden` ist umgesetzt; neue Priorität ist `Scanner- und Trading-Ausgaben mit Backtest-/Kalibrierungskontext verbinden`, weil Lernhinweise bei neuen Chancen sichtbar sein sollten.

- Backtesting-Ausgabe gegen Lern-/Confidence-Kontext konsolidiert: Backtest-Gruppen zeigen jetzt `Historienstatus` und `Lernhinweis`; gespeicherte Backtest-Historie zeigt zusätzlich einen `Confidence-Kontext`.
- Mindestdatenregel vereinheitlicht: Unter 20 Fällen bleibt der Kontext `Datenbasis zu klein`, 20 bis 50 Fälle sind vorsichtige Lernhinweise, über 50 Fälle sind nur manuell prüfbare Kalibrierungshinweise.
- README aktualisiert: Backtesting-Basis beschreibt Historienstatus, Confidence-Kontext und Lernhinweis.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Backtest-Confidence-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Backtesting-Ausgabe gegen Lern-/Confidence-Kontext prüfen` ist umgesetzt; neue Priorität ist `Kalibrierungsvorschläge mit Backtest-Historie verbinden`, weil die Backtest-Ergebnisse nun als Lernkontext strukturiert vorliegen.

- Confidence-System gegen erweiterten Historienkontext konsolidiert: `similar_setup_rows()` zeigt jetzt häufigste Szenario-Lesart, Fehlursache, Decision-Alignment und Historienstatus aus ähnlichen lokalen Review-Fällen.
- Keine Blackbox-Änderung: Die neuen Context-Felder erklären ähnliche Setups, verändern aber keine Score-Gewichtungen automatisch.
- README aktualisiert: Confidence-System beschreibt die zusätzlichen Review-Kontexte.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Confidence-Kontext-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Confidence-System gegen erweiterten Trade-/Decision-/Prediction-Historienkontext prüfen` ist umgesetzt; neue Priorität ist `Backtesting-Ausgabe gegen Lern-/Confidence-Kontext prüfen`, weil Backtesting die nächste Messschicht für die Analysequalität ist.

- Performance-Tracking gegen normalisierte Journal-Felder konsolidiert: `evaluate_due_trade_history()` normalisiert Trade-Records vor der Auswertung und hält Legacy-Felder kompatibel.
- Historienkontext im Review ergänzt: Trade-Journal-Auswertungen speichern jetzt ähnliche Setups, Treffer ähnlicher Setups, Trefferquote, Historienstatus und Historienhinweis im jeweiligen Review-Ergebnis.
- Ergebnislogik unverändert: Ziel/Stop, Rendite, maximale positive/negative Bewegung, beste Alternative und Opportunitätskosten bleiben reine Nachauswertung mit echten Kursdaten.
- README aktualisiert: Performance Tracking beschreibt jetzt Historienkontext aus ähnlichen Setups.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Performance-Tracking-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Performance-Tracking-Ausgabe gegen normalisierte Journal-Felder und Historienkontext prüfen` ist umgesetzt; neue Priorität ist `Confidence-System gegen erweiterten Trade-/Decision-/Prediction-Historienkontext prüfen`, weil Confidence-Ausgaben die erweiterten Review-Felder transparent nutzen sollten.

- Trade-Journal-Datenmodell konsolidiert: `append_trade_records()` normalisiert neue und ältere Feldnamen beim Speichern in `trade_history.json`.
- Legacy-Kompatibilität verbessert: Alias-Felder wie `created_at`, `symbol`, `entry_price`, `target`, `stop`, `similar_setups` und `history_status` werden in die deutschen Journal-Felder übernommen.
- Performance-Tracking vorbereitet: Neue Journal-Einträge erhalten defensiv `review_after`, Historienstatus, ähnliche Setups und Sicherheits-Hinweis, ohne bestehende Werte zu überschreiben.
- README aktualisiert: Trade Journal beschreibt jetzt defensive Feldnormalisierung.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Trade-Journal-Normalisierungscheck erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Trade-Journal-Datenmodell gegen neue Trading-/Performance-Felder konsolidieren` ist umgesetzt; neue Priorität ist `Performance-Tracking-Ausgabe gegen normalisierte Journal-Felder und Historienkontext prüfen`, weil die Auswertung auf den normalisierten Journal-Daten aufsetzt.

- Trading-Modus gegen Lern-/Confidence-Kontext konsolidiert: Trading-Setups zeigen und speichern jetzt Treffer ähnlicher Setups, Trefferquote, Historienstatus und Historienhinweis.
- Performance verbessert: `build_trading_setup()` verwendet bereits geladene Yahoo-Stammdaten für die Asset-Qualität und vermeidet eine doppelte Stammdatenabfrage pro Setup.
- Trade-Journal-Kontext erweitert: Die neuen Felder werden beim automatischen lokalen Dokumentieren mitgespeichert; keine Order, keine Broker-Anbindung.
- README aktualisiert: Trading-Modus beschreibt jetzt Historienstatus und ähnliche Setups.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Trading-Setup-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Trading-Modus-Ergebnisliste gegen Lern-/Confidence-Kontext und Journal-Felder prüfen` ist umgesetzt; neue Priorität ist `Trade-Journal-Datenmodell gegen neue Trading-/Performance-Felder konsolidieren`, weil gespeicherte Setups die Basis für spätere Performance-Auswertungen sind.

- Opportunity Scanner mit Lern-/Confidence-Kontext erweitert: Scanner-Ergebnisse zeigen jetzt ähnliche historische Setups, Trefferquote ähnlicher Setups und Historienstatus.
- Score-Trennung beibehalten: Der Historienkontext verändert den Opportunity Score nicht automatisch, sondern wird als Transparenzfeld und Begründung angezeigt.
- Testbarkeit ergänzt: Scanner-Mock-Test prüft weiter einmalige Yahoo-Stammdatennutzung und zusätzlich die neuen Historienfelder.
- README aktualisiert: Opportunity Scanner beschreibt jetzt historische Setup-Anzahl und Trefferquote.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Scanner-Historien-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Opportunity-Scanner-Ergebnisliste gegen Lern-/Confidence-Kontext prüfen` ist umgesetzt; neue Priorität ist `Trading-Modus-Ergebnisliste gegen Lern-/Confidence-Kontext und Journal-Felder prüfen`, weil Trading-Setups direkt aus Scanner-Kandidaten entstehen und ins Journal fließen.

- Kalibrierungs- und Lernmodul konsolidiert: `evaluated_history_cases()` normalisiert jetzt zusätzlich Szenario-Lesart, Fehlursache und Decision-Alignment aus Review-Daten.
- Fehlfall- und Kalibrierungstabellen erweitert: negative Fälle und Kalibrierungsvorschläge können nun nach Szenario-Lesart, Fehlursache und Decision-Alignment gruppiert werden.
- Signalanalyse erweitert: negative Prognosefälle können Fehlursachen als Lernhinweis anzeigen, ohne Gewichtungen automatisch zu ändern.
- README aktualisiert: Kalibrierungsbereich beschreibt die neuen Lernfelder.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkte Lern-/Kalibrierungs-Mock-Tests erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Kalibrierungs- und Lernmodul gegen Prognose-/Decision-/Forward-Erweiterungen konsolidieren` ist umgesetzt; neue Priorität ist `Opportunity-Scanner-Ergebnisliste gegen Lern-/Confidence-Kontext prüfen`, weil Scanner-Vorschläge die vorhandene Historie transparent berücksichtigen sollten.

- Prognose-Tracking konsolidiert: Prognose-Auswertungen speichern jetzt neben `scenario_read` auch eine einfache `miss_reason` aus vorhandener Marktphase, Signal-Snapshot, Modul-Scores oder Kursentwicklung.
- Trefferquoten erweitert: `prediction_hit_rate_rows()` gruppiert ausgewertete Prognosen zusätzlich nach Szenario-Lesart und Fehlursache.
- Keine Daten erfunden: Fehlursachen werden nur aus bereits gespeicherten Signalen/Modul-Scores oder echter Kursentwicklung abgeleitet; fehlende Felder bleiben kompatibel.
- README aktualisiert: Prognose-Tracking beschreibt jetzt Szenario-Lesart und mögliche Fehlursachen.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Prognose-Tracking-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Prognose-Tracking-Hauptliste gegen Szenario-Treffer, Modulgruppen und Fehlursachen konsolidieren` ist umgesetzt; neue Priorität ist `Kalibrierungs- und Lernmodul gegen Prognose-/Decision-/Forward-Erweiterungen konsolidieren`, weil die neuen Review-Felder nun in der Lernlogik nutzbar gemacht werden sollten.

- Decision-Tracking konsolidiert: Decision-Reviews speichern jetzt zusätzlich App-Exposure, Entscheidungsexposure und ob die Nutzerentscheidung mit oder gegen die App-Einschätzung getroffen wurde.
- Nutzerkontext bleibt erhalten: `user_note`, App-Aktion, Professional-Decision-Kontext, Asset-Qualität, Kaufsignal, Confidence, Marktphase, Signal-Snapshot und Modul-Scores bleiben im lokalen Decision-Datensatz.
- Ergebnisvergleich bleibt getrennt von Empfehlungen: Beste Alternative und Opportunitätskosten werden nur nachträglich aus echten Kursdaten berechnet und verändern keine Live-Scores.
- README aktualisiert: Decision-Tracking beschreibt jetzt Kommentar, App-Alignment, beste Alternative und Opportunitätskosten.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Decision-Tracking-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Decision-Tracking-Hauptliste gegen gespeicherte Scores, Nutzerkommentar und Ergebnisvergleich konsolidieren` ist umgesetzt; neue Priorität ist `Prognose-Tracking-Hauptliste gegen Szenario-Treffer, Modulgruppen und Fehlursachen konsolidieren`, weil Prognosen die nächste wichtige Quelle für messbare Analysequalität sind.

- Forward-Testing konsolidiert: Fällige Forward-Test-Auswertungen speichern jetzt zusätzlich eine einfache Szenario-Lesart aus echter Kursentwicklung.
- Lernfähigkeit verbessert: Signalanalyse zählt ausgewertete Forward-Tests nun zusätzlich nach Szenario-Lesart und gespeicherten Modul-Score-Gruppen.
- Kompatibilität beibehalten: Alte Forward-Test-Historien ohne Modul-Scores oder Szenario-Lesart bleiben lesbar; fehlende Felder werden nicht erfunden.
- README aktualisiert: Forward-Testing beschreibt jetzt Szenario-Lesart, Modul-Scores und die Regel, dass Gewichtungen nicht automatisch geändert werden.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Forward-Test-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Forward-Testing-Hauptliste gegen gespeicherte Modul-Scores, Szenarien und Ergebnisgruppen konsolidieren` ist umgesetzt; neue Priorität ist `Decision-Tracking-Hauptliste gegen gespeicherte Scores, Nutzerkommentar und Ergebnisvergleich konsolidieren`, weil Nutzerentscheidungen die nächste wichtige Messschicht für Analysequalität sind.

- Krypto-Zyklus-Kontext erweitert: Das Krypto-Zyklusmodul nutzt jetzt eine testbare Halving-Kontextfunktion mit Zyklusphase, Zyklusfortschritt, Score und praktischer Anlegerbedeutung.
- Anfänger-Transparenz verbessert: Der Halving-Zyklus wird ausdrücklich als Kontextsignal und nicht als Kaufsignal erklärt; Trend, Liquidität, Volatilität, Makro und Risikomarken bleiben wichtiger.
- Keine Krypto-Daten erfunden: ETF-Flows, Fear & Greed, On-Chain, Orderbuch, Spread, Börsentiefe und Stablecoin-Liquidität bleiben ohne belastbare Quelle `Daten nicht verfügbar`.
- README aktualisiert: Krypto-Zyklus beschreibt jetzt Zyklusfortschritt, Anlegerbedeutung und Unsicherheitsregel.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Krypto-Zyklus-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Krypto-Zyklus-Kontext prüfen und verständlicher in Krypto-Analyse integrieren` ist umgesetzt; neue Priorität ist `Forward-Testing-Hauptliste gegen gespeicherte Modul-Scores, Szenarien und Ergebnisgruppen konsolidieren`, weil messbare Analysequalität und Lernfähigkeit Vorrang vor Komfortfunktionen haben.

- Performance-Tracking für Trade Journal erweitert: Fällige Trade-Auswertungen speichern jetzt zusätzlich gewählte Aktion, beste Alternative, Rendite der besten Alternative und Opportunitätskosten.
- Ziel-/Stop-Auswertung bleibt unverändert erhalten: Ziel erreicht, Stop erreicht, Rendite sowie maximale positive und negative Entwicklung werden weiterhin aus echten Kursdaten berechnet.
- Testbarkeit ergänzt: Neuer Mock-Test prüft einen Long-Trade mit Stop-Berührung, negativer Rendite und Short/Absicherung als beste Alternative.
- README aktualisiert: Performance Tracking beschreibt jetzt beste Alternative und Opportunitätskosten.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkte Funktionschecks für beste Alternative und Trade-Performance-Auswertung erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Performance-Tracking für Trade Journal um beste Alternative und Ziel-/Stop-Auswertung gegen Roadmap prüfen` ist umgesetzt; neue Priorität ist `Krypto-Zyklus-Kontext prüfen und verständlicher in Krypto-Analyse integrieren`, weil Krypto-Analysequalität wichtiger ist als Komfortfunktionen und fehlende Spezialdaten transparent kompensiert werden müssen.

### 2026-07-31

- Scanner-Performance verbessert: `scan_opportunities()` verwendet bereits geladene Yahoo-Stammdaten nun direkt für die Asset-Qualität und vermeidet dadurch eine doppelte Stammdatenabfrage pro Ticker.
- Testbarkeit ergänzt: Ein neuer Mock-Test prüft, dass der Opportunity Scanner pro Symbol nur einmal `load_ticker_info()` aufruft und die Faktor-Spalten weiter ausgibt.
- README aktualisiert: Opportunity Scanner dokumentiert jetzt die Wiederverwendung geladener Stammdaten.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; direkter Scanner-Mock-Test erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Scanner-Performance und Testbarkeit nach Faktorabdeckung prüfen` ist umgesetzt; neue Priorität ist `Performance-Tracking für Trade Journal um beste Alternative und Ziel-/Stop-Auswertung gegen Roadmap prüfen`, weil die Lernfähigkeit von vollständigen Ergebnisdaten abhängt.

- News-Modul erweitert: Yahoo-News werden defensiv normalisiert und je Nachricht mit Quelle, Datum, Relevanz und Sentiment-Qualität angezeigt.
- Keine News erfunden: Fehlende, unklare oder leere News-Daten bleiben neutral und werden als `Daten nicht verfügbar` ausgewiesen.
- README aktualisiert: Research-Modul beschreibt die neue News-Transparenz.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; direkte Funktionschecks für fehlende News und News mit Quelle/Datum/Relevanz erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Nächste Priorität angepasst: Makro-Modul erweitern, Inflation, Realzinsen, Liquidität und Risikoappetit transparenter machen.
- Institutionelle Research-Module validiert: Analysten-Konsens, Earnings, Event-Risiko und institutionelle Daten zeigen jetzt Datenabdeckung und Score-Neutralität.
- Keine institutionellen Daten erfunden: Fehlende Analysten-, Earnings-, Event-, Insider-, Short-Interest- oder ETF-Flow-Daten bleiben ausdrücklich `Daten nicht verfügbar`.
- README aktualisiert: Research-Modul beschreibt Datenabdeckung und Score-Neutralität für institutionelle Module.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; direkte Funktionschecks für fehlende und verfügbare institutionelle Daten erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Nächste Priorität angepasst: News-Modul verbessern, Quelle, Datum, Relevanz und Sentiment-Qualität transparenter machen.
- Bewertungsmodell erweitert: Aktienbewertung zeigt jetzt Forward-KGV-Abstand, EV/Umsatz, Sektor-/Branchenkontext sowie klar getrennte Hinweise zu historischer Bewertungszeitreihe und Peer-Vergleich.
- Keine Daten erfunden: Wenn Yahoo Finance keine historische Multiple-Zeitreihe oder Peer-Multiples liefert, zeigt die App ausdrücklich `Daten nicht verfügbar`.
- README aktualisiert: Research-Modul beschreibt die erweiterten Bewertungskennzahlen und die Transparenzregel für fehlende Historien-/Peer-Daten.
- Tests dokumentiert: `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; direkte Funktionschecks für verfügbare Bewertungsdaten und fehlende Peer-/Historienwerte erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Nächste Priorität angepasst: Analysten-, Earnings-, Event- und institutionelle Module validieren und auf zusätzliche Datenquellen prüfen.

### 2026-07-20

- Kalibrierungsvorschläge aus Fehlmustern umgesetzt: Die App erzeugt im Analyse-Detailbereich manuelle Prüfhinweise mit Datenbasis, Fehlquote, Begründung und Umsetzungsregel.
- Mindestdatenlogik beibehalten: Unter 20 Fällen wird nur gezählt; 20 bis 50 Fälle liefern vorsichtige Hinweise; über 50 Fälle erlauben manuelle Kalibrierungsvorschläge.
- README aktualisiert: Signalanalyse beschreibt nun auch konkrete Kalibrierungsvorschläge aus Fehlmustern.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; direkte Funktionschecks für leere Historie, keine Fehlmuster und große Fehlerbasis erfolgreich; `pytest` konnte nicht laufen, weil das Modul in der lokalen venv fehlt.
- Nächste Priorität angepasst: Bewertungsmodelle ausbauen, historische Bewertung, relative Bewertung und Peer-Vergleich prüfen, falls Daten verfügbar sind.
- Fehlfall-Ursachenanalyse umgesetzt: Verfehlte Historienfälle werden im Analyse-Detailbereich nach Asset-Typ, Marktphase, Kaufsignal, RSI, MACD, Volatilität, CRV, News und Makro gruppiert.
- Mindestdatenlogik beibehalten: Unter 20 Fehlfällen wird nur gezählt; ab 20 Fällen gibt es vorsichtige Hinweise; Gewichtungen werden nie automatisch geändert.
- README aktualisiert: Signalanalyse beschreibt nun auch die gruppierte Fehlfall-Ursachenanalyse.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für leere Historie, keine Fehlfälle und Fehlfall-Gruppen erfolgreich.
- Nächste Priorität angepasst: Lernmodul mit konkreten Kalibrierungsvorschlägen aus häufigen Fehlerursachen erweitern.
- Backtest-Historie in Lern- und Kalibrierungsübersicht integriert: Gespeicherte Backtests aus `backtest_history.json` werden als separater Lernkontext mit Fallzahl, Trefferquote, Durchschnittsrendite und Drawdown angezeigt.
- Transparenzregel beibehalten: Backtest-Historie verändert keine Scores und keine Gewichtungen automatisch.
- README aktualisiert: Kalibrierungsbereich erklärt den neuen Backtest-Lernkontext.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für leere, dünne und belastbare Backtest-Historie erfolgreich.
- Nächste Priorität angepasst: Fehlprognosen und negative Historienfälle nach Ursache kategorisieren.
- Backtesting-Kompaktansicht umgesetzt: Der Analyse-Detailbereich zeigt jetzt beste Trefferquote, schwächste Rendite, größten Drawdown und größte Datenbasis oberhalb der vollständigen Backtest-Tabelle.
- Backtest-Verdichtung bleibt konservativ: Gruppen unter 20 Fällen werden nicht als belastbar interpretiert.
- README aktualisiert: Backtesting-Basis beschreibt nun die Kompaktansicht.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für Backtesting-Kompaktansicht und kleine Datenbasis erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich.
- Nächste Priorität angepasst: Backtest-Historie in Lern- und Kalibrierungsübersicht integrieren.
- Backtesting-Signal-Kombinationen umgesetzt: Die Backtest-Tabelle vergleicht jetzt Kaufsignal-Bucket, RSI-Bucket, MACD-Bucket und CRV-Bucket gemeinsam.
- Die Backtest-Ausgabe zeigt weiterhin Asset-Typ, damalige Marktphase, Zeithorizont, Trefferquote, Durchschnittsrendite und maximalen Drawdown; unter 20 Fällen bleibt `Datenbasis zu klein`.
- README und UI-Überschrift aktualisiert: Backtesting wird nun als historische Signal-Kombinationsauswertung beschrieben.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für Signal-Kombinationen und kurze Historie erfolgreich.
- Nächste Priorität angepasst: Backtesting-Tabelle besser verdichten und interpretieren.
- Backtest-Ergebnisse dauerhaft nutzbar gemacht: Die aktuelle Backtest-Tabelle kann lokal in `backtest_history.json` gespeichert werden.
- Datenschutz umgesetzt: `backtest_history.json` ist in `.gitignore` aufgenommen und enthält nur Analyse-/Backtestdaten, keine Depot-, Broker- oder Zugangsdaten.
- README aktualisiert: lokale Backtest-Historie und Datenschutzliste ergänzt.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Test für Speichern und Laden von Backtest-Ergebnissen erfolgreich.
- Nächste Priorität angepasst: Backtesting-Signal-Kombinationen vergleichen.
- Backtesting verfeinert: Die Backtest-Tabelle gruppiert historische Kaufsignal-Buckets jetzt zusätzlich nach Asset-Typ und damaliger Marktphase.
- Drawdown-Basis ergänzt: Je Backtest-Gruppe wird der maximale Drawdown im späteren Kursfenster angezeigt, sobald mindestens 20 Fälle vorhanden sind.
- README aktualisiert: Backtesting-Basis beschreibt nun Asset-Typ, Marktphase und Drawdown.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für segmentiertes Backtesting und kurze Historie erfolgreich.
- Nächste Priorität angepasst: Backtest-Ergebnisse dauerhaft nutzbar machen.
- Backtesting-Basis umgesetzt: Im Analyse-Detailbereich werden historische Kaufsignal-Buckets gegen spätere Kursentwicklungen über 1, 3, 6 und 12 Monate getestet.
- Backtest-Regeln dokumentiert: Es handelt sich um einen Signaltest, keine Strategieoptimierung, keine automatische Gewichtungsänderung und keine Kauf-/Verkaufsautomatisierung.
- README aktualisiert: Backtesting-Basis beschrieben.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; Mock-Tests für Backtest mit ausreichender und zu kurzer Historie erfolgreich.
- Nächste Priorität angepasst: Backtesting nach Asset-Typ und Marktphase verfeinern.
- Tracking-Zeiträume erweitert: Trade-Journal, Forward-Tests, Prognosen und Decision-Tracking nutzen jetzt zentral `1w`, `1m`, `3m`, `6m` und `12m`.
- Alte Historien bleiben kompatibel: fehlende `6m`- und `12m`-Felder werden beim Auswerten ergänzt, ohne bestehende Review-Ergebnisse zu überschreiben.
- Neue gespeicherte Analysen, Entscheidungen, Prognosen und Trading-Setups erhalten direkt den vollständigen Review-Plan.
- README aktualisiert: Performance-Tracking und Prognose-Tracking nennen jetzt 6- und 12-Monats-Auswertungen.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Test mit alten Historien für Trade, Decision, Prognose und Forward erfolgreich.
- Nächste Priorität angepasst: Backtesting-Basis vorbereiten.

### 2026-07-31

- Opportunity-Scanner-Faktorabdeckung erweitert: Scanner-Ergebnisse zeigen jetzt News, Makro, Liquidität, Bewertung und institutionelle Faktoren separat.
- Fehlende Scanner-Daten bleiben transparent: Institutionelle Faktoren, Bewertung oder Liquidität werden als `Daten nicht verfügbar` angezeigt, wenn Yahoo/Marktdaten keine belastbare Quelle liefern.
- Keine Handelsfunktion ergänzt: Scanner bleibt Vorschlags- und Vergleichswerkzeug; keine Käufe, Verkäufe oder Broker-Anbindung.
- README aktualisiert: Opportunity Scanner beschreibt jetzt zusätzliche Faktorgruppen und fehlende Datenquellen.
- Tests dokumentiert: direkte Scanner-Faktor-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Opportunity-Scanner-Modulabdeckung transparenter machen` ist umgesetzt; neue Priorität ist `Scanner-Performance und Testbarkeit nach Faktorabdeckung prüfen`, weil zusätzliche News-/Yahoo-Faktorabfragen bei großen Watchlists Laufzeit erzeugen können.
- Trade-Journal-Automatik umgesetzt: Trading-Setups aus Scanner-Kandidaten werden beim Scannerlauf automatisch lokal in `trade_history.json` dokumentiert.
- Deduplizierung ergänzt: Setups werden nach Ticker, Richtung und Tag dedupliziert, damit Streamlit-Reruns nicht mehrere gleiche Journal-Einträge erzeugen.
- Sicherheitsgrenzen beibehalten: Trade-Journal speichert nur lokale Analyse-/Trackingdaten; keine Order, keine Broker-Anbindung, keine Kauf-/Verkaufsautomatisierung.
- README aktualisiert: Trade Journal beschreibt jetzt automatische lokale Dokumentation mit Deduplizierung.
- Tests dokumentiert: direkte Trade-Journal-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Trade-Journal-Automatik gegen Roadmap-Anforderung prüfen` ist umgesetzt; neue Priorität ist `Opportunity-Scanner-Modulabdeckung transparenter machen`, weil die Roadmap zusätzliche Scanner-Faktoren wie News, Makro, Liquidität, Bewertung und institutionelle Faktoren fordert.
- Lernlogik-Guardrails ergänzt: Die Analyse-Details zeigen jetzt dokumentierte Fälle, ausgewertete Fälle, Mindestdatenregeln und die aktuelle Freigabe für Lern-/Kalibrierungshinweise.
- Testbarkeit verbessert: `learning_guardrail_rows()` kapselt die Mindestdatenlogik und macht prüfbar, dass unter 20 Fällen keine Kalibrierung erfolgt und über 50 Fällen nur manuelle Vorschläge erlaubt sind.
- Keine Blackbox-Änderungen: Der Guardrail-Block zeigt explizit, dass Score-Gewichtungen, Kaufsignal-Schwellen und Portfolio-Logik niemals automatisch durch das Lernsystem geändert werden.
- README aktualisiert: Kalibrierungsbereich beschreibt jetzt Lernlogik-Guardrails, ausgewertete Fälle und Datenbasisgrenzen.
- Tests dokumentiert: direkte Lernlogik-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Lernlogik-Dokumentation und Testbarkeit konsolidieren` ist umgesetzt; neue Priorität ist `Trade-Journal-Automatik gegen Roadmap-Anforderung prüfen`, weil die Roadmap automatische lokale Dokumentation vorgeschlagener Trades fordert, aber keine automatische Orderfunktion erlaubt.
- Prognose-Tracking konsolidiert: Neue Prognosen speichern jetzt Research-Modul-Scores zusätzlich zu Szenarien, Kurszielen, Wahrscheinlichkeiten, entscheidender Marke und Signal-Snapshot.
- Trefferquoten je Asset und Modul ergänzt: Die Analyse-Details zeigen ausgewertete Prognosen nach Asset-Typ sowie Modul-/Signalgruppen; alte Prognosen ohne Modul-Scores bleiben über `signal_snapshot` kompatibel.
- Mindestdatenlogik beibehalten: Unter 20 Fällen werden Prognosegruppen nur gezählt; ab 20 Fällen sind vorsichtige Hinweise möglich; Gewichtungen werden nie automatisch geändert.
- README aktualisiert: Prognose-Tracking beschreibt jetzt Modul-Scores, Asset-/Modultrefferquoten und Datenbasisgrenzen.
- Tests dokumentiert: direkte Prognose-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Prognose-Tracking-Hauptliste konsolidieren und Modul-Trefferquoten prüfen` ist umgesetzt; neue Priorität ist `Lernlogik-Dokumentation und Testbarkeit konsolidieren`, weil die nächste Analysequalitätsverbesserung in nachvollziehbarer Kalibrierung und Mindestdatenlogik liegt.
- Krypto-Spezialdaten transparenter gemacht: Krypto-Fundamentals, Krypto-Asset-Qualität und Krypto-Zyklus zeigen jetzt Datenabdeckung und Score-Neutralität für Fear & Greed, ETF-Flows, On-Chain, Orderbuch/Spread, Stablecoin-Liquidität und Volumenvergleich.
- Krypto-Marktstruktur ergänzt: Das Krypto-Zyklusmodul bewertet verfügbare 50er/200er-Trendstruktur zusätzlich zu Halving-Zeitfenster, Volatilität und Volumenvergleich.
- Keine Krypto-Daten erfunden: Fear & Greed, ETF-Flows, On-Chain-Daten, Orderbuch, Spread, Börsentiefe und Stablecoin-Liquidität bleiben ohne belastbare Quelle ausdrücklich `Daten nicht verfügbar`.
- README aktualisiert: Krypto-Zyklus beschreibt jetzt Datenabdeckung, Marktstruktur und fehlende Spezialdatenquellen.
- Tests dokumentiert: direkte Krypto-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Krypto-Modul: externe Krypto-Spezialdaten und Marktstruktur transparenter prüfen` ist umgesetzt; neue Priorität ist `Prognose-Tracking-Hauptliste konsolidieren und Modul-Trefferquoten prüfen`, weil die PRIO-B-Umsetzung bereits weit fortgeschritten ist, aber die ältere Hauptliste noch offene Formulierungen enthält.
- Risiko- und Liquiditätsmodule verfeinert: Risiko-Score zeigt jetzt Datenabdeckung, Score-Neutralität, Asset-Typ-Volatilität, Risiko bis Unterstützung, Potenzial bis Widerstand und CRV-Einordnung.
- Liquiditäts-Score erweitert: relatives Volumen zum 20er-Schnitt, Yahoo-Durchschnittsvolumen, 10T-Durchschnittsvolumen und fehlende Spread-/Orderbuchdaten werden transparent ausgewiesen.
- Keine Markttiefedaten erfunden: Bid-Ask-Spread, Orderbuchtiefe, Börsentiefe und Stablecoin-Liquidität bleiben `Daten nicht verfügbar`, wenn keine belastbare Quelle eingebunden ist.
- README aktualisiert: Risiko-Score und Liquiditäts-Score beschreiben jetzt Datenabdeckung und praktische Grenzen.
- Tests dokumentiert: direkte Risiko-/Liquiditäts-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Risiko- und Liquiditätsmodul verfeinern` ist umgesetzt; neue Priorität ist `Krypto-Modul: externe Krypto-Spezialdaten und Marktstruktur transparenter prüfen`, weil Krypto-Signale stark von Datenquellen wie Fear & Greed, ETF-Flows, On-Chain und Liquiditätsstruktur abhängen.
- Geopolitik-Modul umgesetzt: neuer `Geopolitik-Score` im Research-Pack nutzt ausschließlich verfügbare Yahoo-News-Titel als Hinweisquelle für Sanktionen, Zölle, Krieg, Lieferkettenstress oder Exportkontrollen.
- Keine geopolitischen Daten erfunden: Wenn keine News verfügbar sind, zeigt das Modul `Geopolitische Daten nicht verfügbar`; wenn keine Treffer gefunden werden, wird das ausdrücklich nicht als vollständige Entwarnung formuliert.
- Unsicherheitsfaktoren verbessert: geopolitische Risiken werden jetzt nicht mehr nur pauschal genannt, sondern abhängig von Datenverfügbarkeit und Geopolitik-Score eingeordnet.
- README aktualisiert: Geopolitik-Score und Grenzen der Datenlage dokumentiert.
- Tests dokumentiert: direkte Geopolitik-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Geopolitik-Modul prüfen` ist umgesetzt; neue Priorität ist `Risiko- und Liquiditätsmodul verfeinern`, weil Risiko, Volumenqualität und Handelbarkeit die praktische Belastbarkeit eines Kaufsignals stark beeinflussen.
- Makro-Modul erweitert: Datenabdeckung und Score-Neutralität werden jetzt im Makro-Score ausgewiesen.
- Makro-Proxies transparenter gemacht: Risikoappetit/Nasdaq, Zinsdruck/US-Zinsen, Dollar-/Liquiditätsdruck und TIP als Inflations-/Realzinsproxy werden einzeln erklärt.
- Keine Makro- oder Liquiditätsdaten erfunden: direkte Liquiditätsdaten bleiben ohne belastbare Quelle `Daten nicht verfügbar`, und fehlende Proxies führen zu neutraler Bewertung statt Scheingenauigkeit.
- README aktualisiert: Makro-Score beschreibt jetzt Datenabdeckung, Score-Neutralität und verfügbare Proxy-Daten.
- Tests dokumentiert: direkte Makro-Mock-Tests erfolgreich; `python -m py_compile app.py tests\test_stability.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; `pytest` konnte nicht laufen, weil `pytest` in `.venv` nicht installiert ist.
- Priorität angepasst: ursprüngliche Priorität `Makro-Modul erweitern` ist umgesetzt; neue Priorität ist `Geopolitik-Modul prüfen`, weil geopolitische Risiken hohe Analysewirkung haben, aber nur mit belastbarer Datenlage aufgenommen werden dürfen.

### 2026-07-19

- Segmentierte Lernanalyse umgesetzt: Die App zeigt im Analyse-Detailbereich Trefferquote, Durchschnittsrendite und Fallzahl nach Asset-Typ, Marktphase und Zeithorizont.
- Mindestdatenlogik beibehalten: Gruppen unter 20 Fällen bleiben `Datenbasis zu klein`; 20 bis 50 Fälle liefern nur vorsichtige Hinweise; ab über 50 Fällen sind manuelle Kalibrierungsvorschläge erlaubt.
- README aktualisiert: Segment-Trefferquoten nach Asset-Typ, Marktphase und Zeithorizont dokumentiert.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für Segment-Auswertung mit 20+ und kleiner Datenbasis erfolgreich.
- Nächste Priorität angepasst: längere Auswertungszeiträume für Forward-, Prognose-, Decision- und Trade-Tracking vorbereiten.
- Signalbasierte Kalibrierung umgesetzt: neue Historieneinträge speichern eine `signal_snapshot` für RSI, MACD, Volatilität, News, Makro und CRV; ältere Einträge bleiben kompatibel und zeigen fehlende Signalwerte als `Daten nicht verfügbar`.
- Ähnliche historische Setups werden zusätzlich nach Signalbestandteilen aufgeschlüsselt und zeigen je Signal Fallzahl, Trefferquote, Durchschnittsrendite und Kalibrierungsstatus ab den definierten Mindestfallzahlen.
- README aktualisiert: Lernsystem, Signal-Snapshots und Kalibrierungsregeln dokumentiert.
- Tests dokumentiert: `python -m py_compile app.py` erfolgreich; Mock-Tests für signalbasierte Kalibrierung mit 20+ und 50+ Fällen erfolgreich.
- Nächste Priorität angepasst: Trefferquoten und Signalwirkung nach Asset-Typ, Marktphase und Zeithorizont feiner auswerten.
- Technische Bereinigung im Confidence-/Lernmodul umgesetzt: doppelte Funktionsnamen für historische Auswertungen getrennt, damit die Ähnliche-Setup-Auswertung und die allgemeine Confidence-Historie jeweils die richtige Datenstruktur verwenden.
- ROADMAP-Bereinigung fortgeführt: Konfliktmarker und doppelte Änderungsprotokoll-Blöcke entfernt.
- Tests dokumentiert: `python -m py_compile app.py scripts\smoke_test.py` erfolgreich; `scripts\smoke_test.py --skip-live-data` erfolgreich; Mock-Tests für Ähnliche-Setup-Trefferquote und historische Confidence-Auswertung erfolgreich.

### 2026-06-30

- Confidence-System erweitert: Die App zählt ähnliche historische Setups aus `trade_history.json`, `forward_tests.json`, `decision_history.json` und `prediction_history.json` nach Asset-Typ, Empfehlung/Aktionsfamilie, Marktphase, Kaufsignal-Bucket und Asset-Qualitäts-Bucket.
- Trefferquote und Durchschnittsrendite ähnlicher Setups werden erst ab mindestens 20 ähnlichen ausgewerteten Fällen angezeigt; darunter steht transparent `Datenbasis zu klein`.
- Die Auswertung nutzt nur tatsächlich gespeicherte Review-Ergebnisse und erfindet keine fehlenden Renditen.
- Gewichtungen werden weiterhin nicht automatisch geändert; die Ausgabe dient nur als Confidence- und Kalibrierungshinweis.
- Nächste Priorität angepasst: Kalibrierungsvorschläge aus den ähnlichen Setups feiner nach Signalbestandteilen ableiten.

### 2026-06-24

- Professionellere Kauf-/Nichtkauf-Entscheidung umgesetzt: Die App trennt Asset-Qualität, Zukunftspotenzial, Bewertung, eingepreiste Erwartungen, Blasenrisiko, technischen Einstieg und Expected Value, damit starke Qualitätsaktien nicht nur wegen unperfektem Timing pauschal abgelehnt werden.
- Bewertungsmodul für Aktien erweitert: KGV, Forward-KGV, PEG, KUV, EV/EBIT-Näherung, EV/FCF, Kurs/Buchwert, Free-Cashflow-Rendite, Wachstum, Margen, Verschuldung, historische Bewertung und Branchenvergleich werden berücksichtigt oder explizit als `Daten nicht verfügbar` angezeigt; KGV wird nicht isoliert verwendet.
- Neues Expected-Value-Modul ergänzt: Bull-/Base-/Bear-Case, Wahrscheinlichkeiten, erwartete Rendite, erwarteter Verlustbeitrag und Expected-Value-Score fließen in die Entscheidung ein.
- Ablehnungslogik erweitert: Vorsichtige oder negative Empfehlungen zeigen Hauptgrund und Nicht-Hauptgrund, z. B. ob es nicht an der Unternehmensqualität, sondern an Bewertung, Timing, CRV, Blasenrisiko, Makro oder Datenlage liegt.
- Forward-Testing vorbereitet: Empfehlungen werden lokal automatisch einmal pro Symbol, Empfehlung und Tag für spätere Auswertung gespeichert; es gibt weiterhin keine Broker-Anbindung und keine automatische Orderfunktion.

### 2026-06-14

- Repository für GitHub-Datenschutz vorbereitet: lokale Suchhistorie und Secrets werden ignoriert, Beispiel-Dateien ergänzt, README aktualisiert.
- Portablen Depot-Modus vorbereitet: `portfolio.json` auf GitHub-kompatibles Minimalformat standardisiert, sensible Felder ausgeschlossen und App-Leselogik für `ticker`/`shares`/`buy_price` ergänzt.
- ROADMAP um Forward-Testing, Decision-Tracking, Prognose-Tracking sowie Kalibrierungs- und Lernmodul erweitert.
- Dynamische Priorisierung eingeführt: ursprüngliche numerische Prioritäten bleiben Ausgangsbasis, neue tatsächliche Priorität wird nach Nutzen für Analysequalität, Stabilität und Lernfähigkeit abgeleitet.
- Prioritätslogik dokumentiert: PRIO A für Grundfähigkeit der Analyse, PRIO B für Messung der Analysequalität, PRIO C für Architektur und Wartbarkeit, PRIO D für Komfortfunktionen.
- ROADMAP um Opportunity Scanner, Trading-Modus, Trade Journal, Performance Tracking, Confidence-System, Signalanalyse und erweiterte Kalibrierungsvorschläge ergänzt.
- Priorisierung erweitert: Diese neuen Module gehören zu PRIO B und dürfen vor Komfortfunktionen bearbeitet werden, wenn sie Analysequalität messbar verbessern.
- Regel `Wachsende ROADMAP` ergänzt: Neu entdeckte sinnvolle Aufgaben werden aufgenommen, priorisiert und mit Nutzen, Abhängigkeiten sowie Begründung dokumentiert.
- Master-ROADMAP erstellt und aktuellen Projektstand analysiert.
- Projektziel, aktuelle Funktionen, offene Aufgaben, Prioritäten, Akzeptanzkriterien und Arbeitsmodus dokumentiert.
- Regel ergänzt: Bei `Arbeite weiter` wird ROADMAP gelesen, die höchste tatsächliche Priorität dynamisch bestimmt, bearbeitet, getestet und ROADMAP aktualisiert.
- Sicherheitsregel festgehalten: keine automatische Kauf- oder Verkaufsfunktion.
- Institutionelles Research-Modul umgesetzt: Analysten-Konsens, Earnings-Modul, Event-Risiko, institutionelle Daten, Vertrauensscore und Unsicherheitsfaktoren.
- Arbeitsmodus erweitert: Wenn kein Implementierungs-Prompt vorhanden ist, wird selbstständig geplant, umgesetzt, getestet und dokumentiert.
- Autonome Architekturpflege ergänzt: ROADMAP-Reihenfolge darf angepasst werden, wenn eine frühere strukturelle Änderung spätere Aufgaben besser lösbar macht.
- Projekt auf autonomen Langzeitbetrieb vorbereitet: GitHub-Synchronisation, Sicherheits-Commits, Rollback-Regeln, intelligente Priorisierung, Testmatrix und Schutz vor erfundenen Daten dokumentiert.

## Umsetzungsnotiz 2026-07-01

- Confidence-System erweitert: Die App sammelt ausgewertete lokale Fälle aus Trade Journal, Forward-Tests und Prognose-Tracking, gleicht sie nach Asset-Typ, Marktphase, Richtung und Kaufsignal-Bucket ab und zeigt Anzahl ähnlicher Setups sowie Trefferquote.
- Bei weniger als 20 ähnlichen Fällen wird transparent `Datenbasis zu klein` angezeigt; zwischen 20 und 50 Fällen nur ein vorsichtiger Hinweis; über 50 Fällen nur ein Hinweis auf mögliche manuelle Kalibrierung.
- Trading-Setups zeigen die Historien-Einordnung zusätzlich zur Chance und zum Confidence Score.
- Die Research-Vertrauensanalyse enthält die Historien-Einordnung als Detail, verändert aber keine Gewichtungen automatisch.

## Umsetzungsnotiz 2026-07-01 - Aktien-Fundamentaldaten

- Aktien-Fundamentaldaten erweitert: strukturierter Snapshot für Wachstum, Margen, Renditen, Cash, Verschuldung, Free Cashflow, operativen Cashflow, KGV, Forward-KGV, Kurs-Umsatz-Verhältnis, Kurs-Buchwert-Verhältnis, EV/EBITDA und Marktkapitalisierung.
- Asset-Qualität und Bewertungsscore nutzen die zusätzlichen Kennzahlen nur, wenn Yahoo Finance echte Werte liefert; fehlende Werte bleiben `Daten nicht verfügbar`.
- Nächste höchste offene Priorität ist ETF-Datenqualität und ETF-Strukturtransparenz.

## Umsetzungsnotiz 2026-07-01 - ETF-Daten

- ETF-Daten erweitert: strukturierter Snapshot für Kategorie, Fondsgesellschaft, TER/Kostenquote, Fondsvolumen, Holdings, YTD-, 1J-, 3J- und 5J-Performance sowie 3-Jahres-Beta.
- ETF-Qualität zeigt verfügbare Struktur- und Performance-Daten transparent; fehlende ETF-Spezialdaten bleiben `Daten nicht verfügbar`.
- Nächste höchste offene Priorität sind Bewertungsmodelle, relative Bewertung und Peer-Vergleich ohne erfundene Vergleichsdaten.
