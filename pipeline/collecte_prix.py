"""Collecte des données de marché : cours des ETF (Yahoo Finance) et taux de la BCE.

Principe de robustesse : chaque téléchargement est isolé. Si un ETF ou un taux
ne peut pas être récupéré, on le note dans le journal et on continue avec le
reste ; ce module ne fait jamais planter tout le traitement.

Les cours bruts ne sont PAS enregistrés dans le dépôt (prudence vis-à-vis des
conditions d'utilisation de Yahoo) : ils sont retéléchargés chaque nuit et
seules les séries calculées (base 100) et les indicateurs sont publiés.
"""

import io
import time
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import yfinance as yf

from pipeline.journal import Journal

NAVIGATEUR = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36"
API_BCE = "https://data-api.ecb.europa.eu/service/data"


# -----------------------------------------------------------------------------
# 1. Cours des ETF (Yahoo Finance)
# -----------------------------------------------------------------------------

class DividendeDetecte(Exception):
    """L'ETF a versé un dividende : la méthode « cours = rendement total » ne tient plus."""


def _nettoyer(serie: pd.Series) -> pd.Series:
    """Index en dates simples (sans heure ni fuseau), valeurs positives, triées."""
    serie = serie.copy()
    index = pd.DatetimeIndex(serie.index)
    if index.tz is not None:
        index = index.tz_localize(None)
    serie.index = index.normalize()
    serie = pd.to_numeric(serie, errors="coerce").dropna()
    serie = serie[serie > 0]
    serie = serie[~serie.index.duplicated(keep="last")].sort_index()
    # On écarte une éventuelle séance encore en cours (pas de clôture définitive) :
    # la séance d'aujourd'hui (heure de Paris) n'est gardée qu'après 17 h 45.
    maintenant = datetime.now(ZoneInfo("Europe/Paris"))
    aujourd_hui = pd.Timestamp(maintenant.date())
    limite = aujourd_hui if (maintenant.hour, maintenant.minute) < (17, 45) else aujourd_hui + pd.Timedelta(days=1)
    return serie[serie.index < limite].astype(float)


def _cours_ajustes_dividendes(ticker: str) -> tuple[pd.Series, dict]:
    """Pour les ACTIONS (qui versent des dividendes) : cours ajusté, en rendement total.

    Utilisé seulement pour fabriquer des facteurs d'analyse (grandes valeurs
    technologiques), jamais pour les ETF comparés.
    """
    objet = yf.Ticker(ticker)
    df = objet.history(period="max", interval="1d", auto_adjust=True)
    if df is None or df.empty or "Close" not in df:
        raise ValueError("réponse vide")
    return df["Close"], (objet.history_metadata or {})


def _cours_via_yfinance(ticker: str) -> tuple[pd.Series, dict]:
    """Accès principal : la bibliothèque yfinance. Renvoie (cours, métadonnées).

    On prend le cours de clôture « simple » (auto_adjust=False), que Yahoo
    corrige déjà des divisions d'actions. Nos ETF sont capitalisants : ils ne
    versent pas de dividende, donc ce cours est bien un rendement total
    (dividendes réinvestis dans le fonds).
    Pourquoi pas le « cours ajusté » de Yahoo ? Constaté le 17/10/2026 : il
    n'est calculé qu'avec un temps de retard, et la dernière séance resterait
    vide, ce qui décalerait tout le site d'un jour.
    Garde-fou : si un dividende apparaît, on lève une erreur explicite.
    """
    objet = yf.Ticker(ticker)
    df = objet.history(period="max", interval="1d", auto_adjust=False, actions=True)
    if df is None or df.empty or "Close" not in df:
        raise ValueError("réponse vide")
    if "Dividends" in df and df["Dividends"].fillna(0).sum() > 0:
        raise DividendeDetecte(f"{ticker} a versé un dividende : son cours n'est plus un rendement total")
    return df["Close"], (objet.history_metadata or {})


def _cours_via_api_graphique(ticker: str) -> tuple[pd.Series, dict]:
    """Accès de repli : l'interface « chart » de Yahoo, appelée directement.

    C'est la même source (Yahoo), par un autre chemin : utile quand la
    bibliothèque yfinance est cassée par un changement du site de Yahoo.
    """
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{ticker}"
    params = {"period1": 0, "period2": int(time.time()), "interval": "1d", "events": "div"}
    r = requests.get(url, params=params, headers={"User-Agent": NAVIGATEUR}, timeout=30)
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    if res.get("events", {}).get("dividends"):
        raise DividendeDetecte(f"{ticker} a versé un dividende : son cours n'est plus un rendement total")
    dates = pd.to_datetime(res["timestamp"], unit="s", utc=True).tz_convert(res["meta"]["exchangeTimezoneName"])
    return pd.Series(res["indicators"]["quote"][0]["close"], index=dates, dtype=float), res["meta"]


# --- Clôtures provisoires ------------------------------------------------------
# Constaté le 17/10/2026 : dans l'historique de Yahoo, la séance la plus récente
# a souvent une clôture VIDE pendant plusieurs heures, alors que le dernier prix
# de la séance (« regularMarketPrice ») est fourni à part, avec son heure.
# On utilise ce dernier prix comme clôture PROVISOIRE, on le mémorise
# (data/clotures_provisoires.json), et chaque nuit on vérifie si la clôture
# officielle est arrivée : si oui, elle remplace la valeur provisoire.
# Comme tout l'historique est retéléchargé chaque nuit, les 5 dernières
# séances (et toutes les autres) sont systématiquement revérifiées.

def cloture_provisoire(cours_brut: pd.Series, meta: dict, maintenant: pd.Timestamp | None = None
                       ) -> tuple[str, float] | None:
    """Renvoie (date, prix) de la clôture provisoire de la dernière séance, ou None.

    Conditions : la clôture officielle de la dernière séance est vide, le
    dernier prix date bien du jour de cette séance, ET la séance est terminée
    (après 17 h 45, heure de Paris). Le dernier prix échangé de la journée est
    alors le cours de clôture de fait (pour un ETF peu échangé, la dernière
    transaction peut avoir eu lieu avant 17 h 30), mais pas encore la valeur
    officielle publiée.
    """
    if cours_brut.empty or pd.notna(cours_brut.iloc[-1]):
        return None
    prix, heure = meta.get("regularMarketPrice"), meta.get("regularMarketTime")
    fuseau = meta.get("exchangeTimezoneName")
    if prix is None or heure is None or fuseau is None:
        return None
    if maintenant is None:
        maintenant = pd.Timestamp.now(tz="Europe/Paris")
    # Selon le chemin d'accès, l'heure arrive en secondes ou déjà en date.
    if isinstance(heure, (int, float)):
        moment = pd.Timestamp(heure, unit="s", tz="UTC").tz_convert(fuseau)
    else:
        moment = pd.Timestamp(heure)
        moment = moment.tz_convert(fuseau) if moment.tz is not None else moment.tz_localize(fuseau)
    derniere = pd.Timestamp(cours_brut.index[-1])
    derniere_locale = derniere.tz_convert(fuseau) if derniere.tz is not None else derniere.tz_localize(fuseau)
    jour = derniere_locale.date()
    fin_de_seance = pd.Timestamp(jour).tz_localize("Europe/Paris") + pd.Timedelta(hours=17, minutes=45)
    if moment.date() == jour and maintenant >= fin_de_seance:
        return jour.isoformat(), float(prix)
    return None


def fusionner_provisoires(officiel: pd.Series, memoire: dict[str, float],
                          nouvelle: tuple[str, float] | None) -> tuple[pd.Series, dict[str, float]]:
    """Combine les clôtures officielles et les clôtures provisoires mémorisées.

    - une clôture provisoire dont la valeur officielle est désormais publiée
      est abandonnée (l'officielle la remplace) ;
    - sinon elle est réutilisée, et reste marquée provisoire.
    Renvoie la série complétée et la mémoire mise à jour (= les dates encore
    provisoires, avec leur prix).
    """
    memoire = dict(memoire)
    if nouvelle is not None:
        memoire[nouvelle[0]] = nouvelle[1]
    serie = officiel.copy()
    for jour in sorted(memoire):
        if pd.Timestamp(jour) in officiel.index:
            del memoire[jour]  # la clôture officielle est arrivée
        else:
            serie.loc[pd.Timestamp(jour)] = memoire[jour]
    return serie.sort_index(), memoire


def telecharger_cours(ticker: str, journal: Journal, provisoires: dict | None = None,
                      essais: int = 3, action_a_dividendes: bool = False) -> pd.Series | None:
    """Télécharge l'historique quotidien d'un ETF. Renvoie None en cas d'échec.

    `provisoires` : mémoire des clôtures provisoires {ticker: {date: prix}},
    lue et mise à jour par cette fonction (si elle est fournie).
    `action_a_dividendes` : True pour une action qui verse des dividendes
    (cours ajusté des dividendes, sans le garde-fou réservé aux ETF).
    """
    methodes = (_cours_ajustes_dividendes,) if action_a_dividendes else (_cours_via_yfinance, _cours_via_api_graphique)
    for methode in methodes:
        for essai in range(1, essais + 1):
            try:
                brut, meta = methode(ticker)
                serie = _nettoyer(brut)
                if provisoires is not None:
                    serie, provisoires[ticker] = fusionner_provisoires(
                        serie, provisoires.get(ticker, {}), cloture_provisoire(brut, meta))
                    if not provisoires[ticker]:
                        del provisoires[ticker]
                if len(serie) < 20:
                    raise ValueError(f"seulement {len(serie)} cours")
                if methode is _cours_via_api_graphique:
                    journal.noter(f"prix:{ticker}", "avertissement",
                                  "yfinance indisponible, cours obtenus par l'accès de repli de Yahoo")
                return serie
            except DividendeDetecte as erreur:
                # Inutile de réessayer : c'est la méthode qui ne convient plus.
                journal.noter(f"prix:{ticker}", "echec", str(erreur))
                return None
            except Exception as erreur:  # noqa: BLE001 — on veut tout attraper ici
                derniere_erreur = f"{methode.__name__} (essai {essai}) : {erreur}"
                time.sleep(2 * essai)
    journal.noter(f"prix:{ticker}", "echec", derniere_erreur)
    return None


# -----------------------------------------------------------------------------
# 2. Données de la Banque centrale européenne (gratuites, officielles, sans clé)
# -----------------------------------------------------------------------------

def _serie_bce(cle: str, debut: date) -> pd.Series:
    """Télécharge une série de l'API de la BCE au format CSV."""
    url = f"{API_BCE}/{cle}"
    r = requests.get(url, params={"startPeriod": debut.isoformat(), "format": "csvdata"}, timeout=60)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    serie = pd.Series(df["OBS_VALUE"].values, index=pd.to_datetime(df["TIME_PERIOD"]))
    return pd.to_numeric(serie, errors="coerce").dropna().sort_index()


def telecharger_eurusd(debut: date, journal: Journal) -> pd.Series | None:
    """Taux de change de référence de la BCE : nombre de dollars pour 1 euro.

    Il est fixé chaque jour ouvré vers 14 h 15 (heure de Paris).
    """
    try:
        return _serie_bce("EXR/D.USD.EUR.SP00.A", debut)
    except Exception as erreur:  # noqa: BLE001
        journal.noter("bce:eurusd", "echec", str(erreur))
        return None


def telecharger_estr(debut: date, journal: Journal) -> pd.Series | None:
    """€STR : taux d'intérêt au jour le jour de la zone euro, en % par an.

    C'est le « taux sans risque » utilisé pour le ratio de Sharpe.
    """
    try:
        return _serie_bce("EST/B.EU000A2X2A25.WT", debut)
    except Exception as erreur:  # noqa: BLE001
        journal.noter("bce:estr", "echec", str(erreur))
        return None


def convertir_en_euros(cours_usd: pd.Series, eurusd: pd.Series, report_max_jours: int) -> pd.Series:
    """Convertit des cours en dollars en euros avec le taux BCE du même jour.

    Les jours où la BCE ne publie pas de taux (jours fériés TARGET), on reprend
    le dernier taux connu, au plus `report_max_jours` jours en arrière. Au-delà,
    le cours est abandonné plutôt que converti avec un taux trop ancien.
    """
    gauche = cours_usd.rename("cours").rename_axis("date").reset_index()
    droite = eurusd.rename("taux").rename_axis("date").reset_index()
    # Même précision de date des deux côtés (sinon pandas refuse la fusion).
    gauche["date"] = gauche["date"].astype("datetime64[ns]")
    droite["date"] = droite["date"].astype("datetime64[ns]")
    fusion = pd.merge_asof(gauche.sort_values("date"), droite.sort_values("date"), on="date",
                           direction="backward", tolerance=pd.Timedelta(days=report_max_jours))
    fusion = fusion.dropna(subset=["taux"]).set_index("date")
    return fusion["cours"] / fusion["taux"]


def raccorder(ancienne: pd.Series, recente: pd.Series) -> tuple[pd.Series, pd.Timestamp]:
    """Prolonge une série récente vers le passé avec une série plus ancienne.

    Exemple : un ETF coté en euros à Francfort seulement depuis 2025, mais en
    dollars à Amsterdam depuis 2021. Pour chaque date antérieure au premier
    cours de la série récente, on reprend les VARIATIONS de l'ancienne série,
    mises à l'échelle pour qu'à la date de jonction les deux séries coïncident.
    On ne mélange donc jamais deux niveaux de prix différents : seules les
    variations comptent, et ce sont elles qui font la performance.
    """
    jonction = recente.index[0]
    avant = ancienne[ancienne.index <= jonction]
    if avant.empty:
        return recente, jonction
    facteur = recente.iloc[0] / avant.iloc[-1]
    prolongement = avant[avant.index < jonction] * facteur
    return pd.concat([prolongement, recente]).sort_index(), jonction


# -----------------------------------------------------------------------------
# 3. Contrôle qualité des séries de cours
# -----------------------------------------------------------------------------

def controler_qualite(serie: pd.Series, seuil_fige: int, seuil_aberrant_pct: float) -> dict:
    """Repère les anomalies d'une série de cours, sans la modifier.

    - cours « figés » : même valeur pendant plusieurs séances (pas d'échanges) ;
    - variations « aberrantes » : hausse ou baisse quotidienne anormalement forte ;
    - fraîcheur : date du dernier cours.
    """
    variations = serie.pct_change().dropna()
    aberrantes = variations[variations.abs() * 100 > seuil_aberrant_pct]

    # Longueur des séquences de cours identiques consécutifs.
    identique = serie.diff().eq(0)
    groupes = (~identique).cumsum()
    longueurs = identique.groupby(groupes).sum()
    episodes_figes = int((longueurs >= seuil_fige).sum())

    return {
        "premier_cours": serie.index[0].date().isoformat(),
        "dernier_cours": serie.index[-1].date().isoformat(),
        "nb_cours": int(len(serie)),
        "episodes_cours_figes": episodes_figes,
        "variations_aberrantes": [
            {"date": d.date().isoformat(), "variation_pct": round(v * 100, 2)} for d, v in aberrantes.items()
        ],
    }
