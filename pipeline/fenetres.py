"""Journées de sentiment : de la clôture d'une séance de bourse à la suivante.

Définition (correction B, expliquée dans la méthodologie) :
la journée de sentiment J regroupe les articles publiés APRÈS la clôture de la
séance précédente et AU PLUS TARD à la clôture de la séance J (17 h 30, heure
de Paris ; heure réelle les jours de clôture anticipée).
Les articles du week-end ou d'un jour férié tombent donc dans la journée de la
séance suivante (du vendredi 17 h 30 au lundi 17 h 30 → journée du lundi).

Le calendrier utilisé est celui de Xetra (Francfort), où cotent la plupart de
nos ETF ; Paris et Amsterdam clôturent à la même heure.
"""

from functools import lru_cache

import exchange_calendars as xcals
import numpy as np
import pandas as pd


@lru_cache(maxsize=4)
def _clotures(code_calendrier: str) -> pd.Series:
    """Heure de clôture (UTC) de chaque séance, indexée par la date de la séance."""
    cal = xcals.get_calendar(code_calendrier, start="2020-01-01")
    clotures = cal.closes
    if clotures.dt.tz is None:
        clotures = clotures.dt.tz_localize("UTC")
    return clotures.dt.tz_convert("UTC")


def seance_de(moments_utc: pd.Series | pd.DatetimeIndex, code_calendrier: str = "XETR") -> np.ndarray:
    """Pour chaque date de publication (UTC), renvoie la séance (date) de sa journée de sentiment.

    Règle : première séance dont la clôture est postérieure ou égale à la
    publication. Un article publié à 17 h 30 pile appartient à la séance qui
    clôture à ce moment-là ; publié à 17 h 31, il passe à la séance suivante.
    """
    clotures = _clotures(code_calendrier)
    moments = pd.DatetimeIndex(pd.to_datetime(moments_utc, utc=True))
    positions = np.searchsorted(clotures.values, moments.values, side="left")
    if (positions >= len(clotures)).any():
        raise ValueError("date au-delà du calendrier boursier disponible")
    return np.array([d.date().isoformat() for d in clotures.index[positions]])


def bornes(seance: str, code_calendrier: str = "XETR") -> tuple[pd.Timestamp, pd.Timestamp]:
    """Début (clôture précédente, exclue) et fin (clôture de la séance) d'une journée, en heure de Paris."""
    clotures = _clotures(code_calendrier)
    position = clotures.index.get_loc(pd.Timestamp(seance))
    return (clotures.iloc[position - 1].tz_convert("Europe/Paris"),
            clotures.iloc[position].tz_convert("Europe/Paris"))


def seances_closes(maintenant_utc: pd.Timestamp, nombre: int, code_calendrier: str = "XETR") -> list[str]:
    """Les `nombre` dernières séances déjà clôturées à l'instant donné (de la plus ancienne à la plus récente)."""
    clotures = _clotures(code_calendrier)
    closes = clotures[clotures <= maintenant_utc]
    return [d.date().isoformat() for d in closes.index[-nombre:]]
