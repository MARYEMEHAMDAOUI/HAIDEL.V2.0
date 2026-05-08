"""
PythonAnywhere WSGI configuration
Dans PythonAnywhere : Web → WSGI configuration file → remplacer par ce contenu
Modifiez USERNAME par votre nom d'utilisateur PythonAnywhere
"""
import sys, os

# ── Chemin vers votre projet ──────────────────────────────────────────────────
# Remplacez 'USERNAME' par votre username PythonAnywhere
PROJECT_PATH = '/home/USERNAME/haidel'

if PROJECT_PATH not in sys.path:
    sys.path.insert(0, PROJECT_PATH)

os.chdir(PROJECT_PATH)

# ── Import de l'application Flask ─────────────────────────────────────────────
from app import app as application
