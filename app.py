from flask import Flask, request, jsonify
import tempfile
import subprocess
import os
import re
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# --- CONFIGURACIÓN DE LOGGING ---
log_file = 'validador.log'
handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.info("Servicio de validación iniciado.")
# --- FIN DE LOGGING ---

TRUST_PATH = "/app/cr-root-bundle.pem"

# Tu función parse_pyhanko_output se queda igual
def parse_pyhanko_output(output):
    firmas = []
    warnings = []
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
            if line: warnings.append(line)
            continue
        if "The signature is judged VALID" in line: current_firma["firma_valida"] = True
        elif "The signature is judged INVALID" in line: current_firma["firma_valida"] = False
        elif line.startswith("Certificate subject:"):
            m_name = re.search(r"Common Name: ([^,]+)", line)
            m_id = re.search(r"Serial Number: ([^,]+)", line)
            if m_name: current_firma["datos"]["nombre"] = m_name.group(1)
            if m_id: current_firma["datos"]["cedula"] = m_id.group(1)
        elif line.startswith("Signing time as reported by signer:"):
            current_firma["datos"]["fecha_firma"] = line.split(": ", 1)[1]
    if current_firma: firmas.append(current_firma)
    return {"firmas": firmas, "warnings": warnings, "ok": len(firmas) > 0}

# --- NUEVA RUTA DE DIAGNÓSTICO ---
@app.route("/ping")
def ping():
    app.logger.info("Ping recibido! El servicio está vivo y el logging funciona.")
    return jsonify({"status": "ok", "message": "El servicio está en línea."})

@app.route("/validate", methods=["POST"])
def validate_pdf():
    app.logger.info("1. /validate - Petición recibida.")
    if "file" not in request.files:
        app.logger.error("2. /validate - ERROR: No se encontró 'file' en la petición.")
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    app.logger.info(f"3. /validate - Archivo guardado temporalmente en: {tmp_path}")

    try:
        cmd = [
            "python", "-m", "pyhanko.cli.main", "sign", "validate",
            "--no-diff-analysis", "--force-revinfo", "--trust", TRUST_PATH,
            "--no-strict-syntax", "--pretty-print", tmp_path
        ]
        app.logger.info(f"4. /validate - Ejecutando comando: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        app.logger.info("5. /validate - Comando finalizado.")
        
        full_output = result.stdout + "\n" + result.stderr
        app.logger.info(f"6. /validate - --- SALIDA CRUDA DE PYHANKO ---\n{full_output}\n--- FIN SALIDA CRUDA ---")

        parsed = parse_pyhanko_output(full_output)
        app.logger.info(f"7. /validate - Parseo completado. Firmas encontradas: {len(parsed['firmas'])}")
        return jsonify(parsed)
    except Exception as e:
        app.logger.error(f"8. /validate - ERROR 500 INESPERADO: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

@app.route("/logs")
def view_logs():
    if not os.path.exists(log_file):
        return "No se ha generado ningún log todavía."
    try:
        with open(log_file, 'r') as f:
            content = f.read().replace('\n', '<br>')
        return f"<pre style='font-family: monospace; word-wrap: break-word; white-space: pre-wrap;'>{content}</pre>"
    except Exception as e:
        return f"No se pudieron leer los logs: {e}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

