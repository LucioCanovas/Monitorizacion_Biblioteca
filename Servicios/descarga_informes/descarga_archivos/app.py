import os
import sqlite3
from datetime import datetime
from math import ceil
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session
from functools import wraps
from passlib.hash import bcrypt

app = Flask(__name__)
app.secret_key = os.getenv('key')

load_dotenv()

hashed_user = os.getenv('user')
hashed_user_password = os.getenv('password')
hashed_admin = os.getenv('admin')
hashed_admin_password = os.getenv('admin_password')

@app.route('/')
def index():
    return redirect(url_for('login'))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Autenticación de usuario
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        contrasena = request.form['contrasena']

        if bcrypt.verify(usuario, hashed_user) and bcrypt.verify(contrasena, hashed_user_password):
            session['logged_in'] = True
            session['role'] = 'user'  # Almacena el rol del usuario en la sesión
            return redirect(url_for('descargar'))
        
        elif bcrypt.verify(usuario, hashed_admin) and bcrypt.verify(contrasena, hashed_admin_password):
            session['logged_in'] = True
            session['role'] = 'admin'  # Almacena el rol del usuario en la sesión
            return redirect(url_for('descargar'))

        else:
            mensaje_error = 'Credenciales incorrectas. Intenta de nuevo.'
            return render_template('login.html', mensaje_error=mensaje_error)
    return render_template('login.html')

@app.route('/descargar', methods=['GET', 'POST'])
@login_required
def descargar():
    if request.method == 'POST':
        codigo_bib = request.form['codigo_bib']
        intervalo = request.form['intervalo']
        rol_usuario = session.get('role')
        return redirect(url_for('mostrar_archivos', codigo_bib=codigo_bib, intervalo=intervalo))

    return render_template('archivos.html')

@app.route('/descargar/<codigo_bib>/<intervalo>')
@login_required
def mostrar_archivos(codigo_bib, intervalo):
    ruta = f'/app/Compartida/{codigo_bib}/Informes/{intervalo}'
    
    def sort_by_file_name(entry):
        file_name = entry.name  # Obtener el nombre del archivo del objeto DirEntry
        date_str = file_name.split('_')[0]  # Extraer la parte de la fecha del nombre del archivo
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')  # Convertir la cadena de fecha a un objeto datetime
        return date_obj

    archivos_ordenados = sorted(os.scandir(ruta), key=sort_by_file_name, reverse=True)

    nombres_archivos = [archivo.name for archivo in archivos_ordenados]
    
    # Obtener el número total de páginas
    num_paginas = ceil(len(nombres_archivos) / 20)
    
    # Obtener el número de página solicitado, si no se proporciona, establecer en 1
    pagina = int(request.args.get('pagina', 1))
    
    # Calcular los índices de inicio y fin para la página actual
    inicio = (pagina - 1) * 20
    fin = pagina *  20
    
    # Obtener los nombres de archivos para la página actual
    archivos_pagina = nombres_archivos[inicio:fin]
    
    # Renderizar la plantilla HTML y pasar los datos necesarios
    return render_template('archivos.html', archivos=archivos_pagina, codigo_bib=codigo_bib, intervalo=intervalo, num_paginas=num_paginas, pagina_actual=pagina)

@app.route('/descargar/<codigo_bib>/<intervalo>/<nombre>')
@login_required
def descargar_archivo(codigo_bib, nombre, intervalo):
    # Determinar la ruta según el código_bib seleccionado
    ruta = f'/app/Compartida/{codigo_bib}/Informes/{intervalo}'
    ruta_archivo = os.path.join(ruta, nombre)
    #print(f'Ruta archivo:{ruta_archivo}')

    return send_from_directory(os.path.dirname(ruta_archivo), nombre, as_attachment=True, download_name=nombre)

# Ruta para eliminar archivo
@app.route('/eliminar_archivo/<codigo_bib>/<intervalo>/<nombre>', methods=['POST'])
@login_required
def eliminar_archivo(codigo_bib, intervalo, nombre):
    rol = session.get('role')
    if rol != 'admin':
        # Manejar caso en que el usuario no tiene permisos de administrador
        return 'Solo el administrador puede eliminar informes.'

    ruta = f'/app/Compartida/{codigo_bib}/Informes/{intervalo}'
    ruta_archivo = os.path.join(ruta, nombre)

    if os.path.exists(ruta_archivo):
        os.remove(ruta_archivo)    
    else:
        print(f"El archivo '{nombre}' no existe.")

    return redirect(url_for('mostrar_archivos', codigo_bib=codigo_bib, intervalo=intervalo))

@app.route('/horarios', methods=['GET', 'POST'])
@login_required
def horarios():
    if session.get('role') != 'admin':
        return 'Acceso denegado. Solo el administrador puede acceder a esta página.'
    if request.method == 'POST':
        codigo_bib = request.form['codigo_bib']
        return redirect(url_for('mostrar_horarios', codigo_bib=codigo_bib), code=307)

    return render_template('horarios.html')

@app.route('/horarios/<codigo_bib>', methods=['GET', 'POST'])
@login_required
def mostrar_horarios(codigo_bib):
    if session.get('role') != 'admin':
        return 'Acceso denegado. Solo el administrador puede acceder a esta página.'
    if request.method == 'POST':
        codigo_bib_seleccionado = request.form['codigo_bib']
        # Obtener todas las fechas, hora de inicio y hora final asociadas al código_bib seleccionado
        with sqlite3.connect('/app/Compartida/BBDD/BBDD.db') as connection:
            cursor = connection.cursor()
            cursor.execute('''
                SELECT fecha, hora_inicio, hora_final
                FROM horarios
                WHERE codigo_bib = ?
                ORDER BY fecha
            ''', (codigo_bib_seleccionado,))
            horarios = cursor.fetchall()

        return render_template('horarios.html', codigo_bib=codigo_bib, horarios=horarios)

    return render_template('horarios.html')

@app.route('/horarios/<codigo_bib>/agregar', methods=['POST'])
@login_required
def agregar_horario(codigo_bib):
    if session.get('role') != 'admin':
        return 'Acceso denegado. Solo el administrador puede acceder a esta página.'
    if request.method == 'POST':
        # Obtener la nueva información del formulario
        opcion = request.form['opcion']
        fecha_nueva = request.form['fecha_nueva']
        hora_inicio_nueva = request.form['hora_inicio_nueva']
        hora_final_nueva = request.form['hora_final_nueva']

        # Convertir las cadenas a objetos datetime y time
        fecha_nueva = datetime.strptime(fecha_nueva, '%Y-%m-%d').date()
        hora_inicio_nueva = datetime.strptime(hora_inicio_nueva, '%H:%M').time().strftime('%H:%M:%S')
        hora_final_nueva = datetime.strptime(hora_final_nueva, '%H:%M').time().strftime('%H:%M:%S')

        # Guardar la nueva entrada en la base de datos
        with sqlite3.connect('/app/Compartida/BBDD/BBDD.db') as connection:
            cursor = connection.cursor()
            if opcion == "Añadir":
                cursor.execute('''
                    INSERT INTO horarios (codigo_bib, fecha, hora_inicio, hora_final)
                    VALUES (?, ?, ?, ?)
                ''', (codigo_bib, fecha_nueva, hora_inicio_nueva, hora_final_nueva))
                connection.commit()
            elif opcion == "Eliminar":
                cursor.execute('''
                    DELETE FROM horarios
                    WHERE codigo_bib = ? AND fecha = ?
                    ''', (codigo_bib, fecha_nueva))
                connection.commit()

        # Redirigir de nuevo a la página de horarios
        return redirect(url_for('mostrar_horarios', codigo_bib=codigo_bib), code=307)


if __name__ == '__main__':
    # Ruta a tu certificado SSL y clave privada
    cert_file = '/app/Openssl/certificado_firmado.pem'
    key_file = '/app/Openssl/clave_privada.pem'

    # Ejemplo de configuración para HTTPS
    app.run(debug=True, host='0.0.0.0', port=5000, ssl_context=(cert_file, key_file))




