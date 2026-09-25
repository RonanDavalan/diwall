# garde_canal_deb.sh — sourcé par install.sh, deploy.sh et uninstall.sh, jamais
# exécuté seul.
#
# Pourquoi : Diwall s'installe par deux canaux, le clone Git (ces scripts) et
# le paquet Debian. Sur une machine où le paquet est installé, copier le code
# du clone dans /opt/diwall remplace des fichiers que dpkg croit siens : la
# version réelle ne correspond plus à `dpkg -l`, et le prochain `apt purge` ou
# `apt install` du paquet efface ou écrase ce qui a été copié, sans prévenir.
# uninstall.sh est concerné au même titre : il ferait `rm -rf /opt/diwall` et
# `userdel` sur des fichiers et un compte que dpkg croit siens. La garde refuse
# avant toute écriture. Un paquet retiré mais non purgé
# (état config-files) n'a plus de code dans /opt/diwall : il ne bloque pas.

garde_canal_deb() {
    local action="${1:-installer}" etat
    etat="$(dpkg-query -W -f='${db:Status-Status}' diwall 2>/dev/null || true)"
    if [[ "$etat" == "installed" ]]; then
        echo "ERREUR : Diwall est déjà installé par le paquet Debian (dpkg -l diwall)." >&2
        if [[ "$action" == "désinstaller" ]]; then
            echo "  Ce script supprimerait des fichiers et un compte gérés par dpkg." >&2
            echo "  Désinstaller par le paquet : sudo apt purge diwall" >&2
        else
            echo "  Ce script écraserait des fichiers gérés par dpkg." >&2
            echo "  Mettre à jour le paquet : sudo apt install ./diwall_<version>-1_all.deb" >&2
            echo "  Ou passer au canal clone : sudo apt purge diwall, puis relancer ce script." >&2
        fi
        exit 1
    fi
}
