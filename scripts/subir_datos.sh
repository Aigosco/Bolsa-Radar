#!/usr/bin/env bash
# Commit + push de datos/ desde GitHub Actions, con reintentos si otro flujo subió cambios entre medio.
set -u
MSG="${1:-datos}"
git config user.name "bolsa-radar-bot"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git add datos
if git diff --cached --quiet; then
  echo "Sin cambios."
  exit 0
fi
git commit -q -m "$MSG $(date -u +%Y-%m-%dT%H:%MZ)"
for i in 1 2 3 4 5; do
  if git pull -q --rebase -X theirs origin main && git push -q origin HEAD:main; then
    echo "Push OK (intento $i)."
    exit 0
  fi
  sleep $((i * 7))
done
echo "No se pudo subir tras 5 intentos." >&2
exit 1
