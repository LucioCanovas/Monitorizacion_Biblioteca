import time

def comprobar_estado(estado_bib):
    contador_bib_cerrado = 0
    
    try:

        for biblioteca, info_bib in estado_bib.items():
            estado = info_bib[0]
            nombre_contenedor_bib = info_bib[1]
            horario = True
            print(f'Estado: {estado}, horario: {horario}')

            if estado == 'Cerrado' and not horario:
                contador_bib_cerrado += 1

            elif estado == 'Cerrado' and horario:
                estado_bib[biblioteca] = ('Abierto', nombre_contenedor_bib)


            elif estado == 'Abierto' and not horario:
                contador_bib_cerrado += 1
                estado_bib[biblioteca] = ('Cerrado', nombre_contenedor_bib)

            elif estado == 'Abierto' and horario:
                continue

        return estado_bib

    except Exception as e:
        # Manejar cualquier error de conexión con Docker u otro error
        print(f"Error en comprobar_estado: {e}")

estado_bib = {'ANT': ('Cerrado', 'camara_ant')}

while True:
    estado_bib = comprobar_estado(estado_bib)
    print(estado_bib)
    time.sleep(15)