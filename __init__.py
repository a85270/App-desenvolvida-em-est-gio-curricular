from datetime import datetime, timedelta
from flask import Flask, jsonify, request
import logging
import json

from config import Config
from app.extensions import cache, gmaps_wrapper

from app.Crawlers import verificar_cp
from app.flixbus import bus
from app.tap import plane
from app.carro_proprio import carro_proprio
from app.Rent_car import carros_disponiveis
from app.uber_cache import obter_distancia_e_duracao, estimar_preco_uber

TODOS_JSON_PATH = 'app/transport_data/todos.json'
_MAX_DISTANCE_KM = 250

def set_fornecedor_id(localizacao, opcoes_fornecedor, max_distance_km: float = None):
    if isinstance(opcoes_fornecedor, dict):
        localizacao["fornecedor_id"] = opcoes_fornecedor["codigo"]
        localizacao["coordenadas"] = opcoes_fornecedor["coordenadas"]
        return True
    
    from geopy.distance import distance
    max_distance = max_distance_km or _MAX_DISTANCE_KM
    
    latlng_localizacao = localizacao["geometry"]["location"]
    opcao_mais_perto = {}
    for opcao in opcoes_fornecedor:
        distance_km = distance(
            (latlng_localizacao["lat"], latlng_localizacao["lng"]),
            (opcao["coordenadas"]["latitude"], opcao["coordenadas"]["longitude"])
        ).km
        
        if opcao_mais_perto.get("distance", max_distance) > distance_km:
            opcao_mais_perto = opcao | {"distance": distance_km}
    
    if opcao_mais_perto:
        localizacao["fornecedor_id"] = opcao_mais_perto["codigo"]
        localizacao["coordenadas"] = opcao_mais_perto["coordenadas"]
        return True
    else:
        return False
    
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json.sort_keys = False
    
    cache.init_app(app)
    gmaps_wrapper.init_app(app)
    
    fornecedores_data = {}
    with open(TODOS_JSON_PATH, 'r', encoding='utf-8') as f:
        fornecedores_data = json.load(f)
        
    @app.route("/get_trips", methods=["POST"])
    def get_trips():
        try:
            origin = request.json.get("origin")
            destination = request.json.get("destination")
            departure = request.json.get("departure")
            arrival = request.json.get("arrival")
            num_passengers = request.json.get("passengers")

            only_transports = request.json.get("only_transports", None)
            except_transports = request.json.get("except_transports", [])
            is_requested_transport = lambda transport: (
                transport in (only_transports or [transport])
                and transport not in except_transports)
            
            if len(departure) == 10:
                departure += " 09:00:00"
            if len(arrival) == 10:
                arrival += " 23:59:59"  

            try:
                departure = datetime.strptime(departure, '%Y-%m-%d %H:%M:%S')
                arrival = datetime.strptime(arrival, '%Y-%m-%d %H:%M:%S')
            except ValueError as ve:
                logging.error(f"Erro ao converter datas: {ve}")
                return jsonify({"erro": "Formato de data inválido"}), 400

            logging.info("Procurando viagens de {} para {} entre {} e {}".format(
                origin["formatted_address"], destination["formatted_address"],
                departure, arrival))

            results = []
            
            # Pesquisa localizações dos
            origem_localidade = None
            destino_localidade = None
            origem_fornecedores = {}
            destino_fornecedores = {}

            for componente in origin.get("address_components", []):
                if any(tipo in componente["types"] for tipo in ["locality", "administrative_area_level_1"]):
                    origem_localidade = componente["long_name"].lower()
                    break

            for componente in destination.get("address_components", []):
                if any(tipo in componente["types"] for tipo in ["locality", "administrative_area_level_1"]):
                    destino_localidade = componente["long_name"].lower()
                    break

            for data in fornecedores_data:
                if data["nome"].lower() == origem_localidade:
                    origem_fornecedores = data["fornecedor"]
                if data["nome"].lower() == destino_localidade:
                    destino_fornecedores = data["fornecedor"]
                
                if origem_fornecedores and destino_fornecedores:
                    break
                        
            fornecedores = {
                "train": [
                    {"nome": "CP",
                     "pesquisa": verificar_cp
                    },
                ],
                "bus": [
                    {"nome": "FlixBus",
                     "pesquisa": bus
                    },
                ],
                "airplane": [
                    {"nome": "TAP",
                     "pesquisa": plane
                    },
                ],
                "rented car": [
                    {"nome": "Europcar",
                     "pesquisa": carros_disponiveis
                    },
                ]
            }
            # except_transports += {"bus"}      # WIP

            for transport_type in fornecedores:
                if not is_requested_transport(transport_type):
                    continue

                for fornecedor in fornecedores[transport_type]:
                    logging.info(f"Processando fornecedor: {fornecedor['nome']}")
                    origem_fornecedor = origem_fornecedores.get(fornecedor["nome"], None)
                    destino_fornecedor = destino_fornecedores.get(fornecedor["nome"], None)
                    if origem_fornecedor and destino_fornecedor:
                        encontrada_origem = set_fornecedor_id(origin, origem_fornecedor)
                        encontrado_destino = set_fornecedor_id(destination, destino_fornecedor)
                        if not all([encontrada_origem, encontrado_destino]):
                            logging.warning(f"Fornecedor {fornecedor['nome']} não encontrado para origem ou destino.")
                            continue
                        elif origin["fornecedor_id"] == destination["fornecedor_id"]:
                            # Prevent same search input for departure and arrival
                            continue

                    elif fornecedor["nome"] == "CP":
                        pass
                    
                    else:
                        logging.warning(f"Fornecedor {fornecedor['nome']} não possui informações suficientes.")
                        continue

                    try:
                        logging.info(f"Chamando método de pesquisa para {fornecedor['nome']}")
                        results.extend(fornecedor["pesquisa"](origin, destination, departure, arrival, num_passengers))
                    except Exception as e:
                        logging.error(f"Erro ao verificar {fornecedor['nome']}: {e}")
                
            if is_requested_transport("car"):
                try:
                    logging.info("Calculando rotas para 'carro próprio'")
                    carro_proprio_resultados = carro_proprio(
                        origin,
                        destination,
                        (origin["geometry"]["location"]["lat"], origin["geometry"]["location"]["lng"]),
                        (destination["geometry"]["location"]["lat"], destination["geometry"]["location"]["lng"]),
                        modo="CAR",
                        headless=True,
                        departure=departure
                    )
                    results.extend(carro_proprio_resultados)
                except Exception as e:
                    logging.error(f"Erro ao calcular rotas para 'carro próprio': {e}")

            if is_requested_transport("car ride"):
                try:
                    logging.info("Calculando estimativa da Uber")
                    origem_coords = origin["geometry"]["location"]
                    destino_coords = destination["geometry"]["location"]
                    origem = {"lat": origem_coords["lat"], "lng": origem_coords["lng"]}
                    destino = {"lat": destino_coords["lat"], "lng": destino_coords["lng"]}

                    distancia_km, duracao_min = obter_distancia_e_duracao(origem, destino)
                    if distancia_km is not None:
                        for servico in ["UberX", "Comfort"]:
                            preco = estimar_preco_uber(distancia_km, duracao_min, destino_localidade.capitalize(), servico)
                            
                        
                            chegada = (departure + timedelta(minutes=duracao_min)).strftime('%Y-%m-%d %H:%M:%S')

                            results.append({
                                
                                "origem": origem,
                                "destino": destino,
                                "partida": departure.strftime('%Y-%m-%d %H:%M:%S'),
                                "chegada": chegada,
                                "fornecedor": f"Uber {servico}",  
                                "tipo": "Económico" if servico == "UberX" else "Conforto",
                                "moeda": "EUR",
                                "preco": round(preco, 2),
                                "descricao": "O preço apresentado é uma estimativa e pode variar.",
                                "distancia_km": round(distancia_km, 3),
                                "duracao_min": round(duracao_min, 1),
                                "transporte": "car ride",
                            })
                except Exception as e:
                    logging.error(f"Erro ao calcular estimativa da Uber: {e}")
                
            return jsonify(results), 200

        except Exception as e:
            logging.error(f"Erro interno do servidor: {str(e)}")
            return jsonify({"erro": f"Erro interno do servidor: {str(e)}"}), 500

    return app