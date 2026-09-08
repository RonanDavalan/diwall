#!/usr/bin/env bash
# install.sh — installation vierge de Diwall depuis un clone GitHub
# Crée l'utilisateur système, le venv, déploie le code, vérifie les permissions.
# Usage : bash scripts/install.sh [--url URL_TEST]
#
# Options :
#   --url URL   URL utilisée pour le smoke test (défaut : https://example.com)
#   --skip-test Ne pas exécuter le smoke test final
set -euo pipefail

DEST="/opt/diwall"
GROUPE="diwall"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
URL_TEST="https://example.com"
SKIP_TEST=false
# v1.18.0 — doit rester synchronisé avec GUIDE_VERSION_ATTENDUE dans
# lib/preflight_guide.py et <!-- notice-version --> en tête de docs/GUIDE_LLM.md.
# Le smoke test d'installation est un appelant légitime comme un autre : il
# passe le jeton explicitement plutôt que de contourner le verrou.
GUIDE_VERSION="1.3"

# ── Arguments ────────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --url)       URL_TEST="$2"; shift 2 ;;
        --skip-test) SKIP_TEST=true;  shift  ;;
        *) echo "Option inconnue : $1" >&2; exit 1 ;;
    esac
done

echo "=== Diwall — installation depuis $REPO ==="
echo ""

# ── Étape 1 — Utilisateur et groupe système ──────────────────────────────────
# Le groupe est créé séparément car userdel ne supprime pas le groupe primaire
# sous Debian (il peut rester orphelin après désinstallation). useradd échoue
# avec exit 9 si le groupe existe déjà — d'où la vérification préalable.
if ! getent group "$GROUPE" &>/dev/null; then
    sudo groupadd --system "$GROUPE"
    echo "  Créé     : groupe système '$GROUPE'"
else
    echo "  Existant : groupe système '$GROUPE'"
fi

if ! id "$GROUPE" &>/dev/null; then
    sudo useradd --system --no-create-home --shell /bin/false -g "$GROUPE" "$GROUPE"
    echo "  Créé     : utilisateur système '$GROUPE'"
else
    echo "  Existant : utilisateur système '$GROUPE'"
fi

# ── Étape 2 — Répertoire principal ───────────────────────────────────────────
if [ ! -d "$DEST" ]; then
    sudo mkdir -p "$DEST"
    sudo chown root:"$GROUPE" "$DEST"
    sudo chmod 755 "$DEST"
    echo "  Créé     : $DEST"
else
    echo "  Existant : $DEST"
fi

# ── Étape 3 — Environnement Python ───────────────────────────────────────────
if [ ! -f "$DEST/venv/bin/python3" ]; then
    echo "  Création du venv Python..."
    sudo /usr/bin/python3 -m venv "$DEST/venv"
    sudo -H "$DEST/venv/bin/pip" install --quiet -r "$REPO/requirements.txt"
    echo "  Venv     : OK ($(sudo $DEST/venv/bin/python3 --version))"
else
    echo "  Existant : venv ($($DEST/venv/bin/python3 --version 2>/dev/null || echo inconnu))"
fi

# ── Étape 4 — Chromium ───────────────────────────────────────────────────────
# Chemin fixe, passé explicitement à travers sudo (VAR=val cmd, pas export) :
# ne pas dépendre du réglage env_reset de sudo pour HOME sur cette machine.
# Trouvé par un cycle .deb réel sur une machine où sudo remet HOME=/root —
# sans ce réglage, Chromium atterrit dans /root/.cache/ms-playwright,
# invisible pour l'opérateur réel. shot.py fixe le même chemin par défaut à
# l'exécution — les deux doivent rester synchronisés.
PW_BROWSERS="$DEST/.cache/ms-playwright"
if ! sudo PLAYWRIGHT_BROWSERS_PATH="$PW_BROWSERS" "$DEST/venv/bin/python3" -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.stop()" 2>/dev/null; then
    echo "  Playwright non disponible, skip Chromium"
fi
CHROMIUM_PATH=$(sudo PLAYWRIGHT_BROWSERS_PATH="$PW_BROWSERS" "$DEST/venv/bin/python3" -c \
    "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium; print(b.executable_path); p.stop()" 2>/dev/null || true)
if [ -z "$CHROMIUM_PATH" ] || [ ! -f "$CHROMIUM_PATH" ]; then
    echo "  Installation de Chromium..."
    # --with-deps : installe aussi les bibliothèques partagées système
    # (libnspr4, libnss3, etc.) via apt — trouvé manquant par un cycle .deb
    # réel sur machine minimale (TargetClosedError, libnspr4.so introuvable).
    sudo PLAYWRIGHT_BROWSERS_PATH="$PW_BROWSERS" "$DEST/venv/bin/playwright" install --with-deps chromium
    echo "  Chromium : installé"
else
    echo "  Existant : Chromium ($CHROMIUM_PATH)"
fi
sudo chown -R root:"$GROUPE" "$PW_BROWSERS" 2>/dev/null || true
sudo find "$PW_BROWSERS" -type d -exec chmod 755 {} + 2>/dev/null || true
sudo find "$PW_BROWSERS" -type f -exec chmod go+r {} + 2>/dev/null || true

# ── Étape 5 — Déploiement du code ────────────────────────────────────────────
echo ""
bash "$REPO/scripts/deploy.sh"
echo ""

# ── Étape 6 — Répertoire de preuves ──────────────────────────────────────────
sudo mkdir -p "/var/log/diwall/preuves"
sudo chown root:"$GROUPE" "/var/log/diwall"
sudo chown "$USER":"$GROUPE" "/var/log/diwall/preuves"
sudo chmod 2770 "/var/log/diwall/preuves"
echo "  Preuves  : /var/log/diwall/preuves (2770 $USER:$GROUPE)"

# ── Étape 7 — Vérification des permissions ───────────────────────────────────
echo "  Vérification des permissions..."
ERRORS=0

check_dir() {
    local path="$1" expected_mode="$2" expected_owner="$3"
    local actual
    actual=$(sudo stat -c "%a %U:%G" "$path" 2>/dev/null || echo "absent")
    local actual_mode="${actual%% *}"
    local actual_owner="${actual#* }"
    if [ "$actual_mode" != "$expected_mode" ] || [ "$actual_owner" != "$expected_owner" ]; then
        echo "  ERREUR   : $path → $actual (attendu : $expected_mode $expected_owner)"
        ERRORS=$((ERRORS + 1))
    fi
}

check_file() {
    local path="$1" expected_mode="$2" expected_owner="$3"
    if [ ! -f "$path" ]; then
        echo "  ABSENT   : $path (attendu : $expected_mode $expected_owner)"
        ERRORS=$((ERRORS + 1))
        return
    fi
    local actual
    actual=$(sudo stat -c "%a %U:%G" "$path" 2>/dev/null || echo "absent")
    local actual_mode="${actual%% *}"
    local actual_owner="${actual#* }"
    if [ "$actual_mode" != "$expected_mode" ] || [ "$actual_owner" != "$expected_owner" ]; then
        echo "  ERREUR   : $path → $actual (attendu : $expected_mode $expected_owner)"
        ERRORS=$((ERRORS + 1))
    fi
}

check_dir "$DEST"             "755" "root:$GROUPE"
check_dir "$DEST/lib"         "755" "root:$GROUPE"
check_dir "$DEST/scenarios"   "755" "root:$GROUPE"
check_dir "$DEST/references"  "770" "root:$GROUPE"
check_dir "$DEST/skills"               "770" "root:$GROUPE"
check_dir "/var/log/diwall"            "2770" "root:$GROUPE"
check_dir "/var/log/diwall/preuves"    "2770" "$USER:$GROUPE"
check_file "$DEST/diwall-sample.conf"  "644"  "root:$GROUPE"
# diwall.conf n'existe qu'après configuration manuelle — vérifier seulement si présent
if [ -f "$DEST/diwall.conf" ]; then
    check_file "$DEST/diwall.conf" "640" "root:$GROUPE"
fi

if [ "$ERRORS" -eq 0 ]; then
    echo "  Permissions : OK"
else
    echo "  $ERRORS erreur(s) de permission détectée(s)"
    exit 1
fi

# Ajouter l'opérateur courant au groupe diwall si absent
if ! id -Gn "$USER" 2>/dev/null | tr ' ' '\n' | grep -qx "$GROUPE"; then
    sudo usermod -aG "$GROUPE" "$USER"
    echo ""
    echo "  IMPORTANT : $USER ajouté au groupe $GROUPE."
    echo "  Le groupe ne sera actif qu'à la prochaine reconnexion."
    echo "  Pour activer immédiatement sans reconnexion : newgrp $GROUPE"
    echo "  (ou utiliser : sg $GROUPE -c \"commande\")"
fi

# ── Étape 8 — Hook git pre-push (maintainer uniquement) ──────────────────────
# Le hook et le contrôle de publication qu'il appelle sont des outils de
# gouvernance du dépôt : ils ne font pas partie de Diwall et ne sont pas
# distribués. Sur une machine qui ne les a pas, rien n'est activé — ce n'est
# pas une dégradation, un contributeur externe n'a pas à exécuter le contrôle
# de publication du mainteneur.
# Contournement explicite si nécessaire : git push --no-verify
HOOKS_MAINTAINER="$HOME/git/Diwall/scripts/hooks"
if [ ! -d "$HOOKS_MAINTAINER" ]; then
    echo "  Hook     : non activé (outils de mainteneur absents — normal hors machine de développement)"
elif git -C "$REPO" config core.hooksPath "$HOOKS_MAINTAINER" 2>/dev/null; then
    echo "  Hook     : pre-push activé (core.hooksPath → $HOOKS_MAINTAINER)"
else
    echo "  Hook     : non activé (répertoire non-git — ignoré)"
fi

# ── Étape 9 — Smoke test ─────────────────────────────────────────────────────
if [ "$SKIP_TEST" = false ]; then
    echo ""
    echo "  Smoke test sur $URL_TEST..."

    PYTHON="$DEST/venv/bin/python3"

    # shot.py
    RESULT=$(sudo -u "$USER" "$PYTHON" "$DEST/shot.py" --url "$URL_TEST" --som --guide-version "$GUIDE_VERSION" 2>&1)
    if echo "$RESULT" | grep -q '"succes": true'; then
        echo "  shot.py  : OK"
    else
        echo "  shot.py  : ERREUR"
        echo "$RESULT" | head -5
        exit 1
    fi

    # watch.py --sauver-reference
    RESULT=$(sudo -u "$USER" "$PYTHON" "$DEST/watch.py" --url "$URL_TEST" --sauver-reference --guide-version "$GUIDE_VERSION" 2>&1)
    if echo "$RESULT" | grep -q '"succes": true'; then
        echo "  watch.py --sauver-reference : OK"
    else
        echo "  watch.py --sauver-reference : ERREUR"
        echo "$RESULT" | head -5
        exit 1
    fi

    # watch.py --comparer-pixel
    REF="$DEST/references/$(echo "$URL_TEST" | sed 's|https\?://||;s|/.*||')/reference.png"
    RESULT=$(sudo -u "$USER" "$PYTHON" "$DEST/watch.py" --url "$URL_TEST" --comparer-pixel "$REF" --guide-version "$GUIDE_VERSION" 2>&1)
    if echo "$RESULT" | grep -q '"succes": true'; then
        echo "  watch.py --comparer-pixel   : OK"
    else
        echo "  watch.py --comparer-pixel   : ERREUR"
        echo "$RESULT" | head -5
        exit 1
    fi

    echo ""
    echo "=== Installation terminée — smoke test réussi ==="
else
    echo ""
    echo "=== Installation terminée (smoke test ignoré) ==="
fi
