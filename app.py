from flask import Flask, request, jsonify
import tempfile
import subprocess
import os
import re
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# --- CONFIGURACIÓN DE LOGGING (para depuración) ---
log_file = 'validador.log'
handler = RotatingFileHandler(log_file, maxBytes=100000, backupCount=3)
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
handler.setFormatter(formatter)
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
# --- FIN DE LOGGING ---

# Ruta del archivo de certificados dentro del contenedor de Render
TRUST_PATH = "/app/cr-root-bundle.pem"

#
# === ¡ESTA ES TU FUNCIÓN PROBADA Y FUNCIONAL! ===
# La he copiado directamente de la que me proporcionaste.
#
def parse_pyhanko_output(output):
    firmas = []
    warnings = []
    current_firma = None

    for line in output.splitlines():
        line = line.strip()

        field_match = re.match(r"Field \d+: (.+)", line)
        if field_match:
            if current_firma:
                current_firma["validez_interpretada"] = current_firma.get("firma_valida", False)
                firmas.append(current_firma)
            
            current_firma = {
                "campo_firma": field_match.group(1),
                "firma_valida": None,
                "validez_interpretada": False,
                "datos": {"razon_invalidez": None}
            }
            continue

        if not current_firma:
            if line:
                warnings.append(line)
            continue

        if "Some modifications may be illegitimate" in line:
            current_firma["datos"]["razon_invalidez"] = "Modificaciones no permitidas detectadas después de la firma."
        elif "The signature is cryptographically unsound" in line:
            current_firma["datos"]["razon_invalidez"] = "La firma está corrupta o el documento fue alterado."
        
        elif line.startswith("Certificate subject:"):
            current_firma["datos"]["subject_detalle"] = line.replace("Certificate subject: ", "").strip()
            m_name = re.search(r"Common Name: ([^,]+)", line)
            m_id = re.search(r"Serial Number: ([^,]+)", line)
            if m_name: current_firma["datos"]["nombre"] = m_name.group(1)
            if m_id: current_firma["datos"]["cedula"] = m_id.group(1)

        elif line.startswith("Signing time as reported by signer:"):
            current_firma["datos"]["fecha_firma"] = line.split(": ", 1)[1]

        elif "is REVOKED" in line:
            current_firma["datos"]["revocacion"] = "Certificado REVOCADO"
            current_firma["datos"]["razon_invalidez"] = "El certificado del firmante fue revocado."
        
        elif "Revocation data could not be validated" in line:
            current_firma["datos"]["revocacion"] = "No se pudo validar revocación"
            current_firma["datos"]["razon_invalidez"] = "No fue posible verificar el estado de revocación."

        elif "The signature is judged VALID" in line:
            current_firma["firma_valida"] = True
        elif "The signature is judged INVALID" in line:
            current_firma["firma_valida"] = False

    if current_firma:
        current_firma["validez_interpretada"] = current_firma.get("firma_valida", False)
        firmas.append(current_firma)

    return {"firmas": firmas, "warnings": warnings, "ok": len(firmas) > 0}


@app.route("/validate", methods=["POST"])
def validate_pdf():
    app.logger.info("Recibida una nueva petición de validación.")
    if "file" not in request.files:
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # Usamos la forma robusta de llamar a pyhanko como módulo
        cmd = [
            "python", "-m", "pyhanko.cli.main", "sign", "validate",
            "--no-diff-analysis", 
            "--force-revinfo",  # Usamos force-revinfo como en tu servidor original
            "--trust", TRUST_PATH,
            "--no-strict-syntax",
            "--pretty-print",
            tmp_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        full_output = result.stdout + "\n" + result.stderr
        
        # Guardamos la salida cruda en los logs para poder depurar
        app.logger.info(f"--- SALIDA CRUDA DE PYHANKO ---\n{full_output}\n--- FIN SALIDA CRUDA ---")

        parsed = parse_pyhanko_output(full_output)
        return jsonify(parsed)
    except Exception as e:
        app.logger.error(f"Error 500 al procesar el archivo: {e}", exc_info=True)
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

