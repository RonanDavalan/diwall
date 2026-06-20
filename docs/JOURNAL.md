# Journal de développement — Diwall

Historique des décisions et découvertes par session, dans l'ordre chronologique inverse.

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
