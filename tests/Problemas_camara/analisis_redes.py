import time
import logging
from wifi import Cell, Scheme

# Configurar el módulo logging
logging.basicConfig(filename='registro_redes_portatil.log', level=logging.INFO, format='%(asctime)s - %(message)s')

def escanear_redes_wifi(interfaz):
    # Obtener la marca temporal actual
    marca_temporal = time.strftime('%Y-%m-%d %H:%M:%S')

    # Realizar el escaneo de las redes WiFi disponibles en la interfaz especificada
    redes_encontradas = Cell.all(interfaz)

    # Registrar la marca temporal
    logging.info(f"**********  Marca temporal: {marca_temporal}  **********")

    # Registrar información sobre cada red encontrada
    for red in redes_encontradas:
        logging.info(f"SSID: {red.ssid}")
        logging.info(f"BSSID: {red.address}")
        logging.info(f"Canal: {red.channel}")
        logging.info(f"Intensidad de señal: {red.signal}")
        logging.info(f"Calidad de la señal: {red.quality}")
        logging.info("------------------------------")

def tarea_cada_5_segundos():
    interfaz = '[00000003] Intel(R) Wireless-AC 9560 160MHz' 
    escanear_redes_wifi(interfaz)
    time.sleep(1)  # Esperar 5 segundos antes de realizar el siguiente escaneo


if __name__ == "__main__":
    tarea_cada_5_segundos()


