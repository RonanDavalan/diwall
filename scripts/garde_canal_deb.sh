# garde_canal_deb.sh — sourcé par install.sh, deploy.sh et uninstall.sh, jamais
# exécuté seul.
#
# Pourquoi : Diwall s'installe par deux canaux, le clone Git (ces scripts) et
# un paquet du système (Debian, RPM de Fedora et d'openSUSE, pacman d'Arch).
# Sur une machine où un paquet est installé, copier le code du clone dans
# /opt/diwall remplace des fichiers que le gestionnaire croit siens : la
# version réelle ne correspond plus à sa base, et la prochaine mise à jour ou
# suppression du paquet efface ou écrase ce qui a été copié, sans prévenir.
# uninstall.sh est concerné au même titre : il ferait `rm -rf /opt/diwall` et
# `userdel` sur des fichiers et un compte que le gestionnaire croit siens. La
# garde refuse avant toute écriture. Un paquet Debian retiré mais non purgé
# (état config-files) n'a plus de code dans /opt/diwall : il ne bloque pas.
# Le nom de la fonction reste celui de l'origine (trois scripts l'appellent).
# `rpm` peut exister sur une Debian : `rpm -q diwall` y échoue, pas de faux
# positif. Chaque gestionnaire n'est interrogé que s'il existe.

garde_canal_deb() {
    local action="${1:-installer}" etat gestionnaire="" retrait="" id=""
    etat="$(dpkg-query -W -f='${db:Status-Status}' diwall 2>/dev/null || true)"
    if [[ "$etat" == "installed" ]]; then
        gestionnaire="le paquet Debian (dpkg -l diwall)"
        retrait="sudo apt purge diwall"
    elif command -v rpm >/dev/null 2>&1 && rpm -q diwall >/dev/null 2>&1; then
        gestionnaire="le paquet RPM (rpm -q diwall)"
        [[ -r /etc/os-release ]] && id="$(. /etc/os-release; echo "${ID:-} ${ID_LIKE:-}")"
        case " $id " in
            *" fedora "*|*" rhel "*) retrait="sudo dnf remove diwall" ;;
            *" opensuse"*|*" suse "*|*" sles "*) retrait="sudo zypper remove diwall" ;;
            *) retrait="sudo dnf remove diwall (Fedora) ou sudo zypper remove diwall (openSUSE)" ;;
        esac
    elif command -v pacman >/dev/null 2>&1 && pacman -Q diwall >/dev/null 2>&1; then
        gestionnaire="le paquet pacman (pacman -Q diwall)"
        retrait="sudo pacman -R diwall"
    fi
    if [[ -n "$gestionnaire" ]]; then
        echo "ERREUR : Diwall est déjà installé par $gestionnaire." >&2
        if [[ "$action" == "désinstaller" ]]; then
            echo "  Ce script supprimerait des fichiers et un compte gérés par le gestionnaire de paquets." >&2
            echo "  Désinstaller par le paquet : $retrait" >&2
        else
            echo "  Ce script écraserait des fichiers gérés par le gestionnaire de paquets." >&2
            echo "  Mettre à jour le paquet par le gestionnaire du système." >&2
            echo "  Ou passer au canal clone : $retrait, puis relancer ce script." >&2
        fi
        exit 1
    fi
}
