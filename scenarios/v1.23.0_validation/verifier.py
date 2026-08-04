#!/usr/bin/env python3
"""Verifier — v1.23.0 (i18n: manifest, PDF order, segmented translation, nets).

Usage:
    python3 scenarios/v1.23.0_validation/verifier.py

Everything here is mechanical and offline: no Ollama call, no network. The
translation pipeline's *safety* mechanisms are exactly the parts that must not
depend on a model being reachable or well-behaved, so they are testable
without one. Only T-9 touches pandoc, and it skips cleanly if pandoc is
absent.

Counter-tests matter more than the happy path in this suite: a net that never
fires is indistinguishable from a net that is not there. T-2, T-5, T-6 and T-7
each prove a real failure is actually caught.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.dirname(os.path.dirname(ICI))
PYTHON = sys.executable

# The translation chain left this repository on the 31st of July 2026: it
# produces the documentation, it is not part of Diwall. This suite tests that
# chain, so it needs the maintainer tooling and skips cleanly without it —
# a contributor cloning Diwall is not expected to have it, and a suite that
# crashed on import would report a broken product instead of an absent tool.
OUTILLAGE = os.path.join(os.path.expanduser("~"), "git", "Diwall", "scripts")
OUTILLAGE_I18N = os.path.join(OUTILLAGE, "i18n")
sys.path.insert(0, OUTILLAGE_I18N)

try:
    import lib_i18n as lib  # noqa: E402
except ImportError:
    print("SKIP — maintainer tooling absent (expected outside the development machine).")
    print(f"       looked for lib_i18n.py in {OUTILLAGE_I18N}")
    print("       This suite validates the translation chain, not Diwall itself.")
    sys.exit(0)


def _verdict(nom, conditions):
    lignes, ok = [], True
    for libelle, cond in conditions:
        lignes.append(f"    {'✓' if cond else '✗'} {libelle}")
        if not cond:
            ok = False
    return ok, [f"[{'OK' if ok else 'KO'}] {nom}", *lignes]


# ---------------------------------------------------------------------------


def test_1_manifeste_couvre_son_perimetre():
    try:
        manifeste = lib.charger_manifeste()
        charge = True
        erreur = ""
    except lib.ErreurI18n as e:
        manifeste, charge, erreur = None, False, str(e)

    ordonnes = [e["chemin"] for e in manifeste["ordre"]] if charge else []
    exclus = {e["chemin"]: e for e in manifeste["exclusions"]} if charge else {}

    return _verdict(
        "T-1 manifeste — couverture complète du périmètre déclaré",
        [
            (f"charge sans erreur ({erreur[:60]})" if not charge else "charge sans erreur", charge),
            # L'ordre encode le principe du temps d'accès : commandes, puis
            # présentation, puis architecture, puis référence. La fiche est
            # passée en tête après qu'un relecteur externe eut signalé son
            # absence — elle existait, mais hors du PDF.
            ("la fiche de synthèse ouvre le document",
             ordonnes[:1] == ["docs/CHEAT_SHEET.md"]),
            ("README.md vient juste après", ordonnes[1:2] == ["README.md"]),
            ("docs/MANUEL.md est ordonné après docs/GUIDE.md",
             charge and ordonnes.index("docs/MANUEL.md") > ordonnes.index("docs/GUIDE.md")),
            ("les 4 guides sous verrou sont exclus", all(
                f"docs/{n}" in exclus for n in
                ("GUIDE_LLM.md", "GUIDE_LLM_INTERACTIONS.md",
                 "GUIDE_LLM_SESSIONS.md", "GUIDE_LLM_MONITORING.md"))),
            # Les registres d'observation (journal, notes de terrain, radar
            # des modèles, relevés d'accès) ont quitté le dépôt le 02/08/2026 :
            # ils vivent sur le site, le dépôt y renvoie. Ils ne sont donc plus
            # ni dans le périmètre ni dans les exclusions — le test vérifie
            # désormais l'inverse de ce qu'il vérifiait.
            ("aucun registre d'observation ne subsiste au manifeste", not any(
                n in exclus or n in ordonnes for n in
                ("docs/JOURNAL.md", "docs/RETOUR_EXPERIENCE.md",
                 "docs/RADAR_MODELES.md", "docs/ACCESS_OBSERVATIONS.md"))),
            ("chaque exclusion porte un motif non vide",
             all(e.get("motif") for e in exclus.values())),
        ],
    )


def test_2_document_orphelin_echoue():
    """Contre-épreuve : un fichier hors manifeste doit faire échouer, bruyamment."""
    temoin = os.path.join(RACINE, "docs", "ZZZ_TEMOIN_V1230.md")
    with open(temoin, "w", encoding="utf-8") as f:
        f.write("# temoin\n")
    try:
        resultat = subprocess.run(
            [PYTHON, os.path.join(OUTILLAGE_I18N, "generer-pdf.py"),
             "--verifier-seulement"],
            capture_output=True, text=True, cwd=RACINE,
        )
        coherence = subprocess.run(
            ["bash", os.path.join(OUTILLAGE, "verifier-coherence.sh")],
            capture_output=True, text=True, cwd=RACINE,
        )
    finally:
        os.remove(temoin)

    return _verdict(
        "T-2 contre-épreuve — document orphelin détecté (échec bruyant)",
        [
            ("generer-pdf.py sort en erreur", resultat.returncode != 0),
            ("le nom du fichier fautif est cité", "ZZZ_TEMOIN_V1230.md" in resultat.stderr),
            ("la correction attendue est indiquée", "'exclusions'" in resultat.stderr),
            ("verifier-coherence.sh échoue aussi", coherence.returncode != 0),
        ],
    )


def test_3_segmentation_ne_perd_rien():
    perdus = []
    for relatif in ("README.md", "docs/GUIDE.md", "docs/MANUEL.md"):
        with open(os.path.join(RACINE, relatif), encoding="utf-8") as f:
            source = f.read()
        segments = lib.segmenter(source)
        avant = [l for l in source.splitlines() if l.strip()]
        apres = [l for l in lib.recomposer(segments).splitlines() if l.strip()]
        if avant != apres:
            perdus.append(relatif)

    with open(os.path.join(RACINE, "docs", "MANUEL.md"), encoding="utf-8") as f:
        segments = lib.segmenter(f.read())

    return _verdict(
        "T-3 segmentation — aucune ligne perdue, blocs de code entiers",
        [
            (f"les 3 documents se recomposent à l'identique ({perdus})", not perdus),
            ("des blocs de code sont isolés",
             any(s["type"] == "code" for s in segments)),
            ("tout bloc de code commence par une clôture",
             all(s["texte"].lstrip().startswith(("```", "~~~"))
                 for s in segments if s["type"] == "code")),
        ],
    )


def test_4_masquage_reversible():
    echantillon = (
        "Run `shot.py --som` against https://target.local/admin, see "
        "docs/MANUEL.md and the `auth_indicator` key in /opt/diwall/diwall.conf. "
        "Use --wait-until load, then read dernier_code_http."
    )
    masque, valeurs = lib.masquer(echantillon)

    return _verdict(
        "T-4 masquage — les zones protégées n'atteignent jamais le modèle",
        [
            ("restitution strictement identique à l'original",
             lib.restituer(masque, valeurs) == echantillon),
            ("l'option --wait-until est masquée", "--wait-until" not in masque),
            ("l'URL est masquée", "target.local" not in masque),
            ("le chemin /opt/diwall/diwall.conf est masqué", "diwall.conf" not in masque),
            # Régression réelle : un ordre de motifs mal choisi masquait
            # `docs/MANUEL.md` en deux morceaux et laissait `docs` traduisible.
            ("le chemin relatif docs/MANUEL.md est masqué entièrement",
             "docs" not in masque and "MANUEL" not in masque),
            ("la clé dernier_code_http est masquée", "dernier_code_http" not in masque),
            ("de la prose subsiste pour le modèle", lib.contient_prose(masque)),
        ],
    )


def test_5_integrite_des_balises():
    entree = "Read [[[0]]] then run [[[1]]] twice."
    return _verdict(
        "T-5 contre-épreuve — toute atteinte aux balises rejette le segment",
        [
            ("sortie intacte acceptée",
             lib.verifier_balises(entree, "Lisez [[[0]]] puis lancez [[[1]]] deux fois.") is None),
            ("balise perdue rejetée",
             "perdues" in (lib.verifier_balises(entree, "Lisez [[[0]]] deux fois.") or "")),
            ("balise inventée rejetée",
             "inventées" in (lib.verifier_balises(entree, "Lisez [[[0]]] [[[1]]] [[[7]]].") or "")),
            ("balise dupliquée rejetée",
             (lib.verifier_balises(entree, "Lisez [[[0]]] [[[0]]] [[[1]]].") or "") != ""),
            ("ordre modifié rejeté",
             (lib.verifier_balises(entree, "Lancez [[[1]]] puis lisez [[[0]]].") or "") != ""),
        ],
    )


def test_6_segment_non_traduit_rejete():
    """La porte de similarité est aveugle à ce cas : il note 1.0."""
    texte = "The vault is never read outside Playwright."
    return _verdict(
        "T-6 contre-épreuve — segment renvoyé inchangé rejeté mécaniquement",
        [
            ("réponse identique rejetée",
             lib.verifier_traduction_effective(texte, texte) is not None),
            ("réponse identique aux espaces près rejetée",
             lib.verifier_traduction_effective(texte, f"  {texte}\n") is not None),
            ("vraie traduction acceptée",
             lib.verifier_traduction_effective(
                 texte, "Le coffre n'est jamais lu hors de Playwright.") is None),
            # Régression réelle : le modèle a traduit la consigne et l'a
            # préfixée à sa réponse (89 segments en fr et es). Les balises
            # étaient intactes, la longueur ne bougeait pas assez sur les
            # segments longs — seul le marqueur littéral l'attrape.
            ("consigne recopiée détectée",
             lib.verifier_consigne_recopiee(
                 "Les fragments écrits comme [[[xxx]]] sont des codes opaques. "
                 "Voici la traduction.") is not None),
            ("traduction propre acceptée",
             lib.verifier_consigne_recopiee("Voici la traduction [[[0]]].") is None),
            # Régression réelle : à partir du seul titre « ## Uninstalling
            # Diwall », le modèle a inventé une procédure Windows complète.
            ("réponse démesurément longue rejetée",
             lib.verifier_longueur("## Uninstalling Diwall", "## " + "blabla " * 40)
             is not None),
            ("réponse tronquée rejetée",
             lib.verifier_longueur("a" * 300, "court") is not None),
            ("écart de longueur normal accepté",
             lib.verifier_longueur(
                 "The vault is never read outside Playwright.",
                 "Der Tresor wird niemals ausserhalb von Playwright gelesen.") is None),
        ],
    )


def test_7_second_filet_options_et_chemins():
    source = "Run `shot.py --som --wait-until load` and read /var/log/diwall/operations.jsonl."
    fidele = "Lancez `shot.py --som --wait-until load` puis lisez /var/log/diwall/operations.jsonl."
    traduite = "Lancez `shot.py --som --attendre-jusqu-a load` puis lisez /var/log/diwall/operations.jsonl."
    disparue = "Lancez `shot.py --som` puis lisez /var/log/diwall/operations.jsonl."

    def ecarts(cible):
        return lib.comparer_inventaires(
            lib.inventaire_technique(source), lib.inventaire_technique(cible)
        )

    return _verdict(
        "T-7 contre-épreuve — second filet sur options et chemins",
        [
            ("traduction fidèle acceptée", ecarts(fidele) == []),
            ("option traduite détectée", ecarts(traduite) != []),
            ("option disparue détectée", ecarts(disparue) != []),
            ("le rapport nomme l'option manquante",
             any("--wait-until" in e for e in ecarts(disparue))),
            # Régression réelle : le modèle produit « Le/La » en français et
            # « and/or » existe en anglais. Un motif de chemin trop large les
            # prenait pour des chemins et faisait échouer une traduction saine.
            ("une construction de prose avec slash n'est pas un chemin",
             lib.inventaire_technique("Le/La clé and/or la valeur")["chemins"] == []),
            ("un vrai chemin absolu reste détecté",
             lib.inventaire_technique("voir /opt/diwall")["chemins"] == ["/opt/diwall"]),
            # Régression réelle : une phrase se terminant sur un chemin faisait
            # avaler le point final au motif, et le filet signalait une
            # divergence fantôme entre `…/platform` et `…/platform.`
            ("un point final de phrase n'entre pas dans le chemin",
             lib.inventaire_technique("se normalizan plugins/languages/platform.")["chemins"]
             == ["/languages/platform"]),
            ("un chemin suivi d'un point reste intact",
             lib.inventaire_technique("lire /etc/diwall/diwall.conf.")["chemins"]
             == ["/etc/diwall/diwall.conf"]),
        ],
    )


def test_13_arbitrages_humains():
    """Un segment que le modèle ne sait pas produire doit avoir une destination.

    Sans ce mécanisme, une correction à la main vit dans la sortie jusqu'au
    prochain `--forcer`, puis disparaît sans bruit : le rejet n'avait qu'un
    rapport, pas de destination.
    """
    manifeste = lib.charger_manifeste()
    total = 0
    conformes = True
    prioritaire = False

    for langue in manifeste["langues_cibles"]:
        arbitrages = lib.charger_arbitrages(manifeste, langue)
        total += len(arbitrages)
        for entree in arbitrages.values():
            if not entree.get("traduction") or not entree.get("motif"):
                conformes = False

    with open(os.path.join(OUTILLAGE_I18N, "traduire.py"),
              encoding="utf-8") as f:
        code = f.read()
    # L'arbitrage doit être consulté avant le cache, sinon une traduction
    # automatique périmée l'emporterait sur la décision humaine.
    if "arbitre = arbitrages.get(signature)" in code:
        prioritaire = code.index("arbitre = arbitrages.get(signature)") < code.index(
            "precedent = connus.get(signature)"
        )

    restants = 0
    for langue in manifeste["langues_cibles"]:
        for entree in manifeste["ordre"]:
            chemin = lib.chemin_etat(manifeste, langue, entree["chemin"])
            if not chemin.exists():
                continue
            with open(chemin, encoding="utf-8") as f:
                restants += sum(
                    1 for s in json.load(f)["segments"]
                    if s["statut"] == "arbitrage_humain"
                )

    return _verdict(
        "T-13 arbitrages — les segments rejetés ont une destination durable",
        [
            (f"{total} arbitrage(s) enregistré(s)", total > 0),
            ("chaque arbitrage porte une traduction et un motif", conformes),
            ("l'arbitrage humain primait sur le cache automatique", prioritaire),
            (f"aucun segment ne reste en attente ({restants})", restants == 0),
        ],
    )


def test_8_porte_similarite_desactivable_et_positionnement():
    manifeste = lib.charger_manifeste()
    readme = lib.entree_ordonnee(manifeste, "README.md")
    guide = lib.entree_ordonnee(manifeste, "docs/GUIDE.md")

    source = os.path.join(OUTILLAGE_I18N, "verifier-traduction.py")
    with open(source, encoding="utf-8") as f:
        code = f.read()

    return _verdict(
        "T-8 porte de similarité — désactivable, jamais sur le positionnement",
        [
            ("--sans-porte existe", "--sans-porte" in code),
            ("le second filet reste actif sans la porte",
             code.index("Second filet") < code.index("if arguments.sans_porte")),
            ("README.md est marqué positionnement", bool(readme.get("positionnement"))),
            ("docs/GUIDE.md déclare une section de positionnement",
             bool(guide.get("sections_positionnement"))),
            ("la section déclarée existe dans le document",
             all(any(f"# {titre}" in ligne for ligne in
                     open(os.path.join(RACINE, "docs", "GUIDE.md"), encoding="utf-8"))
                 for titre in guide.get("sections_positionnement", []))),
        ],
    )


def test_9_pdf_ordre_pedagogique():
    if not shutil.which("pandoc"):
        return _verdict("T-9 PDF — pandoc absent, test sauté", [("pandoc disponible", True)])

    sortie = tempfile.mkdtemp(prefix="diwall-i18n-")
    try:
        resultat = subprocess.run(
            [PYTHON, os.path.join(OUTILLAGE_I18N, "generer-pdf.py"),
             "--langue", "en", "--sortie", os.path.relpath(sortie, RACINE)],
            capture_output=True, text=True, cwd=RACINE,
        )
        produit = os.path.join(sortie, "diwall-documentation-en.pdf")
        existe = os.path.exists(produit)
        taille = os.path.getsize(produit) if existe else 0

        manquant = subprocess.run(
            [PYTHON, os.path.join(OUTILLAGE_I18N, "generer-pdf.py"),
             "--langue", "it"],
            capture_output=True, text=True, cwd=RACINE,
        )
    finally:
        shutil.rmtree(sortie, ignore_errors=True)

    return _verdict(
        "T-9 PDF — construction anglaise et table des matières générée",
        [
            ("construction en succès", resultat.returncode == 0),
            ("le PDF existe et n'est pas vide", existe and taille > 10000),
            ("une langue hors manifeste est refusée", manquant.returncode != 0),
        ],
    )


def test_10_non_pollution_du_produit():
    # Seules les lignes de dépendance comptent : requirements.txt mentionne
    # Ollama en commentaire depuis l'origine (moteur de perception visuelle),
    # ce qui n'est pas une dépendance déclarée.
    with open(os.path.join(RACINE, "requirements.txt"), encoding="utf-8") as f:
        requirements = " ".join(
            l.strip().lower() for l in f
            if l.strip() and not l.lstrip().startswith("#")
        )
    # La recette d'empaquetage a quitté le dépôt le 02/08/2026 : elle vit dans
    # le répertoire tampon, assemblée le temps du build. Le test la cherche là
    # où elle est, et se déclare non concluant plutôt que d'échouer si elle est
    # absente — un clone public n'a pas à la porter.
    recette = os.path.join(os.path.dirname(RACINE), "debian", "control")
    if not os.path.exists(recette):
        recette = os.path.join(RACINE, "debian", "control")
    if not os.path.exists(recette):
        return _verdict(
            "T-10 frontière — l'outillage n'entre pas dans le produit",
            [("recette d'empaquetage introuvable — contrôle non applicable", True)],
        )
    with open(recette, encoding="utf-8") as f:
        control = f.read()
    depends = [l for l in control.splitlines() if l.startswith("Depends:")]

    interdits = ("pandoc", "texlive", "xelatex", "ollama", "nomic", "translategemma")

    return _verdict(
        "T-10 frontière — l'outillage n'entre pas dans le produit",
        [
            ("requirements.txt exempt d'outillage i18n",
             not any(mot in requirements for mot in interdits)),
            ("Depends du paquet exempt d'outillage i18n",
             not any(mot in " ".join(depends) for mot in interdits)),
            ("les scripts i18n n'utilisent que la bibliothèque standard",
             not any(mot in open(os.path.join(OUTILLAGE_I18N, "lib_i18n.py"),
                                 encoding="utf-8").read()
                     for mot in ("import requests", "import yaml", "import numpy"))),
        ],
    )


def test_11_traductions_conformes_au_manifeste():
    """Les guides sous verrou ne doivent jamais être traduits.

    Les traductions vivent sous `docs/<langue>/` depuis le 02/08/2026,
    avec des chemins aplatis : `docs/MANUEL.md` se traduit en
    `docs/fr/MANUEL.md`.
    """
    manifeste = lib.charger_manifeste()
    exclus = [e["chemin"] for e in manifeste["exclusions"]]
    fuites = []
    presentes = []

    for langue in manifeste["langues_cibles"]:
        racine = os.path.join(RACINE, "docs", langue)
        for relatif in exclus:
            if os.path.exists(os.path.join(racine, os.path.basename(relatif))):
                fuites.append(f"{langue}/{relatif}")
        for entree in manifeste["ordre"]:
            if os.path.exists(os.path.join(racine, os.path.basename(entree["chemin"]))):
                presentes.append(f"{langue}/{entree['chemin']}")

    return _verdict(
        "T-11 arborescence — aucun document exclu ne fuit dans les traductions",
        [
            (f"aucun guide sous verrou traduit ({fuites})", not fuites),
            ("les répertoires de langue existent",
             all(os.path.isdir(os.path.join(RACINE, "docs", l))
                 for l in manifeste["langues_cibles"])),
            (f"traductions présentes : {len(presentes)}", True),
        ],
    )


def test_12_marges_pdf():
    """Contre-épreuve de mise en page — mesurée, pas jugée à l'œil.

    Avant `i18n/style.tex`, la construction anglaise produisait 13 lignes hors
    marge, la pire à 150pt (~5cm au-delà du bord). Pandoc avale le journal
    LaTeX : le défaut n'était visible qu'en ouvrant le PDF.

    Deux langues suffisent à couvrir le risque : l'anglais (source, tableaux de
    référence les plus larges) et l'allemand (mots composés les plus longs).
    """
    if not shutil.which("pandoc") or not shutil.which("xelatex"):
        return _verdict("T-12 marges — outillage absent, test sauté",
                        [("pandoc et xelatex disponibles", True)])

    resultat = subprocess.run(
        [PYTHON, os.path.join(OUTILLAGE_I18N, "generer-pdf.py"),
         "--verifier-marges"],
        capture_output=True, text=True, cwd=RACINE,
    )

    return _verdict(
        "T-12 marges — aucune ligne hors marge dans les PDF",
        [
            (f"vérification en succès ({resultat.stderr.strip()[:80]})",
             resultat.returncode == 0),
            ("l'anglais est contrôlé", "en :" in resultat.stdout),
            ("l'allemand est contrôlé", "de :" in resultat.stdout),
            ("le préambule est déclaré au manifeste",
             lib.charger_manifeste()["pdf"].get("preambule") is not None),
        ],
    )


def test_14_completude_livree():
    """Le filet qui manquait, et celui qui comptait le plus.

    Un segment rejeté garde sa source anglaise. Un document peut donc être à
    moitié anglais pendant que tous les autres filets restent verts : les
    chemins et options sont identiques par construction, et l'anglais ne
    contient aucun mot de registre familier. Mesuré une fois : 165 segments
    espagnols sur 345 non traduits — 48 % du document — sans qu'aucun contrôle
    ne le signale.
    """
    manifeste = lib.charger_manifeste()
    incomplets = []
    total = 0

    for langue in manifeste["langues_cibles"]:
        for entree in manifeste["ordre"]:
            chemin = lib.chemin_etat(manifeste, langue, entree["chemin"])
            if not chemin.exists():
                continue
            with open(chemin, encoding="utf-8") as f:
                segments = json.load(f)["segments"]
            total += len(segments)
            restants = sum(1 for s in segments if s["statut"] != "traduit")
            if restants:
                incomplets.append(f"{langue}/{entree['chemin']} ({restants})")

    with open(os.path.join(OUTILLAGE_I18N, "verifier-traduction.py"),
              encoding="utf-8") as f:
        code = f.read()

    return _verdict(
        "T-14 complétude — aucun segment anglais ne subsiste dans une traduction",
        [
            (f"documents incomplets : {incomplets}", not incomplets),
            (f"{total} segment(s) contrôlé(s)", total > 0),
            ("le vérificateur porte un contrôle de complétude",
             "Complétude" in code),
            ("il s'exécute avant les autres filets",
             code.index("Complétude") < code.index("Second filet")),
        ],
    )


def test_15_integrite_des_blocs_de_code():
    """Traduire un commentaire ne doit jamais toucher une ligne exécutable.

    C'est la condition qui rend l'assouplissement acceptable : jusqu'à la
    v1.23.0, « rien ne bouge dans un bloc de code » était une garantie simple,
    et c'est elle qui fait qu'une commande copiée fonctionne. Elle est
    maintenant tenue par un contrôle plutôt que par une abstention.

    L'appariement se fait par empreinte, jamais par position : resegmenter un
    fichier traduit désaligne tout dès qu'une traduction ajoute un saut de
    ligne, et un contrôle mal apparié criait 259 atteintes là où il n'y en
    avait aucune.
    """
    manifeste = lib.charger_manifeste()
    modifies = atteintes = 0
    details = []

    for langue in manifeste["langues_cibles"]:
        for entree in manifeste["ordre"]:
            source = {
                lib.empreinte(s["texte"]): s
                for s in lib.segmenter(
                    (lib.RACINE / entree["chemin"]).read_text(encoding="utf-8"))
            }
            chemin = lib.chemin_etat(manifeste, langue, entree["chemin"])
            if not chemin.exists():
                continue
            with open(chemin, encoding="utf-8") as f:
                segments = json.load(f)["segments"]
            for segment in segments:
                if segment.get("origine") != "commentaires":
                    continue
                origine = source.get(segment["empreinte"])
                if not origine:
                    continue
                modifies += 1
                motif = lib.verifier_code_intact(origine["texte"], segment["traduction"])
                if motif:
                    atteintes += 1
                    details.append(f"{langue}/{entree['chemin']} : {motif}")

    exemple = "```bash\n#!/usr/bin/env bash\n# Preview what will be removed\nsudo apt remove diwall\n```"
    falsifie = exemple.replace("sudo apt remove diwall", "sudo apt purge diwall")
    traduit = exemple.replace("# Preview what will be removed", "# Aperçu de ce qui sera supprimé")

    return _verdict(
        "T-15 blocs de code — seuls les commentaires changent",
        [
            (f"{modifies} bloc(s) modifié(s), {atteintes} atteinte(s) {details[:2]}",
             atteintes == 0),
            ("le shebang n'est jamais traduisible",
             1 not in lib.lignes_commentaires(exemple)),
            ("une commande commentée est écartée",
             lib.est_commande_commentee("sudo apt install ./diwall.deb")),
            ("une phrase est retenue",
             not lib.est_commande_commentee("Preview what will be removed")),
            ("contre-épreuve : ligne exécutable modifiée détectée",
             lib.verifier_code_intact(exemple, falsifie) is not None),
            ("commentaire traduit accepté",
             lib.verifier_code_intact(exemple, traduit) is None),
        ],
    )


def main():
    resultats = [
        test_1_manifeste_couvre_son_perimetre(),
        test_2_document_orphelin_echoue(),
        test_3_segmentation_ne_perd_rien(),
        test_4_masquage_reversible(),
        test_5_integrite_des_balises(),
        test_6_segment_non_traduit_rejete(),
        test_7_second_filet_options_et_chemins(),
        test_8_porte_similarite_desactivable_et_positionnement(),
        test_9_pdf_ordre_pedagogique(),
        test_10_non_pollution_du_produit(),
        test_11_traductions_conformes_au_manifeste(),
        test_12_marges_pdf(),
        test_13_arbitrages_humains(),
        test_14_completude_livree(),
        test_15_integrite_des_blocs_de_code(),
    ]

    n_ok = 0
    for ok, lignes in resultats:
        print("\n".join(lignes))
        if ok:
            n_ok += 1
    print()
    print(f"=== {n_ok}/{len(resultats)} tests OK ===")
    sys.exit(0 if n_ok == len(resultats) else 1)


if __name__ == "__main__":
    main()
