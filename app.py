from flask import Flask, request, jsonify
import tempfile
import subprocess
import os
import json

app = Flask(__name__)

# La ruta a nuestro ejecutable dentro del entorno de Render
EXECUTABLE_PATH = "/app/validador_cli"

# Le damos permisos de ejecución a nuestro programa al iniciar
# Esto es importante porque los permisos a veces se pierden al subir archivos
if os.path.exists(EXECUTABLE_PATH):
    os.chmod(EXECUTABLE_PATH, 0o755)

@app.route("/")
def home():
    return "Servicio Validador de Firmas (Portable) está en línea."

@app.route("/validate", methods=["POST"])
def validate_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    # Guardamos el archivo recibido en una ubicación temporal
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        # Llamamos a nuestro ejecutable autocontenido, pasándole la ruta del archivo temporal
        cmd = [EXECUTABLE_PATH, tmp_path]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        # El resultado que imprimió el ejecutable está en result.stdout
        # Lo convertimos de texto JSON a un objeto y lo devolvemos
        response_json = json.loads(result.stdout)
        return jsonify(response_json)
    except Exception as e:
        # Si algo falla (ej. el JSON está malformado), devolvemos un error
        error_detail = result.stderr if 'result' in locals() else str(e)
        return jsonify({"error": "Error interno al procesar la respuesta del validador.", "detalle": error_detail}), 500
    finally:
        # Nos aseguramos de borrar el archivo temporal
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    # Este bloque es solo para pruebas locales, Render no lo usará
    app.run(host="0.0.0.0", port=10000)