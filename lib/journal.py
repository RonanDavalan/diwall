"""
journal.py — Journal d'opérations Diwall (lot v1.4, étapes 1-3).

Trace append-only des runs Diwall sur les cibles, en JSON Lines.

Garanties :
- **Best-effort** : un échec de journalisation ne fait JAMAIS échouer
  l'opération Diwall (toute exception est avalée, avec un warning stderr).
- **Zéro credential** : les actions ne sont jamais sérialisées brutes ;
  seul leur résumé neutralisé est écrit, et une valeur `depuis_secrets` est
  remplacée par le marqueur `<secrets:clé>` (la valeur réelle n'existe pas
  dans l'action — Diwall utilise toujours `depuis_secrets`).
- **Append atomique** : écriture d'une seule ligne sous verrou exclusif.

Spécification : _CADRE/SPECIFICATIONS/35_JOURNAL_OPERATIONS.md
"""
import fcntl
import grp
import json
import os
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse


def _journal_path():
    explicite = os.environ.get("DIWALL_JOURNAL")
    if explicite:
        return explicite
    try:
        from lib.repertoire_chiffre import _lire_conf
        conf = _lire_conf()
        chemin = conf.get("journal", {}).get("chemin", "")
        if chemin:
            return os.path.expanduser(chemin)
    except Exception:
        pass
    return "/var/log/diwall/operations.jsonl"


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
    "attendre_mfa_ntfy",
    "cliquer_iframe", "remplir_iframe",  # v1.17.0, item 4
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

    Une valeur `depuis_secrets` devient `<secrets:clé>` : aucune valeur de
    credential ne transite par le journal.
    """
    if not isinstance(action, dict):
        return str(action)[:80]
    t = action.get("type", "?")
    ref = action.get("id", action.get("selecteur", ""))
    tete = f"{t}#{ref}" if ref != "" else t
    if "valeur" in action:
        if action.get("valeur") == "depuis_secrets":
            return f"{tete}=<secrets:{action.get('secret_cle', '?')}>"
        # Défense en profondeur : la valeur d'une saisie n'est jamais
        # journalisée en clair. Selon le chemin d'appel (rpa.py résout le
        # identifiants résolus en amont), une valeur de saisie peut être un credential
        # déjà résolu — on ne peut pas le distinguer ici, donc on masque.
        if t in ("remplir", "remplir_som", "remplir_iframe"):
            return f"{tete}=<saisie>"
        return f"{tete}={str(action.get('valeur'))[:40]}"
    if t == "evaluer" and action.get("script"):
        return f"evaluer:{str(action['script'])[:60]}"
    if t == "naviguer" and action.get("url"):
        return f"naviguer:{action['url']}"
    return tete


def resumer_actions(actions):
    return [_resumer_action(a) for a in (actions or [])]


def _neutraliser_actions_raw(actions):
    """Actions brutes neutralisées pour le champ actions_raw (v1.6).

    Préserve la structure dict (contrairement à resumer_actions qui produit
    des chaînes plates). Masquage appliqué :
    - remplir / remplir_som avec valeur directe : remplacée par "<saisie>"
    - depuis_secrets et depuis_secrets_totp : conservés tels quels (pas de valeur réelle)
    - evaluer : script tronqué à 500 caractères
    - attendre_mfa_ntfy : copié tel quel (le topic vient du répertoire chiffré, pas de l'action)
    - tout le reste : copié tel quel
    """
    resultat = []
    for a in actions or []:
        if not isinstance(a, dict):
            continue
        a2 = dict(a)
        t = a2.get("type", "")
        if t in ("remplir", "remplir_som", "remplir_iframe"):
            v = a2.get("valeur")
            if v not in ("depuis_secrets", "depuis_secrets_totp", None):
                a2["valeur"] = "<saisie>"
        elif t == "evaluer" and "script" in a2:
            a2["script"] = a2["script"][:500]
        resultat.append(a2)
    return resultat


# ── Archivage des preuves (étape 3) ──────────────────────────────────────────
def _preuves_dir_authentifie():
    """Chemin des preuves d'une page authentifiée (D-02) : à l'intérieur du
    répertoire chiffré credentials de l'opérateur, jamais sur le disque hôte
    nu. None si aucun secrets_dir n'est configuré (DIWALL_SECRETS_DIR,
    DIWALL_CONF, ou diwall.conf)."""
    try:
        from lib.repertoire_chiffre import _chemin_secrets
        return os.path.join(_chemin_secrets(), "preuves")
    except Exception:
        return None


def _retention_jours():
    """Rétention des preuves archivées, en jours. Clé 'preuves.retention_jours'
    de diwall.conf ; 0 ou absente désactive la purge (D-02)."""
    try:
        from lib.repertoire_chiffre import _lire_conf
        return int(_lire_conf().get("preuves", {}).get("retention_jours", 0))
    except Exception:
        return 0


def _purger_preuves_expirees(preuves_dir, retention_jours):
    """Supprime les sous-répertoires <preuves_dir>/AAAA-MM/ plus vieux que
    retention_jours. Best-effort, jamais bloquant (D-02)."""
    if retention_jours <= 0:
        return
    try:
        cutoff = datetime.now().toordinal() - retention_jours
        for nom in os.listdir(preuves_dir):
            try:
                mois = datetime.strptime(nom, "%Y-%m")
            except ValueError:
                continue
            if mois.toordinal() < cutoff:
                shutil.rmtree(os.path.join(preuves_dir, nom), ignore_errors=True)
    except OSError:
        pass


def archiver_preuves(operation_id, captures, auth_status=None):
    """Copie les captures vers <preuves>/AAAA-MM/<operation_id>/.

    Retourne la liste des chemins archivés. Best-effort : une copie qui
    échoue est ignorée. Appelée uniquement pour les runs mutatifs.

    Audit 05/08/2026 (D-02, option B — décision Ronan) : quand la page est
    authentifiée (`auth_status == "active"`), les captures ne sont archivées
    que si le répertoire chiffré credentials est monté — auquel cas elles y
    sont archivées, jamais sous le chemin par défaut du disque hôte nu.
    Sans répertoire chiffré monté, rien n'est archivé : la capture reste
    seulement dans le répertoire de run éphémère (/tmp/diwall/), jamais
    dupliquée en clair sur disque persistant. Constaté en production avant ce
    correctif : 73 PNG en clair sous /var/log/diwall/preuves/, permissions
    664, dont une capture pleine page d'un tableau de bord authentifié.

    Garde-fou de montage (v1.17.2, inchangé pour le cas non authentifié) : si
    <preuves> est configuré à l'intérieur du répertoire chiffré credentials
    mais que celui-ci n'est pas monté, n'archive rien.
    """
    if auth_status == "active":
        preuves_dir = _preuves_dir_authentifie()
        from lib.repertoire_chiffre import _repertoire_est_monte
        if not preuves_dir or not _repertoire_est_monte(preuves_dir):
            print(
                "⚠ journal : preuves non archivées (page authentifiée, répertoire "
                "chiffré non monté ou non configuré — capture non dupliquée en clair)",
                file=sys.stderr,
            )
            return list(captures or [])
    else:
        preuves_dir = _preuves_dir()
        if _ecriture_secrets_bloquee(preuves_dir):
            print(
                "⚠ journal : preuves non archivées (répertoire chiffré fermé — "
                "preuves configurées dans le répertoire chiffré)",
                file=sys.stderr,
            )
            return list(captures or [])
    mois = datetime.now().strftime("%Y-%m")
    dest_dir = os.path.join(preuves_dir, mois, operation_id)
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
                os.chmod(dest, 0o600)  # D-02 : 664 par défaut avant ce correctif
                archivees.append(dest)
        except OSError as e:
            print(f"⚠ journal : preuve {chemin} non archivée ({e})",
                  file=sys.stderr)
    _purger_preuves_expirees(preuves_dir, _retention_jours())
    return archivees


# ── Écriture d'une entrée ────────────────────────────────────────────────────
def enregistrer_operation(outil, version, cible_url, resultat, actions,
                          diwall_meta=None, intention=None, captures=None,
                          erreur=None, mutatif=None, evaluations=None,
                          operation_id=None, respect=None,
                          source_scenario=None, chainage=None, auth_status=None):
    """Compose et écrit une entrée de journal. Best-effort, ne lève jamais.

    Réutilise les champs d'environnement de `diwall_meta` (v1.3.2) :
    hostname_executant, utilisateur_executant, profil_actif,
    modeles_utilises.

    `mutatif` : si None, déduit des actions (est_mutatif) ; sinon imposé
    par l'appelant (watch.py n'a pas d'actions au sens de shot.py —
    --sauver-reference est mutatif, les comparaisons sont en lecture).

    `operation_id` (v1.16.0) : si fourni par l'appelant (shot.py transmet son
    identité de run unifiée), réutilisé tel quel — le journal n'en régénère
    pas un second. Sinon généré ici comme avant (appelants historiques :
    watch.py, ou tout appel sans cette primitive).

    `source_scenario` (v1.18.0) : nom de fichier du scénario (sans chemin),
    transmis par rpa.py via --source-scenario. Permet à `mode_conseille`
    d'identifier fiablement une entrée issue de `diagnostic_dom.json` sans
    parser le contenu des scripts journalisés.

    `chainage` (v1.19.0) : liste ordonnée de
    `{"scenario", "profondeur", "action_debut", "action_fin"}` produite par
    `rpa.py::_aplatir_actions()` quand le scénario utilise
    `declencher_scenario` — absente sinon (additif strict). Permet de
    reconstruire l'arbre d'appels d'un scénario chaîné après un échec en
    profondeur, sans quoi le journal ne montre qu'une liste plate d'actions.

    `auth_status` (audit 05/08/2026, D-02) : transmis tel quel à
    archiver_preuves — "active" redirige l'archivage vers le répertoire
    chiffré credentials plutôt que le chemin par défaut du disque hôte nu.
    """
    try:
        meta = diwall_meta or {}
        operation_id = operation_id or uuid.uuid4().hex[:12]
        mutatif = est_mutatif(actions) if mutatif is None else bool(mutatif)

        if mutatif and captures:
            captures_ref = archiver_preuves(operation_id, captures, auth_status=auth_status)
        else:
            captures_ref = list(captures or [])

        entree = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
            "operation_id": operation_id,
            "outil": outil,
            "version": version,
            "cible_url": _sanitiser_url_journal(cible_url),
            "resultat": resultat,
            "mutatif": mutatif,
            "hostname_executant": meta.get("hostname_executant"),
            "utilisateur_executant": meta.get("utilisateur_executant"),
            "profil_actif": meta.get("profil_actif"),
        }
        if intention:
            entree["intention"] = intention
        if source_scenario:
            entree["source_scenario"] = source_scenario
        if chainage:
            entree["chainage"] = chainage
        actions_resumees = resumer_actions(actions)
        if actions_resumees:
            entree["actions"] = actions_resumees
        if resultat == "succes" and actions:
            raw = _neutraliser_actions_raw(actions)
            if raw:
                entree["actions_raw"] = raw
        if captures_ref:
            entree["captures"] = captures_ref
        if meta.get("modeles_utilises"):
            entree["modeles_utilises"] = meta["modeles_utilises"]
        if erreur:
            entree["erreur"] = erreur
        if respect:
            entree["respect"] = respect
        if evaluations:
            entree["evaluations"] = [
                {"script": e.get("script", "")[:500], "valeur_retournee": _neutraliser_valeur_evaluer(e.get("valeur"))}
                for e in evaluations
                if isinstance(e, dict)
            ]

        _ecrire_ligne(entree)
    except Exception as e:  # best-effort absolu : ne jamais casser le run
        print(f"⚠ journal : opération non journalisée ({e})", file=sys.stderr)


# Audit 05/08/2026 (D-06) : le filtre C-06 cherchait des mots, alors que les
# secrets ont des formes — un JWT réel ne contient jamais la chaîne littérale
# "jwt", et PHPSESSID/clés API passaient sans qu'aucun mot ne matche. 'sess'
# (substring, pas de \b : PHPSESSID n'a pas de séparateur avant 'sess'),
# 'csrf'/'xsrf'/'auth' ajoutés ; _BASE64_LONGUE abaissé (40 → 20) pour capter
# les clés API courtes (~36 car.) que le seuil précédent laissait passer.
_MOTIFS_SENSIBLES_EVALUER = re.compile(r"token|session|password|bearer|jwt|sess|csrf|xsrf|auth", re.IGNORECASE)
_BASE64_LONGUE = re.compile(r"[A-Za-z0-9+/=_-]{20,}")
# Forme d'un JWT : trois segments base64url séparés par des points — aucun
# des deux motifs ci-dessus ne le capte, les points cassent _BASE64_LONGUE
# en tronçons et "jwt" n'apparaît jamais dans le jeton lui-même.
_MOTIF_JWT = re.compile(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]+")


def _neutraliser_valeur_evaluer(valeur):
    """Audit 05/08/2026 (C-06, D-06) : valeur_retournee était le seul champ du
    journal à échapper à la doctrine « zéro credential » de ce module (voir
    docstring en tête de fichier). Tronque à 500 caractères comme 'script',
    et remplace par un marqueur toute valeur qui ressemble à un secret —
    par mot-clé ou par forme (base64 longue, JWT).
    """
    if valeur is None:
        return None
    texte = str(valeur)
    if (_MOTIFS_SENSIBLES_EVALUER.search(texte)
            or _BASE64_LONGUE.search(texte)
            or _MOTIF_JWT.search(texte)):
        return "<valeur_filtree>"
    return texte[:500]


def _sanitiser_url_journal(url):
    """Conserve uniquement scheme://host/path — supprime toute query string,
    fragment, et userinfo (audit 05/08/2026, C-07 : p.netloc inclut
    'user:password@', qui survivait en clair dans le journal)."""
    if not url:
        return url
    try:
        p = urlparse(url)
        netloc_sans_userinfo = p.hostname or ""
        if p.port:
            netloc_sans_userinfo += f":{p.port}"
        return f"{p.scheme}://{netloc_sans_userinfo}{p.path}"
    except Exception:
        return "[url non parseable]"


def _fallback_path():
    return os.environ.get(
        "DIWALL_JOURNAL_FALLBACK",
        "/tmp/diwall/operations.fallback.jsonl",
    )


def _gid_diwall():
    try:
        return grp.getgrnam("diwall").gr_gid
    except KeyError:
        return -1


def _ecriture_secrets_bloquee(repertoire):
    """True si `repertoire` est configuré à l'intérieur du secrets_dir de
    l'opérateur mais que ce répertoire chiffré n'est actuellement pas monté (v1.17.2).

    Ne s'applique jamais au chemin système par défaut (`/var/log/diwall/`) ni
    à un `journal.chemin`/preuves personnalisé hors du répertoire chiffré — uniquement au
    cas où l'opérateur a délibérément configuré le journal ou les preuves à
    l'intérieur du répertoire chiffré credentials. Constat terrain à l'origine du
    correctif : écriture silencieuse en clair sur le disque hôte nu quand ce
    garde-fou était absent.
    """
    try:
        from lib.repertoire_chiffre import _chemin_secrets, _repertoire_est_monte
        secrets_dir = os.path.realpath(os.path.expanduser(_chemin_secrets()))
    except Exception:
        return False
    cible = os.path.realpath(repertoire)
    if cible != secrets_dir and not cible.startswith(secrets_dir + os.sep):
        return False
    return not _repertoire_est_monte(repertoire)


def _ecrire_fallback(ligne, raison):
    """Écrit dans le fallback local (spec 36_ §2.3), sans consolidation auto.

    Si le fallback lui-même échoue, l'exception remonte pour être avalée par
    l'enveloppe best-effort de l'appelant (`enregistrer_operation`).
    """
    fb = _fallback_path()
    fb_dir = os.path.dirname(fb) or "."
    os.makedirs(fb_dir, mode=0o700, exist_ok=True)
    fd_fb = os.open(fb, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o600)
    with os.fdopen(fd_fb, "a", encoding="utf-8") as f:
        f.write(ligne)
        f.flush()
    print(f"⚠ journal : {raison}, entrée écrite dans {fb}", file=sys.stderr)


def _ecrire_ligne(entree):
    """Append atomique d'une ligne JSON, sous verrou exclusif.

    Le fichier est ouvert et refermé à chaque appel — aucun descripteur
    de fichier n'est conservé entre deux runs. Ce choix est intentionnel :
    il immunise l'implémentation contre le glissement de descripteur lors
    d'une rotation logrotate (rename de l'inode courant), sans exiger
    copytruncate. Ne pas introduire un fd persistant de module sans relire
    cette note.

    Permissions : 640 + groupe diwall (C2 v1.15.1).
    Garde-fou de montage (v1.17.2) : si le chemin configuré est à l'intérieur du
    répertoire chiffré credentials mais que celui-ci n'est pas monté, écrit directement
    dans le fallback local plutôt que de recréer l'arborescence en clair sur
    le disque hôte nu.
    """
    path = _journal_path()
    repertoire = os.path.dirname(path)
    ligne = json.dumps(entree, ensure_ascii=False) + "\n"

    if repertoire and _ecriture_secrets_bloquee(repertoire):
        _ecrire_fallback(ligne, "répertoire chiffré fermé — journal configuré dans le répertoire chiffré")
        return

    if repertoire:
        os.makedirs(repertoire, mode=0o2770, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_APPEND, 0o640)
        gid = _gid_diwall()
        if gid != -1 and not os.path.exists(path + ".chowned"):
            try:
                os.chown(fd, -1, gid)
                # Audit 05/08/2026 (D-11) : sans cette sentinelle, la condition
                # ci-dessus est toujours vraie et os.chown est retenté à
                # chaque écriture — sans conséquence fonctionnelle, mais
                # fausse affordance d'idempotence pour un lecteur futur.
                open(path + ".chowned", "a").close()
            except PermissionError:
                pass
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(ligne)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        _ecrire_fallback(ligne, "log principal inaccessible")


def dernier_diagnostic_host(host):
    """v1.18.0 — retourne les `evaluations` (format journal, liste de
    {"script", "valeur_retournee"}) de la dernière entrée `operations.jsonl`
    dont `source_scenario == "diagnostic_dom.json"`, `resultat == "succes"`
    (v1.19.0 — un diagnostic interrompu à mi-course ne doit jamais alimenter
    un conseil) et dont l'host de `cible_url` correspond à `host`. None si
    aucune entrée trouvée, si le journal est illisible, ou sur toute erreur —
    best-effort, ne lève jamais (alimente `mode_conseille`, un confort de
    lecture, jamais un bloquant).

    Le journal est append-only : la dernière ligne qui correspond est la
    plus récente, pas besoin de trier par timestamp.
    """
    try:
        chemin = _journal_path()
        derniere = None
        with open(chemin, encoding="utf-8") as f:
            for ligne in f:
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    entree = json.loads(ligne)
                except json.JSONDecodeError:
                    continue
                if entree.get("source_scenario") != "diagnostic_dom.json":
                    continue
                if entree.get("resultat") != "succes":
                    continue
                if urlparse(entree.get("cible_url") or "").hostname != host:
                    continue
                if entree.get("evaluations"):
                    derniere = entree
        return derniere.get("evaluations") if derniere else None
    except (FileNotFoundError, OSError):
        return None
