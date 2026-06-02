#!/usr/bin/env bash
# setup-vault.sh — initialise le coffre Diwall (Phase 7 : gocryptfs).
#
# Mode Phase 6 (plaintext) : crée vault_dir avec chmod 700.
# Mode Phase 7 (chiffré)   : initialise un coffre gocryptfs dans vault_crypt_dir
#                             et crée vault_dir comme point de montage vide.
#
# Usage :
#   bash setup-vault.sh                  # mode plaintext (Phase 6)
#   bash setup-vault.sh --gocryptfs      # mode chiffré (Phase 7)
#   bash setup-vault.sh --config <path>  # chemin diwall.conf alternatif
set -euo pipefail

CONF="${DIWALL_CONF:-/opt/diwall/diwall.conf}"
MODE_CHIFFRE=0

for arg in "$@"; do
    case "$arg" in
        --gocryptfs) MODE_CHIFFRE=1 ;;
        --config) shift; CONF="$1" ;;
    esac
done

# ── Lire la configuration ─────────────────────────────────────────────────────
if [ -f "$CONF" ]; then
    VAULT_DIR=$(python3 -c "
import json, os, sys
conf = json.load(open('$CONF'))
print(os.path.expanduser(conf.get('vault_dir', '~/Vaults/Diwall')))
" 2>/dev/null || echo "$HOME/Vaults/Diwall")
    VAULT_CRYPT_DIR=$(python3 -c "
import json, os, sys
conf = json.load(open('$CONF'))
default = os.path.expanduser(conf.get('vault_dir', '~/Vaults/Diwall')) + '.crypt'
print(os.path.expanduser(conf.get('vault_crypt_dir', default)))
" 2>/dev/null || echo "${VAULT_DIR}.crypt")
else
    VAULT_DIR="${DIWALL_VAULT_DIR:-$HOME/Vaults/Diwall}"
    VAULT_CRYPT_DIR="${DIWALL_VAULT_CRYPT_DIR:-${VAULT_DIR}.crypt}"
fi

echo "=== Diwall — vault setup ==="
echo "    vault_dir      : $VAULT_DIR"
echo "    vault_crypt_dir: $VAULT_CRYPT_DIR"
echo "    mode           : $([ $MODE_CHIFFRE -eq 1 ] && echo 'gocryptfs (Phase 7)' || echo 'plaintext (Phase 6)')"
echo ""

if [ $MODE_CHIFFRE -eq 0 ]; then
    # ── Mode Phase 6 : répertoire en clair ───────────────────────────────────
    if [ -d "$VAULT_DIR" ]; then
        echo "  Répertoire existant : $VAULT_DIR"
    else
        mkdir -p "$VAULT_DIR"
        echo "  Créé : $VAULT_DIR"
    fi
    chmod 700 "$VAULT_DIR"
    echo "  Permissions : 700 (propriétaire uniquement)"
    echo ""
    echo "Pour passer au chiffrement gocryptfs (Phase 7) :"
    echo "  bash setup-vault.sh --gocryptfs"
    echo "  bash migrate-vault.sh"
else
    # ── Mode Phase 7 : initialisation gocryptfs ───────────────────────────────
    if ! command -v gocryptfs &>/dev/null; then
        echo "ERREUR : gocryptfs non trouvé." >&2
        echo "  Debian : sudo apt install gocryptfs" >&2
        exit 1
    fi

    if [ -f "$VAULT_CRYPT_DIR/gocryptfs.conf" ]; then
        echo "  Coffre déjà initialisé : $VAULT_CRYPT_DIR"
        echo "  Rien à faire."
        exit 0
    fi

    mkdir -p "$VAULT_CRYPT_DIR"
    chmod 700 "$VAULT_CRYPT_DIR"
    echo "  Initialisation du coffre chiffré dans : $VAULT_CRYPT_DIR"
    echo "  (saisie du mot de passe de chiffrement — non enregistré)"
    echo ""
    gocryptfs -init "$VAULT_CRYPT_DIR"

    mkdir -p "$VAULT_DIR"
    chmod 700 "$VAULT_DIR"
    echo ""
    echo "  Point de montage créé : $VAULT_DIR"
    echo ""
    echo "Prochaine étape — migrer le vault existant :"
    echo "  bash migrate-vault.sh"
    echo ""
    echo "Ou monter directement si le coffre est vide :"
    echo "  bash mount-vault.sh"
fi

echo "=== Setup terminé ==="
