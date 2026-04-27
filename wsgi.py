import sys
import os

# Rendre le dossier "gestion de salle" importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "gestion de salle"))

from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
