#!/usr/bin/env bash
# construire-paquet.sh — construit le paquet .deb et range ses artefacts.
#
# Pourquoi ce script existe (v1.22.0) :
# `dpkg-buildpackage` écrit ses artefacts dans le répertoire parent de l'arbre
# source, par construction — aucun réglage de debian/rules ne redirige cela
# proprement. La construction se faisant depuis ~/git/Diwall/Diwall/, les .deb
# atterrissaient dans ~/git/Diwall/, qui est un répertoire tampon et n'a jamais
# eu vocation à être une sortie de build.
#
# Le choix retenu est de construire puis de déplacer, plutôt que de tenter de
# détourner le comportement de dpkg : trois lignes de plus, et l'outil garde
# son comportement normal.
#
# Toutes les versions sont conservées : le .buildinfo est la seule trace de
# l'environnement exact de construction, il n'a de valeur que gardé.
#
# Usage :
#   bash scripts/construire-paquet.sh
#
# Sortie : ~/git/Diwall/paquets/<version>/{*.deb,*.buildinfo,*.changes}
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
TAMPON="$(cd "$REPO/.." && pwd)"

cd "$REPO"

# Version lue dans debian/changelog — source de vérité du paquet, jamais saisie
# à la main ici (une version passée en argument finirait par diverger).
VERSION_DEB="$(dpkg-parsechangelog --show-field Version)"
VERSION="${VERSION_DEB%-*}"
DEST="$TAMPON/paquets/$VERSION"

echo "Construction du paquet diwall $VERSION_DEB…"
dpkg-buildpackage -us -uc

mkdir -p "$DEST"

# Motifs exacts de cette construction — jamais un glob large sur le tampon,
# qui contient aussi les artefacts des versions précédentes.
DEPLACES=0
for motif in "diwall_${VERSION_DEB}_all.deb" \
             "diwall_${VERSION_DEB}_"*.buildinfo \
             "diwall_${VERSION_DEB}_"*.changes; do
    for fichier in $TAMPON/$motif; do
        [ -e "$fichier" ] || continue
        mv "$fichier" "$DEST/"
        DEPLACES=$((DEPLACES + 1))
    done
done

if [ "$DEPLACES" -eq 0 ]; then
    echo "construire-paquet: aucun artefact trouvé pour $VERSION_DEB dans $TAMPON" >&2
    exit 1
fi

echo
echo "OK — $DEPLACES artefact(s) rangé(s) dans $DEST"
ls -1 "$DEST"
echo
echo "Installation :"
echo "  sudo apt install $DEST/diwall_${VERSION_DEB}_all.deb"
