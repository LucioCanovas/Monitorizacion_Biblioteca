import os
import cv2
import time
import ping3
import telebot
import logging
import sqlite3
import datetime
import numpy as np
from datetime import datetime
from dotenv import load_dotenv


# Cargar variables de entorno desde el archivo .env
load_dotenv()



def estado_camara_sqlite(codigo_bib, estado):
    try:
        nombre_base_de_datos = os.getenv("path_bbdd")
        # Obtener la fecha actual
        timestamp = datetime.now()
        formatted_timestamp = timestamp.strftime('%Y-%m-%d %H:%M:%S')
        
        # Conectar a la base de datos SQLite
        conn = sqlite3.connect(nombre_base_de_datos)
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS camara_conexion
                    (codigo_bib TEXT, timestamp TEXT, flag TEXT, estado INTEGER)""")
        conn.commit()

        query = [(codigo_bib, formatted_timestamp, 'f', int(not estado))]
        c.executemany("""INSERT INTO camara_conexion (codigo_bib, timestamp, flag, estado) VALUES (?,?,?,?)""", query)
        query = [('ANT', formatted_timestamp, 'i', int(estado))]
        c.executemany("""INSERT INTO camara_conexion (codigo_bib, timestamp, flag, estado) VALUES (?,?,?,?)""", query)
        conn.commit()
        conn.close()
    except Exception as e:
        logging.error(f'Error al registrar estado de la cámara en la base de datos: {str(e)}')


def conexion(ip):
    try:
        # Delay, no sobrecargar la red de ping
        time.sleep(5)
        ping_camara = ping3.ping(ip)
        if ping_camara is None or not ping_camara:
            logging.info(f'Ping: {ip}, fallido')
            return False
        else:
            logging.info(f'Ping: {ip}, éxito')
            return True
    except Exception as e:
        logging.error(f'Error al realizar ping a la cámara: {str(e)}')
        return False



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
    



# =========================== Variables ========================== # 
# Variables de bot telegram
telegram_bot = telebot.TeleBot(os.getenv("telegram_chat"))
telegram_user_id = os.getenv("telegram_user_id")

# Path carpetas
path_imagenes = os.getenv("path_imagenes")  

# Variables del programa
frame_id = 0
secuencia_id = 0
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
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# =========================== Main Loop ========================== #

while True:
    
    #Iniciamos captura y analisis de frames 
    if conexion(os.getenv("Ip_camara")):

        deteccion_anterior = False  
        estado_grabacion_actual = False  
        frame_id = 0
        cap = cv2.VideoCapture(os.getenv("RTSP_URL"))

        logging.info('Conexión con la cámara')
        estado_camara_sqlite(os.getenv("Codigo_bib"), True)
        
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
                    print(f'Secuencia:{secuencia_id}')

                # Actualiza la detección anterior
                deteccion_anterior = deteccion

                if estado_grabacion_actual:
                    nombre_imagen = 'sc{:05d}_f_{:05d}.jpg'.format(secuencia_id, 
                                                                    frame_id)
                    cv2.imwrite(path_imagenes  + '/' + nombre_imagen, frame)

                frame_id += 1

            #Error en la conexion de la cámara   
            else:
                print('Error en el frame')
                break
        
        cap.release()
        logging.info('Desconexión del flujo RTSP')
        print('Desconexión del flujo RTSP')
        estado_camara_sqlite(os.getenv("Codigo_bib"), False)