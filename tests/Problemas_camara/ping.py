import ping3
import time
import logging

ip = '192.168.102.120'

   
logging.basicConfig(filename='registro_ping.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def conexion(ip):
    try:
        # Delay, no sobrecargar la red de ping
        ping_camara = ping3.ping(ip, timeout=8)
        if ping_camara is None or ping_camara is False:
            logging.info(f'Ping a {ip} fallido, {ping_camara}')
            return False
        else:
            logging.info(f'Ping a {ip} exitoso. Tiempo de respuesta: {ping_camara} s')
            time.sleep(1)
            return True
    except Exception as e:
        logging.error(f'Error al realizar ping a {ip}: {e}')
        return False
    
while True:
    conexion(ip)
        