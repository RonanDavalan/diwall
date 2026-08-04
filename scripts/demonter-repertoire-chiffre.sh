#!/usr/bin/env bash
# demonter-repertoire-chiffre.sh — démonte proprement le répertoire chiffré gocryptfs Diwall.
#
# Idempotent : si le répertoire chiffré n'est pas monté, exit 0 sans erreur.
# Gère les fichiers ouverts via lazy unmount (fusermount3 -u -z).
#
# Usage :
#   bash demonter-repertoire-chiffre.sh
#   bash demonter-repertoire-chiffre.sh --force    # lazy unmount sans vérification fichiers ouverts
#   bash demonter-repertoire-chiffre.sh --config /opt/diwall/diwall.conf
#
# Codes de sortie :
#   0 — démonté (ou déjà démonté)
#   1 — fichiers ouverts détectés, démontage refusé (sans --force)
#   2 — erreur technique
set -euo pipefail

CONF="${DIWALL_CONF:-/opt/diwall/diwall.conf}"
FORCE=0

while [ $# -gt 0 ]; do
    case "$1" in
        --force)  FORCE=1; shift ;;
        --config) shift; CONF="$1"; shift ;;
        *) shift ;;
    esac
done

# ── Lire la configuration ─────────────────────────────────────────────────────
if [ -f "$CONF" ]; then
    SECRETS_DIR=$(python3 -c "
import json, os; conf=json.load(open('$CONF'))
print(os.path.expanduser(conf.get('secrets_dir','~/Secrets/Diwall')))")
else
    SECRETS_DIR="${DIWALL_SECRETS_DIR:-$HOME/Secrets/Diwall}"
fi

SECRETS_DIR_REAL=$(realpath -m "$SECRETS_DIR")

# ── Idempotence : pas monté → exit 0 ─────────────────────────────────────────
if ! grep -q "$SECRETS_DIR_REAL" /proc/mounts 2>/dev/null; then
    echo "Répertoire chiffré non monté : $SECRETS_DIR"
    exit 0
fi

# ── Vérifier les fichiers ouverts ────────────────────────────────────────────
FICHIERS_OUVERTS=""
if command -v fuser &>/dev/null; then
    FICHIERS_OUVERTS=$(fuser -m "$SECRETS_DIR" 2>/dev/null || true)
elif command -v lsof &>/dev/null; then
    FICHIERS_OUVERTS=$(lsof +D "$SECRETS_DIR" 2>/dev/null | tail -n +2 || true)
fi

if [ -n "$FICHIERS_OUVERTS" ] && [ $FORCE -eq 0 ]; then
    echo "AVERTISSEMENT : des processus ont des fichiers ouverts dans $SECRETS_DIR" >&2
    echo "$FICHIERS_OUVERTS" >&2
    echo "" >&2
    echo "Pour forcer le démontage (lazy) : bash demonter-repertoire-chiffre.sh --force" >&2
    exit 1
fi

# ── Démontage ─────────────────────────────────────────────────────────────────
if [ -n "$FICHIERS_OUVERTS" ] && [ $FORCE -eq 1 ]; then
    echo "Fichiers ouverts détectés — lazy unmount (le démontage se finalise"
    echo "quand le dernier descripteur est fermé)..."
    fusermount3 -u -z "$SECRETS_DIR"
else
    fusermount3 -u "$SECRETS_DIR"
fi

# ── Vérification post-démontage ───────────────────────────────────────────────
if ! grep -q "$SECRETS_DIR_REAL" /proc/mounts 2>/dev/null; then
    echo "Répertoire chiffré démonté : $SECRETS_DIR"
    exit 0
else
    echo "ERREUR : démontage échoué (toujours dans /proc/mounts)" >&2
    exit 2
fi
