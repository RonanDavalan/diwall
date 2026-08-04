#!/usr/bin/env bash
# monitor-verifier.sh — v1.18.0 : un passage de monitoring structurel, sans
# image ni appel LLM, encapsulant rpa.py --no-capture --replay-verifier.
#
# Pas une boucle interne — un seul passage par exécution. La répétition dans
# le temps est déléguée à cron/systemd-timer (voir docs/GUIDE.md, docs/
# GUIDE_LLM_MONITORING.md). Chaque exécution est un processus isolé : aucun
# risque de fuite mémoire d'un daemon long-running, et les plafonds de
# Navigation Respectueuse se réinitialisent proprement à chaque passage.
#
# Stable → silence, exit 0. Régression détectée → notification ntfy (si
# --ntfy-topic fourni), exit 1 (même code que rpa.py --replay-verifier).
#
# Prérequis opérationnel : si ce script est appelé par cron/systemd sous un
# utilisateur OS distinct (ex. l'utilisateur système diwall), le verrou de
# lecture --guide-version (v1.18.0) doit avoir été validé une fois pour CET
# utilisateur (~<home>/.config/diwall/guide_state.json) — sinon rpa.py
# refusera de s'exécuter avec l'erreur guide_non_lu. Ce script ne contourne
# jamais ce verrou : le seeder une fois est la responsabilité de l'opérateur.
#
# Usage :
#   bash monitor-verifier.sh --scenario FICHIER --reference FICHIER \
#       [--ntfy-topic TOPIC] [--ntfy-url URL]
set -euo pipefail

PYTHON="${DIWALL_PYTHON:-/opt/diwall/venv/bin/python3}"
RPA="${DIWALL_RPA:-/opt/diwall/rpa.py}"
NTFY_URL_BASE="${DIWALL_NTFY_URL:-https://ntfy.sh}"

SCENARIO=""
REFERENCE=""
NTFY_TOPIC=""

while [ $# -gt 0 ]; do
    case "$1" in
        --scenario)   SCENARIO="$2"; shift 2 ;;
        --reference)  REFERENCE="$2"; shift 2 ;;
        --ntfy-topic) NTFY_TOPIC="$2"; shift 2 ;;
        --ntfy-url)   NTFY_URL_BASE="$2"; shift 2 ;;
        *) echo "Argument inconnu : $1" >&2; exit 2 ;;
    esac
done

if [ -z "$SCENARIO" ] || [ -z "$REFERENCE" ]; then
    echo "Usage : monitor-verifier.sh --scenario FICHIER --reference FICHIER [--ntfy-topic TOPIC] [--ntfy-url URL]" >&2
    exit 2
fi

SORTIE_ERR=$(mktemp)
trap 'rm -f "$SORTIE_ERR"' EXIT

set +e
"$PYTHON" "$RPA" --scenario "$SCENARIO" --no-capture --replay-verifier "$REFERENCE" \
    1>/dev/null 2>"$SORTIE_ERR"
CODE=$?
set -e

if [ "$CODE" -eq 0 ]; then
    exit 0
fi

# Verdict structuré émis par rpa.py sur stderr — {"type_comparaison": ...}
VERDICT_LIGNE=$(grep -o '{"type_comparaison"[^$]*}' "$SORTIE_ERR" || true)
[ -z "$VERDICT_LIGNE" ] && VERDICT_LIGNE=$(tail -n 1 "$SORTIE_ERR")

if [ -n "$NTFY_TOPIC" ]; then
    curl -fsS -X POST "${NTFY_URL_BASE%/}/${NTFY_TOPIC}" \
        -H "Title: Diwall - regression structurelle" \
        -H "Priority: high" \
        --data-binary "Scenario : $(basename "$SCENARIO")
Reference : $REFERENCE
$VERDICT_LIGNE" \
        >/dev/null 2>&1 || echo "monitor-verifier.sh : echec envoi ntfy" >&2
fi

echo "$VERDICT_LIGNE" >&2
exit "$CODE"
