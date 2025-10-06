from flask import Flask, request, jsonify, Response
import tempfile
import subprocess
import os
import re
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# --- INICIO: SECCIÓN DE LOGGING (SIN CAMBIOS) ---
log_file = 'validador.log'
handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
formatter = logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
)
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
# --- FIN: SECCIÓN DE LOGGING ---

# La ruta de los certificados se queda igual
TRUST_PATH = "/app/cr-root-bundle.pem"

# La función de parseo se queda igual
def parse_pyhanko_output(output):
    firmas = []
    current_firma = None
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
        # --- ESTA ES LA LÍNEA CORREGIDA Y DEFINITIVA ---
        # Ejecutamos pyhanko como un módulo de python, que es la forma más robusta.
        cmd = [
            "python", "-m", "pyhanko.cli.main", "sign", "validate",
            "--no-diff-analysis", "--soft-revocation-check",
            "--trust", TRUST_PATH, "--no-strict-syntax", "--pretty-print",
            tmp_path
        ]
        # --- FIN DE LA CORRECCIÓN ---

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        full_output = result.stdout + "\n" + result.stderr
        parsed = parse_pyhanko_output(full_output)
        app.logger.info(f"Validación exitosa para el archivo temporal: {tmp_path}")
        return jsonify(parsed)
    except Exception as e:
        app.logger.error(f"Error 500 al procesar el archivo: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# La ruta para ver los logs se queda igual
@app.route("/logs")
def view_logs():
    if not os.path.exists(log_file):
        return "No se ha generado ningún log todavía."
    
    # Leemos las últimas 100 líneas para no sobrecargar
    try:
        with open(log_file, 'r') as f:
            lines = f.readlines()
            last_100_lines = lines[-100:]
            content = "".join(last_100_lines).replace('\n', '<br>')
        return f"<pre style='font-family: monospace; word-wrap: break-word;'>{content}</pre>"
    except Exception as e:
        return f"No se pudieron leer los logs: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)