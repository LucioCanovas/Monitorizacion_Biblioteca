import os
import sqlite3
import pandas as pd
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Cargar variables de entorno desde el archivo .env
load_dotenv()

def calcular_hora_final(hora_inicio_str, intervalo_str):
    # Convertir las cadenas de hora a objetos datetime
    hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M:%S')
    
    # Convertir el intervalo a un objeto timedelta
    intervalo = timedelta(seconds=sum(x * int(t) for x, t in zip([3600, 60, 1], map(int, intervalo_str.split(':')))))

    # Calcular la hora final sumando el intervalo a la hora de inicio
    hora_final = hora_inicio + intervalo

    # Formatear la hora final como cadena sin ceros innecesarios
    hora_final_str = hora_final.strftime('%H:%M:%S')

    return hora_final_str

def obtener_resumen(codigo_bib, fecha, hora_inicio_str, hora_final_str):
    print(hora_final_str)
    # Conectar a la base de datos SQLite
    conexion = sqlite3.connect(os.getenv("path_bbdd"))
    cursor = conexion.cursor()
    
    # Ejecutar la consulta para obtener el resumen
    consulta = """
    SELECT
        codigo_bib,
        fecha,
        SUM(personas_in) as total_personas_in,
        SUM(personas_out) as total_personas_out
    FROM Aforo
    WHERE codigo_bib = ? AND fecha = ? AND Hora >= ? AND Hora < ?
    """
    cursor.execute(consulta, (codigo_bib, fecha, hora_inicio_str, hora_final_str))
    
    # Obtener el resultado
    resultado = cursor.fetchone()

    # Cerrar la conexión
    conexion.close()

    # Devolver el resultado
    return resultado

def obtener_horas_biblioteca(codigo_bib, fecha_ayer_str):
    # Establecer la conexión a la base de datos SQLite
    conn = sqlite3.connect(os.getenv("path_bbdd"))
    cursor = conn.cursor()

    try:
        # Consultar si existe la fecha de ayer en la base de datos
        cursor.execute("""
            SELECT hora_inicio, hora_final
            FROM horarios
            WHERE fecha = ? AND codigo_bib = ?
        """, (fecha_ayer_str, codigo_bib))

        resultado = cursor.fetchone()

        if resultado:
            # Si la fecha de ayer existe, devolver las horas de inicio y fin
            hora_inicio, hora_fin = resultado
            print(resultado)
        else:
            # Si la fecha de ayer no existe, seleccionar una fecha base según el día de la semana
            fecha_entrada_base = '01-01-2000' if datetime.strptime(fecha_ayer_str, '%Y-%m-%d').weekday() < 5 else '01-01-1999'
            
            # Consultar las horas de inicio y fin para la fecha base y código de biblioteca
            cursor.execute("""
                SELECT hora_inicio, hora_final
                FROM horarios
                WHERE fecha = ? AND codigo_bib = ?
            """, (fecha_entrada_base, codigo_bib))

            resultado_base = cursor.fetchone()

            if resultado_base:
                # Si se encuentra en la fecha base, devolver las horas de inicio y fin
                hora_inicio, hora_fin = resultado_base
            else:
                # Si no hay información para la fecha base, asignar valores predeterminados
                hora_inicio, hora_fin = '07:00:00', '21:30:00'

        return hora_inicio, hora_fin

    except sqlite3.Error as e:
        print(e)
        return None, None

    finally:
        # Cerrar la conexión a la base de datos
        conn.close()

def crear_dataframe(codigo_bib, fecha, hora_inicio, intervalo, hora_fin):
    datos = {'codigo_bib': [], 'fecha': [], 'hora_inicio': [],
             'hora_final': [], 'contador_in': [], 'contador_out': [], 'aforo': []}

    aforo = 0
    fecha = fecha.strftime('%Y-%m-%d')
    while hora_inicio < hora_fin:
        hora_final = calcular_hora_final(hora_inicio, intervalo)
        secuencia = obtener_resumen(codigo_bib, fecha, hora_inicio, hora_final)

        contador_in = secuencia[2] if secuencia[2] is not None else 0
        contador_out = secuencia[3] if secuencia[3] is not None else 0
        aforo += contador_in - contador_out

        datos['codigo_bib'].append(codigo_bib)
        datos['fecha'].append(fecha)
        datos['hora_inicio'].append(hora_inicio)
        datos['hora_final'].append(hora_final)
        datos['contador_in'].append(contador_in)
        datos['contador_out'].append(contador_out)
        datos['aforo'].append(aforo)

        hora_inicio = hora_final

    df = pd.DataFrame(datos)
    return df

# Ejemplo de uso
codigos_bib = ['ANT']
dicc_intervalos = {'30min':'00:30:00', 
                   '1min':'00:01:00'}

fecha_ayer = datetime.now()
fecha_ayer_str = fecha_ayer.strftime('%Y-%m-%d')

for codigo_bib in codigos_bib:
    hora_inicio, hora_fin = obtener_horas_biblioteca(codigo_bib, fecha_ayer_str)
   
    for id in dicc_intervalos:
        intervalo = dicc_intervalos[id]
        df = crear_dataframe(codigo_bib, fecha_ayer, hora_inicio, intervalo, hora_fin)

        # Guardar el DataFrame en un archivo Excel en el directorio 'output'
        ruta_archivo = f"/app/Compartida/{codigo_bib}/Informes/{id}/{fecha_ayer_str}_{codigo_bib}_{id}.xlsx"
        if id == '30m':
            df.to_excel(ruta_archivo, index=False)
        else:
            df.to_csv(ruta_archivo, index=False)






