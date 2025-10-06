from flask import Flask, request, jsonify
import tempfile
import os
import re
import sys
import traceback

# --- Importamos las funciones y clases necesarias de pyHanko y sus dependencias ---
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_ltv_signature
from pyhanko_certvalidator import ValidationContext, pem
from pyhanko_certvalidator.path import ValidationPath

app = Flask(__name__)

TRUST_PATH = "/app/cr-root-bundle.pem"

def procesar_con_libreria(ruta_pdf):
    """
    Valida un PDF usando pyHanko como una librería interna, con manejo de errores robusto.
    """
    try:
        # Cargamos los certificados raíz de confianza correctamente
        with open(TRUST_PATH, 'rb') as f:
            trust_roots = list(pem.load_certs(f.read()))
        
        validation_context = ValidationContext(
            trust_roots=trust_roots,
            allow_fetching=True,
            revocation_mode='soft-fail' # Usamos soft-fail para máxima compatibilidad
        )

        firmas_encontradas = []
        with open(ruta_pdf, 'rb') as doc_file:
            r = PdfFileReader(doc_file)
            
            if not r.embedded_signatures:
                 # Si no hay firmas, devolvemos una lista vacía
                 return {"firmas": [], "ok": False}

            for sig in r.embedded_signatures:
                status = validate_pdf_ltv_signature(sig, validation_context)

                # --- LÓGICA "A PRUEBA DE BALAS" ---
                nombre, cedula, razon_invalidez = "No disponible", "No disponible", status.summary
                
                # Verificamos si la validación produjo una ruta de certificación válida.
                if status.path and isinstance(status.path, ValidationPath):
                    cert = status.path.leaf_cert
                    nombre_firmante_str = cert.subject.human_friendly
                    
                    cedula_match = re.search(r'serialNumber=CPF-([\d-]+)', nombre_firmante_str)
                    nombre_match = re.search(r'commonName=([^,]+)', nombre_firmante_str)
                    
                    if nombre_match: nombre = nombre_match.group(1)
                    if cedula_match: cedula = cedula_match.group(1)
                
                fecha_firma = status.signing_time.strftime('%Y-%m-%d %H:%M:%S') if status.signing_time else "No disponible"
                if status.valid: razon_invalidez = "OK"

                firmas_encontradas.append({
                    "firma_valida": status.valid,
                    "datos": {"razon_invalidez": razon_invalidez, "nombre": nombre, "cedula": cedula, "fecha_firma": fecha_firma}
                })
        
        return {"firmas": firmas_encontradas, "ok": len(firmas_encontradas) > 0}

    except Exception as e:
        # Capturamos cualquier error y lo devolvemos para depuración
        print(f"--- ERROR INESPERADO EN LIBRERÍA ---\n{traceback.format_exc()}\n--- FIN ERROR ---", file=sys.stderr)
        return {"firmas": [], "ok": False, "error": str(e)}

@app.route("/")
def home():
    return "Servicio Validador de Firmas está en línea (v_final)."

@app.route("/validate", methods=["POST"])
def validate_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # Llamamos a nuestra función interna que usa la librería
    resultado = procesar_con_libreria(tmp_path)
    
    # Limpiamos el archivo temporal
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
        
    return jsonify(resultado)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

