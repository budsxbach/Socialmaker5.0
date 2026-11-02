#!/usr/bin/env bash
# AuronOrigin | Phase 1 — NUR auf dem Dell Latitude 5530 (16 GB RAM)
set -euo pipefail
REPO="${REPO:-$HOME/Socialmaker5.0}"

echo "== 1/5 Ollama installieren =="
if ! command -v ollama >/dev/null 2>&1; then curl -fsSL https://install.ollama.com | sh; fi

echo "== 2/5 Systemd-Override =="
sudo install -d /etc/systemd/system/ollama.service.d
sudo cp "$REPO/config/ollama-override.conf" /etc/systemd/system/ollama.service.d/10-auron.conf
sudo systemctl daemon-reload
sudo systemctl enable --now ollama
sudo systemctl restart ollama

echo "== 3/5 Modelle laden (einmalig, ~5.5 GB) =="
ollama pull qwen2.5:7b-instruct     # Autor: Skripte, JSON, Recherche-Auswertung
ollama pull llama3.2:3b             # schneller Helfer: Wochenplan, Klassifikation

echo "== 4/5 Firewall: 11434 + 8787 NUR ueber Tailscale =="
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH || true
sudo ufw allow in on tailscale0 to any port 11434 proto tcp comment 'Ollama (Tailscale only)'
sudo ufw allow in on tailscale0 to any port 8787  proto tcp comment 'Auron Worker (Tailscale only)'
sudo ufw --force enable
sudo ufw status verbose

echo "== 5/5 Funktionstest =="
curl -fsS http://127.0.0.1:11434/api/tags | jq -r '.models[].name'
echo '--- Testantwort des 3B-Modells ---'
curl -fsS http://127.0.0.1:11434/api/generate \
  -d '{"model":"llama3.2:3b","prompt":"Erklaere in einem Satz, was ein selbstgehosteter KI-Agent ist.","stream":false}' \
  | jq -r '.response'
