from flask import Flask, request, jsonify
import tempfile
import os
import re
import sys
import traceback

# --- Importamos las funciones y clases necesarias de pyHanko ---
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_ltv_signature
from pyhanko_certvalidator import ValidationContext
from pyhanko_certvalidator.path import ValidationPath # Usaremos esto para verificar

app = Flask(__name__)

TRUST_PATH = "/app/cr-root-bundle.pem"

def procesar_con_libreria(ruta_pdf):
    """
    Valida un PDF usando pyHanko como una librería interna, con manejo de errores robusto.
    """
    print(f"Iniciando validación de librería para: {ruta_pdf}")
    sys.stdout.flush()
    try:
        with open(TRUST_PATH, 'rb') as f:
            trust_roots_pem = f.read()
        
        validation_context = ValidationContext(
            trust_roots=[trust_roots_pem],
            allow_fetching=True,
            revocation_mode='soft-fail' # Usamos soft-fail para máxima compatibilidad
        )

        firmas_encontradas = []
        with open(ruta_pdf, 'rb') as doc_file:
            r = PdfFileReader(doc_file)
            
            if not r.embedded_signatures:
                 print("No se encontraron firmas en el documento.")
                 sys.stdout.flush()
                 return {"firmas": [], "ok": False}

            for i, sig in enumerate(r.embedded_signatures):
                print(f"Analizando firma #{i+1}...")
                sys.stdout.flush()
                status = validate_pdf_ltv_signature(sig, validation_context)

                # --- LÓGICA "A PRUEBA DE BALAS" ---
                nombre = "No disponible"
                cedula = "No disponible"
                razon_invalidez = status.summary

                # Verificamos si la validación produjo una ruta de certificación válida.
                # Esta es la forma correcta de saber si el certificado fue procesado.
                if status.path and isinstance(status.path, ValidationPath):
                    cert = status.path.leaf_cert
                    nombre_firmante_str = cert.subject.human_friendly
                    cedula_match = re.search(r'serialNumber=CPF-([\d-]+)', nombre_firmante_str)
                    nombre_match = re.search(r'commonName=([^,]+)', nombre_firmante_str)
                    
                    if nombre_match: nombre = nombre_match.group(1)
                    if cedula_match: cedula = cedula_match.group(1)
                
                fecha_firma = status.signing_time.strftime('%Y-%m-%d %H:%M:%S') if status.signing_time else "No disponible"
                if status.valid: razon_invalidez = "OK"

                firma_info = {
                    "firma_valida": status.valid,
                    "datos": {
                        "razon_invalidez": razon_invalidez,
                        "nombre": nombre,
                        "cedula": cedula,
                        "fecha_firma": fecha_firma
                    }
                }
                firmas_encontradas.append(firma_info)
        
        print(f"Validación de librería completada. Firmas encontradas: {len(firmas_encontradas)}")
        sys.stdout.flush()
        return {"firmas": firmas_encontradas, "ok": len(firmas_encontradas) > 0}

    except Exception as e:
        print(f"ERROR GRAVE DENTRO DE LA LIBRERÍA: {e}")
        traceback.print_exc()
        sys.stderr.flush()
        return {"firmas": [], "ok": False, "error": str(e)}

@app.route("/")
def home():
    return "Servicio Validador de Firmas está en línea (v2 - Librería Interna)."

@app.route("/validate", methods=["POST"])
def validate_pdf():
    print("Petición de validación recibida.")
    sys.stdout.flush()
    if "file" not in request.files:
        return jsonify({"error": "No se envió archivo PDF"}), 400

    file = request.files["file"]
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    # Llamamos a nuestra nueva función interna
    resultado = procesar_con_libreria(tmp_path)
    
    # Limpiamos el archivo temporal
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)
        
    return jsonify(resultado)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=True)

    

