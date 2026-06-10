# Journal de développement — Diwall

Historique des décisions et découvertes par session, dans l'ordre chronologique inverse.

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

## Sessions antérieures

Les sessions 1 à 17 sont documentées dans :
`~/git/Diwall/_CADRE/MEMOIRE/ADDENDUM_*.md`
et dans `docs/RETOUR_EXPERIENCE.md`.
