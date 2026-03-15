FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime dependencies first to leverage Docker layer cache.
COPY docker/requirements.app.txt /tmp/requirements.app.txt
RUN pip install --upgrade pip && \
	pip install -r /tmp/requirements.app.txt

# Copy project source.
COPY . /app

RUN chmod +x /app/docker/bootstrap_and_run.sh

EXPOSE 8501

CMD ["bash", "/app/docker/bootstrap_and_run.sh"]
