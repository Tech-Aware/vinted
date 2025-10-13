# Assistant d'annonces Vinted

Application de bureau légère construite avec [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter)
pour générer rapidement des titres et descriptions Vinted à partir de photos
et de commentaires utilisateur. L'outil est pensé pour être lancé aussi bien
sous Windows que sous Chromebook (via l'environnement Linux).

## Fonctionnalités

- Sélection de plusieurs photos avec prévisualisation vignette.
- Zone de saisie des tâches et défauts détectés par l'utilisateur.
- Génération automatique d'un titre et d'une description structurée grâce à
  l'API OpenAI Vision (GPT-4o).
- Résultats affichés dans deux zones éditables prêtes au copier/coller.
- Gestion des templates d'annonces (fournit un modèle Levi's femme par défaut).

## Pré-requis

- Python 3.10 ou plus récent.
- Accès à l'API OpenAI avec un modèle vision (par exemple `gpt-4o-mini`).
- Clé API disponible via la variable d'environnement `OPENAI_API_KEY`.

## Installation

1. Créez un environnement virtuel et activez-le.
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows PowerShell : .venv\Scripts\Activate.ps1
   ```
2. Installez les dépendances Python.
   ```bash
   pip install -r requirements.txt
   ```
3. (Optionnel) Définissez un modèle vision spécifique.
   ```bash
   export OPENAI_VISION_MODEL=gpt-4o
   ```

## Lancement

Exécutez l'application en module afin que les imports relatifs fonctionnent :
```bash
python -m app.main
```

L'interface s'ouvre avec trois zones principales :

1. **Prévisualisation des images** : ajoutez vos photos via « Ajouter des photos ».
2. **Commentaires** : précisez les défauts ou informations complémentaires.
3. **Résultats** : titre et description générés, modifiables directement.

Cliquez sur « Analyser » pour envoyer les photos et commentaires à GPT. Les
données transitent en base64 dans la requête OpenAI. Une fois la réponse
reçue, les champs sont remplis avec le template Levi's.

## Personnalisation des templates

Les templates sont déclarés dans `app/backend/templates.py`. Chaque entrée
comprend :

- `name` : identifiant affiché dans la liste déroulante.
- `description` : texte descriptif (pour usage futur dans l'UI).
- `prompt` : instructions complètes envoyées au modèle.

Ajoutez vos propres structures en enrichissant le dictionnaire `_templates`.

## Intégration OpenAI

La classe `ListingGenerator` (fichier `app/backend/gpt_client.py`) encapsule
l'appel à `openai`. L'initialisation de la librairie est paresseuse afin de
permettre l'ouverture de l'interface même sans clé configurée. Toute erreur
renvoyée par l'API est affichée dans la barre de statut de l'application.

## Déploiement sur Chromebook

- Activez Linux (Crostini) et installez Python 3.10.
- Copiez le projet et suivez les instructions d'installation.
- Lancez `python -m app.main` depuis le terminal Linux. L'application s'exécute
  dans une fenêtre dédiée.

## Déploiement sur Windows

- Installez Python 3.10 depuis le Microsoft Store ou python.org.
- Ouvrez PowerShell, créez l'environnement virtuel et installez les dépendances.
- Lancement identique : `python -m app.main`.

## Limitations connues

- Une connexion Internet est nécessaire pour l'appel OpenAI.
- L'interface ne redimensionne pas encore dynamiquement les vignettes.
- Aucun cache n'est implémenté pour réutiliser des analyses précédentes.

## Licence

Projet fourni à titre d'exemple pédagogique, sans licence spécifique.
