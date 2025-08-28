.PHONY: build up start down logs migrate createsuperuser shell dev celery

build:
	docker-compose build

up:
	docker-compose up -d web redis celery

start: build up
	docker-compose exec web python manage.py runserver 0.0.0.0:8000

down:
	docker-compose down

logs:
	docker-compose logs -f

migrate:
	docker-compose exec web python manage.py migrate

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

shell:
	docker-compose exec web python manage.py shell

# Run Django dev server instead of gunicorn
dev:
	docker-compose run --service-ports --rm web python manage.py runserver 0.0.0.0:8000

# Run celery worker manually
celery:
	docker-compose run --rm celery celery -A p2p_comm worker -l info
