from flask import Flask, request, jsonify
import tempfile
import subprocess
import os
import json

app = Flask(__name__)

EXECUTABLE_PATH = "/app/validador_cli"
if os.path.exists(EXECUTABLE_PATH):
    os.chmod(EXECUTABLE_PATH, 0o755)

@app.route("/")
def home():
    return "Servicio Validador de Firmas v1.2 (Portable) está en línea."

@app.route("/validate", methods=["POST"])
def validate_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        cmd = [EXECUTABLE_PATH, tmp_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        raw_output = result.stdout
        raw_error = result.stderr

        try:
            # Intentamos interpretar la salida como JSON
            response_json = json.loads(raw_output)
        except json.JSONDecodeError:
            # Si no es JSON, es un error. Devolvemos la salida cruda.
            return jsonify({
                "error": "El ejecutable validador_cli devolvió una respuesta no válida.",
                "debug_stdout": raw_output,
                "debug_stderr": raw_error
            }), 500

        # Si el JSON es válido pero no encuentra firmas, añadimos la salida cruda para depurar
        if not response_json.get("firmas"):
            response_json["debug_info"] = f"Salida del validador: {raw_output} | Errores: {raw_error}"
        
        return jsonify(response_json)

    except Exception as e:
        return jsonify({"error": "Error interno del servidor.", "detalle": str(e)}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

