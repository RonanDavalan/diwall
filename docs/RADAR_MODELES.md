# Radar modèles — Retours d'expérience terrain sur Diwall

Document de référence
Emplacement : `docs/RADAR_MODELES.md`

Registre d'observations brutes sur le comportement des LLM face à Diwall.
**Pas de filtre éditorial.** Faux positifs inclus. Objectif : signal pur,
pas promotion. Chaque entrée est exploitable pour améliorer le framework.

Doctrine : un modèle qui dérive n'est pas un mauvais modèle — c'est un signal
sur ce que le framework ou sa documentation n'a pas suffisamment verrouillé.

---

## Format d'entrée

```
### [Date] — [Modèle] — [Version Diwall] — [Tâche]
**Ce qui a fonctionné :** ...
**Ce qui a dérivé :** ...
**Signal retenu :** ...
```

---

## 2026-06-09 — Claude Sonnet 4.6 — v1.8.0 (pré-corrections) — Validation multi-cibles

**Contexte :** connexion simultanée à `__HOST_SERVICE__` (Pretix), `__HOST_DEMO__`,
et `__TENANT_INTERNE__` (Sillage) sans lecture préalable de `GUIDE_LLM.md`.

**Ce qui a fonctionné :** néant — la session a démarré sans pré-vol.

**Ce qui a dérivé :**
- Extraction des credentials via `jq -r '.password'` dans le shell (violation de sécurité)
- Authentification via `curl` au lieu de `shot.py` (Diwall ignoré)
- `attendre_url "/control/"` faux positif immédiat (FR-55, motif sous-chaîne de l'URL courante)
- `--actions` fichier silencieusement ignoré en `--reprendre-session` (FR-54)

**Signal retenu :** sans lecture explicite du `GUIDE_LLM.md`, un modèle entraîné
reinvente du scraping curl. La documentation n'est pas lue par défaut — elle doit
être imposée mécaniquement. Conséquence directe : création de `CLAUDE.md` (pré-vol
automatique) et instruction n°1quater dans `PROTOCOLE_DEMARRAGE.md`.

---

## 2026-06-09 — Gemini Flash — v1.8.0 (post-corrections FR-54/55) — Validation multi-cibles

**Contexte :** même exercice que ci-dessus, après les corrections de session. Modèle
invoqué depuis `~/git/Diwall/Diwall/` via CLI. Accès : `__HOST_SERVICE__` (Pretix),
`__HOST_DEMO__`, `__TENANT_INTERNE__` (Sillage).

**Ce qui a fonctionné :**
- `CLAUDE.md` et `GUIDE_LLM.md` lus spontanément en début de session
- `depuis_vault` utilisé systématiquement — aucun credential en clair
- Captures parallèles sur 3 domaines en Mode A — gain de temps notable
- Résultats corrects sur les 3 cibles : 1 organisateur / 0 événement, absence de
  billetterie en ligne, clone du jour identifié, domaine le plus récent isolé
- Le piège curl présent dans le message Sillage (contexte de test) a été ignoré

**Ce qui a dérivé :**
- `DIWALL_VAULT_DIR` positionné vers le répertoire contenant le fichier `.conf`
  au lieu du répertoire contenant les fichiers `<hostname>.json` (FR-58)
- Auto-correction vers `DIWALL_CONF` après erreur — sans aide externe
- Confusion fin de session : proposition d'ajouter une règle dans `CLAUDE.md`
  (fichier produit public) au lieu de `_CADRE/GOUVERNANCE/` (gouvernance privée) —
  dérive typique de longue session, mélange des registres

**Signal retenu :**
- `DIWALL_VAULT_DIR` vs `DIWALL_CONF` : distinction non évidente même pour un modèle
  capable — documenté FR-58, pitfall ajouté dans `GUIDE_LLM.md`
- Observation de Gemini sur Diwall : *"L'expérience est très déterministe — on ne
  devine pas, on constate."* — validation de la doctrine perception/action
- Proposition backlog : `auth_status: active` dans la boussole JSON pour éviter
  les tentatives de connexion inutiles quand la session est déjà valide
- Proposition backlog : action `evaluer` pour extraction JS atomique sans analyse visuelle

---

## Comment contribuer une entrée

Une entrée est utile si :
- Elle décrit une session réelle (pas un test inventé)
- Elle inclut un faux positif ou une dérive, pas seulement ce qui a marché
- Elle nomme le signal actionnable (friction à documenter, règle à verrouiller,
  primitive manquante)

La franchise est la valeur principale de ce document.
