from datetime import timedelta
from app.extensions import gmaps_wrapper

CONSUMO_MEDIO_LITROS_POR_100KM = 6.5  #litros por 100 km
PRECO_COMBUSTIVEL_POR_LITRO = 1.75    #€ por litro


def carro(origem, destino, partida, chegada, passageiros=1):
    gmaps = gmaps_wrapper.get_client()
    route = gmaps.distance_matrix(
        origem["geometry"]["location"], destino["geometry"]["location"],
        mode="DRIVE", # departure_time=partida (Argument commented until supported in wrapper (TODO))
    )[0]
    if route["status"] or route.get("condition") != "ROUTE_EXISTS":
        # No drive routes found between requested coordinates
        return []
    
    distancia = route["distanceMeters"]
    duracao = int(route["duration"][:-1])
    
    chegada_estimada = partida + timedelta(seconds=duracao)
    if chegada_estimada > chegada:
        return []
    
    distancia_km = distancia / 1000  # metros para quilometros
    litros_necessarios = (distancia_km * CONSUMO_MEDIO_LITROS_POR_100KM) / 100  
    custo_viagem = litros_necessarios * PRECO_COMBUSTIVEL_POR_LITRO  # total
    
    resultado = {
        "origem": origem["place_id"],
        "destino": destino["place_id"],
        "partida": partida.strftime('%Y-%m-%d %H:%M:%S'),
        "chegada": chegada_estimada.strftime('%Y-%m-%d %H:%M:%S'),
        "preco": float(custo_viagem),
        "moeda": "EUR",
        "transporte": "car",
    }
    return [resultado]
