"""
journal.py — Journal d'opérations Diwall (lot v1.4, étapes 1-3).

Trace append-only des runs Diwall sur les cibles, en JSON Lines.

Garanties :
- **Best-effort** : un échec de journalisation ne fait JAMAIS échouer
  l'opération Diwall (toute exception est avalée, avec un warning stderr).
- **Zéro credential** : les actions ne sont jamais sérialisées brutes ;
  seul leur résumé neutralisé est écrit, et une valeur `depuis_vault` est
  remplacée par le marqueur `<vault:clé>` (la valeur réelle n'existe pas
  dans l'action — Diwall utilise toujours `depuis_vault`).
- **Append atomique** : écriture d'une seule ligne sous verrou exclusif.

Spécification : _CADRE/SPECIFICATIONS/35_JOURNAL_OPERATIONS.md
"""
import fcntl
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone


def _journal_path():
    return os.environ.get("DIWALL_JOURNAL", "/var/log/diwall/operations.jsonl")


def _preuves_dir():
    explicite = os.environ.get("DIWALL_PREUVES")
    if explicite:
        return explicite
    return os.path.join(os.path.dirname(_journal_path()), "preuves")


# ── Classification des actions (étape 2) ─────────────────────────────────────
# La présence d'une action de classe « écriture » rend le run mutatif.
# `evaluer` est classé écriture par prudence (un script peut muter le DOM).
ACTIONS_ECRITURE = frozenset({
    "cliquer", "cliquer_som", "cliquer_visuel",
    "remplir", "remplir_som", "evaluer",
})


def est_mutatif(actions):
    """True si au moins une action de classe écriture est présente.

    Heuristique technique : le runtime ne connaît pas la sémantique métier
    (un clic peut supprimer ou non). Le sens est porté par `intention`.
    """
    for a in actions or []:
        if isinstance(a, dict) and a.get("type") in ACTIONS_ECRITURE:
            return True
    return False


# ── Neutralisation des actions (sécurité — étape 1) ──────────────────────────
def _resumer_action(action):
    """Résumé court et neutralisé d'une action.

    Une valeur `depuis_vault` devient `<vault:clé>` : aucune valeur de
    credential ne transite par le journal.
    """
    if not isinstance(action, dict):
        return str(action)[:80]
    t = action.get("type", "?")
    ref = action.get("id", action.get("selecteur", ""))
    tete = f"{t}#{ref}" if ref != "" else t
    if "valeur" in action:
        if action.get("valeur") == "depuis_vault":
            return f"{tete}=<vault:{action.get('vault_cle', '?')}>"
        # Défense en profondeur : la valeur d'une saisie n'est jamais
        # journalisée en clair. Selon le chemin d'appel (rpa.py résout le
        # vault en amont), une valeur de saisie peut être un credential
        # déjà résolu — on ne peut pas le distinguer ici, donc on masque.
        if t in ("remplir", "remplir_som"):
            return f"{tete}=<saisie>"
        return f"{tete}={str(action.get('valeur'))[:40]}"
    if t == "evaluer" and action.get("script"):
        return f"evaluer:{str(action['script'])[:60]}"
    if t == "naviguer" and action.get("url"):
        return f"naviguer:{action['url']}"
    return tete


def resumer_actions(actions):
    return [_resumer_action(a) for a in (actions or [])]


# ── Archivage des preuves (étape 3) ──────────────────────────────────────────
def archiver_preuves(operation_id, captures):
    """Copie les captures vers <preuves>/AAAA-MM/<operation_id>/.

    Retourne la liste des chemins archivés. Best-effort : une copie qui
    échoue est ignorée. Appelée uniquement pour les runs mutatifs.
    """
    mois = datetime.now().strftime("%Y-%m")
    dest_dir = os.path.join(_preuves_dir(), mois, operation_id)
    try:
        os.makedirs(dest_dir, exist_ok=True)
    except OSError as e:
        print(f"⚠ journal : preuves non archivées ({e})", file=sys.stderr)
        return list(captures or [])
    archivees = []
    for chemin in captures or []:
        try:
            if chemin and os.path.isfile(chemin):
                dest = os.path.join(dest_dir, os.path.basename(chemin))
                shutil.copy2(chemin, dest)
                archivees.append(dest)
        except OSError as e:
            print(f"⚠ journal : preuve {chemin} non archivée ({e})",
                  file=sys.stderr)
    return archivees


# ── Écriture d'une entrée ────────────────────────────────────────────────────
def enregistrer_operation(outil, version, cible_url, resultat, actions,
                          diwall_meta=None, intention=None, captures=None,
                          erreur=None, mutatif=None):
    """Compose et écrit une entrée de journal. Best-effort, ne lève jamais.

    Réutilise les champs d'environnement de `diwall_meta` (v1.3.2) :
    hostname_executant, utilisateur_executant, profil_actif,
    modeles_utilises.

    `mutatif` : si None, déduit des actions (est_mutatif) ; sinon imposé
    par l'appelant (watch.py n'a pas d'actions au sens de shot.py —
    --sauver-reference est mutatif, les comparaisons sont en lecture).
    """
    try:
        meta = diwall_meta or {}
        operation_id = uuid.uuid4().hex[:12]
        mutatif = est_mutatif(actions) if mutatif is None else bool(mutatif)

        if mutatif and captures:
            captures_ref = archiver_preuves(operation_id, captures)
        else:
            captures_ref = list(captures or [])

        entree = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "operation_id": operation_id,
            "outil": outil,
            "version": version,
            "cible_url": cible_url,
            "resultat": resultat,
            "mutatif": mutatif,
            "hostname_executant": meta.get("hostname_executant"),
            "utilisateur_executant": meta.get("utilisateur_executant"),
            "profil_actif": meta.get("profil_actif"),
        }
        if intention:
            entree["intention"] = intention
        actions_resumees = resumer_actions(actions)
        if actions_resumees:
            entree["actions"] = actions_resumees
        if captures_ref:
            entree["captures"] = captures_ref
        if meta.get("modeles_utilises"):
            entree["modeles_utilises"] = meta["modeles_utilises"]
        if erreur:
            entree["erreur"] = erreur

        _ecrire_ligne(entree)
    except Exception as e:  # best-effort absolu : ne jamais casser le run
        print(f"⚠ journal : opération non journalisée ({e})", file=sys.stderr)


def _fallback_path():
    return os.environ.get(
        "DIWALL_JOURNAL_FALLBACK",
        "/tmp/diwall/operations.fallback.jsonl",
    )


def _ecrire_ligne(entree):
    """Append atomique d'une ligne JSON, sous verrou exclusif.

    Le fichier est ouvert et refermé à chaque appel — aucun descripteur
    de fichier n'est conservé entre deux runs. Ce choix est intentionnel :
    il immunise l'implémentation contre le glissement de descripteur lors
    d'une rotation logrotate (rename de l'inode courant), sans exiger
    copytruncate. Ne pas introduire un fd persistant de module sans relire
    cette note.
    """
    path = _journal_path()
    repertoire = os.path.dirname(path)
    if repertoire:
        os.makedirs(repertoire, exist_ok=True)
    ligne = json.dumps(entree, ensure_ascii=False) + "\n"
    try:
        with open(path, "a", encoding="utf-8") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(ligne)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        # Fallback sans consolidation auto (spec 36_ §2.3).
        # En cas d'échec du fallback lui-même, on abandonne silencieusement.
        try:
            fb = _fallback_path()
            os.makedirs(os.path.dirname(fb) or ".", exist_ok=True)
            with open(fb, "a", encoding="utf-8") as f:
                f.write(ligne)
                f.flush()
            print(
                f"⚠ journal : log principal inaccessible, "
                f"entrée écrite dans {fb}",
                file=sys.stderr,
            )
        except OSError:
            raise  # remonte pour être avalée par l'enveloppe best-effort
