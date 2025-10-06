from flask import Flask, request, jsonify
import tempfile
import subprocess
import os
import re

app = Flask(__name__)

# Rutas DENTRO de nuestro contenedor Docker de Oracle Linux
# Serán idénticas a las de tu servidor
TRUST_PATH = "/app/cr-root-bundle.pem"
PYHANKO_BIN = "/app/venv/bin/pyhanko" 

def parse_pyhanko_output(output):
    # Tu función de parseo que ya funciona
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
    if "file" not in request.files:
        return jsonify({"error": "No se envió archivo PDF"}), 400
    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    try:
        cmd = [
            PYHANKO_BIN, "sign", "validate",
            "--no-diff-analysis", "--force-revinfo", "--trust", TRUST_PATH,
            "--no-strict-syntax", "--pretty-print", tmp_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        full_output = result.stdout + "\n" + result.stderr
        parsed = parse_pyhanko_output(full_output)
        return jsonify(parsed)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
