"""Chemins des dossiers et lecture des fichiers de configuration (config/*.yaml)."""

from pathlib import Path

import yaml

# Dossier racine du projet (le dossier qui contient « pipeline », « config », etc.)
RACINE = Path(__file__).resolve().parent.parent

DOSSIER_CONFIG = RACINE / "config"
DOSSIER_DATA = RACINE / "data"              # historique conservé dans le dépôt
DOSSIER_SITE_DATA = RACINE / "docs" / "data"  # fichiers JSON lus par le site


def lire_yaml(nom_fichier: str) -> dict:
    """Lit un fichier YAML du dossier config/ et le renvoie sous forme de dictionnaire."""
    with open(DOSSIER_CONFIG / nom_fichier, encoding="utf-8") as f:
        return yaml.safe_load(f)


def config_etf() -> dict:
    return lire_yaml("etf.yaml")


def parametres() -> dict:
    return lire_yaml("parametres.yaml")
