import os
import logging
import pandas as pd
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Cargar variables de entorno desde el archivo .env
load_dotenv()

def calcular_hora_final(hora_inicio, intervalo_str): 
    # Convertir el intervalo a un objeto timedelta
    intervalo = timedelta(seconds=sum(x * int(t) for x, t in zip([3600, 60, 1], map(int, intervalo_str.split(':')))))

    # Calcular la hora final sumando el intervalo a la hora de inicio
    hora_final = hora_inicio + intervalo

    return hora_final

def deltatime_to_timehour(delta):
    # Calcular las horas, minutos y segundos
    horas = delta // timedelta(hours=1)
    minutos = (delta - timedelta(hours=horas)) // timedelta(minutes=1)
    segundos = (delta - timedelta(hours=horas, minutes=minutos)).seconds

    # Formatear el tiempo como una cadena
    cadena_tiempo = "{:02}:{:02}:{:02}".format(horas, minutos, segundos)
    return cadena_tiempo

def obtener_resumen(codigo_bib, fecha, hora_inicio_str, hora_final_str):
    try:
        # Conexión a la base de datos
        connection = mysql.connector.connect(
            host="BaseDatos_bibliotecas",
            user="root",
            password="BBDD_sistema_conteo$",
            database="base_datos_bibliotecas"
        )
        cursor = connection.cursor()
    
        # Ejecutar la consulta para obtener el resumen
        consulta = """
            SELECT
            SUM(personas_in) as total_personas_in,
            SUM(personas_out) as total_personas_out
            FROM aforo_biblioteca
            WHERE codigo_bib = %s AND fecha = %s AND hora >= %s AND hora < %s
        """
        cursor.execute(consulta, (codigo_bib, fecha, hora_inicio_str, hora_final_str))
        
        # Obtener el resultado
        resultado = cursor.fetchone()

        # Cerrar la conexión
        connection.close()

    except Exception as e:
        logging.error(f'Error en BBDD, funcion: obtener_resumen, biblioteca: {codigo_bib}, error: {e}')
        if connection.is_connected():
            connection.close()

    finally:
        if connection.is_connected():
            connection.close()

    return resultado

def obtener_horas_biblioteca(codigo_bib, fecha):
    try:
        # Conexión a la base de datos
        connection = mysql.connector.connect(
            host="BaseDatos_bibliotecas",
            user="root",
            password="BBDD_sistema_conteo$",
            database="base_datos_bibliotecas"
        )

        cursor = connection.cursor()
       
        cursor.execute("""
            SELECT hora_inicio, hora_final
            FROM horarios_biblioteca
            WHERE fecha = %s AND codigo_bib = %s
        """, (fecha, codigo_bib))

        resultado = cursor.fetchone()

        if resultado:
            hora_apertura, hora_cierre = resultado
        else:
            # Si la fecha no existe, seleccionar una fecha base según el día de la semana
            fecha_base = datetime.strptime('2000-01-01', '%Y-%m-%d') if fecha.weekday() < 5 else datetime.strptime('1999-01-01', '%Y-%m-%d')
            
            # Consultar las horas de inicio y fin para la fecha base y código de biblioteca
            cursor.execute("""
                SELECT hora_inicio, hora_final
                FROM horarios_biblioteca
                WHERE fecha = %s AND codigo_bib = %s
            """, (fecha_base, codigo_bib))

            resultado_base = cursor.fetchone()

            if resultado_base:
                # Si se encuentra en la fecha base, devolver las horas de inicio y fin
                hora_apertura, hora_cierre = resultado_base
            else:
                # Si no hay información para la fecha base, asignar valores predeterminados
                hora_apertura, hora_cierre = datetime.strptime('07:00:00', '%H:%M:%S'), datetime.strptime('21:30:00', '%H:%M:%S')
                #Objetos datetime.timedelta (igual en la BBDD)
                hora_apertura = timedelta(
                    hours=hora_apertura.hour,
                    minutes=hora_apertura.minute,
                    seconds=hora_apertura.second)
                
                hora_cierre = timedelta(
                    hours=hora_cierre.hour,
                    minutes=hora_cierre.minute,
                    seconds=hora_cierre.second)

        connection.close()

        return hora_apertura, hora_cierre

    except Exception as e:
        logging.error(f'Error en BBDD, funcion: obtener_horas_biblioteca, biblioteca: {codigo_bib}, error: {e}')
        if connection.is_connected():
            connection.close()

        hora_apertura, hora_cierre = datetime.strptime('07:00:00', '%H:%M:%S'), datetime.strptime('21:30:00', '%H:%M:%S')
        #Objetos datetime.timedelta (igual en la BBDD)
        hora_apertura = timedelta(
                    hours=hora_apertura.hour,
                    minutes=hora_apertura.minute,
                    seconds=hora_apertura.second)
        
        hora_cierre = timedelta(
                    hours=hora_cierre.hour,
                    minutes=hora_cierre.minute,
                    seconds=hora_cierre.second)
        
        return hora_apertura, hora_cierre

    finally:
        if connection.is_connected():
            connection.close()

def crear_dataframe(codigo_bib, fecha, hora_inicio, intervalo, hora_fin):
    datos = {'codigo_bib': [], 'fecha': [], 'hora_inicio': [],
             'hora_final': [], 'contador_in': [], 'contador_out': [], 'aforo': []}

    aforo = 0

    while hora_inicio < hora_fin:

        hora_final = calcular_hora_final(hora_inicio, intervalo)
        # Resumen del total de personas_in y personas_out, dentro del intervalo hora_inicio y hora_final
        secuencia = obtener_resumen(codigo_bib, fecha, hora_inicio, hora_final)

        contador_in = secuencia[0] if secuencia[0] is not None else 0
        contador_out = secuencia[1] if secuencia[1] is not None else 0
        aforo += contador_in - contador_out
        
        cadena_hora_inicio = deltatime_to_timehour(hora_inicio)
        cadena_hora_final = deltatime_to_timehour(hora_final)

        datos['codigo_bib'].append(codigo_bib)
        datos['fecha'].append(fecha)
        datos['hora_inicio'].append(cadena_hora_inicio)
        datos['hora_final'].append(cadena_hora_final)
        datos['contador_in'].append(contador_in)
        datos['contador_out'].append(contador_out)
        datos['aforo'].append(aforo)

        hora_inicio = hora_final

    df = pd.DataFrame(datos)

    return df

ruta = f'/app/Compartida/logs/log_informes.log'
logging.basicConfig(filename=ruta, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info('Inicio de programa')

# Obtenemos el codigo de todas las bibliotecas
codigos_bib = []
num_bibliotecas = os.getenv('num_bibliotecas')
for id in range(0, int(num_bibliotecas)):
    codigos_bib.append(os.getenv(f'bib_{id}'))

dicc_intervalos = {'30min':'00:30:00', 
                   '1min':'00:01:00'}

# Obtener la fecha y hora actual
fecha_hoy = datetime.now()

# Calcular la fecha de ayer restando un día
fecha_ayer = (fecha_hoy - timedelta(days=1)).date()

# Para cada biblioteca e intervalo de tiempo se crea un dataframe resumen del día
try:
    for codigo_bib in codigos_bib:
        hora_apertura, hora_cierre = obtener_horas_biblioteca(codigo_bib, fecha_ayer)
    
        for id in dicc_intervalos:
            intervalo = dicc_intervalos[id]
            df = crear_dataframe(codigo_bib, fecha_ayer, hora_apertura, intervalo, hora_cierre)

            # Guardar el DataFrame
            if id == '30min':
                ruta_archivo = f"/app/Compartida/{codigo_bib}/Informes/{id}/{fecha_ayer}_{codigo_bib}_{id}.xlsx"
                df.to_excel(ruta_archivo, index=False)
            else:
                ruta_archivo = f"/app/Compartida/{codigo_bib}/Informes/{id}/{fecha_ayer}_{codigo_bib}_{id}.csv"
                
                df.to_csv(ruta_archivo, index=False)
except Exception as e:
    logging.error(f'Error al generar informe: {e}')






