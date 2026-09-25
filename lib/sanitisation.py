"""
sanitisation.py — Neutralisation partagée des secrets et URLs sensibles.

Pourquoi ce fichier existe : cinq vagues d'audit ont chacune refermé un
symptôme de la même faille — une fonction de neutralisation correcte
n'existait que dans lib/journal.py, donc seul le canal journal en
bénéficiait. stdout/stderr, ce que lit l'agent LLM, laissait fuir en clair
un `document.cookie`, une query OAuth (`?code=...`) ou un message
d'exception Playwright. Ce module est le point d'appel unique pour
shot.py, rpa.py, watch.py et journal.py — plus aucun des quatre ne
redéfinit sa propre neutralisation.

Entrée / sortie :
    Fonctions pures — une valeur (str/dict/list/URL) en entrée, sa forme
    neutralisée en sortie. Aucun état, aucun I/O.

Dépend de / dont dépend :
    Aucune dépendance interne au projet. journal.py, shot.py, rpa.py et
    watch.py importent depuis ce module.

Spécification : _CADRE/SPECIFICATIONS/CHANTIER_SANITISATION.md (LOT 1)
"""
import math
import re
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Audit 05/08/2026 (D-06) : le filtre C-06 cherchait des mots, alors que les
# secrets ont des formes — un JWT réel ne contient jamais la chaîne littérale
# "jwt", et PHPSESSID/clés API passaient sans qu'aucun mot ne matche. 'sess'
# (substring, pas de \b : PHPSESSID n'a pas de séparateur avant 'sess'),
# 'csrf'/'xsrf'/'auth' ajoutés.
# Audit 06/08/2026 (E-05) : le seuil base64 remonte de 20 à 32 caractères et
# se double d'un plancher d'entropie — sans ça, un sélecteur CSS
# (#btn-sauvegarder-barre) ou un nom de fichier (capture_...png) matchaient
# aussi. Sur `diagnostic_dom.json`, la redaction ne porte plus sur la chaîne
# entière d'une structure JSON (un dict contenant "type":"password" perdait
# tout l'inventaire des <input>, pas seulement ce champ) mais uniquement sur
# les feuilles qui, individuellement, portent une forme ou un mot-clé de
# secret — et les mots-clés ne s'appliquent qu'aux feuilles qui ressemblent
# à un jeton isolé (ni espace ni ponctuation JSON), pour ne pas happer un
# libellé ordinaire ("Authentification à deux facteurs").
_MOTIFS_SENSIBLES_EVALUER = re.compile(r"token|session|password|bearer|jwt|sess|csrf|xsrf|auth", re.IGNORECASE)
# G-30 (CHANTIER_SANITISATION.md, LOT 5, amendement 07/08/2026) demandait
# d'abaisser ce seuil à 16-20 caractères. Non appliqué, écart signalé :
# testé le 07/08/2026, un seuil de 16 ou 20 fait remonter en faux positif
# exactement les deux exemples déjà cités par le commentaire E-05 ci-dessus
# — "capture_...png" (préfixe réel produit par shot.py::chemin_png() : un
# nom généré par `time.time_ns()` donne "capture_1786069867572488219",
# 27 caractères, entropie 3.84 ≥ seuil 3.5) — et un troisième cas neuf,
# "diwall-monter-secrets" (nom d'un script Diwall lui-même, entropie 3.69).
# Le plancher d'entropie (E-05) ne suffit pas seul à les exclure sous 32.
# Abaisser réintroduirait la régression que E-05 avait corrigée la veille
# dans ce même fichier. Conservé à 32, arbitrage à soumettre à Ronan.
# Limite résiduelle (documentation demandée par G-30) : un secret de 20-31
# caractères base64 échappe à ce filtre — rattrapé seulement s'il porte par
# ailleurs un mot-clé sensible sur un jeton isolé, ou s'il prend la forme
# d'un JWT (_MOTIF_JWT, indépendant de cette longueur).
_BASE64_LONGUE = re.compile(r"[A-Za-z0-9+/=_-]{32,}")
# Forme d'un JWT : trois segments base64url séparés par des points — aucun
# des deux motifs ci-dessus ne le capte, les points cassent _BASE64_LONGUE
# en tronçons et "jwt" n'apparaît jamais dans le jeton lui-même.
# Les deux premiers segments encodent un en-tête puis une charge JSON : ils
# commencent par `eyJ`, qui est `{"` en base64url. C'est cette signature qui
# est exigée ici. Trois identifiants chaînés par des points, seule condition
# d'une forme plus large, décrivent aussi bien `navigator.languages.join` ou
# un nom d'hôte à deux libellés longs, et faisaient refuser un script
# ordinaire comme masquer une URL renvoyée par `evaluer`. Un jeton dont le
# JSON commencerait par une espace (`{ "` → `eyAi`) échappe à ce motif ; sa
# signature, longue et aléatoire, reste prise par _BASE64_LONGUE.
_MOTIF_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{5,}\.eyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]*")
# Ponctuation JSON ou espace : une feuille qui en contient n'est pas un
# jeton isolé (un mot-clé qui matche dedans est un mot ordinaire, pas un
# secret collé sans séparateur).
_PONCTUATION_OU_ESPACE = re.compile(r'[\s{}\[\]":,]')
_PROFONDEUR_MAX_EVALUER = 8


def _entropie_shannon(texte):
    """Entropie de Shannon en bits/caractère — distingue un jeton aléatoire
    (~4.5-6 bits/car. sur l'alphabet base64) d'une chaîne structurée
    (nom de fichier, sélecteur CSS, timestamp), nettement plus répétitive."""
    if not texte:
        return 0.0
    freq = {}
    for c in texte:
        freq[c] = freq.get(c, 0) + 1
    n = len(texte)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


_SEUIL_ENTROPIE_BASE64 = 3.5


def _forme_secrete(texte):
    """Vrai si `texte` porte une forme de secret : JWT, ou segment base64
    long avec une entropie suffisante pour exclure les chaînes structurées."""
    if _MOTIF_JWT.search(texte):
        return True
    for m in _BASE64_LONGUE.finditer(texte):
        if _entropie_shannon(m.group(0)) >= _SEUIL_ENTROPIE_BASE64:
            return True
    return False


def _ressemble_jeton_isole(texte):
    """Vrai si `texte` ne contient ni espace ni ponctuation JSON — condition
    pour appliquer les mots-clés (`_MOTIFS_SENSIBLES_EVALUER`) : un libellé
    ordinaire ("Authentification à deux facteurs") contient des espaces et
    ne doit pas être traité comme un jeton collé (ex. PHPSESSID=abc123)."""
    return bool(texte) and not _PONCTUATION_OU_ESPACE.search(texte)


def _neutraliser_feuille_evaluer(valeur):
    texte = str(valeur)
    if _forme_secrete(texte):
        return "<valeur_filtree>"
    if _ressemble_jeton_isole(texte) and _MOTIFS_SENSIBLES_EVALUER.search(texte):
        return "<valeur_filtree>"
    return texte[:500]


def _neutraliser_structure_evaluer(valeur, profondeur=0):
    """Parcourt récursivement dict/list et ne rédige que les feuilles à
    risque (audit 06/08/2026, E-05) — la version précédente stringifiait la
    structure entière avant de décider, et perdait tout un inventaire
    `diagnostic_dom` (6 évaluations sur 6, dont 1 filtrée à tort) pour un
    seul champ `"type":"password"` noyé dedans."""
    if profondeur > _PROFONDEUR_MAX_EVALUER:
        return "<structure_tronquee>"
    if isinstance(valeur, dict):
        return {k: _neutraliser_structure_evaluer(v, profondeur + 1) for k, v in valeur.items()}
    if isinstance(valeur, list):
        return [_neutraliser_structure_evaluer(v, profondeur + 1) for v in valeur]
    if isinstance(valeur, str):
        return _neutraliser_feuille_evaluer(valeur)
    return valeur  # int/float/bool/None : pas de forme de secret possible


def _neutraliser_valeur_evaluer(valeur):
    """Audit 05/08/2026 (C-06, D-06), affiné 06/08/2026 (E-05) :
    valeur_retournee était le seul champ du journal à échapper à la
    doctrine « zéro credential » de ce module (voir docstring en tête de
    fichier). Les structures (dict/list — le cas courant de `evaluer` sur
    un inventaire DOM) sont parcourues feuille par feuille ; seules les
    feuilles qui portent une forme de secret (JWT, base64 à haute entropie)
    ou un mot-clé sur un jeton isolé sont rédigées.
    """
    if valeur is None:
        return None
    if isinstance(valeur, (dict, list)):
        return _neutraliser_structure_evaluer(valeur)
    return _neutraliser_feuille_evaluer(valeur)


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


def sanitiser_urls_dans_chaine(texte):
    """Trouve toute sous-chaîne `https?://\\S+` dans une chaîne libre (un
    message d'exception Playwright n'est pas une URL, mais peut en contenir
    une) et lui applique `_sanitiser_url_journal`. LOT 1, G-05."""
    if not texte:
        return texte
    return re.sub(r"https?://\S+", lambda m: _sanitiser_url_journal(m.group(0)), str(texte))


# Motif dédié, distinct de _MOTIFS_SENSIBLES_EVALUER : celui-ci ne couvre ni
# 'code' ni 'state', essentiels pour un callback OAuth en query string. On ne
# touche pas un motif déjà validé pour un autre usage sans revue séparée.
_MOTIFS_SENSIBLES_QUERY_PARAM = re.compile(
    r"token|code|state|key|secret|session|auth|password|bearer|jwt", re.IGNORECASE
)


def rediger_query_params_sensibles(url):
    """Rédige la valeur des paramètres de query dont le *nom* matche
    `_MOTIFS_SENSIBLES_QUERY_PARAM`, conserve le nom du paramètre et le
    reste de l'URL intact — contrairement à `_sanitiser_url_journal`, qui
    supprime la query entière.

    Nécessaire pour `derive_session` (CHANTIER_SANITISATION.md §1b) : la
    query y porte le signal de dérive de session
    (`/?vue=login` remplaçant `/?vue=domaine`), qu'une suppression totale
    détruirait — variante du piège `attendre_url` (FR-55)."""
    if not url:
        return url
    try:
        p = urlparse(url)
        params = parse_qsl(p.query, keep_blank_values=True)
        params_rediges = [
            (cle, "<redige>" if _MOTIFS_SENSIBLES_QUERY_PARAM.search(cle) else valeur)
            for cle, valeur in params
        ]
        return urlunparse(p._replace(query=urlencode(params_rediges)))
    except Exception:
        return "[url non parseable]"


# LOT 4 (CHANTIER_SANITISATION.md, G-16/G-17, audit 07/08/2026) : port Python
# du prédicat JS _DW_EST_SENSIBLE_JS (shot.py, sur el.name/el.id/el.autocomplete
# après rendu) — appliqué ici à la chaîne du sélecteur CSS d'une action de
# scénario, avant tout lancement de Chromium. Même liste de mots-clés ; ne pas
# la faire diverger de _DW_EST_SENSIBLE_JS sans revue des deux côtés.
# Étendue le 07/08/2026 (LOT 5, G-33) : mfa|2fa|cvv|cvc|pan|ssn|iban, en
# miroir de l'extension apportée à _DW_EST_SENSIBLE_JS le même jour.
_MOTIFS_SENSIBLES_SELECTEUR = re.compile(
    r"password|pwd|passwd|pass|mdp|token|secret|api_key|apikey|credential|otp|totp"
    r"|mfa|2fa|cvv|cvc|pan|ssn|iban",
    re.IGNORECASE,
)


def valider_actions_secrets(actions):
    """Rejette toute action `remplir`/`remplir_som` portant un credential en
    clair — deux contrôles indépendants, tous deux avant tout lancement de
    Chromium :

    1. (préexistant) `secret_cle` présent mais `valeur` différente de
       `depuis_secrets`/`depuis_secrets_totp`.
    2. (LOT 4, G-16) le `selecteur` matche un motif sensible
       (`_MOTIFS_SENSIBLES_SELECTEUR`) et `valeur` n'est pas
       `depuis_secrets`/`depuis_secrets_totp` — indépendamment de
       `secret_cle`, qui n'est jamais obligatoire dans le schéma. Ne
       s'applique qu'à `remplir` (sélecteur CSS littéral) : `remplir_som`
       cible un id numérique de Set-of-Mark, sans texte exploitable avant
       le rendu de la page.

    Point d'entrée unique — importé par shot.py (charger_actions, avant
    Playwright) et par rpa.py (avant sérialisation de `actions` en argv du
    sous-processus shot.py, G-17 : un argv transite en clair par
    /proc/<pid>/cmdline, donc avant même que shot.py ait la moindre chance
    de valider).
    """
    valeurs_autorisees = {"depuis_secrets", "depuis_secrets_totp"}
    for i, a in enumerate(actions):
        t = a.get("type")
        if t == "evaluer" and _forme_secrete(str(a.get("script") or "")):
            raise ValueError(
                f"Action #{i} (evaluer) : le script contient une forme de secret "
                f"(JWT ou segment base64 à haute entropie) — credential en clair interdit"
            )
        if t not in {"remplir", "remplir_som"}:
            continue
        valeur = a.get("valeur")
        if a.get("secret_cle") and valeur not in valeurs_autorisees:
            raise ValueError(
                f"Action #{i} ({a['type']}) : secret_cle défini mais valeur n'est pas "
                f"'depuis_secrets' ou 'depuis_secrets_totp' — credential en clair interdit"
            )
        if t == "remplir" and valeur not in valeurs_autorisees and valeur is not None:
            selecteur = a.get("selecteur") or ""
            if _MOTIFS_SENSIBLES_SELECTEUR.search(selecteur):
                raise ValueError(
                    f"Action #{i} (remplir) : sélecteur {selecteur!r} ressemble à un champ "
                    f"sensible — valeur doit être 'depuis_secrets' ou 'depuis_secrets_totp', "
                    f"indépendamment de secret_cle"
                )


# Résiduel LOT 1/LOT 4 (audit GLM 07/08/2026, M-05) : motif dédié aux NOMS de
# clé d'un fichier secrets, distinct de _MOTIFS_SENSIBLES_EVALUER (teste des
# valeurs) et _MOTIFS_SENSIBLES_SELECTEUR (teste un sélecteur CSS) — un nom
# de clé qui matche ce motif n'est jamais listé, même quand la clé elle-même
# est absente et que le message d'erreur énumère les clés disponibles.
_MOTIFS_SENSIBLES_NOM_CLE = re.compile(
    r"password|totp|api.?key|bearer|jwt|secret|token|cvv|cvc|pan|ssn|iban",
    re.IGNORECASE,
)


def filtrer_noms_cles_sensibles(cles):
    """Retire de `cles` (liste de noms) tout nom qui matche
    `_MOTIFS_SENSIBLES_NOM_CLE`. Liste blanche inversée : un nom comme
    `totp_cle` révèle que le MFA est configuré, `api_key` suggère un accès
    API — ces noms ne doivent pas apparaître dans un message d'erreur
    `Clés disponibles` (CHANTIER_SANITISATION.md, M-05), même si les
    *valeurs* ne fuient jamais."""
    return [c for c in cles if not _MOTIFS_SENSIBLES_NOM_CLE.search(str(c))]
