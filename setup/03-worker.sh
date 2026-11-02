#!/usr/bin/env bash
# AuronOrigin | Phase 3 — NUR auf dem Dell (der "Renderer")
set -euo pipefail
REPO="${REPO:-$HOME/Socialmaker5.0}"
AU="$HOME/AuronOrigin"

echo "== 1/5 Verzeichnisse & Dateien =="
mkdir -p "$AU"/{out/ENTWURF,out/FREIGEGEBEN,out/VERWORFEN,out/PLAN,assets/music,cache,worker,logs}
cp -r "$REPO/worker/." "$AU/worker/"
[ -f "$AU/.env" ] || cp "$REPO/config/env.example" "$AU/.env"

echo "== 2/5 Python-Umgebung =="
python3 -m venv "$AU/.venv"
"$AU/.venv/bin/pip" install --upgrade pip -q
"$AU/.venv/bin/pip" install -r "$AU/worker/requirements.txt" -q

echo "== 3/5 .env bearbeiten =="
echo "-> JETZT: nano $AU/.env   (WORKER_TOKEN = langer Zufallsstring, CONTENT_LANG=en)"

echo "== 4/5 Systemd-Dienst =="
sudo cp "$REPO/systemd/auron-worker.service" /etc/systemd/system/auron-worker.service
sudo sed -i "s|DEINUSER|$USER|g" /etc/systemd/system/auron-worker.service
sudo systemctl daemon-reload
sudo systemctl enable --now auron-worker.service

echo "== 5/5 Healthcheck & Review-Link =="
for i in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:8787/health >/dev/null 2>&1; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:8787/health | jq .
IP="$(tailscale ip -4 2>/dev/null || hostname -I | awk '{print $1}')"
echo "Review (1-Klick-Freigabe): http://$IP:8787/review"
