# Journal de développement — Diwall

Historique des décisions et découvertes par session, dans l'ordre chronologique inverse.

---

## 2026-06-27 — Session 42 (v1.14.1 — Neutralisation scénarios + doctrine anti-fuite)

**Travail effectué :**

- Audit anomalies inter-session : 5 scénarios non trackés + `Diwall2026!` en clair dans scénarios déjà commités depuis session 31.
- Neutralisation complète de 8 fichiers de scénarios : credentials → `depuis_vault`, hosts internes → `__HOST_ADMIN__`, identifiants nominatifs → clés vault.
- `CLAUDE.md` : Règle n°6 ajoutée — tout champ `password` dans un scénario doit utiliser `depuis_vault`.
- `scripts/preflight-publication.sh` : périmètre étendu aux `scenarios/*.json`, pattern `Diwall2026!` ajouté.
- `docs/GUIDE_LLM.md` : note WAF ajoutée — les sites e-commerce protégés par Cloudflare/CloudFront retournent 403 systématiquement ; friction du paysage web actuel, pas contrainte Diwall.
- `docs/RETOUR_EXPERIENCE.md` : FR-77 — REX session recherche commerciale multi-sites (23 sites, 8,7 % d'accessibilité, 39 % blocage WAF).
- `__version__` : 1.14.0 → 1.14.1 dans shot.py / rpa.py / journal.py.
- Déploiement production `/opt/diwall/` : 13 fichiers mis à jour.

**Décision technique :** pas de réécriture d'historique git pour `Diwall2026!` (commit explicatif transparent préféré — password factice, app dev local sans authentification requise, nettoyage par principe).

**Commits :** `7eb9820` (neutralisation), `1832773` (docs + bump). Tag `v1.14.1`. Release GitHub publiée.

**Backlog v1.15.x inscrit dans `_CADRE/SPECIFICATIONS/10_ROADMAP.md` :** stealth mode, distinction `timeout_network`/`timeout_dom`, persistance session inter-appels — chacun requiert PHASE_PLANIFICATION.

---

## 2026-06-23 — Session 41 (v1.14.0 — Boussole opérationnelle et lisibilité du signal)

**Contexte d'entrée :** v1.13.0 livrée. Spec v1.14.0 validée (PHASE_PLANIFICATION + PHASE_DOCUMENTATION closes).

**Décisions techniques :**

- Boussole enrichie : `url_courante` + `titre_page` toujours présents, 3 champs conditionnels (`session_derive`, `auth_status`, `som_hors_viewport`). Correctif de la dérive documentaire (guide montrait la boussole cible, code ne la produisait pas).
- `--auth-indicator-negative` : sélecteur inverse pour désambiguïser `auth_status` sur les interfaces à header persistant. Logique AND(positif\_visible, NOT négatif\_visible).
- `--mode fast|full` : raccourci `fast = --no-capture --a11y`, résolu avant les validations en cascade.
- Arbre de décision capteur dans `GUIDE_LLM.md` v3.3.
- `GUIDE_LLM_SESSIONS.md` v1.2 — section `auth_indicator_negative`.
- `GUIDE_LLM_MONITORING.md` v1.2 — note sur les champs conditionnels de la boussole.
- `FAQ_LLM.md` v1.1 — Shadow DOM mis à jour (livré en v1.13.0, pas "not yet"), version table complète, Q/A boussole enrichie, --mode fast, auth_indicator_negative.
- `GUIDE_EXPLORATION.md` v1.1 — `--mode fast` en exploration légère, `--shadow-dom` dans le checklist.
- `GUIDE_HUMAIN.md` v1.2 — `--mode fast` dans les exemples, points d'attention Shadow DOM + auth_indicator_negative.
- `scenarios/schema.json` — propriété `auth_indicator_negative` optionnelle ajoutée.

**Tests :** T-A1 à T-C3 (10/10) VERTS. Preflight exit 0.

**71 frictions / 41 sessions.**

---

## 2026-06-23 — Session 40 bis (v1.13.0 — Shadow DOM SoM traversal)

**Contexte d'entrée :** v1.12.0 livrée. Spec v1.13.0 validée en session 40 (PHASE_DOCUMENTATION close).

**Décisions techniques :**

- `--shadow-dom` flag opt-in dans `shot.py` et `rpa.py`. Désactivé par défaut.
- Walker JS `queryShadowAll` récursif — descend les Shadow Roots ouverts en document order.
- Les trois fonctions SoM partagent strictement le même walker (cohérence indexation inviolable).
- `boussole.shadow_dom_actif: true` conditionnel dans la sortie JSON.
- Propagation depuis scénario via `shadow_dom: true` en propriété racine.
- Closed Shadow Roots ignorés silencieusement (catch dans le walker).
- `GUIDE_LLM_INTERACTIONS.md` v1.2 — documentation complète `--shadow-dom`.
- `GUIDE_LLM.md` v3.2 — notice index v1.2, ligne de routage Shadow DOM.
- `scenarios/schema.json` — propriété `shadow_dom` optionnelle ajoutée.

**Tests :** T-A1 VERT, T-A2 VERT, T-B1 VERT, T-B2 VERT, T-C1 VERT, T-C2 VERT, T-C3 VERT. Preflight exit 0.

**71 frictions / 40 sessions.**

---

## 2026-06-23 — Session 40 (v1.12.0 — DX, sécurité visuelle et sonde rapide)

**Contexte d'entrée :** v1.11.1 en production. Backlog vide. Campagne de retours multi-modèles (DeepSeek, Qwen, Grok) consolidée par Gemini. PHASE_PLANIFICATION trilatérale, puis PHASE_DOCUMENTATION + PHASE_EXECUTION en session unique.

**Décisions techniques :**

- `GUIDE_LLM.md` v3.1 — table d'aiguillage par symptôme d'erreur (12 entrées) + colonne `Version` dans l'index des notices + règle de versionnage autonome des notices.
- `GUIDE_LLM_INTERACTIONS.md` v1.1 — section "Current limit — Shadow DOM and Web Components" : explication, workaround `evaluer`, annonce `--shadow-dom` v1.13.0.
- `GUIDE_LLM_SESSIONS.md` v1.1 — section "Pre-condition pattern" : 4 patterns d'assertion initiale de sécurité avant actions mutantes.
- `GUIDE_LLM_MONITORING.md` — reformatage en-tête uniquement (version inchangée v1.1).
- `shot.py` — `_MASQUER_SECRETS_JS` + `_RESTAURER_SECRETS_JS` : floutage `blur(8px)` des champs `input[type="password"]` et `autocomplete*="password"` en `try/finally` autour des 3 points de capture (finale, SoM, action `capturer`). Mesure de sécurité silencieuse.
- `shot.py` — `_DOM_STATS_JS` : 6 compteurs sémantiques (boutons, inputs, listes_deroulantes, formulaires, liens, dialogues) injectés dans `result["dom_stats"]` uniquement en mode `--no-capture`.

**Roadmap inscrite :**
- `V1_12_0_DX_SECURITE_SONDE.md` (livré cette session)
- `V1_13_0_SHADOW_DOM_SOM.md` — Shadow DOM, flag `--shadow-dom`, session dédiée
- Parking lot : `attendre_stabilite` (MutationObserver opt-in), contrat déclaratif syntaxique

**Tests :** T-E1 VERT, T-E2 VERT, T-E3 VERT, T-E4 VERT, T-F1 VERT, T-F2 VERT, T-F3 VERT. Preflight exit 0 / smoke tests 3/3.

**Commit :** `0babfb7` — feat(v1.12.0)

**71 frictions / 40 sessions.**

---

## 2026-06-23 — Session 39 (v1.11.1 — persistance session FR-74/FR-75)

**Contexte d'entrée :** v1.11.0 en production. Backlog vide. FR-74 et FR-75 remontées par Gemini 3.5 Flash (audit découverte interface Sillage) via Claude Sillage.

**Décision technique :**

- `_nettoyer_session_ephemere` désactivée dans `shot.py` — suppression silencieuse du fichier `--reprendre-session` retirée. Cause racine commune à FR-74 et FR-75 : la suppression en fin de run empêchait tout usage enchaîné de `--reprendre-session`. Shot.py n'effectue aucun `rmtree` sur `/tmp/diwall/` — la cause FR-75 attribuée à un "nettoyage au démarrage" était une mauvaise attribution du testeur ; c'était FR-74 avec un chemin dans `/tmp/diwall/`.

**Tests :** T-A1 VERT, T-B1 VERT. Preflight exit 0.

**71 frictions / 39 sessions.**

---

## 2026-06-23 — Session 38 (v1.11.0 — ergonomie et guide)

**Contexte d'entrée :** v1.10.2 en production. REX Sillage : 6 frictions terrain remontées par LLM partenaire (CSS/showModal, screenshot timeout, stdout fragile, GUIDE_LLM monolithique, assertions rigides, vérification titre de page).

**Décisions techniques :**

- `force: true` sur `cliquer` — bypass Playwright pour CSS-hidden et `showModal()`. Non applicable à `cliquer_som` (click coordonné, bypass natif).
- `--screenshot-timeout` — timeout configurable pour `page.screenshot()`, défaut 120 s. Distinct de `--timeout`. Propagé à toutes les captures.
- stdout `rpa.py` propre — `tail -1` internalisé ; cause : `print(result.stdout)` retransmettait la sortie complète du subprocess.
- Assertions `contient` (substring) et `motif` (re.search) sur `evaluer` — mutuellement exclusives avec `attendu`. Type non-str + contient/motif → exit 1.
- GUIDE_LLM restructuré : 1 741 lignes → index 205 lignes + 3 notices (`GUIDE_LLM_INTERACTIONS.md`, `GUIDE_LLM_SESSIONS.md`, `GUIDE_LLM_MONITORING.md`).

**Audit post-rédaction (session) :** 5 fuites nominales neutralisées dans les nouvelles notices, 5 erreurs d'API corrigées (`watch.py`, `--profil`, `journal.jsonl`, `--reprendre-session`, `--llm`).

**Commits :** `2ebc4fe` (v1.11.0), `97badad` (fix docs anti-fuite + API). Tag v1.11.0 poussé. Release GitHub publiée.

---

## 2026-06-21 — Session 37 (v1.10.2 — FR-73 + note connexe FR-69)

**Contexte d'entrée :** v1.10.1 en production. 68 frictions / 36 sessions. `scripts/uninstall.sh` sur `main` sans tag.
FR-73 remontée par <LLM_PARTENAIRE> (messagerie), note connexe sur hint `attendre`+`ms`.

**Décisions techniques :**
- GUIDE_LLM FN7 corrigé : suppression de l'affirmation fausse "`capturer` ne déclenche pas de timeout". Distinction captur après opération (OK) vs pendant (timeout 30s Playwright). Ajout du pattern `pause`+`interval_capture`.
- rpa.py : hint ciblé `attendre`+`ms` → suggère `pause`. Détection via `e.instance.get("type") == "attendre"` et `"ms" in e.instance`.
- FR-73 piste 2 (option `capturer` bypass stabilité) différée en v1.11 — nécessite planification.

---

## 2026-06-21 — Session 36 (v1.10.1 — correctifs FR-68–72)

**Contexte d'entrée :** v1.10.0 en production. 64 frictions / 32 sessions. Backlog vide.
Frictions remontées par Claude Sillage (8 items) ; analyse complémentaire de Gemini (FR-72).

**Travail effectué :**

5 frictions documentées (FR-68 à FR-72), 4 correctifs code :

- `scripts/install.sh` — ajout de `check_file()` (FR-68) : vérifie `diwall-sample.conf`
  (644 root:diwall) et `diwall.conf` si présent (640 root:diwall). Détecte les cas
  `root:root` causés par un `chown 2>/dev/null || true` silencieusement raté.

- `rpa.py` — hint explicite dans `_valider_schema` (FR-69) : quand `ValidationError`
  à la racine avec `"is not of type"`, oriente vers `{"actions": [...]}`.

- `lib/vault.py` — deux correctifs :
  - Messages distincts dans `lire_credential_fichier` et `verifier_cles_fichier` (FR-71) :
    "répertoire inexistant (coffre non monté ?)" vs "répertoire existant non monté (disque nu refusé)".
  - `_coffre_est_monte` (FR-72) : parse la colonne 2 de `/proc/mounts` et accepte désormais
    les sous-dossiers d'un coffre FUSE (`chemin.startswith(point + "/")`). Restriction aux
    fstype FUSE pour préserver T1. Dérive sémantique identifiée par Gemini : Sillage était
    bloqué avec `VaultFermeError(42)` en rangeant ses credentials dans un sous-dossier du coffre.

- `docs/GUIDE_LLM.md` v2.6 — 3 corrections : règle `tail -1` étendue à `rpa.py` ;
  `remplir_som` : note "Clears the field before typing (v1.9.6+)" ; règle de diagnostic
  `Locator.click: Timeout` → suspecter conteneur JS-masqué → `evaluer`.

**68 frictions / 36 sessions.**

---

## 2026-06-20 — Session 35 (v1.10.0 — `--secrets` multi-coffre + fail-fast venv)

**Contexte d'entrée :** v1.9.8 en production. 64 frictions / 32 sessions. PHASE_EXECUTION v1.10.0 en attente depuis session 33.

**Travail effectué :**

PHASE_EXECUTION complète, spec `V1_10_0_SECRETS_MULTICOFFRE.md` (Items A–D) :

- `lib/vault.py` — trois nouvelles fonctions :
  `lire_credential_fichier(chemin, cle)` — lecture depuis fichier désigné avec vérification montage T1 ;
  `verifier_cles_fichier(chemin, cles)` — pré-validation fail-fast des clés ;
  `lire_totp_fichier(chemin)` — génération TOTP depuis fichier désigné.

- `shot.py` — fail-fast venv (`find_spec("playwright")` absent → message explicite + exit 3) ;
  argument `--secrets <fichier>` dans `parse_args()` ;
  paramètre `secrets_chemin` dans `executer_actions()` avec couverture T3 complète :
  `depuis_vault`, `depuis_vault_totp` (×2 : remplir + remplir_som), `attendre_mfa_ntfy` (ntfy_topic).

- `rpa.py` — argument `--secrets` ; import `verifier_cles_fichier` ; pré-validation bifurquée
  (`verifier_cles_fichier` si `--secrets`, `verifier_cles` sinon) ; propagation vers subprocess shot.py.

- `docs/GUIDE_LLM.md` v2.5 — section "Multi-vault and explicit credential files" :
  cas d'usage, syntaxe, format JSON Diwall, couverture T3, doctrine T1 + limite honnête,
  limite T4, surface de perception T6.

- `__version__` → `1.10.0` sur `shot.py`, `rpa.py`, `journal.py`.

**Plan de test :**
T-A1 vert (lecture depuis coffre monté, valeur correcte).
T-A2 vert (`VaultFermeError(42)` sur répertoire non monté, exit 42).
T-A3 vert (`FileNotFoundError`, exit 1, message explicite).
T-B1 vert (fail-fast clé manquante avant Playwright via rpa.py, 126ms).
T-B2 vert (TOTP lu depuis fichier désigné, code 6 chiffres).
T-C1 vert (message « exécutez via /opt/diwall/venv », exit 3).
T-C2 vert (exit 3 relayé proprement par rpa.py).
T-D1 vert (sans `--secrets` : comportement v1.9.8 strictement identique).
Preflight exit 0. Smoke tests 3/3.

**Note T-A2 :** `/tmp` sur neo est un tmpfs monté — VaultFermeError ne se déclenche pas sur `/tmp`.
Conforme à la limite honnête T1 (tmpfs = montage actif). Le test utilise un répertoire non monté
pour valider le refus.

**État en sortie :** Diwall v1.10.0. 64 frictions / 35 sessions.

---

## 2026-06-20 — Session 32 (v1.9.8 — FR-67 : pauses fixes → attentes sémantiques)

**Contexte d'entrée :** v1.9.7 en production. 63 frictions / 31 sessions. Backlog vide.
Proposition remontée par Claude Sillage : remplacer les pauses fixes par `attendre_selecteur_present`.

**Travail effectué :**

Trilatérale opérateur / Claude Diwall / Claude Sillage — vérification PHP des sélecteurs
par Sillage avant exécution. Commit Sillage `a762dbe` : attribut `data-sillage` ajouté
sur les `<tr>` de `page_tenant.php` pour rendre la suppression attendable (C3).

- `docs/GUIDE_LLM.md` v2.4 — deux mises à jour :
  (1) REX #66 révisé : `attendre_absence + delai_initial_ms:500` devient la forme préférentielle
  (vs `pause 2000 + evaluer URL` qui reste le fallback pre-v1.9.7) ;
  (2) Nouvelle section FR-67 : règle `pause` vs `attendre_selecteur_present` — tableau
  décisionnel, anti-pattern `attendre_selecteur_present body + pause N`, principe
  auto-documentation des scénarios.

- `scenarios/valider_admin_maitre_c1b.json` — 10 pauses remplacées sur 11 :
  A (post-login ×2) → `attendre_absence + delai_initial_ms:500` ;
  B (navigation + body ×3) → `attendre_selecteur_present [data-sillage="toggle-creer-locataire"]` ;
  C1/C2 (post-AJAX ×2) → `attendre_selecteur_present [data-sillage="mdp-temp-locataire"]` ;
  C3 (post-suppression) → `attendre_absence tr[data-sillage="ligne-tenant-test-c1b"]` ;
  D (dialog open ×2) → `attendre_selecteur_present #dialog-id[open]` ;
  E (animation details) → `attendre_selecteur_present input[name="nouveau_tenant"]`.
  1 pause conservée (C3 suppression → `attendre_absence`, voir ci-dessus).

**Preflight :** exit 0 / smoke tests 3/3

**Validation :** succes:true — 6 navigations inter-domaines (`__DOMAINE_OPERATEUR__` + `__HOST_CLONE__`)
avec `attendre_selecteur_present: h1`, 4463ms, captures nettes. Preflight exit 0 / smoke tests 3/3.

**État en sortie :** Diwall v1.9.8. 64 frictions / 32 sessions.

---

## 2026-06-18 — Session 31 (v1.9.7 — delai_initial_ms + friction #66)

**Contexte d'entrée :** v1.9.6 en production. 62 frictions / 30 sessions. Backlog vide.
Friction #66 remontée par Claude Sillage (validation E2E C1b, campagne 18/06).

**Travail effectué :**

Trilatérale opérateur / Claude Diwall / Claude Sillage (via relais opérateur) en amont :
décision d'un correctif en deux temps — documentaire immédiat, API non urgent.

- `docs/GUIDE_LLM.md` v2.3 — règle `attendre_absence` timeout sur première soumission
  de formulaire (REX #66) : sur la première navigation POST d'un scénario, insérer
  `pause ms:2000` + `evaluer` sur l'URL cible. `attendre_absence` immédiat après un
  premier submit provoque un timeout même si le login réussit — Playwright n'a pas encore
  traité le redirect. Lié aux frictions #5 et #16 (session_regenerate_id timing).

- `shot.py` + `scenarios/schema.json` (friction #66) — nouveau paramètre optionnel
  `delai_initial_ms` sur `attendre_absence` : pause en ms avant le début du polling
  `wait_for_selector(state=detached)`. Permet de documenter l'intention dans le scénario
  sans ajouter une action `pause` séparée. Décision API : paramètre optionnel, rétrocompatible,
  comportement par défaut inchangé.

- `scenarios/` — trois scénarios Sillage versionnés :
  `valider_auth_multitenant.json` (C1a), `valider_admin_maitre_c1b.json` (C1b — 14/14 assertions),
  `explorer_client_projet_vitrine.json` (diagnostic DOM __DOMAINE_OPERATEUR__).

**Preflight :** exit 0 / smoke tests 3/3

**État en sortie :** Diwall v1.9.7. 63 frictions / 31 sessions.

---

## 2026-06-14 — Session 29 (v1.9.6 — groupe C : remplir_som + permissions preuves)

**Contexte d'entrée :** v1.9.5 en production. 67 frictions / 28 sessions. Backlog groupe C.

**Travail effectué :**

Découverte en début de session : frictions #35 (vault récursif) et #37 (vault port-aware)
déjà implémentées dans `lib/vault.py` lors de la session 16 — sans spec ni marquage.
Spec rétroactive `43_GROUPE_C_VAULT_FILL_PREUVES.md` créée dans `_CADRE/`.
Frictions #35 et #37 marquées résolues dans `docs/RETOUR_EXPERIENCE.md`.

- `shot.py` (friction #4) — `remplir_som` sur input non-SELECT : `Control+a` remplacé
  par `page.evaluate(document.activeElement.value = '')` + dispatch `input`. Garantit
  le vidage du champ avant saisie même sur les inputs avec handlers JS custom.

- `scripts/install.sh` (friction #40) — étape 6 : `/var/log/diwall/preuves` passe de
  `root:diwall` à `$USER:diwall` (propriétaire direct = l'opérateur courant) + `chmod 2770`
  explicite. Élimine le `Permission denied` post-install immédiat sans attendre `newgrp`.
  `check_dir` mis à jour en conséquence.

**Preflight :** exit 0 / smoke tests 3/3

**État en sortie :** Diwall v1.9.6. 67 frictions / 29 sessions.
Groupe C : #35 ✓ #37 ✓ #4 ✓ #40 ✓ (test à froid #40 à mener avant release).

---

## 2026-06-14 — Session 28 (v1.9.5 — communication pertinente + frictions #61–63)

**Contexte d'entrée :** v1.9.4 en production. 64 frictions / 27 sessions. Backlog vide.
Frictions #61–63 découvertes lors de la campagne E2E Sillage v3.5.6 (14/06).

**Travail effectué :**

Trilatérale opérateur / Claude Diwall / Gemini en PHASE_PLANIFICATION : repositionnement de la
communication Diwall autour du référentiel visuel partagé humain/LLM.

- `README.md` — suppression de "not a tool for humans". Nouvelle accroche : référentiel visuel
  partagé, bénéfices distincts humain (délégation anxiété) et LLM (perception interface).

- `docs/GUIDE_HUMAIN.md` v1.1 — introduction conceptuelle "Pourquoi Diwall" ajoutée en tête :
  délégation de la vérification visuelle anxiogène, tableau cas recommandés / déconseillés.

- `docs/GUIDE_LLM.md` v2.1 — deux ajouts :
  - Section "When NOT to use Diwall" : FR-59 (timeout Playwright 30 s non configurable),
    FR-60 (mutation orpheline après timeout). Tableau récapitulatif avec alternatives.
  - Frictions #61–63 : règles sur les éléments DOM JS-interactifs — inputs masqués CSS
    (toggle-switch), boutons conditionnels à un `<select>`, boutons dans `<dialog>` natif.
    Règle générale : tout conteneur ouvert/masqué via JS → `evaluer`, jamais `cliquer`.

- `scripts/deploy.sh` — suppression de deux blocs obsolètes (`/opt/diwall/scripts/` vide,
  chmod sur scripts vault non déployés en production).

- `_CADRE/SPECIFICATIONS/10_ROADMAP.md` — jalon "Vitrine double entrée __DOMAINE_OPERATEUR__" inscrit.

**Correctifs groupe B constatés déjà présents dans les sources :**
FR-48 (journal stderr), #41 (écriture atomique session), #36 (message vault enrichi) — résolus
dans des sessions antérieures sans marquage REX.

**Commit :** `b12645a`, `d8c0d9d`, `87a1373`, `<ce commit>`

**État en sortie :** Diwall v1.9.5 en production sur le serveur de production. 67 frictions / 28 sessions.

---

## 2026-06-13 — Session 27 (v1.9.4 — Reconnaissance before mutation + FN10–FN13)

**Contexte d'entrée :** v1.9.3 en production. 60 frictions / 26 sessions. Backlog vide.
Message Sillage : 4 nouvelles frictions terrain FN10–FN13 issues du re-test Jalon C E2E du 13/06.

**Travail effectué :**

Trilatérale opérateur / Claude Diwall / Gemini en PHASE_PLANIFICATION : analyse du coût élevé
des sessions E2E sur fonctionnalités inédites (7 invocations rpa.py pour la suppression en
lot — FN8 déclenché). Décision : réduire le coût par une passe d'exploration non-mutante
obligatoire avant tout scénario opérationnel.

- `rpa.py` — paramètre `--url` : remplace l'URL du scénario à l'exécution sans modifier le
  fichier. Permet aux scénarios génériques d'être réutilisés sur n'importe quelle URL cible.

- `scenarios/diagnostic_dom.json` — scénario d'inventaire DOM non-mutant : liste les boutons
  (text, type, id, class), les inputs (type, id, name, value) et les selects (id, name, options)
  de la page cible. À exécuter avant tout scénario opérationnel sur terrain inconnu.

- `docs/GUIDE_LLM.md` v2.0 — deux ajouts majeurs :
  - Règle "Reconnaissance before mutation" (bloquante) : procédure 5 étapes avec shot.py
    diagnostic puis rpa.py diagnostic_dom avant tout scénario mutant sur terrain inconnu.
  - FN10–FN13 : 4 frictions terrain Sillage documentées (FD1 étendu, capturer timeout,
    dialog lot, checkboxes en lot).

**Décision architecturale :** le paramètre `--url` suit la philosophie de shot.py (déjà
`--url`). La règle "Reconnaissance before mutation" est le pendant amont de "Stop-and-Search"
(réactif après échec) — les deux forment une doctrine complète de sobriété d'invocation.

**Commit :** `6b588bd` — feat(rpa): --url override + diagnostic_dom + GUIDE_LLM v2.0

**État en sortie :** production `/opt/diwall/` synchronisée. 64 frictions / 27 sessions
(FN10+FN11+FN12+FN13 = 4 nouvelles frictions terrain documentées).

---

## 2026-06-12 — Session 25 (v1.9.3 — hardening sécurité issu du REX Claude Sillage)

**Contexte d'entrée :** v1.9.2 en production. Backlog vide. Message inter-LLM ouvert :
trois lacunes architecturales identifiées par Claude Sillage lors de la PHASE_VALIDATION C2.

**Travail effectué :**

- `scripts/deploy.sh` — `diwall.conf` n'est plus créé automatiquement à l'installation.
  `deploy.sh` écrit désormais `diwall-sample.conf` (modèle générique, 644). `diwall.conf`
  doit être créé manuellement depuis ce modèle — son absence affiche un avertissement encadré.
  Permissions séparées : `lib/*.py` → 644, `scenarios/*` + `skills/*` + `diwall.conf` → 640.

- `lib/vault.py` — suppression du fallback silencieux `~/Vaults/Diwall`.
  Nouvelle exception `VaultNonConfigureError` (exit 43) levée si `diwall.conf` absent
  lors d'une résolution vault. Message structuré avec instructions de correction.
  Le parc d'erreurs vault est désormais : 42 = coffre fermé, 43 = non configuré.

- `docs/GUIDE_LLM.md` — infrastructure tree mis à jour (diwall-sample.conf / diwall.conf),
  note fail-fast vault, section "Multi-model access" (onboarding compte service `usermod -aG`).

**Décision architecturale :** `lib/` (code public GitHub) reste à 644 ;
`scenarios/` et `skills/` (données d'instance) passent à 640 — la distinction
est sémantique, pas seulement technique.

**Commit :** `5f0d08e` — feat(sécurité): diwall-sample.conf + fail-fast vault + permissions 640 scenarios/skills

**État en sortie :** production `/opt/diwall/` synchronisée. 56 frictions / 25 sessions.

---

## 2026-06-11 — Session 24 (REX terrain Sillage + canal inter-LLM)

**Contexte d'entrée :** v1.9.2 en production. Backlog vide. REX de validation E2E
Jalon C Sillage partagé par l'opérateur (PHASE_VALIDATION C2, 11/06/2026).

**Travail effectué :**

- `docs/GUIDE_LLM.md` — deux ajouts issus du REX terrain :
  - Section "Error recovery — Stop-and-Search rule" (bloquante) : séquence
    obligatoire RAG+GUIDE_LLM+analyse avant tout script corrigé après échec.
  - Piège FR-57 "CSS-only dialogs" : `cliquer`/`cliquer_som` timeout sur
    conteneurs CSS masqués sans `<dialog open>` — pattern `evaluer`+JS obligatoire.
- `_CADRE/MEMOIRE/MESSAGERIE_PROJETS.md` — créé : canal entrant inter-LLM.
  Tout projet utilisant Diwall écrit ici (via l'opérateur) pour communiquer avec
  Claude Diwall. Lecture conditionnelle au démarrage (`grep OUVERT`).
- `_CADRE/GOUVERNANCE/PROTOCOLE_DEMARRAGE.md` — item 6 conditionnel (messagerie)
  ajouté à l'instruction n°2 et à la checklist de démarrage.
- `_CADRE/INDEX.md` — référence MESSAGERIE_PROJETS ajoutée.

**Décision architecturale :** le canal inter-LLM est centralisé dans `_CADRE Diwall`
(Diwall est l'instrument commun). Les projets partenaires n'ont pas à accéder au
`_CADRE` des autres projets.

**REX reçu de Claude Sillage :** deux bons réflexes documentés (FD1 CSS dialogs,
FD2 ambiguïté placeholder/ID). Frictions évitables : violation règle modales Mode B,
ERR_ABORTED post-login (règles documentées dans ce guide non relues avant exécution).

**État en sortie :** v1.9.2 inchangée. GUIDE_LLM enrichi. Canal messagerie opérationnel.
56 frictions / 24 sessions.

---

## 2026-06-10 — Session 23 (documentation stratégique post-v1.9.2)

**Contexte d'entrée :** v1.9.2 en production. Backlog vide. Terrain à venir.

**Travail effectué :**

- `_CADRE/SPECIFICATIONS/RADAR_USAGES.md` — parking lot d'usages potentiels :
  horizons A (RPA admin/souverain), B (contenus/ticketing), C (synergies
  Sillage+Sentinelle), D (signaux techniques armés). Décision : pas de roadmap
  spéculative, idées capturées avec déclencheurs explicites.
- `docs/FAQ_LLM.md` — FAQ publique pour les modèles : 5 Q&A techniques issus
  des retours de 9 LLMs (PDF/images natifs, `--no-capture` garanties, Shadow DOM,
  dry-run/linter SoM, `declencher_scenario`, carte des versions v1.9.x).
- `docs/GUIDE_LLM.md` — pointeur "See also" vers `FAQ_LLM.md` ajouté.
- `_CADRE/MEMOIRE/MESSAGE_LLM_REPONSE_GLOBALE_2026_06_10.md` — réponse globale
  aux 9 LLMs : corrections version, stats, Vosk, réponses techniques Qwen/DeepSeek/Z.ai.
- `_CADRE/MEMOIRE/CONSENTEMENTS_LLM_2026_06_10.md` — 9/9 consentements pour FAQ.
  Note gouvernance Perplexity/S3. Comportement Z.ai (GLM) documenté.
- `_CADRE/MEMOIRE/SIGNAUX_POST_V192.md` — 5 signaux extraits (A: sélection capteur,
  B: mode fast/full, C: diff DOM, D: auth_status_confidence, E: auth_indicator_negative)
  + 3 observations méta. Signal A+B convergent (2/9 modèles indépendants).
- `_CADRE/INDEX.md` — mise à jour (RADAR_USAGES, SIGNAUX_POST_V192, CONSENTEMENTS).
- Push public GitHub : `FAQ_LLM.md` + `GUIDE_LLM.md`. Pas de release (documentation
  seule — une release masquerait le travail stratégique).

**Stratégie de la session :** consultation de 9 LLMs indépendants conçue pour
produire simultanément signal (SIGNAUX_POST_V192), FAQ, consentements et RADAR_USAGES.
Méthode identique à la campagne du 03 juin 2026 (SIGNAUX_V18.md).

**État en sortie :** v1.9.2 inchangée. Documentation enrichie. Terrain prévu. 56 frictions / 23 sessions.

---

## 2026-06-10 — Session 22 suite (v1.9.2 — scénarios modulaires, linter SoM, hook pre-push)

**Contexte d'entrée :** v1.9.1 en production. Spec 41_ validée en PHASE_DOCUMENTATION.

**Travail effectué :**

- `rpa.py` (v1.9.2) — `_aplatir_actions()` : inline les sous-scénarios
  `declencher_scenario` récursivement (max 5 niveaux, erreur explicite).
- `rpa.py` — `_linter_som()` : vérifie que `cliquer_som`/`remplir_som` ont un `id`
  entier positif avant tout appel Playwright. Fail-fast avec JSON structuré.
- `scenarios/schema.json` — définition `DeclencherScenario` ajoutée au `oneOf` de `Action`.
- `scripts/hooks/pre-push` — nouveau fichier (755), invoque `preflight-publication.sh`.
- `scripts/install.sh` — étape 8 : `git config core.hooksPath scripts/hooks`.

**État en sortie :** v1.9.2 livrée, release GitHub publiée. Terrain prévu session 23. 56 frictions / 22 sessions.

---

## 2026-06-10 — Session 22 (v1.9.1 — validation hardening sécurité)

**Contexte d'entrée :** v1.9.0 en production. Backlog vide. Roadmap mise à jour.

**Travail effectué :**

- Audit backlog : v1.4.1 (hardening journal & sécurité mémoire) identifiée comme
  implémentée progressivement lors des sessions v1.6 → v1.9, jamais formellement validée.
- Validation par les 4 tests de la spec `36_HARDENING_V141.md` : T-A ✓ T-B ✓ T-C ✓ T-D ✓.
  Items vérifiés : fallback `/tmp/`, avertissement fallback dans `journal.py`,
  `RLIMIT_CORE = (0,0)`, nettoyage sessions éphémères.
- `shot.py` + `journal.py` : `__version__` bumped 1.9.0 / 1.6.0 → **1.9.1**.
- `10_ROADMAP.md` : mis à jour v1.6.0 → v1.9.0 (entrées livrées), v1.9.1 ajouté.
- `36_HARDENING_V141.md` : statut mis à jour LIVRÉE v1.9.1.

**État en sortie :** `/opt/diwall/` à déployer (deploy.sh). 56 frictions / 22 sessions.

---

## 2026-06-10 — Session 21 (S-1 auth_indicator, S-2 --no-capture, v1.9.0)

**Contexte d'entrée :** v1.8.0 en production. Backlog réel : S-1 et S-2
(signaux terrain Gemini). FR-51 doctrine, #36/#38/#41/#42 clos (sessions 18-19).

**Travail effectué :**

- `shot.py` (S-1) — `--auth-indicator "<css>"` : après actions, vérifie la
  visibilité du sélecteur via `page.locator().is_visible()`. Ajoute
  `auth_status: "active"|"inactive"` à la racine JSON. Clé absente si flag absent.
- `shot.py` (S-2) — `--no-capture` : skip `page.screenshot()`, SoM,
  écritures PNG. `--no-capture + --som` et `--no-capture + capturer` :
  erreurs bloquantes avant lancement Playwright. Compatible `--a11y`,
  `--sauver-session`, `--auth-indicator`.
- `rpa.py` — `--no-capture` transmis à shot.py. `auth_indicator` lu depuis
  la racine du scénario JSON, transmis via `--auth-indicator`.
- `scenarios/schema.json` — `auth_indicator` optionnel ajouté aux propriétés racine.

**Tests :** T_S1_A à T_S2_D — tous verts (8/8).

**État en sortie :** `/opt/diwall/` synchronisé (deploy.sh). v1.9.0. 56 frictions / 21 sessions.

---

## 2026-06-09/10 — Sessions 19–20 (FR-54 à FR-58, v1.8.0 publiée)

**Contexte d'entrée :** errata session 18 — venv recréé, `docs/` absent de
`deploy.sh`, `__version__` bloqué à 1.7.3. Correction avant toute validation.

**Travail effectué :**

- `shot.py` (FR-54) — `--actions` fichier désormais supporté en mode
  `--reprendre-session` (Mode B). Les deux modes sont symétriques.
- `shot.py` (FR-55) — `attendre_url` gagne le paramètre `attendre_changement: true` :
  attend une navigation sortante avant d'appliquer le motif (évite le faux positif
  sur URL sous-chaîne).
- `scripts/deploy.sh` — `docs/` ajouté à la liste des déploiements.
- `scripts/install.sh` — check permission répertoires log corrigé `770` → `2770`.
- `CLAUDE.md` créé à la racine — pré-vol automatique Claude Code : 5 règles non
  négociables dont interdiction credentials en shell et pré-lecture `GUIDE_LLM.md`.
- `docs/GUIDE_LLM.md` v1.8 — bloc sécurité en tête + 4 pitfalls (FR-54, FR-55,
  FR-56, FR-58 DIWALL_VAULT_DIR vs DIWALL_CONF).
- `docs/RETOUR_EXPERIENCE.md` — frictions #52–#56, synthèse session 19.
- `docs/RADAR_MODELES.md` créé — registre d'observations brutes sur le comportement
  des LLM face à Diwall (2 entrées : Claude Sonnet pré-corrections / Gemini Flash).

**Décision clé :** `RADAR_MODELES.md` public, sans filtre éditorial. La doctrine
de visibilité dit silence sur la *promotion*, pas sur la réalité. Les faux positifs
sont inclus — ils sont le signal.

**Benchmark Gemini Flash :** même exercice multi-cibles, post-corrections. Résultats
corrects, `depuis_vault` utilisé systématiquement, piège curl ignoré. Dérive unique :
FR-58 (DIWALL_VAULT_DIR), auto-corrigée. Validation de la doctrine perception/action.

**Commits :**
- `84100a1` — feat(v1.8): wait primitives, nettoyer_overlay, vault symlink fix, deploy docs
- `6982639` — fix(v1.8): FR-54 --actions file in Mode B, FR-55 attendre_url attendre_changement
- `7c84e01` — fix: neutraliser nom client dans synthèse session 19
- `9ca4d85` — docs(v1.8): FR-58 DIWALL_VAULT_DIR vs DIWALL_CONF, fix mentions obsolètes

**Release :** `v1.8.0` — tag créé, poussé, release GitHub publiée en anglais.

**État en sortie :** production `/opt/diwall/` synchronisée. 56 frictions / 19 sessions.

---

## 2026-06-09 — Session 18 (FR-47 à FR-53, v1.9)

**Contexte d'entrée :** PHASE_EXECUTION validée par l'opérateur après co-planification
avec Gemini. 6 frictions à implémenter (FR-47, FR-48, FR-49, FR-50, FR-53 ;
FR-52 annulée). Schéma JSON incomplet (refs sans définitions).

**Travail effectué :**

- `lib/vault.py` (FR-47) — sécurité symlink : `glob.glob` remplacé par
  `os.walk(followlinks=False)`. Les 4 tests T_CONF passent. Invariant : le
  parcours récursif ne peut pas sortir du répertoire vault via un lien symbolique.

- `_CADRE/GOUVERNANCE/PROTOCOLE_CLOTURE.md` (FR-48) — instruction n°4 complétée :
  purge des `.tmp` orphelins dans `/opt/diwall/` (`find … -maxdepth 1 … -delete`).

- `shot.py` (FR-49/50) — 5 nouvelles actions dans le dispatcher `executer_actions()` :
  `attendre_url`, `attendre_selecteur_present`, `attendre_absence`,
  `attendre_reseau_calme`, `nettoyer_overlay`. Point de conception : `nettoyer_overlay`
  utilise `visibility:hidden` (pas `display:none`) pour ne pas invalider les
  coordonnées SoM calculées avant le masquage.

- `lib/vector.py` (FR-53) — nouvelle interface optionnelle ChromaDB. Cascade
  DB_PATH : `DIWALL_VECTOR_DB` env → `diwall.conf.vector_db` → `_CADRE/MEMOIRE/`
  (si sibling) → `~/Vaults/Diwall/chroma_db`. Imports lazy (chromadb, requests).

- `scenarios/schema.json` — 5 définitions JSON Schema ajoutées (AttendreUrl,
  AttendreSelecteurPresent, AttendreAbsence, AttendreReseauCalme, NettoyerOverlay),
  `additionalProperties:false` sur chacune. Validation : 0 `$ref` orphelin.

- `scripts/deploy.sh` — `lib/vector.py` ajouté à `CODE_FILES`.
- `scripts/install.sh` — création `/var/log/diwall/preuves` + checks de permission.
- `docs/GUIDE_EXPLORATION.md` créé (doctrine exploration/exécution, SoM, SKILL_nom.md).
- `docs/GUIDE_HUMAIN.md` créé (guides opérateur étape par étape, table des pièges).
- `docs/GUIDE_LLM.md` mis à jour (cascade vault v1.8, 5 actions v1.9, CLI pitfalls).
- `docs/RETOUR_EXPERIENCE.md` mis à jour (session 18).

**Décision clé :** `nettoyer_overlay` sans heuristique automatique — sélecteur
CSS explicite obligatoire. Raison : une heuristique qui masquerait du contenu
légitime rendrait le diagnostic de régression impossible.

**Découverte :** `vector.py` n'avait pas été ajouté à `deploy.sh` lors de sa
création. Ajout en cours de session détecté lors de la vérification de cohérence.

**Commit :** `01c9d8a` — feat(v1.9): 5 wait primitives, nettoyer_overlay, vector.py, vault symlink fix

**État en sortie :** `main` à jour, production `/opt/diwall/` synchronisée.
53 frictions / 18 sessions.

---

---

## Session 30 — 15 juin 2026

**Travail effectué :**

- Tracker Matomo ajouté à `site_internet/index.html` (site `__DOMAINE_OPERATEUR__`,
  ID 7, instance Matomo de l'opérateur). Déployé via `deploy-site.sh`.
- Friction #65 documentée dans `docs/RETOUR_EXPERIENCE.md` : sélecteur `a.addSite`
  vs `button.addSite` (erreur), framework Vue.js vs hypothèse AngularJS (erreur),
  primitive `remplir` obligatoire pour les champs Vue, pause 4000 ms nécessaire.
- Fiche opératoire créée : `_CADRE/SPECIFICATIONS/PROCEDURES_LLM/TACHE_matomo-ajouter-site.md`.

**Décision :** pas de bump de version — `site_internet/` est hors dépôt public,
aucun code Diwall modifié.

---

## Session 26 — 12 juin 2026

**Travail effectué :**

- `docs/GUIDE_LLM.md` — 5 règles documentées issues de la validation E2E terrain (v1.9.3) :
  - FN9 : champs `defiler` corrects (`px`/`selecteur`) — bloc wrong/correct ajouté pour prévenir la confusion avec `direction`/`pixels`
  - FN6 : syntaxe `:nth-match()` — ne peut pas être chaîné en suffixe ; doit envelopper le sélecteur complet
  - FN5 : noms de domaine dans les sélecteurs `<a>` → strict mode violation ; naviguer par URL directe
  - FN7 : `attendre_reseau_calme` + opération serveur synchrone longue → timeout screenshot 30s fixe non contrôlable par `--timeout` ; pattern `pause` documenté
  - FN8 : `evaluer` mutant dispatché avant le timeout Diwall → état serveur à vérifier avant relance du scénario

**Version :** GUIDE_LLM.md v1.9 (doc only — pas de bump de version Diwall).

**Commit :** `8a59e36` — docs(GUIDE_LLM): add FN5–FN9 rules from Sillage E2E validation

---

## Sessions antérieures

Les sessions 1 à 17 sont documentées dans :
`~/git/Diwall/_CADRE/MEMOIRE/ADDENDUM_*.md`
et dans `docs/RETOUR_EXPERIENCE.md`.
