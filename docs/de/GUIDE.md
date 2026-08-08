# Diwall – Bedienungsanleitung

Version 1.10 – August 2026 (v1.23.0) – vier weitere Demonstrationsanwendungsfälle (selbstgehostete Observability, Verwaltung von Ticketing-Plattformen, Verfolgung lokaler Veranstaltungen, E-Commerce-Zugriff unter Verwendung von Respectful Navigation).

*Ebenfalls auf Französisch, Deutsch und Spanisch unter `docs/fr/`, `docs/de/` und `docs/es/`.*

---

## Warum Diwall – was Sie tatsächlich delegieren

### Das Problem, das Diwall löst

Wenn Sie mit einem LLM in einer Webanwendung arbeiten, entsteht eine Wahrnehmungsasymmetrie:
Das Modell liest Code, führt Befehle aus und beobachtet textuelle Ausgaben – aber es sieht nicht
die Benutzeroberfläche, die Ihre Benutzer sehen. Sie schon.

Diese Asymmetrie erzeugt eine bestimmte Form von Unsicherheit: Sie wissen nicht, ob das, was
das Modell beschreibt, mit dem übereinstimmt, was Sie in einem Browser sehen würden. Um sicherzugehen, müssen Sie
entweder ihm vertrauen oder es selbst überprüfen.

Diwall löst dieses Problem, indem es eine **gemeinsame visuelle Referenz** schafft:
das Modell erfasst die Benutzeroberfläche mit einem echten Browser (headless Chromium),
und Sie haben Zugriff auf dieselben PNG-Aufnahmen und Accessibility-Bäume.
Sie müssen dem Modell nicht mehr blind vertrauen – Sie beobachten denselben Zustand wie es.

```
 Browser (headless Chromium)
        │  Playwright drives it — click, fill, navigate
        ▼
 shot.py / rpa.py
        │  reads the resulting DOM state through parallel views
        ├──▶ capture_som   PNG, interactive elements numbered
        ├──▶ elements_som  JSON list — id, tag, text
        ├──▶ a11y_tree     accessibility tree, text
        └──▶ session file  cookies only (--sauver-session)
        │
        ▼
 boussole + JSON on stdout — same state you would see in a browser
        │
        ▼
 You (the model): read → analyse → decide → act → loop
```

### Was Sie delegieren

Diwall ermöglicht es Ihnen, **wiederholende und stressauslösende visuelle Überprüfungen** auszulagern:

- Überprüfen, ob 20 Seiten einer Website nach einem Deployment korrekt angezeigt werden.
- Bestätigen, dass ein Anmeldeformular auf der richtigen Oberfläche funktioniert.
- Sicherstellen, dass ein Deployment die Darstellung einer kritischen Ansicht nicht beeinträchtigt hat.
- Visuelle Validierung, ob eine Korrektur korrekt auf dem Bildschirm sichtbar ist.

Ohne Diwall sind diese Überprüfungen Ihre Verantwortung. Mit Diwall führt das Modell sie durch und meldet das Ergebnis – mit visuellen Beweisen.

### Was Sie behalten

Sie behalten die **übergeordnete Validierung des Ergebnisses**: Sie entscheiden, ob das Ergebnis,
das das Modell präsentiert, akzeptabel ist, mit Ihren Erwartungen übereinstimmt und im Einklang
mit dem steht, was Ihre Benutzer sehen sollten. Diese Entscheidung bleibt bei Ihnen.

### Respektvolles Navigieren (Version 1.15.0)

Diwall verschleiert seine Identität nicht, um die Erkennung durch Bots zu umgehen. `--stealth`
entfernt automatische technische Markierungen (`navigator.webdriver`), die Headless-Browser blockieren, unabhängig von der Absicht – es ändert weder die IP-Adresse des Betreibers noch dessen Identität, noch die Tatsache, dass der Durchlauf deklariert ist. Im Gegenzug meldet jeder Durchlauf seinen eigenen Fingerabdruck (`respect`: besuchte Seiten, ausgeführte Aktionen, Dauer) und respektiert konfigurierbare Höflichkeitsverzögerungen und harte Limits (`diwall.conf [navigation]`). Das Recht zu navigieren und die Pflicht zur messbaren Navigation werden als untrennbar behandelt – siehe `docs/RETOUR_EXPERIENCE.md` FR-77/FR-78/FR-79 für den Kontext, der dies geprägt hat.

Lokale Ziele – die Höflichkeitsverzögerung ist keine Doktrin, sondern eine Standardeinstellung.
(v1.19.0): Die ausgelieferte Einstellung `min_action_delay_ms: 800` schützt
einen unkonfigurierten ersten Start vor dem öffentlichen Internet – sie ist bedeutungslos
gegenüber Ihrem eigenen Entwicklungs-/Produktionssystem. Setzen Sie sie auf `0` in Ihrer lokalen
Konfiguration `diwall.conf` für lokales Debugging; siehe Abschnitt `docs/MANUEL.md` 3b.

### Wann ist Diwall das richtige Werkzeug?

| Anwendungsfall | Geeignet für Diwall? |
|---|---|
| Visuelle Validierung nach der Bereitstellung | ✓ Ja |
| Diagnose von Rendering-Fehlern | ✓ Ja |
| Navigation und Formulareingabe (max. ~30 s) | ✓ Ja |
| Delegation wiederholter Prüfungen | ✓ Ja |
| Lange Serveroperationen (Klonen ~2–5 min) | ✗ Nein — Playwright Timeout |
| Massenlöschung oder -änderung | ✗ Nein — direkte API-Aufrufe bevorzugen |
| Workflows, die ein Rollback erfordern | ✗ Nein — Diwall kann keine Änderungen rückgängig machen |

Für Fälle, in denen die Anwendung nicht geeignet ist, siehe Abschnitt "Wann man Diwall NICHT verwenden sollte" (Dokumentation der Reibungskörper FR-59 und FR-60).
`docs/GUIDE_LLM.md`

---

**Dieses Dokument ist für die Person bestimmt, die Diwall bedient.**

Es ergänzt `GUIDE_LLM.md` (für Modelle gedacht) mit konkreten Beispielen,
Schritt-für-Schritt-Anleitungen und Hinweisen zu häufigen Problempunkten.

---

## Demonstrationsszenarien

Die folgenden Beispiele veranschaulichen, wie eine "Agent-plus-Diwall"-Sitzung in der
Praxis aussehen kann. Sie dienen dazu, dass Sie sie im Kontext Ihrer eigenen Situation bewerten, und sind nicht als Empfehlung zur Übernahme eines bestimmten Ansatzes gedacht. Nur Fall 1 wird als ausführbares Szenario bereitgestellt; die anderen sind absichtlich deskriptiv, und jeder erklärt unter seiner eigenen Überschrift, warum dies so ist.

### Fall 1 – Fehlerbehebung bei lokalen CSS-/JavaScript-Dateien

Als ein echtes, ausführbares Szenario implementiert:
`scenarios/exemples/depannage_local.json`. Es diagnostiziert eine visuelle
Änderung oder eine blockierte Interaktion auf einer lokal bereitgestellten Schnittstelle – eine schnelle Prüfung
(`--mode fast`), die `erreurs_js`/`erreurs_console` liest, eine `--som` Aufnahme,
falls die Änderung rein visuell ist, dann wird die Korrektur mit
`watch.py --comparer-pixel` anhand einer Referenz validiert, die vor der
Regression erfasst wurde. Führen Sie es direkt aus:

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/exemples/depannage_local.json \
  --guide-version 1.2
```

### Fall 2 – Vergleich von Hardwarekomponenten in verschiedenen Geschäften

Ein Agent, der beauftragt wurde, den Preis und die Verfügbarkeit eines Produkts in mehreren Online-Shops zu vergleichen, könnte Diwall mit einem separaten URL-Findungs-Tool (z. B. einer lokalen Suchmaschine) verwenden, um potenzielle Shop-Seiten zu finden, dann Diwall im Sondermodus (`--mode fast`, ohne PNG) mit `evaluer` Aktionen nutzen, um den Preis/stock/specifications von jeder Seite zu extrahieren und schließlich die Ergebnisse selbst zu vergleichen.

**Bewusst nicht als versioniertes Szenario ausgeliefert:** einen bestimmten
Shop in einem öffentlichen, versionierten Szenario zu nennen, ist eine
Entscheidung, die Ihnen gehört — keine Vorgabe, die dieses Projekt an Ihrer
Stelle treffen sollte. Sie birgt zudem ein reales Fragilitätsrisiko: ein
öffentliches Szenario, das eine namentlich genannte kommerzielle Website
anspricht, kann Monate später scheitern, wenn sich deren Anti-Bot-Haltung
ändert (39 % der in `docs/RETOUR_EXPERIENCE.md` FR-77 untersuchten
kommerziellen Websites antworteten mit einer sofortigen Sperre) — was das
Beispiel mehr diskreditiert als es hilft. Wenn Sie diese Komposition selbst
bauen: jedes Werkzeug zur URL-Ermittlung, das Sie mit Diwall kombinieren (eine
lokale Suchinstanz oder anderes), ist kein Bestandteil von Diwall — es ist ein
eigenständiger Baustein, den der Agent darüber komponiert.

### Fall 3 – Erkundung und Zusammenfassung von technischer Dokumentation (Single-Page-Anwendungen)

Ein Agent, der mit der Erstellung eines Integrationshandbuchs für eine Dokumentationsseite beauftragt ist, die als Single-Page-Anwendung aufgebaut ist, könnte `rpa.py` zusammen mit `attendre_reseau_calme` verwenden, um das clientseitige Routing zu ermöglichen, den Accessibility-Baum im Schnellmodus zu extrahieren, um die Seitenstruktur abzubilden, dann Codeblöcke rekursiv mit `evaluer` durchzugehen, um ihren genauen Inhalt abzurufen, und schließlich das gesammelte Material zu einem Handbuch zusammenzufassen.

**Nicht als fertiges Szenario versendet, aus dem gleichen Grund wie Fall 2** –
die Nennung einer bestimmten Dokumentationsseite (oder, schlimmer noch, eines bestimmten Zahlungsanbieters, dessen Dokumentation zufällig ein funktionierendes Beispiel ist) stellt eine kommerzielle und reputationsbezogene Verpflichtung dar, die dieses Projekt grundsätzlich nicht eingehen sollte. Das gleiche Risiko von WAF-Schwachstellen besteht auch bei einem öffentlichen Szenario, das an ein bestimmtes reales Ziel gebunden ist.

### Fall 4 – Konfiguration eines selbst gehosteten Observability- oder Analyse-Dashboards

Ein Administrator, der ein selbstgehostetes Monitoring- oder Webanalyse-Dashboard hinter einem Reverse-Proxy einrichtet, kann Diwall verwenden, um die Benutzeroberfläche selbst zu steuern –
um ein Dashboard zu erstellen, eine Datenquelle anzuschließen und eine Alarmregel festzulegen –
auf die gleiche Weise, wie jedes andere Admin-Panel konfiguriert wird, anstatt Dateien manuell zu bearbeiten für Schritte, die die Benutzeroberfläche eigentlich abdecken soll. Dies umfasst auch Ziele, die sich
hinter einer HTTP Basic Auth-Authentifizierung auf Netzwerkebene befinden (`--http-credentials`,
Version 1.21.0) – dies wurde anhand einer echten, von Caddy geschützten Admin-Oberfläche bestätigt, nicht nur anhand eines simulierten Systems: die gespeicherten Zugangsdaten haben die
Authentifizierung beim ersten Versuch erfolgreich bestanden.

**Nicht als einheitliches Szenario ausgeliefert** – das Layout des Dashboards und die Namen der Datenquellen sind spezifisch für die Infrastruktur eines bestimmten Operators. Eine synthetische Entsprechung zu erstellen würde bedeuten, dass das, was bereits durch die lokale Testumgebung in Fall 1 abgedeckt wird (nämlich strukturelle Regression), dupliziert würde, und zwar nicht für diese Art von geführter, mehrstufiger Konfigurationsarbeit.

### Fall 5 – Betrieb einer Ticketing-Plattform von Anfang bis Ende

Diwall wurde über mehrere Sitzungen verwendet, um eine echte, selbst gehostete Ticketinstallation zu konfigurieren und zu betreiben – einschließlich der Einrichtung von Veranstaltungen, Ticketkategorien, einer benutzerdefinierten Domain sowie der Tools für den Scannen/Check-in am Veranstaltungstag – und zwar über die gleiche Weboberfläche, die auch ein menschlicher Administrator verwenden würde. Es gab echte Probleme, die auf dem Weg gelöst wurden (Session-Management, Eigenheiten bei Dropdown-Menüs, eine Berechtigungsabfrage, die einen unbeaufsichtigten Schritt blockierte) – es war also keine reibungslose Erfolgsgeschichte, was Teil dessen ist, was dieses Beispiel nützlich macht: Die Hindernisse waren typische Probleme der Webautomatisierung und nicht etwas Spezifisches für Diwall.

**Nicht als fest definiertes Szenario versendet** – eine Ticketkonfiguration betrifft
Abrechnungsdetails und spezifische Informationen zur Veranstaltung, die für den jeweiligen Betreiber einzigartig sind, aus dem gleichen Grund wie
Fall 2.

### Fall 6 – Verfolgung eines regionalen Veranstaltungskalenders

Eine einfache Verwendung von semantischen Abfragen: Ein Agent wird gebeten, einen lokalen Ereigniskalender auf bevorstehende Veranstaltungen zu überprüfen, ohne im Voraus zu wissen, welche Seite die Antwort enthält. Diwalls schneller Modus (`--mode fast`, keine Erfassung) in Kombination mit dem Accessibility-Baum ermöglicht es dem Agenten, innerhalb weniger Anfragen zu scannen und Ergebnisse zurückzumelden – für diese Art von rein lesender, textbasierter Aufgabe ist kein Vision-Modell erforderlich. Eine Sitzung lieferte auch ein sauberes, reales Beispiel für das dokumentierte Fehlalarmverhalten des WAF-Signals: eine Seite wurde normal geladen (reichhaltiger Inhalt, kein Captcha, keine Zwischenseite), während `respect.waf_bloquants` dennoch ausgelöst wurde, weil eine nicht zusammenhängende Ressource eines Drittanbieters auf der Seite ein Erkennungswort enthielt – dies wurde in etwa einer Minute behoben, indem der bereits im selben Antwort-Dokument vorhandene Accessibility-Baum gelesen wurde, genau wie von der Regel "Signal, niemals ein Lock" des Handbuchs erwartet.

**Nicht als fest definiertes Szenario versendet** – eine bestimmte regionale Ereignis-Website
ist kein stabiles, reproduzierbares öffentliches Ziel, und die Benennung einer solchen Website öffentlich liegt im Ermessen des Betreibers, nicht in der Standardeinstellung des Projekts.

### Fall 7 – Test des Zugriffs auf E-Commerce-Seiten unter realen Bedingungen im Rahmen von "Respectful Navigation"

Eine wiederkehrende, ehrliche Beobachtung aus tatsächlichen Sitzungen: verwendet mit Respekt
(durch Ratenbegrenzung verursachte Verzögerungen, Beschränkungen für Seiten/Aktionen, `--stealth` aktiv, kein Versuch,
auf eine echte Blockade zuzugreifen), Diwall-Tests gegen verschiedene E-Commerce-
Seiten zeigen, dass ein großer Teil der großen Plattformen einen direkten
Block zurückgibt – HTTP 403 oder eine Anfrage, die nie abgeschlossen wird – unabhängig davon, wie
höflich der Datenverkehr ist. Dies ist kein Fehler von Diwall, den es beheben muss:
Die Anti-Bot-Strategie ist die eigene Wahl der Website, und Diwall versucht nicht,
diese zu umgehen (siehe "Respektvolle Navigation" oben). Praktisch: Bei
Vergleichsaufgaben für große kommerzielle Plattformen sollte man mit einer
bedeutenden Anzahl von Sackgassen rechnen und ein Block-Signal
(`respect.waf_bloquants`) als Information betrachten, um einen anderen Weg zu finden, nicht als
Fehler, der wiederholt werden soll.

Eine Unterscheidung, die es wert ist, im Hinterkopf behalten zu werden: Ein unsichtbarer Verifizierungsbildschirm, der
niemals aufgelöst wird und nichts präsentiert, auf das man reagieren könnte (keine Checkbox, keine Bildaufgabe), unterscheidet sich von einem interaktiven CAPTCHA. Letzteres kann ehrlich beantwortet werden – ein Agent, der im Auftrag einer bestimmten Person handelt, von deren eigener IP-Adresse aus, ist nicht der "Roboter", an den die Frage gerichtet ist. Der erste bietet einfach keine Möglichkeit für den Agenten, etwas zu tun, und das Umgehen (IP-Rotation, TLS-Fingerprint-Spoofing) fällt außerhalb dessen, was Diwall tut.

**Bewusst nicht als versioniertes Szenario ausgeliefert, und bewusst ohne
Nennung der beteiligten Plattformen** — siehe die Überlegung zur
WAF-Fragilität unter Fall 2: eine datierte Tabelle mit Sperre/keine Sperre,
gebunden an namentlich genannte kommerzielle Websites, veraltet und untergräbt
ihre eigene Aussage schneller, als sie sie belegt. `docs/RETOUR_EXPERIENCE.md`
FR-77 dokumentiert dasselbe Muster im Panel-Maßstab (39 % sofortige Sperrrate).

---

## Voraussetzungen vor dem Start

```bash
# 1. Überprüfen Sie, ob Diwall antwortet.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://example.com --som --a11y
# → must return {"succes": true, ...}

# 2. Überprüfen Sie, ob das verschlüsselte Verzeichnis gemountet ist (falls gocryptfs verwendet wird).
ls ~/Vaults/Diwall/
# → müssen `.json`-Dateien anzeigen, keine verschlüsselten Inhalte.

# 3. Überprüfen Sie die Anmeldeinformationen für eine Domain.
/opt/diwall/venv/bin/python3 -c "
import sys; sys.path.insert(0, '/opt/diwall')
from lib.repertoire_chiffre import lire_credential
print('OK' if lire_credential('target.local', 'password') else 'EMPTY')
"
```

---

## Konfiguration der Anmeldeinformationen pro Projekt

Jedes Projekt kann sein eigenes Verzeichnis für Anmeldeinformationen haben. Zwei Methoden:

**Methode 1 – Direkte Umgebungsvariable (einmalige Ausführung):**

```bash
DIWALL_SECRETS_DIR=~/Vaults/MyProject \
  /opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

Methode 2 – Projektdatei `.diwall.conf` (empfohlen für wiederkehrende Projekte):

```bash
# Erstellen Sie die Datei im Projektstammverzeichnis.
echo '{"secrets_dir": "../MyProject-secrets"}' > ~/git/MyProject/.diwall.conf

# Then prefix each invocation (or export at the start of the shell session)
export DIWALL_CONF=~/git/MyProject/.diwall.conf
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url …
```

Der `secrets_dir` in `.diwall.conf` kann ein relativer Pfad sein – er wird relativ zum Speicherort der `.diwall.conf` Datei aufgelöst.

---

## Eine Seite erfassen und analysieren

```bash
# Schnelle Prüfung (keine PNG-Dateien – ca. 2 Sekunden, schreibgeschützt).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --mode fast
# Gibt url_courante, titre_page, a11y_tree im JSON zurück.

# Vollständige Erfassung mit nummerierten Elementen.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ \
  --som --a11y
# Der PNG-Screenshot befindet sich unter /tmp/diwall/capture_<ts>.png.
```

**Was Sie erhalten:**
- `boussole.url_courante` + `boussole.titre_page`: effektive URL und Titel nach der Navigation
- `capture`: Pfad zum PNG der Seite, wie sie dargestellt wurde
- `capture_som`: annotiertes PNG mit den Elementnummern
- `a11y_tree`: Struktur der Seite als Text (Überschriften, Felder, Schaltflächen)

---

## Automatisierung eines Anmeldeformulars

**Schritt 1** – Bereiten Sie die Datei mit den Zugangsdaten vor.

Die Datei mit den Zugangsdaten hat den Namen `<hostname>.json`, wobei `hostname` das Ergebnis von `urlparse(url).hostname` ist. Für `https://app.example.com/` lautet der Dateiname `app.example.com.json`.

```json
{"username": "admin@example.com", "password": "my-secret"}
```

**Schritt 2** — Untersuchen Sie die Anmeldeseite.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://app.example.com/login/ --som --a11y
```

Öffnen Sie das annotierte PNG-Bild (`capture_som`), um die SoM-IDs der Felder zu identifizieren.

**Schritt 3** – Schreiben Sie das Szenario.

```bash
cat > /tmp/login.json << 'EOF'
{
  "nom": "app_login",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "capturer",     "nom": "after-login"}
  ]
}
EOF
```

**Schritt 4** — Ausführen.

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /tmp/login.json --som
```

---

## Gültigkeit mehrerer Seiten mit einem einzigen Aufruf prüfen

Um N Seiten einer authentifizierten Website zu überprüfen, ohne jedes Mal die Anmeldung erneut durchführen zu müssen:

```bash
cat > /tmp/audit.json << 'EOF'
{
  "nom": "audit_pages",
  "url": "https://app.example.com/login/",
  "actions": [
    {"type": "remplir_som", "id": 1, "valeur": "depuis_secrets", "secret_cle": "username"},
    {"type": "remplir_som", "id": 2, "valeur": "depuis_secrets", "secret_cle": "password"},
    {"type": "cliquer_som", "id": 3},
    {"type": "pause",        "ms": 2000},
    {"type": "naviguer",     "url": "https://app.example.com/dashboard/"},
    {"type": "capturer",     "nom": "dashboard"},
    {"type": "naviguer",     "url": "https://app.example.com/settings/"},
    {"type": "capturer",     "nom": "settings"}
  ]
}
EOF
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario /tmp/audit.json --som
```

---

## Extrahieren eines Wertes von der Seite

Um eine Textzeichenkette, einen Zähler oder einen beliebigen DOM-Wert auszulesen:

```bash
cat > /tmp/extract.json << 'EOF'
[{"type": "evaluer", "script": "document.title"}]
EOF
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://target.local/ --actions /tmp/extract.json
# → führt zu evaluations[0].valeur
```

**Wichtig**: schreiben Sie JS-Skripte immer in eine `--actions`-Datei,
niemals inline mit `--action` (die Shell beschädigt verschachtelte Anführungszeichen).

---

## Visuelle Überwachung einrichten

```bash
# 1. Speichern Sie die visuelle Referenz.
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --nom home

# 2. Später vergleichen (Pixel-Differenz).
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ \
  --comparer-pixel /opt/diwall/references/target.local_home/reference.png \
  --nom home
# → Urteil: stabil / Drift / Regression (Exit-Code 0 oder 1)

# 3. Auf einer authentifizierten Seite: zuerst mit rpa.py erfassen, dann speichern.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario /tmp/login.json > /tmp/out.json
CAPTURE=$(python3 -c "import json; d=json.load(open('/tmp/out.json')); print(d['captures_intermediaires'][-1])")
/opt/diwall/venv/bin/python3 /opt/diwall/watch.py \
  --url https://target.local/ --sauver-reference --capture "$CAPTURE" --nom dashboard
```

---

## Einrichten einer kontinuierlichen Strukturüberwachung (Version 1.18.0)

Ergänzt die oben beschriebene visuelle Überwachung: Dies prüft die *Struktur*
(Statuscode, Anzahl der DOM-Elemente, Ergebnisse der JavaScript-Auswertung) der Seite anstelle ihres
*Aussehens* – kostengünstiger und erfasst eine andere Art von Regression (z. B. ein verschwundenes Formularfeld mit unveränderter Anordnung).

```bash
# 1. Speichern Sie eine strukturelle Referenz, einmalig.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --sauver-verifier-reference /opt/diwall/references/my-scenario.ref.json

# 2. Ein Check- und Alarmvorgang.
bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --reference /opt/diwall/references/my-scenario.ref.json \
  --ntfy-topic diwall-monitoring
```

Stumm, wenn stabil; ein `ntfy` Push, wenn eine Regression erkannt wird. Planen Sie dies selbst mit Cron – das Skript führt einen Durchlauf durch und beendet sich, es läuft nicht in einer Schleife.
`scripts/*.sh` wird niemals auf `/opt/diwall/` bereitgestellt, sodass der Cron-Eintrag von der Git-Quelle aus ausgeführt wird, als Ihr eigener Benutzer (nicht das Dienstkonto `diwall`, das keinen Zugriff auf `~/git/Diwall/Diwall/` hat):

```bash
# crontab -e (Ihre eigene Crontab)
*/15 * * * * bash ~/git/Diwall/Diwall/scripts/monitor-verifier.sh \
  --scenario /opt/diwall/scenarios/my-scenario.json \
  --reference /opt/diwall/references/my-scenario.ref.json \
  --ntfy-topic diwall-monitoring \
  >> /var/log/diwall/cron-structural.jsonl 2>&1
```

---

## Häufige Fehlerquellen

| Situation | Was zu tun ist |
|---|---|
| `FileNotFoundError` in der Datei mit den Zugangsdaten | Überprüfen Sie, ob die JSON-Datei mit dem vollständigen FQDN (`urlparse(url).hostname`) benannt ist. |
| `SecretsFermesError` (Exit 42) | Das verschlüsselte Verzeichnis mounten: `bash ~/git/Diwall/Diwall/scripts/monter-repertoire-chiffre.sh` |
| Ungültiges JSON in der Ausgabe | Verwenden Sie `2>/dev/null \| tail -1`, um nur die JSON-Zeile zu extrahieren. |
| SoM-IDs unterscheiden sich zwischen Sitzungen | Erwartet – SoM-IDs werden bei jeder Aufnahme neu berechnet. Verwenden Sie sie nicht wiederholt über mehrere Sitzungen hinweg. |
| Anmeldung, gefolgt von einer Django-Weiterleitung zum Dashboard | Verwenden Sie `naviguer` nicht in einer fortgesetzten Django-Sitzung – übergeben Sie die URL über `--url`. |
| Das Formularfeld `<select>` ist nicht ausgefüllt | Verwenden Sie `remplir_som` (nicht `remplir`) mit der SoM-ID des `<select>`. |
| Ein Klick hat keine Auswirkung auf einen Button außerhalb des sichtbaren Bereichs | Fügen Sie `{"type":"defiler","selecteur":"#the-button"}` vor dem Klick ein. |
| `auth_status: "active"` auch auf der Anmeldeseite | Der positive Selektor ist mehrdeutig (persistenter Header) – fügen Sie `--auth-indicator-negative .btn-login` hinzu. |
| Web Components-Elemente werden nicht von SoM nummeriert | Fügen Sie `--shadow-dom` hinzu (Angular, Lit, Stencil). |
| `respect.waf_bloquants` erscheint auf einer Seite, die tatsächlich nicht blockiert ist | Die Erkennung basiert auf Schlüsselwörtern (v1.16.0, verfeinert v1.17.2) – behandeln Sie dies als ein Signal und nicht als ein Urteil. Wenn es auf einer Seite weiterhin angezeigt wird, von der Sie bestätigt haben, dass sie nicht blockiert ist, fügen Sie `--ignorer-waf` hinzu. |
| `cliquer_som` klickt auf das falsche Element auf einer Seite, die sich zwischen Aufnahme und Klick geändert hat | Fügen Sie `--som-rafraichir` hinzu (v1.17.0) – behebt dies durch einen stabilen Marker anstelle von Live-Reindexierung. |
| Ein langes RPA-Szenario schlägt mitten im Ablauf fehl, und Sie möchten die abgeschlossenen Schritte nicht erneut ausführen | Fügen Sie `--checkpoint FILE` hinzu (v1.17.0) – starten Sie den gleichen Befehl neu, um fortzufahren; der DOM-Zustand wird nicht beibehalten, nur Sitzung + Aktionsposition. |
| Interaktive Elemente innerhalb eines Iframes sind für Diwall unsichtbar | SoM kann Inhalte von Iframes (gleichnamig oder übergeordnet) nicht nummerieren – verwenden Sie `cliquer_iframe`/`remplir_iframe` (v1.17.0) mit einem expliziten CSS-Selektor oder `iframe_chemin` (v1.18.0) für einen innerhalb eines anderen verschachtelten Iframe. |
| Ihr Modell meldet `"erreur": "guide_non_lu"` / Exit 1 bei seinem ersten Diwall-Aufruf | Erwartet beim ersten Mal, dass ein Modell Diwall auf dieser Maschine als dieser Betriebssystembenutzer verwendet (v1.18.0) – es muss `docs/GUIDE_LLM.md` lesen und `--guide-version` einmal übergeben. Dies ist absichtlich und kein Fehler – weisen Sie das Modell an, die Anleitung zu lesen, anstatt den Fehler zu umgehen. |

---

## Deinstallation von Diwall

Das Skript `~/git/Diwall/Diwall/scripts/uninstall.sh` entfernt die Installation sauber, in der umgekehrten Reihenfolge von `install.sh`.

```bash
# Beobachten Sie, was entfernt wird, ohne etwas zu tun.
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --dry-run

# Vollständige Deinstallation (interaktive Bestätigung).
bash ~/git/Diwall/Diwall/scripts/uninstall.sh

# Ohne Bestätigung (Kalttests, mehrfache Neuinstallationen).
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme && bash ~/git/Diwall/Diwall/scripts/install.sh
```

Was wird entfernt:

| Item | Detail |
|---|---|
| `/opt/diwall/` | Code, Python venv, Konfiguration |
| `/var/log/diwall/` | Operationsprotokolle |
| `diwall` system user | Erstellt ausschließlich für Diwall |
| `diwall` system group | Gleiches gilt |
| Gruppenmitgliedschaft | Ihr Konto wird aus der Gruppe `diwall` entfernt. |
| git pre-push hook | `core.hooksPath` deaktiviert im Quellrepository |

**Was niemals verändert wird:**
- `~/Vaults/` – Ihre Zugangsdaten
- `~/git/Diwall/` – Git-Quellen
- Der Browser-Cache von Playwright (***`~/.cache/ms-playwright/`***)

Beweise erfassen (`/var/log/diwall/preuves/`): Wenn das Verzeichnis Unterverzeichnisse enthält, werden diese standardmäßig mit einer Warnung beibehalten. Um sie zu entfernen:

```bash
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme --purge-preuves
```

---

## Einsicht in die Betriebshistorie

```bash
# Alle Operationen an einem Ziel.
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local

# Nur mutierende Operationen (Klicks, Formulareingaben).
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local --mutatif

# Von einem Datum
/opt/diwall/venv/bin/python3 /opt/diwall/journal.py --cible target.local \
  --depuis 2026-06-01
```
