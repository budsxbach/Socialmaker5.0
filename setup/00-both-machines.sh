#!/usr/bin/env bash
# AuronOrigin | Phase 0 — auf BEIDEN Laptops ausfuehren (Ubuntu 22.04 / 24.04)
set -euo pipefail

echo "== 1/5 Basis-Pakete =="
sudo apt update
sudo apt install -y curl ca-certificates gnupg jq unzip ffmpeg fonts-dejavu-core espeak-ng python3-venv python3-pip

echo "== 2/5 Tailscale installieren (0 EUR, bis 100 Geraete) =="
if ! command -v tailscale >/dev/null 2>&1; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
echo "JETZT MANUELL (einmalig, Browser-Login noetig):  sudo tailscale up"
echo "Danach:  tailscale status   -> Tailscale-IP beider Geraete notieren."

echo "== 3/5 24/7: Schlaf/Lid dauerhaft abschalten =="
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target || true
sudo install -d /etc/systemd/logind.conf.d
printf '[Login]\nHandleLidSwitch=ignore\nHandleLidSwitchExternalPower=ignore\nIdleAction=ignore\n' | sudo tee /etc/systemd/logind.conf.d/99-auron.conf >/dev/null
sudo systemctl restart systemd-logind || true

echo "== 4/5 Zeit & automatische Sicherheitsupdates =="
sudo timedatectl set-timezone Europe/Berlin
sudo timedatectl set-ntp true
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure --priority=low unattended-upgrades || true

echo "== 5/5 Status =="
echo "Host: $(hostname)"; free -h | head -2; df -h / | tail -1
tailscale status || true
