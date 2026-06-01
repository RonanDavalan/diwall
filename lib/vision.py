"""
vision.py — Phase 3 : localisation d'éléments par description visuelle.

Utilisé par shot.py pour exécuter l'action cliquer_visuel.
Le LLM reçoit une capture d'écran et une description en langage naturel,
et retourne les coordonnées du centre de l'élément décrit.
"""

import base64
import json
import re
import struct


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3-vl:2b"  # défaut localisation, validé par benchmark vision interne (qwen3-vl 2b/4b/8b)
CLAUDE_MODEL = "claude-haiku-4-5-20251001"


def _dimensions_png(path):
    """Lit largeur et hauteur depuis l'en-tête PNG sans dépendance externe."""
    with open(path, "rb") as f:
        f.read(16)  # signature PNG (8 octets) + tag IHDR (4) + longueur (4)
        largeur = struct.unpack(">I", f.read(4))[0]
        hauteur = struct.unpack(">I", f.read(4))[0]
    return largeur, hauteur


MAX_VISION_LARGEUR = 640
MAX_VISION_HAUTEUR = 360


def _lire_b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _reduire_et_b64(path):
    """Réduit l'image à MAX_VISION_* pour économiser les tokens de contexte."""
    from PIL import Image
    import io

    img = Image.open(path)
    if img.width > MAX_VISION_LARGEUR or img.height > MAX_VISION_HAUTEUR:
        img = img.resize((MAX_VISION_LARGEUR, MAX_VISION_HAUTEUR), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def _prompt(description, largeur, hauteur):
    return (
        f"Tu analyses une capture d'écran de {largeur}x{hauteur} pixels. "
        f"Localise l'élément suivant : \"{description}\".\n\n"
        "Retourne un JSON avec exactement ces champs :\n"
        "- found (bool) : true si l'élément est clairement visible\n"
        f"- x_pct (float 0.0-1.0) : position horizontale du centre, en fraction de {largeur}px\n"
        f"- y_pct (float 0.0-1.0) : position verticale du centre, en fraction de {hauteur}px\n"
        "- confiance (float 0.0-1.0) : degré de certitude sur la localisation\n\n"
        "Si l'élément n'est pas visible ou ambigu, retourne {\"found\": false}.\n"
        "Réponds uniquement en JSON valide, sans texte avant ni après."
    )


def _extraire_json(texte):
    """Extrait le premier objet JSON valide d'une réponse LLM (gère markdown, texte libre)."""
    texte = texte.strip()
    # Tentative directe
    try:
        return json.loads(texte)
    except (json.JSONDecodeError, TypeError):
        pass
    # Bloc ```json ... ``` ou ``` ... ```
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", texte, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Premier { ... } dans le texte libre
    m = re.search(r"\{[^{}]+\}", texte, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    return None


def _parse_resultat(raw, largeur, hauteur):
    """Convertit la réponse LLM en coordonnées pixel clampées."""
    data = _extraire_json(raw)
    if data is None:
        return {"found": False, "erreur": "reponse_non_parseable", "brut": raw[:200]}

    if not data.get("found"):
        return {"found": False}

    x_pct = float(data.get("x_pct", 0.5))
    y_pct = float(data.get("y_pct", 0.5))
    confiance = float(data.get("confiance", 0.5))

    x = max(0, min(int(x_pct * largeur), largeur - 1))
    y = max(0, min(int(y_pct * hauteur), hauteur - 1))

    return {"found": True, "x": x, "y": y, "confiance": confiance}


def _localiser_ollama(image_path, description, largeur, hauteur):
    import requests

    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Tu es un assistant d'analyse d'interface web. "
                    "Tu réponds UNIQUEMENT avec un objet JSON valide. "
                    "Aucun texte avant ni après le JSON. Aucun bloc markdown."
                ),
            },
            {
                "role": "user",
                "content": _prompt(description, largeur, hauteur),
                "images": [_reduire_et_b64(image_path)],
            },
        ],
        "stream": False,
        "think": False,  # désactive le mode chain-of-thought de qwen3
    }
    resp = requests.post(
        "http://localhost:11434/api/chat",
        json=payload,
        timeout=120,
    )
    resp.raise_for_status()
    raw = resp.json().get("message", {}).get("content", "")
    return _parse_resultat(raw, largeur, hauteur)


def _localiser_claude(image_path, description, largeur, hauteur):
    try:
        import anthropic
    except ImportError:
        raise ImportError(
            "Le mode claude nécessite : pip install anthropic\n"
            f"Ou utiliser --llm local (Ollama {OLLAMA_MODEL})."
        )

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=256,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": _lire_b64(image_path),
                    },
                },
                {"type": "text", "text": _prompt(description, largeur, hauteur)},
            ],
        }],
    )
    raw = message.content[0].text
    return _parse_resultat(raw, largeur, hauteur)


def localiser_element(image_path, description, mode_llm="local"):
    """
    Localise un élément par description visuelle dans une capture d'écran.

    Args:
        image_path  : chemin vers le PNG à analyser
        description : description en langage naturel de l'élément à trouver
        mode_llm    : "local" (Ollama qwen3-vl) ou "claude" (API Anthropic)

    Returns:
        {"found": True, "x": int, "y": int, "confiance": float, "modele": str}
        {"found": False, "erreur": str, "modele": str}

    La clé `modele` (v1.3) porte le tag exact résolu au runtime
    (`OLLAMA_MODEL` ou `CLAUDE_MODEL`). Source de vérité pour la
    composition de `diwall_meta.modeles_utilises`.
    """
    largeur, hauteur = _dimensions_png(image_path)

    if mode_llm == "local":
        result = _localiser_ollama(image_path, description, largeur, hauteur)
        result["modele"] = OLLAMA_MODEL
    elif mode_llm == "claude":
        result = _localiser_claude(image_path, description, largeur, hauteur)
        result["modele"] = CLAUDE_MODEL
    else:
        raise ValueError(f"Mode LLM inconnu : {mode_llm!r}. Utiliser 'local' ou 'claude'.")
    return result
