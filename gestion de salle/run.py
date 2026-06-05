"""
Lancement en mode développement avec rechargement automatique.

- Tailwind CSS watch  : recompile le CSS dès qu'un template change
- LiveReload          : rafraîchit le navigateur automatiquement
- Flask debug=True    : recharge le serveur si app.py change

Usage : python run.py
Adresse : http://127.0.0.1:5000
"""

import subprocess
import sys
import os
import signal
import threading
from livereload import Server

BASE = os.path.dirname(os.path.abspath(__file__))
NODE = os.path.join(BASE, "node_modules", "tailwindcss", "lib", "cli.js")

# ── 1. Tailwind watch en arrière-plan ─────────────────────────────────────────
tw = subprocess.Popen(
    ["node", NODE, "-i", "./static/css/input.css",
     "-o", "./static/css/tailwind.css", "--watch"],
    cwd=BASE,
)

# ── 2. Arrêt propre sur Ctrl+C ────────────────────────────────────────────────
def arreter(sig, frame):
    tw.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, arreter)
signal.signal(signal.SIGTERM, arreter)

# ── 3. Flask via livereload (rafraîchit le navigateur automatiquement) ─────────
from app import app

app.debug = True

server = Server(app.wsgi_app)

# Surveille les templates et Python → recharge la page
server.watch("templates/**/*.html")
server.watch("app.py")
server.watch("models/*.py")
server.watch("services/*.py")

# Surveille le CSS compilé → injecte le nouveau CSS sans rechargement complet
server.watch("static/css/tailwind.css")

server.serve(port=5000, host="0.0.0.0", debug=True)
