start:
	docker-compose up --build web celery

stop:
	docker-compose down

logs:
	docker-compose logs -f

migrate:
	docker-compose run --rm web python manage.py migrate