#!/usr/bin/env bash
# configurer-repertoire-chiffre.sh — initialise le répertoire chiffré Diwall (Phase 7 : gocryptfs).
#
# Mode par défaut (chiffré) : initialise un répertoire chiffré gocryptfs dans
#                             secrets_crypt_dir et crée secrets_dir comme point
#                             de montage vide.
# Mode dégradé (--sans-chiffrement) : crée secrets_dir en clair avec chmod 700.
#                             Réservé aux machines où gocryptfs n'est pas
#                             installable. Les identifiants y sont lisibles.
#
# Usage :
#   bash configurer-repertoire-chiffre.sh                     # chiffré (défaut)
#   bash configurer-repertoire-chiffre.sh --sans-chiffrement  # en clair, dégradé
#   bash configurer-repertoire-chiffre.sh --config <path>     # diwall.conf alternatif
set -euo pipefail

CONF="${DIWALL_CONF:-/opt/diwall/diwall.conf}"
MODE_CHIFFRE=1

for arg in "$@"; do
    case "$arg" in
        --sans-chiffrement) MODE_CHIFFRE=0 ;;
        --gocryptfs) MODE_CHIFFRE=1 ;;   # conservé : ancien drapeau, sans effet nouveau
        --config) shift; CONF="$1" ;;
    esac
done

# ── Lire la configuration ─────────────────────────────────────────────────────
if [ -f "$CONF" ]; then
    SECRETS_DIR=$(python3 -c "
import json, os, sys
conf = json.load(open('$CONF'))
print(os.path.expanduser(conf.get('secrets_dir', '~/Vaults/Diwall')))
" 2>/dev/null || echo "$HOME/Secrets/Diwall")
    SECRETS_CRYPT_DIR=$(python3 -c "
import json, os, sys
conf = json.load(open('$CONF'))
default = os.path.expanduser(conf.get('secrets_dir', '~/Vaults/Diwall')) + '.crypt'
print(os.path.expanduser(conf.get('secrets_crypt_dir', default)))
" 2>/dev/null || echo "${SECRETS_DIR}.crypt")
else
    SECRETS_DIR="${DIWALL_SECRETS_DIR:-$HOME/Secrets/Diwall}"
    SECRETS_CRYPT_DIR="${DIWALL_SECRETS_CRYPT_DIR:-${SECRETS_DIR}.crypt}"
fi

echo "=== Diwall — configuration du repertoire chiffre ==="
echo "    secrets_dir      : $SECRETS_DIR"
echo "    secrets_crypt_dir: $SECRETS_CRYPT_DIR"
echo "    mode             : $([ $MODE_CHIFFRE -eq 1 ] && echo 'chiffre (gocryptfs)' || echo 'EN CLAIR — mode degrade')"
echo ""

if [ $MODE_CHIFFRE -eq 0 ]; then
    # ── Mode Phase 6 : répertoire en clair ───────────────────────────────────
    if [ -d "$SECRETS_DIR" ]; then
        echo "  Répertoire existant : $SECRETS_DIR"
    else
        mkdir -p "$SECRETS_DIR"
        echo "  Créé : $SECRETS_DIR"
    fi
    chmod 700 "$SECRETS_DIR"
    echo "  Permissions : 700 (propriétaire uniquement)"
    echo ""
    echo "ATTENTION : ce répertoire n'est pas chiffré. Les identifiants y sont"
    echo "lisibles par tout processus de votre compte. Pour le chiffrer :"
    echo "  bash configurer-repertoire-chiffre.sh"
    echo "  bash migrer-repertoire-chiffre.sh"
else
    # ── Mode Phase 7 : initialisation gocryptfs ───────────────────────────────
    if ! command -v gocryptfs &>/dev/null; then
        echo "ERREUR : gocryptfs non trouvé." >&2
        echo "  Debian : sudo apt install gocryptfs" >&2
        exit 1
    fi

    if [ -f "$SECRETS_CRYPT_DIR/gocryptfs.conf" ]; then
        echo "  Répertoire chiffré déjà initialisé : $SECRETS_CRYPT_DIR"
        echo "  Rien à faire."
        exit 0
    fi

    mkdir -p "$SECRETS_CRYPT_DIR"
    chmod 700 "$SECRETS_CRYPT_DIR"
    echo "  Initialisation du répertoire chiffré dans : $SECRETS_CRYPT_DIR"
    echo "  (saisie du mot de passe de chiffrement — non enregistré)"
    echo ""
    gocryptfs -init "$SECRETS_CRYPT_DIR"

    mkdir -p "$SECRETS_DIR"
    chmod 700 "$SECRETS_DIR"
    echo ""
    echo "  Point de montage créé : $SECRETS_DIR"
    echo ""
    echo "Prochaine étape — migrer le répertoire chiffré existant :"
    echo "  bash migrer-repertoire-chiffre.sh"
    echo ""
    echo "Ou monter directement si le répertoire chiffré est vide :"
    echo "  bash monter-repertoire-chiffre.sh"
fi

echo "=== Setup terminé ==="
