#!/usr/bin/env bash
# deploy.sh — déploie ~/git/Diwall/Diwall/ vers /opt/diwall/
# Atomique, idempotent, préserve diwall.conf et les références watch.py
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DEST="/opt/diwall"
GROUPE="diwall"

# Fichiers de code à déployer (relatifs à REPO)
CODE_FILES=(
    shot.py
    watch.py
    rpa.py
    journal.py
    lib/__init__.py
    lib/journal.py
    lib/modeles.py
    lib/ntfy.py
    lib/profil_operateur.py
    lib/vision.py
    lib/vault.py
    lib/vector.py
)

# Répertoires de code — mode 755 (lisibles par tous)
# Justification : lib/*.py et scenarios/*.json sont publics sur GitHub, aucun secret.
# Restreindre à 750 root:diwall bloquerait l'opérateur hors session active du groupe.
DIRS_CODE=(
    "$DEST/lib"
    "$DEST/scenarios"
)

# Répertoires de données générées à l'exécution — mode 770 (groupe diwall en écriture)
# references/ : captures de dashboards authentifiés (sensibles)
# skills/ : skills versionnés (spécifiques à l'instance)
DIRS_RW=(
    "$DEST/references"
    "$DEST/skills"
)

# Fichiers à ne PAS toucher (config machine, données générées)
PRESERVE=(
    "$DEST/diwall.conf"
)

echo "=== Diwall — déploiement vers $DEST ==="
echo "    Source : $REPO"
echo ""

# ── Créer les répertoires /opt manquants (sudo) ───────────────────────────────
for d in "${DIRS_CODE[@]}"; do
    if [ ! -d "$d" ]; then
        sudo install -d -m 755 -o root -g "$GROUPE" "$d"
        echo "  Créé    : $d"
    fi
done
for d in "${DIRS_RW[@]}"; do
    if [ ! -d "$d" ]; then
        sudo install -d -m 770 -o root -g "$GROUPE" "$d"
        echo "  Créé    : $d"
    fi
done

# ── /opt/diwall/scripts : scripts utilitaires déployés ───────────────────────
if [ ! -d "$DEST/scripts" ]; then
    sudo install -d -m 755 -o root -g "$GROUPE" "$DEST/scripts"
    echo "  Créé    : $DEST/scripts"
fi

# ── /var/log/diwall : journal d'opérations v1.4 ───────────────────────────────
if [ ! -d "/var/log/diwall" ]; then
    sudo install -d -m 2770 -o root -g diwall /var/log/diwall
    echo "  Créé    : /var/log/diwall"
fi
if [ ! -d "/var/log/diwall/preuves" ]; then
    sudo install -d -m 2770 -o root -g diwall /var/log/diwall/preuves
    echo "  Créé    : /var/log/diwall/preuves"
fi

# ── /tmp/diwall : répertoire de l'opérateur, jamais sudo ─────────────────────
# Captures éphémères lues/écrites par l'utilisateur courant — pas besoin de root.
if [ ! -d "/tmp/diwall" ]; then
    install -d -m 700 "/tmp/diwall"
    echo "  Créé    : /tmp/diwall"
else
    chmod 700 /tmp/diwall
fi

# ── Copier les fichiers de code ───────────────────────────────────────────────
changed=0
for f in "${CODE_FILES[@]}"; do
    src="$REPO/$f"
    dst="$DEST/$f"
    if [ ! -f "$src" ]; then
        echo "  ABSENT  : $src (ignoré)"
        continue
    fi
    if diff -q "$src" "$dst" > /dev/null 2>&1; then
        echo "  Inchangé: $f"
    else
        sudo cp "$src" "$dst"
        echo "  Déployé : $f"
        changed=$((changed + 1))
    fi
done

# ── Déployer les scénarios d'exemple ─────────────────────────────────────────
for f in "$REPO"/scenarios/*.json "$REPO"/scenarios/*.yaml; do
    [ -f "$f" ] || continue
    base="$(basename "$f")"
    dst="$DEST/scenarios/$base"
    if diff -q "$f" "$dst" > /dev/null 2>&1; then
        echo "  Inchangé: scenarios/$base"
    else
        sudo cp "$f" "$dst"
        echo "  Déployé : scenarios/$base"
        changed=$((changed + 1))
    fi
done

# ── Déployer les skills (README + skills versionnés) ─────────────────────────
for f in "$REPO"/skills/*.json "$REPO"/skills/*.md; do
    [ -f "$f" ] || continue
    base="$(basename "$f")"
    dst="$DEST/skills/$base"
    if diff -q "$f" "$dst" > /dev/null 2>&1; then
        echo "  Inchangé: skills/$base"
    else
        sudo cp "$f" "$dst"
        echo "  Déployé : skills/$base"
        changed=$((changed + 1))
    fi
done

# ── Déployer docs/ (guides LLM, journal, retour d'expérience) ───────────────
if [ ! -d "$DEST/docs" ]; then
    sudo install -d -m 755 -o root -g "$GROUPE" "$DEST/docs"
    echo "  Créé    : $DEST/docs"
fi
for f in "$REPO"/docs/*.md; do
    [ -f "$f" ] || continue
    base="$(basename "$f")"
    dst="$DEST/docs/$base"
    if diff -q "$f" "$dst" > /dev/null 2>&1; then
        echo "  Inchangé: docs/$base"
    else
        sudo cp "$f" "$dst"
        echo "  Déployé : docs/$base"
        changed=$((changed + 1))
    fi
done

# ── Modèle de configuration : diwall-sample.conf (toujours écrit) ────────────
SAMPLE="$DEST/diwall-sample.conf"
sudo tee "$SAMPLE" > /dev/null << 'CONF_EOF'
{
  "vault_dir": "~/Vaults/Diwall"
}
CONF_EOF
echo "  Écrit   : diwall-sample.conf (modèle générique)"

# ── diwall.conf : config machine — ne jamais créer ni écraser ────────────────
CONF="$DEST/diwall.conf"
if [ ! -f "$CONF" ]; then
    echo ""
    echo "  ┌─ DIWALL.CONF ABSENT — ÉTAPE MANUELLE REQUISE ──────────────────────────┐"
    echo "  │  Aucune configuration vault active sur cette machine.                │"
    echo "  │  Toute opération vault échouera jusqu'à la création de ce fichier.   │"
    echo "  │                                                                      │"
    echo "  │    sudo cp $SAMPLE $CONF      │"
    echo "  │    sudo nano $CONF                                                   │"
    echo "  │    → {\"vault_dir\": \"~/Vaults/<PROJET>/Diwall\"}                       │"
    echo "  └──────────────────────────────────────────────────────────────────────┘"
else
    echo "  Préservé: diwall.conf (config machine existante)"
fi

# ── Permissions — une passe atomique ─────────────────────────────────────────
# chown puis chmod : si interruption après chown mais avant chmod, les fichiers
# appartiennent au bon groupe mais ont les droits de la copie (644 par défaut)
# ce qui est plus sûr que l'inverse.
sudo chown root:"$GROUPE" "$DEST"/*.py "$DEST"/lib/*.py "$DEST"/scripts/*.sh \
     "$DEST"/diwall-sample.conf "$DEST"/diwall.conf 2>/dev/null || true
sudo chown root:"$GROUPE" "$DEST"/scenarios/*.json "$DEST"/scenarios/*.yaml \
     2>/dev/null || true
sudo chown root:"$GROUPE" "$DEST"/skills/*.json "$DEST"/skills/*.md \
     2>/dev/null || true
sudo chown root:"$GROUPE" "$DEST"/docs/*.md 2>/dev/null || true

# lib/*.py : code public GitHub → 644 lisible par tous
sudo chmod 644 "$DEST"/*.py "$DEST"/lib/*.py "$DEST"/diwall-sample.conf 2>/dev/null || true
# diwall.conf : contient vault_dir (chemin sensible) → 640 groupe diwall uniquement
sudo chmod 640 "$DEST"/diwall.conf 2>/dev/null || true
# scenarios/ et skills/ : données d'instance (cibles, séquences vault) → 640
sudo chmod 640 "$DEST"/scenarios/*.json "$DEST"/scenarios/*.yaml 2>/dev/null || true
sudo chmod 640 "$DEST"/skills/*.json "$DEST"/skills/*.md 2>/dev/null || true
sudo chmod 644 "$DEST"/docs/*.md 2>/dev/null || true
sudo chmod 755 "$DEST"/shot.py "$DEST"/watch.py "$DEST"/rpa.py \
     "$DEST"/journal.py 2>/dev/null || true
sudo chmod 755 "$DEST"/scripts/setup-vault.sh \
     "$DEST"/scripts/migrate-vault.sh \
     "$DEST"/scripts/mount-vault.sh \
     "$DEST"/scripts/umount-vault.sh 2>/dev/null || true
echo ""
if [ "$changed" -gt 0 ]; then
    echo "=== $changed fichier(s) mis à jour — déploiement terminé ==="
else
    echo "=== Aucun changement — /opt/diwall/ est à jour ==="
fi
