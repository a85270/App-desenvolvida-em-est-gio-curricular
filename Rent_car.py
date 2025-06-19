from flask import Flask, request, jsonify
import requests
import json
from datetime import datetime
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

def carros_disponiveis(origem, destino, pickup_date, drop_off_date, passengers, driver_age=26):
    origem_station_code = origem["fornecedor_id"]
    destino_station_code = destino["fornecedor_id"]

    if not all([pickup_date, drop_off_date]):
        logging.error("As datas de retirada e devolução são obrigatórias.")
        return []

    try:
        duration = (drop_off_date - pickup_date).days

        if duration <= 0:
            logging.error("A data de devolução deve ser posterior à data de retirada.")
            return []

        pickup_date_formatted = pickup_date.strftime("%Y-%m-%dT10:00:00")
        drop_off_date_formatted = drop_off_date.strftime("%Y-%m-%dT10:00:00")

    except ValueError:
        logging.error("Formato de data inválido. Use AAAA-MM-DD.")
        return []

    url = "https://services.europcar.com/emobgapi/v1/offers"
    params = {
        "apikey": "mqK5fTg12djSMga6sl1NbgeuOwbMhAxR",
        "origin": "www.europcar.pt/onesite",
        "vehicle-types": "CAR,LUXURY",
        "country-of-residence": "PT",
        "pickup-station-code": origem_station_code,
        "drop-off-station-code": destino_station_code,
        "pickup-date": pickup_date_formatted,
        "drop-off-date": drop_off_date_formatted,
        "driver-age": driver_age,
        "limit": 10,
        "offset": 0
    }

    response = requests.get(url, params=params)

    if response.status_code == 400:
        error_data = response.json()
        logging.error(f"Erro 400 da API: {error_data}")
        return []

    if response.status_code == 200:
        data = response.json()
        if 'data' in data and len(data['data']) > 0:
            offers = []
            for offer in data['data']:
                car = offer.get('car', {})
                rates = offer.get('rates', [{}])[0]
                price_info = rates.get('priceInCustomerCurrency', {})

                if not car or not price_info:
                    continue

                price_per_day = price_info.get('amount', 0)
                currency = price_info.get('currency', "EUR")
                total_price = price_per_day * duration

              
                partida_formatada = datetime.strptime(pickup_date.strftime("%Y-%m-%dT10:00:00"), "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                chegada_formatada = datetime.strptime(drop_off_date.strftime("%Y-%m-%dT10:00:00"), "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")

                offers.append({
                    "origem": origem["coordenadas"],
                    "destino": destino["coordenadas"],
                    "partida": partida_formatada,  
                    "chegada": chegada_formatada, 
                    "modelo": car.get('model', 'Desconhecido'),
                    "fornecedor": "Europcar",
                    "preco": float(total_price),
                    "moeda": currency,
                    "transporte": "rented car"
                })

            return offers
        else:
            logging.warning("Nenhuma oferta encontrada.")
            return []
    else:
        logging.error(f"Erro ao fazer a requisição. Status code: {response.status_code}, Detalhes: {response.text}")
        return []

if __name__ == '__main__':
    origem = {
        "formatted_address": "Av. José Malhoa 16, 1070-159 Lisboa, Portugal",
        "fornecedor_id" :"LIST01",
        "geometry": {
            "location": {
            "lat": 38.737739,
            "lng": -9.164437999999999
            },
            "location_type": "ROOFTOP"
        },
        "address_components": [
            {
            "long_name": "16",
            "short_name": "16",
            "types": [
                "street_number"
            ]
            },
            {
            "long_name": "Avenida José Malhoa",
            "short_name": "Av. José Malhoa",
            "types": [
                "route"
            ]
            },
            {
            "long_name": "Lisboa",
            "short_name": "Lisboa",
            "types": [
                "locality",
                "political"
            ]
            },
            {
            "long_name": "Campolide",
            "short_name": "Campolide",
            "types": [
                "administrative_area_level_3",
                "political"
            ]
            },
            {
            "long_name": "Lisboa",
            "short_name": "Lisboa",
            "types": [
                "administrative_area_level_2",
                "political"
            ]
            },
            {
            "long_name": "Lisboa",
            "short_name": "Lisboa",
            "types": [
                "administrative_area_level_1",
                "political"
            ]
            },
            {
            "long_name": "Portugal",
            "short_name": "PT",
            "types": [
                "country",
                "political"
            ]
            },
            {
            "long_name": "1070-159",
            "short_name": "1070-159",
            "types": [
                "postal_code"
            ]
            }
        ]
    }
    destino = {
  "formatted_address": "Estr. da Penha, 8005-139 Faro, Portugal",
  "fornecedor_id" :"FAOT01",
  "address_components": [
    {
      "long_name": "Estrada da Penha",
      "short_name": "Estr. da Penha",
      "types": [
        "route"
      ]
    },
    {
      "long_name": "Faro",
      "short_name": "Faro",
      "types": [
        "locality",
        "political"
      ]
    },
    {
      "long_name": "União das freguesias de Faro (Sé e São Pedro)",
      "short_name": "União das freguesias de Faro (Sé e São Pedro)",
      "types": [
        "administrative_area_level_3",
        "political"
      ]
    },
    {
      "long_name": "Faro",
      "short_name": "Faro",
      "types": [
        "administrative_area_level_2",
        "political"
      ]
    },
    {
      "long_name": "Faro",
      "short_name": "Faro",
      "types": [
        "administrative_area_level_1",
        "political"
      ]
    },
    {
      "long_name": "Portugal",
      "short_name": "PT",
      "types": [
        "country",
        "political"
      ]
    },
    {
      "long_name": "8005-139",
      "short_name": "8005-139",
      "types": [
        "postal_code"
      ]
    }
  ],
  "geometry": {
    "location": {
      "lat": 37.0284708,
      "lng": -7.923857699999999
    },
    "location_type": "GEOMETRIC_CENTER"
  }
}
    pickup_date = datetime.strptime('2025-05-29', '%Y-%m-%d')
    drop_off_date = datetime.strptime('2025-05-30', '%Y-%m-%d')
    passageiros = 1
    origem["coordenadas"] = origem["geometry"]["location"]
    destino["coordenadas"] = destino["geometry"]["location"]
    resultados = carros_disponiveis(origem, destino, pickup_date, drop_off_date, passageiros)
    print(json.dumps(resultados, indent=2))