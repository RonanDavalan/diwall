# Journal de développement — Diwall

Historique des décisions et découvertes par session, dans l'ordre chronologique inverse.

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
