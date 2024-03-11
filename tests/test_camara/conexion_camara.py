import os
import subprocess
import time
import cv2
import psutil
from scapy.all import *
import time
from dotenv import load_dotenv


# Cargar variables de entorno desde el archivo .env
load_dotenv()

def medir_retardo_paquetes(ip_destino, num_paquetes=10):
    # Inicializar lista para almacenar los retardos de los paquetes
    retardos = []

    for _ in range(num_paquetes):
        # Enviar paquete UDP al destino
        inicio_envio = time.time()
        respuesta = sr1(IP(dst=ip_destino)/UDP(dport=12345)/b'ping', timeout=1, verbose=False)
        fin_envio = time.time()

        if respuesta:
            # Calcular retardo en milisegundos
            retardo_ms = (fin_envio - inicio_envio) * 1000
            retardos.append(retardo_ms)
            print(f'Retardo de paquete hacia {ip_destino}: {retardo_ms:.2f} ms')
        else:
            print(f'No se recibió respuesta de {ip_destino}.')

    # Calcular y mostrar estadísticas de los retardos
    if retardos:
        promedio_retardos = sum(retardos) / len(retardos)
        maximo_retardo = max(retardos)
        minimo_retardo = min(retardos)
        print(f'Estadísticas de retardo:')
        print(f'  Promedio: {promedio_retardos:.2f} ms')
        print(f'  Máximo: {maximo_retardo:.2f} ms')
        print(f'  Mínimo: {minimo_retardo:.2f} ms')

def medir_fps(ip_camara):
    cap = cv2.VideoCapture(ip_camara)  # Abrir transmisión de la cámara IP
    start_time = time.time()
    frame_count = 0
    
    while time.time() - start_time < 60:  # Limitar la medición a 60 segundos
        ret, frame = cap.read()  # Leer fotograma
        if not ret:
            break
        
        frame_count += 1
    
    end_time = time.time()
    tiempo_transcurrido = end_time - start_time
    fps = frame_count / tiempo_transcurrido
    
    cap.release()
    cv2.destroyAllWindows()
    
    print(f'FPS de la cámara IP ({ip_camara}): {fps}')

def medir_perdida_paquetes(ip_destino):
    # Realizar un ping y medir la pérdida de paquetes
    resultado_ping = subprocess.run(['ping', '-c', '10', ip_destino], stdout=subprocess.PIPE)
    if resultado_ping.returncode == 0:
        perdida_paquetes = float(resultado_ping.stdout.decode().split("\n")[-2].split()[6].strip('%'))
        print(f'Pérdida de paquetes hacia {ip_destino}: {perdida_paquetes}%')
    else:
        print(f'Error al realizar ping a {ip_destino}.')

def medir_ancho_de_banda():
    # Obtener estadísticas de uso de ancho de banda
    network_io = psutil.net_io_counters()
    bytes_enviados = network_io.bytes_sent
    bytes_recibidos = network_io.bytes_recv

    print(f'Bytes enviados: {bytes_enviados} bytes')
    print(f'Bytes recibidos: {bytes_recibidos} bytes')

# Dirección IP de la cámara IP
ip_camara = os.getenv('IP_Camara')

# Llamadas a las funciones de medición
print(f'Iniciando pruebas de conexión a la IP: {ip_camara}')

print(f'Prueba de retardo')
medir_retardo_paquetes(ip_camara)

print(f'Midiendo FPS')
medir_fps(os.getenv('RTSP_URL'))

print(f'Prueba de perdida de paquetes')
medir_perdida_paquetes(ip_camara)

print(f'Midiendo ancho de banda')
medir_ancho_de_banda()






