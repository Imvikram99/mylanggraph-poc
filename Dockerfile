FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip && pip install -r requirements.txt && pip install -e .

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.ui.server:app", "--host", "0.0.0.0", "--port", "8000"]
