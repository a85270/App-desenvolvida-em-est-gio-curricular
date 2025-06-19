from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from app.utils import cached_time_margin
import json
import logging
import time
import re

logging.basicConfig(level=logging.INFO)


def get_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--enable-unsafe-webgl')
    service = Service(ChromeDriverManager().install())
    retries = 3
    for attempt in range(retries):
        try:
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver
        except Exception as e:
            logging.error(f'Erro ao iniciar o WebDriver: {str(e)}')
            if attempt < retries - 1:
                time.sleep(5)
            else:
                raise

def limpar_texto(texto):
    texto = texto.replace("Paragem de partida: ", "").replace("Paragem de chegada: ", "").replace("Hora de partida: ", "").replace("Hora de chegada: ", "")
    partes = texto.split()
    texto_limpo = []
    for parte in partes:
        if parte not in texto_limpo:
            texto_limpo.append(parte)
    return " ".join(texto_limpo).replace('(','').replace(')','')

def limpar_tempo(tempo, data):
    # Extrai a hora no formato hh:mm usando regex
    match = re.search(r'(\d{2}:\d{2})', tempo)
    if not match:
        logging.error(f"Hora não encontrada em: {tempo}")
        return None
    hora = match.group(1)
    data_formatada = datetime.strptime(data, '%d.%m.%Y').strftime('%Y-%m-%d')
    return f"{data_formatada} {hora}:00"

@cached_time_margin
def bus(origem, destino, partida, chegada, passageiros=1):
    id_origem = origem["fornecedor_id"]
    id_destino = destino["fornecedor_id"]
    
    data = partida.strftime('%d.%m.%Y')
    url = f'https://shop.flixbus.pt/search?departureCity={id_origem}&arrivalCity={id_destino}&rideDate={data}&adult={passageiros}&_locale=pt&departureCountryCode=PT&arrivalCountryCode=PT'
    logging.info(f'Acessando URL: {url}')
    
    driver = get_driver()
    driver.get(url)
    
    try:
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, 'li.SearchResult__searchResult___cgxzZ')))
    except Exception as e:
        logging.error(f'Erro ao carregar a página: {str(e)}')
        driver.quit()
        return []
    
    html_content = driver.page_source
    driver.quit()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    tickets = soup.find_all('li', class_='SearchResult__searchResult___cgxzZ')
    
    results = []
    for ticket in tickets:
        try:
            partida_str = ticket.find('div', attrs={'data-e2e': 'search-result-departure-time'}).get_text(strip=True)
            chegada_str = ticket.find('div', attrs={'data-e2e': 'search-result-arrival-time'}).get_text(strip=True)
            partida_ticket = limpar_tempo(partida_str, data)
            # Passa a hora de partida para a função de chegada
            chegada_ticket = limpar_tempo(chegada_str, data)
            if not all([partida_ticket, chegada_ticket]):
                logging.warning('Partida ou chegada inválida, ignorando ticket...')
                continue
            preco_span = ticket.find('span', class_='Price__voPriceText___HO0dB')
            if preco_span:
                preco = preco_span.get_text(strip=True).replace('€', '').replace('\xa0', '').replace(',', '.').strip()
            else:
                preco = None
                raise ValueError('Preço não encontrado')
            viagem = {
                'origem': origem['coordenadas'],
                'destino': destino['coordenadas'],
                'partida': partida_ticket,
                'chegada': chegada_ticket,
                'fornecedor': "FlixBus",  
                'preco': float(preco), 
                'moeda': "EUR",
                'transporte': "bus"
            }
            results.append(viagem)
        except (AttributeError, ValueError):
            logging.warning('Elemento esperado não encontrado em um dos tickets, ignorando...')
    return results

if __name__ == '__main__':

    origem = {
        "place_id": "ChIJwUqMhBYzGQ0RIkWqnDL2Al0",
        "formatted_address": "Av.JoséMalhoa16,1070-159Lisboa,Portugal",
        "fornecedor_id": "14eefc82-b630-4aea-88dc-eb91e0b9d482",
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
    destino ={
        "place_id": "ChIJibOS4k2tGg0RF1lU7gZRZ-o",
        "fornecedor_id":"d0189569-bd3c-461f-9906-3bb7ebd9f65f",
        "formatted_address": "Estr.daPenha,8005-139Faro,Portugal",
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
    origem["coordenadas"] = origem["geometry"]["location"]
    destino["coordenadas"] = destino["geometry"]["location"]
    passageiros = 1
    result = bus(origem, destino, datetime.now(), datetime.now() + timedelta(days=1), passageiros)
    print(json.dumps(result, indent=2))
