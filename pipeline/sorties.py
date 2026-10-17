"""Écriture prudente des fichiers JSON lus par le site.

Règle d'or : on n'écrase JAMAIS un fichier valide par un fichier douteux.
Si les nouvelles données ne passent pas les contrôles, l'ancien fichier reste
en place et le site continue d'afficher les dernières données valides.
"""

import json
import os
from datetime import date, datetime
from pathlib import Path


def _serialiser(objet):
    """Permet d'écrire les dates dans le JSON (au format AAAA-MM-JJ)."""
    if isinstance(objet, (date, datetime)):
        return objet.isoformat()
    raise TypeError(f"Type non sérialisable : {type(objet)}")


def lire_json(chemin: Path) -> dict | None:
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def ecrire_json_si_valide(chemin: Path, donnees: dict, controles: list[tuple[bool, str]]) -> tuple[bool, str]:
    """Écrit `donnees` dans `chemin` seulement si tous les contrôles sont vrais.

    `controles` est une liste de couples (condition, explication). Renvoie
    (True, "") si le fichier a été écrit, sinon (False, raison du refus).
    L'écriture passe par un fichier temporaire puis un renommage : en cas de
    coupure au milieu, l'ancien fichier n'est jamais à moitié écrasé.
    """
    for condition, explication in controles:
        if not condition:
            return False, explication
    try:
        # allow_nan=False : refuse les valeurs « NaN » ou infinies, signe d'un calcul raté.
        texte = json.dumps(donnees, ensure_ascii=False, indent=1, allow_nan=False, default=_serialiser)
    except ValueError as erreur:
        return False, f"valeur non numérique dans les données : {erreur}"
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(".tmp")
    temporaire.write_text(texte, encoding="utf-8")
    os.replace(temporaire, chemin)
    return True, ""
