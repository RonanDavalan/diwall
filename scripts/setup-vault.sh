#!/usr/bin/env bash
# setup-vault.sh — creates the Diwall credential vault directory with strict permissions.
#
# The vault stores one JSON file per target domain:
#   ~/Vaults/Diwall/<hostname>.json  →  {"password": "...", "username": "admin"}
#
# Encrypted vault support (gocryptfs) is planned for a future release.
# For now, the directory is protected by filesystem permissions (owner only).
set -euo pipefail

VAULT_DIR="${DIWALL_VAULT_DIR:-$HOME/Vaults/Diwall}"

echo "=== Diwall — vault setup ==="
echo "    Vault directory: $VAULT_DIR"
echo ""

if [ -d "$VAULT_DIR" ]; then
    echo "  Directory already exists."
else
    mkdir -p "$VAULT_DIR"
    echo "  Created: $VAULT_DIR"
fi

chmod 700 "$VAULT_DIR"
echo "  Permissions set to 700 (owner only)."

echo ""
echo "Create one JSON file per target domain:"
echo "  $VAULT_DIR/<hostname>.json"
echo ""
echo "Example — $VAULT_DIR/your-app.local.json:"
echo '  {"password": "your-password", "username": "admin"}'
echo ""
echo "Configure the vault path in /opt/diwall/diwall.conf if different from default:"
echo "  {\"vault_dir\": \"$VAULT_DIR\"}"
echo ""
echo "Recommendation: use gocryptfs to encrypt this directory."
echo "  Encrypted vault support is planned for a future release."
echo ""
echo "=== Setup complete ==="
