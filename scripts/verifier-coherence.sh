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

if [ "$DERIVE" -eq 0 ]; then
    echo "verifier-coherence: OK — notice-versions synchrones, flags documentés."
    exit 0
fi

exit 1
