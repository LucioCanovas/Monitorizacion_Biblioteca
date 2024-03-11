import os
import cv2
import pika
import glob
import time
import math
import torch
import cProfile
import pstats
import shutil
import random
import sqlite3
import logging
import datetime
import tracking as tr
from datetime import datetime
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
load_dotenv()


def descifrar_mensaje(body):
    mensaje = body.decode('utf-8') 

    biblioteca_id = int(mensaje.split(",")[0])
    secuencia_id = int(mensaje.split(",")[1])
    hora_inicio = str(mensaje.split(",")[2])
    logging.info(f'Mensaje recibido y descifrado: {biblioteca_id}, {secuencia_id}, {hora_inicio}')
 
    return biblioteca_id, secuencia_id, hora_inicio


def obtener_aforo_secuencias():

    # Conexión a la base de datos SQLite3 (asegúrate de tener el archivo de base de datos correcto)
    db_path = os.getenv("path_bbdd")
    connection = sqlite3.connect(db_path)
    cursor = connection.cursor()

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

    connection.commit()

    # Fecha actual
    fecha_actual_str = datetime.now().strftime('%Y-%m-%d')

    # Inicializar arrays para secuencias y aforos
    secuencias = []
    aforos = []
    try:
        for i in range(0,3): 
            codigo_bib = diccionario_biblioteca[i]
        
            # Obtener la última secuencia y aforo para cada biblioteca
            cursor.execute("""
                SELECT COALESCE(MAX(secuencia), 0) as ultima_secuencia, COALESCE((aforo), 0) as ultimo_aforo
                FROM Aforo
                WHERE fecha = ? AND codigo_bib = ?
            """, (fecha_actual_str,codigo_bib,))

            # Recorrer resultados
            for row in cursor.fetchall():
                ultima_secuencia, ultimo_aforo = row
                secuencias.append(ultima_secuencia)
                aforos.append(ultimo_aforo)

    except sqlite3.Error as e:
        logging.error(f'Error en BBDD, al intentar obtener el aforo secuencia')

    finally:
        # Cerrar conexión
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
 

def contadorPersonas(frame):
    
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


def almacenar_con_probabilidad(patron, directorio_destino, directorio_origen):
    # Crear el directorio de destino si no existe
    if not os.path.exists(directorio_destino):
        os.makedirs(directorio_destino)

    # Generar un número aleatorio entre 0 y 1
    probabilidad = random.uniform(0, 1)

    # Verificar si se cumple la probabilidad del 5%
    if probabilidad < 0:
        # Almacenar imágenes con patrones dados desde el directorio de origen al de destino
        archivos_coincidentes = glob.glob(os.path.join(directorio_origen, patron))
        for archivo in archivos_coincidentes:
            nombre_archivo = os.path.basename(archivo)
            shutil.copy(archivo, os.path.join(directorio_destino, nombre_archivo))
    

def procesar_secuencia(codigo_bib, secuencia_id, biblioteca_id):
    global array_aforo

    path_imagen = f'/app/Compartida/{codigo_bib}/Imagenes/'
    #path_imagen_test = f'/app/Compartida/{codigo_bib}/test/'

    secuencia = 'sc%05d' %secuencia_id
    longitud = len([file for file in os.listdir(path_imagen) if secuencia in file]) 

    lista_objetos_rastreados = {}
    contador_in = 0
    contador_out = 0

    grado_0 = 0
    grado_1 = 0
    grado_2 = 0
    grado_3 = 0
    grado_4 = 0

    for x in range(0,longitud):
        nombre_frame = secuencia + '_f_%05d.jpg' %x
        frame = cv2.imread(path_imagen + nombre_frame)
        num_personas, array_centroides, grado = contadorPersonas(frame)

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
                                                                              array_centroides, contador_in, 
                                                                              contador_out)
    
            
    
    array_aforo[biblioteca_id] += (contador_in - contador_out)
    patron = 'sc%05d_*.jpg' %secuencia_id
    #almacenar_con_probabilidad(patron, path_imagen_test, path_imagen)
    eliminar_imagenes(path_imagen, patron)
    
    return array_aforo, contador_in, contador_out, grado_0, grado_1, grado_2, grado_3, grado_4


def añadir_fila_BBDD(codigo_bib, biblioteca_id, secuencia_id, hora_inicio, personas_in, personas_out, array_aforo, grado_0, grado_1, grado_2, grado_3, grado_4):
    try:
        conn = sqlite3.connect(os.getenv("path_bbdd"))
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS Aforo
            (codigo_bib TEXT,timestamp TEXT, fecha TEXT, secuencia INTEGER, Hora TEXT,Hora_final TEXT, personas_in INTEGER, personas_out INTEGER, aforo INTEGER, grado_0 INTEGER, grado_1 INTEGER, grado_2 INTEGER, grado_3 INTEGER, grado_4 INTEGER)""")

        conn.commit()

        
        hora = datetime.now()
        hora_final = hora.strftime('%H:%M:%S')
        hora_obj = datetime.strptime(hora_inicio, '%H:%M:%S')
        hora_formateada_str = hora_obj.strftime('%H:%M:%S')

        fecha = hora.strftime("%Y-%m-%d")
        timestamp = f'{fecha} {hora_formateada_str}'
        aforo = array_aforo[biblioteca_id]
            
        query = [(codigo_bib, timestamp, fecha, secuencia_id, hora_formateada_str,hora_final, personas_in, personas_out, aforo, grado_0, grado_1, grado_2, grado_3, grado_4)]
        logging.debug(f'Query: {query}')
        c.executemany("""INSERT INTO Aforo (codigo_bib, timestamp, fecha, secuencia, Hora, Hora_final, personas_in, personas_out, aforo, grado_0, grado_1, grado_2, grado_3, grado_4) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", query)

        conn.commit()
        conn.close()

    except sqlite3.Error as e:
        logging.error(f'********** Error en BBDD, al intentar añadir una nueva fila **********')


#============================   Cola de mensajes    ==============================#
def crear_cola_mensajes(ip_broker):
    credentials = pika.PlainCredentials(os.getenv("mq_user"),
                                        os.getenv("mq_password"))
    
    parameters = pika.ConnectionParameters(ip_broker, 5672, '/', credentials)

    while True:
        try:
            connection = pika.BlockingConnection(parameters)
            channel = connection.channel()
            channel.queue_declare(queue='BibliotecaUPCT')
            channel.queue_purge(queue='BibliotecaUPCT')
            logging.info(f'Cola mensajes creada')
            return channel, connection
        
        except pika.exceptions.AMQPConnectionError as e:
            logging.error(f'********* Error al crear cola rabbit **********')
            time.sleep(1)


def callback(ch, method, properties, body):
    global array_aforo, connection, channel, final
    try:
        biblioteca_id, secuencia_id, hora_inicio = descifrar_mensaje(body)
        if secuencia_id == 0:
            final = True
            channel.close()
            connection.close()
            
        ultima_sec_analizada = array_secuencias[biblioteca_id]
        

        for secuencia in range(ultima_sec_analizada+1, secuencia_id+1):
            codigo_bib = diccionario_biblioteca[biblioteca_id]
            array_aforo, personas_in, personas_out, grado_0, grado_1, grado_2, grado_3, grado_4 = procesar_secuencia(codigo_bib, 
                                                                                                                   secuencia,
                                                                                                                   biblioteca_id)

            añadir_fila_BBDD(codigo_bib,
                             biblioteca_id,
                             secuencia,
                             hora_inicio,
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
        time.sleep(1)

        # Intenta reconectar y reenviar el mensaje
        if channel.is_open:
            channel.close()
            connection.close()
 
        channel, connection = crear_cola_mensajes(ip_broker)
        channel.basic_consume(queue='BibliotecaUPCT',
                              on_message_callback=callback,
                              auto_ack=True)
        consume_messages()


def consume_messages():
    global connection, channel, final

    while True:
        try:
            channel.start_consuming()
        except Exception as e:
            logging.error(f'********** Error al consumir mensaje *********')

            #Cierra la conexión con RabbitMQ
            if channel.is_open:   
                channel.close()
                connection.close()
                time.sleep(1)

            # Volvemos a crear la cola RabbitMQ
            if not final:
                channel, connection = crear_cola_mensajes(ip_broker)
                channel.basic_consume(queue='BibliotecaUPCT',
                                      on_message_callback=callback,
                                      auto_ack=True)
            else:
                break



# Variables cola mq-rabbit
ip_broker = os.getenv("Ip_broker")
final = False
modelo_deteccion = torch.hub.load('ultralytics/yolov5','custom',path='/app/Compartida/Detector/modelo_v5.pt')

# Configuración del registro para escribir en un archivo
log_file_path = os.getenv("path_logging")   
logging.basicConfig(filename=log_file_path, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.getLogger('pika').setLevel(logging.CRITICAL)
logging.info(f'----------   Detector iniciado   ----------')

# Variables detector+tracking
diccionario_biblioteca = {0: 'ANT', 1: 'CIM', 2: 'ALF'}
array_secuencias, array_aforo = obtener_aforo_secuencias()
logging.debug(f'Secuencias: {array_secuencias}')

with cProfile.Profile() as profile:

    channel, connection = crear_cola_mensajes(ip_broker)
    channel.basic_consume(queue='BibliotecaUPCT',
                        on_message_callback=callback,
                        auto_ack=True)

    # Start consuming messages
    consume_messages()

results = pstats.Stats(profile)
results.sort_stats(pstats.SortKey.TIME)
logging.info('********** Stats del detector **********')
logging.info(f'{results.print_stats()}')
results.dump_stats("profile_detector.prof")

    