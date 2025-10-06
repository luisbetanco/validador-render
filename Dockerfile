# Empezamos con la base de Oracle Linux 9 slim, idéntica a tu entorno
FROM oraclelinux:9-slim

# --- ETAPA 1: CONSTRUIR EL "TALLER DE ENSAMBLAJE" ---
# Instalamos Python Y las librerías de desarrollo que descubrimos que son necesarias.
RUN microdnf install -y python3.11 python3.11-pip gcc make libxml2-devel zlib-devel && \
    microdnf clean all

# Establecemos el directorio de trabajo
WORKDIR /app

# Creamos el entorno virtual
RUN python3.11 -m venv venv

# --- LA SOLUCIÓN CLAVE ---
# Añadimos el directorio de binarios del venv al PATH del sistema.
# Esto permite que los comandos 'pip', 'gunicorn' y 'pyhanko' se encuentren fácilmente.
ENV PATH="/app/venv/bin:$PATH"

# Copiamos la lista de "ingredientes" de Python
COPY requirements.txt .

# Ahora, cuando pip instale pyhanko, usará el "taller" para construirlo a la medida
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de la aplicación (el código y los certificados)
COPY app.py .
COPY cr-root-bundle.pem .

# El comando final para iniciar el servicio, usando el gunicorn de nuestro venv
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"]