"""
securite_url.py — validation de schéma et d'absence de userinfo pour toute
URL externe manipulée par Diwall.

Pourquoi ce fichier existe :
    Extrait de shot.py (audit 06/08/2026, F-02) — cette validation existait
    en deux exemplaires indépendants, shot.py (schéma + userinfo) et rpa.py
    (schéma seul). Une URL à userinfo (user:pass@host) passait le contrôle
    appauvri de rpa.py puis transitait par l'argv du sous-processus shot.py
    (donc /proc/<pid>/cmdline) avant d'être rejetée là — la forme interdite
    par la règle n°2 de CLAUDE.md, atteinte par un chemin interne à Diwall.
    Point de passage unique désormais : tout appelant qui reçoit une URL
    externe avant de la faire transiter vers un sous-processus ou une
    navigation l'appelle en premier.
"""
from urllib.parse import urlparse


def valider_schema_url(url):
    """Rejette les URL dont le schéma n'est pas http ou https, ou qui portent
    un userinfo (audit 05/08/2026, C-07 : user:password@host survivait en
    clair jusqu'au journal — --http-credentials traite ce cas correctement,
    scopé par origine)."""
    if not url:
        return
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError(
            f"URL scheme '{scheme}' interdit — seuls http et https sont acceptés. URL: {url}"
        )
    if parsed.username or parsed.password:
        raise ValueError(
            "URL avec identifiants embarqués (user:password@host) interdite — "
            "utilisez --http-credentials, scopé par origine et jamais journalisé en clair."
        )
