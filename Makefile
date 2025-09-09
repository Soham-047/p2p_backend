# Makefile

start:
	docker-compose build --no-cache
	docker-compose up -d
	docker-compose logs -f

stop:
	docker-compose down

restart: stop start

logs:
	docker-compose logs -f

build:
	docker-compose build --no-cache

ps:
	docker-compose ps

shell:
	docker-compose exec web bash

migrate:
	docker-compose exec web python manage.py migrate

makemigrations:
	docker-compose exec web python manage.py makemigrations

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

collectstatic:
	docker-compose exec web python manage.py collectstatic --noinput

celery:
	docker-compose exec celery celery -A p2p_comm worker -l info
