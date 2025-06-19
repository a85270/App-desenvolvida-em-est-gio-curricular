from datetime import datetime, timedelta
from flask import Flask, jsonify, request
import logging
import json
from itertools import permutations
import re

from config import Config
from app.extensions import gmaps_wrapper

from app.Crawlers import verificar_cp
from app.flixbus import bus
from app.tap import plane
from Backend.app.carro_proprio import carro_proprio
from app.Rent_car import carros_disponiveis
from app.uber_cache import obter_distancia_e_duracao, estimar_preco_uber

from TravelSuggestor.app.routes.claude import ask_claude  

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

def sugerir_cidades_intermedias(origem, destino):
    prompt = f"""
Considera uma viagem entre {origem} e {destino}. Indica até 2 cidades reais que sejam as melhores opções para fazer uma paragem ou escala no percurso, ou seja, cidades que fiquem plausivelmente no caminho e que possam tornar a viagem mais conveniente.

Responde apenas com os nomes das cidades, separados por vírgulas, sem texto adicional, explicações ou formatações. Apenas os nomes das cidades.
"""
    resposta = ask_claude(prompt, temperature=0.3, max_tokens=60)
    return [cidade.strip() for cidade in resposta.split(',') if cidade.strip()]

def gerar_rotas_com_intermedias(origem, destino, intermedias):
    rotas = []
    # Limitada a avaliação só da primeira rota com 1 cidade intermédia para otimizar
    if intermedias:
        rota = [origem, intermedias[0], destino]
        rotas.append(rota)
    return rotas

def validar_resposta_regex(resposta):
    # Regex valida formato: Cidade - meio/fornecedor - Cidade - meio/fornecedor - Cidade ...
    pattern = r"^([A-Za-zÀ-ÿ0-9\s,\.]+ - [\w\s]+\/[\w\s]+)( - [A-Za-zÀ-ÿ0-9\s,\.]+ - [\w\s]+\/[\w\s]+)*$"
    return re.match(pattern, resposta.strip()) is not None

def preparar_prompt_avaliacao(opcoes):
    texto = "És um agente de viagens. Avalia a melhor rota possível entre as opções abaixo, com base nas viagens disponíveis. Usa apenas os meios e fornecedores listados. Responde só com o trajeto no formato:\n\nCidade - meio/fornecedor - Cidade - meio/fornecedor - Cidade\n\n"
    for idx, (rota, segmentos) in enumerate(opcoes, 1):
        viagens_str = "\n".join(
            [f"- {v.get('fornecedor', 'Desconhecido')}: {v.get('duracao_min', 'N/A')} min, {v.get('preco', 'N/A')} {v.get('moeda', 'N/A')}"
             for v in segmentos]
        )
        texto += f"Opção {idx}:\nRota: {' - '.join(rota)}\nViagens:\n{viagens_str}\n\n"
    texto += "Escolhe a melhor rota entre as opções acima e responde apenas com o trajeto no formato indicado, sem texto adicional."
    return texto

def obter_viagens_segmentadas(rota, partida, chegada, passageiros, get_trips_func, json_data, cache):
    segmentos_viagens = []
    for i in range(len(rota) - 1):
        origem_nome = rota[i]
        destino_nome = rota[i+1]
        cache_key = (origem_nome, destino_nome, partida, chegada, passageiros)
        if cache_key in cache:
            viagens = cache[cache_key]
        else:
            origem = None
            destino = None
           
            for loc in [json_data["origin"], json_data["destination"]]:
                if loc["formatted_address"] == origem_nome:
                    origem = loc
                if loc["formatted_address"] == destino_nome:
                    destino = loc
            if not origem:
                origem = {"formatted_address": origem_nome, "geometry": {"location": {"lat": 0, "lng": 0}}, "address_components": [{"long_name": origem_nome, "types": ["locality"]}]}
            if not destino:
                destino = {"formatted_address": destino_nome, "geometry": {"location": {"lat": 0, "lng": 0}}, "address_components": [{"long_name": destino_nome, "types": ["locality"]}]}
            viagens = get_trips_func(origem, destino, partida, chegada, passageiros)
            cache[cache_key] = viagens
        if viagens:
            segmentos_viagens.append(viagens[0])
        else:
            return None
    return segmentos_viagens

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.json.sort_keys = False

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

            fornecedores = [
                {"nome": "CP",
                 "pesquisa": verificar_cp
                 },
                {"nome": "FlixBus",
                 "pesquisa": bus
                 },
                {"nome": "TAP",
                 "pesquisa": plane
                 },
                {"nome": "Europcar",
                 "pesquisa": carros_disponiveis
                 },
            ]

            for fornecedor in fornecedores:
                logging.info(f"Processando fornecedor: {fornecedor['nome']}")
                origem_fornecedor = origem_fornecedores.get(fornecedor["nome"], None)
                destino_fornecedor = destino_fornecedores.get(fornecedor["nome"], None)

                if origem_fornecedor and destino_fornecedor:
                    encontrada_origem = set_fornecedor_id(origin, origem_fornecedor)
                    encontrado_destino = set_fornecedor_id(destination, destino_fornecedor)

                    if origin.get("coordenadas") == destination.get("coordenadas"):
                        logging.warning(f"As coordenadas de origem e destino são iguais para o fornecedor {fornecedor['nome']}")
                        continue
                    if not all([encontrada_origem, encontrado_destino]):
                        logging.warning(f"Fornecedor {fornecedor['nome']} não encontrado para origem ou destino.")
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

            try:
                logging.info("Calculando estimativa da Uber")
                origem_coords = origin["geometry"]["location"]
                destino_coords = destination["geometry"]["location"]
                origem_coords_dict = {"lat": origem_coords["lat"], "lng": origem_coords["lng"]}
                destino_coords_dict = {"lat": destino_coords["lat"], "lng": destino_coords["lng"]}

                distancia_km, duracao_min = obter_distancia_e_duracao(origem_coords_dict, destino_coords_dict)
                if distancia_km is not None:
                    for servico in ["UberX", "Comfort"]:
                        preco = estimar_preco_uber(distancia_km, duracao_min, destino_localidade.capitalize(), servico)

                        chegada = (departure + timedelta(minutes=duracao_min)).strftime('%Y-%m-%d %H:%M:%S')

                        results.append({
                            "origem": origem_coords_dict,
                            "destino": destino_coords_dict,
                            "partida": departure.strftime('%Y-%m-%d %H:%M:%S'),
                            "chegada": chegada,
                            "fornecedor": f"Uber {servico}",
                            "tipo": "Económico" if servico == "UberX" else "Conforto",
                            "moeda": "EUR",
                            "preco": round(preco, 2),
                            "descricao": "O preço apresentado é uma estimativa e pode variar.",
                            "distancia_km": round(distancia_km, 3),
                            "duracao_min": round(duracao_min, 1)
                        })
            except Exception as e:
                logging.error(f"Erro ao calcular estimativa da Uber: {e}")

            return jsonify(results), 200

        except Exception as e:
            logging.error(f"Erro interno do servidor: {str(e)}")
            return jsonify({"erro": f"Erro interno do servidor: {str(e)}"}), 500

    # --- Endpoint /plan_route com cache e validação regex ---

    @app.route("/plan_route", methods=["POST"])
    def plan_route():
        data = request.json
        origem = data["origin"]
        destino = data["destination"]
        partida = data["departure"]
        chegada = data["arrival"]
        passageiros = data["passengers"]

        origem_nome = origem["formatted_address"]
        destino_nome = destino["formatted_address"]

        def get_trips_local(origem_obj, destino_obj, partida, chegada, passageiros):
            with app.test_request_context():
                req_data = {
                    "origin": origem_obj,
                    "destination": destino_obj,
                    "departure": partida,
                    "arrival": chegada,
                    "passengers": passageiros
                }
                resp = app.test_client().post("/get_trips", json=req_data)
                if resp.status_code == 200:
                    return resp.get_json()
                else:
                    return []

        # Cache para evitar chamadas repetidas
        segmentos_cache = {}

        # viagem direta
        diretas = get_trips_local(origem, destino, partida, chegada, passageiros)

        # cidades intermédias (limitada a 1 para rapidez)
        intermedias = sugerir_cidades_intermedias(origem_nome, destino_nome)[:1]
        rotas_intermedias = gerar_rotas_com_intermedias(origem_nome, destino_nome, intermedias)

        opcoes_viagens = []
        if diretas:
            opcoes_viagens.append(([origem_nome, destino_nome], [diretas[0]]))

        for rota in rotas_intermedias:
            segmentos = obter_viagens_segmentadas(rota, partida, chegada, passageiros, get_trips_local, data, segmentos_cache)
            if segmentos:
                opcoes_viagens.append((rota, segmentos))

        if not opcoes_viagens:
            return jsonify({"erro": "Não foram encontradas viagens válidas."}), 404

        prompt = preparar_prompt_avaliacao(opcoes_viagens)
        resposta_final = ask_claude(prompt, temperature=0.0, max_tokens=200)

        # Valida resposta com regex
        if not validar_resposta_regex(resposta_final):
            return jsonify({"erro": "Resposta do agente com formato inválido.", "resposta": resposta_final}), 500

        return jsonify({"melhor_rota": resposta_final})

    return app
