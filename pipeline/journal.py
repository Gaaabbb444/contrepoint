"""Journal d'exécution : une ligne par étape, pour savoir ce qui a marché ou échoué.

Le journal est un simple fichier CSV (data/journal_execution.csv), lisible dans
Excel. Chaque ligne contient : la date et l'heure (UTC), l'étape, le statut
(ok, avertissement ou echec) et un message explicatif.
"""

import csv
from datetime import datetime, timezone

from pipeline.config import DOSSIER_DATA

FICHIER_JOURNAL = DOSSIER_DATA / "journal_execution.csv"
COLONNES = ["horodatage_utc", "etape", "statut", "message"]


class Journal:
    """Accumule les événements d'une exécution, puis les écrit dans le fichier."""

    def __init__(self):
        self.lignes = []

    def noter(self, etape: str, statut: str, message: str = "") -> None:
        assert statut in ("ok", "avertissement", "echec")
        ligne = {
            "horodatage_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "etape": etape,
            "statut": statut,
            "message": message,
        }
        self.lignes.append(ligne)
        # Affichage immédiat : visible dans les journaux de GitHub Actions.
        print(f"[{statut.upper():>13}] {etape} : {message}")

    def a_des_echecs(self) -> bool:
        return any(l["statut"] == "echec" for l in self.lignes)

    def enregistrer(self) -> None:
        """Ajoute les lignes de cette exécution à la fin du fichier CSV."""
        FICHIER_JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        nouveau = not FICHIER_JOURNAL.exists()
        # « utf-8-sig » : Excel reconnaît alors l'encodage et affiche bien les accents.
        with open(FICHIER_JOURNAL, "a", newline="", encoding="utf-8-sig") as f:
            ecrivain = csv.DictWriter(f, fieldnames=COLONNES)
            if nouveau:
                ecrivain.writeheader()
            ecrivain.writerows(self.lignes)
