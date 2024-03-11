import sqlite3
import docker
import logging
import time
import telebot
from datetime import datetime

def estado_servidor():
    client = docker.from_env()
    contenedor = client.containers.get('descarga_archivos_v2')
    contenedor.stop()
    contenedor.start()

    conn = sqlite3.connect('/home/admincamaras/CamarasBiblioteca/Compartida/BBDD/BBDD.db')
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS estado_servidor
            (timestamp TEXT, estado INTEGER)""")
    
    conn.commit()

    formatted_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    query = [(formatted_timestamp, 1)]
    cursor.executemany("""INSERT INTO estado_servidor (timestamp, estado) VALUES (?,?)""", query)
    conn.commit()

    conn.close()
    

def comprobar_estado(estado_bib, bot, user_id):
    client = docker.from_env()
    contador_bib_cerrado = 0
    
    try:
        contenedor_detector = client.containers.get('detector')

        for biblioteca, info_bib in estado_bib.items():
            estado = info_bib[0]
            nombre_contenedor_bib = info_bib[1]
            contenedor_bib = client.containers.get(nombre_contenedor_bib)
            horario = check_time_in_range(biblioteca)  # Supongo que tienes definida esta función
            logging.info(f'Argumentos: {estado_bib}, horario: {horario}')

            if estado == 'Cerrado' and not horario:
                contador_bib_cerrado += 1
                logging.info(f'Primero: estado Cerrado, horario False')
                if contenedor_bib.status == "running":
                    contenedor_bib.stop()

            elif estado == 'Cerrado' and horario:
                logging.info(f'Segundo: estado Cerrado, horario True')
                #bot.send_message(user_id, message=f'Contenedor {nombre_contenedor_bib} iniciado')
                if contenedor_bib.status != "running":
                    contenedor_bib.start()
                    estado_bib[biblioteca] = ('Abierto', nombre_contenedor_bib)
                if contenedor_detector.status != "running":
                    contenedor_detector.start()

            elif estado == 'Abierto' and not horario:
                logging.info(f'Tercero: estado Abierto, horario False')
                contador_bib_cerrado += 1
                #bot.send_message(user_id, message=f'Contenedor {nombre_contenedor_bib} cerrado')
                if contenedor_bib.status == "running":
                    contenedor_bib.stop()
                    estado_bib[biblioteca] = ('Cerrado', nombre_contenedor_bib)

            elif estado == 'Abierto' and horario:
                logging.info(f'Cuarto: estado Abierto, horario True')
                if contenedor_bib.status != "running":
                    contenedor_bib.start()
                if contenedor_detector.status != "running":
                    contenedor_detector.start()

        if contador_bib_cerrado == len(estado_bib) and contenedor_detector.status == "running":
            contenedor_detector.stop()
            contenedor_informes = client.containers.get('informes')
            contenedor_informes.start()
            #bot.send_message(user_id, message=f'Contenedor {contenedor_detector.name} cerrado, iniciando la creación de informe')

        return estado_bib

    except Exception as e:
        # Manejar cualquier error de conexión con Docker u otro error
       logging.error(f'Error al comprobar estado: {e}')


def check_time_in_range(codigo_bib):
    # Conectar a la base de datos SQLite3
    conn = sqlite3.connect('/home/admincamaras/CamarasBiblioteca/Compartida/BBDD/BBDD.db')
    cursor = conn.cursor()
    
    # Obtener la fecha actual en formato YYYY-MM-DD
    fecha_actual = datetime.today().strftime('%Y-%m-%d')
    
    # Código biblioteca

    try:
        # Consultar si existe la fecha de ayer en la base de datos
        cursor.execute("""
            SELECT hora_inicio, hora_final
            FROM horarios
            WHERE fecha = ? AND codigo_bib = ?
        """, (fecha_actual, codigo_bib))

        resultado = cursor.fetchone()

        if resultado:
            # Si la fecha de ayer existe, devolver las horas de inicio y fin
            hora_inicio, hora_fin = resultado
        else:
            # Si la fecha de ayer no existe, seleccionar una fecha base según el día de la semana
            fecha_entrada_base = '2000-01-01' if datetime.strptime(fecha_actual, '%Y-%m-%d').weekday() < 5 else '1999-01-01'
            
            # Consultar las horas de inicio y fin para la fecha base y código de biblioteca
            cursor.execute("""
                SELECT hora_inicio, hora_final
                FROM horarios
                WHERE fecha = ? AND codigo_bib = ?
            """, (fecha_entrada_base, codigo_bib))

            resultado = cursor.fetchone()

            if resultado:
                # Si se encuentra en la fecha base, devolver las horas de inicio y fin
                hora_inicio, hora_fin = resultado
            else:
                # Si no hay información para la fecha base, asignar valores predeterminados
                hora_inicio, hora_fin = '07:30:00', '21:30:00'

    except sqlite3.Error as e:
        logging.error('Error en BBDD al obtener el horario')
        return None, None

    finally:
        # Cerrar la conexión a la base de datos
        conn.close()

    logging.info(f'Horario: {hora_inicio} - {hora_fin}, Biblioteca: {codigo_bib}')
    if resultado:
        hora_inicio, hora_fin = resultado
        if hora_inicio == '00:00:00' and hora_fin == '00:00:00':
            return False
        current_time = datetime.now().strftime('%H:%M:%S')
        return hora_inicio <= current_time <= hora_fin
    return False
   

logging.info('Inicio de programa')

bot = telebot.TeleBot("6679369644:AAHxfnQvlimJlF1ke7x_ewfFo7TuQwHI3Tc")
user_id = '1849448005'

log_file_path = '/home/admincamaras/CamarasBiblioteca/Compartida/Maestro/log_maestro.log'  
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
cont = 0

estado_bib = {'ANT': ('Cerrado', 'camara_ant')}
t_inicio = time.time()

while True:
    t_comprobacion = time.time() - t_inicio
    if t_comprobacion > 24 * 3600:
        break
    elif cont == 12:
        estado_servidor()

    logging.info('Comprobacion')
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    logging.info(f'Estado Biblioteca (antes): {estado_bib}')
    estado_bib = comprobar_estado(estado_bib, bot, user_id)
    logging.info(f'Estado Biblioteca(despues): {estado_bib}')
    time.sleep(300)
    cont+=1
