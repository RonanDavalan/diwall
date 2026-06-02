#!/usr/bin/env bash
# mount-vault.sh — monte le coffre gocryptfs Diwall.
#
# Idempotent : si le coffre est déjà monté, exit 0 sans erreur.
# Le mot de passe n'est jamais passé en argument (visible dans ps).
#
# Compatible Plasma Vault : si Plasma Vault a déjà monté le coffre,
# ce script le détecte via /proc/mounts et sort proprement.
#
# Usage :
#   bash mount-vault.sh
#   bash mount-vault.sh --config /opt/diwall/diwall.conf
set -euo pipefail

CONF="${DIWALL_CONF:-/opt/diwall/diwall.conf}"
for arg in "$@"; do
    case "$arg" in --config) shift; CONF="$1" ;; esac
done

# ── Lire la configuration ─────────────────────────────────────────────────────
if [ -f "$CONF" ]; then
    VAULT_DIR=$(python3 -c "
import json, os; conf=json.load(open('$CONF'))
print(os.path.expanduser(conf.get('vault_dir','~/Vaults/Diwall')))")
    VAULT_CRYPT_DIR=$(python3 -c "
import json, os; conf=json.load(open('$CONF'))
d = os.path.expanduser(conf.get('vault_dir','~/Vaults/Diwall'))+'.crypt'
print(os.path.expanduser(conf.get('vault_crypt_dir',d)))")
else
    VAULT_DIR="${DIWALL_VAULT_DIR:-$HOME/Vaults/Diwall}"
    VAULT_CRYPT_DIR="${DIWALL_VAULT_CRYPT_DIR:-${VAULT_DIR}.crypt}"
fi

VAULT_DIR_REAL=$(realpath -m "$VAULT_DIR")

# ── Idempotence : déjà monté → exit 0 ────────────────────────────────────────
if grep -q "$VAULT_DIR_REAL" /proc/mounts 2>/dev/null; then
    echo "Coffre déjà monté : $VAULT_DIR"
    exit 0
fi

# ── Vérifications ─────────────────────────────────────────────────────────────
if ! command -v gocryptfs &>/dev/null; then
    echo "ERREUR : gocryptfs non trouvé. sudo apt install gocryptfs" >&2; exit 1
fi

if [ ! -f "$VAULT_CRYPT_DIR/gocryptfs.conf" ]; then
    echo "ERREUR : coffre non initialisé dans $VAULT_CRYPT_DIR" >&2
    echo "  Initialiser : bash setup-vault.sh --gocryptfs" >&2; exit 1
fi

mkdir -p "$VAULT_DIR"
chmod 700 "$VAULT_DIR"

# ── Montage (mot de passe par saisie interactive, jamais en argument) ─────────
echo "Montage du coffre Diwall..."
echo "  Chiffré       : $VAULT_CRYPT_DIR"
echo "  Point montage : $VAULT_DIR"
echo ""

read -s -p "Mot de passe du coffre : " VAULT_PASS
echo ""
printf '%s' "$VAULT_PASS" | gocryptfs -passfile /dev/stdin "$VAULT_CRYPT_DIR" "$VAULT_DIR"
unset VAULT_PASS

# ── Vérification post-montage ─────────────────────────────────────────────────
if grep -q "$VAULT_DIR_REAL" /proc/mounts 2>/dev/null; then
    echo "Coffre monté avec succès : $VAULT_DIR"
    exit 0
else
    echo "ERREUR : montage échoué (point de montage absent de /proc/mounts)" >&2
    exit 1
fi
