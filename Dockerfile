# Usamos la base de Oracle Linux 9 slim
FROM oraclelinux:9-slim

# Instalamos Python y sus herramientas
RUN microdnf install -y python3.11 python3.11-pip && \
    microdnf clean all

# Establecemos el directorio de trabajo
WORKDIR /app

# Creamos el entorno virtual
RUN python3.11 -m venv venv

# --- LA SOLUCIÓN CLAVE ---
# Añadimos el directorio de binarios del venv al PATH del sistema.
# Ahora, todos los programas (python, pip, gunicorn, pyhanko) son accesibles globalmente.
ENV PATH="/app/venv/bin:$PATH"

# Copiamos la lista de "ingredientes"
COPY requirements.txt .

# Ahora podemos usar 'pip' directamente, porque está en el PATH
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos el resto de la aplicación
COPY app.py .
COPY cr-root-bundle.pem .

# Ahora podemos usar 'gunicorn' directamente
CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:10000", "app:app"]