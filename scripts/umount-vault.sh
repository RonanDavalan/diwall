#!/usr/bin/env bash
# umount-vault.sh — démonte proprement le coffre gocryptfs Diwall.
#
# Idempotent : si le coffre n'est pas monté, exit 0 sans erreur.
# Gère les fichiers ouverts via lazy unmount (fusermount3 -u -z).
#
# Usage :
#   bash umount-vault.sh
#   bash umount-vault.sh --force    # lazy unmount sans vérification fichiers ouverts
#   bash umount-vault.sh --config /opt/diwall/diwall.conf
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
    VAULT_DIR=$(python3 -c "
import json, os; conf=json.load(open('$CONF'))
print(os.path.expanduser(conf.get('vault_dir','~/Vaults/Diwall')))")
else
    VAULT_DIR="${DIWALL_VAULT_DIR:-$HOME/Vaults/Diwall}"
fi

VAULT_DIR_REAL=$(realpath -m "$VAULT_DIR")

# ── Idempotence : pas monté → exit 0 ─────────────────────────────────────────
if ! grep -q "$VAULT_DIR_REAL" /proc/mounts 2>/dev/null; then
    echo "Coffre non monté : $VAULT_DIR"
    exit 0
fi

# ── Vérifier les fichiers ouverts ────────────────────────────────────────────
FICHIERS_OUVERTS=""
if command -v fuser &>/dev/null; then
    FICHIERS_OUVERTS=$(fuser -m "$VAULT_DIR" 2>/dev/null || true)
elif command -v lsof &>/dev/null; then
    FICHIERS_OUVERTS=$(lsof +D "$VAULT_DIR" 2>/dev/null | tail -n +2 || true)
fi

if [ -n "$FICHIERS_OUVERTS" ] && [ $FORCE -eq 0 ]; then
    echo "AVERTISSEMENT : des processus ont des fichiers ouverts dans $VAULT_DIR" >&2
    echo "$FICHIERS_OUVERTS" >&2
    echo "" >&2
    echo "Pour forcer le démontage (lazy) : bash umount-vault.sh --force" >&2
    exit 1
fi

# ── Démontage ─────────────────────────────────────────────────────────────────
if [ -n "$FICHIERS_OUVERTS" ] && [ $FORCE -eq 1 ]; then
    echo "Fichiers ouverts détectés — lazy unmount (le démontage se finalise"
    echo "quand le dernier descripteur est fermé)..."
    fusermount3 -u -z "$VAULT_DIR"
else
    fusermount3 -u "$VAULT_DIR"
fi

# ── Vérification post-démontage ───────────────────────────────────────────────
if ! grep -q "$VAULT_DIR_REAL" /proc/mounts 2>/dev/null; then
    echo "Coffre démonté : $VAULT_DIR"
    exit 0
else
    echo "ERREUR : démontage échoué (toujours dans /proc/mounts)" >&2
    exit 2
fi
