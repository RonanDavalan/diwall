#!/usr/bin/env bash
# migrate-vault.sh — migration atomique du vault plaintext vers gocryptfs.
#
# Spec : _CADRE/SPECIFICATIONS/28_PHASE7_VAULT_CHIFFRE.md §Migration atomique
#
# Séquence en 5 étapes :
#   1. Vérifications préalables
#   2. (Le coffre doit être déjà initialisé via setup-vault.sh --gocryptfs)
#   3. Montage temporaire + copie + vérification checksums
#   4. Bascule du point de montage
#   5. Confirmation humaine (l'archive plaintext n'est JAMAIS supprimée auto)
#
# Usage :
#   bash migrate-vault.sh
#   bash migrate-vault.sh --config /opt/diwall/diwall.conf
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

DATE=$(date +%Y%m%d_%H%M%S)
ARCHIVE="${VAULT_DIR}.plaintext_backup_${DATE}"
TMP_MOUNT=$(mktemp -d)

# Nettoyage en cas d'interruption
cleanup() {
    if mountpoint -q "$TMP_MOUNT" 2>/dev/null; then
        fusermount3 -u "$TMP_MOUNT" 2>/dev/null || true
    fi
    rmdir "$TMP_MOUNT" 2>/dev/null || true
}
trap cleanup EXIT

echo "=== Diwall — migration vault → gocryptfs ==="
echo "    vault_dir      : $VAULT_DIR"
echo "    vault_crypt_dir: $VAULT_CRYPT_DIR"
echo "    archive prévu  : $ARCHIVE"
echo ""

# ── Étape 1 : Vérifications préalables ───────────────────────────────────────
echo "--- Étape 1 : vérifications ---"

if ! command -v gocryptfs &>/dev/null; then
    echo "ERREUR : gocryptfs non trouvé. sudo apt install gocryptfs" >&2; exit 1
fi

if [ ! -f "$VAULT_CRYPT_DIR/gocryptfs.conf" ]; then
    echo "ERREUR : coffre gocryptfs non initialisé." >&2
    echo "  Lancer d'abord : bash setup-vault.sh --gocryptfs" >&2; exit 1
fi

if [ ! -d "$VAULT_DIR" ] || [ -z "$(ls -A "$VAULT_DIR" 2>/dev/null)" ]; then
    echo "ERREUR : vault_dir vide ou inexistant — rien à migrer." >&2; exit 1
fi

if python3 -c "
import os
vault = '$VAULT_DIR'
with open('/proc/mounts') as f:
    if any(os.path.realpath(vault) in l for l in f):
        exit(0)
exit(1)" 2>/dev/null; then
    echo "ERREUR : vault_dir est déjà un point de montage actif." >&2
    echo "  Démonter d'abord : bash umount-vault.sh" >&2; exit 1
fi

N_SOURCE=$(find "$VAULT_DIR" -maxdepth 1 -name "*.json" | wc -l)
echo "  OK — $N_SOURCE fichier(s) JSON à migrer."

# ── Étape 3 : Montage temporaire + copie + checksums ─────────────────────────
echo ""
echo "--- Étape 3 : montage temporaire et copie ---"
echo "  Montage de $VAULT_CRYPT_DIR → $TMP_MOUNT"
echo "  (saisie du mot de passe — non enregistré)"
echo ""

read -s -p "Mot de passe du coffre gocryptfs : " VAULT_PASS
echo ""
printf '%s' "$VAULT_PASS" | gocryptfs -passfile /dev/stdin "$VAULT_CRYPT_DIR" "$TMP_MOUNT"
unset VAULT_PASS

echo "  Copie des fichiers..."
cp -a "$VAULT_DIR"/. "$TMP_MOUNT"/

echo "  Vérification des checksums..."
OK=1
while IFS= read -r -d '' src; do
    base=$(basename "$src")
    dst="$TMP_MOUNT/$base"
    if [ ! -f "$dst" ]; then
        echo "  ERREUR : $base absent de la copie" >&2; OK=0; continue
    fi
    sum_src=$(sha256sum "$src" | cut -d' ' -f1)
    sum_dst=$(sha256sum "$dst" | cut -d' ' -f1)
    if [ "$sum_src" != "$sum_dst" ]; then
        echo "  ERREUR : checksum KO pour $base" >&2; OK=0
    else
        echo "  OK : $base"
    fi
done < <(find "$VAULT_DIR" -maxdepth 1 -name "*.json" -print0)

if [ $OK -eq 0 ]; then
    echo "" >&2
    echo "ERREUR : vérification échouée — migration annulée." >&2
    exit 3
fi
echo "  Tous les checksums OK."

# Démontage du temporaire
fusermount3 -u "$TMP_MOUNT"
rmdir "$TMP_MOUNT"
trap - EXIT

# ── Étape 4 : Bascule du point de montage ────────────────────────────────────
echo ""
echo "--- Étape 4 : bascule ---"
echo "  Archive : $VAULT_DIR → $ARCHIVE"
mv "$VAULT_DIR" "$ARCHIVE"
mkdir -p "$VAULT_DIR"
chmod 700 "$VAULT_DIR"

echo "  Montage chiffré : $VAULT_CRYPT_DIR → $VAULT_DIR"
echo "  (saisie du mot de passe)"
echo ""
read -s -p "Mot de passe du coffre gocryptfs : " VAULT_PASS
echo ""
printf '%s' "$VAULT_PASS" | gocryptfs -passfile /dev/stdin "$VAULT_CRYPT_DIR" "$VAULT_DIR"
unset VAULT_PASS

# Vérification post-montage
N_DEST=$(find "$VAULT_DIR" -maxdepth 1 -name "*.json" | wc -l)
if [ "$N_DEST" -ne "$N_SOURCE" ]; then
    echo "ERREUR : $N_DEST fichier(s) dans le montage, attendu $N_SOURCE." >&2
    echo "  Restaurer : mv '$ARCHIVE' '$VAULT_DIR'" >&2; exit 1
fi
echo "  $N_DEST fichier(s) lisibles dans le coffre monté."

# ── Étape 5 : Confirmation humaine ───────────────────────────────────────────
echo ""
echo "=== Migration terminée avec succès ==="
echo ""
echo "  Coffre chiffré opérationnel : $VAULT_DIR"
echo "  Archive plaintext conservée : $ARCHIVE"
echo ""
echo "  Vérifier que Diwall fonctionne normalement, puis :"
echo "  Pour supprimer l'archive plaintext (IRREVERSIBLE) :"
echo "    rm -rf '$ARCHIVE'"
echo ""
echo "  L'archive N'EST PAS supprimée automatiquement."
