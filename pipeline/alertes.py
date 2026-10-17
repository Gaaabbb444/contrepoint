"""Alertes envoyées au propriétaire du dépôt sous forme de « tickets » (issues) GitHub.

Lancement (dans GitHub Actions) :  python -m pipeline.alertes

GitHub envoie un e-mail à chaque nouveau ticket. Une alerte déjà ouverte n'est
pas recréée (même titre) : pas de répétition chaque nuit.

Alertes :
1. Un média dépasse le plafond (25 %) d'un groupe sur la fenêtre de mesure
   (20 dernières séances). Décision prise le 17/10/2026 : attendre 20 séances
   avant de choisir d'activer ou non la pondération plafonnée.
2. Un flux RSS actif tombe en panne de façon répétée (au moins 3 jours
   différents sur les 5 derniers) : il faut alors le remplacer ou le retirer.
"""

import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from pipeline.config import DOSSIER_SITE_DATA, lire_yaml, parametres
from pipeline.journal import FICHIER_JOURNAL
from pipeline.sorties import lire_json

PARIS = ZoneInfo("Europe/Paris")

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


def alertes_flux(journal: pd.DataFrame, flux_actifs: set[str], aujourdhui: date,
                 jours_min: int, fenetre_jours: int) -> list[tuple[str, str]]:
    """Liste de (titre, texte) pour chaque flux actif en panne sur au moins `jours_min`
    jours différents (heure de Paris) parmi les `fenetre_jours` derniers jours."""
    pannes = journal[journal["etape"].str.startswith("flux:") & (journal["statut"] != "ok")].copy()
    if pannes.empty:
        return []
    instants = pd.to_datetime(pannes["horodatage_utc"]).dt.tz_localize("UTC").dt.tz_convert(PARIS)
    pannes["jour"] = instants.dt.date
    debut = aujourdhui - timedelta(days=fenetre_jours - 1)
    pannes = pannes[(pannes["jour"] >= debut) & (pannes["jour"] <= aujourdhui)]
    alertes = []
    for etape, lignes in pannes.groupby("etape"):
        nom = etape.removeprefix("flux:")
        jours = sorted(set(lignes["jour"]))
        if nom not in flux_actifs or len(jours) < jours_min:
            continue
        titre = f"Flux en panne : {nom}"
        texte = (f"Le flux « {nom} » a échoué sur {len(jours)} jours différents parmi les {fenetre_jours} derniers "
                 f"({', '.join(j.strftime('%d/%m') for j in jours)} ; {len(lignes)} relevés en échec).\n\n"
                 f"Dernière erreur : {lignes['message'].iloc[-1]}\n\n"
                 f"À décider : le remplacer par un flux équivalent, ou le retirer. Dans les deux cas, modifier "
                 f"config/flux_rss.yaml (actif: false pour le retirer) et dater le changement dans l'historique "
                 f"des sources de contenu/methodologie.md.\n\n"
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
    if FICHIER_JOURNAL.exists():
        journal = pd.read_csv(FICHIER_JOURNAL, encoding="utf-8-sig", dtype=str).fillna("")
        actifs = {f["nom"] for f in lire_yaml("flux_rss.yaml")["flux"] if f.get("actif", True)}
        aujourdhui = datetime.now(timezone.utc).astimezone(PARIS).date()
        pannes = alertes_flux(journal, actifs, aujourdhui, p["flux_panne_jours_min"], p["flux_panne_fenetre_jours"])
        if not pannes:
            print("Aucun flux en panne durable.")
        alertes += pannes
    if not alertes:
        return 0
    try:
        creer_tickets(alertes)
    except (subprocess.CalledProcessError, FileNotFoundError) as erreur:
        print(f"::warning::Impossible de créer le ticket d'alerte : {erreur}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
