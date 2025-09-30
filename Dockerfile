FROM python:3.12-slim

# Install system dependencies including netcat
RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# Create a user and group 'appuser' with uid 1001
RUN addgroup --system appuser && adduser --system --group appuser

WORKDIR /app

COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . /app/

# Copy and make entrypoint executable
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Change ownership of app files to appuser
RUN chown -R appuser:appuser /app

# Switch to appuser
USER appuser

# Set environment variables if needed
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/app/entrypoint.sh"]

# Run Daphne for ASGI
CMD ["sh", "-c", "daphne -b 0.0.0.0 -p $PORT p2p_comm.asgi:application"]


