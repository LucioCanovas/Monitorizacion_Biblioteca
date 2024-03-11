import pika, os
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
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

# Función callback para procesar los mensajes recibidos
def callback(ch, method, properties, body):
    msg = body.decode('utf-8')
    print(f" [x] Recibido '{body}'")

# Configuración del consumo de la cola
channel.basic_consume(queue=queue_name, on_message_callback=callback, auto_ack=True)

# Iniciar la escucha de mensajes durante 5 minutos
print(' [*] Esperando mensajes. Se detendrá después de 5 minutos.')
try:
    channel.start_consuming()
except KeyboardInterrupt:
    print(' [!] Interrupción del usuario. Cerrando el receptor.')

# Cerrar la conexión
connection.close()

