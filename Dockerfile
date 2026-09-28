FROM python:3.13.1-slim

ENV PYTHONHASHSEED=0 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# os dados da competição (txt/ e desafio1_bracis.db) são montados em /app/data:
#   docker run --rm -v "$PWD/data:/app/data" -v "$PWD/out:/app/out" citeverify
CMD ["make", "reproduce"]
