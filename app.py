from flask import Flask, request, jsonify, render_template_string
import tempfile
import subprocess
import os
import re
import sys
import traceback

app = Flask(__name__)

# --- Rutas y Configuración ---
TRUST_PATH = "/app/cr-root-bundle.pem"
PYTHON_EXEC = "/app/venv/bin/python"

# --- Plantilla HTML para la interfaz web de diagnóstico ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8"><title>Validador de Firmas</title>
    <style>
        body { font-family: sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; background-color: #f8f9fa; }
        .container { background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
        h1, h2 { border-bottom: 2px solid #dee2e6; padding-bottom: 10px; }
        pre { background: #e9ecef; padding: 15px; border-radius: 5px; white-space: pre-wrap; word-wrap: break-word; }
        .error { color: #dc3545; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Validador de Firmas (Diagnóstico)</h1>
        <p>Suba un archivo PDF para analizarlo y ver la salida cruda del motor de validación.</p>
        <form action="/validate" method="post" enctype="multipart/form-data">
            <input type="file" name="file" accept="application/pdf" required>
            <button type="submit">Validar</button>
        </form>
        
        {% if filename %}
            <h2>Resultados para: {{ filename }}</h2>
            {% if results and results.firmas %}
                <p><strong>Veredicto:</strong> El documento contiene {{ results.firmas|length }} firma(s).</p>
            {% else %}
                <p class="error"><strong>Veredicto:</strong> El documento no está firmado o no se reconocieron las firmas.</p>
            {% endif %}

            <h2>Depuración (Salida Cruda Completa)</h2>
            <pre>{{ raw_output if raw_output else "[NINGUNA SALIDA RECIBIDA]" }}</pre>
        {% endif %}

        {% if error %}
            <h2 class="error">Error de Procesamiento</h2>
            <pre>{{ error }}</pre>
        {% endif %}
    </div>
</body>
</html>
"""

def log_message(message, is_error=False):
    """ Función para enviar mensajes a los logs de Render. """
    stream = sys.stderr if is_error else sys.stdout
    print(message, file=stream)
    stream.flush()

def parse_pyhanko_output(output):
    # Tu función de parseo probada, sin cambios
    firmas = []
    current_firma = None
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

@app.route("/", methods=["GET"])
def home():
    """ Muestra la interfaz web para subir archivos. """
    return render_template_string(HTML_TEMPLATE)

@app.route("/validate", methods=["POST"])
def validate_pdf():
    log_message("--- INICIO DE PETICIÓN DE VALIDACIÓN ---")
    if "file" not in request.files:
        log_message("ERROR: Petición sin el campo 'file'.", is_error=True)
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    filename = file.filename
    log_message(f"1. Archivo recibido: {filename}")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    log_message(f"2. Archivo guardado en: {tmp_path}")

    try:
        cmd = [
            PYTHON_EXEC, "-m", "pyhanko.cli.main", "sign", "validate",
            "--no-diff-analysis", "--force-revinfo", "--trust", TRUST_PATH,
            "--no-strict-syntax", "--pretty-print", tmp_path
        ]
        log_message(f"3. Ejecutando comando: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        log_message("4. Comando finalizado.")
        
        full_output = result.stdout + "\n" + result.stderr
        log_message(f"--- SALIDA CRUDA COMPLETA ---\n{full_output}\n--- FIN SALIDA ---")

        # Detectamos si la petición vino del navegador para mostrar la página HTML
        is_web_request = 'text/html' in request.headers.get('Accept', '')
        
        try:
            response_json = parse_pyhanko_output(full_output)
            if is_web_request:
                return render_template_string(HTML_TEMPLATE, results=response_json, filename=filename, raw_output=full_output)
            else:
                return jsonify(response_json)
        except Exception as parse_error:
            error_message = f"Error al parsear la salida de pyhanko: {parse_error}\n\nSALIDA RECIBIDA:\n{full_output}"
            log_message(error_message, is_error=True)
            if is_web_request:
                return render_template_string(HTML_TEMPLATE, error=error_message, filename=filename)
            else:
                return jsonify({"error": error_message}), 500

    except Exception as e:
        error_message = f"Error interno grave: {e}\n{traceback.format_exc()}"
        log_message(error_message, is_error=True)
        is_web_request = 'text/html' in request.headers.get('Accept', '')
        if is_web_request:
            return render_template_string(HTML_TEMPLATE, error=error_message, filename="N/A")
        else:
            return jsonify({"error": error_message}), 500
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

