#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# EC2 bootstrap script — run once on a fresh Amazon Linux 2023 / Ubuntu instance
#
# What this does:
#   1. Installs Docker + Docker Compose
#   2. Clones your repo
#   3. Starts the containerized API
#
# Usage:
#   ssh ec2-user@<your-ec2-ip>
#   bash <(curl -s https://raw.githubusercontent.com/krishsabloak/Real-Time-ML-System-with-a-Production-Pipeline/main/deploy/ec2_setup.sh)
# ─────────────────────────────────────────────────────────────────────────────
set -e

REPO_URL="https://github.com/krishsabloak/Real-Time-ML-System-with-a-Production-Pipeline.git"
APP_DIR="$HOME/app"

echo "==> Installing Docker..."
if command -v apt-get &>/dev/null; then
    sudo apt-get update -y
    sudo apt-get install -y docker.io docker-compose-plugin curl
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER"
elif command -v yum &>/dev/null; then
    sudo yum update -y
    sudo yum install -y docker curl
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER"
    # Docker Compose v2 plugin
    DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
    mkdir -p "$DOCKER_CONFIG/cli-plugins"
    curl -SL https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64 \
        -o "$DOCKER_CONFIG/cli-plugins/docker-compose"
    chmod +x "$DOCKER_CONFIG/cli-plugins/docker-compose"
fi

echo "==> Cloning repo..."
git clone "$REPO_URL" "$APP_DIR" || (cd "$APP_DIR" && git pull)

cd "$APP_DIR"

if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  Edit $APP_DIR/.env with your Reddit credentials before starting:"
    echo "    nano $APP_DIR/.env"
    echo "Then run:  cd $APP_DIR && docker compose up -d"
    exit 0
fi

echo "==> Starting containers..."
mkdir -p data
docker compose up -d --build

echo ""
echo "✅  API is running. Test it:"
echo "    curl http://localhost:8000/health"
echo "    curl -X POST http://localhost:8000/predict -H 'Content-Type: application/json' -d '{\"text\": \"The economy is recovering fast\"}'"
