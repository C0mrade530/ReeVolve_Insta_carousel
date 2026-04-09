#!/bin/bash
# =============================================
# RealPost Pro — Local Dev Setup (Mac)
# =============================================

set -e

echo "🚀 RealPost Pro — локальный запуск"
echo ""

# 1. Redis через Docker
echo "📦 Запускаю Redis..."
docker run -d --name realpost-redis -p 6379:6379 redis:7-alpine 2>/dev/null || echo "Redis уже запущен"
echo "✅ Redis: localhost:6379"
echo ""

# 2. Backend
echo "🐍 Настраиваю backend..."
cd backend

# Создаём venv если нет
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt -q

# Копируем .env
if [ ! -f ".env" ]; then
    cp ../.env .env 2>/dev/null || echo "⚠️  Скопируй .env в backend/"
fi

echo "✅ Backend готов"
echo ""
echo "========================================="
echo "Для запуска открой 3 терминала:"
echo ""
echo "Terminal 1 (Backend API):"
echo "  cd backend && source venv/bin/activate"
echo "  uvicorn app.main:app --reload --port 8000"
echo ""
echo "Terminal 2 (Celery Worker):"
echo "  cd backend && source venv/bin/activate"
echo "  celery -A app.tasks.celery_app worker -l info"
echo ""
echo "Terminal 3 (Frontend):"
echo "  cd frontend && npm install && npm run dev"
echo ""
echo "========================================="
echo "Backend API: http://localhost:8000"
echo "API Docs:    http://localhost:8000/docs"
echo "Frontend:    http://localhost:3000"
echo "========================================="
