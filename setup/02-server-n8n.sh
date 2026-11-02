#!/usr/bin/env bash
# AuronOrigin | Phase 2 — NUR auf dem 24/7-Laptop (5 GB RAM, Ryzen)
set -euo pipefail
REPO="${REPO:-$HOME/Socialmaker5.0}"

echo "== 1/6 4 GB Swap (bei 5 GB RAM zwingend) =="
if ! swapon --show | grep -q '/swapfile'; then
  sudo fallocate -l 4G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-auron.conf >/dev/null
sudo sysctl -p /etc/sysctl.d/99-auron.conf >/dev/null

echo "== 2/6 Desktop abschalten (spart ~1 GB RAM) =="
sudo systemctl set-default multi-user.target
# Rueckgaengig:  sudo systemctl set-default graphical.target

echo "== 3/6 Docker inkl. Compose-Plugin =="
if ! command -v docker >/dev/null 2>&1; then curl -fsSL https://get.docker.com | sh; fi
sudo usermod -aG docker "$USER"
echo "HINWEIS: einmal ab- und wieder anmelden (oder 'newgrp docker')."

echo "== 4/6 Konfiguration =="
mkdir -p "$HOME/AuronOrigin/n8n"
cp "$REPO/config/docker-compose.yml" "$HOME/AuronOrigin/n8n/docker-compose.yml"
cp "$REPO/config/env.example" "$HOME/AuronOrigin/n8n/.env"
echo "-> JETZT: nano ~/AuronOrigin/n8n/.env   (N8N_HOST / WEBHOOK_URL / TZ pruefen)"

echo "== 5/6 Start =="
cd "$HOME/AuronOrigin/n8n"
sudo -E docker compose up -d
sudo -E docker compose ps

echo "== 6/6 Healthcheck =="
for i in $(seq 1 20); do
  if curl -fsS http://127.0.0.1:5678/healthz >/dev/null 2>&1; then break; fi
  sleep 3
done
curl -fsS http://127.0.0.1:5678/healthz && echo " -> n8n laeuft auf http://$(hostname -I | awk '{print $1}'):5678"
