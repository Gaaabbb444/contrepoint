"""Collecte et notation des titres d'actualité (exécutée toutes les 3 heures).

Lancement dans GitHub Actions :   python -m pipeline.collecte_titres
Test sur l'ordinateur (SANS le modèle, rien n'est enregistré) :
                                  python -m pipeline.collecte_titres --sans-modele

Étapes :
1. lecture de chaque flux RSS (une panne de flux n'arrête pas les autres) ;
2. nettoyage (HTML, liens), filtre des articles trop anciens ;
3. suppression des doublons (même lien, ou titre quasi identique), y compris
   par rapport aux titres déjà enregistrés les jours précédents ;
4. notation par FinBERT du texte « titre + début du résumé » ;
5. enregistrement du titre, de la source, du lien, de la date et du score.

DROIT D'AUTEUR (correction C) : le résumé ne sert qu'au calcul. Il n'est
JAMAIS écrit sur le disque : seules les colonnes de COLONNES_CSV le sont.
"""

import argparse
import csv
import hashlib
import html
import re
import sys
from calendar import timegm
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import feedparser
import pandas as pd
import requests
from rapidfuzz import fuzz, process

from pipeline import fenetres
from pipeline.config import DOSSIER_DATA, lire_yaml, parametres
from pipeline.journal import Journal

DOSSIER_TITRES = DOSSIER_DATA / "titres"
NAVIGATEUR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"

# Colonnes enregistrées. Le résumé n'y figure volontairement pas.
COLONNES_CSV = ["id", "groupe", "source", "type", "titre", "lien", "date_publication_utc",
                "date_approximative", "seance", "p_positif", "p_neutre", "p_negatif", "classe", "collecte_utc"]


# -----------------------------------------------------------------------------
# Nettoyage
# -----------------------------------------------------------------------------

def nettoyer_texte(texte: str | None) -> str:
    """Retire les balises HTML et les espaces superflus, décode les entités (&amp; → &)."""
    if not texte:
        return ""
    texte = re.sub(r"<[^>]+>", " ", texte)
    return re.sub(r"\s+", " ", html.unescape(texte)).strip()


def lien_canonique(url: str) -> str:
    """Supprime du lien les paramètres de suivi publicitaire (utm_…) et l'ancre (#…)."""
    morceaux = urlsplit(url.strip())
    params = [(k, v) for k, v in parse_qsl(morceaux.query) if not k.lower().startswith(("utm_", "mod", "cmpid"))]
    return urlunsplit((morceaux.scheme, morceaux.netloc.lower(), morceaux.path, urlencode(params), ""))


def normaliser_titre(titre: str) -> str:
    """Version « squelette » d'un titre pour comparer : minuscules, sans ponctuation."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", titre.lower())).strip()


def titre_sans_source(titre: str, source: str) -> str:
    """Google Actualités ajoute « - Nom du média » à la fin des titres : on le retire."""
    suffixe = f" - {source}"
    return titre[: -len(suffixe)].strip() if source and titre.endswith(suffixe) else titre


def texte_a_analyser(titre: str, resume: str, mots_max: int) -> str:
    """Texte donné à FinBERT : le titre, suivi du début du résumé s'il apporte autre chose."""
    resume = " ".join(resume.split()[:mots_max])
    if not resume or normaliser_titre(resume).startswith(normaliser_titre(titre)):
        return titre
    return f"{titre}. {resume}"


# -----------------------------------------------------------------------------
# Lecture des flux
# -----------------------------------------------------------------------------

def lire_flux(contenu: bytes | str, flux: dict, maintenant: datetime, age_max_heures: int) -> list[dict]:
    """Transforme le contenu d'un flux RSS en liste d'articles (avec résumé, en mémoire seulement)."""
    analyse = feedparser.parse(contenu)
    articles = []
    for entree in analyse.entries:
        titre = nettoyer_texte(entree.get("title"))
        lien = entree.get("link", "")
        if not titre or not lien:
            continue
        source = flux["nom"]
        if flux["type"] == "agregateur":
            # Le vrai média est indiqué dans <source> ; le résumé n'est qu'une copie du titre.
            source = nettoyer_texte(entree.get("source", {}).get("title")) or flux["nom"]
            titre = titre_sans_source(titre, source)
            resume = ""
        else:
            resume = nettoyer_texte(entree.get("summary"))
        date_struct = entree.get("published_parsed") or entree.get("updated_parsed")
        if date_struct:
            date_pub = datetime.fromtimestamp(timegm(date_struct), tz=timezone.utc)
            approximative = False
        else:
            # Pas de date dans le flux : on prend l'heure de collecte (à 3 h près).
            date_pub, approximative = maintenant, True
        if date_pub < maintenant - timedelta(hours=age_max_heures) or date_pub > maintenant + timedelta(hours=1):
            continue
        articles.append({"groupe": flux["groupe"], "source": source, "type": flux["type"], "titre": titre,
                         "resume": resume, "lien": lien_canonique(lien), "date_publication": date_pub,
                         "date_approximative": approximative})
    return articles


def telecharger_flux(flux: dict) -> bytes:
    r = requests.get(flux["url"], headers={"User-Agent": NAVIGATEUR}, timeout=25)
    r.raise_for_status()
    return r.content


# -----------------------------------------------------------------------------
# Dédoublonnage
# -----------------------------------------------------------------------------

def dedoublonner(articles: list[dict], deja_vus: dict[str, list[tuple[str, str]]], seuil: int) -> tuple[list[dict], int]:
    """Supprime les doublons, groupe par groupe.

    `deja_vus` : pour chaque groupe, liste de (lien, titre normalisé) déjà
    enregistrés. Les flux directs passent avant les agrégateurs : si un même
    article apparaît dans les deux, c'est la version du média lui-même qui
    est gardée. Un même article peut en revanche compter dans les deux groupes
    (marché et ESG), car il concerne les deux indicateurs.
    """
    ordre = sorted(articles, key=lambda a: (a["type"] != "direct", a["date_publication"]))
    gardes, doublons = [], 0
    liens = {g: {l for l, _ in v} for g, v in deja_vus.items()}
    titres = {g: [t for _, t in v] for g, v in deja_vus.items()}
    for art in ordre:
        g = art["groupe"]
        liens.setdefault(g, set())
        titres.setdefault(g, [])
        squelette = normaliser_titre(art["titre"])
        if art["lien"] in liens[g] or (titres[g] and process.extractOne(
                squelette, titres[g], scorer=fuzz.token_sort_ratio, score_cutoff=seuil)):
            doublons += 1
            continue
        gardes.append(art)
        liens[g].add(art["lien"])
        titres[g].append(squelette)
    return gardes, doublons


def titres_deja_enregistres(jours: int, maintenant: datetime) -> dict[str, list[tuple[str, str]]]:
    """Liens et titres déjà enregistrés sur les derniers jours, par groupe."""
    vus: dict[str, list[tuple[str, str]]] = {}
    for fichier in fichiers_recents(jours, maintenant):
        with open(fichier, encoding="utf-8-sig", newline="") as f:
            for ligne in csv.DictReader(f):
                vus.setdefault(ligne["groupe"], []).append((ligne["lien"], normaliser_titre(ligne["titre"])))
    return vus


def chemin_fichier_jour(jour: str) -> Path:
    """data/titres/AAAA/MM/AAAA-MM-JJ.csv (jour de publication, heure de Paris)."""
    return DOSSIER_TITRES / jour[:4] / jour[5:7] / f"{jour}.csv"


def fichiers_recents(jours: int, maintenant: datetime) -> list[Path]:
    dates = pd.date_range(maintenant.date() - timedelta(days=jours), maintenant.date() + timedelta(days=1))
    return [p for p in (chemin_fichier_jour(d.date().isoformat()) for d in dates) if p.exists()]


# -----------------------------------------------------------------------------
# Notation et enregistrement
# -----------------------------------------------------------------------------

class ModeleFactice:
    """Remplace FinBERT pour les tests sur l'ordinateur : renvoie toujours « neutre »."""

    def predire(self, textes: list[str]) -> list[dict]:
        return [{"positif": 0.0, "neutre": 1.0, "negatif": 0.0} for _ in textes]


def noter(articles: list[dict], modele, mots_max: int, code_calendrier: str, maintenant: datetime) -> list[dict]:
    """Ajoute à chaque article ses probabilités FinBERT, sa classe et sa séance. Retire le résumé."""
    if not articles:
        return []
    textes = [texte_a_analyser(a["titre"], a["resume"], mots_max) for a in articles]
    probas = modele.predire(textes)
    seances = fenetres.seance_de(pd.Series([a["date_publication"] for a in articles]), code_calendrier)
    lignes = []
    for art, p, seance in zip(articles, probas, seances):
        cle = f"{art['groupe']}|{art['lien']}"
        lignes.append({
            "id": hashlib.sha1(cle.encode("utf-8")).hexdigest()[:12],
            "groupe": art["groupe"], "source": art["source"], "type": art["type"],
            "titre": art["titre"], "lien": art["lien"],
            "date_publication_utc": art["date_publication"].strftime("%Y-%m-%dT%H:%M:%SZ"),
            "date_approximative": art["date_approximative"],
            "seance": str(seance),
            "p_positif": round(p["positif"], 4), "p_neutre": round(p["neutre"], 4), "p_negatif": round(p["negatif"], 4),
            "classe": max(("positif", "neutre", "negatif"), key=lambda c: p[c]),
            "collecte_utc": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
        # Le résumé n'est recopié nulle part : il disparaît avec `art`.
    return lignes


def enregistrer(lignes: list[dict]) -> int:
    """Ajoute les lignes aux fichiers du jour de publication (heure de Paris)."""
    par_jour: dict[str, list[dict]] = {}
    for l in lignes:
        jour = pd.Timestamp(l["date_publication_utc"]).tz_convert("Europe/Paris").date().isoformat()
        par_jour.setdefault(jour, []).append(l)
    for jour, contenu in par_jour.items():
        chemin = chemin_fichier_jour(jour)
        chemin.parent.mkdir(parents=True, exist_ok=True)
        nouveau = not chemin.exists()
        with open(chemin, "a", encoding="utf-8-sig", newline="") as f:
            ecrivain = csv.DictWriter(f, fieldnames=COLONNES_CSV, extrasaction="raise")
            if nouveau:
                ecrivain.writeheader()
            ecrivain.writerows(contenu)
    return len(lignes)


# -----------------------------------------------------------------------------
# Programme principal
# -----------------------------------------------------------------------------

def collecter(modele, journal: Journal, ecrire: bool = True, maintenant: datetime | None = None) -> dict:
    maintenant = maintenant or datetime.now(timezone.utc)
    cfg_flux = lire_yaml("flux_rss.yaml")
    p = parametres()["sentiment"]

    bruts, bilan_flux = [], {}
    for flux in cfg_flux["flux"]:
        if not flux.get("actif", True) or (flux["type"] == "agregateur" and not cfg_flux.get("agregateurs_actifs", True)):
            continue
        try:
            articles = lire_flux(telecharger_flux(flux), flux, maintenant, p["age_max_heures"])
            bruts.extend(articles)
            bilan_flux[flux["nom"]] = len(articles)
        except Exception as erreur:  # noqa: BLE001 — un flux en panne n'arrête pas les autres
            bilan_flux[flux["nom"]] = None
            journal.noter(f"flux:{flux['nom']}", "avertissement", f"flux indisponible : {erreur}")

    deja_vus = titres_deja_enregistres(p["doublons_jours"], maintenant)
    nouveaux, doublons = dedoublonner(bruts, deja_vus, p["seuil_doublon"])
    lignes = noter(nouveaux, modele, p["mots_max_resume"], p["calendrier_bourse"], maintenant)
    if ecrire:
        enregistrer(lignes)

    bilan = {"lus": len(bruts), "doublons": doublons, "nouveaux": len(lignes),
             "par_groupe": pd.Series([l["groupe"] for l in lignes], dtype=str).value_counts().to_dict(),
             "flux_en_panne": [n for n, v in bilan_flux.items() if v is None], "par_flux": bilan_flux}
    statut = "ok" if len([v for v in bilan_flux.values() if v is not None]) > 0 else "echec"
    journal.noter("collecte_titres", statut,
                  f"{bilan['lus']} articles lus, {doublons} doublons, {bilan['nouveaux']} nouveaux "
                  f"{bilan['par_groupe']}, {len(bilan['flux_en_panne'])} flux en panne")
    return bilan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sans-modele", action="store_true",
                        help="test local : pas de FinBERT, aucune écriture sur le disque")
    args = parser.parse_args()
    journal = Journal()
    if args.sans_modele:
        bilan = collecter(ModeleFactice(), journal, ecrire=False)
        for nom, n in bilan["par_flux"].items():
            print(f"  {nom:<45} {'EN PANNE' if n is None else n}")
        return 0
    from pipeline.sentiment import FinBERT  # importé ici : torch n'existe que dans GitHub Actions
    bilan = collecter(FinBERT(), journal, ecrire=True)
    journal.enregistrer()
    return 1 if journal.a_des_echecs() else 0


if __name__ == "__main__":
    sys.exit(main())
