# Usamos una imagen de Python completa y robusta (Debian Bullseye)
# Esto incluye todas las librerías de sistema que pyhanko podría necesitar
FROM python:3.11-bullseye

# Establecemos el directorio de trabajo
WORKDIR /app

# Copiamos la lista de "ingredientes"
COPY requirements.txt .

# Instalamos las dependencias de Python. Esto funcionará sin problemas.
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de nuestros archivos
COPY app.py .
COPY cr-root-bundle.pem .

# El comando para iniciar el servicio web
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"]