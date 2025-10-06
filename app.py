from flask import Flask, request, jsonify
import tempfile
import subprocess
import os
import re
import sys
import traceback

app = Flask(__name__)

TRUST_PATH = "/app/cr-root-bundle.pem"

def parse_pyhanko_output(output):
    """ Parsea la salida de texto del comando pyhanko. """
    firmas = []
    current_firma = None
    # Tu código de parseo probado, sin cambios
    for line in output.splitlines():
        line = line.strip()
        field_match = re.match(r"Field \d+: (.+)", line)
        if field_match:
            if current_firma: firmas.append(current_firma)
            current_firma = {"campo_firma": field_match.group(1), "firma_valida": None, "datos": {}}
            continue
        if not current_firma: continue
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
    return {"firmas": firmas, "ok": len(firmas) > 0}


@app.route("/")
def home():
    return "Servicio Validador de Firmas está en línea."

@app.route("/validate", methods=["POST"])
def validate_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # --- LA LLAMADA SIMPLIFICADA ---
        # El sistema encontrará 'pyhanko' porque está en el PATH que definimos en el Dockerfile.
        cmd = [
            "pyhanko", "sign", "validate",
            "--no-diff-analysis", "--force-revinfo", "--trust", TRUST_PATH,
            "--no-strict-syntax", "--pretty-print", tmp_path
        ]
        # --- FIN DE LA SIMPLIFICACIÓN ---
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        full_output = result.stdout + "\n" + result.stderr

        # Imprimimos la salida a los logs de Render para poder depurar si algo falla
        print(f"--- Salida Cruda de PyHanko ---\n{full_output}\n--- Fin Salida Cruda ---", file=sys.stdout)
        sys.stdout.flush()

        parsed = parse_pyhanko_output(full_output)
        return jsonify(parsed)
    except Exception as e:
        print(f"--- ERROR INESPERADO ---\n{traceback.format_exc()}\n--- FIN ERROR ---", file=sys.stderr)
        sys.stderr.flush()
        return jsonify({"error": "Error interno del servidor", "detalle": str(e)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

