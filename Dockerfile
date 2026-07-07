FROM python:3.13-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/src

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock* ./
COPY src ./src
COPY alembic.ini ./alembic.ini

RUN uv sync --frozen

COPY . .

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
