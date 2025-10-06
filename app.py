from flask import Flask, request, jsonify, render_template_string
import tempfile
import subprocess
import os
import json
import sys

app = Flask(__name__)

EXECUTABLE_PATH = "/app/validador_cli"
if os.path.exists(EXECUTABLE_PATH):
    os.chmod(EXECUTABLE_PATH, 0o755)

# --- Plantilla HTML para la interfaz web ---
# Todo está en un solo archivo para simplicidad
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Validador de Firmas Digitales</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; line-height: 1.6; background-color: #f8f9fa; color: #212529; }
        .container { background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        h1, h2 { color: #343a40; border-bottom: 2px solid #dee2e6; padding-bottom: 10px; }
        form { margin-top: 20px; padding: 20px; background: #f1f3f5; border-radius: 5px; }
        pre { background: #e9ecef; padding: 15px; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; font-family: "Courier New", Courier, monospace; }
        .results-table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        .results-table th, .results-table td { border: 1px solid #dee2e6; padding: 12px; text-align: left; }
        .results-table th { background-color: #f8f9fa; }
        .error { color: #dc3545; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Validador de Firmas Digitales</h1>
        <p>Suba un archivo PDF para analizar sus firmas digitales directamente desde el servidor.</p>
        <form action="/validate" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept="application/pdf" required>
            <button type="submit">Validar Archivo</button>
        </form>
        
        {% if results %}
        <h2>Resultados para: {{ filename }}</h2>
        {% if results.firmas %}
            <table class="results-table">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Firmante</th>
                        <th>Cédula</th>
                        <th>Fecha Firma</th>
                        <th>Veredicto</th>
                    </tr>
                </thead>
                <tbody>
                {% for firma in results.firmas %}
                    <tr>
                        <td>{{ loop.index }}</td>
                        <td>{{ firma.datos.get('nombre', 'N/D') }}</td>
                        <td>{{ firma.datos.get('cedula', 'N/D') }}</td>
                        <td>{{ firma.datos.get('fecha_firma', 'N/D') }}</td>
                        <td><strong>{{ 'Válida' if firma.get('firma_valida') else 'Inválida' }}</strong></td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        {% else %}
            <p class="error">El documento no está firmado o no se pudieron reconocer las firmas.</p>
        {% endif %}

        <h2>Depuración (Salida Cruda del Validador)</h2>
        <pre>{{ raw_output if raw_output else "[STDOUT ESTABA VACÍO]" }}</pre>
        {% endif %}

        {% if error %}
        <h2 class="error">Error de Procesamiento</h2>
        <pre>{{ error }}</pre>
        {% endif %}
    </div>
</body>
</html>
"""

# --- Ruta principal que muestra la página web para subir archivos ---
@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML_TEMPLATE)

# --- Ruta de validación que ahora sirve tanto a la API como a la web ---
@app.route("/validate", methods=["POST"])
def validate_pdf():
    # Usamos print() para enviar todo a los logs de Render
    print("--- INICIO DE PETICIÓN DE VALIDACIÓN ---", file=sys.stdout)
    
    if "file" not in request.files:
        print("ERROR: Petición recibida sin el campo 'file'.", file=sys.stderr)
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    filename = file.filename
    print(f"1. Archivo recibido: {filename}", file=sys.stdout)
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    print(f"2. Archivo guardado temporalmente en: {tmp_path}", file=sys.stdout)

    try:
        cmd = [EXECUTABLE_PATH, tmp_path]
        print(f"3. Ejecutando comando: {' '.join(cmd)}", file=sys.stdout)
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        
        print("4. Comando finalizado.", file=sys.stdout)
        raw_output = result.stdout
        raw_error = result.stderr

        # --- LOGGING INCONDICIONAL ---
        print("--- SALIDA STDOUT DEL EJECUTABLE ---", file=sys.stdout)
        print(raw_output if raw_output else "[VACÍO]", file=sys.stdout)
        print("--- SALIDA STDERR DEL EJECUTABLE ---", file=sys.stdout)
        print(raw_error if raw_error else "[VACÍO]", file=sys.stdout)
        print("--- FIN DE SALIDAS ---", file=sys.stdout)
        sys.stdout.flush()
        
        # Detectamos si la petición vino del navegador para mostrar la página HTML
        is_web_request = 'text/html' in request.headers.get('Accept', '')
        
        try:
            response_json = json.loads(raw_output)
            # Combinamos la salida cruda para mostrarla siempre en el HTML
            full_raw_output = f"STDOUT:\n{raw_output}\n\nSTDERR:\n{raw_error}"
            if is_web_request:
                return render_template_string(HTML_TEMPLATE, results=response_json, filename=filename, raw_output=full_raw_output)
            else:
                return jsonify(response_json)
        except json.JSONDecodeError:
            error_message = f"El ejecutable devolvió una respuesta no válida.\n\n--- STDOUT ---\n{raw_output}\n\n--- STDERR ---\n{raw_error}"
            print(f"ERROR: {error_message}", file=sys.stderr)
            if is_web_request:
                return render_template_string(HTML_TEMPLATE, error=error_message, filename=filename)
            else:
                return jsonify({"error": error_message}), 500

    except Exception as e:
        error_message = f"Error interno grave del servidor: {e}"
        print(f"ERROR GRAVE: {error_message}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        is_web_request = 'text/html' in request.headers.get('Accept', '')
        if is_web_request:
            return render_template_string(HTML_TEMPLATE, error=error_message, filename="N/A")
        else:
            return jsonify({"error": error_message}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)