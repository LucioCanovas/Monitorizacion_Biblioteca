import os
import sqlite3
from datetime import date
from dotenv import load_dotenv
from flask import Flask, jsonify, abort, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

load_dotenv()

# Configuración para JWT
app.config['JWT_SECRET_KEY'] = os.getenv("key")
jwt = JWTManager(app)

# Datos de ejemplo de usuarios
USERS = {
    os.getenv("user"): os.getenv("password"),
}

biblioteca = ['ANT', 'CIM', 'ALF']


# Conexión a la base de datos SQLite
DATABASE = os.getenv("path_bbdd")

# Ruta para obtener el aforo de una biblioteca específica
@app.route('/api/aforo', methods=['GET'])
@jwt_required()
def obtener_aforo():
    dicc_aforo = {'ANT':0, 'CIM':0, 'ALF':0}
    # Obtener la fecha actual en formato 'YYYY-MM-DD'
    fecha_actual = date.today().strftime("%Y-%m-%d")

    # Consulta a la base de datos para obtener el último registro de aforo
    query = """
        SELECT aforo
        FROM Aforo
        WHERE codigo_bib = ? AND fecha = ? 
        ORDER BY Hora DESC
        LIMIT 1
    """

    # Inicializa la variable de resultado fuera del bloque try para manejar el caso de excepción
    resultado = None

    try:
        for codigo_bib in biblioteca:
            print(codigo_bib)
            with sqlite3.connect(DATABASE) as conn:
                cursor = conn.cursor()
                cursor.execute(query, (codigo_bib, fecha_actual))
                resultado = cursor.fetchone()


            if resultado is None:
                aforo = 0
            else:
                aforo = resultado[0]
            # Verificar si el aforo es negativo y ajustarlo a 0
            aforo = max(aforo, 0)
            dicc_aforo[codigo_bib] = aforo

            # Devuelve la información del aforo
        return jsonify({"ANT": dicc_aforo['ANT'],
                        "CIM": dicc_aforo['CIM'], 
                        "ALF": dicc_aforo['ALF']})


    finally:
        # Cierra la conexión después de completar la operación
        if 'conn' in locals():
            conn.close()

# Ruta para la autenticación y obtención del token
@app.route('/api/auth', methods=['POST'])
def authenticate():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    # Verifica las credenciales
    if USERS.get(username) == password:
        # Emite un token de acceso
        access_token = create_access_token(identity=username)
        return jsonify(access_token=access_token)
    else:
        return jsonify({"message": "Credenciales incorrectas"}), 401

if __name__ == '__main__':
    cert_file = r'C:\Users\Usuario\Desktop\TFG\src\Codigo_final\API_REST\certificado_firmado.pem'
    key_file = r'C:\Users\Usuario\Desktop\TFG\src\Codigo_final\API_REST\clave_privada.pem'

    # Ejemplo de configuración para HTTPS
    app.run(debug=True, host='0.0.0.0', port=5001, ssl_context=(cert_file, key_file))



