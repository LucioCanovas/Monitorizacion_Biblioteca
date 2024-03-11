import os
import pika
import time
import random
from dotenv import load_dotenv

load_dotenv()
# Configuración de conexión a RabbitMQ
credentials = pika.PlainCredentials(os.getenv("mq_user"), 
                                    os.getenv("mq_password"))
parameters = pika.ConnectionParameters(os.getenv("Ip_broker"),
                                   5672,
                                   '/',
                                   credentials)

connection = pika.BlockingConnection(parameters)
channel = connection.channel()
queue_name = 'test_queue'
channel.queue_declare(queue=queue_name)

# Función para enviar mensajes con tiempos aleatorios
def send_random_messages():
    for _ in range(120):  # 2 minutos
        message = f'Mensaje aleatorio: {random.randint(1, 100)}'
        channel.basic_publish(exchange='', routing_key=queue_name, body=message)
        print(f" [x] Enviado '{message}'")
        time.sleep(random.uniform(5, 15))

# Enviar mensajes aleatorios
send_random_messages()

# Cerrar la conexión
connection.close()