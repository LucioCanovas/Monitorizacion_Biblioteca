import time
import docker
import telebot
import logging
import schedule
import mysql.connector
from datetime import datetime, timedelta

def estado_servidor():
    try:
        client = docker.from_env()
        contenedor = client.containers.get('descarga_archivos')
        contenedor.stop()
        contenedor.start()

        # Conexión a la base de datos
        connection = mysql.connector.connect(
            host="BaseDatos_bibliotecas",
            user="root",
            password="BBDD_sistema_conteo$",
            database="base_datos_bibliotecas"
        )
        cursor = connection.cursor()

        timestamp = datetime.now()

        # Parámetros para executemany deben estar dentro de una lista de tuplas
        parameters = [(timestamp, 1)]

        # Llamada correcta a executemany
        cursor.executemany("""INSERT INTO estado_servidor (timestamp, estado) VALUES (%s,%s)""", parameters)
        
        connection.commit()

        cursor.close()
        connection.close()

    except Exception as e:
        logging.error(f'Error en BBDD, funcion: estado_servidor, error: {e}')
        if connection.is_connected():
            cursor.close()
            connection.close()

    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()
    

def comprobar_estado():
    global estado_bib, detector_estado, bot, user_id

    client = docker.from_env()
    
    try:
        contenedor_detector = client.containers.get('detector')

        for biblioteca, nombre_contenedor_bib in estado_bib.items():

            contenedor_bib = client.containers.get(nombre_contenedor_bib)
            horario = check_time_in_range(biblioteca)  # True, biblioteca debe de estar encendida, False biblioteca debe de estar apagada
            logging.debug(f'Argumentos: {estado_bib}, horario: {horario}')

            if contenedor_bib.status != "running" and horario: 
                #Encendemos el detector si esta apagado
                if not detector_estado:
                    detector_estado = True
                    contenedor_detector.start()
                    time.sleep(180)
                    bot.send_message(user_id, f'Contenedor detector encendido')
                    logging.info(f'El contenedor detector, esta iniciado')

                contenedor_bib.start()
                bot.send_message(user_id, f'Contenedor {nombre_contenedor_bib} encendido')
                logging.info(f'El contenedor {nombre_contenedor_bib}, esta iniciado')
                
                #Encendemos el detector si esta apagado
                if not detector_estado:
                    detector_estado = True
                    contenedor_detector.start()
                    bot.send_message(user_id, f'Contenedor detector encendido')
                    logging.info(f'El contenedor detector, esta iniciado')


        hora_actual = datetime.now().time()
        hora_informes_1 = datetime.strptime('03:00:00', '%H:%M:%S').time()
        hora_informes_2 = datetime.strptime('03:15:00', '%H:%M:%S').time()

        if hora_informes_2 > hora_actual > hora_informes_1 and detector_estado == True:
            detector_estado = False
            contenedor_informes = client.containers.get('informes')
            contenedor_informes.start()
            #bot.send_message(user_id,f'Contenedor {contenedor_detector.name} cerrado, iniciando la creación de informe')
        logging.debug(f'Argumentos: {estado_bib}, detector_estado: {detector_estado}')

    except Exception as e:
        # Manejar cualquier error de conexión con Docker u otro error
       logging.error(f'Error al comprobar_estado: {e}')


def check_time_in_range(codigo_bib):
    try:
        fecha = datetime.now().date()
        
        connection = mysql.connector.connect(
            host="BaseDatos_bibliotecas",
            user="root",
            password="BBDD_sistema_conteo$",
            database="base_datos_bibliotecas"
        )
        cursor = connection.cursor()

        
        # Consulta para leer datos
        select_query = """
            SELECT hora_inicio, hora_final
            FROM horarios_biblioteca
            WHERE fecha = %s AND codigo_bib = %s
        """

        cursor.execute(select_query, (fecha, codigo_bib))

        resultado = cursor.fetchone()

        if resultado:
            hora_inicio, hora_fin = resultado
        else:
            # Si la fecha no existe, probar con las fechas predeterminadas para días de semana y fin de semana
            fecha_entrada_base = datetime.strptime('2000-01-01', '%Y-%m-%d') if fecha.weekday() < 5 else datetime.strptime('1999-01-01', '%Y-%m-%d')
            
            select_query = """
            SELECT hora_inicio, hora_final
            FROM horarios_biblioteca
            WHERE fecha = %s AND codigo_bib = %s
            """

            cursor.execute(select_query, (fecha_entrada_base, codigo_bib))

            resultado = cursor.fetchone()

            if resultado:
                # Si se encuentra en la fecha base, devolver las horas fin
                hora_inicio, hora_fin = resultado
            else:
                # Si no hay información para la fecha base, asignar valores predeterminados
                hora_inicio = datetime.strptime('07:00:00', '%H:%M:%S')

                hora_inicio = timedelta(
                    hours=hora_inicio.hour,
                    minutes=hora_inicio.minute,
                    seconds=hora_inicio.second)
                
                hora_fin = datetime.strptime('21:30:00', '%H:%M:%S')

                hora_fin = timedelta(
                    hours=hora_fin.hour,
                    minutes=hora_fin.minute,
                    seconds=hora_fin.second)

        connection.close()

    except Exception as e:
        hora_inicio = datetime.strptime('07:00:00', '%H:%M:%S')

        hora_inicio = timedelta(
            hours=hora_inicio.hour,
            minutes=hora_inicio.minute,
            seconds=hora_inicio.second)
        
        hora_fin = datetime.strptime('21:30:00', '%H:%M:%S')

        hora_fin = timedelta(
            hours=hora_fin.hour,
            minutes=hora_fin.minute,
            seconds=hora_fin.second)
        
        logging.error(f'Error en BBDD, funcion: limite_de_tiempo, biblioteca: {codigo_bib}, error: {e}')
        if connection.is_connected():
                connection.close()

    finally:
        if connection.is_connected():
                connection.close()

    if hora_inicio == 0 and hora_fin == 0:
        return False
    
    hora_actual = datetime.now().time()

    hora_actual = timedelta(
            hours=hora_actual.hour,
            minutes=hora_actual.minute,
            seconds=hora_actual.second)

    return hora_inicio < hora_actual < hora_fin

      
bot = telebot.TeleBot("6679369644:AAHxfnQvlimJlF1ke7x_ewfFo7TuQwHI3Tc")
user_id = '1849448005'

ruta = f'/app/Compartida/logs/maestro/log_maestro.log'

logging.basicConfig(filename=ruta, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('schedule').setLevel(logging.CRITICAL)
logging.info('Inicio de programa')

estado_bib = {'ANT': 'camara_ant',
              'CIM': 'camara_cim',
              'ALF': 'camara_alf'}

detector_estado = False

schedule.every(1).hours.do(estado_servidor)
schedule.every(5).minutes.do(comprobar_estado)

while True:
    # Verificar si hay tareas programadas para ejecutar
    schedule.run_pending()
    time.sleep(30)
    


