from flask import Flask, request, jsonify
import tempfile
import subprocess
import os
import re
import sys # Importamos sys para forzar la escritura de logs

app = Flask(__name__)

# Ya no necesitamos la configuración de logging a archivo.

TRUST_PATH = "/app/cr-root-bundle.pem"

# Tu función parse_pyhanko_output se queda igual.
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

@app.route("/")
def home():
    # Una página de bienvenida para confirmar que el servicio está vivo
    return "Servicio Validador de Firmas está en línea."

@app.route("/validate", methods=["POST"])
def validate_pdf():
    print("1. /validate - Petición recibida.")
    sys.stdout.flush() # Forzar que el log se escriba inmediatamente

    if "file" not in request.files:
        print("2. /validate - ERROR: No se encontró 'file'.")
        sys.stderr.flush()
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    print(f"3. /validate - Archivo guardado en: {tmp_path}")
    sys.stdout.flush()

    try:
        cmd = [
            "python", "-m", "pyhanko.cli.main", "sign", "validate",
            "--no-diff-analysis", "--force-revinfo", "--trust", TRUST_PATH,
            "--no-strict-syntax", "--pretty-print", tmp_path
        ]
        print(f"4. /validate - Ejecutando comando: {' '.join(cmd)}")
        sys.stdout.flush()
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        print("5. /validate - Comando finalizado.")
        sys.stdout.flush()
        
        full_output = result.stdout + "\n" + result.stderr
        print(f"6. /validate - --- SALIDA CRUDA DE PYHANKO ---\n{full_output}\n--- FIN SALIDA CRUDA ---")
        sys.stdout.flush()

        parsed = parse_pyhanko_output(full_output)
        print(f"7. /validate - Parseo completado. Firmas: {len(parsed['firmas'])}")
        sys.stdout.flush()
        return jsonify(parsed)
    except Exception as e:
        print(f"8. /validate - ERROR 500 INESPERADO: {e}")
        sys.stderr.flush()
        # Imprime el traceback completo al log de errores
        import traceback
        traceback.print_exc()
        return jsonify({"error": "Error interno del servidor"}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

# La ruta /logs ya no es necesaria, la eliminamos.

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

    

