# Usar una imagen oficial de Python como base
FROM python:3.11-slim

# Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalar las librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de los archivos del proyecto
COPY . .

# Comando para iniciar el servidor web Gunicorn. Render gestionará el puerto.
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"]
