import os
import cv2
import time
import pika
import ping3
import logging
import sqlite3
import datetime
import numpy as np
from datetime import datetime
from dotenv import load_dotenv


# Cargar variables de entorno desde el archivo .env
load_dotenv()

def obtener_secuencia_del_dia(codigo_bib):

    nombre_base_de_datos = os.getenv("path_bbdd")

    # Obtener la fecha actual
    fecha_actual = datetime.now().strftime('%Y-%m-%d')

    # Conectar a la base de datos SQLite
    conn = sqlite3.connect(nombre_base_de_datos)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS Aforo (
            codigo_bib TEXT,
            timestamp TEXT,
            fecha TEXT,
            secuencia INTEGER,
            Hora TEXT,
            Hora_final TEXT,
            personas_in INTEGER,
            personas_out INTEGER,
            aforo INTEGER,
            grado_0 INTEGER, 
            grado_1 INTEGER, 
            grado_2 INTEGER, 
            grado_3 INTEGER, 
            grado_4 INTEGER
        )
    ''')

    conn.commit()

    # Consulta SQL para obtener la secuencia del día para el código_bib específico
    query = "SELECT COALESCE(MAX(secuencia), 0) FROM Aforo WHERE codigo_bib = ? AND fecha = ?"
    cursor.execute(query, (codigo_bib, fecha_actual))
    resultado = cursor.fetchone()

    # Cerrar la conexión
    conn.close()

    # Retornar la secuencia del día (o None si no hay resultados)
    return resultado[0] if resultado else 0


def estado_camara_sqlite(codigo_bib, estado):

    nombre_base_de_datos = os.getenv("path_bbdd")

    # Obtener la fecha actual
    timestamp = datetime.now()
    formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')

    # Conectar a la base de datos SQLite
    conn = sqlite3.connect(nombre_base_de_datos)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS estado_camara
            (codigo_bib TEXT, timestamp TEXT, flag TEXT, estado INTEGER)""")

    conn.commit()

    if estado:
        # Cámara activa
        query = [(codigo_bib, formatted_timestamp, 'f', 0)]
        c.executemany("""INSERT INTO estado_camara (codigo_bib, timestamp, flag, estado) VALUES (?,?,?,?)""", query)
        conn.commit()

        query = [('ANT', formatted_timestamp, 'i', 1)]
        c.executemany("""INSERT INTO estado_camara (codigo_bib, timestamp, flag, estado) VALUES (?,?,?,?)""", query)
        conn.commit()

    else: 
        # Cámara no activa
        query = [(codigo_bib, formatted_timestamp, 'f', 1)]
        c.executemany("""INSERT INTO estado_camara (codigo_bib, timestamp, flag, estado) VALUES (?,?,?,?)""", query)
        conn.commit()

        query = [('ANT', formatted_timestamp, 'i', 0)]
        c.executemany("""INSERT INTO estado_camara (codigo_bib, timestamp, flag, estado) VALUES (?,?,?,?)""", query)
        conn.commit()

    conn.close()


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
    

def conexion(ip):
    try:
        # Delay, no sobrecargar la red de ping
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
    

def crear_cola_mensajes():
    credentials = pika.PlainCredentials(os.getenv("mq_user"),
                                        os.getenv("mq_password"))
    
    parameters = pika.ConnectionParameters(os.getenv("Ip_broker"),
                                           5672,
                                           '/',
                                           credentials)

    while True:
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.queue_declare(queue='BibliotecaUPCT')
            return channel
        except Exception as e:
            logging.error(f'********** Error al crear la cola rabbit **********')
            time.sleep(2)


def enviar_mensaje_cola(secuencia):
    global channel 
    try:
        hora_actual = datetime.now()
        mensaje = f'{int(os.getenv("Id_bib"))},{secuencia},{hora_actual.hour}:{hora_actual.minute}:{hora_actual.second}'
        logging.info(f'Mensaje enviado: {mensaje}')
        
        channel.basic_publish(exchange='',
                              routing_key='BibliotecaUPCT',
                              body=mensaje)
        
    except Exception as e:
        logging.error(f'********** Error al enviar mensaje **********')
        time.sleep(2)
        channel = crear_cola_mensajes()
        enviar_mensaje_cola(secuencia)



# =========================== Variables ========================== # 
# Variables de bot telegram
#telegram_bot = telebot.TeleBot(os.getenv("telegram_chat"))
#telegram_user_id = os.getenv("telegram_user_id")

# Path carpetas
path_imagenes = os.getenv("path_imagenes")  
# Variables del programa
frame_id = 0
secuencia_id = obtener_secuencia_del_dia(os.getenv("Codigo_bib"))
deteccion_anterior = False 

# Variable para controlar si se guarda la imagen actual
estado_grabacion_actual = False  


# Variables del sustractor CNT
area = int(os.getenv("area"))
k = int(os.getenv("k"))
cnt = cv2.bgsegm.createBackgroundSubtractorCNT(minPixelStability=10, 
                                                maxPixelStability=10*15)

# Kernels operaciones de postprocesado de imagenes
kernel_erosion = np.ones((3, 3), np.uint8)
kernel_dilatacion = np.ones((11, 11), np.uint8)

# Archivo logging
log_file_path = os.getenv("path_logging")   
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('pika').setLevel(logging.CRITICAL)

# =========================== Main Loop ========================== #
channel = crear_cola_mensajes()

while True:
        
    #Iniciamos captura y analisis de frames 
    if conexion(os.getenv("Ip_camara")):

        deteccion_anterior = False  
        estado_grabacion_actual = False  
        frame_id = 0
        cap = cv2.VideoCapture(os.getenv("RTSP_URL"))

        logging.info('Conexion con la camara')
        estado_camara_sqlite(os.getenv("Codigo_bib"), True)
        time.sleep(1)

        while cap.isOpened():

            status, frame = cap.read()

            if status:
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
                    enviar_mensaje_cola(secuencia_id)

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
                break
            
        cap.release()
        logging.warning('Desconexion con la camara')
        estado_camara_sqlite(os.getenv("Codigo_bib"), False)

