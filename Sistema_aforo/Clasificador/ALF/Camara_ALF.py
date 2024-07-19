import os
import cv2
import pika
import time
import ping3
import pstats
import telebot
import logging
import cProfile
import numpy as np
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime, timedelta


# Cargar variables de entorno desde el archivo .env
load_dotenv()

def cierre_biblioteca(codigo_bib):
    try:
        # Conexión a la base de datos
        connection = mysql.connector.connect(
            host="BaseDatos_bibliotecas",
            user="root",
            password="BBDD_sistema_conteo$",
            database="base_datos_bibliotecas"
        )
        cursor = connection.cursor()

        fecha_actual = datetime.today().date()

        # Consulta para leer datos
        select_query = """
            SELECT hora_final
            FROM horarios_biblioteca
            WHERE fecha = %s AND codigo_bib = %s
        """

        cursor.execute(select_query, (fecha_actual, codigo_bib))

        resultado = cursor.fetchone()

        if resultado:
            # Si la fecha de ayer existe, devolver las horas de inicio y fin
            hora_cierre = resultado[0]
        else:
            # Si la fecha de ayer no existe, seleccionar una fecha base según el día de la semana
            fecha_entrada_base = datetime.strptime('2000-01-01', '%Y-%m-%d') if fecha_actual.weekday() < 5 else datetime.strptime('1999-01-01', '%Y-%m-%d')
            
            select_query = """
            SELECT hora_final
            FROM horarios_biblioteca
            WHERE fecha = %s AND codigo_bib = %s
            """

            cursor.execute(select_query, (fecha_entrada_base, codigo_bib))

            resultado = cursor.fetchone()

            if resultado:
                # Si se encuentra en la fecha base, devolver las horas de inicio y fin
                hora_cierre = resultado[0]
            else:
                # Si no hay información para la fecha base, asignar valores predeterminados
                hora_cierre = datetime.strptime('21:30:00', '%H:%M:%S')

                hora_cierre = timedelta(
                    hours=hora_cierre.hour,
                    minutes=hora_cierre.minute,
                    seconds=hora_cierre.second)
        connection.close()

    except Exception as e:
        hora_cierre = datetime.strptime('21:30:00', '%H:%M:%S')

        hora_cierre = timedelta(
            hours=hora_cierre.hour,
            minutes=hora_cierre.minute,
            seconds=hora_cierre.second)
        logging.error(f'Error en BBDD, funcion: cierre_biblioteca, biblioteca: {codigo_bib}, error: {e}')

        if connection.is_connected():
                connection.close()

    finally:
        if connection.is_connected():
                connection.close()

            

    hora_actual = datetime.now().time()

    hora_actual = timedelta(
    hours=hora_actual.hour,
    minutes=hora_actual.minute,
    seconds=hora_actual.second)

    return hora_actual > hora_cierre

def obtener_ultima_secuencia(codigo_bib):
    try: 
        # Conexión a la base de datos
        connection = mysql.connector.connect(
            host="BaseDatos_bibliotecas",
            user="root",
            password="BBDD_sistema_conteo$",
            database="base_datos_bibliotecas"
        )
        cursor = connection.cursor()

        fecha_actual = datetime.now().date()

        cursor.execute("""
                    SELECT IFNULL(secuencia, 0) as ultima_secuencia
                    FROM aforo_biblioteca
                    WHERE fecha = %s AND codigo_bib = %s
                    ORDER BY secuencia DESC
                    LIMIT 1
                """, (fecha_actual, codigo_bib,))

        resultado = cursor.fetchone()

        connection.close()

        # Retornar la secuencia (0 si no hay resultados)
        return resultado[0] if resultado else 0
    
    except Exception as e:
        logging.error(f'Error en BBDD, funcion: obtener_ultima_secuencia, biblioteca: {codigo_bib}, error: {e}')
        if connection.is_connected():
                connection.close()

    finally:
        if connection.is_connected():
            connection.close()

def estado_camara_basedatos(codigo_bib, estado):
    global contador_tiempo_camara_activa, ultima_hora_activacion_camara 
    try: 
        # Conexión a la base de datos
        connection = mysql.connector.connect(
            host="BaseDatos_bibliotecas",
            user="root",
            password="BBDD_sistema_conteo$",
            database="base_datos_bibliotecas"
        )
        cursor = connection.cursor()

        if estado:
            # Cámara activa
            query = "INSERT INTO estado_camara (codigo_bib, timestamp, flag, estado) VALUES (%s,%s,%s,%s)"
            timestamp = datetime.now()
            formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            valores = (codigo_bib, formatted_timestamp, 'f', 0)
            cursor.execute(query, valores)

            time.sleep(1)

            query = "INSERT INTO estado_camara (codigo_bib, timestamp, flag, estado) VALUES (%s,%s,%s,%s)"
            timestamp = datetime.now()
            ultima_hora_activacion_camara = timestamp
            formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            valores = (codigo_bib, formatted_timestamp, 'i', 1)
            cursor.execute(query, valores)

        else: 
            # Cámara desactivada
            query = "INSERT INTO estado_camara (codigo_bib, timestamp, flag, estado) VALUES (%s,%s,%s,%s)"
            timestamp = datetime.now()
            diferencia = timestamp - ultima_hora_activacion_camara
            contador_tiempo_camara_activa += diferencia
            formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            valores = (codigo_bib, formatted_timestamp, 'f', 1)
            cursor.execute(query, valores)

            time.sleep(1)

            query = "INSERT INTO estado_camara (codigo_bib, timestamp, flag, estado) VALUES (%s,%s,%s,%s)"
            timestamp = datetime.now()
            formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            valores = (codigo_bib, formatted_timestamp, 'i', 0)
            cursor.execute(query, valores)

        connection.commit()
        connection.close()

    except Exception as e:
        logging.error(f'Error en BBDD, funcion: estado_camara_basedatos, biblioteca: {codigo_bib}, error: {e}')
        if connection.is_connected():
                connection.close()

    finally:
        if connection.is_connected():
            connection.close()

def conexion(ip):
    try:
        ping_camara = ping3.ping(ip, timeout=8)
        if ping_camara is None or ping_camara is False:
            logging.info(f'Ping a {ip} fallido, respuesta: {ping_camara}')
            return False
        else:
            logging.info(f'Ping a {ip} exitoso. Tiempo de respuesta: {ping_camara} s')
            return True
    except Exception as e:
        logging.error(f'********** Error al realizar ping a {ip}: {e} **********')
        return False
    
def crear_cola_mensajes(usuario, contraseña, ip_broker, cola): 
    credentials = pika.PlainCredentials(usuario,
                                        contraseña)
    
    parameters = pika.ConnectionParameters(ip_broker,
                                           5672,
                                           '/',
                                           credentials)

    while True:
        try:
            connection = pika.BlockingConnection(parameters)
            canal = connection.channel()
            canal.queue_declare(queue=cola)
            logging.info('Cola mensajes creada')
            return canal
        except Exception as e:
            logging.error(f'********** Error al crear la cola rabbit **********')
            logging.error(e)
            time.sleep(1)

def enviar_mensaje_cola(secuencia, id_bib, cola): 
    global canal
    try:
        hora_actual = datetime.now()
        hora_actual_formateada = hora_actual.strftime('%Y-%m-%d %H:%M:%S')
        
        mensaje = f'{id_bib},{secuencia},{hora_actual_formateada}'
        logging.debug(f'Mensaje enviado: {mensaje}')
        
        canal.basic_publish(exchange='',
                              routing_key=cola,
                              body=mensaje)
    
    except Exception as e:
        logging.error(f'Error al enviar mensaje: {e}')
        time.sleep(1)
        canal = crear_cola_mensajes(usuario, contraseña, ip_broker, 'BibliotecaUPCT')
        enviar_mensaje_cola(secuencia, id_bib, cola)

def clasificadorPersona(frame, area, k):
    # Aplicamos sustractor CNT
    imagen_binaria = cnt.apply(frame, learningRate=0.2)

    # Erosion para eliminar ruido
    imagen_binaria = cv2.erode(imagen_binaria, kernel_erosion)

    for _ in range(0,k):
        imagen_binaria = cv2.dilate(imagen_binaria, kernel_dilatacion)
    
    # Lista de contornos
    contornos = cv2.findContours(imagen_binaria, 
                                 cv2.RETR_EXTERNAL, 
                                 cv2.CHAIN_APPROX_SIMPLE)[0]
   
    for contorno in contornos:
        if cv2.contourArea(contorno) > area:
            #Hay personas en el frame
            return True
    # No hay personas en el frame   
    return False

def continuar_grabacion(deteccion_actual, deteccion_anterior, grabacion_activa):
    # Si ambos frames tienen detección, continúa grabando
    if deteccion_actual and deteccion_anterior:
        return True
    
    # Si ambos frames no tienen detección, detiene la grabación
    elif not deteccion_actual and not deteccion_anterior:
        return False
    
    # Resto de casos, sigue en el estado actual
    else:
        return grabacion_activa

def crear_pasillo_virtual(img_pasillo):

    pts_pasillo = np.array([[punto_izq_sup], [punto_drcha_sup], [punto_drcha_inf], [punto_izq_inf]], np.int32)

    # Crear una máscara con los puntos del contorno
    imAux = np.zeros(shape=(img_pasillo.shape[:2]), dtype=np.uint8)
    imAux = cv2.drawContours(imAux, [pts_pasillo], -1, 255, -1)

    # Aplicar la máscara a la imagen original
    img_conjunta = cv2.bitwise_and(img_pasillo, img_pasillo, mask=imAux)
    return img_conjunta

def añadir_tiempo_camara_activa(codigo_bib, tiempo):
    try: 
        # Conexión a la base de datos
        connection = mysql.connector.connect(
            host="BaseDatos_bibliotecas",
            user="root",
            password="BBDD_sistema_conteo$",
            database="base_datos_bibliotecas"
        )
        cursor = connection.cursor()

        fecha = datetime.now().date()

        total_segundos = int(tiempo.total_seconds())
        horas = total_segundos // 3600
        minutos = (total_segundos % 3600) // 60
        segundos = total_segundos % 60
        string_tiempo_activo_camara = f'{horas}:{minutos}:{segundos}'

        query = "INSERT INTO tiempo_camara_activa (codigo_bib, tiempo, fecha) VALUES (%s,%s,%s)"
        valores = (codigo_bib, string_tiempo_activo_camara, fecha)
        cursor.execute(query, valores)
        connection.commit()
        connection.close()

    except Exception as e:
        logging.error(f'Error en BBDD, funcion: añadir_tiempo_camara_activa, biblioteca, error: {e}')
        if connection.is_connected():
                connection.close()

    finally:
        if connection.is_connected():
            connection.close()

# =========================== Variables ========================== # 
# Bot Telegram
bot = telebot.TeleBot(os.getenv('telegram_chat'))
user_id = os.getenv('telegram_user_id')

# Path carpetas
path_imagenes = os.getenv("path_imagenes")  

# Variables generales
frame_id = 0
secuencia_id = obtener_ultima_secuencia(os.getenv("Codigo_bib"))
estado_grabacion_actual = False
deteccion_anterior = False 
contador_tiempo_camara_activa = timedelta()
ultima_hora_activacion_camara = None

# Kernels operaciones de postprocesado de imagenes
kernel_erosion = np.ones((3, 3), np.uint8)
kernel_dilatacion = np.ones((11, 11), np.uint8)

# Variables del clasificador personas
area = int(os.getenv("area"))
k = int(os.getenv("k"))
cnt = cv2.bgsegm.createBackgroundSubtractorCNT(minPixelStability=10, 
                                                maxPixelStability=10*15)
# Variables cola mq-rabbit
ip_broker = os.getenv("Ip_broker")
usuario = os.getenv("mq_user")
contraseña = os.getenv("mq_password")
Id_bib = os.getenv("Id_bib")

# Pasillo virtual esquinas
x_izq_sup = int(os.getenv('x_izq_sup'))
y_izq_sup = int(os.getenv('y_izq_sup'))
punto_izq_sup = [x_izq_sup, y_izq_sup]

x_drcha_sup = int(os.getenv('x_drcha_sup'))
y_drcha_sup = int(os.getenv('y_drcha_sup'))
punto_drcha_sup = [x_drcha_sup, y_drcha_sup]

x_izq_inf = int(os.getenv('x_izq_inf'))
y_izq_inf = int(os.getenv('y_izq_inf'))
punto_izq_inf = [x_izq_inf, y_izq_inf]

x_drcha_inf = int(os.getenv('x_drcha_inf'))
y_drcha_inf = int(os.getenv('y_drcha_inf'))
punto_drcha_inf = [x_drcha_inf, y_drcha_inf]

# Archivo logging
log_file_path = os.getenv("path_logging")
fecha_hoy = datetime.now().date()
fecha_formateada = fecha_hoy.strftime('%Y-%m-%d')

ruta = f'{log_file_path}/log_camara_ant_{fecha_formateada}.log'

logging.basicConfig(filename=ruta, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('pika').setLevel(logging.CRITICAL)

logging.info('Programa iniciado')

with cProfile.Profile() as profile:

# =========================== Main Loop ========================== #
    conexion_camara = conexion(os.getenv("Ip_camara"))
    bot.send_message(user_id,f'Iniciando cámara {os.getenv("Codigo_bib")}, conexión: {conexion_camara}')

    canal = crear_cola_mensajes(usuario, contraseña, ip_broker, 'BibliotecaUPCT')
    enviar_mensaje_cola(0, Id_bib, 'BibliotecaUPCT') #Mensaje inicio de biblioteca


    while True:
        
        #Si se excede el tiempo limite se envía mensaje de cierre de biblioteca
        if cierre_biblioteca(os.getenv("Codigo_bib")):
            enviar_mensaje_cola(-1, Id_bib, 'BibliotecaUPCT')
            break   # Salimos del while

        conexion_camara = conexion(os.getenv("Ip_camara"))
        if conexion_camara:

            deteccion_anterior = False  
            estado_grabacion_actual = False  
            frame_id = 0
            cap = cv2.VideoCapture(os.getenv("RTSP_URL"))

            logging.info('Conexion con la camara')
            estado_camara_basedatos(os.getenv("Codigo_bib"), True)
        
            #Iniciamos captura y analisis de frames 
            while cap.isOpened():

                status, frame = cap.read()

                if status:
                    frame = cv2.rotate(frame, cv2.ROTATE_180)   #Activar o desactivar dependiendo de la orientación de la cámara
                    frame = crear_pasillo_virtual(frame)
                    # Realiza la detección de personas
                    deteccion = clasificadorPersona(frame, area, k)

                    estado_grabacion_anterior  = estado_grabacion_actual

                    # Determina si se debe continuar grabando las imagenes
                    estado_grabacion_actual = continuar_grabacion(deteccion, 
                                                                deteccion_anterior, 
                                                                estado_grabacion_actual)

                    # Si comienza una nueva secuencia o si acaba una secuencia
                    if not estado_grabacion_anterior and estado_grabacion_actual:
                        secuencia_id += 1
                        frame_id = 0
                    elif estado_grabacion_anterior and not estado_grabacion_actual:
                        enviar_mensaje_cola(secuencia_id, Id_bib, 'BibliotecaUPCT')

                    # Actualiza la detección anterior
                    deteccion_anterior = deteccion

                    if estado_grabacion_actual:
                        nombre_imagen = 'sc{:05d}_f_{:05d}.jpg'.format(secuencia_id, 
                                                                        frame_id)
                            
                        cv2.imwrite(path_imagenes  + '/' + nombre_imagen, frame)

                    frame_id += 1

                #Error en la conexion de la cámara   
                else:
                    logging.info(f'Error en el frame')
                    break   #Salimos del bucle While cap.isOpened()
                
            cap.release()
            logging.error('Desconexion con la camara')
            estado_camara_basedatos(os.getenv("Codigo_bib"), False)
    
    bot.send_message(user_id,f'Cámara {os.getenv("Codigo_bib")} finalizada')
    añadir_tiempo_camara_activa(os.getenv("Codigo_bib"), contador_tiempo_camara_activa)
    results = pstats.Stats(profile)
    results.sort_stats(pstats.SortKey.TIME)
    logging.info('Programa finalizado')
    results.dump_stats(f"profile_camara_ant_{fecha_formateada}.prof")



