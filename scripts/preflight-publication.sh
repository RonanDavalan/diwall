#!/usr/bin/env bash
# preflight-publication.sh — vérifie l'absence de tokens d'infrastructure réelle
# dans les fichiers Markdown du dépôt avant un push public.
#
# Usage :
#   bash scripts/preflight-publication.sh [--verbose]
#
# Sortie :
#   exit 0 — aucune fuite, publication possible.
#   exit 1 — au moins une fuite détectée, publication bloquée.
#
# Doctrine : tout token d'infrastructure (host, IP, tenant, client, chemins
# nominaux) doit avoir été substitué par un placeholder de la liste blanche
# définie dans ~/git/Diwall/_CADRE/SPECIFICATIONS/PROCEDURES_LLM/INDEX.md.
# Voir aussi 27_PROCESSUS_PUBLICATION_GITHUB.md.

set -euo pipefail

VERBOSE=0
if [[ "${1:-}" == "--verbose" ]]; then
    VERBOSE=1
fi

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# ── Liste des patterns interdits ──────────────────────────────────────────────
# Format : "label;;;regex_etendue;;;recommandation"
# Séparateur ';;;' choisi pour ne pas entrer en collision avec les '|' des
# alternations regex. Maintenue en tête du script (pas d'input externe).
PATTERNS=(
    "host admin LAN;;;\\bsillage\\.ike4\\.local\\b;;;substituer par __HOST_ADMIN__"
    "vitrine opérateur;;;\\bsillage\\.davalan\\.fr\\b;;;substituer par __HOST_ADMIN__"
    "host clone WP;;;\\bclone\\.davalan\\.fr\\b;;;substituer par __HOST_ADMIN__"
    "domaine opérateur;;;\\bdavalan\\.fr\\b;;;substituer par __DOMAINE_OPERATEUR__"
    "host admin IKE4;;;\\bIKE4\\b;;;substituer par __HOST_ADMIN__"
    "host VPS nominal;;;\\bVpsL\\b;;;substituer par __HOST_VPS__"
    "tenant nominal;;;\\bronan-davalan\\b;;;substituer par __TENANT__"
    "client nominal;;;\\bprojet-vitrine\\b;;;substituer par __CLIENT_SANCTUARISE__"
    "prénom opérateur;;;\\bRonan\\b;;;reformuler (« l'opérateur ») ou pseudonymiser"
    "username dans chemin;;;/home/ron(/|\\b);;;relativiser en ~ ou ~/<utilisateur>/"
    "vault projet nommé;;;~/Vaults/Sillage/;;;substituer par ~/Vaults/<PROJET>/"
    "IP LAN 192.168.x.x;;;\\b192\\.168\\.[0-9]+\\.[0-9]+\\b;;;substituer par __IP_LAN__"
    "IP LAN 10.x.x.x;;;\\b10\\.[0-9]+\\.[0-9]+\\.[0-9]+\\b;;;substituer par __IP_LAN__"
    "IP LAN 172.16-31.x.x;;;\\b172\\.(1[6-9]|2[0-9]|3[0-1])\\.[0-9]+\\.[0-9]+\\b;;;substituer par __IP_LAN__"
    "IP VPS nominale;;;\\b87\\.106\\.213\\.110\\b;;;substituer par __IP_VPS__"
)

# ── Exceptions documentées ────────────────────────────────────────────────────
# Format : "chemin_fichier;;;label_pattern;;;raison"
# Un match qui satisfait <fichier == chemin_fichier ET label == label_pattern>
# est silencieusement ignoré. À documenter explicitement : tout ajout exige une
# raison pérenne (typiquement : crédit auteur, citation d'une norme, etc.).
EXCEPTIONS=(
    "./README.md;;;prénom opérateur;;;crédit auteur public dans la section Credits"
    "./README.md;;;domaine opérateur;;;diwall.davalan.fr est le domaine public du projet Diwall"
)

# ── Découverte du périmètre ───────────────────────────────────────────────────
# Tous les fichiers .md du dépôt, en excluant .git, venv, node_modules.
mapfile -d '' FICHIERS < <(find . -type f -name '*.md' \
    -not -path './.git/*' \
    -not -path './venv/*' \
    -not -path './node_modules/*' \
    -print0)

NB_FICHIERS=${#FICHIERS[@]}

echo "=== Diwall preflight publication ==="
echo "Dépôt   : $REPO_ROOT"
echo "Périmètre : $NB_FICHIERS fichiers .md (hors .git/, venv/, node_modules/)"
echo "Patterns : ${#PATTERNS[@]} interdits"
echo

# ── Audit positif (verbose) : compter les placeholders rencontrés ─────────────
if [[ $VERBOSE -eq 1 ]]; then
    echo "--- Placeholders en place (audit positif) ---"
    if [[ $NB_FICHIERS -gt 0 ]]; then
        # Collecte tous les __XXX_YYY__ uniques et compte les occurrences.
        grep -hoE '__[A-Z][A-Z_]+__' "${FICHIERS[@]}" 2>/dev/null \
            | sort | uniq -c | sort -rn \
            | awk '{printf "  %-30s %s occurrences\n", $2, $1}' || true
    fi
    echo
fi

# ── Audit négatif : recherche des fuites ──────────────────────────────────────
NB_FUITES=0
declare -A FUITES_PAR_PATTERN

if [[ $NB_FICHIERS -gt 0 ]]; then
    for entree in "${PATTERNS[@]}"; do
        label="${entree%%;;;*}"
        reste="${entree#*;;;}"
        regex="${reste%%;;;*}"
        recommandation="${reste#*;;;}"
        # grep -E : regex étendues ; -H : préfixer chemin ; -n : numéro ligne
        # On ignore le code retour 1 (= aucune correspondance) avec || true
        # Filtre additionnel : on saute les lignes où le pattern est dans un
        # exemple « literal placeholder explanation » (ex. « ex. `IKE4` »).
        # Approche simple : on signale tout match, c'est à l'opérateur d'arbitrer.
        if matches=$(grep -EnH "$regex" "${FICHIERS[@]}" 2>/dev/null); then
            while IFS= read -r ligne; do
                [[ -z "$ligne" ]] && continue
                fichier_match="${ligne%%:*}"
                # Vérifier si <fichier_match × label> a une exception documentée
                exempte=0
                for exc in "${EXCEPTIONS[@]}"; do
                    exc_fichier="${exc%%;;;*}"
                    exc_reste="${exc#*;;;}"
                    exc_label="${exc_reste%%;;;*}"
                    exc_raison="${exc_reste#*;;;}"
                    if [[ "$fichier_match" == "$exc_fichier" && "$label" == "$exc_label" ]]; then
                        exempte=1
                        [[ $VERBOSE -eq 1 ]] && echo "SKIP  [$label] $ligne (exception : $exc_raison)"
                        break
                    fi
                done
                if [[ $exempte -eq 0 ]]; then
                    NB_FUITES=$((NB_FUITES + 1))
                    FUITES_PAR_PATTERN["$label"]=$(( ${FUITES_PAR_PATTERN["$label"]:-0} + 1 ))
                    echo "FUITE [$label] $ligne"
                    echo "       → $recommandation"
                fi
            done <<< "$matches"
        fi
    done
fi

# ── Audit secrets dans les YAML publiés sous diwall.conf.d/ (v1.3) ────────────
# Cible : operateur.exemple.yaml (template public versionné). Les profils
# nominaux operateur.*.yaml sont gitignorés et n'entrent pas dans le scope.
# Patterns interdits : clés YAML qui exposeraient un secret en clair.
PATTERNS_SECRETS_YAML=(
    "mot de passe;;;^[[:space:]]*(password|passwd|mot_de_passe)[[:space:]]*:;;;jamais de credential en clair dans un profil opérateur"
    "token API;;;^[[:space:]]*(token|api_key|apikey|api_token|access_token)[[:space:]]*:;;;jamais de credential en clair dans un profil opérateur"
    "secret générique;;;^[[:space:]]*secret[[:space:]]*:;;;jamais de credential en clair dans un profil opérateur"
    "clé privée;;;^[[:space:]]*(private_key|privkey|ssh_key)[[:space:]]*:;;;clé privée à conserver hors du profil"
    "marqueur PEM;;;-----BEGIN [A-Z ]*PRIVATE KEY-----;;;clé privée à conserver hors du profil"
)

mapfile -d '' YAMLS < <(find ./diwall.conf.d -type f -name '*.yaml' -print0 2>/dev/null)
NB_YAMLS=${#YAMLS[@]}
echo "--- Audit YAML profil opérateur (v1.3) ---"
echo "Périmètre YAML : $NB_YAMLS fichier(s) sous diwall.conf.d/"

if [[ $NB_YAMLS -gt 0 ]]; then
    for entree in "${PATTERNS_SECRETS_YAML[@]}"; do
        label="${entree%%;;;*}"
        reste="${entree#*;;;}"
        regex="${reste%%;;;*}"
        recommandation="${reste#*;;;}"
        if matches=$(grep -EnH "$regex" "${YAMLS[@]}" 2>/dev/null); then
            while IFS= read -r ligne; do
                [[ -z "$ligne" ]] && continue
                NB_FUITES=$((NB_FUITES + 1))
                FUITES_PAR_PATTERN["$label"]=$(( ${FUITES_PAR_PATTERN["$label"]:-0} + 1 ))
                echo "FUITE [$label] $ligne"
                echo "       → $recommandation"
            done <<< "$matches"
        fi
    done
fi

echo

# ── Smoke test installation vierge ────────────────────────────────────────────
# Vérifie que le code déployé dans /opt/diwall/ est fonctionnel avant push.
# Requis à chaque fin de session, avant tout git push ou création de release.
# Pour un test depuis un clone GitHub propre : bash scripts/install.sh
echo "--- Smoke test /opt/diwall/ ---"
DEST="/opt/diwall"
PYTHON="$DEST/venv/bin/python3"
URL_SMOKE="https://example.com"
NB_ECHECS=0

if [ ! -f "$PYTHON" ]; then
    echo "SKIP — $DEST/venv absent (installation non déployée)"
else
    # shot.py (écrit dans /tmp/diwall/ — pas de groupe requis)
    RESULT=$("$PYTHON" "$DEST/shot.py" --url "$URL_SMOKE" --som 2>&1)
    if echo "$RESULT" | grep -q '"succes": true'; then
        echo "OK   — shot.py --som"
    else
        echo "FAIL — shot.py --som"
        NB_ECHECS=$((NB_ECHECS + 1))
    fi

    # watch.py écrit dans references/ (770 root:diwall).
    # Si le groupe diwall n'est pas actif dans la session courante (cas typique
    # après usermod -aG diwall dans la même session sans reconnexion), on utilise
    # sg diwall pour activer le groupe le temps de la commande.
    if id -Gn 2>/dev/null | tr ' ' '\n' | grep -qx "diwall"; then
        RUN_WATCH_REF="$PYTHON $DEST/watch.py --url $URL_SMOKE --sauver-reference"
        RUN_WATCH_CMP="$PYTHON $DEST/watch.py --url $URL_SMOKE --comparer-pixel $DEST/references/example.com/reference.png"
    else
        RUN_WATCH_REF="sg diwall -c \"$PYTHON $DEST/watch.py --url $URL_SMOKE --sauver-reference\""
        RUN_WATCH_CMP="sg diwall -c \"$PYTHON $DEST/watch.py --url $URL_SMOKE --comparer-pixel $DEST/references/example.com/reference.png\""
    fi

    # watch.py --sauver-reference
    RESULT=$(eval "$RUN_WATCH_REF" 2>&1)
    if echo "$RESULT" | grep -q '"succes": true'; then
        echo "OK   — watch.py --sauver-reference"
    else
        echo "FAIL — watch.py --sauver-reference"
        NB_ECHECS=$((NB_ECHECS + 1))
    fi

    # watch.py --comparer-pixel
    # sudo test -f : references/ est en 770 root:diwall — le shell courant
    # ne peut pas traverser le répertoire si le groupe diwall n'est pas actif.
    REF="$DEST/references/example.com/reference.png"
    if sudo test -f "$REF"; then
        RESULT=$(eval "$RUN_WATCH_CMP" 2>&1)
        if echo "$RESULT" | grep -q '"succes": true'; then
            echo "OK   — watch.py --comparer-pixel"
        else
            echo "FAIL — watch.py --comparer-pixel"
            NB_ECHECS=$((NB_ECHECS + 1))
        fi
    else
        echo "SKIP — watch.py --comparer-pixel (référence absente, lancez --sauver-reference d'abord)"
    fi

    if [ "$NB_ECHECS" -gt 0 ]; then
        echo "$NB_ECHECS smoke test(s) échoué(s) — publication BLOQUÉE."
        NB_FUITES=$((NB_FUITES + NB_ECHECS))
    fi
fi

echo
echo "=== Résumé ==="
if [[ $NB_FUITES -eq 0 ]]; then
    echo "OK — aucune fuite, smoke test réussi. Publication possible."
    exit 0
fi

echo "FUITES par pattern :"
for label in "${!FUITES_PAR_PATTERN[@]}"; do
    printf "  %-30s %s occurrences\n" "$label" "${FUITES_PAR_PATTERN[$label]}"
done
echo
echo "Total : $NB_FUITES occurrence(s) — publication BLOQUÉE."
exit 1
