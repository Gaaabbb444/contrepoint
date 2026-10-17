# Méthodologie — texte source

*Ce fichier est la source rédactionnelle de la page « Méthodologie » du site (étape 5). Il est complété à chaque étape. Les chiffres cités sont datés ; le site affiche les valeurs du jour.*

---

Cette page explique d'où viennent les chiffres de Contrepoint, comment ils sont calculés, et ce qu'ils ne permettent pas de conclure. Chaque choix de méthode y est justifié ; les paramètres correspondants sont modifiables dans le dossier `config/` du dépôt.

## Performance des ETF

### Ce que l'on compare
Quatre ETF ESG, tous construits à partir du MSCI World, sont comparés à un ETF qui réplique le MSCI World lui-même. Trois sont de la même famille (iShares : mêmes frais de 0,20 %, même gestion, même domicile), pour que l'écart observé vienne de la méthode ESG et non des frais. Le quatrième, BNP Paribas Easy MSCI World SRI PAB (labellisé ISR, 0,25 % de frais), est présenté à part, en complément.

### Comment
- **Rendement total** : tous les ETF sont capitalisants (les dividendes sont réinvestis dans le fonds) ; leur cours de bourse suffit donc à mesurer un rendement « dividendes réinvestis ».
- **Mêmes dates, même devise** : tous les cours sont en euros et seules les séances communes à tous les ETF sont retenues.
- **Mêmes horaires** : tous les ETF clôturent à 17 h 30 (Francfort, Paris, Amsterdam). Les comparaisons entre eux sont donc homogènes. En revanche, nos chiffres peuvent différer de quelques dixièmes de point de ceux publiés par les émetteurs, qui calculent sur la valeur liquidative arrêtée après la clôture de Wall Street (vérifié : écart de 0,1 point sur 3 et 5 ans pour l'ETF SRI).
- **Indicateurs** : performance cumulée ; performance annualisée (à partir de 3 ans) ; performance relative (ETF ESG − MSCI World, en points) ; volatilité annualisée (écart-type des variations quotidiennes × √252) ; perte maximale ; ratio de Sharpe (à partir d'1 an, avec le €STR de la BCE comme taux sans risque) ; écart de suivi (volatilité de la différence quotidienne avec le MSCI World).

### Contrôle des données
- **Cours erronés** : une séance est écartée si un seul ETF s'écarte de plus de 5 % du MSCI World puis revient le lendemain, alors que les autres ETF suivent le MSCI World. Un vrai choc de marché (comme début avril 2025) touche tous les ETF ensemble et n'est jamais écarté. Exemple réel détecté : le 24/10/2025, Yahoo Finance affichait pour un ETF coté en euros son cours en dollars.
- **Clôtures provisoires** : Yahoo publie parfois la clôture officielle avec plusieurs heures de retard. On utilise alors le dernier prix de la séance, signalé comme **provisoire** (astérisque), puis remplacé automatiquement par la clôture officielle dès sa publication. Tout l'historique est retéléchargé chaque nuit.

### Le cas de l'ETF Paris-Aligned (raccordement et taux de change)
Sa cotation en euros à Francfort n'existe que depuis le 25/08/2025. Avant cette date, on utilise sa cotation en dollars d'Amsterdam, convertie en euros au taux de référence de la BCE, et l'on « raccorde » les deux séries (seules les variations sont reprises).

Deux sources de bruit affectent cette partie ancienne :
1. **Le décalage horaire du taux de change** : le taux de la BCE est fixé vers 14 h 15, alors que l'ETF clôture à 17 h 30. Si l'euro bouge entre ces deux heures, la variation en euros d'une séance est légèrement faussée, puis corrigée le lendemain. Sur des périodes longues, ces erreurs se compensent et sont négligeables ; sur les variations quotidiennes, elles ajoutent du bruit.
2. **Le peu d'échanges** sur la cotation d'Amsterdam (cours inchangé une séance sur quinze environ).

Mesure (sur 14 mois où les deux cotations existent) : écart quotidien moyen de 0,28 point, écart de suivi gonflé à 5,9 % contre 2,0 % en direct, mais seulement 0,5 point d'écart sur la performance cumulée. C'est pourquoi la **performance** de cet ETF est fiable sur toutes les périodes, alors que ses **indicateurs de risque quotidiens** (volatilité, écart de suivi, Sharpe) et la mesure de l'effet sectoriel sont signalés « fiabilité réduite » sur 3 et 5 ans.

---

## Pourquoi les approches ESG strictes ont-elles fait moins bien ?

*Données : composition officielle des fonds iShares au 15/10/2026 ; mesure sur les séances du 16/10/2023 au 15/10/2026.*

Une idée répandue veut que les fonds ESG sous-performent parce qu'ils excluent le secteur de l'énergie. Les données racontent une histoire différente.

**1. Ce n'est pas d'abord une question de secteur, mais de quelques très grandes entreprises.** L'ETF SRI contient autant de technologie que le MSCI World (environ 30 %). Mais il ne détient, parmi les sept géants technologiques américains, que Nvidia et Tesla : ni Apple, ni Microsoft, ni Amazon, ni Alphabet, ni Meta, écartés par sa méthode de sélection « best-in-class ». Ces sept valeurs pèsent environ 25 % du MSCI World, contre 12 % de l'ETF SRI.

**2. L'énergie a peu compté sur la période.** Les ETF ESG détiennent peu ou pas d'énergie (0 % pour le SRI, contre 4,3 % pour le MSCI World), mais ce secteur a évolué à peu près comme le marché sur ces trois années : ce pari a pesé pour moins d'un dixième de point.

**3. Mesure.** On compare, séance par séance, l'écart de performance de chaque ETF ESG avec le MSCI World, à l'écart entre un panier des sept géants technologiques et le MSCI World, et à l'écart entre le secteur de l'énergie et le MSCI World (régression linéaire). Sur trois ans :
- **ETF SRI** : environ **la moitié** de son retard s'explique par la sous-pondération des géants technologiques ; l'autre moitié vient de ses autres choix de valeurs.
- **BNP Easy SRI PAB** : environ **70 %** de son retard s'explique de la même façon.
- **ETF Screened** (exclusions légères) : sa légère avance vient de ce qu'en excluant quelques secteurs, il **surpondère** mécaniquement ces géants.

**4. Limites.** La composition utilisée est celle d'aujourd'hui, pas celle d'il y a trois ans. Le panier des sept géants est pondéré selon leurs poids actuels. La régression mesure une association statistique, pas une causalité. Pour l'ETF Paris-Aligned, la mesure est peu fiable (données quotidiennes bruitées avant août 2025, voir plus haut).

**5. Le résultat dépend de la période (rappel affiché sur le site).** De 2023 à 2026, les géants technologiques américains ont porté le marché : tout indice qui les sous-pondère a mécaniquement fait moins bien. Sur une autre période — un recul de ces valeurs, ou une hausse de l'énergie — le classement peut s'inverser. La sous-performance observée n'est donc pas une « loi » de l'investissement responsable, mais la conséquence de ses choix de portefeuille dans un marché donné.


---

## Sentiment de l'actualité

### Sources
Deux groupes de flux RSS gratuits, en anglais : la presse financière et économique générale (CNBC, Wall Street Journal, Financial Times, Bloomberg, BBC, The Guardian, New York Times, Euronews, Deutsche Welle) et la presse spécialisée en finance durable (ESG Today, ESG Dive, ESG News, Responsible Investor, ImpactAlpha, Trellis, FT Moral Money, etc.), complétée par deux recherches Google Actualités (« ESG investing », « sustainable finance »). La liste complète, et les flux écartés avec leur raison, figurent dans `config/flux_rss.yaml`.

Les flux sont relevés toutes les 3 heures : beaucoup ne gardent que leurs 10 à 30 derniers articles, et un relevé quotidien en manquerait la majorité.

### Poids des médias
Chaque article compte autant ; un média très prolifique pourrait donc peser trop lourd (CNBC fournit 4 des 17 flux du groupe « marché »). La part de chaque **média** (et non de chaque flux) dans chaque groupe est calculée chaque nuit sur les 20 dernières séances et publiée sur le site ; une alerte est déclenchée si un média dépasse 25 % d'un groupe. Première mesure (17/10/2026, une seule collecte) : groupe « marché » — Wall Street Journal 20 %, CNBC 19 %, Bloomberg 18 %, Financial Times 16 %, New York Times 12 %, autres 15 % ; aucun média ne dépasse 25 %. Dans le groupe « ESG », les articles de Google Actualités proviennent de dizaines de médias différents, chacun pesant peu. Si le plafond venait à être dépassé durablement, une pondération plafonnée (chaque média ramené à 25 % au plus, l'excédent redistribué aux autres au prorata) est déjà calculée à titre de simulation.

### Traitement
- Seuls le **titre** et le **début du résumé** sont analysés ; l'article complet n'est jamais récupéré.
- **Doublons** : un article est ignoré s'il a le même lien, ou un titre quasi identique (similarité ≥ 90 %), qu'un article déjà retenu dans le même groupe au cours des 3 derniers jours. Quand un article apparaît à la fois dans un flux direct et dans Google Actualités, c'est la version du média lui-même qui est gardée.
- **Droit d'auteur** : le résumé sert uniquement au calcul et n'est jamais enregistré. Le dépôt public ne conserve que le titre, la source, le lien, la date et le score.

### Le modèle : FinBERT
FinBERT (ProsusAI/finbert) est un modèle de langage de type BERT, spécialisé en finance : il a été entraîné sur des textes financiers (corpus Reuters TRC2), puis sur des phrases de presse financière annotées à la main comme positives, négatives ou neutres (Financial PhraseBank, Malo et al., 2014). Pour chaque texte, il donne trois probabilités ; on retient la plus élevée. Chaque article compte autant.

Version figée (Hugging Face, commit `0bc2ac10`, 12/10/2026) pour que les résultats restent comparables dans le temps. Licence CC BY-NC-SA 4.0, © MIH AI B.V. (Prosus) : usage non commercial, avec citation. Références : Araci (2019), *FinBERT: Financial Sentiment Analysis with Pre-trained Language Models* ; Malo et al. (2014), *Good debt or bad debt*.

Pourquoi l'anglais : aucun modèle de sentiment financier en français n'a fait l'objet d'une validation comparable.

**Limite du modèle, constatée dans nos propres données.** FinBERT juge la tonalité de la phrase, pas l'effet de la nouvelle sur les marchés. Exemple réel (16/10/2026) : « Wholesale prices jumped 6.3% annually in September, biggest gain since 2022 » est classé *positif* à 95 %, alors qu'une accélération de l'inflation est plutôt une mauvaise nouvelle pour les marchés (elle éloigne une baisse des taux). À l'inverse, « Dollar Index Falls 0.32% » est classé *négatif* alors que c'est une information neutre. Sur un grand nombre d'articles, ces erreurs se compensent en partie, mais l'indicateur mesure **le ton de l'actualité**, pas une prévision de marché. C'est pourquoi les titres les plus positifs et les plus négatifs sont affichés chaque jour : chacun peut juger de la cohérence du modèle.

### Indicateurs d'une journée
- **Répartition** positif / neutre / négatif, en %.
- **Solde net** = % positifs − % négatifs (de −100 à +100).
- **Étiquette du jour** : le seuil n'est pas fixe, il dépend du nombre d'articles. C'est la **marge d'erreur statistique à 95 %** du solde : 1,96 × √((p + q − (p − q)²) / n), où *n* est le nombre d'articles, *p* la part de positifs et *q* la part de négatifs. L'étiquette est « positif » si le solde dépasse +marge, « négatif » s'il est inférieur à −marge, « neutre » sinon (impossible à distinguer du hasard de l'échantillon). Exemple : avec 30 % de positifs et 30 % de négatifs, la marge vaut ±9,6 points pour 250 articles, mais ±19,6 pour 60. Avec peu d'articles, il faut donc un écart beaucoup plus net pour conclure.
- **Signal insuffisant** : moins de 30 articles, ou marge d'erreur supérieure à 25 points.
- **Score d'un titre** (page « Titres du jour ») : probabilité « positif » moins probabilité « négatif » données par FinBERT, de −1 (très négatif) à +1 (très positif). Les cinq titres les plus positifs et les cinq plus négatifs de chaque groupe sont classés selon ce score.
- **Barres du graphique** : pour 1 mois et 3 mois, une barre par journée de sentiment (contour en pointillé si la journée est partiellement relevée, pas de barre si le signal est insuffisant). Pour les périodes plus longues, une barre par semaine (depuis janvier, 1 an) ou par mois (3 et 5 ans) : c'est la **moyenne simple des soldes des journées exploitables** de la période (signal suffisant et couverture complète) ; l'infobulle indique combien de journées ont été retenues et écartées. Une période sans journée exploitable n'a pas de barre. Aucune barre n'existe avant le 16/10/2026, date de début de la collecte.
- **Limite** : la formule suppose des articles indépendants ; or plusieurs médias couvrent souvent le même événement. Le dédoublonnage réduit ce problème sans le supprimer : la vraie marge est un peu plus large.

### La « journée » de sentiment
Une journée de sentiment couvre les articles publiés **de la clôture de la séance de bourse précédente (17 h 30, heure de Paris) jusqu'à la clôture de la séance du jour**, d'après le calendrier officiel de Xetra (y compris ses clôtures anticipées). Les articles publiés le week-end ou un jour férié sont rattachés à la séance suivante : la journée du lundi va du vendredi 17 h 30 au lundi 17 h 30.

**Pourquoi ce choix.** La performance d'une séance se mesure de la clôture de la veille à celle du jour : la journée de sentiment couvre exactement la même plage.
- Le **test du même jour** (sentiment J et performance J) ne permet aucune interprétation de sens : les articles peuvent faire bouger le marché, mais aussi simplement **commenter** un marché qui a bougé (« les marchés chutent… »).
- Le **test de décalage** (sentiment J et performance J+1) élimine cet effet : tous les articles de la journée J sont publiés **avant** le début de la séance J+1 ; un article ne peut pas commenter une variation qui n'a pas encore eu lieu. Il reste soumis à la règle « corrélation n'est pas causalité » : un troisième facteur peut agir sur les deux.
- **Limite connue** : Wall Street reste ouverte jusqu'à 22 h (heure de Paris). Les articles publiés en soirée sur la séance américaine tombent dans la journée suivante ; ils ne faussent pas le test de décalage, car ils restent antérieurs à la clôture suivante.

**Articles sans date fiable.** Quand un flux ne donne pas de date de publication, l'article reçoit l'heure de sa collecte (connue à 3 heures près) et il est marqué « date approximative ». Il compte dans l'indicateur du jour affiché, mais un second solde, calculé **sans** ces articles, est utilisé pour les tests statistiques, où l'heure exacte compte (un article mal daté pourrait sinon être rattaché à la mauvaise séance). Les articles datés de plus de 36 heures, ou de plus d'une heure dans le futur (date erronée), sont ignorés. Au 17/10/2026, aucun des articles collectés n'était sans date.

**Couverture d'une journée.** Une journée de sentiment n'est fiable que si les flux ont été relevés assez souvent. Elle est marquée automatiquement « couverture partielle » si moins de 75 % des relevés attendus (un toutes les 3 heures) ont réussi, s'il n'y a pas eu de relevé après la clôture, ou si plus de 12 heures se sont écoulées entre deux relevés réussis. Le seuil de 12 heures vient d'une mesure : le flux qui renouvelait le plus vite ses articles (CNBC Top News, 30 articles, retiré depuis) en couvrait environ 13 heures, et le plus rapide des flux actuels (Edie) en couvre environ 23 ; un trou de moins de 12 heures ne fait donc perdre presque aucun article ; 75 % tolère les relevés que GitHub retarde ou saute parfois, sans accepter une journée majoritairement manquée. Une journée partielle reste affichée, avec cette mention, mais elle est exclue des tests statistiques.

**Comment FinBERT traite l'actualité ESG.** Le groupe « ESG » est nettement plus souvent neutre (environ 70 %) que le groupe « marché » (environ 30 %). FinBERT a été entraîné à juger l'effet d'une phrase sur la situation financière d'une entreprise, du point de vue d'un investisseur ; or beaucoup de titres ESG sont informatifs (calendrier réglementaire, publication d'un rapport, lancement d'une initiative) sans conséquence financière explicite, et sont donc classés neutres. Sur les premiers titres collectés, les annonces d'entreprises (lancements, partenariats) ne sont jamais classées négatives, alors que les titres réglementaires le sont plus souvent (environ un quart : contraintes, reports, sanctions). Conséquence : le niveau du solde ESG ne se compare pas à celui du marché, mais à **son propre historique**. Ce taux de neutres est suivi chaque nuit (moyenne sur 20 journées).

### Contrôle externe : GDELT
GDELT, projet universitaire gratuit, publie la « tonalité » moyenne de la presse mondiale, calculée en comptant les mots positifs et négatifs d'un dictionnaire sur les articles complets. C'est une méthode très différente de FinBERT ; les deux séries sont affichées séparément et ne se comparent qu'en tendance. Le service refuse souvent les requêtes : cette série peut donc présenter des trous.

### Historique des changements de sources
Toute modification de la liste des sources change ce que mesure l'indicateur ; elle est donc datée ici. Les changements intervenus avant la première journée exploitable ont été appliqués rétroactivement aux titres déjà collectés, pour que l'historique reste homogène.

| Date | Changement | Raison |
|---|---|---|
| 17/10/2026 | Lancement : 18 flux « marché », 11 flux « ESG », 2 recherches Google Actualités | Flux testés un par un (voir `config/flux_rss.yaml`) |
| 17/10/2026 | ImpactAlpha désactivé | Refuse les serveurs de GitHub (erreur 403) |
| 17/10/2026 | Filtre par mots-clés ESG sur les titres de Google Actualités (42 titres déjà collectés retirés) | 43 % des titres obtenus étaient hors sujet |
| 17/10/2026 | CNBC Top News retiré (titres déjà collectés retirés) | Malgré son nom, actualité générale américaine (politique, élections), pas une rubrique économique |
| 17/10/2026 | Liste noire des médias pour Google Actualités : Kalkine India (titres déjà collectés retirés) | Fiches de notes ESG générées en série (« Zydus Wellness ESG Rating 72 FY2026 ») ; 9 des 97 titres ESG à lui seul |
| 17/10/2026 | Liste noire : scanx.trade ajouté (titres déjà collectés retirés) | Même type de contenu (« V-Guard Industries secures ESG rating of 73 for FY26 ») ; 5 titres |


---

## Mise en parallèle : sentiment et performance relative (volet 3)

### Questions posées
1. Le sentiment de l'actualité évolue-t-il en même temps que la performance relative des ETF ESG (ETF ESG − MSCI World) ? → **corrélation glissante sur 30 séances**.
2. Le sentiment d'un jour est-il lié à la performance relative du **lendemain** ? → **test de décalage J / J+1**. Tous les articles de la journée J sont publiés avant le début de la séance J+1 : ce test écarte l'effet « l'actualité commente le marché ».
3. Les ETF ESG font-ils mieux ou moins bien que le marché les jours de sentiment négatif que les jours de sentiment positif ? → **comparaison des moyennes** (test t de Welch, qui n'exige pas que les deux groupes de jours aient la même dispersion).

Chaque test est mené pour chaque ETF ESG et pour les deux indicateurs de sentiment (marché, ESG), soit 24 tests au total.

### Un test principal, fixé à l'avance
Mener 24 tests expose à un piège : au seuil habituel de 5 %, environ un test sur vingt paraît « significatif » par pur hasard. Avec 24 tests, on s'attend donc à au moins un faux résultat positif, même s'il n'existe aucun lien réel. Choisir après coup le test qui « marche » reviendrait à présenter du hasard comme une découverte.

Pour l'éviter, **un seul test principal a été fixé le 17/10/2026, avant de disposer d'une seule journée exploitable** : *le sentiment « marché » du jour J est-il lié à la performance relative de l'ETF SRI (contre le MSCI World) à la séance suivante J+1 ?* Ce choix se justifie ainsi : le groupe « marché » est le plus fourni (donc le plus précis) ; le test de décalage est le seul qui écarte l'effet « l'actualité commente le marché » ; l'ETF SRI est l'approche ESG la plus exigeante et celle affichée par défaut. Ce test est lu au seuil de 5 %, sans correction, puisqu'il est unique. Il est inscrit dans `config/parametres.yaml` et ne sera pas modifié une fois les données arrivées.

Les 23 autres tests sont **exploratoires**. Leurs probabilités sont corrigées par la **méthode de Holm** : on classe les probabilités de la plus petite à la plus grande, on multiplie la première par 23, la deuxième par 22, et ainsi de suite, en imposant que les valeurs corrigées ne diminuent pas. Un résultat exploratoire ne compte que s'il reste sous 5 % après cette correction, et même alors il est présenté comme une **piste à confirmer**, jamais comme une conclusion. La synthèse automatique ne cite que le test principal.

### Contrôle de validité de l'indicateur
Avant de chercher un lien avec les ETF ESG, on vérifie que l'indicateur mesure bien quelque chose : le sentiment « marché » du jour J est comparé à la performance du MSCI World **le même jour**. Un lien positif signifie que les journées où les marchés montent sont aussi celles où l'actualité financière est plus positive — l'indicateur capte bien l'humeur du marché. **Ce n'est pas une prévision** : une partie de ce lien vient justement de ce que la presse commente la séance en cours.

### Garde-fous
- **Journées exploitables uniquement** : étiquette autre que « signal insuffisant », couverture complète, solde calculé sans les articles à date approximative.
- **Pas de conclusion avant 60 journées exploitables** (environ trois mois de bourse) et, pour la comparaison, au moins 15 journées positives et 15 négatives. Avant ce seuil, le site affiche la progression (par exemple « 12 / 60 jours de bourse ») et la date estimée à laquelle les résultats deviendront interprétables, calculée sur le calendrier officiel de la Bourse de Francfort en supposant que chaque séance à venir soit exploitable.
- **Seuil de significativité de 5 %** : un résultat n'est qualifié de « significatif » que s'il avait moins de 5 % de chances d'apparaître par pur hasard.
- **Tests multiples** : un seul test principal, les autres corrigés par la méthode de Holm (voir ci-dessus).
- **La corrélation glissante ne s'interprète pas seule** : sur 30 séances, elle varie beaucoup par simple hasard. Démonstration faite sur les vraies performances de l'ETF SRI avec un sentiment tiré au hasard : la corrélation glissante a oscillé entre +0,06 et +0,32 alors qu'il n'y avait, par construction, aucun lien. Elle est donc toujours affichée avec une **zone du hasard** : sur 30 séances, une corrélation comprise entre −0,36 et +0,36 peut apparaître par pur hasard dans 95 % des cas. Tant que la courbe reste dans cette zone, elle ne dit rien.
- **Corrélation n'est pas causalité** : un lien statistique ne prouve pas que le sentiment fait bouger les prix ; un troisième facteur peut agir sur les deux.

### Synthèse automatique
Le court texte affiché en haut du site est produit par des **règles fixes**, sans intelligence artificielle : des phrases à trous remplies avec les chiffres du jour (humeur du marché et de l'actualité ESG, bilan des 5 dernières journées, performance relative de l'ETF choisi sur 5 séances et sur un an, état du **test principal**). Elle ne cite jamais un test exploratoire, même « significatif ». Les règles sont écrites dans `pipeline/synthese.py`.

### Contrôle externe GDELT
Quand la série GDELT est indisponible ou vide, rien n'est affiché sur le site (ni graphique vide, ni message d'alerte) : c'est un complément facultatif.

---

## Crédits
Analyse de sentiment : FinBERT (ProsusAI/finbert), © MIH AI B.V., licence CC BY-NC-SA 4.0 (usage non commercial) ; Araci (2019) ; Financial PhraseBank, Malo et al. (2014). Ce crédit figure dans le pied de page de chaque page du site.
