# Plan d'architecture — Contrepoint

*Performance ESG et sentiment de marché*

*Rédigé le 17 octobre 2026, validé le 17 octobre 2026 avec quatre corrections (A à D), intégrées ci-dessous et repérées par 🔧.*

### Décisions validées
- Compte GitHub déjà connecté sur le PC. Git et Python installés sur le PC uniquement pour développer et vérifier les petits calculs ; FinBERT ne tourne jamais sur le PC.
- BNP Paribas Easy MSCI World SRI PAB : **en complément, hors de la vue principale**, frais signalés, label ISR affiché seulement après vérification dans la liste officielle.
- Google Actualités activé (groupe ESG), avec interrupteur et dédoublonnage par rapport aux autres flux.
- Note MSCI ESG relevée à la main (date + source), MSCI World inclus ; rappel de mise à jour dans le README.
- Ratio de Sharpe (taux sans risque €STR de la BCE) + écart de suivi.
- ETF ESG par défaut : SRI.
- Nom : **Contrepoint**, sous-titre « Performance ESG et sentiment de marché ».
- Maquette Claude Design fournie après l'étape 3, sur données réelles.

---

## 1. Ce que j'ai testé, et ce qui en ressort

| Point du brief | Test réalisé | Résultat |
|---|---|---|
| Prix des ETF via Yahoo Finance | Historique quotidien téléchargé pour 17 ETF candidats | ✅ Fonctionne, historique long et propre pour les ETF retenus |
| Stooq comme source de secours | Téléchargement CSV de 5 ETF | ❌ **Stooq bloque désormais les robots** (vérification JavaScript). Le contourner reviendrait à forcer une protection anti-robot : je ne le ferai pas. Stooq est abandonné. |
| Notes Sustainalytics sur Yahoo | Requête des notes ESG pour les ETF et même pour Apple | ❌ **Yahoo ne fournit plus aucune note ESG** (erreur « introuvable » partout). Piste abandonnée. |
| Notes ESG MSCI | Lecture de la fiche iShares | ⚠️ Seule une note **globale** (AAA à CCC) est affichée, pas de notes E, S, G séparées. Voir § 4.4. |
| Flux RSS | 59 flux testés (34 « marché », 25 « ESG ») | ✅ 18 flux « marché » et 13 flux « ESG » retenus (liste au § 5.1) |
| GDELT DOC 2.0 | 6 requêtes espacées de 6 à 30 secondes | ⚠️ **Refus systématique** (« trop de requêtes »). **Retiré le 17/10/2026** (§ 5.6). |
| FinBERT (ProsusAI/finbert) | Vérification sur Hugging Face | ✅ Disponible, très utilisé (≈ 4 millions de téléchargements par mois). Licence **CC BY-NC-SA 4.0** : usage non commercial autorisé, avec citation. |
| Modèle de sentiment français | Recherche sur Hugging Face | ❌ Aucun modèle financier français éprouvé. On reste en anglais. |
| Banque centrale européenne (BCE) | Taux EUR/USD et €STR | ✅ API officielle, gratuite, sans clé |
| Règle des 60 jours de GitHub | Documentation officielle | ⚠️ La doc parle d'« activité du dépôt » sans la définir. Solution double au § 6.3. |

---

## 2. Vue d'ensemble

```
            ┌───────────────── GitHub (gratuit, dépôt public) ─────────────────┐
            │                                                                   │
 Flux RSS ──┼──► [Toutes les 3 h] collecte + score FinBERT des nouveaux titres  │
            │      → on garde titre, source, lien, date, score (résumé jeté)    │
            │                                                                   │
 Yahoo   ───┼──► [Chaque nuit, 04 h 41 UTC]                                     │
 BCE     ───┼──►   1. prix → performances                                       │
            │      2. agrégation du sentiment de la dernière fenêtre de bourse  │
            │      3. mise en parallèle + synthèse                              │
            │      4. vérification → écriture des JSON → commit automatique     │
            │                                                                   │
            │   docs/  ◄── GitHub Pages sert le site statique qui lit les JSON  │
            └───────────────────────────────────────────────────────────────────┘
```

**Pourquoi collecter les titres toutes les 3 heures alors que le brief dit « une fois par nuit » ?**
Mes tests montrent que beaucoup de flux ne gardent que leurs 10 à 30 derniers articles. Certains ne couvrent que 2 à 13 heures. Une seule collecte nocturne raterait donc la majorité des articles de la journée, et l'échantillon serait biaisé vers la soirée. Ces collectes ont un second avantage : elles créent de l'activité régulière dans le dépôt (§ 6.3).

🔧 **Conséquence de la correction C (droit d'auteur).** Le résumé ne doit jamais être enregistré dans le dépôt public. Or, entre deux collectes, le seul endroit fiable où garder des données est le dépôt lui-même. FinBERT doit donc noter chaque nouvel article **au moment de sa collecte**, puis le résumé est jeté aussitôt. On ne conserve que le titre, la source, le lien, la date de publication et les trois probabilités FinBERT. FinBERT tourne donc toutes les 3 heures, sur quelques dizaines de titres à chaque fois, pendant environ 2 minutes, dans GitHub Actions et gratuitement. **Le site, lui, reste mis à jour une seule fois par nuit** : il n'y a toujours aucune IA en temps réel côté site.

---

## 3. Arborescence des fichiers

```
Projet/
├── README.md                     ← explication pédagogique (pour les entretiens)
├── PLAN_ARCHITECTURE.md          ← ce document
├── requirements.txt              ← liste des bibliothèques Python
│
├── config/                       ← tout ce que tu peux modifier sans toucher au code
│   ├── etf.yaml                  ← les ETF, leurs codes, frais, SFDR, labels, date de vérification
│   ├── flux_rss.yaml             ← les flux RSS, groupe « marche » ou « esg », actif oui/non
│   └── parametres.yaml           ← seuils (étiquette du jour, taille minimale d'échantillon…)
│
├── pipeline/                     ← le code Python, exécuté uniquement dans GitHub Actions
│   ├── collecte_titres.py        ← lit les flux RSS, note les nouveaux titres, jette les résumés
│   ├── collecte_prix.py          ← télécharge les cours (Yahoo) et les taux (BCE)
│   ├── performance.py            ← rendements, volatilité, perte maximale, ratios
│   ├── sentiment.py              ← dédoublonnage + FinBERT + indicateurs du jour
│   ├── mise_en_parallele.py      ← corrélations, test de décalage, comparaison
│   ├── synthese.py               ← phrase automatique en français (règles fixes)
│   ├── journal.py                ← enregistre succès et échecs de chaque étape
│   └── traitement_nuit.py        ← chef d'orchestre : enchaîne tout, isole les pannes
│
├── data/                         ← l'historique, conservé indéfiniment
│   ├── titres/2026/10/2026-10-17.csv          ← titre, source, lien, date, score FinBERT (jamais le résumé)
│   ├── sentiment_quotidien.csv                ← une ligne par jour et par groupe
│   └── journal_execution.csv                  ← une ligne par exécution et par étape
│
├── docs/                         ← le site (GitHub Pages sert ce dossier)
│   ├── index.html                ← vue d'ensemble
│   ├── methodologie.html
│   ├── assets/ (css, js, police, icône)
│   └── data/                     ← JSON produits chaque nuit, lus par le site
│       ├── etat.json             ← date de mise à jour, sources en panne
│       ├── performance.json
│       ├── sentiment.json
│       ├── parallele.json
│       └── synthese.json
│
├── tests/                        ← vérifications automatiques des calculs
└── .github/workflows/
    ├── collecte_titres.yml       ← toutes les 3 heures
    └── traitement_nuit.yml       ← chaque nuit
```

Formats : **CSV** pour l'historique (ouvrable dans Excel, lisible par un jury), **JSON** pour le site.
Volume estimé : environ 30 Mo par an. Un dépôt GitHub peut contenir plusieurs Go : l'historique tient des décennies.

---

## 4. Volet 1 — Performance ESG

### 4.1 Référence : MSCI World plutôt qu'ACWI

Je garde le **MSCI World**. Les indices ESG retenus sont tous **construits à partir du MSCI World** : c'est leur « indice parent ». Les comparer à l'ACWI mélangerait deux effets : l'effet ESG et l'effet « pays émergents », car l'ACWI contient environ 10 % d'émergents absents des indices ESG. On ne saurait plus ce qu'on mesure. L'ACWI serait la bonne référence seulement si l'on choisissait des ETF ESG basés sur l'ACWI.

### 4.2 Sélection proposée

Principe : **même émetteur (iShares), même frais (0,20 %), même réplication physique, même domicile (Irlande), même catégorie capitalisante**. Ainsi, l'écart de performance vient de la méthode de l'indice, et non des frais ou de la gestion. C'est l'argument de rigueur le plus fort devant un jury.

| Rôle | ETF | Code Yahoo | Place / devise | Historique gratuit |
|---|---|---|---|---|
| **Référence** | iShares Core MSCI World UCITS ETF (Acc) — IE00B4L5Y983 | EUNL.DE | Xetra, EUR | depuis 2009 |
| **ESG large** | iShares MSCI World Screened UCITS ETF (Acc) — IE00BFNM3J75 | SNAW.DE | Xetra, EUR | depuis oct. 2018 |
| **ESG strict (SRI)** | iShares MSCI World SRI UCITS ETF EUR (Acc) — IE00BYX2JD69 | 2B7K.DE | Xetra, EUR | depuis fév. 2019 |
| **Climat (Paris-Aligned)** | iShares MSCI World Paris-Aligned Climate UCITS ETF (Acc) — IE00BMXC7W70 | WPAB.DE, raccordé à WPAB.AS | Xetra, EUR (Amsterdam, USD, converti, avant le 25/08/2025) | depuis avr. 2021 |
| *Complément (hors vue principale)* | *BNP Paribas Easy MSCI World SRI PAB (Capitalisation)* | *EMWE.PA* | *Paris, EUR* | *depuis 2017* |

Remarques :
- **Changement de nom** : l'ETF « ESG Screened » s'appelle désormais « Screened ». Les règles européennes de 2025 sur le nom des fonds (ESMA) ont imposé ces retraits du mot « ESG ». Je l'expliquerai sur le site, c'est un bon sujet d'entretien.
- **Climat** : la cotation en euros sur Xetra n'existe sur Yahoo que depuis août 2025. J'utilise donc la cotation en dollars d'Amsterdam (5,5 ans d'historique), convertie en euros avec le **taux officiel de la BCE**. L'alternative Amundi (PABW.PA, en euros) n'a que 2 ans et 10 mois d'historique sur Yahoo.
  🔧 **Correction D — à écrire dans la méthodologie** : le taux de référence de la BCE est fixé vers **14 h 15** (heure de Paris), alors que l'ETF clôture à **17 h 30**. Si l'euro bouge entre ces deux heures, la variation en euros d'un jour donné est légèrement faussée, puis corrigée le lendemain. Sur un mois, un an ou cinq ans, ces petites erreurs se compensent et deviennent négligeables. En revanche, elles ajoutent du **bruit aux variations quotidiennes**, donc à la volatilité, à l'écart de suivi et aux corrélations jour par jour de cet ETF. La méthodologie le signalera, et j'en mesurerai l'ampleur à l'étape 1.
- **BNP Paribas Easy** (validé) : affiché **en complément, hors de la vue principale**, avec ses frais signalés. Il combine deux filtres (SRI + Paris-Aligned) et n'est pas de la même famille que les iShares. Son label ISR ne sera affiché qu'après vérification dans la **liste officielle des fonds labellisés**.
- **SFDR et labels** : je les relèverai **dans les documents officiels** (prospectus, annexe SFDR, site du label ISR, liste Greenfin) à l'étape 1, avec la date de vérification, dans `config/etf.yaml`. Je ne les écris pas ici de mémoire : plusieurs ETF « Paris-Aligned » sont passés de l'article 9 à l'article 8 en 2023.

### 4.2 bis Constats de l'étape 1 (17/10/2026)
- **Paris-Aligned, raccordement des cotations** : la cotation d'Amsterdam en dollars est peu échangée. Son cours est inchangé lors de 20 séances sur 294, et sa conversion au taux BCE de 14 h 15 ajoute du bruit. Comparée à la cotation directe en euros de Xetra (disponible depuis le 25/08/2025) :
  - écart quotidien moyen de 0,28 point ;
  - écart de suivi gonflé à 5,9 %, contre 2,0 % en direct ;
  - performance cumulée faussée de seulement 0,5 point sur 14 mois.

  **Décision** : la cotation Xetra en euros est utilisée depuis le 25/08/2025, et la cotation d'Amsterdam convertie seulement avant cette date. Le raccordement conserve les variations, sans mélanger les niveaux de prix. Sur 3 et 5 ans, la volatilité, l'écart de suivi et le Sharpe de cet ETF sont signalés « fiabilité réduite ». Vérification reproductible : `python -m analyses.verifications_etape1`.
- **Cours erroné de Yahoo** : le 24/10/2025, SNAW.DE affichait le cours en dollars de Londres (+17 % puis −13 %). Un filtre « pics isolés » écarte désormais ce type d'erreur : écart de plus de 5 % avec les autres ETF, puis retour le lendemain. Les séances écartées sont listées dans le JSON.
- **Clôture du jour vide chez Yahoo** : le « cours ajusté » de la dernière séance n'est calculé qu'avec retard. Pour ces ETF capitalisants, on utilise donc le cours de clôture, déjà corrigé des divisions d'actions. Une alerte se déclenche si un dividende apparaît.
- **Contrôle par rapport à la fiche officielle** (ETF SRI, au 30/09/2026) :
  - sur 3 et 5 ans, nos chiffres rejoignent ceux d'iShares à 0,1 point près ;
  - sur des périodes courtes, l'écart peut atteindre 1,3 point. iShares calcule sur la valeur liquidative, arrêtée après la clôture américaine, et nous sur le cours de Xetra à 17 h 30.
  - Tous nos ETF sont cotés à 17 h 30 en Europe. La comparaison entre eux reste donc homogène.
- **Source de secours** : aucune source indépendante gratuite et fiable n'a été trouvée. Le repli prévu est un second chemin d'accès à Yahoo (son interface « chart » directe), utile si la bibliothèque yfinance casse. Si Yahoo entier est en panne, le site garde les dernières données valides, avec leur date.

### 4.2 ter Ajustements validés après l'étape 1
- **Filtre des cours erronés** : il prend le MSCI World pour repère. Une séance n'est écartée que si un seul ETF décroche du MSCI World puis revient le lendemain, alors que les autres le suivent. Les chocs communs, comme celui d'avril 2025, sont conservés, ce que vérifie un test sur les vraies variations. Si c'est le MSCI World qui décroche seul, l'erreur lui est attribuée.
- **Clôtures provisoires** : le dernier prix de séance est utilisé si la clôture officielle manque. Il est mémorisé dans `data/clotures_provisoires.json`, marqué « provisoire » dans les données du site, puis remplacé automatiquement par la clôture officielle. Tout l'historique est retéléchargé chaque nuit.
- **Explication des résultats** (`pipeline/secteurs.py`, `docs/data/secteurs.json`) :
  - poids par secteur et poids des 7 géants technologiques américains, tirés des fichiers officiels de composition iShares (date affichée, rafraîchis chaque semaine) ;
  - mesure, sur 3 ans, de la part de l'écart de performance due aux paris « grandes tech » et « énergie » ;
  - texte dans `contenu/methodologie.md`, avec un rappel que le résultat dépend de la période.
  - La composition du fonds BNP n'a pas été relevée : son site impose d'accepter un profil d'investisseur.

### 4.3 Méthode de calcul

- **Rendement total** : uniquement des ETF capitalisants. Les dividendes sont réinvestis dans le fonds, donc le cours suffit. Vérifié : aucun dividende versé dans les historiques, et une alerte automatique se déclenche si cela change.
- **Indicateurs selon la période** : le rendement annualisé n'est affiché qu'à partir de 3 ans, et le ratio de Sharpe qu'à partir d'1 an. Sur un mois, extrapoler à l'année n'a pas de sens.
- **Mêmes dates** : on ne garde que les jours où **tous** les ETF ont un cours. Aucun cours inventé ni recopié.
- **Même devise** : tout en euros.
- **Contrôle qualité** : détection des cours absents, des cours « figés » (même valeur plusieurs jours, signe d'absence d'échange) et des variations aberrantes. Les anomalies sont enregistrées dans le journal.

**Indicateurs** (pour chaque période : 1 mois, 3 mois, depuis le 1ᵉʳ janvier, 1 an, 3 ans, 5 ans) :

| Indicateur | Définition simple |
|---|---|
| Performance cumulée | Gain ou perte en % sur la période |
| Performance annualisée | Pour 3 et 5 ans seulement, pour comparer à un rendement annuel |
| Performance relative | Performance ESG − performance MSCI World, en points |
| Volatilité annualisée | Amplitude moyenne des variations, ramenée à un an |
| Perte maximale | Pire baisse entre un plus haut et un plus bas sur la période |
| **Ratio de Sharpe** | (Rendement − taux sans risque €STR) ÷ volatilité. C'est le ratio standard en gestion de patrimoine. Le €STR vient de la BCE. |
| **Écart de suivi** *(ajout proposé)* | À quel point l'ETF ESG s'écarte du MSCI World au quotidien. Il indique si l'ETF reste proche du marché ou s'il est très différent. Information réellement utile pour un conseiller. |

### 4.4 Biais signalés sur le site
1. **Frais** : identiques chez iShares (0,20 %). À signaler si l'option BNP est retenue.
2. **Change** : tous les fonds investissent surtout en dollars. Le change pèse sur la performance absolue en euros, mais s'annule presque entièrement dans la performance relative.
3. **Écart de suivi** : un ETF ne reproduit jamais parfaitement son indice.
4. **Biais sectoriel** *(le plus important)* : les indices ESG sous-pondèrent l'énergie et surpondèrent souvent la technologie. Une grande partie de la sur- ou sous-performance vient de ces paris sectoriels, pas d'une « vertu » ESG en soi.
5. **Biais de survie et de sélection** : on ne compare que des fonds qui existent encore aujourd'hui.
6. **Cours de bourse et valeur liquidative** : on utilise le cours de bourse, qui peut légèrement s'écarter de la vraie valeur du fonds.

### 4.5 Notes ESG — ce que je propose
- **Notes E, S, G séparées** : **pas disponibles gratuitement et légalement** pour ces ETF. Yahoo n'en publie plus, et MSCI ne publie gratuitement qu'une note globale. **Je propose de les abandonner.**
- **À la place** (validé) : la **note MSCI ESG du fonds** (AAA à CCC), relevée à la main sur la fiche de l'émetteur, avec sa date et sa source, **y compris pour le MSCI World**, pour situer les ETF ESG. Elle est réutilisée ici à titre de citation, dans un projet personnel non commercial. Le README contiendra un rappel de mise à jour.
- La méthodologie expliquera que **les notes ESG divergent fortement d'une agence à l'autre**. L'étude « Aggregate Confusion » (Berg, Kölbel, Rigobon) trouve une corrélation d'environ 0,54 seulement entre agences. Elle expliquera aussi que **Sustainalytics mesure un risque**, où un score bas est meilleur.

### 4.6 Source de prix de secours — franchise
- **Source principale** : Yahoo Finance, via la bibliothèque `yfinance`. Les conditions de Yahoo autorisent un usage **personnel et non commercial**, ce qui est ton cas. Par prudence, **le dépôt ne stockera pas les cours bruts** : seulement les séries calculées (base 100) et les indicateurs. Les cours sont retéléchargés chaque nuit.
- **Secours** : Stooq n'est plus utilisable. À l'étape 1, je testerai les fichiers officiels des émetteurs et Euronext. **Si aucun secours automatique fiable n'existe, je te le dirai.** Le filet de sécurité reste celui du brief : le site affiche les dernières données valides, avec leur date bien visible.

---

## 5. Volet 2 — Sentiment de l'actualité

### 5.1 Flux retenus (testés le 17/10/2026)

**Groupe « marché »** (18 flux, environ 150 à 250 articles nouveaux par jour) :
CNBC (Top News, Finance, Economy, Investing, Europe) · WSJ (Markets, Economy) · Financial Times (Markets, Global Economy) · Bloomberg (Markets, Economics) · BBC Business · The Guardian (Business, Economics) · New York Times (Business, Economy) · Euronews Business · DW Business.

**Groupe « ESG / finance durable »** (11 flux spécialisés, environ 40 articles par jour) :
ESG Today · ESG Dive · ESG News · Responsible Investor · ImpactAlpha · Trellis (ex-GreenBiz) · FT Moral Money · FT Climate Capital · Edie · GreenMoney · TriplePundit
\+ **2 recherches Google Actualités** (« ESG investing », « sustainable finance »), environ 100 articles supplémentaires par jour (validé). Elles ont un interrupteur dans la configuration, et leurs articles sont dédoublonnés par rapport aux autres flux : si un article de Google Actualités existe déjà dans un flux direct, on garde la version du flux direct.

**Écartés, et pourquoi** :
- Yahoo Finance, Fortune, Bloomberg Green, IPE : flux morts (erreur 404).
- Investing.com, Seeking Alpha : pas de résumé, et renouvellement trop rapide.
- MarketWatch, Nasdaq, Business Insider : 10 à 15 articles couvrant seulement 1 à 2 h.
- Fed, BCE : communiqués officiels, pas de la presse.
- Carbon Brief, Inside Climate News, Climate Home, Guardian Climat : **actualité climatique, pas finance durable**. Une canicule serait classée « négative », ce qui fausserait l'indicateur ESG-finance.

Tout est listé dans `config/flux_rss.yaml`, avec un interrupteur `actif: oui/non` par flux.

### 5.2 Traitement (toutes les 3 heures)
1. Texte analysé = **titre + résumé**, nettoyé du HTML et tronqué, sans récupérer l'article complet.
2. **Dédoublonnage** : même lien, ou titres quasi identiques (similarité ≥ 90 %, par exemple la même dépêche reprise par deux journaux). Il se fait aussi par rapport aux titres déjà enregistrés les jours précédents.
3. **FinBERT** (ProsusAI/finbert), version officielle sur processeur. La version ONNX quantifiée n'est pas nécessaire. Les versions ONNX disponibles sont des conversions d'amateurs peu téléchargées, et la quantification modifie légèrement les résultats. Le modèle est mis en cache entre deux exécutions.
4. Chaque article reçoit 3 probabilités (positif, neutre, négatif). On retient la classe la plus probable.
5. 🔧 **Correction C — droit d'auteur** : le résumé ne sert qu'au calcul et **n'est jamais écrit sur le disque du dépôt**. On conserve uniquement le **titre, la source, le lien, la date de publication et le score**.

### 5.3 🔧 La « journée » de sentiment (correction B)

**Définition** : la journée de sentiment J couvre les articles publiés **de la clôture de la séance de bourse précédente (17 h 30, heure de Paris) jusqu'à la clôture du jour J (17 h 30)**. 17 h 30 est l'heure de clôture commune de Xetra, d'Euronext Paris et d'Euronext Amsterdam, où cotent nos ETF. Une journée de sentiment correspond donc exactement à une séance de bourse.

**Week-ends et jours fériés** : il n'y a pas de séance, donc pas de journée de sentiment propre. Les articles publiés du vendredi 17 h 30 au lundi 17 h 30 forment **la journée de sentiment du lundi**. C'est la même règle pour un jour férié de la Bourse de Francfort, d'après le calendrier officiel Xetra. Ces journées contiennent donc plus d'articles : c'est normal, et le nombre d'articles est toujours affiché.

**Heure de référence d'un article** : la date de publication indiquée dans le flux, convertie à l'heure de Paris. Si un flux n'en donne pas, l'article est marqué « date approximative » : on prend l'heure de sa première collecte, à 3 heures près. Ces articles sont exclus des tests du volet 3.

**Pourquoi ce choix (texte repris dans la méthodologie)** :
La performance du jour J se mesure de la clôture J−1 à la clôture J. Notre journée de sentiment J couvre **exactement la même plage horaire**.
- **Test du même jour** (sentiment J et performance J) : actualité et marché évoluent en même temps. Un lien peut venir des deux sens : l'actualité fait bouger le marché, ou les articles **commentent** un marché qui a bougé (« les marchés chutent… »). Ce test ne permet donc **aucune interprétation de sens**.
- **Test de décalage** (sentiment J et performance J+1) : tous les articles de la journée J sont publiés **avant** le début de la période de performance J+1. Un article ne peut pas commenter une variation qui n'a pas encore eu lieu. Ce test élimine donc l'effet « l'actualité commente le marché ». Il reste soumis à la règle « corrélation ≠ causalité » : un troisième facteur peut agir sur les deux.
- **Limite connue** : Wall Street reste ouverte après 17 h 30 (heure de Paris). Les articles publiés en soirée sur une séance américaine agitée tombent dans la journée suivante. Ils ne faussent pas le test de décalage, car ils restent antérieurs à la clôture suivante, mais ils sont signalés dans la méthodologie.

**Affichage** : le site présente toujours la **dernière journée de sentiment complète**, avec sa plage exacte (par exemple « du jeudi 16/10 à 17 h 30 au vendredi 17/10 à 17 h 30 »). Le samedi et le dimanche, il affiche donc celle du vendredi.

### 5.4 Indicateurs quotidiens (pour « marché » et pour « ESG »)
- Répartition positif / neutre / négatif (en %). Chaque article compte autant.
- **Solde net** = % positif − % négatif, entre −100 et +100.
- 🔧 **Étiquette du jour avec un seuil qui dépend du nombre d'articles (correction A)**. Le seuil est la **marge d'erreur statistique du solde**, calculée chaque jour et pour chaque groupe :

  **seuil = 1,96 × √( (p + q − (p − q)²) / n ) × 100**

  où *n* est le nombre d'articles, *p* la part d'articles positifs et *q* la part d'articles négatifs.
  - *Positif* si le solde est **au-dessus de +seuil**, *négatif* s'il est **en dessous de −seuil**, *neutre* entre les deux, c'est-à-dire impossible à distinguer du hasard de l'échantillon.
  - **« Signal insuffisant »** si *n* < 30 articles, ou si la marge d'erreur dépasse ±25 points : l'échantillon est alors trop petit pour qu'une étiquette ait un sens.
  - Exemples, avec 30 % de titres positifs et 30 % de négatifs : 250 articles → seuil ±9,6 ; 140 articles → ±12,8 ; 60 articles → ±19,6 ; 40 articles → ±24.
  - En plus clair : avec peu d'articles, il faut un écart beaucoup plus net pour afficher « positif » ou « négatif ».
  - Le seuil exact et le nombre d'articles sont affichés dans l'infobulle.
  - Le facteur 1,96, le minimum de 30 articles et la marge maximale de 25 points sont réglables dans `config/parametres.yaml`.
- **Limite signalée** : la formule suppose des articles indépendants. Or plusieurs journaux couvrent souvent le même événement. Le dédoublonnage réduit ce problème sans le supprimer, ce qui rend la vraie marge un peu plus large. C'est une raison de plus pour rester prudent.

### 5.5 Transparence
Chaque jour, les **5 titres les plus positifs et les 5 plus négatifs** (titre, source, lien, probabilité, sans résumé) sont affichés. Tous les titres notés sont archivés en CSV. N'importe qui peut ainsi vérifier la cohérence du modèle.

### 5.5 bis État de l'étape 2 (17/10/2026)
- **Code écrit et testé** (44 tests automatiques) :
  - `collecte_titres.py` : collecte, dédoublonnage, notation et enregistrement sans résumé ;
  - `fenetres.py` : journées de bourse, d'après le calendrier officiel Xetra ;
  - `sentiment.py` : FinBERT et indicateurs du jour ;
  - agrégation quotidienne dans `traitement_nuit.py`.
- **Collecte réelle à blanc** depuis le PC : 31 flux sur 31 fonctionnent. Sur 36 heures : 429 articles lus, 32 doublons, 397 retenus (253 « marché », 144 « ESG »).
- **FinBERT** : version figée (commit `0bc2ac10`, 12/10/2026). Ce commit, publié par ProsusAI, ajoute les conditions de licence CC BY-NC-SA 4.0 et des poids au format sûr « safetensors ». Notre usage, personnel et non commercial, est autorisé avec citation.
- **Mise en cache** (`.github/workflows/collecte_titres.yml`) : la clé du cache contient la version du modèle. Quand le modèle est trouvé dans le cache, tout accès à Hugging Face est coupé (`HF_HUB_OFFLINE=1`), ce qui prouve qu'il n'est pas retéléchargé.
- **Non encore exécuté** : FinBERT lui-même, qui ne peut tourner que dans GitHub Actions. Cela nécessite le dépôt GitHub.

### 5.6 GDELT — retiré le 17/10/2026
- **Décision (17/10/2026, après la mise en ligne)** : GDELT est retiré du traitement. Bilan : 2 réponses sur 7 tentatives depuis GitHub, jamais pour la requête ESG ; série trop lacunaire pour servir de contrôle. Il n'est plus mentionné que dans la partie « Limites » de la méthodologie. Le texte ci-dessous est conservé pour l'historique.
- **Constat** : l'API a refusé presque toutes mes requêtes, même espacées de 30 secondes. Une seule est passée le 17/10/2026 : l'accès est donc possible, mais très intermittent. Les serveurs de GitHub partagent leurs adresses avec beaucoup d'utilisateurs, ce sera sans doute pire.
- **Proposition** : une tentative facultative par nuit (2 requêtes), **qui ne peut jamais faire échouer le reste**. Si elle réussit au premier lancement, elle fournit 3 mois de tonalité comme historique de départ, **affiché séparément** et étiqueté « GDELT — méthode différente ».
- **Différence expliquée sur le site** : GDELT compte des mots positifs et négatifs d'après un dictionnaire, sur des articles complets du monde entier. FinBERT est un réseau de neurones entraîné sur des phrases financières, appliqué à nos titres. Les deux échelles ne sont pas comparables : on ne les mélange jamais.

---

## 6. Automatisation et fiabilité

### 6.1 Horaires (cron en heure UTC)
| Tâche | Horaire | Pourquoi |
|---|---|---|
| Collecte et notation des titres | toutes les 3 h, à la minute 23 | Les heures rondes sont saturées sur GitHub, ce qui provoque des retards ou des sauts |
| Traitement de nuit | **04 h 41 UTC**, soit 06 h 41 à Paris l'été et 05 h 41 l'hiver | Clôtures de la veille disponibles : Xetra et Amsterdam à 17 h 30, Wall Street à 22 h. GitHub peut retarder une tâche planifiée de 10 à 60 minutes : le site reste à jour avant 8 h. |

### 6.2 Résistance aux pannes
- Chaque source est traitée **séparément**. Un flux RSS mort ou un ETF sans cours n'arrête pas le reste.
- Avant d'écraser un fichier du site, **contrôle de validité** : date plus récente, pas de valeur vide ou aberrante, nombre minimal d'articles. Si le contrôle échoue, l'ancien fichier est conservé.
- `etat.json` alimente un bandeau toujours visible : « Mis à jour le … à … », avec la liste des sources indisponibles s'il y en a.
- `journal_execution.csv` enregistre la date, l'étape, le statut et le message d'erreur. GitHub t'envoie aussi un e-mail si la tâche échoue.
- Les deux tâches ne peuvent pas écrire en même temps : verrou GitHub `concurrency`.

### 6.2 bis État de l'étape 3 (17/10/2026)
- **Dépôt public** : https://github.com/Gaaabbb444/contrepoint. Les commits sont signés avec l'adresse anonyme de GitHub, donc aucun e-mail personnel n'est publié.
- **Tâches automatiques**, actives depuis le 17/10/2026 :
  - `collecte_titres.yml` : toutes les 3 heures, à la minute 23 ;
  - `traitement_nuit.yml` : chaque nuit à 04 h 41 UTC. Elle lance d'abord les tests (un code cassé ne produit jamais de chiffres faux), puis les calculs, l'enregistrement et la réactivation des tâches.
- **Testé sur GitHub** :
  - collecte avec FinBERT : 2 min 26 s au premier passage (téléchargement du modèle), puis modèle repris du cache, hors ligne ;
  - traitement de nuit : 4 étapes réussies, GDELT refusé (simple avertissement), commit automatique, réactivation des deux tâches réussie.
- **Fichier d'état** (`docs/data/etat.json`) : il contient la date de la dernière exécution et des dernières données, le statut de chaque étape avec la date de sa dernière réussite (conservée d'une nuit sur l'autre), et les alertes des dernières 24 heures, relevés de titres compris.
- **Tests de résistance** (`tests/test_robustesse.py`) :
  - Yahoo en panne : le site garde ses données ;
  - une étape qui plante n'empêche pas les suivantes, et la tâche passe en rouge, ce qui déclenche un e-mail de GitHub ;
  - la date de dernière réussite est conservée ;
  - des données plus anciennes n'écrasent jamais des données plus récentes.
- **Filtre Google Actualités** : un titre d'agrégateur n'est retenu que s'il contient un mot-clé ESG (liste dans `config/flux_rss.yaml`). Les sigles en majuscules (ESG, COP…) doivent apparaître en majuscules. Les titres déjà collectés ont été nettoyés : 42 retirés.

### 6.3 La règle des 60 jours
La documentation dit qu'en dépôt public, les tâches planifiées sont désactivées après 60 jours **sans activité du dépôt**, sans préciser si les commits du robot GitHub comptent. Ils comptent très probablement, mais ce n'est pas garanti. Double protection :
1. Les commits automatiques quotidiens, plus les collectes toutes les 3 heures.
2. Une étape qui **réactive officiellement la tâche** via l'API de GitHub une fois par mois. C'est gratuit, prévu par GitHub, et ne crée pas de faux commit.

---

## 7. Volet 3 — Mise en parallèle

*Programmé le 17/10/2026 (`pipeline/parallele.py`, `pipeline/synthese.py`, sorties `docs/data/parallele.json` et `docs/data/synthese.json`). Le contrôle de validité (sentiment « marché » du jour J et MSCI World du même jour) a été ajouté. Il a été testé sur des données simulées, sur les vraies performances de l'ETF SRI avec un sentiment simulé (`python -m analyses.demo_volet3`), et en conditions réelles (2 journées pour l'instant, donc progression affichée).*

- **Graphique principal** : performance relative cumulée de l'ETF ESG choisi face au MSCI World, superposée au solde de sentiment, avec option de colorer le fond selon l'étiquette du jour.
- **Corrélation glissante sur 30 jours de bourse** entre le solde de sentiment et la performance relative quotidienne.
- **Test de décalage** : sentiment du jour J comparé à la performance relative du jour de bourse suivant.
- **Comparaison** : performance relative moyenne les jours négatifs et les jours positifs, avec un test statistique (test t de Welch).
- **Alignement** : une journée de sentiment correspond à une séance de bourse (§ 5.3). Les week-ends et jours fériés sont rattachés à la séance suivante. Seules les journées dont l'étiquette n'est pas « signal insuffisant » entrent dans les tests.
- **Garde-fous** :
  - le nombre de jours utilisés est toujours affiché ;
  - **aucune conclusion avant 60 jours de bourse**, et au moins 15 jours dans chaque catégorie : le site affiche « échantillon insuffisant (n = 23 / 60) » ;
  - rappel que « corrélation ≠ causalité » ;
  - avertissement sur les tests multiples : avec 4 ETF et 3 tests, un résultat « significatif » peut sortir par hasard.
- **Synthèse automatique** : phrases à trous, règles fixes, aucune IA. Exemple : « Sentiment négatif cette semaine (solde −14) ; l'indice SRI sous-performe le MSCI World de 0,4 point sur 5 jours. »

---

## 8. Interface (étape 4)
- **Technique** : HTML, CSS et JavaScript simples, sans outil de construction, donc rien à installer pour le site. Graphiques avec **Apache ECharts** (gratuit, open source). Il gère les infobulles, les zones colorées par humeur et le zoom sur période.
- **Vue d'ensemble** : bandeau « humeur du marché » + « humeur ESG », puis la carte « l'ESG fait-il mieux ? » (performance relative selon la période choisie), le graphique de mise en parallèle et la synthèse. Le détail (tableau des indicateurs, titres du jour, notes, SFDR) est accessible en un clic.
- **Interactivité** : choix de la période, choix de l'ETF ESG, infobulles. Rien d'autre.
- **Direction visuelle** : je suivrai la maquette Claude Design si tu me la fournis. Sinon, je te proposerai 2 directions avant de coder.

**Règles d'affichage déjà décidées** (à respecter quelle que soit la maquette) :
- **Pied de page de chaque page** : crédits lus dans `etat.json`, dont FinBERT (© MIH AI B.V., CC BY-NC-SA 4.0), les sources de cours (Yahoo Finance, BCE) et les données ESG.
- **Bandeau de mise à jour** : date des dernières données (`etat.json`), astérisque si la dernière clôture est provisoire, alertes des dernières 24 heures.
- **GDELT** : retiré le 17/10/2026 (§ 5.6) ; mentionné seulement dans les limites de la méthodologie.
- **Volet 3** : tant que l'échantillon est insuffisant, une barre de progression (« 12 / 60 jours de bourse ») et la date estimée, jamais un simple message d'attente.
- **Corrélation glissante** : toujours affichée avec une **zone du hasard** (bande grisée de −0,36 à +0,36 sur 30 séances, valeur lue dans `parallele.json` → `zone_hasard_correlation_glissante`), accompagnée d'une phrase expliquant qu'à l'intérieur de cette zone, la courbe ne dit rien.
- **Test principal et tests exploratoires** : le test principal est mis en avant. Les tests exploratoires sont présentés à part, sous ce nom, avec leur probabilité corrigée (Holm), et jamais formulés comme des conclusions.
- **Journées partielles** : mention « journée partiellement relevée ».
- **Explication des résultats** : rappel que le résultat dépend de la période observée (`secteurs.json`).
- **Notes MSCI** : « non publiée » pour le MSCI World. **BNP** : affiché hors de la vue principale.

**Noms proposés** : **Contrepoint** · **Écart** · **Boussole** · **Baromètre ISR** · **Humeur & Impact**
*(ma préférence : Contrepoint, qui dit exactement la mise en parallèle de deux lignes, l'ESG et l'humeur)*

---

## 9. Choix techniques — résumé

| Choix | Pourquoi |
|---|---|
| Python | Langage de référence en finance et en analyse de données ; FinBERT est en Python |
| GitHub Actions, dépôt public | Minutes illimitées et gratuites pour un dépôt public |
| GitHub Pages, dossier `docs/` | Hébergement gratuit, aucune configuration complexe |
| CSV et JSON dans le dépôt | Gratuit, historique versionné, chaque chiffre traçable dans le temps |
| Yahoo Finance via yfinance | Seule source gratuite testée avec un historique long et propre pour ces ETF |
| API BCE | Source officielle pour l'EUR/USD et l'€STR |
| FinBERT, version officielle sur processeur | Modèle de référence en finance, rapide sur processeur, sans conversion douteuse |
| ECharts | Gratuit, beau, interactif, sans installation |
