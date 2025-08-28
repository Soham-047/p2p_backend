FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update && apt-get install -y netcat-openbsd gcc postgresql-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

COPY . /app/

# RUN mkdir -p /app/staticfiles
# RUN chown -R root:root /app/staticfiles
ENV DJANGO_SETTINGS_MODULE=p2p_comm.settings
# RUN python manage.py collectstatic --noinput

COPY ./entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "p2p_comm.wsgi:application", "--bind", "0.0.0.0:8000"]
