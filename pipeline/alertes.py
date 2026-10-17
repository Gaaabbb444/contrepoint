"""Alertes envoyées au propriétaire du dépôt sous forme de « tickets » (issues) GitHub.

Lancement (dans GitHub Actions) :  python -m pipeline.alertes

GitHub envoie un e-mail à chaque nouveau ticket. Une alerte déjà ouverte n'est
pas recréée (même titre) : pas de répétition chaque nuit.

Alerte actuelle : un média dépasse le plafond (25 %) d'un groupe sur la
fenêtre de mesure (20 dernières séances). Décision prise le 17/10/2026 :
attendre 20 séances avant de choisir d'activer ou non la pondération plafonnée.
"""

import json
import subprocess
import sys

from pipeline.config import DOSSIER_SITE_DATA, parametres
from pipeline.sorties import lire_json

NOMS_GROUPES = {"marche": "marché", "esg": "ESG"}


def alertes_plafond(sentiment: dict, plafond: float, seances_cible: int) -> list[tuple[str, str]]:
    """Liste de (titre, texte) pour chaque média au-dessus du plafond."""
    alertes = []
    for groupe, rep in (sentiment.get("repartition_medias") or {}).items():
        for media, part in rep.get("parts_pct", {}).items():
            if part > plafond:
                titre = f"Plafond dépassé : {media} pèse plus de {plafond:g} % du groupe {NOMS_GROUPES.get(groupe, groupe)}"
                texte = (f"{media} représente {part} % des {rep['nb_articles']} articles du groupe "
                         f"{NOMS_GROUPES.get(groupe, groupe)} sur les {rep['nb_seances']} dernières séances "
                         f"(plafond : {plafond:g} %).\n\n"
                         f"Décision prévue : attendre {seances_cible} séances de données, puis choisir d'activer "
                         f"ou non la pondération plafonnée (déjà calculée en simulation : colonne "
                         f"« solde_avec_plafond » de data/sentiment_quotidien.csv).\n\n"
                         f"Ticket créé automatiquement par le traitement de nuit.")
                alertes.append((titre, texte))
    return alertes


def creer_tickets(alertes: list[tuple[str, str]]) -> int:
    """Crée les tickets qui n'existent pas encore (ouverts). Renvoie le nombre créé."""
    if not alertes:
        return 0
    ouverts = json.loads(subprocess.run(["gh", "issue", "list", "--state", "open", "--limit", "100", "--json", "title"],
                                        capture_output=True, text=True, check=True).stdout)
    titres_ouverts = {t["title"] for t in ouverts}
    crees = 0
    for titre, texte in alertes:
        if titre in titres_ouverts:
            print(f"Déjà signalé : {titre}")
            continue
        subprocess.run(["gh", "issue", "create", "--title", titre, "--body", texte], check=True)
        print(f"Ticket créé : {titre}")
        crees += 1
    return crees


def main() -> int:
    p = parametres()["sentiment"]
    sentiment = lire_json(DOSSIER_SITE_DATA / "sentiment.json") or {}
    alertes = alertes_plafond(sentiment, p["plafond_media_pct"], p["repartition_seances"])
    if not alertes:
        print("Aucun média au-dessus du plafond.")
        return 0
    try:
        creer_tickets(alertes)
    except (subprocess.CalledProcessError, FileNotFoundError) as erreur:
        print(f"::warning::Impossible de créer le ticket d'alerte : {erreur}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
