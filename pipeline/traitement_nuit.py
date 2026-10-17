"""Chef d'orchestre du traitement de nuit.

Lancement :  python -m pipeline.traitement_nuit

Étape 1 du projet : seule la partie « performance des ETF » existe pour
l'instant. Le sentiment, la mise en parallèle et la synthèse s'ajouteront aux
étapes suivantes, chacune isolée : la panne de l'une n'empêche pas les autres.
"""

from datetime import date, datetime, timedelta, timezone

import pandas as pd

from pipeline import (collecte_prix, collecte_titres, controle_gdelt, fenetres, parallele, performance, secteurs, site,
                      sentiment, synthese)
from pipeline.config import DOSSIER_DATA, DOSSIER_SITE_DATA, config_etf, lire_yaml, parametres
from pipeline.journal import FICHIER_JOURNAL, Journal
from pipeline.sorties import ecrire_json_si_valide, lire_json

FICHIER_PERFORMANCE = DOSSIER_SITE_DATA / "performance.json"
FICHIER_PROVISOIRES = DOSSIER_DATA / "clotures_provisoires.json"
FICHIER_SECTEURS = DOSSIER_SITE_DATA / "secteurs.json"
FICHIER_SENTIMENT = DOSSIER_SITE_DATA / "sentiment.json"
FICHIER_HISTO_SENTIMENT = DOSSIER_DATA / "sentiment_quotidien.csv"
FICHIER_GDELT = DOSSIER_DATA / "gdelt_ton.csv"
FICHIER_GDELT_SITE = DOSSIER_SITE_DATA / "gdelt.json"
FICHIER_ETAT = DOSSIER_SITE_DATA / "etat.json"
FICHIER_PARALLELE = DOSSIER_SITE_DATA / "parallele.json"
FICHIER_SYNTHESE = DOSSIER_SITE_DATA / "synthese.json"

# Champs de config/etf.yaml recopiés tels quels dans le JSON du site.
CHAMPS_FICHE = ["id", "nom_court", "nom", "nom_precedent", "role", "approche", "vue_principale", "isin",
                "ticker_yahoo", "place", "devise_cotation", "indice", "emetteur", "replication",
                "distribution", "lancement_part", "frais_annuels_pct", "sfdr", "labels", "note_msci",
                "note_msci_commentaire", "sources", "verifie_le"]


def etape_performance(journal: Journal) -> pd.DataFrame | None:
    """Calcule les performances ; renvoie le tableau des cours alignés (ou None)."""
    cfg = config_etf()
    params = parametres()["performance"]
    id_ref = cfg["reference"]

    # --- 1. Téléchargements ---------------------------------------------------
    cotations = [e for e in cfg["etf"]] + [e["historique_avant"] for e in cfg["etf"] if e.get("historique_avant")]
    besoin_change = any(c["devise_cotation"] != "EUR" for c in cotations)
    eurusd = collecte_prix.telecharger_eurusd(date(2009, 1, 1), journal) if besoin_change else None
    estr = collecte_prix.telecharger_estr(date(2019, 10, 1), journal)  # le €STR existe depuis le 01/10/2019

    # Mémoire des clôtures provisoires (voir collecte_prix.py).
    provisoires = lire_json(FICHIER_PROVISOIRES) or {}

    def cours_en_euros(cotation: dict) -> pd.Series | None:
        """Télécharge une cotation et la convertit en euros si besoin."""
        serie = collecte_prix.telecharger_cours(cotation["ticker_yahoo"], journal, provisoires)
        if serie is None or cotation["devise_cotation"] == "EUR":
            return serie
        if cotation["devise_cotation"] != "USD" or eurusd is None:
            journal.noter(f"prix:{cotation['ticker_yahoo']}", "echec", "conversion en euros impossible")
            return None
        return collecte_prix.convertir_en_euros(serie, eurusd, params["change_report_max_jours"])

    cours_eur, qualite, indisponibles, raccordements = {}, {}, [], {}
    for etf in cfg["etf"]:
        serie = cours_en_euros(etf)
        if serie is not None and etf.get("historique_avant"):
            ancienne = cours_en_euros(etf["historique_avant"])
            if ancienne is None:
                # Sans son historique, cet ETF raccourcirait la période commune
                # de TOUS les ETF : on préfère l'écarter cette nuit.
                journal.noter(f"prix:{etf['id']}", "echec", "historique ancien indisponible, ETF écarté")
                serie = None
            else:
                serie, jonction = collecte_prix.raccorder(ancienne, serie)
                raccordements[etf["id"]] = {"cotation_ancienne": etf["historique_avant"]["ticker_yahoo"],
                                            "cotation_recente": etf["ticker_yahoo"],
                                            "jonction": jonction.date().isoformat()}
        if serie is None:
            indisponibles.append(etf["id"])
            continue
        cours_eur[etf["id"]] = serie

    # Enregistre la mémoire des clôtures provisoires et liste celles utilisées.
    ecrire_json_si_valide(FICHIER_PROVISOIRES, provisoires, [])
    ticker_vers_id = {e["ticker_yahoo"]: e["id"] for e in cfg["etf"]}
    valeurs_provisoires = []
    for ticker, jours in provisoires.items():
        for jour in sorted(jours):
            # Une cotation « historique ancien » (raccordement) n'est pas utilisée
            # pour les séances récentes : inutile de la signaler sur le site.
            if ticker in ticker_vers_id:
                valeurs_provisoires.append({"etf": ticker_vers_id[ticker], "ticker": ticker, "date": jour})
            if pd.Timestamp(jour) < pd.Timestamp(date.today() - timedelta(days=5)):
                journal.noter(f"prix:{ticker}", "avertissement",
                              f"clôture officielle du {jour} toujours absente chez Yahoo (valeur provisoire conservée)")

    if id_ref not in cours_eur:
        journal.noter("performance", "echec", "référence MSCI World indisponible : fichier du site conservé tel quel")
        return

    # Fraîcheur : un ETF en retard d'un jour sur les autres retarde tout le
    # tableau commun (on exige les mêmes dates). On le signale.
    dernier = {k: v.index[-1] for k, v in cours_eur.items()}
    plus_recent = max(dernier.values())
    for id_etf, d in dernier.items():
        if d < plus_recent:
            journal.noter(f"fraicheur:{id_etf}", "avertissement",
                          f"dernier cours au {d.date()} contre {plus_recent.date()} pour les autres")

    # --- 2. Calculs -----------------------------------------------------------
    tableau = performance.aligner(cours_eur)
    tableau, pics = performance.supprimer_pics_isoles(tableau, params["pic_isole_seuil_pct"] / 100, id_ref)
    for pic in pics:
        journal.noter(f"qualite:{pic['etf']}", "avertissement",
                      f"cours erroné écarté le {pic['date']} (écart de {pic['ecart_pct']} % avec les autres ETF)")

    # Contrôle qualité sur les cours réellement utilisés dans les calculs
    # (après alignement des dates et retrait des cours erronés).
    for id_etf in tableau.columns:
        qualite[id_etf] = collecte_prix.controler_qualite(tableau[id_etf], params["cours_fige_seances"],
                                                          params["variation_aberrante_pct"])
        for anomalie in qualite[id_etf]["variations_aberrantes"]:
            journal.noter(f"qualite:{id_etf}", "avertissement",
                          f"variation de {anomalie['variation_pct']} % le {anomalie['date']}")

    debut_fiable = {k: pd.Timestamp(v["jonction"]) for k, v in raccordements.items()}
    periodes = [performance.indicateurs_periode(tableau, id_ref, estr, p, params, debut_fiable)
                for p in params["periodes"]]
    serie_100 = performance.base_100(tableau)

    fiches = []
    for etf in cfg["etf"]:
        fiche = {champ: etf.get(champ) for champ in CHAMPS_FICHE}
        fiche["disponible"] = etf["id"] in cours_eur
        fiche["qualite"] = qualite.get(etf["id"])
        fiche["raccordement"] = raccordements.get(etf["id"])
        fiches.append(fiche)

    donnees = {
        "genere_le_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "derniere_seance": tableau.index[-1].date().isoformat(),
        "premiere_seance_commune": tableau.index[0].date().isoformat(),
        "nb_seances_communes": int(len(tableau)),
        "devise": "EUR",
        "reference": id_ref,
        "defaut_esg": cfg["defaut_esg"],
        "etf_indisponibles": indisponibles,
        "cours_errones_ecartes": pics,
        # Clôtures provisoires (dernier prix de séance, en attente de la clôture
        # officielle de Yahoo) : le site les signale par un astérisque.
        "valeurs_provisoires": valeurs_provisoires,
        "derniere_seance_provisoire": any(v["date"] == tableau.index[-1].date().isoformat()
                                          for v in valeurs_provisoires),
        "etf": fiches,
        "periodes": periodes,
        "series": {
            "dates": [d.date().isoformat() for d in serie_100.index],
            "base100": {col: [round(float(v), 6) for v in serie_100[col]] for col in serie_100.columns},
        },
    }

    # --- 3. Écriture prudente ---------------------------------------------------
    ancien = lire_json(FICHIER_PERFORMANCE)
    ancienne_date = ancien.get("derniere_seance", "") if ancien else ""
    un_an = next((p for p in periodes if p["id"] == "1a"), {})
    controles = [
        (donnees["derniere_seance"] >= ancienne_date,
         f"données plus anciennes ({donnees['derniere_seance']}) que celles déjà publiées ({ancienne_date})"),
        (tableau.index[-1] >= pd.Timestamp(date.today() - timedelta(days=10)),
         f"dernière séance trop ancienne ({donnees['derniere_seance']})"),
        (un_an.get("disponible", False), "période d'un an non calculable"),
    ]
    ecrit, raison = ecrire_json_si_valide(FICHIER_PERFORMANCE, donnees, controles)
    if ecrit:
        journal.noter("performance", "ok",
                      f"{len(cours_eur)} ETF, séance du {donnees['derniere_seance']}, "
                      f"{donnees['nb_seances_communes']} séances communes")
    else:
        journal.noter("performance", "echec", f"fichier du site conservé tel quel : {raison}")
    return tableau


AVERTISSEMENT_PERIODE = ("Ces résultats dépendent fortement de la période observée. De 2023 à 2026, "
                         "les grandes valeurs technologiques américaines ont porté le marché : un indice "
                         "qui les sous-pondère a mécaniquement fait moins bien. Sur une autre période "
                         "(par exemple une baisse de la technologie ou une hausse de l'énergie), "
                         "le classement peut s'inverser.")


def etape_secteurs(journal: Journal, tableau: pd.DataFrame | None) -> None:
    """Poids par secteur des fonds et effet des paris sectoriels (voir secteurs.py)."""
    perf = lire_json(FICHIER_PERFORMANCE) or {}
    raccords = {f["id"]: f["raccordement"]["jonction"] for f in perf.get("etf", []) if f.get("raccordement")}
    cfg = config_etf()
    params = parametres()["secteurs"]
    id_ref = cfg["reference"]
    ancien = lire_json(FICHIER_SECTEURS) or {}
    donnees = {"genere_le_utc": secteurs.horodatage(), "avertissement_periode": AVERTISSEMENT_PERIODE,
               "compositions": dict(ancien.get("compositions", {})), "effet_sectoriel": {}}

    # 1. Compositions : rafraîchies seulement si elles datent de plus de N jours.
    for etf in cfg["etf"]:
        url = etf.get("composition_csv")
        if not url:
            continue
        precedente = donnees["compositions"].get(etf["id"])
        if precedente:
            age = (datetime.now(timezone.utc) - datetime.fromisoformat(precedente["releve_le_utc"].replace("Z", "+00:00"))).days
            if age < params["rafraichir_tous_les_jours"]:
                continue
        try:
            date_compo, df = secteurs.telecharger_composition(url)
            donnees["compositions"][etf["id"]] = {
                "date_composition": date_compo,
                "releve_le_utc": secteurs.horodatage(),
                "source": url,
                "nb_lignes": int(len(df)),
                "secteurs_pct": secteurs.poids_par_secteur(df),
                "grandes_tech": secteurs.poids_grandes_tech(df, params["grandes_tech"]),
            }
        except Exception as erreur:  # noqa: BLE001
            journal.noter(f"secteurs:{etf['id']}", "avertissement",
                          f"composition non mise à jour ({erreur}) ; ancienne version conservée si elle existe")

    # Écarts de poids par secteur avec le MSCI World (en points).
    compo_ref = donnees["compositions"].get(id_ref)
    donnees["ecarts_secteurs_pts"] = {}
    if compo_ref:
        for id_etf, compo in donnees["compositions"].items():
            if id_etf == id_ref:
                continue
            tous = set(compo["secteurs_pct"]) | set(compo_ref["secteurs_pct"])
            donnees["ecarts_secteurs_pts"][id_etf] = {
                s: round(compo["secteurs_pct"].get(s, 0) - compo_ref["secteurs_pct"].get(s, 0), 2) for s in sorted(tous)}

    # 2. Effet des paris (grandes tech, énergie) sur les 3 dernières années.
    if tableau is not None and compo_ref:
        cours_secteurs = {nom: collecte_prix.telecharger_cours(t, journal) for nom, t in params["etf_sectoriels"].items()}
        # Facteur « grandes tech » : les 7 actions cotées sur Xetra, pondérées
        # selon leur poids actuel dans le MSCI World (Alphabet A + C regroupés).
        poids_ref = compo_ref["grandes_tech"]["detail"]
        poids_codes = {"AAPL": "APPLE", "MSFT": "MICROSOFT", "NVDA": "NVIDIA", "AMZN": "AMAZON.COM INC",
                       "META": "META PLATFORMS CLASS A", "TSLA": "TESLA INC"}
        poids = {code: poids_ref.get(nom, 0) for code, nom in poids_codes.items()}
        poids["GOOGL"] = poids_ref.get("ALPHABET CLASS A", 0) + poids_ref.get("ALPHABET CLASS C", 0)
        actions = {code: collecte_prix.telecharger_cours(t, journal, action_a_dividendes=True)
                   for code, t in params["grandes_tech_xetra"].items()}
        if all(a is not None for a in actions.values()):
            cours_secteurs = {"grandes_tech": secteurs.facteur_panier(actions, poids), **cours_secteurs}
            donnees["poids_facteur_grandes_tech"] = poids
        else:
            cours_secteurs["grandes_tech"] = None
        if all(s is not None for s in cours_secteurs.values()):
            fin = tableau.index[-1]
            debut = fin - pd.DateOffset(months=params["periode_mois"])
            for etf in cfg["etf"]:
                if etf["id"] == id_ref or etf["id"] not in tableau.columns:
                    continue
                cours = performance.aligner({etf["id"]: tableau[etf["id"]], id_ref: tableau[id_ref], **cours_secteurs})
                cours = cours[cours.index >= debut]
                mesure = secteurs.effet_sectoriel(cours, etf["id"], id_ref, list(cours_secteurs))
                # Cotation ancienne bruitée (raccordement) : la régression quotidienne
                # en souffre directement (R² artificiellement faible).
                jonction = (raccords or {}).get(etf["id"])
                if jonction and pd.Timestamp(jonction) > cours.index[0]:
                    mesure["fiabilite_reduite"] = (f"cours quotidiens bruités avant le {jonction} "
                                                   "(cotation d'Amsterdam convertie) : mesure peu fiable")
                donnees["effet_sectoriel"][etf["id"]] = mesure
            donnees["effet_sectoriel_source"] = {"grandes_tech": params["grandes_tech_xetra"],
                                                 **params["etf_sectoriels"]}
        else:
            journal.noter("secteurs", "avertissement", "cours des facteurs indisponibles : effet sectoriel non mesuré")

    ecrit, raison = ecrire_json_si_valide(FICHIER_SECTEURS, donnees, [(bool(donnees["compositions"]), "aucune composition")])
    journal.noter("secteurs", "ok" if ecrit else "avertissement",
                  f"{len(donnees['compositions'])} compositions, {len(donnees['effet_sectoriel'])} mesures d'effet sectoriel"
                  if ecrit else f"fichier conservé : {raison}")


COLONNES_HISTO_SENTIMENT = ["seance", "groupe", "nb_articles", "nb_sources", "positif_pct", "neutre_pct",
                            "negatif_pct", "solde", "marge_erreur", "etiquette", "couverture_partielle",
                            "releves_reussis", "releves_attendus", "plus_long_trou_heures",
                            "nb_dates_approximatives", "solde_dates_fiables",
                            "media_principal", "part_media_principal_pct", "solde_avec_plafond"]

CREDIT_FINBERT = ("Analyse de sentiment : FinBERT (ProsusAI/finbert), © MIH AI B.V., licence CC BY-NC-SA 4.0 "
                  "(usage non commercial). Références : Araci (2019) ; Financial PhraseBank, Malo et al. (2014).")


def releves_reussis() -> list[pd.Timestamp]:
    """Heures des relevés de titres réussis, lues dans le journal d'exécution."""
    if not FICHIER_JOURNAL.exists():
        return []
    j = pd.read_csv(FICHIER_JOURNAL, encoding="utf-8-sig", dtype=str)
    ok = j[(j["etape"] == "collecte_titres") & (j["statut"] == "ok")]
    return [pd.Timestamp(h, tz="UTC") for h in ok["horodatage_utc"]]


def media_des_titres(titres: pd.DataFrame) -> pd.Series:
    """Média de chaque titre : celui du flux (config) ou, pour Google Actualités, celui de l'article."""
    flux = lire_yaml("flux_rss.yaml")["flux"]
    media_du_flux = {f["nom"]: f.get("media", f["nom"]) for f in flux if f["type"] == "direct"}
    return titres.apply(lambda r: media_du_flux.get(r["source"], r["source"]) if r["type"] == "direct"
                        else r["source"], axis=1)


def suivi_neutres(historique: pd.DataFrame, n: int = 20) -> dict:
    """Part moyenne de titres neutres par groupe sur les n dernières journées complètes (point 11)."""
    resultat = {}
    for groupe, d in historique.groupby("groupe"):
        d = d[~d["couverture_partielle"].astype(str).str.lower().eq("true")].tail(n)
        if len(d):
            resultat[groupe] = {"neutre_moyen_pct": round(float(d["neutre_pct"].mean()), 1), "nb_journees": int(len(d))}
    return resultat


def etape_sentiment(journal: Journal, maintenant: pd.Timestamp | None = None) -> None:
    """Indicateurs des dernières journées de sentiment closes, à partir des titres notés.

    Les 10 dernières journées sont recalculées chaque nuit (le calcul est
    déterministe : refaire le calcul donne le même résultat), ce qui intègre
    les articles collectés tardivement. La répartition par média est mesurée
    sur les 20 dernières.
    """
    p = parametres()["sentiment"]
    cal = p["calendrier_bourse"]
    maintenant = maintenant or pd.Timestamp.now(tz="UTC")
    seances_repartition = fenetres.seances_closes(maintenant, p["repartition_seances"], cal)
    seances = seances_repartition[-10:]
    debut = fenetres.bornes(seances_repartition[0], cal)[0]
    jours = pd.date_range(debut.date() - timedelta(days=1), maintenant.date() + timedelta(days=1))
    fichiers = [f for f in (collecte_titres.chemin_fichier_jour(d.date().isoformat()) for d in jours) if f.exists()]
    if not fichiers:
        journal.noter("sentiment", "avertissement", "aucun titre collecté sur la période : fichier du site conservé")
        return
    titres = pd.concat([pd.read_csv(f, encoding="utf-8-sig", dtype=str) for f in fichiers], ignore_index=True)
    # Une fusion de deux enregistrements simultanés peut répéter la ligne d'en-tête : on l'écarte.
    titres = titres[titres["id"] != "id"].drop_duplicates(subset="id")
    for col in ("p_positif", "p_neutre", "p_negatif"):
        titres[col] = pd.to_numeric(titres[col], errors="coerce")
    titres["media"] = media_des_titres(titres)
    # Relevés réussis : journal d'exécution, complété par les heures de collecte des titres.
    releves = sorted(set(releves_reussis()) | {pd.Timestamp(c) for c in titres["collecte_utc"].unique()})

    lignes, details = [], {}
    for seance in seances:
        debut_fenetre, fin_fenetre = fenetres.bornes(seance, cal)
        couv = sentiment.couverture(debut_fenetre.tz_convert("UTC"), fin_fenetre.tz_convert("UTC"), releves, p)
        for groupe in ("marche", "esg"):
            sous = titres[(titres["seance"] == seance) & (titres["groupe"] == groupe)]
            if sous.empty:
                continue
            ind = sentiment.indicateurs_journee(sous, p) | couv
            details[(seance, groupe)] = ind
            lignes.append({c: ind.get(c) for c in COLONNES_HISTO_SENTIMENT if c not in ("seance", "groupe")}
                          | {"seance": seance, "groupe": groupe})

    # Poids des médias sur les 20 dernières séances (point 3).
    recents = titres[titres["seance"].isin(seances_repartition)]
    repartition = {}
    for groupe in ("marche", "esg"):
        d = recents[recents["groupe"] == groupe]
        if d.empty:
            continue
        parts = d["media"].value_counts(normalize=True).mul(100).round(1)
        repartition[groupe] = {"nb_articles": int(len(d)), "nb_seances": int(d["seance"].nunique()),
                               "parts_pct": parts.head(15).to_dict(),
                               "autres_medias_pct": round(float(parts.iloc[15:].sum()), 1)}
        if parts.iloc[0] > p["plafond_media_pct"]:
            journal.noter("sentiment", "avertissement",
                          f"{parts.index[0]} pèse {parts.iloc[0]} % du groupe {groupe} sur "
                          f"{d['seance'].nunique()} séances (plafond de {p['plafond_media_pct']} % dépassé)")

    if not lignes:
        journal.noter("sentiment", "avertissement", "aucune journée close avec des titres : fichier du site conservé")
        return

    # Historique : on remplace les journées recalculées, on garde les autres.
    nouveau = pd.DataFrame(lignes)[COLONNES_HISTO_SENTIMENT]
    if FICHIER_HISTO_SENTIMENT.exists():
        ancien = pd.read_csv(FICHIER_HISTO_SENTIMENT, encoding="utf-8-sig", dtype={"seance": str})
        cles = set(zip(nouveau["seance"], nouveau["groupe"]))
        ancien = ancien[[(s, g) not in cles for s, g in zip(ancien["seance"], ancien["groupe"])]]
        nouveau = pd.concat([ancien, nouveau], ignore_index=True)
    nouveau = nouveau.sort_values(["seance", "groupe"])
    FICHIER_HISTO_SENTIMENT.parent.mkdir(parents=True, exist_ok=True)
    nouveau.to_csv(FICHIER_HISTO_SENTIMENT, index=False, encoding="utf-8-sig")

    derniere = max(s for s, _ in details)
    debut_d, fin_d = fenetres.bornes(derniere, p["calendrier_bourse"])
    donnees = {
        "genere_le_utc": maintenant.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "derniere_seance": derniere,
        "fenetre": {"debut": debut_d.isoformat(), "fin": fin_d.isoformat(),
                    "definition": "articles publiés après la clôture de la séance précédente et "
                                  "au plus tard à la clôture de cette séance (heure de Paris)"},
        "groupes": {g: details[(derniere, g)] for g in ("marche", "esg") if (derniere, g) in details},
        "historique": nouveau.where(pd.notna(nouveau), None).to_dict(orient="records"),
        "repartition_medias": repartition,
        # Barres du graphique pour les périodes longues (voir sentiment.agreger_periodes).
        "agregats": {g: {f: sentiment.agreger_periodes(nouveau, g, f) for f in ("semaine", "mois")}
                     for g in ("marche", "esg")},
        "suivi_taux_neutre": suivi_neutres(nouveau),
        "modele": {"nom": p["modele"], "revision": p["revision"],
                   "licence": "CC BY-NC-SA 4.0 — © MIH AI B.V. (Prosus)"},
        # Crédit à afficher sur le site lui-même (pied de page), exigé par la licence.
        "credit": CREDIT_FINBERT,
    }
    ecrit, raison = ecrire_json_si_valide(FICHIER_SENTIMENT, donnees, [(bool(donnees["groupes"]), "aucun groupe")])
    resume = ", ".join(f"{g} {d['etiquette']} (solde {d['solde']}, n={d['nb_articles']})"
                       for g, d in donnees["groupes"].items())
    journal.noter("sentiment", "ok" if ecrit else "echec",
                  f"journée du {derniere} : {resume}" if ecrit else f"fichier conservé : {raison}")


def etape_parallele(journal: Journal, tableau: pd.DataFrame | None) -> None:
    """Volet 3 (mise en parallèle) et synthèse automatique en français."""
    cfg = config_etf()
    p = parametres()
    perf = lire_json(FICHIER_PERFORMANCE)
    senti = lire_json(FICHIER_SENTIMENT)
    resultats = None
    if tableau is not None and FICHIER_HISTO_SENTIMENT.exists():
        historique = pd.read_csv(FICHIER_HISTO_SENTIMENT, encoding="utf-8-sig", dtype={"seance": str})
        resultats = parallele.analyser(tableau, cfg["reference"], historique, p["parallele"],
                                       p["sentiment"]["calendrier_bourse"])
        resultats["genere_le_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        resultats["parametres"] = p["parallele"]
        ecrire_json_si_valide(FICHIER_PARALLELE, resultats, [])
        prog = resultats["etf"].get(cfg["defaut_esg"], {}).get("marche", {}).get("progression", {})
        journal.noter("parallele", "ok", f"{prog.get('jours_exploitables', 0)} / {prog.get('jours_requis')} "
                                         f"jours exploitables (estimation : {prog.get('date_estimee')})")
    else:
        journal.noter("parallele", "avertissement", "cours ou historique de sentiment indisponibles : volet 3 non recalculé")
        resultats = lire_json(FICHIER_PARALLELE)

    # Synthèse : une version par ETF ESG (le site affiche celle de l'ETF choisi).
    textes = {e["id"]: synthese.generer(perf, senti, resultats, e["id"])
              for e in cfg["etf"] if e["id"] != cfg["reference"]}
    donnees = {"genere_le_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "methode": "Phrases générées par des règles fixes (aucune intelligence artificielle) : voir pipeline/synthese.py.",
               "defaut": cfg["defaut_esg"], "par_etf": textes,
               # Version courte pour l'accueil (humeur du jour et écart de performance).
               "essentiel_par_etf": {k: synthese.essentiel(v) for k, v in textes.items()}}
    ecrit, raison = ecrire_json_si_valide(FICHIER_SYNTHESE, donnees, [(any(textes.values()), "aucune phrase")])
    journal.noter("synthese", "ok" if ecrit else "avertissement",
                  " ".join(textes.get(cfg["defaut_esg"], []))[:300] if ecrit else raison)


def etape_gdelt(journal: Journal) -> None:
    """Tonalité GDELT (contrôle facultatif) : un échec n'est qu'un avertissement."""
    try:
        series = controle_gdelt.collecter()
    except Exception as erreur:  # noqa: BLE001
        journal.noter("gdelt", "avertissement", f"GDELT indisponible cette nuit ({erreur}) — sans conséquence")
        return
    nouveau = pd.concat({g: s for g, s in series.items()}, axis=1).rename_axis("date").reset_index()
    nouveau["date"] = nouveau["date"].astype(str)
    if FICHIER_GDELT.exists():
        ancien = pd.read_csv(FICHIER_GDELT, encoding="utf-8-sig", dtype={"date": str})
        nouveau = pd.concat([ancien[~ancien["date"].isin(nouveau["date"])], nouveau]).sort_values("date")
    nouveau.to_csv(FICHIER_GDELT, index=False, encoding="utf-8-sig")
    donnees = {"genere_le_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "methode": "Tonalité moyenne GDELT (dictionnaire de mots, articles complets, presse mondiale). "
                          "Méthode différente de FinBERT : à comparer en tendance uniquement.",
               "requetes": controle_gdelt.REQUETES,
               "series": nouveau.where(pd.notna(nouveau), None).to_dict(orient="records")}
    ecrire_json_si_valide(FICHIER_GDELT_SITE, donnees, [(len(nouveau) > 0, "série vide")])
    journal.noter("gdelt", "ok", f"{len(nouveau)} jours de tonalité GDELT")


ETAPES = ["performance", "secteurs", "sentiment", "parallele", "synthese", "gdelt"]


def gdelt_a_des_donnees() -> bool:
    """Vrai seulement si le fichier GDELT du site existe et contient au moins une valeur."""
    donnees = lire_json(FICHIER_GDELT_SITE) or {}
    return any(v is not None for ligne in donnees.get("series", []) for k, v in ligne.items() if k != "date")


def ecrire_etat(journal: Journal, maintenant: datetime | None = None) -> dict:
    """Écrit docs/data/etat.json : ce que le site affiche dans son bandeau de mise à jour.

    - date de la dernière exécution et des dernières données valides ;
    - pour chaque étape : statut de cette nuit et date de sa dernière réussite
      (conservée d'une nuit sur l'autre : si une étape échoue, le site sait
      depuis quand ses données datent) ;
    - alertes des dernières 24 heures (sources en panne, cours écartés…),
      y compris celles des relevés de titres faits toutes les 3 heures.
    """
    maintenant = maintenant or datetime.now(timezone.utc)
    horodatage = maintenant.strftime("%Y-%m-%dT%H:%M:%SZ")
    ancien = lire_json(FICHIER_ETAT) or {}
    etapes = {}
    for etape in ETAPES:
        lignes = [l for l in journal.lignes if l["etape"] == etape]
        precedent = ancien.get("etapes", {}).get(etape, {})
        statut = lignes[-1]["statut"] if lignes else "non exécutée"
        etapes[etape] = {
            "statut": statut,
            "message": lignes[-1]["message"] if lignes else "",
            "derniere_reussite_utc": horodatage if statut == "ok" else precedent.get("derniere_reussite_utc"),
        }

    # Alertes : cette exécution + journal des dernières 24 h (relevés de titres).
    # GDELT est facultatif : ses incidents restent dans le journal mais ne sont
    # pas affichés sur le site (point 10 : rien ne s'affiche si la série est vide).
    alertes = [{"horodatage_utc": l["horodatage_utc"], "etape": l["etape"], "statut": l["statut"], "message": l["message"]}
               for l in journal.lignes if l["statut"] != "ok" and l["etape"] != "gdelt"]
    if FICHIER_JOURNAL.exists():
        histo = pd.read_csv(FICHIER_JOURNAL, encoding="utf-8-sig", dtype=str).fillna("")
        limite = (maintenant - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        recents = histo[(histo["horodatage_utc"] >= limite) & (histo["statut"] != "ok") & (histo["etape"] != "gdelt")]
        alertes += recents.to_dict(orient="records")
    vues, uniques = set(), []
    for a in alertes:  # une même alerte répétée à chaque relevé n'apparaît qu'une fois
        cle = (a["etape"], a["message"][:80])
        if cle not in vues:
            vues.add(cle)
            uniques.append(a)

    perf, sent = lire_json(FICHIER_PERFORMANCE) or {}, lire_json(FICHIER_SENTIMENT) or {}
    etat = {
        "derniere_execution_utc": horodatage,
        "donnees": {
            "performance_derniere_seance": perf.get("derniere_seance"),
            "performance_provisoire": perf.get("derniere_seance_provisoire", False),
            "sentiment_derniere_journee": sent.get("derniere_seance"),
        },
        "etapes": etapes,
        "tout_va_bien": all(e["statut"] == "ok" for k, e in etapes.items() if k != "gdelt"),
        "alertes_24h": uniques,
        # Le site n'affiche la série GDELT que si elle contient des valeurs.
        "gdelt_disponible": gdelt_a_des_donnees(),
        # Crédits affichés dans le pied de page de chaque page du site.
        "credits": [
            CREDIT_FINBERT,
            "Cours : Yahoo Finance (usage personnel, non commercial). Taux de change et €STR : Banque centrale européenne.",
            "Données ESG et réglementaires : fiches officielles des émetteurs (iShares, BNP Paribas AM), "
            "liste officielle du label ISR, liste Greenfin. Notes ESG : MSCI ESG Research, via les fiches iShares.",
        ],
    }
    ecrire_json_si_valide(FICHIER_ETAT, etat, [])
    return etat


def main() -> int:
    journal = Journal()
    tableau = None
    try:
        tableau = etape_performance(journal)
    except Exception as erreur:  # noqa: BLE001 — une erreur imprévue ne doit pas tout bloquer
        journal.noter("performance", "echec", f"erreur imprévue : {erreur!r}")
    try:
        etape_secteurs(journal, tableau)
    except Exception as erreur:  # noqa: BLE001
        journal.noter("secteurs", "echec", f"erreur imprévue : {erreur!r}")
    try:
        etape_sentiment(journal)
    except Exception as erreur:  # noqa: BLE001
        journal.noter("sentiment", "echec", f"erreur imprévue : {erreur!r}")
    try:
        etape_parallele(journal, tableau)
    except Exception as erreur:  # noqa: BLE001
        journal.noter("parallele", "echec", f"erreur imprévue : {erreur!r}")
    try:
        # Texte de la méthodologie pour le site (converti depuis contenu/methodologie.md).
        site.main()
    except Exception as erreur:  # noqa: BLE001
        journal.noter("site", "avertissement", f"méthodologie non mise à jour : {erreur!r}")
    try:
        etape_gdelt(journal)
    except Exception as erreur:  # noqa: BLE001
        journal.noter("gdelt", "avertissement", f"erreur imprévue : {erreur!r}")
    try:
        ecrire_etat(journal)
    except Exception as erreur:  # noqa: BLE001
        journal.noter("etat", "echec", f"erreur imprévue : {erreur!r}")
    journal.enregistrer()
    # Code de sortie 1 si une étape a échoué : GitHub Actions affichera la
    # tâche en rouge et t'enverra un e-mail.
    return 1 if journal.a_des_echecs() else 0


if __name__ == "__main__":
    raise SystemExit(main())
