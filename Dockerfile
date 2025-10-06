# Usamos una imagen de Linux mínima, ya que nuestro ejecutable tiene todo lo que necesita
FROM debian:bookworm-slim

WORKDIR /app

# Solo necesitamos instalar Python para poder correr el servidor web Flask/Gunicorn
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip gunicorn && rm -rf /var/lib/apt/lists/*
RUN pip install Flask

# Copiamos nuestro "motor" (el ejecutable) y el código del servidor "adaptador"
COPY validador_cli .
COPY app.py .

# Exponemos el puerto que usará Gunicorn
EXPOSE 10000

# El comando para iniciar el servicio
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"]