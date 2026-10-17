"""Tests de l'étape 2 : collecte, journées de sentiment, étiquette du jour."""

import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from pipeline import collecte_titres as ct
from pipeline import fenetres, sentiment

P = {"facteur_confiance": 1.96, "articles_min": 30, "marge_max_points": 25, "titres_extremes": 5}


# --- Correction A : seuil qui dépend du nombre d'articles ----------------------

@pytest.mark.parametrize("n, attendu", [(250, 9.6), (140, 12.8), (60, 19.6), (40, 24.0)])
def test_marge_erreur_exemples_du_plan(n, attendu):
    # 30 % de positifs, 30 % de négatifs : exemples donnés dans le plan.
    assert sentiment.marge_erreur(0.30, 0.30, n, 1.96) == pytest.approx(attendu, abs=0.05)


def test_etiquette_selon_taille_echantillon():
    # Même solde de +15 : « positif » avec 250 articles, « neutre » avec 60.
    assert sentiment.etiquette(15, sentiment.marge_erreur(0.375, 0.225, 250, 1.96), 250, P) == "positif"
    assert sentiment.etiquette(15, sentiment.marge_erreur(0.375, 0.225, 60, 1.96), 60, P) == "neutre"
    # Moins de 30 articles : signal insuffisant, quel que soit le solde.
    assert sentiment.etiquette(-60, 5, 29, P) == "signal insuffisant"
    # Marge supérieure à 25 points : signal insuffisant.
    assert sentiment.etiquette(-30, 26, 35, P) == "signal insuffisant"
    assert sentiment.etiquette(-12, 9.6, 250, P) == "négatif"


def test_indicateurs_journee():
    articles = pd.DataFrame({
        "classe": ["positif"] * 20 + ["negatif"] * 10 + ["neutre"] * 70,
        "p_positif": [0.6 + i / 100 for i in range(20)] + [0.1] * 80,
        "p_negatif": [0.1] * 20 + [0.5 + i / 100 for i in range(10)] + [0.1] * 70,
        "titre": [f"t{i}" for i in range(100)], "source": ["A", "B"] * 50,
        "lien": [f"https://x/{i}" for i in range(100)], "date_publication_utc": ["2026-10-16T10:00:00Z"] * 100,
    })
    ind = sentiment.indicateurs_journee(articles, P)
    assert ind["nb_articles"] == 100 and ind["solde"] == 10.0
    assert ind["positif_pct"] == 20.0 and ind["negatif_pct"] == 10.0 and ind["neutre_pct"] == 70.0
    assert ind["plus_positifs"][0]["titre"] == "t19" and len(ind["plus_positifs"]) == 5
    assert ind["plus_negatifs"][0]["titre"] == "t29"
    assert ind["etiquette"] == "neutre"  # marge ≈ 10,5 > solde de 10


# --- Correction B : journée de sentiment = de clôture à clôture ------------------

@pytest.mark.parametrize("publication, seance", [
    ("2026-10-16T15:30:00Z", "2026-10-16"),  # vendredi 17 h 30 pile (Paris) : séance du vendredi
    ("2026-10-16T15:31:00Z", "2026-10-19"),  # vendredi 17 h 31 : séance du lundi
    ("2026-10-17T10:00:00Z", "2026-10-19"),  # samedi : séance du lundi
    ("2026-10-19T06:00:00Z", "2026-10-19"),  # lundi matin
    ("2026-12-24T12:00:00Z", "2026-12-28"),  # 24 et 25 décembre fériés à Francfort
    ("2026-12-30T14:00:00Z", "2027-01-04"),  # 30/12 : clôture anticipée à 14 h (Paris)
])
def test_seance_de(publication, seance):
    assert str(fenetres.seance_de(pd.Series([publication]))[0]) == seance


def test_bornes_du_lundi_incluent_le_week_end():
    debut, fin = fenetres.bornes("2026-10-19")
    assert debut.isoformat() == "2026-10-16T17:30:00+02:00"
    assert fin.isoformat() == "2026-10-19T17:30:00+02:00"


# --- Nettoyage et dédoublonnage ---------------------------------------------------

def test_nettoyage():
    assert ct.nettoyer_texte("<p>Stocks &amp; bonds <b>rally</b></p>") == "Stocks & bonds rally"
    assert ct.lien_canonique("https://WWW.ft.com/a?utm_source=rss&id=3#top") == "https://www.ft.com/a?id=3"
    assert ct.titre_sans_source("Fed holds rates - Reuters", "Reuters") == "Fed holds rates"
    assert ct.texte_a_analyser("Fed holds rates", "Fed holds rates steady as expected", 60) == "Fed holds rates"
    assert ct.texte_a_analyser("Fed holds", "Markets cheered the decision", 60) == "Fed holds. Markets cheered the decision"


def article(titre, lien, groupe="marche", type_="direct", heure=10):
    return {"groupe": groupe, "source": "S", "type": type_, "titre": titre, "resume": "", "lien": lien,
            "date_publication": datetime(2026, 10, 16, heure, tzinfo=timezone.utc), "date_approximative": False}


def test_dedoublonnage():
    articles = [
        article("Fed holds rates steady as inflation cools", "https://news.google.com/1", type_="agregateur", heure=9),
        article("Fed holds rates steady as inflation cools", "https://cnbc.com/fed", heure=11),
        article("Fed holds rates steady, as inflation cools!", "https://wsj.com/fed", heure=12),   # quasi identique
        article("Oil prices jump on supply fears", "https://ft.com/oil"),
        article("Oil prices jump on supply fears", "https://ft.com/oil", groupe="esg"),          # autre groupe : gardé
        article("Gold hits record", "https://bbc.com/gold"),                                       # déjà vu hier
    ]
    deja_vus = {"marche": [("https://bbc.com/gold", "gold hits record")]}
    gardes, doublons = ct.dedoublonner(articles, deja_vus, 90)
    assert doublons == 3
    liens = sorted(a["lien"] for a in gardes)
    # Le flux direct (CNBC) est gardé de préférence à Google Actualités.
    assert liens == ["https://cnbc.com/fed", "https://ft.com/oil", "https://ft.com/oil"]


def test_filtre_mots_cles_agregateur():
    motif = ct.motif_mots_cles(["ESG", "sustainab*", "green", "net zero", "COP", "COP3*", "impact invest*"])
    gardes = ["EU softens ESG rules", "Sustainability reporting delayed", "Green bonds hit record",
              "Banks miss net zero targets", "Deals struck at COP30", "Rise of impact investing in Asia"]
    rejetes = ["Greenback heads for weekly fall", "What UniCredit Buyers Were Betting On",
               "Monthly Asset Allocation Update", "Copper prices climb", "Police cop suspended"]
    assert all(motif.search(t) for t in gardes)
    assert not any(motif.search(t) for t in rejetes)
    flux = {"nom": "GN", "groupe": "esg", "type": "agregateur"}
    gn = """<?xml version="1.0"?><rss version="2.0"><channel><title>GN</title>
    <item><title>Green bonds hit record - FT</title><link>https://news.google.com/a</link><source url="x">FT</source>
    <pubDate>Fri, 16 Oct 2026 14:00:00 GMT</pubDate></item>
    <item><title>What UniCredit Buyers Were Betting On - Bloomberg</title><link>https://news.google.com/b</link>
    <source url="y">Bloomberg</source><pubDate>Fri, 16 Oct 2026 14:00:00 GMT</pubDate></item></channel></rss>"""
    arts = ct.lire_flux(gn, flux, datetime(2026, 10, 16, 20, tzinfo=timezone.utc), 36, motif)
    assert [(a["titre"], a["source"]) for a in arts] == [("Green bonds hit record", "FT")]
    # Liste noire : le même article est ignoré si son média est exclu (majuscules indifférentes).
    assert ct.lire_flux(gn, flux, datetime(2026, 10, 16, 20, tzinfo=timezone.utc), 36, motif, {"ft"}) == []


def test_liste_noire_dans_la_configuration():
    from pipeline.config import lire_yaml
    cfg = lire_yaml("flux_rss.yaml")
    exclus = cfg["medias_exclus_agregateurs"]
    assert all(e.get("raison") and e.get("depuis") for e in exclus)   # raison et date obligatoires
    assert {"kalkine india", "scanx.trade"} <= {e["media"].casefold() for e in exclus}


RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>Test</title>
<item><title>Stocks rally on earnings</title><link>https://ex.com/a?utm_medium=rss</link>
<description>SECRET-RESUME-123 Investors cheered strong quarterly results.</description>
<pubDate>Fri, 16 Oct 2026 14:00:00 GMT</pubDate></item>
<item><title>Ancien article</title><link>https://ex.com/old</link><description>vieux</description>
<pubDate>Mon, 05 Oct 2026 14:00:00 GMT</pubDate></item>
<item><title>Sans date</title><link>https://ex.com/nodate</link><description>texte</description></item>
</channel></rss>"""


def test_lire_flux_filtre_les_anciens_et_signale_les_dates_absentes():
    maintenant = datetime(2026, 10, 16, 20, 0, tzinfo=timezone.utc)
    flux = {"nom": "Test", "groupe": "marche", "type": "direct"}
    arts = ct.lire_flux(RSS, flux, maintenant, 36)
    assert [a["titre"] for a in arts] == ["Stocks rally on earnings", "Sans date"]
    assert arts[0]["lien"] == "https://ex.com/a" and arts[0]["date_approximative"] is False
    assert arts[1]["date_approximative"] is True


# --- Correction C : le résumé n'est jamais enregistré --------------------------------

def test_le_resume_n_est_jamais_ecrit(tmp_path, monkeypatch):
    monkeypatch.setattr(ct, "DOSSIER_TITRES", tmp_path / "titres")
    monkeypatch.setattr(ct, "lire_yaml", lambda _: {"agregateurs_actifs": True, "flux": [
        {"groupe": "marche", "nom": "Test", "type": "direct", "actif": True, "url": "https://ex.com/rss"}]})
    monkeypatch.setattr(ct, "telecharger_flux", lambda flux: RSS.encode())

    class ModeleQuiVerifie(ct.ModeleFactice):
        textes_recus = []

        def predire(self, textes):
            ModeleQuiVerifie.textes_recus = textes
            return super().predire(textes)

    from pipeline.journal import Journal
    bilan = ct.collecter(ModeleQuiVerifie(), Journal(), ecrire=True,
                         maintenant=datetime(2026, 10, 16, 20, 0, tzinfo=timezone.utc))
    assert bilan["nouveaux"] == 2
    # Le résumé a bien servi au calcul...
    assert any("SECRET-RESUME-123" in t for t in ModeleQuiVerifie.textes_recus)
    # ... mais il n'apparaît dans aucun fichier écrit.
    fichiers = list((tmp_path / "titres").rglob("*.csv"))
    assert fichiers
    for f in fichiers:
        contenu = f.read_text(encoding="utf-8-sig")
        assert "SECRET-RESUME-123" not in contenu and "cheered" not in contenu
        assert contenu.splitlines()[0].split(",") == ct.COLONNES_CSV


def test_lecture_gdelt():
    from pipeline.controle_gdelt import lire_tonalite
    reponse = {"timeline": [{"series": "Average Tone", "data": [
        {"date": "20261015T000000Z", "value": -1.25}, {"date": "20261016T000000Z", "value": -0.8}]}]}
    s = lire_tonalite(reponse)
    assert [str(d) for d in s.index] == ["2026-10-15", "2026-10-16"] and s.iloc[0] == -1.25


# --- Agrégation de nuit, de bout en bout -------------------------------------------------

PC = {"intervalle_releves_heures": 3, "couverture_min_pct": 75, "couverture_ecart_max_heures": 12}
DEBUT, FIN = pd.Timestamp("2026-10-15T15:30Z"), pd.Timestamp("2026-10-16T15:30Z")  # journée de 24 h


def test_couverture_complete_avec_tous_les_releves():
    releves = [pd.Timestamp("2026-10-15T15:23Z") + pd.Timedelta(hours=3 * i) for i in range(1, 10)]
    c = sentiment.couverture(DEBUT, FIN, releves, PC)
    assert c["releves_attendus"] == 8 and c["releves_reussis"] == 8
    assert c["couverture_partielle"] is False and c["plus_long_trou_heures"] <= 3


def test_couverture_tolere_deux_releves_manques_mais_pas_un_grand_trou():
    tous = [pd.Timestamp("2026-10-15T15:23Z") + pd.Timedelta(hours=3 * i) for i in range(1, 10)]
    # Deux relevés sautés par GitHub (6/8 = 75 %, trou de 9 h) : journée complète.
    assert sentiment.couverture(DEBUT, FIN, tous[:3] + tous[5:], PC)["couverture_partielle"] is False
    # Quatre relevés consécutifs manqués (trou de 15 h) : couverture partielle.
    assert sentiment.couverture(DEBUT, FIN, tous[:2] + tous[6:], PC)["couverture_partielle"] is True
    # Lancement du projet en cours de journée (premier relevé 9 h après le début) mais tous les suivants :
    c = sentiment.couverture(DEBUT, FIN, tous[3:], PC)
    assert c["releves_reussis"] == 5 and c["couverture_partielle"] is True


def test_plafond_par_media():
    parts = pd.Series({"CNBC": 0.40, "WSJ": 0.25, "FT": 0.15, "BBC": 0.10, "NYT": 0.10})
    poids = sentiment.poids_plafonnes(parts.copy(), 0.25)
    assert poids.max() == pytest.approx(0.25) and poids.sum() == pytest.approx(1)
    # Les 15 points retirés à CNBC sont répartis au prorata entre FT, BBC et NYT.
    assert poids["FT"] == pytest.approx(0.15 + 0.15 * 0.15 / 0.35)
    assert poids["BBC"] == pytest.approx(poids["NYT"])
    # Simulation : CNBC très négatif et surreprésenté → le plafond adoucit le solde.
    articles = pd.DataFrame({"media": ["CNBC"] * 6 + ["WSJ", "FT", "BBC", "NYT"],
                             "classe": ["negatif"] * 6 + ["positif"] * 4})
    assert sentiment.solde_avec_plafond(articles, 100) == -20.0     # sans plafond effectif
    assert sentiment.solde_avec_plafond(articles, 25) == pytest.approx(50.0)


def test_dates_approximatives_exclues_du_solde_des_tests():
    articles = pd.DataFrame({
        "classe": ["positif", "positif", "negatif", "neutre"], "p_positif": [0.9, 0.8, 0.1, 0.1],
        "p_negatif": [0.05, 0.1, 0.9, 0.1], "titre": list("abcd"), "source": list("abcd"), "media": list("abcd"),
        "lien": list("abcd"), "date_publication_utc": ["2026-10-16T10:00:00Z"] * 4,
        "date_approximative": [False, True, False, False]})
    ind = sentiment.indicateurs_journee(articles, P)
    assert ind["solde"] == 25.0                 # tous les articles comptent dans l'indicateur du jour
    assert ind["solde_dates_fiables"] == 0.0    # sans l'article à date approximative
    assert ind["nb_dates_approximatives"] == 1


def test_etape_sentiment_de_bout_en_bout(tmp_path, monkeypatch):
    from pipeline import traitement_nuit as tn
    from pipeline.journal import Journal
    monkeypatch.setattr(ct, "DOSSIER_TITRES", tmp_path / "titres")
    monkeypatch.setattr(tn, "FICHIER_JOURNAL", tmp_path / "journal.csv")
    monkeypatch.setattr(tn, "FICHIER_SENTIMENT", tmp_path / "sentiment.json")
    monkeypatch.setattr(tn, "FICHIER_HISTO_SENTIMENT", tmp_path / "sentiment_quotidien.csv")
    lignes = []
    for i in range(40):  # 40 articles « marché » de la journée du vendredi 16/10/2026
        classe = "negatif" if i < 25 else "neutre"
        lignes.append({"id": f"id{i}", "groupe": "marche", "source": f"S{i % 4}", "type": "direct",
                       "titre": f"Titre {i}", "lien": f"https://x/{i}",
                       "date_publication_utc": "2026-10-16T09:00:00Z", "date_approximative": False,
                       "seance": "2026-10-16", "p_positif": 0.05, "p_neutre": 0.9 if classe == "neutre" else 0.1,
                       "p_negatif": 0.85 if classe == "negatif" else 0.05, "classe": classe,
                       "collecte_utc": "2026-10-15T18:23:00Z"})
    ct.enregistrer(lignes)
    tn.etape_sentiment(Journal(), maintenant=pd.Timestamp("2026-10-17T04:41:00Z"))
    d = json.loads((tmp_path / "sentiment.json").read_text(encoding="utf-8"))
    assert d["derniere_seance"] == "2026-10-16"
    marche = d["groupes"]["marche"]
    assert marche["nb_articles"] == 40 and marche["solde"] == -62.5 and marche["etiquette"] == "négatif"
    assert "esg" not in d["groupes"]
    histo = pd.read_csv(tmp_path / "sentiment_quotidien.csv", encoding="utf-8-sig")
    assert list(histo["seance"].astype(str)) == ["2026-10-16"]
