#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PYTHON="python3"

usage() {
  cat <<'USAGE'
Usage: scripts/crostini/setup.sh [--python /path/to/python]

Options:
  --python PATH   Utiliser un interpréteur Python spécifique (par défaut: python3)
USAGE
}

# Parse arguments
while (( $# > 0 )); do
  case "$1" in
    --python)
      shift || { echo "Erreur: --python nécessite un argument" >&2; exit 1; }
      PYTHON="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Argument inconnu: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
  shift
done

cd "$ROOT"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Python introuvable (essayé: $PYTHON). Installez-le avec :" >&2
  echo "    sudo apt install python3.11 python3.11-venv" >&2
  exit 1
fi

if ! "$PYTHON" -m venv --help >/dev/null 2>&1; then
  echo "Le module venv est indisponible. Installez-le avec :" >&2
  echo "    sudo apt install python3.11-venv" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Création de l'environnement virtuel (.venv)"
  "$PYTHON" -m venv .venv
else
  echo "Environnement virtuel déjà présent (.venv)"
fi

source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

deactivate

echo "Installation terminée. Activez l'environnement via 'source .venv/bin/activate' si besoin."

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "[Info] OPENAI_API_KEY n'est pas défini. Exportez-le avant d'exécuter l'application :" >&2
  echo "    export OPENAI_API_KEY=\"votre_cle\"" >&2
fi
