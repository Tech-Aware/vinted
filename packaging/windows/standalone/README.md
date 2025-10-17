# Packaging standalone Windows (compatibilité Windows 7/8)

Ce dossier contient les scripts nécessaires pour produire un binaire PyInstaller autonome fonctionnant sur toutes les éditions 64 bits de Windows supportant Python 3.8 (Vista SP2 et versions ultérieures).

## Pré-requis

- Python 3.8 (ou plus récent) 64 bits installé localement.
- Accès PowerShell avec l'exécution des scripts autorisée (`Set-ExecutionPolicy -Scope Process RemoteSigned`).
- Connexion Internet pour installer les dépendances Python lors du build.

## Construction de l'archive

Exécutez la commande suivante depuis PowerShell :

```powershell
powershell -ExecutionPolicy Bypass -File packaging/windows/standalone/build.ps1 -PythonPath "C:\\Python38\\python.exe"
```

Le script :

1. installe les dépendances de l'application ainsi que PyInstaller avec l'interpréteur fourni ;
2. exécute PyInstaller avec le spec `vinted_standalone.spec` ;
3. compacte le dossier `dist/VintedAssistant/` en `dist/VintedAssistant-win64.zip`.

Le fichier ZIP généré contient l'exécutable autonome à distribuer. Il suffit de le décompresser sur la machine cible et de lancer `VintedAssistant.exe`.

## Différences avec le packaging MSIX

- Aucun manifeste ou signature MSIX requis ;
- Fonctionne sur toutes les versions de Windows à partir de Vista, alors que le MSIX impose Windows 10 (build 19041) ;
- La mise à jour se fait en remplaçant l'archive ZIP, sans installateur.
