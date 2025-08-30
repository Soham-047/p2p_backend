start:
	docker-compose up --build -d web celery
	docker-compose logs -f web

stop:
	docker-compose down

logs:
	docker-compose logs -f

migrate:
	docker-compose run --rm web python manage.py migrate

shell:
	docker-compose run --rm web python manage.py shell

createsuperuser:
	docker-compose run --rm web python manage.py createsuperuser