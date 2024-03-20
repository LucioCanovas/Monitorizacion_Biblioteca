import cv2
import subprocess
import numpy as np

# URL RTSP de la cámara
rtsp_url = 'rtsp://username:password@ip_address:port/h264/ch1/main/av_stream'

# Comando de ffmpeg para capturar la transmisión RTSP y escribir en una tubería
ffmpeg_cmd = [
    'ffmpeg',
    '-i', rtsp_url,
    '-f', 'image2pipe',
    '-pix_fmt', 'bgr24',
    '-vcodec', 'rawvideo',
    '-'
]

# Iniciar el proceso de ffmpeg y crear una tubería
ffmpeg_process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

# Leer los fotogramas de la tubería y procesarlos con OpenCV
while True:
    # Leer el fotograma desde la tubería
    raw_frame = ffmpeg_process.stdout.read(640*480*3)  # Ajusta el tamaño según la resolución del video
    if len(raw_frame) != 640*480*3:
        break

    # Decodificar el fotograma en un formato que OpenCV pueda entender
    frame = cv2.imdecode(np.frombuffer(raw_frame, dtype=np.uint8), -1)

    # Mostrar el fotograma
    cv2.imshow('Frame', frame)
    
    # Salir del bucle si se presiona la tecla 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Liberar recursos y finalizar el proceso de ffmpeg
cv2.destroyAllWindows()
ffmpeg_process.kill()


