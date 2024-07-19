import os
import cv2
import csv
import glob
import math
import time
import pika
import torch
import shutil
import random
import zipfile
import cProfile
import pstats
import logging
import tracking as tr
import mysql.connector
from datetime import datetime, timedelta
from dotenv import load_dotenv


# Cargar variables de entorno desde el archivo .env
load_dotenv()

def descifrar_mensaje(body):
    mensaje = body.decode('utf-8') 

    biblioteca_id = int(mensaje.split(",")[0])
    secuencia_id = int(mensaje.split(",")[1])
    timestamp = str(mensaje.split(",")[2])

    logging.debug(f'Mensaje recibido y descifrado: {biblioteca_id}, {secuencia_id}, {timestamp}')

    timestamp_datetime = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
 
    return biblioteca_id, secuencia_id, timestamp_datetime

def procesar_secuencia(codigo_bib, secuencia_id, biblioteca_id):
    global array_aforo

    path_imagen = f'/app/Compartida/{codigo_bib}/Imagenes/'
    #path_imagen_test = f'/app/Compartida/{codigo_bib}/test/'
    
    # Obtenemos el número de frames de la secuencia_id
    secuencia = 'sc%05d' %secuencia_id
    longitud = len([file for file in os.listdir(path_imagen) if secuencia in file]) 

    # Reiniciamos las variables
    lista_objetos_rastreados = {}
    contador_in = 0
    contador_out = 0

    grado_0 = 0
    grado_1 = 0
    grado_2 = 0
    grado_3 = 0
    grado_4 = 0

    # Detectamos y trackeamos las personas de la secuencia
    for x in range(0,longitud):
        nombre_frame = secuencia + '_f_%05d.jpg' %x
        frame = cv2.imread(path_imagen + nombre_frame)
        num_personas, array_centroides, grado = contadorPersonas(frame)

        # A cada frame le asignamos su grado
        if grado == 0:
            grado_0 += 1
        elif grado == 1:
            grado_1 += 1
        elif grado == 2:
            grado_2 += 1
        elif grado == 3:
            grado_3 += 1
        elif grado == 4:
            grado_4 += 1

        if num_personas != 0:
            lista_objetos_rastreados, contador_in, contador_out = tr.tracking(lista_objetos_rastreados, 
                                                                              array_centroides, 
                                                                              contador_in, 
                                                                              contador_out)
    
            
    # Actualizamos el aforo 
    array_aforo[biblioteca_id] += (contador_in - contador_out)
    patron = 'sc%05d_*.jpg' %secuencia_id
    eliminar_imagenes(path_imagen, patron)
    
    return array_aforo, contador_in, contador_out, grado_0, grado_1, grado_2, grado_3, grado_4

def contadorPersonas(frame):
    global modelo_deteccion
    
    detect = modelo_deteccion(frame)
    info = detect.pandas().xyxy[0]
    detecciones = (info.shape)[0]

    num_personas = 0
    array_centroide = []
    array_box = []
    
    for i in range(0, detecciones):
        confidence = info.loc[i]['confidence']
        if confidence > 0.3:
            num_personas += 1
            array_puntos = []

            info_persona = info.loc[i]
            (x,y) = (int(info_persona['xmin']), int(info_persona['ymin']))
            (xmax, ymax) = (int(info_persona['xmax']), int(info_persona['ymax']))
            centroide = (int(x+((xmax-x)/2)), int(y+((ymax-y)/2)))

            array_centroide.append(centroide)
            array_puntos.append(x)
            array_puntos.append(y)
            array_puntos.append(xmax)
            array_puntos.append(ymax)
            array_box.append(array_puntos)
            
    grado = calcular_grado(num_personas, array_centroide, array_box)
                
    return num_personas, array_centroide, grado

def crear_cola_mensajes(usuario, contraseña, ip_broker, cola):
    credentials = pika.PlainCredentials(usuario,
                                        contraseña)
    
    parameters = pika.ConnectionParameters(ip_broker,
                                           5672,
                                           '/',
                                           credentials)

    try:
        connection = pika.BlockingConnection(parameters)
        canal = connection.channel()
        canal.queue_declare(queue=cola)
        logging.info('Cola rabbit creada')
        return canal, connection
    
    except Exception as e:
            logging.error(f'********** Error al crear la cola rabbit **********')
            logging.error(e)
            time.sleep(1)

def callback(ch, method, properties, body):
    global array_aforo, connection, canal, final, cont_cierre
    try:
        biblioteca_id, secuencia_id, timestamp = descifrar_mensaje(body)
        if secuencia_id == -1:  #Cierre de biblioteca_id
            diccionario_biblioteca_estado[biblioteca_id] = secuencia_id
            cerrar_detector = True
            for id in diccionario_biblioteca_estado:
                estado = diccionario_biblioteca_estado[id]
                if estado == 0: cerrar_detector = False
            if cerrar_detector:
                final = True
                canal.close()
                connection.close()

        elif secuencia_id == 0: #Inicio de biblioteca_id
            diccionario_biblioteca_estado[biblioteca_id] = secuencia_id

        else:   # Secuencia normal de biblioteca_id   
            ultima_sec_analizada = array_secuencias[biblioteca_id]
            

            for secuencia in range(ultima_sec_analizada+1, secuencia_id+1):
                codigo_bib = diccionario_biblioteca[biblioteca_id]
                array_aforo, personas_in, personas_out, grado_0, grado_1, grado_2, grado_3, grado_4 = procesar_secuencia(codigo_bib, 
                                                                                                                    secuencia,
                                                                                                                    biblioteca_id)

                insertar_secuencia(codigo_bib,
                                biblioteca_id,
                                secuencia,
                                timestamp,
                                personas_in,
                                personas_out,
                                array_aforo, 
                                grado_0, 
                                grado_1, 
                                grado_2, 
                                grado_3, 
                                grado_4)
                    
            array_secuencias[biblioteca_id] = secuencia_id


    except Exception as e:
        logging.error(f'********** Error en el callback, al intentar procesar mensaje **********')
        logging.error(e)
        time.sleep(1)

        # Intenta reconectar 
        if canal.is_open:
            canal.close()
            connection.close()
 
        canal, connection = crear_cola_mensajes(usuario, contraseña, ip_broker,  'BibliotecaUPCT')
        canal.basic_consume(queue='BibliotecaUPCT',
                              on_message_callback=callback,
                              auto_ack=True)
        consume_messages()

def consume_messages():
    global connection, canal, final

    while True:
        try:
            canal.start_consuming()
        except Exception as e:
            logging.error(f'********** Error al consumir mensaje *********')
            logging.error(e)

            #Cierra la conexión con RabbitMQ
            if canal.is_open:   
                canal.close()
                connection.close()

            # Si no es el final de las detecciones volvemos a crear la cola RabbitMQ
            if not final:
                canal, connection = crear_cola_mensajes(usuario, contraseña, ip_broker,  'BibliotecaUPCT')
                canal.basic_consume(queue='BibliotecaUPCT',
                                      on_message_callback=callback,
                                      auto_ack=True)
            else:
                break

def obtener_arrayAforo_arraySecuencias(diccionario_biblioteca):

        try: 
            # Conexión a la base de datos
            connection = mysql.connector.connect(
                host="BaseDatos_bibliotecas",
                user="root",
                password="",
                database="base_datos_bibliotecas"
            )
            cursor = connection.cursor()

            fecha_actual = datetime.now().date()

            # Inicializar arrays para secuencias y aforos
            secuencias = []
            aforos = []

            for i in range(len(diccionario_biblioteca)): 
                codigo_bib = diccionario_biblioteca[i]
                
                # Obtener la última secuencia y aforo para cada biblioteca
                cursor.execute("""
                    SELECT IFNULL(secuencia, 0) as ultima_secuencia, IFNULL(aforo, 0) as ultimo_aforo
                    FROM aforo_biblioteca
                    WHERE fecha = %s AND codigo_bib = %s
                    ORDER BY secuencia DESC
                    LIMIT 1
                """, (fecha_actual, codigo_bib,))

                # Recorrer resultados
                rows = cursor.fetchall()
                if not rows:  # Si no se encontraron filas
                    secuencias.append(0)
                    aforos.append(0)
                else:
                    for row in rows:
                        ultima_secuencia, ultimo_aforo = row
                        secuencias.append(ultima_secuencia)
                        aforos.append(ultimo_aforo)

            connection.close()

        except Exception as e:
            logging.error(f'Error en BBDD, funcion: obtener_arrayAforo_arraySecuencias, error: {e}')
            if connection.is_connected():
                connection.close()

        finally:
            if connection.is_connected():
                connection.close()

        return secuencias, aforos

def calcular_grado(num_personas, array_centroide, array_box):
    if num_personas == 0:
        return 0
    elif num_personas == 1:
        return 1
    elif num_personas == 2 or num_personas == 3:
        superposicion = calcular_superposicion(array_box)
        distancia = calculo_distancia(array_centroide)
        if superposicion == True or distancia == True:
            return 3
        return 2
    else:
        return 4
    
def calculo_distancia(array_centroide):
     for c1 in array_centroide:
         for c2 in array_centroide:
             x1, x2, y1, y2 = (c1[0], c2[0], c1[1], c2[1])
             distancia = math.sqrt((x2-x1)**2+(y2-y1)**2)
             if distancia > 0 and distancia < 250: return True 
     return False

def calcular_superposicion(array_box):
    for puntos in array_box:
        punto_1 = (puntos[0], puntos[3])
        punto_2 = (puntos[0], puntos[1])
        punto_3 = (puntos[2], puntos[1])
        punto_4 = (puntos[2], puntos[3])     
        for box in array_box:
            xmin_box = box[0]
            ymin_box = box[1]
            xmax_box = box[2]
            ymax_box = box[3]
            if (punto_1[0] < xmax_box) and (punto_1[0] > xmin_box) and (punto_1[1] < ymax_box) and (punto_1[1] > ymin_box): return True
            if (punto_2[0] < xmax_box) and (punto_2[0] > xmin_box) and (punto_2[1] < ymax_box) and (punto_2[1] > ymin_box): return True
            if (punto_3[0] < xmax_box) and (punto_3[0] > xmin_box) and (punto_3[1] < ymax_box) and (punto_3[1] > ymin_box): return True
            if (punto_4[0] < xmax_box) and (punto_4[0] > xmin_box) and (punto_4[1] < ymax_box) and (punto_4[1] > ymin_box): return True
    
    return False

def almacenar_con_probabilidad(patron, directorio_destino, directorio_origen):
    # Crear el directorio de destino si no existe
    if not os.path.exists(directorio_destino):
        os.makedirs(directorio_destino)

    # Generar un número aleatorio entre 0 y 1
    probabilidad = random.uniform(0, 1)

    # Verificar si se cumple la probabilidad del 5%
    if probabilidad < float(os.getenv('probabilidad')):
        # Almacenar imágenes con patrones dados desde el directorio de origen al de destino
        archivos_coincidentes = glob.glob(os.path.join(directorio_origen, patron))
        for archivo in archivos_coincidentes:
            nombre_archivo = os.path.basename(archivo)
            shutil.copy(archivo, os.path.join(directorio_destino, nombre_archivo))
        return True
    return False

def comprimir_imagenes_en_ruta(ruta, codigo_bib):
    # Obtener la fecha de hoy
    fecha_hoy = datetime.now().date()
    fecha_formateada = fecha_hoy.strftime('%Y-%m-%d')

    # Nombre del archivo ZIP basado en la fecha de hoy
    nombre_archivo_zip = f"{codigo_bib}_{fecha_formateada}.zip"
    ruta_zip = os.path.join(ruta, nombre_archivo_zip)

    # Comprobar si hay archivos .jpg en la ruta
    imagenes = [archivo for archivo in os.listdir(ruta) if archivo.lower().endswith('.jpg')]

    if imagenes:
        # Crear un objeto ZipFile en modo escritura
        with zipfile.ZipFile(ruta_zip, 'w') as archivo_zip:
            # Comprimir cada imagen en el archivo zip
            for imagen in imagenes:
                archivo_completo = os.path.join(ruta, imagen)
                archivo_zip.write(archivo_completo, imagen)
        
        logging.info(f"Se han comprimido las imágenes en '{ruta}' en '{nombre_archivo_zip}'")
    else:
        logging.error(f"No se encontraron imágenes en '{ruta}'")

def insertar_secuencia(codigo_bib, biblioteca_id, secuencia_id, timestamp_inicio, personas_in, personas_out, array_aforo, grado_0, grado_1, grado_2, grado_3, grado_4):
    try: 
        # Conexión a la base de datos
        connection = mysql.connector.connect(
                host="BaseDatos_bibliotecas",
                user="root",
                password="",
                database="base_datos_bibliotecas"
        )
        cursor = connection.cursor()

        timestamp = datetime.now()
        fecha = timestamp.date()

        hora_inicio_delta = timedelta(
                                hours=timestamp_inicio.hour,
                                minutes=timestamp_inicio.minute,
                                seconds=timestamp_inicio.second)
        
        hora_fin_delta = timedelta(
                                hours=timestamp.hour,
                                minutes=timestamp.minute,
                                seconds=timestamp.second)      

        delay =  hora_fin_delta - hora_inicio_delta 


        aforo = array_aforo[biblioteca_id]
            
        query = [(codigo_bib, timestamp_inicio, fecha, secuencia_id, hora_inicio_delta, delay, personas_in, personas_out, aforo, grado_0, grado_1, grado_2, grado_3, grado_4)]
        cursor.executemany("""INSERT INTO aforo_biblioteca (codigo_bib, timestamp, fecha, secuencia, hora, delay, personas_in, personas_out, aforo, grado_0, grado_1, grado_2, grado_3, grado_4) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", query)

        connection.commit()
        connection.close()

    except Exception as e:
        logging.error(f'Error al añdir una nueva fila en BBDD, función: insertar_secuencia, error: {e}')
        if connection.is_connected():
                connection.close()

def guardar_en_csv(secuencia_id, contador_in, contador_out, codigo_bib):
    # Definir el nombre del archivo CSV
    nombre_archivo = f'/app/Compartida/{codigo_bib}/test/datos.csv'

    # Abrir el archivo en modo de escritura, si no existe, se creará automáticamente
    with open(nombre_archivo, mode='a', newline='') as archivo_csv:
        # Definir los nombres de las columnas
        nombres_columnas = ['secuencia', 'personas_in', 'personas_out']
        escritor_csv = csv.DictWriter(archivo_csv, fieldnames=nombres_columnas)

        # Si el archivo está vacío, escribir los nombres de las columnas
        if archivo_csv.tell() == 0:
            escritor_csv.writeheader()

        # Escribir la información en el archivo CSV
        escritor_csv.writerow({'secuencia': secuencia_id, 'personas_in': contador_in, 'personas_out': contador_out})

def eliminar_imagenes(directorio, patron='*.jpg'):
    # Ruta del directorio
    ruta_directorio = os.path.abspath(directorio)

    # Patrón de búsqueda para archivos de imagen
    patron_imagenes = os.path.join(ruta_directorio, patron)  

    # Obtener la lista de archivos de imagen
    archivos_imagen = glob.glob(patron_imagenes)

    # Eliminar cada archivo
    for archivo in archivos_imagen:
        os.remove(archivo)


# Variables cola mq-rabbit
ip_broker = os.getenv("Ip_broker")
usuario = os.getenv("mq_user")
contraseña = os.getenv("mq_password")
final = False
cont_cierre = 0

modelo_deteccion = torch.hub.load('ultralytics/yolov5','custom',path='/app/Compartida/Detector/modelo_v5.pt')

# Archivo logging
log_file_path = os.getenv("path_logging")
fecha_hoy = datetime.now().date()
fecha_formateada = fecha_hoy.strftime('%Y-%m-%d')

ruta = f'{log_file_path}/log_detector_{fecha_formateada}.log'   
logging.basicConfig(filename=ruta, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('pika').setLevel(logging.CRITICAL)

logging.info(f'----------   Detector iniciado   ----------')

# Variables detector+tracking
diccionario_biblioteca = {0: 'ANT', 1: 'CIM', 2: 'ALF'}
diccionario_biblioteca_estado = {0: -1, 1: -1, 2: -1} #codigo_bib : estado (abierto = 0, cerrado = -1)
array_secuencias, array_aforo = obtener_arrayAforo_arraySecuencias(diccionario_biblioteca)
logging.debug(f'Secuencias: {array_secuencias}')

with cProfile.Profile() as profile:

    canal, connection= crear_cola_mensajes(usuario, contraseña, ip_broker, 'BibliotecaUPCT')
    canal.queue_purge('BibliotecaUPCT')
    canal.basic_consume(queue='BibliotecaUPCT',
                        on_message_callback=callback,
                        auto_ack=True)

    # Consumir mensajes hasta final del día
    consume_messages()


#Comprimir las imagenes para Transfer learning una vez cierra biblioteca
for clave, valor in diccionario_biblioteca.items():
    codigo_bib = valor
    ruta_secuencias = f'/app/Compartida/{codigo_bib}/test/'
    comprimir_imagenes_en_ruta(ruta_secuencias, codigo_bib)
    eliminar_imagenes(ruta_secuencias, patron='*.jpg')

results = pstats.Stats(profile)
results.sort_stats(pstats.SortKey.TIME)
logging.info('********** Stats del detector **********')
logging.info(f'{results.print_stats()}')
results.dump_stats(f"profile_detector_{fecha_formateada}.prof")

    