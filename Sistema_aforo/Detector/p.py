import sqlite3


conn = sqlite3.connect('/home/admincamaras/CamarasBiblioteca/Compartida/BBDD/BBDD.db')
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS horarios
            (codigo_bib TEXT, fecha TEXT, hora_inicio TEXT, hora_final TEXT)""")

conn.commit()
conn.close