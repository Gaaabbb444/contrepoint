"""Génère l'image d'aperçu (partage LinkedIn, e-mail) et les icônes d'onglet du site.

Lancement (une seule fois, ou après un changement d'identité visuelle) :
    python outils/images_partage.py

Utilise les polices du site (Newsreader, IBM Plex Sans, licence SIL OFL 1.1),
converties à la volée depuis leurs fichiers .woff2. Aucune donnée chiffrée
n'apparaît sur l'image : elle ne peut donc pas devenir périmée.
Dépendances (outil ponctuel, pas nécessaires au traitement de nuit) :
    pip install pillow fonttools brotli
"""

import io
from pathlib import Path

from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parent.parent
POLICES = RACINE / "docs" / "assets" / "polices"
SORTIE = RACINE / "docs" / "assets"
PAPIER, ENCRE, GRIS, GRIS_CLAIR, BLEU = "#F5F4F0", "#15171C", "#4A4E57", "#5C6068", "#2D5A8A"


def police(fichier: str, taille: int, graisse: int | None = None) -> ImageFont.FreeTypeFont:
    """Charge une police .woff2 du site (convertie en mémoire) à la taille voulue."""
    tt = TTFont(POLICES / fichier)
    tt.flavor = None
    tampon = io.BytesIO()
    tt.save(tampon)
    tampon.seek(0)
    f = ImageFont.truetype(tampon, taille)
    if graisse is not None:
        try:  # police variable : on fixe la graisse (et la taille optique si elle existe)
            axes = f.get_variation_axes()
            valeurs = []
            for a in axes:
                nom = a.get("name", b"")
                nom = nom.decode() if isinstance(nom, bytes) else str(nom)
                if nom.lower().startswith("weight"):
                    valeurs.append(graisse)
                elif "optical" in nom.lower():
                    valeurs.append(min(a["maximum"], max(a["minimum"], taille * 0.75)))
                else:
                    valeurs.append(a.get("default", a["minimum"]))
            f.set_variation_by_axes(valeurs)
        except Exception:  # noqa: BLE001 — police non variable : on garde la graisse par défaut
            pass
    return f


def image_partage() -> None:
    l, h = 1200, 630
    im = Image.new("RGB", (l, h), PAPIER)
    d = ImageDraw.Draw(im)
    marge = 88
    titre = police("newsreader-romain-latin.woff2", 132, 500)
    sous_titre = police("ibm-plex-sans-latin.woff2", 36, 400)
    petit = police("ibm-plex-sans-latin.woff2", 24, 500)
    d.text((marge, 64), "TABLEAU DE BORD · MIS À JOUR CHAQUE NUIT", font=petit, fill=GRIS_CLAIR)
    d.text((marge, 120), "Contrepoint", font=titre, fill=ENCRE)
    d.text((marge, 300), "Performance ESG et sentiment de marché", font=sous_titre, fill=GRIS)
    # Double filet, comme sous l'en-tête du site.
    d.rectangle([marge, 384, l - marge, 385], fill=ENCRE)
    d.rectangle([marge, 389, l - marge, 390], fill=ENCRE)
    texte = police("newsreader-italique-latin.woff2", 34)
    d.text((marge, 430), "Les fonds ESG mondiaux font-ils mieux que le MSCI World ?", font=texte, fill=ENCRE)
    d.text((marge, 478), "Et que dit l’humeur de l’actualité financière ?", font=texte, fill=ENCRE)
    d.text((marge, 556), "ETF ESG face au MSCI World · sentiment FinBERT · méthodologie ouverte",
           font=police("ibm-plex-sans-latin.woff2", 22, 400), fill=GRIS_CLAIR)
    im.save(SORTIE / "apercu-partage.png", optimize=True)


def icones() -> None:
    for taille, nom in ((32, "icone-32.png"), (180, "icone-180.png"), (512, "icone-512.png")):
        echelle = 4  # dessin en grand puis réduction : bords plus nets
        t = taille * echelle
        im = Image.new("RGBA", (t, t), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, t - 1, t - 1], radius=int(t * 0.18), fill=ENCRE)
        f = police("newsreader-romain-latin.woff2", int(t * 0.78), 500)
        boite = d.textbbox((0, 0), "C", font=f)
        x = (t - (boite[2] - boite[0])) / 2 - boite[0]
        y = (t - (boite[3] - boite[1])) / 2 - boite[1]
        d.text((x, y), "C", font=f, fill=PAPIER)
        im.resize((taille, taille), Image.LANCZOS).save(SORTIE / nom, optimize=True)


if __name__ == "__main__":
    image_partage()
    icones()
    print("Images créées dans", SORTIE)
