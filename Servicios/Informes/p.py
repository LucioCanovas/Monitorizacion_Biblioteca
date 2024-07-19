from datetime import datetime, timedelta

hora = datetime.now().time()
hora_informes = datetime.strptime('03:00:00', '%H:%M:%S').time()


print(hora>hora_informes)