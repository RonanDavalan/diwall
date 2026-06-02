#!/opt/diwall/venv/bin/python3
import argparse
import base64
import getpass
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urlparse


__version__ = "1.3.2"

REFERENCES_DIR = "/opt/diwall/references"
SHOT_SCRIPT = "/opt/diwall/shot.py"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen3-vl:2b"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# Permet d'importer lib/ depuis le même répertoire que watch.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PROMPT_DEFAUT = (
    "Tu reçois deux captures d'écran : la première est la référence (état de référence), "
    "la seconde est l'état actuel. Réponds uniquement en JSON avec les champs suivants : "
    "changement_detecte (booléen), "
    "analyse (string décrivant les différences observées, ou null si aucune), "
    "priorite (string : 'haute' si erreur visible, contenu manquant ou dégradation "
    "fonctionnelle ; 'basse' si changement cosmétique mineur). "
    "Si aucune différence significative, changement_detecte doit être false."
)


def parse_args():
    p = argparse.ArgumentParser(description="Diwall watch.py — surveillance visuelle")
    p.add_argument("--url", help="URL à surveiller")
    p.add_argument("--sauver-reference", dest="sauver_reference", action="store_true",
                   help="Capture et enregistre la référence visuelle")
    p.add_argument("--comparer", action="store_true",
                   help="Compare la capture actuelle avec la référence stockée (LLM sémantique)")
    p.add_argument("--liste", help="Fichier de liste d'URLs (une par ligne, # pour commentaires)")
    p.add_argument("--prompt", default=PROMPT_DEFAUT,
                   help="Prompt LLM pour la comparaison (remplace le prompt par défaut)")
    p.add_argument("--llm", choices=["local", "claude"], default="local",
                   help="Mode LLM : local (Ollama llava) ou claude (API Anthropic)")
    p.add_argument("--ntfy-url", dest="ntfy_url",
                   help="URL ntfy pour les notifications push en cas d'alerte")
    p.add_argument("--timeout", type=int, default=10000,
                   help="Timeout de capture Playwright en ms (défaut : 10000)")
    # ── Lot 9.1 — diff visuel pixel local ─────────────────────────────────────
    p.add_argument("--comparer-pixel", dest="comparer_pixel", default=None,
                   metavar="REF_PNG",
                   help="Mode pixel : compare une capture à une référence PNG locale (lot 9.1)")
    p.add_argument("--capture", default=None, metavar="CAP_PNG",
                   help="Capture à comparer (mode --comparer-pixel). Si absent, --url est requis.")
    p.add_argument("--seuil-bruit", dest="seuil_bruit", type=int, default=5,
                   help="Δ max par canal RGB pour considérer un pixel inchangé (défaut : 5)")
    p.add_argument("--seuil-stable", dest="seuil_stable", type=float, default=0.002,
                   help="Borne haute du verdict 'stable' en fraction (défaut : 0.002)")
    p.add_argument("--seuil-regression", dest="seuil_regression", type=float, default=0.05,
                   help="Borne basse du verdict 'regression' en fraction (défaut : 0.05)")
    p.add_argument("--heatmap", action="store_true",
                   help="Produit une heatmap PNG en plus de l'image de diff")
    p.add_argument("--heatmap-tile", dest="heatmap_tile", type=int, default=16,
                   help="Côté du tile en pixels pour la heatmap (défaut : 16)")
    p.add_argument("--llm-en-complement", dest="llm_en_complement", action="store_true",
                   help="Relance le diff sémantique LLM si verdict pixel != stable")
    p.add_argument("--sortie-json", dest="sortie_json", default=None,
                   help="Redirige le JSON de verdict vers un fichier (défaut : stdout)")
    p.add_argument("--intention", default=None,
                   help="Libellé métier du run, consigné dans le journal d'opérations (v1.4).")
    return p.parse_args()


def slug_url(url):
    parsed = urlparse(url)
    slug = parsed.netloc + parsed.path.rstrip("/")
    if parsed.query:
        slug += "_" + parsed.query
    slug = re.sub(r"[^a-zA-Z0-9._-]", "_", slug)
    return re.sub(r"_+", "_", slug).strip("_")


def repertoire_reference(url):
    d = os.path.join(REFERENCES_DIR, slug_url(url))
    os.makedirs(d, exist_ok=True)
    return d


def capturer(url, sortie, timeout):
    result = subprocess.run(
        [SHOT_SCRIPT, "--url", url, "--output", sortie, "--timeout", str(timeout)],
        capture_output=True, text=True
    )
    data = json.loads(result.stdout) if result.stdout.strip() else {}
    if result.returncode != 0:
        raise RuntimeError(data.get("message", result.stderr.strip()))
    return data


def comparer_ollama(ref_path, actuel_path, prompt):
    import requests

    def lire_b64(path):
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode()

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "images": [lire_b64(ref_path), lire_b64(actuel_path)],
        "stream": False,
        "format": "json",
    }
    resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
    resp.raise_for_status()
    raw = resp.json().get("response", "{}")
    try:
        analyse = json.loads(raw)
    except json.JSONDecodeError:
        changement = "changement" in raw.lower() and "true" in raw.lower()
        analyse = {"changement_detecte": changement, "analyse": raw.strip(), "priorite": "basse"}
    analyse["_modele"] = OLLAMA_MODEL
    return analyse


def comparer_claude(ref_path, actuel_path, prompt):
    raise NotImplementedError("Mode claude API non implémenté (Phase 4+). Utiliser --llm local.")


def notifier_ntfy(ntfy_url, url, analyse, priorite="basse"):
    import requests
    ntfy_priority = "high" if priorite == "haute" else "default"
    try:
        requests.post(
            ntfy_url,
            data=(analyse or "Changement visuel détecté.").encode("utf-8"),
            headers={
                "Title": f"Diwall — changement détecté : {url}",
                "Priority": ntfy_priority,
            },
            timeout=10,
        )
    except Exception:
        pass


def sauver_reference(url, timeout, profil=None):
    rep = repertoire_reference(url)
    sortie = os.path.join(rep, "reference.png")
    horodatage = datetime.now(timezone.utc).astimezone().isoformat()

    if profil is None:
        from lib.profil_operateur import charger_profil
        profil = charger_profil()

    data = capturer(url, sortie, timeout)

    meta = {
        "url": url,
        "horodatage": horodatage,
        "http_status": data.get("http_status"),
        "erreurs_js": data.get("erreurs_js", []),
    }
    with open(os.path.join(rep, "reference.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {
        "succes": True,
        "url": url,
        "reference": sortie,
        "horodatage": horodatage,
        "diwall_meta": _construire_diwall_meta_watch(profil, horodatage, [], url),
    }


def _construire_diwall_meta_watch(profil, horodatage, modeles_appeles, url=None):
    """Bloc diwall_meta pour les sorties de watch.py (symétrique shot.py).

    Si la traçabilité modèles est désactivée dans le profil, la clé
    `modeles_utilises` est omise (§5.4 spec 33_).
    """
    meta = {
        "version_watch": __version__,
        "horodatage_iso": horodatage,
        "hostname_executant": socket.gethostname(),
        "utilisateur_executant": getpass.getuser(),
        "profil_actif": profil.descripteur(),
    }
    if url:
        meta["url_au_moment_capture"] = url
    if not profil.tracabilite_modeles_active:
        return meta

    from lib.modeles import collecter_modele_ollama, collecter_modele_claude
    modeles_utilises = []
    for entree in modeles_appeles:
        tag = entree["_tag"]
        role = entree["role"]
        if entree["mode_llm"] == "local":
            modeles_utilises.append(collecter_modele_ollama(
                tag, role,
                inclure_hash=profil.tracabilite_inclure_hash,
            ))
        else:
            modeles_utilises.append(collecter_modele_claude(tag, role))
    meta["modeles_utilises"] = modeles_utilises
    return meta


def _journaliser_run_watch(result, cible_url, mutatif, intention=None):
    """Consigne un run watch.py dans le journal d'opérations (v1.4). Best-effort."""
    try:
        from lib import journal
    except Exception:
        return
    captures = []
    for cle in ("capture", "reference", "image_diff", "heatmap"):
        c = result.get(cle)
        if c:
            captures.append(c)
    journal.enregistrer_operation(
        outil="watch.py",
        version=__version__,
        cible_url=cible_url or "",
        resultat="succes" if result.get("succes", True) else "echec",
        actions=[],
        diwall_meta=result.get("diwall_meta"),
        intention=intention,
        captures=captures,
        mutatif=mutatif,
    )


def comparer(url, prompt, mode_llm, ntfy_url, timeout, profil=None):
    rep = repertoire_reference(url)
    ref_path = os.path.join(rep, "reference.png")
    horodatage = datetime.now(timezone.utc).astimezone().isoformat()

    if profil is None:
        from lib.profil_operateur import charger_profil
        profil = charger_profil()

    if not os.path.exists(ref_path):
        return {
            "succes": False,
            "url": url,
            "erreur": "reference_absente",
            "message": f"Pas de référence pour {url} — lancer --sauver-reference d'abord.",
            "diwall_meta": _construire_diwall_meta_watch(profil, horodatage, [], url),
        }

    actuel_path = os.path.join("/tmp/diwall", f"watch_{slug_url(url)}_{int(time.time())}.png")
    data = capturer(url, actuel_path, timeout)

    modeles_appeles = []
    if mode_llm == "local":
        analyse = comparer_ollama(ref_path, actuel_path, prompt)
        modeles_appeles.append({
            "_tag": analyse.get("_modele", OLLAMA_MODEL),
            "mode_llm": "local",
            "role": "comparaison_semantique",
        })
    else:
        analyse = comparer_claude(ref_path, actuel_path, prompt)
        modeles_appeles.append({
            "_tag": CLAUDE_MODEL,
            "mode_llm": "claude",
            "role": "comparaison_semantique",
        })

    changement = analyse.get("changement_detecte", False)
    analyse_llm = analyse.get("analyse")
    priorite = analyse.get("priorite", "basse")

    if changement and ntfy_url:
        notifier_ntfy(ntfy_url, url, analyse_llm, priorite)

    return {
        "succes": True,
        "url": url,
        "changement_detecte": changement,
        "priorite": priorite,
        "capture": actuel_path,
        "reference": ref_path,
        "analyse_llm": analyse_llm,
        "http_status": data.get("http_status"),
        "erreurs_js": data.get("erreurs_js", []),
        "horodatage": horodatage,
        "diwall_meta": _construire_diwall_meta_watch(
            profil, horodatage, modeles_appeles, url,
        ),
    }


# ── Lot 9.1 — Diff visuel pixel local ─────────────────────────────────────────

def _charger_image_rgb(chemin):
    """Charge une image PNG en mode RGB. Lève FileNotFoundError ou OSError."""
    from PIL import Image
    img = Image.open(chemin)
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def _calcul_diff_numpy(ref_img, cap_img, seuil_bruit):
    """Calcul vectorisé du diff via NumPy.

    Retourne (pixels_modifies, pixels_totaux, delta_max_2d, modifie_mask_2d)
    où delta_max_2d est utilisé pour la heatmap (intensité par tile) et
    modifie_mask_2d pour l'image diff.
    """
    import numpy as np
    a = np.asarray(ref_img, dtype=np.int16)
    b = np.asarray(cap_img, dtype=np.int16)
    delta = np.abs(a - b)
    delta_max = delta.max(axis=2).astype(np.uint8)  # H × W
    modifie = delta_max >= seuil_bruit
    pixels_modifies = int(modifie.sum())
    pixels_totaux = int(modifie.size)
    return pixels_modifies, pixels_totaux, delta_max, modifie


def _calcul_diff_pillow(ref_img, cap_img, seuil_bruit):
    """Calcul du diff en Pillow pur (fallback sans NumPy). Lent mais sans dépendance.

    Retourne (pixels_modifies, pixels_totaux, delta_max_flat, modifie_mask_flat)
    où les masks sont des listes plates de longueur W*H (ordre row-major).
    """
    from PIL import ImageChops
    diff = ImageChops.difference(ref_img, cap_img)
    pixels = list(diff.getdata())  # list de tuples (r, g, b)
    delta_max = [max(px) for px in pixels]
    modifie = [d >= seuil_bruit for d in delta_max]
    pixels_modifies = sum(1 for m in modifie if m)
    pixels_totaux = len(modifie)
    return pixels_modifies, pixels_totaux, delta_max, modifie


def _produire_image_diff_numpy(ref_img, modifie_mask, chemin_sortie):
    """Construit l'image diff via NumPy : pixels inchangés en gris 50 %,
    pixels modifiés en rouge saturé. modifie_mask est un array 2D booléen H×W."""
    import numpy as np
    from PIL import Image
    a = np.asarray(ref_img, dtype=np.uint8)  # H × W × 3
    # Fond : luminance ramenée à 50 % d'intensité (gris désaturé).
    gris = a.mean(axis=2).astype(np.uint8)
    fond = np.stack([gris // 2 + 64] * 3, axis=2)  # gris medium clair
    # Pixels modifiés : rouge saturé
    rouge = np.zeros_like(a)
    rouge[..., 0] = 255
    sortie = np.where(modifie_mask[..., None], rouge, fond).astype(np.uint8)
    Image.fromarray(sortie, mode="RGB").save(chemin_sortie, format="PNG")


def _produire_image_diff_pillow(ref_img, modifie_mask, chemin_sortie):
    """Variante Pillow pur. modifie_mask est une liste plate de longueur W*H."""
    from PIL import Image
    w, h = ref_img.size
    src = list(ref_img.getdata())
    sortie_pixels = []
    for i, (r, g, b) in enumerate(src):
        if modifie_mask[i]:
            sortie_pixels.append((255, 0, 0))
        else:
            lum = (r + g + b) // 3
            v = lum // 2 + 64
            sortie_pixels.append((v, v, v))
    img = Image.new("RGB", (w, h))
    img.putdata(sortie_pixels)
    img.save(chemin_sortie, format="PNG")


def _produire_heatmap_numpy(delta_max_2d, tile_size, chemin_sortie):
    """Heatmap NumPy : Δ moyen par tile, gradient noir → rouge saturé."""
    import numpy as np
    from PIL import Image
    h, w = delta_max_2d.shape
    nh = (h + tile_size - 1) // tile_size
    nw = (w + tile_size - 1) // tile_size
    # Pad pour multiple de tile_size
    padded = np.zeros((nh * tile_size, nw * tile_size), dtype=np.float32)
    padded[:h, :w] = delta_max_2d
    # Reshape pour moyenne par tile
    tiled = padded.reshape(nh, tile_size, nw, tile_size).mean(axis=(1, 3))
    # Intensité : delta_moyen 0-255 → rouge 0-255
    intensite = tiled.clip(0, 255).astype(np.uint8)
    # Expansion en bloc plein de la taille de l'image source
    expanse = np.repeat(np.repeat(intensite, tile_size, axis=0), tile_size, axis=1)[:h, :w]
    sortie = np.zeros((h, w, 3), dtype=np.uint8)
    sortie[..., 0] = expanse  # canal R seul
    Image.fromarray(sortie, mode="RGB").save(chemin_sortie, format="PNG")


def _produire_heatmap_pillow(delta_max_flat, largeur, hauteur, tile_size, chemin_sortie):
    """Heatmap Pillow pur. delta_max_flat = liste plate de longueur W*H."""
    from PIL import Image
    nh = (hauteur + tile_size - 1) // tile_size
    nw = (largeur + tile_size - 1) // tile_size
    # Calcul moyen par tile
    intensites = [[0.0] * nw for _ in range(nh)]
    compteurs = [[0] * nw for _ in range(nh)]
    for i, d in enumerate(delta_max_flat):
        y, x = divmod(i, largeur)
        ty, tx = y // tile_size, x // tile_size
        intensites[ty][tx] += d
        compteurs[ty][tx] += 1
    pixels = []
    for y in range(hauteur):
        ty = y // tile_size
        for x in range(largeur):
            tx = x // tile_size
            c = compteurs[ty][tx]
            moyenne = int(intensites[ty][tx] / c) if c else 0
            v = max(0, min(255, moyenne))
            pixels.append((v, 0, 0))
    img = Image.new("RGB", (largeur, hauteur))
    img.putdata(pixels)
    img.save(chemin_sortie, format="PNG")


def _verdict_pixel(taux_diff, seuil_stable, seuil_regression):
    if taux_diff < seuil_stable:
        return "stable"
    if taux_diff < seuil_regression:
        return "drift"
    return "regression"


def comparer_pixel(args):
    """Orchestrateur du mode --comparer-pixel.

    Retourne (resultat_dict, exit_code) sans imprimer.
    """
    t0 = time.time()
    horodatage = datetime.now(timezone.utc).astimezone().isoformat()
    from lib.profil_operateur import charger_profil
    profil = charger_profil()
    modeles_appeles = []
    ref_path = args.comparer_pixel
    cap_path = args.capture

    def _avec_meta(res):
        res["diwall_meta"] = _construire_diwall_meta_watch(
            profil, horodatage, modeles_appeles, args.url,
        )
        return res

    # ── Préconditions I/O ─────────────────────────────────────────────────────
    if not os.path.isfile(ref_path):
        return _avec_meta({
            "succes": False,
            "type_comparaison": "pixel",
            "erreur": "reference_introuvable",
            "message": f"Référence introuvable : {ref_path}",
        }), 3

    # Si --capture absent, capturer depuis --url
    if not cap_path:
        if not args.url:
            return _avec_meta({
                "succes": False,
                "type_comparaison": "pixel",
                "erreur": "capture_manquante",
                "message": "Fournir --capture <chemin> ou --url pour générer une capture.",
            }), 3
        try:
            cap_path = os.path.join("/tmp/diwall",
                                     f"watch_pixel_{slug_url(args.url)}_{int(time.time())}.png")
            capturer(args.url, cap_path, args.timeout)
        except Exception as e:
            return _avec_meta({
                "succes": False,
                "type_comparaison": "pixel",
                "erreur": "capture_echec",
                "message": str(e),
            }), 3

    if not os.path.isfile(cap_path):
        return _avec_meta({
            "succes": False,
            "type_comparaison": "pixel",
            "erreur": "capture_introuvable",
            "message": f"Capture introuvable : {cap_path}",
        }), 3

    # ── Chargement images ─────────────────────────────────────────────────────
    try:
        ref_img = _charger_image_rgb(ref_path)
        cap_img = _charger_image_rgb(cap_path)
    except Exception as e:
        return _avec_meta({
            "succes": False,
            "type_comparaison": "pixel",
            "erreur": "image_illisible",
            "message": str(e),
        }), 3

    # ── Précondition viewport : refus strict (pas de resize) ──────────────────
    if ref_img.size != cap_img.size:
        return _avec_meta({
            "succes": False,
            "type_comparaison": "pixel",
            "verdict": "viewport_mismatch",
            "erreur": (
                f"Dimensions divergentes : référence {ref_img.size[0]}×{ref_img.size[1]}, "
                f"capture {cap_img.size[0]}×{cap_img.size[1]}. "
                "Le redimensionnement automatique est désactivé (introduit du bruit "
                "d'interpolation). Régénérer la référence avec le viewport courant."
            ),
            "dimensions_reference": list(ref_img.size),
            "dimensions_capture": list(cap_img.size),
            "reference": ref_path,
            "capture": cap_path,
        }), 2

    largeur, hauteur = ref_img.size

    # ── Calcul du delta ───────────────────────────────────────────────────────
    try:
        import numpy as np  # noqa: F401
        moteur = "numpy"
        pixels_modifies, pixels_totaux, delta_max, modifie_mask = (
            _calcul_diff_numpy(ref_img, cap_img, args.seuil_bruit)
        )
    except ImportError:
        moteur = "pillow"
        pixels_modifies, pixels_totaux, delta_max, modifie_mask = (
            _calcul_diff_pillow(ref_img, cap_img, args.seuil_bruit)
        )

    taux_diff = pixels_modifies / pixels_totaux if pixels_totaux else 0.0
    verdict = _verdict_pixel(taux_diff, args.seuil_stable, args.seuil_regression)

    # ── Production des artefacts visuels ──────────────────────────────────────
    base_cap = os.path.basename(cap_path).rsplit(".", 1)[0]
    dossier = os.path.dirname(cap_path) or "/tmp/diwall"
    image_diff_path = None
    heatmap_path = None

    if verdict != "stable":
        image_diff_path = os.path.join(dossier, f"diff_{base_cap}.png")
        if moteur == "numpy":
            _produire_image_diff_numpy(ref_img, modifie_mask, image_diff_path)
        else:
            _produire_image_diff_pillow(ref_img, modifie_mask, image_diff_path)

    if args.heatmap and verdict != "stable":
        heatmap_path = os.path.join(dossier, f"heatmap_{base_cap}.png")
        if moteur == "numpy":
            _produire_heatmap_numpy(delta_max, args.heatmap_tile, heatmap_path)
        else:
            _produire_heatmap_pillow(delta_max, largeur, hauteur,
                                      args.heatmap_tile, heatmap_path)

    # ── Complément LLM optionnel ──────────────────────────────────────────────
    analyse_llm = None
    if args.llm_en_complement and verdict != "stable":
        try:
            analyse = comparer_ollama(ref_path, cap_path, args.prompt)
            analyse_llm = analyse.get("analyse")
            modeles_appeles.append({
                "_tag": analyse.get("_modele", OLLAMA_MODEL),
                "mode_llm": "local",
                "role": "comparaison_semantique",
            })
        except Exception as e:
            analyse_llm = f"(complément LLM indisponible : {e})"

    # ── JSON de sortie ────────────────────────────────────────────────────────
    resultat = {
        "succes": True,
        "type_comparaison": "pixel",
        "verdict": verdict,
        "taux_diff": round(taux_diff, 6),
        "pixels_modifies": pixels_modifies,
        "pixels_totaux": pixels_totaux,
        "seuils": {
            "bruit": args.seuil_bruit,
            "stable": args.seuil_stable,
            "regression": args.seuil_regression,
        },
        "reference": ref_path,
        "capture": cap_path,
        "image_diff": image_diff_path,
        "heatmap": heatmap_path,
        "duree_ms": int((time.time() - t0) * 1000),
        "moteur": moteur,
    }
    if analyse_llm is not None:
        resultat["analyse_llm"] = analyse_llm

    exit_code = 1 if verdict == "regression" else 0
    return _avec_meta(resultat), exit_code


def main():
    args = parse_args()

    # ── Mode --comparer-pixel (lot 9.1) ───────────────────────────────────────
    if args.comparer_pixel:
        resultat, exit_code = comparer_pixel(args)
        _journaliser_run_watch(resultat, args.url or args.comparer_pixel,
                               mutatif=False, intention=args.intention)
        payload = json.dumps(resultat, ensure_ascii=False)
        if args.sortie_json:
            with open(args.sortie_json, "w", encoding="utf-8") as f:
                f.write(payload)
        else:
            print(payload)
        sys.exit(exit_code)

    if args.liste:
        with open(args.liste, encoding="utf-8") as f:
            urls = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        resultats = []
        for url in urls:
            try:
                r = comparer(url, args.prompt, args.llm, args.ntfy_url, args.timeout)
            except Exception as e:
                r = {"succes": False, "url": url, "erreur": str(e)}
            _journaliser_run_watch(r, url, mutatif=False, intention=args.intention)
            resultats.append(r)
        print(json.dumps(resultats, ensure_ascii=False))
        return

    if not args.url:
        print(json.dumps({
            "succes": False,
            "erreur": "argument_manquant",
            "message": "Fournir --url ou --liste",
        }))
        sys.exit(1)

    if args.sauver_reference:
        result = sauver_reference(args.url, args.timeout)
        _journaliser_run_watch(result, args.url, mutatif=True,
                               intention=args.intention)
    elif args.comparer:
        result = comparer(args.url, args.prompt, args.llm, args.ntfy_url, args.timeout)
        _journaliser_run_watch(result, args.url, mutatif=False,
                               intention=args.intention)
    else:
        print(json.dumps({
            "succes": False,
            "erreur": "mode_requis",
            "message": "Utiliser --sauver-reference ou --comparer",
        }))
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
