# Diwall — guía rápida

Versión 1.23.0 — Agosto de 2026

Todo en una página. Referencia completa: `docs/MANUEL.md`.

---

## Tres comandos

```bash
# Ver una página: PNG + elementos numerados + árbol de accesibilidad.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url URL --som --a11y

# Leer sin captura (~2 segundos más rápido, sin archivos PNG).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url URL --mode fast

# Ejecutar un escenario.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario FILE.json
```

¿Instalado desde el `.deb`? Use `diwall-shot` y `diwall-rpa` en lugar de las
rutas completas. La primera llamada en una máquina necesita
`--guide-version X.Y`, que se lee con
`grep notice-version /opt/diwall/docs/GUIDE_LLM.md`.

---

## El bucle

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

El estado de la sesión se guarda en un archivo, no en el proceso: una segunda llamada con
`--reprendre-session` reutiliza las cookies; nunca el estado del DOM.

---

## Leer la salida en este orden

| Leer | Qué indica |
|---|---|
| `succes` | si la ejecución llegó a término |
| `boussole.url_courante` | dónde se terminó realmente |
| `boussole.dernier_code_http` | código de la última navegación |
| `etat.pret_a_agir` + `etat.raisons` | fricciones percibidas — un informe, nunca una barrera |
| `capture_som` / `elements_som` | qué pulsar, y con qué número |
| `respect` | la propia huella: páginas, acciones, duración |

Si `boussole` no coincide con lo esperado, deténgase antes de cualquier acción que modifique algo.

---

## Cada acción

`type` siempre es obligatorio. Las claves siguientes son las adicionales.

| Acción | Requerido | Opcional |
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

## Credenciales: la única forma correcta

```json
{"type": "remplir_som", "id": 3, "valeur": "depuis_secrets", "secret_cle": "password"}
```

Nunca extraiga un secreto al shell. `lib/repertoire_chiffre.py` lo resuelve dentro del
proceso de Playwright; el valor nunca llega a su línea de órdenes, a su
historial ni a ningún registro. `depuis_secrets_totp` hace lo mismo con un
código TOTP.

---

## Cuando algo se resiste

| Síntoma | Intente |
|---|---|
| El tiempo de espera se agota al hacer clic, el elemento está visualmente oculto | `"force": true`, luego `"repli_js": true` |
| El elemento no está numerado por SoM | `--shadow-dom` (habilitar Shadow Roots) |
| Elemento que está fuera de la pantalla visible | `defiler` primero; verifique `boussole.som_hors_viewport` |
| La página nunca termina de cargar | `--wait-until load` |
| El botón "Enviar" no hace nada, sin error | validación HTML nativa; envíe el formulario a través de `evaluer` |
| `exit 42` | directorio cifrado no montado: `diwall-monter-secrets` |
| `exit 43` | no hay `diwall.conf` — copie la muestra que está al lado |
| `guide_non_lu` | pase `--guide-version` una vez |
| 403 / 429 | lea `respect.waf_bloquants` — es una señal, no una excepción |

---

## Códigos de salida

`0` éxito · `1` error de Playwright o aserción fallida · `2` viewport no
coincidente (`watch.py`) · `3` intérprete incorrecto, use el venv · `42`
directorio cifrado cerrado o suma de control incorrecta · `43` falta `diwall.conf`.
