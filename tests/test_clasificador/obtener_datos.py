import cv2
import os
import time
import pandas as pd

def capturar_frames_y_generar_video():
    # Configuración de la cámara
    RTSP_URL='rtsp://biblioteca:camaraBibAlex@192.168.102.120:554/h264/ch1/main/av_stream'
    cap = cv2.VideoCapture(RTSP_URL)

    # Configuración de la captura de video
    fps = 15  # FPS (cuadros por segundo) del video
    dimensiones = (720, 1280)  # Dimensiones de las imágenes

    # Configuración de la carpeta para almacenar los frames
    carpeta_frames = "frames"
    if not os.path.exists(carpeta_frames):
        os.makedirs(carpeta_frames)

    # Inicializar variables para el video
    nombre_video = "video.mp4"
    video = cv2.VideoWriter(nombre_video, cv2.VideoWriter_fourcc(*'mp4v'), fps, dimensiones)

    # Inicializar lista para almacenar los datos del CSV
    datos_csv = []

    # Tiempo de inicio
    tiempo_inicio = time.time()
    frame_id = 0

    while (time.time() - tiempo_inicio) < 300:  # Capturar durante 5 minutos
        ret, frame = cap.read()
        if ret:
            # Guardar el frame en la carpeta
            nombre_frame = f"frame_{frame_id}.jpg"
            cv2.imwrite(os.path.join(carpeta_frames, nombre_frame), frame)

            # Agregar datos al CSV
            datos_csv.append((frame_id, 0))

            # Agregar frame al video
            video.write(frame)

            frame_id += 1

    # Liberar recursos
    cap.release()
    video.release()
    cv2.destroyAllWindows()

    # Crear un DataFrame de pandas con los datos
    df = pd.DataFrame(datos_csv, columns=['frame_id', 'valor'])

    # Guardar el DataFrame como un archivo CSV
    df.to_csv('datos.csv', index=False)

if __name__ == "__main__":
    capturar_frames_y_generar_video()
