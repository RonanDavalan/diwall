# Diwall – Schnellreferenz

Version 1.23.0 – August 2026

Alles auf einer Seite. Vollständige Referenz: `docs/MANUEL.md`.

---

## Drei Befehle

```bash
# Eine Seite anzeigen: PNG-Bild + nummerierte Elemente + Accessibility-Baum.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url URL --som --a11y

# Lesen ohne Zwischenspeichern (~2 Sekunden schneller, keine PNG-Dateien).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url URL --mode fast

# Führen Sie ein Szenario aus.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario FILE.json
```

Über das `.deb` installiert? Verwenden Sie `diwall-shot` und `diwall-rpa`
statt der vollständigen Pfade. Der erste Aufruf auf einer Maschine benötigt
`--guide-version X.Y`, auszulesen mit
`grep notice-version /opt/diwall/docs/GUIDE_LLM.md`.

---

## Die Schleife

```
        you decide what to do next
                  │
                  ▼
   ┌──────────────────────────────┐
   │  shot.py / rpa.py            │   one process, one JSON on stdout
   │    ├─ Chromium (headless)    │
   │    ├─ SoM: numbers elements  │
   │    ├─ A11y: page structure   │
   │    └─ secrets: fills credentials│   never in the shell, never in a log
   └──────────────┬───────────────┘
                  │  PNG + JSON
                  ▼
        you read the same state
        the operator can see too
```

Der Sitzungsstatus wird in einer Datei gespeichert, nicht im Prozess: ein zweiter Aufruf mit
`--reprendre-session` verwendet Cookies erneut – niemals den DOM-Zustand.

---

## Die Ausgabe in dieser Reihenfolge lesen

| Lesen Sie | Zeigt Ihnen |
|---|---|
| `succes` | ob die Ausführung abgeschlossen wurde |
| `boussole.url_courante` | wo Sie tatsächlich angekommen sind |
| `boussole.dernier_code_http` | letzter Navigationsstatus |
| `etat.pret_a_agir` + `etat.raisons` | wahrgenommene Reibung – ein Bericht, niemals eine Fehlermeldung |
| `capture_som` / `elements_som` | was Sie anklicken sollen und seine Nummer |
| `respect` | Ihre eigene Spur: Seiten, Aktionen, Dauer |

Wenn `boussole` nicht Ihren Erwartungen entspricht, stoppen Sie vor jeglicher verändernden Aktion.

---

## Jede Aktion

`type` ist immer erforderlich. Die Schlüssel unten sind die zusätzlichen.

| Aktion | Erforderlich | Optional |
|---|---|---|
| `naviguer` | `url` | — |
| `cliquer` | `selecteur` | `force`, `repli_js` |
| `cliquer_som` | `id` | — |
| `cliquer_visuel` | `description` | — |
| `cliquer_iframe` | `iframe_selecteur` \| `iframe_chemin`, `selecteur` | `force` |
| `remplir` | `selecteur`, `valeur` | `secret_cle` |
| `remplir_som` | `id`, `valeur` | `secret_cle` |
| `remplir_iframe` | `iframe_selecteur` \| `iframe_chemin`, `selecteur`, `valeur` | `secret_cle` |
| `capturer` | `nom` | `som` |
| `evaluer` | `script` | `attendu` \| `contient` \| `motif` |
| `defiler` | `px` \| `selecteur` | — |
| `pause` | `ms` | `interval_capture` |
| `attendre` | `selecteur` | `interval_capture` |
| `attendre_selecteur_present` | `selecteur` | — |
| `attendre_absence` | `selecteur` | `delai_initial_ms` |
| `attendre_navigation` | — | — |
| `attendre_url` | `motif` | `attendre_changement` |
| `attendre_reseau_calme` | — | `timeout_ms` |
| `attendre_mfa_ntfy` | `id_som` | `timeout` |
| `nettoyer_overlay` | `selecteur` | — |
| `declencher_scenario` | `scenario` | — |

---

## Zugangsdaten – die einzige korrekte Formularausgabe

```json
{"type": "remplir_som", "id": 3, "valeur": "depuis_secrets", "secret_cle": "password"}
```

Extrahieren Sie ein Geheimnis niemals in die Shell. `lib/repertoire_chiffre.py` löst es
innerhalb des Playwright-Prozesses auf; der Wert erreicht weder Ihre
Befehlszeile noch Ihren Verlauf noch irgendein Protokoll.
`depuis_secrets_totp` tut dasselbe für einen TOTP-Code.

---

## Wenn etwas Widerstand leistet

| Symptom | Versuchen Sie |
|---|---|
| Klick führt zu einem Timeout, Element ist visuell ausgeblendet | `"force": true`, dann `"repli_js": true` |
| Element wird nicht von SoM nummeriert | `--shadow-dom` (Shadow Roots öffnen) |
| Element befindet sich außerhalb des sichtbaren Bereichs | `defiler` zuerst — prüfen Sie `boussole.som_hors_viewport` |
| Seite lädt nie vollständig | `--wait-until load` |
| Absenden-Button hat keine Funktion, kein Fehler | native HTML-Validierung — Formular über `evaluer` absenden |
| `exit 42` | verschlüsseltes Verzeichnis nicht gemountet: `diwall-monter-secrets` |
| `exit 43` | kein `diwall.conf` — Beispiel daneben kopieren |
| `guide_non_lu` | einmal `--guide-version` ausführen |
| 403 / 429 | lesen Sie `respect.waf_bloquants` — ein Signal, keine Ausnahme |

---

## Rückgabecodes

`0` Erfolg · `1` Fehler im Playwright oder fehlende Assertion · `2` Abweichung der Bildschirmauflösung
(`watch.py`) · `3` Falscher Interpreter, verwenden Sie die virtuelle Umgebung · `42` Verschlüsseltes Verzeichnis geschlossen oder fehlerhafte
Prüfsumme · `43` `diwall.conf` fehlt.
