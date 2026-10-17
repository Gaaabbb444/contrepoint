"""Test de l'enregistrement sûr : deux écritures qui se croisent ne perdent aucune ligne.

On fabrique un faux « dépôt GitHub » local et deux copies de travail (comme
deux tâches automatiques). Les deux ajoutent une ligne au journal ; la
première envoie ; la seconde doit récupérer, fusionner et envoyer à son tour.
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git n'est pas installé")


def git(dossier: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=dossier, capture_output=True, text=True, check=True).stdout


def lancer_enregistrer(dossier: Path, message: str) -> int:
    env = {**os.environ, "PYTHONPATH": str(RACINE)}
    return subprocess.run(["python", "-m", "pipeline.enregistrer", "--message", message, "data"],
                          cwd=dossier, env=env, capture_output=True, text=True).returncode


def preparer_copie(origine: Path, dossier: Path) -> Path:
    subprocess.run(["git", "clone", "-q", str(origine), str(dossier)], check=True)
    git(dossier, "config", "user.name", "test")
    git(dossier, "config", "user.email", "test@example.com")
    return dossier


def test_deux_enregistrements_qui_se_croisent(tmp_path):
    origine = tmp_path / "origine.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origine)], check=True)
    # Contenu initial : le vrai .gitattributes du projet et un journal avec une ligne.
    depart = preparer_copie(origine, tmp_path / "depart")
    shutil.copy(RACINE / ".gitattributes", depart / ".gitattributes")
    (depart / "data").mkdir()
    (depart / "data" / "journal_execution.csv").write_text("horodatage_utc,etape,statut,message\n"
                                                           "2026-10-17 00:10:00,collecte_titres,ok,premier\n")
    git(depart, "add", "-A")
    git(depart, "commit", "-q", "-m", "départ")
    git(depart, "push", "-q", "origin", "main")

    tache_a = preparer_copie(origine, tmp_path / "a")
    tache_b = preparer_copie(origine, tmp_path / "b")
    with open(tache_a / "data" / "journal_execution.csv", "a") as f:
        f.write("2026-10-17 03:23:00,collecte_titres,ok,ligne de la tâche A\n")
    with open(tache_b / "data" / "journal_execution.csv", "a") as f:
        f.write("2026-10-17 04:41:00,performance,ok,ligne de la tâche B\n")

    assert lancer_enregistrer(tache_a, "tâche A") == 0
    # B n'a pas vu l'envoi de A : sans protection, son envoi serait refusé ou en conflit.
    assert lancer_enregistrer(tache_b, "tâche B") == 0

    verif = preparer_copie(origine, tmp_path / "verif")
    contenu = (verif / "data" / "journal_execution.csv").read_text()
    assert "premier" in contenu and "ligne de la tâche A" in contenu and "ligne de la tâche B" in contenu
    assert contenu.count("horodatage_utc") == 1


def test_rien_a_enregistrer(tmp_path):
    origine = tmp_path / "origine.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origine)], check=True)
    depart = preparer_copie(origine, tmp_path / "depart")
    (depart / "data").mkdir()
    (depart / "data" / "x.txt").write_text("x")
    git(depart, "add", "-A")
    git(depart, "commit", "-q", "-m", "départ")
    git(depart, "push", "-q", "origin", "main")
    assert lancer_enregistrer(depart, "rien") == 0
