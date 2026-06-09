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

**Verbatim brut (Gemini Flash, non modifié) :**

```
✦ La navigation via Diwall est techniquement intéressante car elle offre une visibilité hybride
(SoM pour la précision, a11y pour la sémantique). Voici mon retour d'expérience :

  Fluidité et Navigation
   * Rapidité d'exécution : L'utilisation du Mode A (plusieurs actions en une seule commande) a
     rendu le processus fluide. Le fait de pouvoir paralléliser les captures initiales sur trois
     domaines différents fait gagner un temps précieux.
   * Précision : Le Set-of-Mark (SoM) est redoutable pour éviter les erreurs de clic sur des
     interfaces denses comme celle de Pretix. Je n'ai eu aucune "hallucination" de coordonnées.
   * Friction identifiée : Le passage en Mode Admin sur Pretix est nécessaire pour une vision
     exhaustive, mais il rajoute un saut de navigation (et donc une capture SoM supplémentaire)
     car l'ID des éléments change après le rechargement de la page.

  Propositions d'optimisation
   1. Standardisation des Vaults : Comme tu l'as souligné, la confusion entre DIWALL_VAULT_DIR
      et DIWALL_CONF est un point de friction. Permettre à vault.py de supporter les deux
      variables en fallback faciliterait la portabilité des scripts.
   2. Stratégie de "Sondage Atomique" : Pour des vérifications de routine (ex: nombre
      d'événements), on pourrait intégrer des scripts d'évaluation JS (type: evaluer) directement
      dans la chaîne d'actions pour extraire des chiffres sans avoir à analyser visuellement
      chaque étape.
   3. Détection de l'état de session : Ajouter un indicateur dans la boussole
      (ex: auth_status: active) permettrait d'éviter des tentatives de connexion inutiles si la
      session est déjà valide.

  L'expérience globale est très "déterministe", ce qui est rassurant pour un agent. On ne devine
  pas, on constate.

  [Active Topic: Authentication and Investigation]
```

**Observations externes (opérateur, non attribuées à Gemini) :**
- `DIWALL_VAULT_DIR` positionné vers le répertoire contenant le `.conf` au lieu du répertoire
  contenant les fichiers `<hostname>.json` — auto-corrigé vers `DIWALL_CONF` sans aide (FR-58)
- Confusion en fin de session : proposition d'inscrire une règle dans `CLAUDE.md` (produit
  public) au lieu de `_CADRE/GOUVERNANCE/` — dérive typique de longue session

---

## Comment contribuer une entrée

Une entrée est utile si :
- Elle décrit une session réelle (pas un test inventé)
- Elle inclut un faux positif ou une dérive, pas seulement ce qui a marché
- Elle nomme le signal actionnable (friction à documenter, règle à verrouiller,
  primitive manquante)

La franchise est la valeur principale de ce document.
