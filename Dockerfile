# Usamos una imagen oficial de Python, que está preparada para instalar paquetes con pip
FROM python:3.11-slim

# Establecemos el directorio de trabajo
WORKDIR /app

# Copiamos primero el archivo de requerimientos
COPY requirements.txt .

# Instalamos las dependencias con pip. Esto funcionará sin problemas en esta imagen.
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos nuestro "motor" (el ejecutable) y el código del servidor "adaptador"
COPY validador_cli .
COPY app.py .

# Exponemos el puerto que usará Gunicorn
EXPOSE 10000

# El comando para iniciar el servicio
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"]