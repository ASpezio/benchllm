#!/bin/bash
# Навигатор по проекту приказа ФОП: локальный сервер + браузер.
# Двойной клик — откроется браузер. Чтобы остановить, закройте это окно Терминала.
cd "$(dirname "$0")" || exit 1
PORT=8765
while lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; do PORT=$((PORT+1)); done
URL="http://localhost:$PORT/navigator/"
echo "Навигатор открыт: $URL"
echo "Чтобы остановить — закройте это окно."
(sleep 1; open "$URL") &
if command -v python3 >/dev/null 2>&1; then
  exec python3 -m http.server "$PORT" --bind 127.0.0.1
else
  exec npx --yes http-server -p "$PORT" -a 127.0.0.1 -c-1 -s
fi
