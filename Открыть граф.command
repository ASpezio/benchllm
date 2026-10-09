#!/bin/bash
# ИС ОЗЯМ-ФОП · просмотр графа понятий: локальный сервер + браузер.
# Двойной клик — откроется браузер. Чтобы остановить, закройте это окно Терминала.
cd "$(dirname "$0")" || exit 1
PORT=8765
while lsof -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; do PORT=$((PORT+1)); done
URL="http://localhost:$PORT/2_%D0%B3%D1%80%D0%B0%D1%84/%D0%BF%D1%80%D0%BE%D1%81%D0%BC%D0%BE%D1%82%D1%80/?v=$(date +%s)"
echo "Граф открыт: $URL"
echo "Чтобы остановить — закройте это окно."
(sleep 1; open "$URL") &
if command -v python3 >/dev/null 2>&1; then
  # сервер без кэша: браузер всегда берёт свежий index.html после пересборки
  exec python3 -c '
import sys, http.server
class H(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()
http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
' "$PORT"
else
  exec npx --yes http-server -p "$PORT" -a 127.0.0.1 -c-1 -s
fi
