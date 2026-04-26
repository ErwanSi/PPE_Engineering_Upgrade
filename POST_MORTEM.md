# Post-Mortem Individuel — Projet ArbicoreX

**Projet** : PPE Engineering Upgrade — Moteur d'Arbitrage de Taux de Financement Cross-Exchange  
**Equipe** : Erwan Simon, Jeromsan Judis Ramses, Hamza Ouadoudi, Badr El Bakkali, Farhan Morisson  
**Periode** : Octobre 2025 — Avril 2026  
**Ecole** : ECE Paris

---

## POST-MORTEM DE ERWAN SIMON

*Quantitative Researcher & Strategy Architect*

### Cadre general et objectifs initiaux

Ce projet avait pour ambition de construire un moteur d'arbitrage capable d'exploiter les ecarts de taux de financement entre plusieurs exchanges crypto. Mon role consistait a definir la logique quantitative de la strategie, concevoir les filtres statistiques de risque et valider la coherence mathematique de l'ensemble du pipeline, du signal brut jusqu'a la decision de trading. L'objectif etait de produire un systeme qui genere de l'alpha de maniere systematique, avec un cadre de risque rigoureux.

### Trois reussites notables

**1. La mise en place du filtre statistique ADF + Cointegraton**

C'est probablement la contribution dont je suis le plus satisfait. Plutot que de lancer la strategie sur toutes les paires disponibles, j'ai insiste pour qu'on filtre d'abord par stationnarite du spread (test ADF) puis par cointegraton (Engle-Granger). Ca a elimine 29% des paires, mais celles qui restaient etaient solides. Sans ce filtre, on aurait eu des faux signaux en pagaille. Ce qui a rendu ca possible, c'est d'avoir pris le temps de lire les travaux academiques sur le pairs trading avant de coder quoi que ce soit.

**2. Le backtester event-driven avec gates successives**

Plutot qu'un backtester classique qui parcourt les donnees et applique des regles, j'ai opte pour une architecture en "gates" : Risk Gate, Profitability Gate, Trend Filter, et ensuite seulement le signal Z-Score. Chaque trade potentiel doit passer toutes les portes avant d'etre execute. Ca rend le systeme beaucoup plus defensif. Le Sharpe de 3.85 sur la meilleure paire valide cette approche. La cle a ete de prototyper rapidement en Python avec des fonctions simples avant d'assembler le tout.

**3. L'optimiseur Grid Search automatise**

J'avais l'habitude de regler les parametres a la main dans mes projets precedents. Cette fois, j'ai code un optimiseur qui teste 24 combinaisons de parametres et classe les resultats par Sharpe Ratio. Ca m'a fait gagner un temps enorme et ca a montre clairement que Z=2.0 et Lookback=168h etaient optimaux. Le fait de pouvoir montrer une heatmap d'optimisation lors de la soutenance a aussi ete un vrai plus pour la credibilite du projet.

### Trois obstacles majeurs

**1. La gestion du benchmark Funding Hold**

Au depart, j'avais implement un benchmark "Hold" qui achetait simplement le token et le gardait. Mais ca n'avait aucun sens pour une strategie d'arbitrage de funding. Il m'a fallu plusieurs semaines et des resultats absurdes pour comprendre que le bon benchmark etait "Funding Hold", c'est a dire une position permanente qui collecte le spread sans timing. J'aurais du definir le benchmark correctement des le premier jour, en me posant la question "contre quoi compare-t-on exactement ?" avant de coder.

**2. La difficulte a calibrer le slippage**

J'ai utilise un slippage fixe de 1.5 bps par transaction, mais en realite le slippage depend de la liquidite, du moment de la journee, et de la taille de la position. Ce choix simplifie beaucoup le modele et pourrait surestimer la rentabilite reelle. J'aurais aime integrer un modele de slippage dynamique base sur les donnees d'orderbook, mais le temps manquait. Pour un prochain projet, je commencerais par collecter les donnees d'orderbook des le debut.

**3. La communication des resultats quantitatifs a l'equipe**

Quand je presentais des resultats comme "ADF t-stat de -8.47" ou "Sharpe de 2.47", le reste de l'equipe ne voyait pas toujours ce que ca signifiait concretement. J'ai mis du temps a comprendre qu'il fallait traduire ca en termes simples : "cette paire est stable, on peut l'utiliser" ou "avec ces parametres, on gagne 3 fois sur 4". A l'avenir, je preparerais systematiquement une version vulgarisee de chaque resultat quantitatif.

### Pistes d'amelioration

- Pour un prochain projet quantitatif, je definirai le benchmark et les metriques de succes avant d'ecrire la premiere ligne de code. Ca evite de se retrouver a mi-parcours avec des comparaisons qui ne font pas sens.
- Je voudrais apprendre a utiliser des frameworks de backtest existants (comme Backtrader ou Zipline) avant de tout recoder from scratch. Ca ferait gagner du temps et reduirait les risques de bugs dans la simulation.
- Je prevois de suivre un cours sur la communication de donnees quantitatives (data storytelling) pour mieux transmettre mes analyses a des profils non-techniques.

---

## POST-MORTEM DE JEROMSAN JUDES RAMESH

*Backend & Trading Engine Developer*

### Cadre general et objectifs initiaux

Ma responsabilite sur ce projet etait de construire le backend qui fait tourner tout le systeme : l'API REST pour servir les donnees, les WebSockets pour le temps reel, le superviseur du bot de trading, et l'integration avec les exchanges via CCXT. L'objectif etait d'avoir un backend robuste, rapide, et capable de fonctionner en continu sans intervention humaine.

### Trois reussites notables

**1. L'architecture FastAPI asynchrone**

Le choix de FastAPI avec un design entierement asynchrone s'est avere excellent. Les routes live repondent en moins de 50 ms en p99, et le backend supporte 20 clients WebSocket simultanes sans degradation. Ce qui a bien fonctionne, c'est d'avoir fait le choix technique des la premiere semaine et de s'y tenir. J'avais hesite avec Flask, mais FastAPI offrait le support natif de l'async et la documentation automatique avec Swagger, ce qui m'a fait gagner beaucoup de temps.

**2. Le BotSupervisor avec boucle de simulation et mode live**

Le superviseur du bot est la piece la plus complexe du backend. Il gere trois modes (paper, simulation, live), maintient un etat interne avec les positions ouvertes, et genere une simulation historique de 60 jours au demarrage. La partie dont je suis le plus fier, c'est le systeme de journalisation : chaque action du bot est enregistree avec un timestamp, ce qui rend le debugging tres facile. La cle a ete de tester chaque mode separement avant de les combiner.

**3. L'authentification JWT pour securiser le bot**

J'ai implementun systeme d'authentification avec tokens JWT pour proteger les routes du bot. C'etait la premiere fois que je mettais en place de l'auth de zero. Le fait de gerer les credentials chiffres cote serveur et d'avoir un token avec expiration de 24h donne un niveau de securite correct pour un projet de cette taille. J'ai appris en faisant, en suivant la documentation de python-jose et en testant avec Postman a chaque etape.

### Trois obstacles majeurs

**1. La gestion de l'etat du bot entre les redemarrages**

Au debut, quand le backend redemarrait, le bot perdait tout son etat : positions ouvertes, historique, PnL cumule. Il m'a fallu un bon moment pour implementer la persistance dans un fichier JSON. Le probleme de fond etait que j'avais pense le bot comme un processus ephemere alors qu'il devait se comporter comme un service persistent. J'aurais du concevoir le modele de donnees avec la persistance en tete des le depart.

**2. Les problemes de concurrence avec Redis**

Quand les 4 collectors ecrivaient en meme temps dans Redis, il y avait parfois des lectures incoherentes cote backend. J'ai perdu presque une semaine a debugger des valeurs de funding qui semblaient aleatoires avant de comprendre que c'était un probleme de timing de lecture/ecriture. La solution a ete d'utiliser des locks Redis et de standardiser les cles. A l'avenir, je modeliserais les flux de donnees concurrents sur papier avant de coder.

**3. Le mode live jamais teste en conditions reelles**

Le code pour le trading live via CCXT est ecrit et fonctionnel en theorie, mais on ne l'a jamais teste avec de vrais fonds. C'est frustrant parce que tout le reste du pipeline est valide. Le frein etait double : la peur de perdre de l'argent reel et le manque de temps pour mettre en place un environnement de test avec de petits montants. Si c'etait a refaire, j'aurais alloue un petit budget de test (50-100 dollars) des le debut du projet pour valider le mode live graduellement.

### Pistes d'amelioration

- Pour mes prochains projets backend, j'adopterai une base de donnees legere (SQLite ou PostgreSQL) au lieu de fichiers JSON pour la persistance. Ca resout les problemes de concurrence et de corruption de donnees.
- Je voudrais approfondir mes connaissances en tests automatises. Sur ce projet, j'ai principalement teste manuellement avec Postman, ce qui est lent et pas reproductible. Des tests unitaires avec pytest et des tests d'integration auraient detecte certains bugs plus tot.
- Je compte pratiquer le pair programming plus regulierement. Les sessions ou j'ai travaille avec Erwan sur l'integration strategy/backend ont ete les plus productives du projet.

---

## POST-MORTEM DE HAMZA OUADOUDI

*Data Engineer*

### Cadre general et objectifs initiaux

Ma mission etait de construire et maintenir le pipeline de donnees complet du projet : la collecte des funding rates et des prix depuis les 4 exchanges (Binance, Hyperliquid, Extended, Paradex), le nettoyage, l'alignement temporel, et le stockage en format Parquet. Sans donnees fiables, aucune strategie ne peut fonctionner, donc mon travail etait en quelque sorte la fondation de tout le reste.

### Trois reussites notables

**1. Le pipeline de collecte historique robuste**

J'ai reussi a collecter 6 mois de donnees (plus de 2.6 millions d'enregistrements) depuis 4 exchanges avec des API tres differentes. Chaque exchange a ses specificites : Binance utilise un systeme de poids pour le rate limiting, Hyperliquid est extremement lent (0.4 req/s), et Paradex necessite des requetes specifiques a Starknet. Le fait d'avoir gere la pagination, les reessais automatiques et la reprise apres coupure pour chacun d'eux est une reussite technique dont je suis fier. Ce qui m'a aide, c'est d'avoir documente chaque API dans un fichier de notes avant de coder le collector correspondant.

**2. Le script de nettoyage (cleaner.py) qui resout tout**

Le cleaner.py est devenu l'outil central du projet. Il prend les donnees brutes heterogenes des 4 exchanges et produit un dataset propre, aligne a l'heure, avec un taux de NaN de seulement 0.04%. L'interpolation lineaire pour les petites lacunes et la suppression automatique des paires sous le seuil de qualite (5% de NaN) ont ete des choix qui se sont averes payants. Ca a fonctionne parce que j'ai pris le temps de visualiser les donnees brutes avant de coder les regles de nettoyage.

**3. Le choix du format Parquet**

Au debut, je stockais tout en CSV. Quand les fichiers ont depasse 200 Mo, les temps de chargement sont devenus insupportables. Le passage a Parquet a reduit la taille par 8x et le temps de lecture de 10 secondes a moins de 2 secondes. C'est un choix technique simple mais qui a eu un impact enorme sur l'experience de toute l'equipe. J'ai decouvert Parquet en lisant un article sur les bonnes pratiques data engineering, et je suis content de l'avoir applique.

### Trois obstacles majeurs

**1. Les differences de format de funding entre exchanges**

Chaque exchange renvoie les funding rates dans un format different : Binance en pourcentage sur 8h, Hyperliquid en taux horaire, Paradex avec des timestamps Unix differents. J'ai passe presque trois semaines a comprendre et normaliser ces differences. A un moment, j'avais des taux qui semblaient 8 fois trop eleves parce que je n'avais pas divise le funding Binance pour le ramener a une base horaire. Si c'etait a refaire, je commencerais par ecrire des tests unitaires qui verifient que les valeurs normalisees sont dans des plages attendues (par exemple, un funding rate horaire devrait etre entre -0.01% et +0.01% en general).

**2. La gestion du rate limiting d'Hyperliquid**

Hyperliquid impose une limite de 0.4 requetes par seconde, ce qui rend la collecte historique extremement lente. Pour 6 mois de donnees, ca representait plusieurs heures de collecte. J'ai du implementer un systeme de pause avec reprise automatique, mais j'ai quand meme eu des timeout et des collectes incompletes qu'il a fallu relancer manuellement. A l'avenir, j'utiliserais un systeme de queue (comme Celery) pour gerer les collectes de maniere plus fiable et reprendre automatiquement la ou ca s'est arrete.

**3. Le manque de monitoring des donnees en production**

Une fois le pipeline mis en place, je n'avais pas de moyen automatique de savoir si les donnees entrantes etaient correctes. A deux reprises, des donnees aberrantes se sont glissees dans le dataset (un funding rate de 5%, clairement une erreur de l'API) sans que personne ne s'en rende compte pendant plusieurs jours. J'aurais du mettre en place des alertes automatiques qui signalent les valeurs hors normes. C'est quelque chose que je ferai systematiquement a l'avenir.

### Pistes d'amelioration

- Je veux apprendre a utiliser un orchestrateur de pipelines comme Airflow ou Prefect pour gerer les collectes planifiees et les dependances entre les etapes du pipeline. Ca rendrait le systeme beaucoup plus fiable qu'un simple cron job.
- Je prevois d'integrer des validations de donnees automatiques (avec un outil comme Great Expectations) au debut de chaque pipeline pour detecter les anomalies le plus tot possible.
- J'aimerais aussi ameliorer mes competences en visualisation de donnees. Sur ce projet, j'ai souvent du expliquer des problemes de qualite de donnees a l'equipe, et des graphiques clairs auraient aide.

---

## POST-MORTEM DE BADR EL BAKKALI

*Frontend Developer & UI/UX*

### Cadre general et objectifs initiaux

J'etais charge de concevoir et developper l'interface utilisateur du projet avec Next.js. L'objectif etait de creer un dashboard professionnel qui permette de visualiser les donnees de funding en temps reel, de lancer des backtests, de controler le bot, et de consulter les resultats d'optimisation. Le tout devait etre fonctionnel, reactif, et visuellement a la hauteur d'un outil de trading.

### Trois reussites notables

**1. Le design dark theme coherent**

J'ai passe du temps a definir une charte graphique sombre avec des couleurs bien choisies pour les indicateurs positifs et negatifs. Le resultat est un dashboard qui ressemble a un vrai terminal de trading, pas a un projet etudiant. Ce qui a aide, c'est d'avoir etudie des interfaces existantes (TradingView, Deribit) avant de commencer, et d'avoir defini les tokens de couleur dans un fichier CSS unique avant de coder les composants.

**2. L'integration temps reel avec WebSocket**

La matrice de funding rates se met a jour toutes les 15 secondes sans que l'utilisateur n'ait a recharger la page. C'etait la premiere fois que j'implementais des WebSockets dans un projet Next.js, et ca m'a demande pas mal de recherche. Le fait que ca fonctionne de maniere fluide, avec reconnexion automatique en cas de coupure, est quelque chose dont je suis fier. La cle a ete de bien separer la logique WebSocket dans un hook React dedie.

**3. Le Strategy Lab avec backtest interactif**

La page de backtest permet a l'utilisateur de choisir un token, deux exchanges, d'ajuster les parametres (Z-Score, Lookback, fees), et de voir instantanement les resultats avec la courbe d'equity et les KPI. C'est la page la plus complexe de l'application et celle qui a impressionne le plus lors des demos. Ce qui m'a permis de la construire, c'est d'avoir d'abord fait un wireframe papier avant de coder, et d'avoir travaille en etroite collaboration avec Jeromsan pour definir les endpoints API necessaires.

### Trois obstacles majeurs

**1. Les erreurs d'hydratation Next.js**

J'ai passe plusieurs jours bloques sur des erreurs de type "Hydration failed because the initial UI does not match what was rendered on the server." Le probleme venait du fait que certaines donnees (comme les timestamps) etaient differentes entre le rendu serveur et le rendu client. La solution a ete de forcer le rendu client-side pour les composants dynamiques avec `useEffect`, mais j'ai perdu du temps a comprendre le fonctionnement de l'hydratation SSR. Pour un prochain projet, je prendrais le temps de bien comprendre le cycle de rendu de Next.js avant de commencer a coder.

**2. La responsivite mobile negligee**

Le dashboard fonctionne tres bien sur desktop et laptop, mais l'experience est degradee sur mobile et tablette. Les tableaux debordent, la sidebar ne se replie pas correctement. J'ai priorise les fonctionnalites desktop parce que c'est l'usage principal d'un outil de trading, mais avec le recul, j'aurais pu au moins rendre la navigation mobile fonctionnelle avec quelques heures de travail supplementaires. A l'avenir, j'utiliserais une approche mobile-first meme si le public cible est desktop.

**3. L'absence de tests frontend**

Je n'ai ecrit aucun test automatise pour le frontend. Chaque modification necessitait des verifications manuelles sur chaque page, ce qui est devenu de plus en plus chronophage a mesure que l'application grandissait. Vers la fin du projet, j'avais peur de casser quelque chose a chaque commit. J'aurais du au minimum ecrire des tests de snapshot pour les composants principaux. C'est clairement une lacune que je compte combler en apprenant Jest et React Testing Library.

### Pistes d'amelioration

- J'aimerais apprendre Storybook pour developper et tester les composants UI de maniere isolee. Ca permettrait aussi de constituer une bibliotheque de composants reutilisables pour les prochains projets.
- Je prevois d'adopter TypeScript de maniere plus stricte. Sur ce projet, j'ai parfois utilise `any` pour gagner du temps, et ca m'a coute cher en bugs difficiles a tracer. Un typage strict des le debut aurait evite ca.
- Je veux pratiquer le design system : definir tous les tokens (couleurs, espacements, typographies) dans un fichier central et generer les composants a partir de la. Ca garantit la coherence visuelle meme quand le projet grossit.

---

## POST-MORTEM DE FARHAN MORISSON

*DevOps & Blockchain Infrastructure*

### Cadre general et objectifs initiaux

Mon role dans le projet couvrait toute la partie infrastructure : le deploiement avec Docker Compose, la configuration des services (Redis, Backend, Frontend), l'integration avec les blockchains (Starknet pour Paradex et Extended), et la mise en place d'un environnement de developpement reproductible. L'objectif etait que n'importe quel membre de l'equipe puisse lancer l'ensemble du projet avec une seule commande.

### Trois reussites notables

**1. Le Docker Compose qui demarre tout en 28 secondes**

Le fichier `docker-compose.yml` orchestre 3 services (Redis, Backend, Frontend) avec des health checks, des restart policies, et un reseau interne. Le fait que tout demarre en 28 secondes et que n'importe qui puisse lancer le projet avec `docker compose up` est une vraie reussite. Ce qui m'a aide, c'est d'avoir commence par le Docker Compose des les premieres semaines, avant meme que le code ne soit fonctionnel. Ca a force l'equipe a definir les interfaces entre services tres tot.

**2. La configuration Redis optimisee**

Redis sert de bridge entre les collectors et le backend pour les donnees temps reel. J'ai configure la persistance RDB pour ne pas perdre les donnees en cas de redemarrage, et j'ai optimise la structure des cles pour que les lectures soient rapides (2.3 ms pour 50 tokens). L'empreinte memoire reste sous 2 Mo, ce qui est negligeable. Ca a fonctionne parce que j'ai pris le temps de lire la documentation officielle de Redis plutot que de copier des configurations trouvees en ligne.

**3. L'integration avec les API blockchain (Starknet)**

Les exchanges Paradex et Extended fonctionnent sur Starknet, ce qui implique des interactions differentes des exchanges centralises. J'ai du comprendre le fonctionnement des gas fees L2, les formats de requete specifiques, et les limites de debit. C'etait ma premiere experience avec une blockchain L2, et le fait d'avoir reussi a integrer ces exchanges dans le pipeline est formateur. J'ai beaucoup appris en lisant la documentation de Starknet et en experimentant avec des appels API de test.

### Trois obstacles majeurs

**1. Les conflits de versions de dependances entre les services**

Le backend et le frontend utilisent des versions de Node.js differentes, et certaines dependances Python du backend entraient en conflit selon les plateformes (Windows vs Linux dans Docker). J'ai passe beaucoup de temps a resoudre des erreurs de build qui n'apparaissaient que dans Docker mais pas en local. La solution a ete de figer toutes les versions dans les Dockerfiles et les fichiers requirements.txt. A l'avenir, je commencerais chaque projet en definissant un fichier `.tool-versions` partage par toute l'equipe.

**2. L'absence de pipeline CI/CD**

On n'a jamais mis en place de pipeline d'integration continue. Chaque deploiement etait manuel : pull, rebuild, relance. Ca a cause des situations ou le code sur une machine ne correspondait pas a ce qui etait en production. J'aurais du configurer un pipeline GitHub Actions des le debut du projet, meme basique (lint + build + tests). C'est un standard de l'industrie que j'ai neglige par manque de temps, et c'est un regret. Pour un prochain projet, ce sera la premiere chose que je mettrai en place.

**3. Le monitoring en production inexistant**

On n'avait aucun outil pour surveiller l'etat des services en production : pas de metriques, pas d'alertes, pas de logs centralises. Quand le bot ou un collector plantait, on ne le decouvrait que lorsque quelqu'un regardait le dashboard et voyait des donnees manquantes. J'aurais du integrer au minimum un stack de monitoring leger (Prometheus + Grafana ou meme un simple script de health check avec notifications). C'est une lacune que je ne repeterai pas.

### Pistes d'amelioration

- Mon premier objectif est de maitriser GitHub Actions pour mettre en place des pipelines CI/CD sur tous mes futurs projets. Je compte suivre un tutoriel complet et l'appliquer immediatement sur un projet personnel.
- J'aimerais apprendre Terraform ou Pulumi pour gerer l'infrastructure as code. Sur ce projet, toute la configuration etait manuelle, ce qui la rend difficile a reproduire et a documenter.
- Je prevois d'integrer systematiquement un outil de monitoring (au minimum Uptime Kuma ou un health check cron) dans mes prochains deploiements. Savoir que quelque chose ne va pas avant que l'utilisateur s'en plaigne, c'est la base du DevOps.

---

*Documents rediges en avril 2026*  
*Projet ArbicoreX — ECE Paris 2025-2026*
