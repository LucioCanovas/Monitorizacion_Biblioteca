import sqlite3
import docker
import logging
import schedule
import psutil
import time
import telebot
from datetime import datetime

def estado_servidor():
    client = docker.from_env()
    contenedor = client.containers.get('descarga_archivos_v2')
    contenedor.stop()
    contenedor.start()

    conn = sqlite3.connect('/app/Compartida/BBDD/BBDD.db')
    cursor = conn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS estado_servidor
            (timestamp TEXT, estado INTEGER)""")
    
    conn.commit()

    formatted_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    query = [(formatted_timestamp, 1)]
    cursor.executemany("""INSERT INTO estado_servidor (timestamp, estado) VALUES (?,?)""", query)
    conn.commit()

    conn.close()
    

def comprobar_estado():
    global estado_bib, detector_estado, bot, user_id

    client = docker.from_env()
    
    try:
        contenedor_detector = client.containers.get('detector')

        for biblioteca, info_bib in estado_bib.items():
            estado = info_bib[0]
            nombre_contenedor_bib = info_bib[1]
            contenedor_bib = client.containers.get(info_bib[1])
            horario = check_time_in_range(biblioteca)  # True, biblioteca debe de estar encendida, False biblioteca debe de estar apagada
            logging.debug(f'Argumentos: {estado_bib}, horario: {horario}')

            if estado == 'Cerrado' and horario: 
                contenedor_bib.start()
                bot.send_message(user_id, f'Contenedor detector encendido')
                logging.info(f'El contenedor {nombre_contenedor_bib}, esta iniciado')
                estado_bib[biblioteca] = ('Abierto', nombre_contenedor_bib)
                
                #Encendemos el detector si esta apagado
                if not detector_estado:
                    detector_estado = True
                    contenedor_detector.start()
                    bot.send_message(user_id, f'Contenedor {nombre_contenedor_bib} encendido')
                    logging.info(f'El contenedor detector, esta iniciado')


            if estado == 'Abierto' and not horario: #Los contenedores de cada biblioteca se deben de apagar por si solos 
                estado_bib[biblioteca] = ('Cerrado', nombre_contenedor_bib)
                logging.info(f'El contenedor {nombre_contenedor_bib}, esta cerrado')
                bot.send_message(user_id, f'Contenedor {nombre_contenedor_bib} apagado')


        if contenedor_detector.status != "running" and detector_estado:
            detector_estado = False
            contenedor_informes = client.containers.get('informes')
            contenedor_informes.start()
            bot.send_message(user_id,f'Contenedor {contenedor_detector.name} cerrado, iniciando la creación de informe')

        return estado_bib, detector_estado

    except Exception as e:
        # Manejar cualquier error de conexión con Docker u otro error
       logging.error(f'Error al comprobar estado: {e}')


def check_time_in_range(codigo_bib):
    # Conectar a la base de datos SQLite3
    conn = sqlite3.connect('/app/Compartida/BBDD/BBDD.db')
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

    logging.debug(f'Horario: {hora_inicio} - {hora_fin}, Biblioteca: {codigo_bib}')
    if resultado:
        hora_inicio, hora_fin = resultado
        if hora_inicio == '00:00:00' and hora_fin == '00:00:00':
            return False
        current_time = datetime.now().strftime('%H:%M:%S')
        return hora_inicio <= current_time <= hora_fin
    return False


def obtener_cpu_memoria():
    global detector_estado
    if detector_estado:
        conn = sqlite3.connect("/app/Compartida/BBDD/BBDD.db")
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS memoria
                        (timestamp TEXT, porcentaje REAL)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS cpu
                        (timestamp TEXT, porcentaje REAL)''')
        conn.commit()

        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        porcentaje_cpu = psutil.cpu_percent()
        memoria_info = psutil.virtual_memory()
        porcentaje_memoria = memoria_info.percent

        cursor.execute("INSERT INTO cpu (timestamp, porcentaje) VALUES (?, ?)", (timestamp, porcentaje_cpu))
        cursor.execute("INSERT INTO memoria (timestamp, porcentaje) VALUES (?, ?)", (timestamp, porcentaje_memoria))

        conn.commit()
        conn.close()
      

bot = telebot.TeleBot("6679369644:AAHxfnQvlimJlF1ke7x_ewfFo7TuQwHI3Tc")
user_id = '1849448005'

fecha_hoy = datetime.now().date()

# Convertir la fecha a formato YYYY-MM-DD
fecha_formateada = fecha_hoy.strftime('%Y-%m-%d')

ruta = f'/app/Compartida/logs/maestro/log_maestro_{fecha_formateada}.log'

logging.basicConfig(filename=ruta, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info('Inicio de programa')

estado_bib = {'ANT': ('Cerrado', 'camara_ant')}
detector_estado = False

schedule.every(1).hours.do(estado_servidor)
schedule.every(5).minutes.do(comprobar_estado)
schedule.every(5).seconds.do(obtener_cpu_memoria)

while True:
    # Verificar si hay tareas programadas para ejecutar
    schedule.run_pending()
    time.sleep(2)
    


