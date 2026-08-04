#!/usr/bin/env bash
# verifier-coherence.sh — v1.19.0 : audit statique doc/code, deux vérifications
# indépendantes correspondant à des dérives réellement payées (sessions 40-47) :
#
#   1. Synchronisation des notice-version : le commentaire
#      <!-- notice-version: X.Y --> en tête de chaque docs/GUIDE_LLM_*.md doit
#      être identique à la colonne « Version » de la table « Notice index »
#      de docs/GUIDE_LLM.md.
#   2. Flags documentés : chaque `add_argument("--...")` de shot.py, rpa.py,
#      watch.py doit apparaître au moins une fois quelque part sous docs/.
#   3. Budget de longueur de docs/GUIDE_LLM.md (v1.21.0) : ≤250 lignes,
#      promesse écrite dans CLAUDE.md — dérive silencieuse constatée le
#      14/07/2026 (413 lignes réelles vs 250 promises), jamais détectée
#      faute de ce contrôle.
#
# Best-effort assumé (grep, pas d'AST) — un faux négatif est possible sur une
# construction Python inhabituelle ; un faux positif quasi impossible (une
# chaîne "--xxx" présente en doc suffit à satisfaire la vérification 2).
#
# Invocable seul, ou en fin d'audit de scripts/preflight-publication.sh — non
# bloquant pour le hook pre-push dans ce cycle (on observe d'abord son taux
# de faux positifs avant de le durcir en bloquant).
#
# Usage : bash verifier-coherence.sh
# Exit 0 : rien à signaler. Exit 1 : au moins une divergence (détail sur stderr).
set -uo pipefail

REPO_DIR="${DIWALL_REPO_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
DOCS_DIR="${DIWALL_DOCS_DIR:-$REPO_DIR/docs}"
GUIDE_LLM="$DOCS_DIR/GUIDE_LLM.md"

DERIVE=0

# ── Vérification 1 — notice-version vs table d'index ────────────────────────
if [ -f "$GUIDE_LLM" ]; then
    while IFS='|' read -r _ notice_col _reste_col version_col _; do
        notice=$(echo "$notice_col" | tr -d ' `')
        case "$notice" in
            GUIDE_LLM_*.md) ;;
            *) continue ;;
        esac
        version_table=$(echo "$version_col" | tr -d ' ')
        fichier="$DOCS_DIR/$notice"
        if [ ! -f "$fichier" ]; then
            echo "verifier-coherence: $notice référencé dans l'index mais absent de docs/" >&2
            DERIVE=1
            continue
        fi
        version_brute=$(grep -m1 -oP '(?<=notice-version: )[0-9]+\.[0-9]+' "$fichier" || true)
        if [ -z "$version_brute" ]; then
            echo "verifier-coherence: $notice — aucun <!-- notice-version: X.Y --> trouvé" >&2
            DERIVE=1
            continue
        fi
        version_fichier="v$version_brute"
        if [ "$version_fichier" != "$version_table" ]; then
            echo "verifier-coherence: $notice — table d'index=$version_table, fichier=$version_fichier" >&2
            DERIVE=1
        fi
    done < <(grep -E '^\| `GUIDE_LLM_[A-Za-z_]+\.md`' "$GUIDE_LLM")
else
    echo "verifier-coherence: $GUIDE_LLM introuvable — vérification 1 sautée" >&2
fi

# ── Vérification 2 — flags argparse documentés quelque part sous docs/ ──────
for script in shot.py rpa.py watch.py; do
    fichier="$REPO_DIR/$script"
    [ -f "$fichier" ] || continue
    flags=$(grep -oP 'add_argument\(\s*"--[a-zA-Z0-9-]+"' "$fichier" \
             | grep -oP '(?<=")--[a-zA-Z0-9-]+' | sort -u)
    while IFS= read -r flag; do
        [ -z "$flag" ] && continue
        # Une plomberie interne (ex. --source-scenario, --chainage) documente
        # souvent le champ JSON qu'elle alimente (underscore, sans tirets) plutôt
        # que le flag lui-même — les deux formes sont acceptées pour éviter un
        # faux positif sur ces cas, réels dans ce dépôt (v1.19.0).
        flag_underscore=$(echo "${flag#--}" | tr '-' '_')
        if ! grep -rqF -- "$flag" "$DOCS_DIR" 2>/dev/null \
           && ! grep -rqF -- "$flag_underscore" "$DOCS_DIR" 2>/dev/null; then
            echo "verifier-coherence: $flag ($script) absent de docs/" >&2
            DERIVE=1
        fi
    done <<< "$flags"
done

# ── Vérification 3 — budget de longueur de GUIDE_LLM.md (v1.21.0) ──────────
BUDGET_LIGNES=250
if [ -f "$GUIDE_LLM" ]; then
    lignes=$(wc -l < "$GUIDE_LLM")
    if [ "$lignes" -gt "$BUDGET_LIGNES" ]; then
        echo "verifier-coherence: $GUIDE_LLM — $lignes lignes, budget $BUDGET_LIGNES dépassé" >&2
        DERIVE=1
    fi
fi

# ── Vérification 4 — jeton de guide synchronisé partout (v1.22.0) ──────────
# Le jeton attendu vit à trois endroits qui doivent rester égaux : la constante
# GUIDE_VERSION_ATTENDUE (lib/preflight_guide.py, autorité), et les deux
# scripts qui passent ce jeton à leurs propres smoke tests.
#
# Origine : découvert le 29/07/2026 — install.sh et preflight-publication.sh
# portaient encore 3.7 quand le guide était passé à 4.0. Sur la machine de
# développement, un marqueur local déjà valide rendait la dérive invisible ;
# sur une machine vierge, le smoke test final d'install.sh aurait échoué en
# guide_non_lu, sans que rien n'explique pourquoi. Le test d'installation à
# froid ne peut pas attraper ce cas — le canal .deb ne passe aucun jeton — et
# c'est précisément pourquoi cette vérification est statique.
ATTENDU_PY="$REPO_DIR/lib/preflight_guide.py"
if [ -f "$ATTENDU_PY" ]; then
    reference=$(grep -m1 -oP '(?<=^GUIDE_VERSION_ATTENDUE = ")[0-9]+\.[0-9]+' "$ATTENDU_PY" || true)
    if [ -z "$reference" ]; then
        echo "verifier-coherence: GUIDE_VERSION_ATTENDUE introuvable dans lib/preflight_guide.py" >&2
        DERIVE=1
    else
        # Le guide lui-même — l'autorité que le jeton prétend refléter.
        if [ -f "$GUIDE_LLM" ]; then
            notice=$(grep -m1 -oP '(?<=notice-version: )[0-9]+\.[0-9]+' "$GUIDE_LLM" || true)
            if [ "$notice" != "$reference" ]; then
                echo "verifier-coherence: GUIDE_LLM.md notice-version=$notice, GUIDE_VERSION_ATTENDUE=$reference" >&2
                DERIVE=1
            fi
        fi
        for script in scripts/install.sh scripts/preflight-publication.sh; do
            fichier="$REPO_DIR/$script"
            [ -f "$fichier" ] || continue
            valeur=$(grep -m1 -oP '(?<=^GUIDE_VERSION=")[0-9]+\.[0-9]+' "$fichier" || true)
            if [ -z "$valeur" ]; then
                echo "verifier-coherence: $script — aucun GUIDE_VERSION=\"X.Y\" trouvé" >&2
                DERIVE=1
            elif [ "$valeur" != "$reference" ]; then
                echo "verifier-coherence: $script — GUIDE_VERSION=$valeur, attendu $reference" >&2
                DERIVE=1
            fi
        done
    fi
fi

if [ "$DERIVE" -eq 0 ]; then
    echo "verifier-coherence: OK — notice-versions synchrones, flags documentés, budget de longueur respecté, jeton de guide synchronisé."
    exit 0
fi

exit 1
