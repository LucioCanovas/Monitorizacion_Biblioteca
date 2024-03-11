import numpy as np

#============================   Tracking    ==============================#
def encontrar_cercano(centroide, centroides, distancia_maxima=150):
    if len(centroides) == 0:
        return centroide, []

    centroides = np.array(centroides)
    distancias = np.linalg.norm(centroides - centroide, axis=1)
    candidatos_cercanos = np.where(distancias <= distancia_maxima)[0]

    if len(candidatos_cercanos) > 0:
        # Encuentra el centroide más cercano dentro del rango permitido
        indice_cercano = candidatos_cercanos[np.argmin(distancias[candidatos_cercanos])]
        centroide_cercano = centroides[indice_cercano]
        centroides_actualizados = np.delete(centroides, indice_cercano, axis=0)
    else:
        # No se encontraron candidatos cercanos dentro del rango
        centroide_cercano = centroide
        centroides_actualizados = centroides

    return centroide_cercano, centroides_actualizados


def generar_id_unico(diccionario):
    if not diccionario:
        # Si el diccionario está vacío, devuelve 1 como el primer ID
        return 1
    else:
        # Encuentra el valor más alto entre las claves y agrega 1
        nuevo_id = max(diccionario.keys()) + 1
        return nuevo_id


def zona_inicio(coordenadas, umbral):
    coordenada_y = coordenadas[1]
    if coordenada_y < umbral:
        return True     #Sale de la biblioteca
    else: return False  #Entra a la biblioteca
    

def tracking(lista, array, contador_in, contador_out):
    #Actualizamos centroides
    for id in lista: 
        result = lista[id]
        centroide = result[0]
        nuevo_centro, array = encontrar_cercano(centroide, array)
        lista[id][0] = nuevo_centro

    #Añadimos los nuevos centroides
    for centroide in array:
        nuevo_id = generar_id_unico(lista)  
        lista[nuevo_id] = [centroide, zona_inicio(centroide, 360), False] 
    
    #Comprobamos que centroides han pasado
    for id in lista:
        result = lista[id]
        centroide_y = result[0][1]
        paso = result[2]
        if paso:
            continue
        else:
            if centroide_y < 360 and not result[1]:
                lista[id][2] = True
                contador_in = contador_in + 1
            elif centroide_y > 360 and result[1]:
                lista[id][2] = True
                contador_out = contador_out + 1
    return (lista, contador_in, contador_out)