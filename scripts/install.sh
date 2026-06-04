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

# ── Étape 1 — Utilisateur système ────────────────────────────────────────────
if id "$GROUPE" &>/dev/null; then
    echo "  Existant : utilisateur système '$GROUPE'"
else
    sudo useradd --system --no-create-home --shell /bin/false "$GROUPE"
    echo "  Créé     : utilisateur système '$GROUPE'"
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
    sudo "$DEST/venv/bin/pip" install --quiet -r "$REPO/requirements.txt"
    echo "  Venv     : OK ($(sudo $DEST/venv/bin/python3 --version))"
else
    echo "  Existant : venv ($($DEST/venv/bin/python3 --version 2>/dev/null || echo inconnu))"
fi

# ── Étape 4 — Chromium ───────────────────────────────────────────────────────
if ! sudo "$DEST/venv/bin/python3" -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); p.stop()" 2>/dev/null; then
    echo "  Playwright non disponible, skip Chromium"
fi
CHROMIUM_PATH=$(sudo "$DEST/venv/bin/python3" -c \
    "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium; print(b.executable_path); p.stop()" 2>/dev/null || true)
if [ -z "$CHROMIUM_PATH" ] || [ ! -f "$CHROMIUM_PATH" ]; then
    echo "  Installation de Chromium..."
    sudo "$DEST/venv/bin/playwright" install chromium
    echo "  Chromium : installé"
else
    echo "  Existant : Chromium ($CHROMIUM_PATH)"
fi

# ── Étape 5 — Déploiement du code ────────────────────────────────────────────
echo ""
bash "$REPO/scripts/deploy.sh"
echo ""

# ── Étape 6 — Vérification des permissions ───────────────────────────────────
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

check_dir "$DEST"             "755" "root:$GROUPE"
check_dir "$DEST/lib"         "750" "root:$GROUPE"
check_dir "$DEST/scenarios"   "750" "root:$GROUPE"
check_dir "$DEST/references"  "770" "root:$GROUPE"
check_dir "$DEST/skills"      "770" "root:$GROUPE"

if [ "$ERRORS" -eq 0 ]; then
    echo "  Permissions : OK"
else
    echo "  $ERRORS erreur(s) de permission détectée(s)"
    exit 1
fi

# ── Étape 7 — Smoke test ─────────────────────────────────────────────────────
if [ "$SKIP_TEST" = false ]; then
    echo ""
    echo "  Smoke test sur $URL_TEST..."

    PYTHON="$DEST/venv/bin/python3"

    # shot.py
    RESULT=$(sudo -u "$USER" "$PYTHON" "$DEST/shot.py" --url "$URL_TEST" --som 2>&1)
    if echo "$RESULT" | grep -q '"succes": true'; then
        echo "  shot.py  : OK"
    else
        echo "  shot.py  : ERREUR"
        echo "$RESULT" | head -5
        exit 1
    fi

    # watch.py --sauver-reference
    RESULT=$(sudo -u "$USER" "$PYTHON" "$DEST/watch.py" --url "$URL_TEST" --sauver-reference 2>&1)
    if echo "$RESULT" | grep -q '"succes": true'; then
        echo "  watch.py --sauver-reference : OK"
    else
        echo "  watch.py --sauver-reference : ERREUR"
        echo "$RESULT" | head -5
        exit 1
    fi

    # watch.py --comparer-pixel
    REF="$DEST/references/$(echo "$URL_TEST" | sed 's|https\?://||;s|/.*||')/reference.png"
    RESULT=$(sudo -u "$USER" "$PYTHON" "$DEST/watch.py" --url "$URL_TEST" --comparer-pixel "$REF" 2>&1)
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
