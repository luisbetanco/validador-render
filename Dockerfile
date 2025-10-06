# --- ETAPA 1: Usar una base IDÉNTICA a tu servidor ---
FROM oraclelinux:9-slim

# --- ETAPA 2: Instalar las mismas herramientas que tienes tú ---
# Usamos 'microdnf' que es el instalador en la versión 'slim'
RUN microdnf install -y python3.11 python3.11-pip && \
    microdnf clean all

# Establecer el directorio de trabajo
WORKDIR /app

# --- ETAPA 3: Crear el mismo entorno virtual ---
RUN python3.11 -m venv venv

# Copiamos la lista de "ingredientes"
COPY requirements.txt .

# Instalamos las librerías DENTRO del entorno virtual, como en tu servidor
RUN ./venv/bin/pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de la aplicación
COPY app.py .
COPY cr-root-bundle.pem .

# --- ETAPA 4: El comando final para ejecutar el servicio ---
# Usamos el gunicorn de nuestro entorno virtual, garantizando la compatibilidad
CMD ["./venv/bin/gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"]