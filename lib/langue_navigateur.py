"""
langue_navigateur.py — dérive la langue que le navigateur déclare, à partir de
l'environnement du processus.

Pourquoi ce fichier existe :
    Un contexte Playwright créé sans `locale` laisse Chromium prendre sa langue
    d'interface dans l'environnement (`navigator.language`), mais il n'envoie
    alors aucun en-tête `Accept-Language`. Le JavaScript de la page voit une
    langue, le serveur n'en voit aucune : l'identité déclarée est incohérente,
    et tout site qui choisit sa langue sur l'en-tête sert sa langue par défaut.
    Passer la même valeur en `locale` fait poser à Playwright le même code dans
    l'en-tête et dans `navigator.language`.

Entrée / sortie :
    locale_navigateur(environ) -> str, un code du type "fr-FR", "de" ou "en-US".
    Fonction pure : elle ne lit que le dictionnaire reçu, jamais os.environ
    directement, pour rester testable hors d'un navigateur.
"""
import re

# Ordre suivi par Chromium lui-même, vérifié par mesure : LANGUAGE l'emporte,
# même quand LANG vaut C ou POSIX ; ensuite les variables de locale POSIX,
# de la plus générale à la plus faible.
_VARIABLES_LOCALE = ("LC_ALL", "LC_MESSAGES", "LANG")

# Ce que Chromium déclare quand l'environnement ne dit rien d'exploitable.
_PAR_DEFAUT = "en-US"

# Forme acceptée en sortie : une langue de deux ou trois lettres, suivie de
# sous-étiquettes. Une valeur d'environnement inattendue ne doit jamais
# atteindre Playwright, qui refuserait de créer le contexte.
_FORME_ETIQUETTE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


def _normaliser(valeur):
    """`fr_FR.UTF-8@euro` -> `fr-FR` ; `fr` reste `fr`. Retire l'encodage et
    le modificateur, remplace le séparateur POSIX par celui des étiquettes de
    langue."""
    valeur = valeur.split("@", 1)[0].split(".", 1)[0].strip()
    return valeur.replace("_", "-")


def locale_navigateur(environ):
    """Langue à déclarer par le navigateur, dérivée de `environ`."""
    brute = ""
    langage = environ.get("LANGUAGE") or ""
    for element in langage.split(":"):
        if element.strip():
            brute = element
            break
    if not brute:
        for nom in _VARIABLES_LOCALE:
            if environ.get(nom):
                brute = environ[nom]
                break
    etiquette = _normaliser(brute)
    if not etiquette or etiquette in ("C", "POSIX") or not _FORME_ETIQUETTE.match(etiquette):
        return _PAR_DEFAUT
    return etiquette
