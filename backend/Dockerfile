FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md alembic.ini ./
COPY backend ./backend
COPY migrations ./migrations
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn", "backend.app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
