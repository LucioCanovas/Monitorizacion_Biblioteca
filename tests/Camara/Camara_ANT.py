import os
import cv2
import time
import pika
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
            logging.info(f'Ping a {ip} fallido')
            return False
        else:
            logging.info(f'Ping a {ip} exitoso. Tiempo de respuesta: {ping_camara} s')
            return True
    except Exception as e:
        logging.error(f'Error al realizar ping a {ip}: {e}')
        return False



# =========================== Variables ========================== # 
# Variables de bot telegram
telegram_bot = telebot.TeleBot(os.getenv("telegram_chat"))
telegram_user_id = os.getenv("telegram_user_id")

# Path carpetas
path_imagenes = os.getenv("path_imagenes")  

# Variables del programa
frame_id = 0
secuencia_id = 256
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

# Variables cola mq-rabbit


# Archivo logging
log_file_path = os.getenv("path_logging")   
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('pika').setLevel(logging.ERROR)

# =========================== Main Loop ========================== #
cont_status = 0

while True:
    
    #Iniciamos captura y analisis de frames 
    if conexion(os.getenv("Ip_camara")):

        deteccion_anterior = False  
        estado_grabacion_actual = False  
        frame_id = 0
        cap = cv2.VideoCapture(os.getenv("RTSP_URL"))
        print('Conexión cámara')

        logging.info('Conexión con la cámara')
        time.sleep(3)
        num_frames = 0
        t_init = time.time()
        while cap.isOpened():
            ti = time.time()
            status, frame = cap.read()
            tl = time.time()
            num_frames+=1
            logging.info(f'Leer frame: {num_frames}, tiempo: {(tl - ti)*1000}, ti: {ti}, tl: {tl}, media: {(t_init - tl)*1000/num_frames}')


            if status:
                cont_status = 0

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
                    print(f'Secuencia: {secuencia_id}')

                # Actualiza la detección anterior
                deteccion_anterior = deteccion

                if estado_grabacion_actual:
                    nombre_imagen = 'sc{:05d}_f_{:05d}.jpg'.format(secuencia_id, 
                                                                    frame_id)
                    cv2.imwrite(path_imagenes  + '/' + nombre_imagen, frame)

                frame_id += 1
                tp = time.time()
                logging.info(f'Procesar frame: {num_frames}, tiempo: {(tp - tl)*1000}, tl: {tl}, tp: {tp}')
            #Error en la conexion de la cámara   
            else:
                te = time.time()
                logging.info(f'Error frame: {num_frames}, tiempo: {(te - tl)*1000}, tl: {tl}, tp: {te}')
                logging.info(f'Error en el frame, {cont_status}, num_frames: {num_frames}')
                print(f'Fallo frame: {cont_status}')
                cont_status += 1
                if cont_status == 15:
                    cont_status = 0
                    break
        
        cap.release()
        logging.warning('Desconexión con la cámara')
        print('Fallo cámara')