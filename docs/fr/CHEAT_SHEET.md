# Diwall — guide rapide

Version 1.23.0 — Août 2026

Tout sur une seule page. Référence complète : `docs/MANUEL.md`.

---

## Trois commandes

```bash
# Consulter une page : PNG + éléments numérotés + arbre d'accessibilité.
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url URL --som --a11y

# Lecture sans capture (~2 secondes plus rapide, pas de fichier PNG).
/opt/diwall/venv/bin/python3 /opt/diwall/shot.py --url URL --mode fast

# Exécuter un scénario.
/opt/diwall/venv/bin/python3 /opt/diwall/rpa.py --scenario FILE.json
```

Installé depuis le `.deb`? Utilisez les chemins relatifs [`diwall-shot`] et [`diwall-rpa`] au lieu des
chemins complets. Le premier appel sur une machine nécessite [`--guide-version X.Y`], à lire avec
`grep notice-version /opt/diwall/docs/GUIDE_LLM.md`].

---

## La boucle

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

L'état de la session est stocké dans un fichier, et non dans le processus : un deuxième appel avec
`--reprendre-session` réutilise les cookies – jamais l'état du DOM.

---

## Lire la sortie dans cet ordre

| Lire | Vous indique |
|---|---|
| `succes` | si l'exécution s'est terminée |
| `boussole.url_courante` | où vous vous êtes réellement trouvé |
| `boussole.dernier_code_http` | le dernier état de navigation |
| `etat.pret_a_agir` + `etat.raisons` | les frictions perçues — un rapport, et non une alerte |
| `capture_som` / `elements_som` | ce qu'il faut cliquer, et son numéro |
| `respect` | votre propre trace : pages, actions, durée |

Si `boussole` ne correspond pas à vos attentes, arrêtez-vous avant toute action modifiant le texte.

---

## Chaque action

`type` est toujours requis. Les clés ci-dessous sont les clés supplémentaires.

| Action | Requis | Optionnel |
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

## Identifiants — la seule forme correcte

```json
{"type": "remplir_som", "id": 3, "valeur": "depuis_secrets", "secret_cle": "password"}
```

N'extrayez jamais un secret dans le shell. `lib/repertoire_chiffre.py` le résout à
l'intérieur du processus Playwright ; la valeur n'atteint jamais votre ligne
de commande, votre historique, ni aucun journal. `depuis_secrets_totp` fait de
même pour un code TOTP.

---

## Quand quelque chose résiste

| Symptôme | Essayez |
|---|---|
| Le délai d'attente de clic, l'élément est visuellement masqué | `"force": true`, puis `"repli_js": true` |
| L'élément n'est pas numéroté par SoM | `--shadow-dom` (ouvrir les Shadow Roots) |
| Élément situé en dessous du "fold" | `defiler` d'abord — vérifiez `boussole.som_hors_viewport` |
| La page ne se charge jamais complètement | `--wait-until load` |
| Le bouton de soumission ne fait rien, aucune erreur | validation HTML native — soumettez le formulaire via `evaluer` |
| `exit 42` | répertoire chiffré non monté : `diwall-monter-secrets` |
| `exit 43` | pas de `diwall.conf` — copiez l'exemple à côté |
| `guide_non_lu` | passer `--guide-version` une fois |
| 403 / 429 | lire `respect.waf_bloquants` — un signal, et non une exception |

---

## Codes de sortie

`0` succès · `1` Erreur du playwright ou assertion échouée · `2` Incompatibilité de la zone d'affichage
(`watch.py`) · `3` Mauvais interpréteur, utilisez l'environnement virtuel (venv) · `42` Répertoire chiffré fermé ou somme de contrôle incorrecte · `43` `diwall.conf` manquant.
