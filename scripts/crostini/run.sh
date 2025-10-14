#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV_DIR="$ROOT/.venv"

cd "$ROOT"

if [ ! -d "$VENV_DIR" ]; then
  echo "Environnement virtuel introuvable dans $VENV_DIR." >&2
  echo "Exécutez d'abord scripts/crostini/setup.sh" >&2
  exit 1
fi

source "$VENV_DIR/bin/activate"

if [ -z "${OPENAI_API_KEY:-}" ]; then
  echo "[Info] OPENAI_API_KEY n'est pas défini dans l'environnement courant." >&2
  echo "L'application risque de ne pas pouvoir se connecter à l'API OpenAI." >&2
fi

python -m app.main "$@"
