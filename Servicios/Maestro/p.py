import docker
import time

client = docker.from_env()

while True:
    contenedor = client.containers.get('consumidor')
    if contenedor.status == 'running':
        print('Productor corriendo')
        time.sleep(10)
    else:
        print('Productor detenido')
        contenedor.start()
        print('Productor iniciado')
        time.sleep(10)

