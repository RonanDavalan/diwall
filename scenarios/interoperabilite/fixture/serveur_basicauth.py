#!/usr/bin/env python3
"""Serveur HTTP minimal émettant un vrai challenge Basic Auth (RFC 7617).

Fixture de non-régression pour --http-credentials (v1.21.0) — ne dépend
d'aucune cible tierce, comportement déterministe. Identifiants attendus :
diwall_fixture / diwall_fixture_password (aucune valeur sensible, usage
local uniquement).

Usage :
    python3 scenarios/interoperabilite/fixture/serveur_basicauth.py [port]
    # défaut : port 8643
"""
import base64
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

UTILISATEUR = "diwall_fixture"
MOT_DE_PASSE = "diwall_fixture_password"
REALM = "diwall-fixture"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        entete = self.headers.get("Authorization")
        if entete and self._identifiants_valides(entete):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Basic Auth OK</h1></body></html>")
            return
        self.send_response(401)
        self.send_header("WWW-Authenticate", f'Basic realm="{REALM}"')
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>401 Unauthorized</h1></body></html>")

    def _identifiants_valides(self, entete):
        if not entete.startswith("Basic "):
            return False
        try:
            decode = base64.b64decode(entete[len("Basic "):]).decode("utf-8")
        except Exception:
            return False
        return decode == f"{UTILISATEUR}:{MOT_DE_PASSE}"

    def log_message(self, format, *args):
        pass  # silence — la fixture n'a pas besoin de journaliser chaque requête


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8643
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()
