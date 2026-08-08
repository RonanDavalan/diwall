% DIWALL(1) | Diwall-Befehle
%
% Juli 2026

# BEZEICHNUNG

diwall - Toolkit für visuelle Wahrnehmung und Robotic Process Automation (RPA) für Large Language Model (LLM)-Agenten

# ÜBERSICHT

**diwall-shot** \[*Optionen*\] **--url** *URL*

**diwall-rpa** \[*Optionen*\] **--scenario** *DATEI*

**diwall-watch** \[*Optionen*\]

**diwall-monter-secrets** \[*Optionen*\]

**diwall-demonter-secrets** \[*Optionen*\]

**diwall-monitor-verifier** **--scenario** *DATEI* **--reference** *DATEI*

# BESCHREIBUNG

Diwall verleiht einem LLM-Agenten "Augen" und "Hände" für Webinterfaces, die er sonst nicht sehen oder bedienen kann: Screenshots, Markierungen und einen Accessibility-Baum auf der einen Seite, Playwright-gesteuerte Aktionen auf der anderen. Jeder Befehl gibt ein einzelnes JSON-Objekt auf der Standardausgabe aus, das dafür gedacht ist, von einem Programm gelesen zu werden, anstatt von einem Menschen.

Dieses Paket installiert sechs Befehle unter **/usr/bin**. Sie sind dünne
Wrapper um die Python-Einstiegspunkte in **/opt/diwall**, und sie lesen
ihre Konfiguration aus **/etc/diwall/diwall.conf** anstelle der
**/opt/diwall/diwall.conf**, die vom Installationskanal `git-clone` verwendet wird.

Es gibt eine einzige Manualseite für alle sechs Befehle, und das absichtlich: Eine einzelne Seite darf nicht aus dem Gleichklang mit sich selbst geraten. Für die vollständige Optionsliste eines jeden Befehls führen Sie ihn mit **--help** aus – diese Ausgabe ist immer maßgeblich gegenüber dieser Seite.

# BEFEHLE

**diwall-shot**
: Macht einen Screenshot einer Seite und gibt ein JSON-Objekt zurück, das diese beschreibt. Mit **--som** werden interaktive Elemente im Screenshot nummeriert, sodass ein Agent sie anhand ihres Index referenzieren kann; mit **--a11y** wird der Accessibility-Baum enthalten. Aktionen können in derselben Browsersitzung über **--actions** ausgeführt werden.

**diwall-rpa**
: Führt eine Szenario-Datei (JSON oder YAML) aus, die eine Sequenz von Aktionen beschreibt,
und gibt eine JSON-Zeile zurück. Dies ist der Befehl, den Sie für alles verwenden sollten,
was wiederholbar ist, und der einzige, der Szenario-Assertions bewertet.

**diwall-watch**
: Visuelle Überwachung. Speichert ein Referenzbild einer Seite und vergleicht später erstellte Bilder damit – entweder durch einen lokalen Pixelvergleich oder durch eine Beschreibung eines lokalen Bilderkennungsmodells. Wird verwendet, um visuelle Fehler zu erkennen, ohne dass ein Mensch dies überprüfen muss.

**diwall-monter-secrets**, **diwall-demonter-secrets**
: Das verschlüsselte Credential-Verzeichnis von gocryptfs mounten und unmounten. Diwall weigert sich,
irgendeine Credential zu verarbeiten, während es geschlossen ist, und beendet den Vorgang mit dem Status 42,
anstatt auf eine schwächere Methode zurückzugreifen.

**diwall-monitor-verifier**
: Führt einen strukturellen Nicht-Regressions-Test für ein Szenario gegen eine gespeicherte Referenz durch und beendet den Vorgang mit einem Fehlercode, wenn Abweichungen festgestellt werden.  Soll von cron oder einem systemd-Timer gesteuert werden; es enthält keine eigene Schleife.

# GEMEINSAME OPTIONEN

Die folgenden Optionen werden von **diwall-shot** und **diwall-rpa** gemeinsam genutzt, es sei denn,
es wird anders angegeben. Dies ist eine Auswahl, nicht die vollständige Liste.

**--guide-version** *X.Y*
: Pflichtnachweis, dass **/opt/diwall/docs/GUIDE_LLM.md** gelesen wurde. Ohne diesen Nachweis
— und ohne einen noch gültigen lokalen Marker — wird der Befehl nicht ausgeführt und
beendet sich mit dem Fehlercode 1. Der erwartete Wert ist der Kommentar "*notice-version*" in Zeile 3 dieser
Anleitung. Dies ist der einzige Ort, an dem Diwall nicht optional ist.

**--version**
: Die installierte Version als JSON ausgeben und beenden, ohne einen Browser zu starten.
Unterscheidet sich von **--guide-version**; die beiden Zahlen stehen in keinem Zusammenhang miteinander.

**--mode** *fast*|*full*
: *fast* ist **--no-capture --a11y**: ohne PNG-Unterstützung, etwa zwei Sekunden schneller,
ausreichend, um den Status anzuzeigen. *full* ist die Standardeinstellung und erfasst das Rendering.

**--som**
: Nummeriere die sichtbaren interaktiven Elemente im Screenshot, sodass Aktionen sie anhand ihres Index und nicht anhand eines CSS-Selektors ansprechen können.

**--wait-until** *networkidle*|*load*|*domcontentloaded*
: Wann die anfängliche Navigation als abgeschlossen betrachtet wird. Standardmäßig wartet *networkidle* 500 ms lang auf Netzwerkaktivität und ist für die meisten Zielsysteme geeignet. Eine Seite, die kontinuierlich Daten abruft, bleibt niemals still – verwenden Sie in diesem Fall *load*; das Auslösen von **--timeout** hilft nicht, da die Seite nie fertig wird.
**diwall-shot** nur.

**--timeout** *MS*
: Timeout pro Operation in Millisekunden (Standardwert: 10000). Unterscheidet sich von
**--screenshot-timeout** (Standardwert: 120000), der nur den Screenshot abdeckt.

**--stealth**
: Entfernen Sie die automatischen Markierungen, die einen Browser ohne grafische Oberfläche identifizieren. Es ändert nicht die IP-Adresse des Benutzers und fälscht keine Identität – der Punkt ist eine gleichberechtigte Behandlung, nicht eine Verschleierung.

**--secrets** *DATEI*
: Löst Anmeldeinformationen aus einer expliziten JSON-Datei innerhalb eines gemounteten Verzeichnisses ab,
anstatt der standardmäßigen Host-basierten Suche.

**--no-evaluer**
: Verweigern Sie die Aktion "**evaluer**" für den gesamten Durchlauf – willkürlicher JavaScript-Code wird nicht auf der Zielseite ausgeführt.

**--no-filtre-evaluer**
: Deaktivieren der Standardausgabe-Neutralisierung von **evaluer**-Rückgabewerten, URLs und Fehlermeldungen – nur für explizite Debug-Läufe. Die Neutralisierung ist standardmäßig aktiviert; wenn sie deaktiviert ist, wird `boussole.filtre_evaluer_actif: false` in der Ausgabe gesetzt, damit der Operator sie anhand des JSON selbst überprüfen kann.

# DATEIEN

**/etc/diwall/diwall.conf**
: Konfiguration, die von den mitgelieferten Befehlen gelesen wird. Sie wird vom Administrator erstellt und niemals automatisch generiert. Die Umgebungsvariable **DIWALL_CONF** überschreibt diesen Pfad, wodurch mehrere Projekte separate Konfigurationen auf einer einzigen Maschine verwalten können.

**/opt/diwall/**
: Anwendungscode, die Python-Virtualisierungsumgebung und die Dokumentation, auf die die Befehle selbst verweisen.

**/opt/diwall/docs/GUIDE_LLM.md**
: Der Einstiegspunkt, den ein Agent lesen muss. **MANUEL.md** im selben
Verzeichnis enthält die genauen Befehle mit vollständigen Pfaden.

**/var/log/diwall/**
: Nur schreibgeschütztes Protokoll von Operationen. Wird bei **apt remove** beibehalten, aber bei **apt purge** gelöscht.

**/tmp/diwall/**
: Gespeicherte PNG-Dateien, werden beim Neustart gelöscht.

# RÜCKGABEWERT

**0**
: Der Testlauf wurde abgeschlossen. Beachten Sie, dass ein HTTP-Fehler 404 oder 403 auf dem Ziel im JSON-Format gemeldet wird, aber nicht als Fehler des Befehls selbst.

**1**
: Der Lauf ist fehlgeschlagen oder die Vorabprüfung wurde nicht erfolgreich abgeschlossen (*guide_non_lu*) .

**2**
: Inkompatible Argumente, abgelehnt bevor ein Browser gestartet wurde.

**42**
: Das Verzeichnis für Anmeldeinformationen ist geschlossen. Montieren Sie es mit **diwall-monter-secrets**.

**43**
: Eine Prüfsumme zur Integrität der Anmeldeinformationen stimmte nicht überein.

# BEISPIELE

Erfassen Sie eine Seite mit nummerierten Elementen und dem Accessibility-Baum:

    diwall-shot --url https://example.com --som --a11y --guide-version 1.2

Zeigen Sie nur den Zustand einer Seite an, ohne ein Bild zu erzeugen:

    diwall-shot --url https://example.com --mode fast --guide-version 1.2

Erreichen Sie ein Administrationspanel, das Statistiken kontinuierlich aktualisiert:

    diwall-shot --url http://target.local/ --wait-until load --som

Führen Sie ein Szenario mit Anmeldeinformationen aus einer expliziten Datei durch:

    diwall-rpa --scenario ./login.json --secrets ~/Vaults/project/creds.json

Überprüfen Sie, ob eine Seite keine strukturellen Rückschritte erfahren hat:

    diwall-monitor-verifier --scenario ./page.json --reference ./page.ref.json

# SIEHE AUCH

Die vollständige Dokumentation ist im Paket enthalten:
**/opt/diwall/docs/MANUEL.md** für das Betriebshandbuch,
**/opt/diwall/docs/GUIDE_LLM.md** für den Leitfaden für Mitarbeiter,
**/opt/diwall/docs/FAQ_LLM.md** für Antworten nach Funktionsweise und Version.

Die Projekt-Homepage wird mit dem Befehl **apt show diwall** aufgelistet.
