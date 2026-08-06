#!/usr/bin/env bash
# monter-repertoire-chiffre.sh — monte le répertoire chiffré gocryptfs Diwall.
#
# Idempotent : si le répertoire chiffré est déjà monté, exit 0 sans erreur.
# Le mot de passe n'est jamais passé en argument (visible dans ps).
#
# Compatible Plasma Vault : si Plasma Vault a déjà monté le répertoire chiffré,
# ce script le détecte via /proc/mounts et sort proprement.
#
# Usage :
#   bash monter-repertoire-chiffre.sh
#   bash monter-repertoire-chiffre.sh --config /opt/diwall/diwall.conf
set -euo pipefail

CONF="${DIWALL_CONF:-/opt/diwall/diwall.conf}"
# Audit 06/08/2026 (C-10) : shift dans un for sur "$@" ne modifie pas la
# liste itérée — --config ne fonctionnait qu'en premier argument.
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config) CONF="$2"; shift 2 ;;
        *) echo "Option inconnue : $1" >&2; exit 1 ;;
    esac
done

# ── Lire la configuration ─────────────────────────────────────────────────────
# Audit 06/08/2026 (C-09) : $CONF interpolé dans une chaîne Python entre
# apostrophes — passé désormais en argument positionnel (sys.argv[1]).
if [ -f "$CONF" ]; then
    SECRETS_DIR=$(python3 -c "
import json, os, sys
conf = json.load(open(sys.argv[1]))
print(os.path.expanduser(conf.get('secrets_dir','~/Vaults/Diwall')))" "$CONF")
    SECRETS_CRYPT_DIR=$(python3 -c "
import json, os, sys
conf = json.load(open(sys.argv[1]))
d = os.path.expanduser(conf.get('secrets_dir','~/Vaults/Diwall'))+'.crypt'
print(os.path.expanduser(conf.get('secrets_crypt_dir',d)))" "$CONF")
else
    SECRETS_DIR="${DIWALL_SECRETS_DIR:-$HOME/Secrets/Diwall}"
    SECRETS_CRYPT_DIR="${DIWALL_SECRETS_CRYPT_DIR:-${SECRETS_DIR}.crypt}"
fi

SECRETS_DIR_REAL=$(realpath -m "$SECRETS_DIR")

# Audit 06/08/2026 (C-11) : `grep -q "$SECRETS_DIR_REAL" /proc/mounts`
# interprète le chemin comme motif cherché en sous-chaîne — un point de
# montage dont le chemin CONTIENT celui du répertoire chiffré (ou
# l'inverse) déclenchait un faux positif. Reprend la logique de
# _repertoire_est_monte (lib/repertoire_chiffre.py) : champ 2 exact ou
# sous-répertoire, restreint aux systèmes de fichiers FUSE.
_est_monte() {
    local cible="$1" point fstype
    while read -r _ point fstype _; do
        case "$fstype" in *fuse*) ;; *) continue ;; esac
        if [[ "$cible" == "$point" || "$cible" == "$point"/* ]]; then
            return 0
        fi
    done < /proc/mounts
    return 1
}

# ── Idempotence : déjà monté → exit 0 ────────────────────────────────────────
if _est_monte "$SECRETS_DIR_REAL"; then
    echo "Répertoire chiffré déjà monté : $SECRETS_DIR"
    exit 0
fi

# ── Vérifications ─────────────────────────────────────────────────────────────
if ! command -v gocryptfs &>/dev/null; then
    echo "ERREUR : gocryptfs non trouvé. sudo apt install gocryptfs" >&2; exit 1
fi

if [ ! -f "$SECRETS_CRYPT_DIR/gocryptfs.conf" ]; then
    echo "ERREUR : répertoire chiffré non initialisé dans $SECRETS_CRYPT_DIR" >&2
    echo "  Initialiser : bash configurer-repertoire-chiffre.sh --gocryptfs" >&2; exit 1
fi

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

# ── Montage (mot de passe par saisie interactive, jamais en argument) ─────────
echo "Montage du répertoire chiffré Diwall..."
echo "  Chiffré       : $SECRETS_CRYPT_DIR"
echo "  Point montage : $SECRETS_DIR"
echo ""

read -s -p "Mot de passe du répertoire chiffré : " SECRETS_PASS
echo ""
printf '%s' "$SECRETS_PASS" | gocryptfs -passfile /dev/stdin "$SECRETS_CRYPT_DIR" "$SECRETS_DIR"
unset SECRETS_PASS

# ── Vérification post-montage ─────────────────────────────────────────────────
if _est_monte "$SECRETS_DIR_REAL"; then
    echo "Répertoire chiffré monté avec succès : $SECRETS_DIR"
    exit 0
else
    echo "ERREUR : montage échoué (point de montage absent de /proc/mounts)" >&2
    exit 1
fi
