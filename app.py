from flask import Flask, request, jsonify, Response
import tempfile
import subprocess
import os
import re
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# --- INICIO: NUEVA SECCIÓN DE LOGGING ---
# Configura el logging para que escriba en un archivo
log_file = 'validador.log'
# Crea un manejador que rota los logs para que no crezcan indefinidamente
handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
# Formato del log: [Timestamp] [Nivel de Error] Mensaje
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)
handler.setFormatter(formatter)
handler.setLevel(logging.INFO) # Captura desde errores informativos hasta críticos
app.logger.addHandler(handler)
# --- FIN: NUEVA SECCIÓN DE LOGGING ---

# Las rutas a los archivos DENTRO del contenedor de Render
TRUST_PATH = "/app/cr-root-bundle.pem"
PYHANKO_BIN = "/usr/local/bin/pyhanko"

# Tu función parse_pyhanko_output se queda igual
def parse_pyhanko_output(output):
    firmas = []
    current_firma = None
    # ... (lógica de parseo sin cambios)
    for line in output.splitlines():
        line = line.strip()
        field_match = re.match(r"Field \d+: (.+)", line)
        if field_match:
            if current_firma:
                firmas.append(current_firma)
            current_firma = {"campo_firma": field_match.group(1), "firma_valida": None, "datos": {}}
            continue
        if not current_firma:
            continue
        if "The signature is judged VALID" in line:
            current_firma["firma_valida"] = True
        elif "The signature is judged INVALID" in line:
            current_firma["firma_valida"] = False
        elif line.startswith("Certificate subject:"):
            m_name = re.search(r"Common Name: ([^,]+)", line)
            m_id = re.search(r"Serial Number: ([^,]+)", line)
            if m_name: current_firma["datos"]["nombre"] = m_name.group(1)
            if m_id: current_firma["datos"]["cedula"] = m_id.group(1)
        elif line.startswith("Signing time as reported by signer:"):
            current_firma["datos"]["fecha_firma"] = line.split(": ", 1)[1]
    
    if current_firma:
        firmas.append(current_firma)
    return {"firmas": firmas, "ok": len(firmas) > 0}


@app.route("/validate", methods=["POST"])
def validate_pdf():
    app.logger.info("Recibida una nueva petición de validación.")
    if "file" not in request.files:
        app.logger.error("Petición fallida: No se encontró 'file' en la petición.")
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        cmd = [
            PYHANKO_BIN, "sign", "validate",
            "--no-diff-analysis", "--soft-revocation-check",
            "--trust", TRUST_PATH, "--no-strict-syntax", "--pretty-print",
            tmp_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        full_output = result.stdout + "\n" + result.stderr
        parsed = parse_pyhanko_output(full_output)
        app.logger.info(f"Validación exitosa para el archivo temporal: {tmp_path}")
        return jsonify(parsed)
    except Exception as e:
        # --- ¡IMPORTANTE! Aquí registramos el error en nuestro archivo de log ---
        app.logger.error(f"Error 500 al procesar el archivo: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# --- INICIO: NUEVA RUTA PARA VER LOS LOGS ---
@app.route("/logs")
def view_logs():
    """
    Esta página muestra el contenido del archivo de logs.
    """
    if not os.path.exists(log_file):
        return "No se ha generado ningún log todavía."
    
    with open(log_file, 'r') as f:
        content = f.read().replace('\n', '<br>')
    return f"<pre style='font-family: monospace; word-wrap: break-word;'>{content}</pre>"
# --- FIN: NUEVA RUTA PARA VER LOS LOGS ---


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

    

