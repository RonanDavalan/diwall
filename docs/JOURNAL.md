# Journal de développement — Diwall

Historique des décisions et découvertes par session, dans l'ordre chronologique inverse.

---

## 2026-06-09 — Session 18 (FR-47 à FR-53, v1.9)

**Contexte d'entrée :** PHASE_EXECUTION validée par Ronan après co-planification
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
