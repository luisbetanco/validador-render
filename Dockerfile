# Usamos la base de Oracle Linux 9 slim, idéntica a tu entorno
FROM oraclelinux:9-slim

# --- ETAPA 1: CONSTRUIR EL "TALLER DE ENSAMBLAJE" ---
# Instalamos las herramientas de desarrollo y los "manuales" que descubrimos que faltaban.
RUN microdnf install -y python3.11 python3.11-pip gcc make libxml2-devel zlib-devel && \
    microdnf clean all

# Establecemos el directorio de trabajo
WORKDIR /app

# --- ETAPA 2: CREAR Y USAR EL ENTORNO VIRTUAL ---
RUN python3.11 -m venv venv

# Copiamos la lista de "ingredientes" de Python
COPY requirements.txt .

# Ahora, cuando pip instale, usará el "taller" para construir las piezas a medida
RUN ./venv/bin/pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de la aplicación
COPY app.py .
COPY cr-root-bundle.pem .

# --- ETAPA 3: INICIAR EL SERVICIO ---
# El comando final, que sabemos que funciona en este entorno
CMD ["./venv/bin/gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"]