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

echo
echo "=== Résumé ==="
if [[ $NB_FUITES -eq 0 ]]; then
    echo "OK — aucune fuite détectée. Publication possible."
    exit 0
fi

echo "FUITES par pattern :"
for label in "${!FUITES_PAR_PATTERN[@]}"; do
    printf "  %-30s %s occurrences\n" "$label" "${FUITES_PAR_PATTERN[$label]}"
done
echo
echo "Total : $NB_FUITES occurrence(s) sur $NB_FICHIERS fichier(s) — publication BLOQUÉE."
exit 1
