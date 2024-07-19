import os
import mysql.connector
import logging
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, jsonify, make_response, request
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


# Ruta para obtener el aforo de una biblioteca específica
@app.route('/api/aforo', methods=['GET'])
@jwt_required()
def obtener_aforo():
    try:
        dicc_aforo = {'ANT':0, 'CIM':0, 'ALF':0}
        # Obtener la fecha actual en formato 'YYYY-MM-DD'
        fecha_actual = datetime.now().date()

        # Consulta a la base de datos para obtener el último registro de aforo
        query = """
            SELECT aforo
            FROM aforo_biblioteca
            WHERE codigo_bib = %s AND fecha = %s 
            ORDER BY secuencia DESC
            LIMIT 1
        """

        resultado = None

        try:
            for codigo_bib in biblioteca:
                connection = mysql.connector.connect(
                    host="BaseDatos_bibliotecas",
                    user="root",
                    password="",
                    database="base_datos_bibliotecas"
                )
                cursor = connection.cursor()

                cursor.execute(query, (codigo_bib, fecha_actual))
                resultado = cursor.fetchone()
                logging.info(f'codigo: {codigo_bib}, fecha: {fecha_actual}')
                cursor.close()
                connection.close()

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
           if connection.is_connected():
            # Cerrar la conexión a la base de datos
            connection.close()
            cursor.close()

    except Exception as e:
            logging.error(f'Error al obtener aforo: {e}')
            if connection.is_connected():
                # Cerrar la conexión a la base de datos
                connection.close()
                cursor.close()

            # Devolver mensaje de error al cliente
            mensaje_error = {"error": "Ocurrió un error al obtener el aforo"}
            return make_response(jsonify(mensaje_error), 500)

# Ruta para la autenticación y obtención del token
@app.route('/api/auth', methods=['POST'])
def authenticate():
    try:
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
        
    except Exception as e:
        logging.error(f'Error en la autenticacion: {e}')


if __name__ == '__main__':
    cert_file = r'/app/certificado_firmado.pem'
    key_file = r'/app/clave_privada.pem'

    ruta_log = f'/app/Compartida/logs/api/log_api.log'
    logging.basicConfig(filename=ruta_log, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    app.run(debug=True, host='0.0.0.0', port=5001, ssl_context=(cert_file, key_file))



