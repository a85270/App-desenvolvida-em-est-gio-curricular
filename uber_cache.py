from flask import Flask, jsonify, request
from app.extensions import gmaps_wrapper 
import random

app = Flask(__name__)

tarifas_uber = {
    "Lisboa": {"UberX": (0.90, 0.59, 0.09, 2.5), "Comfort": (1.15, 0.8, 0.15, 3.25)},
    "Porto": {"UberX": (0.90, 0.59, 0.09, 2.5), "Comfort": (1.15, 0.8, 0.15, 3.25)},
    "Algarve": {"UberX": (1.00, 0.7, 0.09, 2.5), "Comfort": (1.3, 1.0, 0.12, 3.25)},
    "Madeira": {"UberX": (1.2, 0.65, 0.3, 2.5), "Comfort": (1.5, 0.9, 0.2, 3.5)}
}

def obter_distancia_e_duracao(origem, destino):
    """Obtém a distância e duração entre dois locais usando o GMapsCachedWrapper."""
    cliente = gmaps_wrapper.get_client()
    
    origem_str = f"{origem['lat']},{origem['lng']}"
    destino_str = f"{destino['lat']},{destino['lng']}"
    
    response = cliente.distance_matrix(origem_str, destino_str, mode="DRIVE")

    if not isinstance(response, list) or len(response) == 0:
        return None, 'Resposta inválida do Google Maps'

    elemento = response[0]  
    if not elemento.get('condition') == "ROUTE_EXISTS":
        return None, 'Não foi possível calcular a rota'

    distancia = elemento.get('distanceMeters', 0)               # em metros
    duracao = elemento.get('duration', '0s').replace('s', '')  # em segundos 

    try:
        duracao_min = int(duracao) / 60  # converte para minutos
    except ValueError:
        return None, 'Erro ao processar a duração'

    distancia_km = distancia / 1000  # converte metros para quilómetros
    print(f"Distância calculada: {distancia_km} km, Duração calculada: {duracao_min} minutos")
    return distancia_km, duracao_min

def estimar_preco_uber(distancia_km, duracao_min, cidade, servico):
    """Estima o preço da viagem com base na distância e duração."""
    if cidade in tarifas_uber and servico in tarifas_uber[cidade]:
        base, por_km, por_min, minimo = tarifas_uber[cidade][servico]
    else:
        tarifas_validas = [tarifas_uber[c][servico] for c in tarifas_uber if servico in tarifas_uber[c]]
        if not tarifas_validas:
            return f"O serviço {servico} não é suportado."
        
        base = sum(t[0] for t in tarifas_validas) / len(tarifas_validas)
        por_km = sum(t[1] for t in tarifas_validas) / len(tarifas_validas)
        por_min = sum(t[2] for t in tarifas_validas) / len(tarifas_validas)
        minimo = sum(t[3] for t in tarifas_validas) / len(tarifas_validas)
    
    preco_estimado = base + (distancia_km * por_km) + (duracao_min * por_min)
    preco_estimado = max(preco_estimado, minimo)
    
    variacao = random.uniform(0.9, 1.1)  # Varia entre -10% e +10%
    preco_estimado *= variacao
    
    return round(preco_estimado, 2)

@app.route('/estimar_preco', methods=['GET'])
def estimar_preco():
    cidade_origem = request.args.get('origem')
    cidade_destino = request.args.get('destino')
    servico = request.args.get('servico', 'UberX')

    if not cidade_origem or not cidade_destino:
        return jsonify({"erro": "Os parâmetros 'origem' e 'destino' são obrigatórios."}), 400

    distancia_km, duracao_min = obter_distancia_e_duracao(cidade_origem, cidade_destino)
    
    if distancia_km is None:
        return jsonify({"erro": duracao_min}), 500
    
    preco = estimar_preco_uber(distancia_km, duracao_min, cidade_destino, servico)
    return jsonify({
        "origem": cidade_origem,
        "destino": cidade_destino,
        "servico": servico,
        "preco_estimado": preco
    })

if __name__ == '__main__':
    app.run(debug=True)