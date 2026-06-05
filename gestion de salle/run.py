"""
Lancement en mode développement.
Démarre Tailwind CSS watch + serveur Flask simultanément.
Usage : python run.py
"""

import subprocess
import sys
import os
import signal

BASE = os.path.dirname(os.path.abspath(__file__))
NODE = os.path.join(BASE, "node_modules", "tailwindcss", "lib", "cli.js")

tw = subprocess.Popen([
    "node", NODE,
    "-i", "./static/css/input.css",
    "-o", "./static/css/tailwind.css",
    "--watch",
], cwd=BASE)

fl = subprocess.Popen([sys.executable, "main.py"], cwd=BASE)

def arreter(sig, frame):
    tw.terminate()
    fl.terminate()
    sys.exit(0)

signal.signal(signal.SIGINT, arreter)
signal.signal(signal.SIGTERM, arreter)

fl.wait()
tw.terminate()
