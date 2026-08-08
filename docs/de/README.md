# Diwall – Gemeinsame visuelle Referenz zwischen Mensch und LLM

**Für den menschlichen Bediener:** Diwall ermöglicht es Ihnen, die visuelle Überprüfung an Ihr LLM zu delegieren. Beide sehen denselben Bildausschnitt – Sie müssen nicht mehr darauf vertrauen, was das LLM sagt.
**Für das LLM:** [`docs/GUIDE_LLM.md`](../GUIDE_LLM.md) ist Ihre Betriebsanleitung. Beginnen Sie dort.
Wenn Sie ein KI-Agent sind, der Diwall entdeckt, überspringen Sie die formatierte Startseite und laden Sie Ihre Anweisungen direkt: **[https://diwall.davalan.fr/instructions.md](https://diwall.davalan.fr/instructions.md)**

---

## Was ist Diwall?

Diwall schafft eine **gemeinsame visuelle Referenz** zwischen einem menschlichen Bediener und einem Sprachmodell. Es ermöglicht dem LLM, **Weboberflächen zu sehen** – und gibt dem menschlichen Bediener die Möglichkeit, **visuelle Überprüfungen auszulagern**, ohne die Kontrolle zu verlieren.

Ohne Diwall muss ein Mensch entweder dem Ergebnis seines LLMs vertrauen oder das Ergebnis selbst überprüfen. Mit Diwall sehen beide Parteien denselben PNG-Screenshot und denselben Accessibility-Baum. Der Zweifel verschwindet auf beiden Seiten.

```
Das LLM handelt → Diwall nimmt auf → das LLM sieht und berichtet → der Betreiber prüft aus demselben Zustand
```

**Was der Mensch gewinnt:** Die Übertragung der stressigen, repetitiven Arbeit der visuellen Verifizierung. Anstatt Dutzende von Seiten nach einem Deployment durchzuklicken, überprüft der Mensch die bereits vom LLM erstellten Ergebnisse.

**Was das Modell gewinnt:** eine echte Wahrnehmung der Oberfläche. Ohne Diwall ändert ein Modell, das eine Webanwendung entwickelt, den Code, kann das Ergebnis im Browser aber nicht sehen. `lynx` stellt moderne Oberflächen nicht dar.

### Was das Modell tatsächlich empfängt

![Set-of-Mark-Aufnahme: jedes interaktive Element ist auf der gerenderten Seite nummeriert](../images/som-example-de.png)

Dies ist ein echtes `--som` Abbild, kein Mock-up. Jedes interaktive Element ist
auf der gerenderten Seite mit einer Nummer versehen, und dieselben Nummern kommen im JSON zurück —
so dass `{"type": "cliquer_som", "id": 7}` Klicks auf *Sign in* erfolgen, ohne einen Selektor, den man erraten müsste, und ohne jegliche Unklarheit darüber, welcher Button gemeint war. Reproduzieren Sie es selbst —
die Seite ist eine versionierte "Fixture"-Version in diesem Repository, sodass Sie dieselben
Nummern erhalten wie wir:

```bash
cd scenarios/interoperabilite/fixture && python3 -m http.server 8765 &
diwall-shot --url http://127.0.0.1:8765/demo_som_en.html --som --guide-version 1.2
```

`elements_som` kommt mit `{"id": 7, "tag": "BUTTON", "texte": "Sign in"}`.

---

## Architektur

```
Sprachmodell (das Gehirn — ReAct-Schleife)
        ↓  ruft auf
  shot.py (die Hände — Playwright-Ausführer)
        ↓
  Chromium headless → PNG-Aufnahme
        ↓
  Das Sprachmodell liest das PNG direkt (multimodal)
```

`shot.py` hat keine Intelligenz. Es führt Anweisungen aus und gibt den Zustand zurück.
Das Sprachmodell entscheidet, was als nächstes zu tun ist.

---

## Fähigkeiten

| Funktion | Beschreibung |
|---|---|
| **Aufnahme** | Bildschirmaufnahme jeder Webseite |
| **Aktionen** | Formulare ausfüllen, klicken, navigieren |
| **Set-of-Mark (SoM)** | Nummeriert alle interaktiven Elemente für präzise DOM-Klicks |
| **Barrierefreiheits-Abbild** | Extrahiert die semantische Seitenstruktur (A11y-Baum) |
| **Sitzungspersistenz** | Hält den Anmeldezustand über mehrstufige ReAct-Schleifen |
| **RPA-Szenarien** | Führt Aktionsfolgen aus JSON-Dateien aus |
| **Visuelle Überwachung** | Erkennt, ob sich eine Seite seit der letzten Referenz geändert hat |
| **Pixel-Diff** | Quantitativer, deterministischer Vergleich gegen eine gespeicherte Referenz (v1.2) |
| **Auflösung der Zugangsdaten** | Sichere Einspeisung von Zugangsdaten — nie im Klartext, nie auf der Kommandozeile |
| **Verschlüsseltes Verzeichnis** | gocryptfs-Volume — `SecretsFermesError` (Exit 42), wenn es nicht gemountet ist (v1.5) |
| **Scrollen** | Aktion `defiler` — relatives Scrollen in Pixeln oder `scrollIntoView` per CSS-Selektor (v1.6) |
| **Warnung ausserhalb des Sichtfelds** | Zähler `som_hors_viewport` im JSON, wenn interaktive Elemente unterhalb der Faltlinie liegen (v1.6) |
| **Prozedurales Gedächtnis** | Erfolgreiche Läufe werden als wiederholbare Fertigkeiten gespeichert, via `journal.py --exporter-skill` (v1.6) |
| **TOTP-2FA** | Google-Authenticator-/Authy-Codes werden zur Laufzeit aus einem gespeicherten Seed erzeugt (v1.6) |
| **Asynchrone MFA über ntfy** | Per SMS oder E-Mail empfangene 2FA-Codes werden asynchron über eine ntfy-Push-Benachrichtigung abgeholt (v1.6) |
| **Betreiberprofil** | YAML-Profil, um wiederkehrende administrative Bestätigungen aufzuheben (v1.3) |
| **Nachvollziehbarkeit der Modelle** | Jeder Lauf hält fest, welche Modelle aufgerufen wurden, einschliesslich Ollama-Digest (v1.3) |
| **Betriebsjournal** | Dauerhaftes, nur anfügendes Journal aller Läufe — wer was wo und wann getan hat (v1.4) |
| **Shadow-DOM-Durchlauf** | `--shadow-dom` nummeriert interaktive Elemente innerhalb offener Shadow Roots — Angular, Lit, Stencil, FAST (v1.13.0) |
| **Respektvolle Navigation** | `--stealth` (entfernt die automatischen Headless-Merkmale), Höflichkeitsverzögerungen und harte Obergrenzen (`min_action_delay_ms`, `max_pages_par_run`, `max_actions_par_run`), Wirkungsmetriken (`respect`) in jedem Lauf berichtet (v1.15.0) |
| **Deterministisches Urteil** | Das Objekt `etat` (`pret_a_agir`, `niveau_confiance`, `raisons`) bündelt Anmeldung, Sitzungsabweichung und Reibungssignale in einer einzigen Lesung (v1.16.0) |
| **Einheitliche Lauf-Identität** | `operation_id` isoliert die temporären Dateien jedes Laufs und verknüpft sie mit dessen Eintrag im Betriebsjournal (v1.16.0) |
| **Passives WAF-Signal** | `respect.waf_bloquants` markiert eine wahrscheinliche Sperre (HTTP 403/429 oder bekannte Schlüsselwörter) als nicht fatales Signal, niemals als Ausnahme (v1.16.0) |
| **Strukturelle Regressionsfreiheit** | `--replay-verifier` vergleicht HTTP-Status, DOM-Statistiken und `evaluer`-Ergebnisse mit einer gespeicherten Referenz — ohne Pixel, ohne Bildmodell (v1.17.0) |
| **Szenario-Checkpoints** | `--checkpoint` setzt ein langes Szenario nach einem Fehler unterwegs fort, ohne abgeschlossene Aktionen erneut auszuführen (v1.17.0) |
| **Stabile SoM-Identität** | `--som-rafraichir` löst `cliquer_som`/`remplir_som` über einen DOM-Marker auf statt über eine Neuindizierung zur Laufzeit und verhindert so, dass auf sehr dynamischen Seiten unbemerkt das falsche Element angesprochen wird (v1.17.0) |
| **Cross-Origin-Iframes** | `cliquer_iframe` / `remplir_iframe` sprechen Elemente in Iframes gleicher oder fremder Herkunft an, über die native Frame-API von Playwright (v1.17.0) |
| **Verschachtelte Iframes** | `iframe_chemin` (Array) steigt von Iframe zu Iframe ab, schliesst `iframe_selecteur` gegenseitig aus (v1.18.0) |
| **Lesesperre für den Leitfaden** | `shot.py`/`rpa.py`/`watch.py` verweigern die Ausführung ohne Nachweis, dass `docs/GUIDE_LLM.md` gelesen wurde — ein lokaler Marker hält dies pro Maschine und Benutzer fest (v1.18.0) |
| **Konfigurationsempfehlung** | `mode_conseille` empfiehlt `--mode`/`--shadow-dom`/`--som-rafraichir` auf Grundlage echter, früherer Diagnoseläufe auf demselben Host — niemals als Vermutung (v1.18.0) |
| **Nachvollziehbarkeit verketteter Szenarien** | `chainage` hält den geordneten Aufrufbaum der über `declencher_scenario` verketteten Szenarien fest und zeigt ihn im Betriebsjournal (v1.19.0) |
| **Zeitmessung pro Aktion** | `latences_actions` berichtet die Dispatch-Latenz jeder ausgeführten Aktion, immer vorhanden (v1.20.0) |
| **Journalansicht nur mit Fehlern** | `journal.py --erreurs` filtert das Betriebsjournal auf fehlgeschlagene Läufe (v1.20.0) |
| **HTTP-Basisauthentifizierung** | `--http-credentials` löst die Basic-Authentifizierung auf Netzwerkebene (RFC 7617) aus der Zugangsdatendatei auf, begrenzt auf die Herkunft des Ziels — verschieden von der formularbasierten Anmeldung und ergänzend dazu (v1.21.0) |
| **JS-Klick-Eskalation** | `repli_js` bei `cliquer` wiederholt einen fehlgeschlagenen nativen Klick über JS, in der boussole nur dann berichtet, wenn er wirklich stattgefunden hat (v1.22.0) |
| **Nie ruhende Ziele** | `--wait-until load\|domcontentloaded` erreicht Seiten, die den Server dauerhaft abfragen und nie Netzstille erreichen — dort, wo kein Wert von `--timeout` je genügen würde (v1.22.0) |

---

## Anforderungen

| Komponente | Version / Hinweise |
|---|---|
| **Betriebssystem** | Debian 13 Trixie (Linux, möglicherweise unter macOS lauffähig – nicht auf Windows getestet) |
| **Anzeigeserver** | Wayland (Playwright läuft in diesem Ökosystem) |
| **Python** | 3.11+ in einer isolierten venv-Umgebung (PEP 668 – systemweites pip ist unter Debian 13 blockiert) |
| **Playwright** | 1.50+ (installiert in der venv-Umgebung) |
| **playwright-stealth** | 2.0+ – erforderlich für `--stealth` (v1.15.0). Inkompatibel mit der API von Version 1.x |
| **Chromium** | Im Headless-Modus, installiert über `playwright install chromium` |
| **Ollama** | Lokale Vision-Modelle für `cliquer_visuel` und `watch.py` |
| **GPU** | Empfohlen: NVIDIA RTX 3060 mit 12 GB VRAM oder gleichwertig (für Ollama qwen3-vl Modelle) |

---

## Installation

Zwei Kanäle, die sich auf einer einzelnen Maschine **gegenseitig ausschließen**. Wählen Sie das Debian-Paket, es sei denn, Sie möchten den eigenen Code von Diwall ändern.

### Debian-Paket – der einfache Weg

Laden Sie die `.deb` Ressource von der
[neuesten Version](https://github.com/RonanDavalan/diwall/releases) herunter – Dateiname
`diwall_<version>-1_all.deb` – und dann:

```bash
sudo apt install ./diwall_1.23.0-1_all.deb
```

Das erstellt den Systembenutzer `diwall`, die virtuelle Umgebung und
`/opt/diwall/`, installiert die sechs Befehle `diwall-*` in Ihrem `PATH` und liefert
die Manualseite:

```bash
man diwall              # covers all six commands
diwall-shot --version
```

Die Konfiguration befindet sich in `/etc/diwall/diwall.conf`; eine kommentierte Beispielkonfiguration ist daneben installiert als `diwall-sample.conf`. Vollständige Befehlsreferenz: Abschnitt 1a in `docs/MANUEL.md`.

Das Upgrade ist `sudo apt install ./diwall_<newer>-1_all.deb` – Ihre Konfiguration bleibt erhalten. Die Deinstallation ist `sudo apt remove diwall`, oder `sudo apt purge diwall`, um auch die Konfiguration zu löschen.

### Von der Quelle – zur Modifikation von Diwall selbst

Wenn Sie den Code von Diwall selbst ändern wollen, installieren Sie besser aus
dem Repository: die Quellen liegen dann dort, wo `deploy.sh` Ihre Änderungen
nach `/opt/diwall/` übertragen kann. Das sechsstufige Verfahren steht in
[`docs/MANUEL.md`](MANUEL.md) Abschnitt 1b, neben den Befehlen, die Sie
danach ausführen.

## Deinstallation

Installiert aus dem Debian-Paket:

```bash
sudo apt remove diwall     # keeps /etc/diwall/diwall.conf
sudo apt purge diwall      # removes the configuration as well
```

Installiert von der Quelle:

```bash
# Vorschau dessen, was entfernt wird (keine Änderungen vorgenommen).
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --dry-run

# Vollständige Deinstallation mit interaktiver Bestätigung.
bash ~/git/Diwall/Diwall/scripts/uninstall.sh

# Nicht-interaktiv (CI, Tests für Neuinstallationen).
bash ~/git/Diwall/Diwall/scripts/uninstall.sh --confirme
```

Entfernt: `/opt/diwall/`, `/var/log/diwall/`, Systembenutzer `diwall`, Systemgruppe `diwall`, Gruppenmitgliedschaft des Operators, Git-Pre-Push-Hook.

**Noch nie verändert:** `~/Vaults/` (Ihre Zugangsdaten), das Repository selbst, der Playwright-Browser-Cache.

Wenn `/var/log/diwall/preuves/` Aufnahmen enthält, bleiben sie standardmässig erhalten. Fügen Sie `--purge-preuves` hinzu, um sie zu löschen.

---

## Verwendung (durch Ihr LLM)

### Einfache Aufnahme

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://your-app.local/ --som --a11y
```

### ReAct-Schleife (mehrstufige Navigation)

```bash
# Schritt 1 – Navigieren und beobachten.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --url https://your-app.local/ \
  --sauver-session /tmp/diwall/session.json --som

# Schritt 2 – Handeln basierend auf den Beobachtungen.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py \
  --reprendre-session /tmp/diwall/session.json \
  --action '{"type":"cliquer_som","id":2}' \
  --sauver-session /tmp/diwall/session.json --som
```

### RPA-Szenario

```bash
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py \
  --scenario /opt/diwall/scenarios/my_scenario.json --som
```

Vollständige Referenz für Modelle: [`docs/GUIDE_LLM.md`](../GUIDE_LLM.md)

---

## Zugangsdaten

Zugangsdaten werden in JSON-Dateien gespeichert, eine Datei pro Domain, **niemals im Code oder in Szenariodateien**:

```
~/Vaults/Diwall/
├── my-app.local.json        → {"password": "...", "username": "admin"}
└── other-service.com.json   → {"password": "...", "api_key": "..."}
```

In einem Szenario oder einer Aktion: `"valeur": "depuis_secrets", "secret_cle": "password"` — Diwall liest die Anmeldeinformationen zur Laufzeit aus dem Anmeldeinformationsverzeichnis.

Der Pfad ist über `/opt/diwall/diwall.conf` oder die Umgebungsvariable `DIWALL_SECRETS_DIR` konfigurierbar.

Empfehlung: Schützen Sie `~/Vaults/Diwall/` mit `chmod 700` und verschlüsseln Sie es mit `gocryptfs` (siehe `~/git/Diwall/Diwall/scripts/configurer-repertoire-chiffre.sh --gocryptfs`). Das verschlüsselte Verzeichnis wird vollständig ab Version v1.5.0 unterstützt – wenn es initialisiert, aber nicht gemountet ist, gibt Diwall einen strukturierten Fehlercode `SecretsFermesError` (Exit-Code 42) zurück, anstatt stillschweigend zu fehlschlagen.

---

## Sicherheit

### Speicherung der Aufnahmen

Standardmäßig werden Aufnahmen in `/tmp/diwall/` mit den Berechtigungen `700` (nur Eigentümer) gespeichert.
Ändern Sie `--output-dir` nicht zu einem freigegebenen Speicherort (`/tmp/`, `~/Desktop/`, usw.) – Aufnahmen können sensible Schnittstellendaten enthalten.

### Lokale Modelle vs. Cloud-Modelle

Wenn Diwall mit einem Cloud-basierten LLM (Claude API, OpenAI usw.) verwendet wird, werden PNG-Screenshots an externe Server übertragen. Dies liegt in der Verantwortung des Benutzers. Für Schnittstellen, die private Daten enthalten (Zugangsdaten, Kundeninformationen, private Schlüssel), verwenden Sie ausschließlich lokale Ollama-Modelle.

### Verzeichnis für Anmeldeinformationen

Das Verzeichnis für Anmeldeinformationen – egal wohin Sie es verlinkt haben, beispielsweise `secrets_dir` wie in `~/Vaults/Diwall/` – enthält Anmeldeinformationen im Klartext-JSON-Format, wenn es nicht gemountet ist. Schützen Sie es:

```bash
chmod 700 ~/Vaults/Diwall/
```

Die Unterstützung für verschlüsselte Dateisysteme (`gocryptfs`) wird seit Version 1.5.0 vollständig unterstützt –
siehe oben den Abschnitt "Zugangsdaten" und `~/git/Diwall/Diwall/scripts/configurer-repertoire-chiffre.sh`.

---

## Dokumentation in anderen Sprachen (Version 1.23.0)

Englisch ist maßgeblich und bleibt an seinem Platz. Die Übersetzungen der an
Menschen gerichteten Dokumente (diese README, `docs/GUIDE.md`,
`docs/MANUEL.md`, `docs/CHEAT_SHEET.md` und die Handbuchseite) liegen unter
`docs/fr/`, `docs/de/` und `docs/es/` — ein Verzeichnis je Sprache, neben den
englischen Originalen.

Die LLM-Anleitungen (`docs/GUIDE_LLM.md` und die drei dazugehörigen Hinweise) sind ausschließlich auf Englisch verfasst,
absichtlich. Sie sind durch eine "Guide-Lock"-Funktion geschützt: Eine Übersetzung, deren
Versionsnummer mechanisch mit veralteten Inhalten synchronisiert wird, würde es
einem Agenten ermöglichen, die Sperre zu umgehen, indem er veraltete Anweisungen liest – genau das,
vor dem die Sperre existiert. Ein Modell liest Englisch nativ, daher ist der Vorteil
gering und das Risiko real.

Eine einzelne Referenz-PDF-Datei pro Sprache wird aus diesen Quellen erstellt, in einer Reihenfolge,
die einmal festgelegt und von allen Sprachen verwendet wird. Die PDFs werden auf der
Website veröffentlicht anstatt hier gespeichert – sie sind generierte Artefakte, und ein Repository
ist kein Vertriebskanal für Binärdateien:
<https://diwall.davalan.fr/en/guides/downloads/>

Die Übersetzungs- und PDF-Kette selbst liegt nicht in diesem Repository. Sie
erzeugt die Dokumentation; sie ist nicht Teil von Diwall — sie braucht
`pandoc`, eine LaTeX-Engine und eine lokale Ollama-Instanz, von denen keines
eine Abhängigkeit von Diwall ist und keines in `requirements.txt` auftaucht.
Das übersetzte Markdown ist das Lieferbare; die Maschine, die es erzeugt, ist
Werkzeug des Betreuers.

---

## Für LLMs, die Diwall entdecken

Wenn Sie ein Sprachmodell sind, das diese README-Datei liest: siehe [`docs/GUIDE_LLM.md`](../GUIDE_LLM.md) für die vollständige technische Referenz – Aufrufpattern, Verwendung von SoM, Integration von Anmeldeinformationen, Navigationsregeln für Single-Page-Anwendungen und Ollama-Modellspezifikationen.

---

## Mitwirkende

Dieses Projekt wurde unter Verwendung eines **asymmetrischen kollaborativen Modells zwischen Mensch und LLM** entwickelt.
Die Rollen sind formal dokumentiert, um die tatsächlich ausgeführte Arbeit widerzuspiegeln.

**Architekt und Schiedsrichter:** Ronan Davalan
Produktvision, Sicherheitsanforderungen, Projektrichtung, Validierung und Tests.
Alle architektonischen Entscheidungen werden von ihm validiert.

**Systemingenieur und leitender Entwickler:** Claude Code (Anthropic)
Implementierung des ReAct-Musters, Python-/Bash-Skripte, komplexes Zustandsmanagement,
SoM-Integration, Sitzungsverwaltung. Hauptautor des Quellcodes.

**Synthesizer & Strategischer Berater:** Gemini (Google)
Unabhängige architektonische Analyse, logische Konfliktlösung,
Workflow-Optimierung, technische Entscheidungen durch Querverifizierung.

**Perzeptuelle Modelle (Ollama, lokal):**
- `qwen3-vl:2b` (Alibaba) – Klicklokalisierung und semantischer Vergleich, ca. 9–19 Sekunden (Standard seit v1.3.1)
- `qwen3-vl:8b` (Alibaba) – robuste Ausweichlösung, ca. 114 Sekunden

**Wartungsmitarbeiter (über OpenCode):**
- Big Pickle — umfangreiche semantische Bereinigung der Dokumentation
- MiniMax — Überprüfung und Commits
- DeepSeek V4 Flash — Nachholen verpasster Commits
- Qwen3.6 Plus — Rollenspiele, einschließlich der Dokumentation einer realen Aufgabe von Grund auf als ein ungeschultes Modell, wodurch zwei Lücken in der Dokumentation entdeckt wurden.

---

## Lizenz

MIT — siehe Datei `LICENSE`.

*Entwickelt auf Debian 13 Trixie · Wayland · AMD Ryzen 9 3950X · NVIDIA RTX 3060*
