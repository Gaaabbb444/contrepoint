"""Test de l'alerte « plafond par média dépassé »."""

from pipeline.alertes import alertes_plafond


def test_alerte_si_un_media_depasse_25_pct():
    sentiment = {"repartition_medias": {
        "marche": {"nb_articles": 1200, "nb_seances": 20, "parts_pct": {"CNBC": 27.4, "Financial Times": 21.0}},
        "esg": {"nb_articles": 800, "nb_seances": 20, "parts_pct": {"ESG News": 18.0}},
    }}
    alertes = alertes_plafond(sentiment, 25, 20)
    assert len(alertes) == 1
    titre, texte = alertes[0]
    assert titre == "Plafond dépassé : CNBC pèse plus de 25 % du groupe marché"
    assert "27.4 %" in texte and "20 dernières séances" in texte


def test_pas_d_alerte_sous_le_plafond():
    sentiment = {"repartition_medias": {"marche": {"nb_articles": 10, "nb_seances": 2, "parts_pct": {"FT": 22.2}}}}
    assert alertes_plafond(sentiment, 25, 20) == []
