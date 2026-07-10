# Depression Detection System - Quick Commands
# Usage: make [command]

.PHONY: up down logs restart clean indexes

# Default: build and start everything
up:
	docker-compose up --build

# Start in background (detached)
upd:
	docker-compose up --build -d

# Stop all services
down:
	docker-compose down

# View logs (follow mode)
logs:
	docker-compose logs -f

# Restart all services
restart:
	docker-compose restart

# Stop and remove volumes (fresh start)
clean:
	docker-compose down -v

# Setup MongoDB indexes (run after services are up)
indexes:
	python3 scripts/setup_mongo_indexes.py

# Seed demo data
demo:
	python3 scripts/seed_demo_data.py
