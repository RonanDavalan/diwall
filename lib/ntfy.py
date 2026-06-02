"""
ntfy.py — Pont asynchrone pour les codes 2FA reçus par SMS ou courriel.

Pattern : Diwall publie une attente sur un topic ntfy →
l'opérateur publie le code depuis son téléphone (ou via curl) →
Diwall interroge l'API ntfy, récupère le code et l'injecte.

Configuration (par ordre de priorité) :
  1. DIWALL_NTFY_URL (variable d'environnement)
  2. Clé "ntfy.url" dans /opt/diwall/diwall.conf (JSON)
  3. Défaut : https://ntfy.sh

Sécurité : le topic doit être un secret partagé opérateur-machine,
jamais un nom prévisible. Le stocker dans le vault sous 'ntfy_topic'.
"""
import json
import os
import time

_CONF_PATH = "/opt/diwall/diwall.conf"
_NTFY_DEFAULT = "https://ntfy.sh"
_POLL_INTERVAL_S = 3


def _ntfy_url() -> str:
    if "DIWALL_NTFY_URL" in os.environ:
        return os.environ["DIWALL_NTFY_URL"].rstrip("/")
    if os.path.isfile(_CONF_PATH):
        try:
            with open(_CONF_PATH, encoding="utf-8") as f:
                conf = json.load(f)
            ntfy_conf = conf.get("ntfy") or {}
            if "url" in ntfy_conf:
                return ntfy_conf["url"].rstrip("/")
        except Exception:
            pass
    return _NTFY_DEFAULT


def publier_attente(topic: str, url_page: str, url_ntfy: str = None) -> None:
    """Publie un message d'attente MFA sur le topic ntfy."""
    import requests
    base = (url_ntfy or _ntfy_url()).rstrip("/")
    requests.post(
        f"{base}/{topic}",
        data=f"Code MFA attendu pour : {url_page}".encode("utf-8"),
        headers={
            "Title": "Diwall — Code 2FA requis",
            "Priority": "high",
            "Tags": "key",
        },
        timeout=10,
    )


def attendre_code(topic: str, timeout_s: int = 120, url_ntfy: str = None) -> str:
    """Interroge l'API ntfy jusqu'à réception d'un message ou timeout.

    Retourne le contenu du premier message reçu sur le topic depuis
    l'appel de cette fonction. Lève TimeoutError si timeout_s est dépassé.
    """
    import requests
    base = (url_ntfy or _ntfy_url()).rstrip("/")
    ts_debut = int(time.time())
    deadline = time.time() + timeout_s

    while time.time() < deadline:
        try:
            resp = requests.get(
                f"{base}/{topic}/json",
                params={"poll": "1", "since": str(ts_debut)},
                timeout=10,
            )
            for ligne in resp.text.strip().splitlines():
                if not ligne:
                    continue
                try:
                    msg = json.loads(ligne)
                except json.JSONDecodeError:
                    continue
                if msg.get("event") == "message" and msg.get("message"):
                    return msg["message"].strip()
        except Exception:
            pass
        time.sleep(_POLL_INTERVAL_S)

    raise TimeoutError(
        f"Aucun code MFA reçu sur le topic ntfy après {timeout_s}s."
    )
