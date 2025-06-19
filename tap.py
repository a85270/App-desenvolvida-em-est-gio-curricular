from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from app.utils import cached_time_margin
import logging
import json

logging.basicConfig(level=logging.INFO)

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

@cached_time_margin
def plane(origem, destino, partida, chegada, passageiros=1):
    origem_iata = origem["fornecedor_id"]
    destino_iata = destino["fornecedor_id"]
    
    data = partida.strftime('%Y-%m-%d')
    url = f'https://booking.flytap.com/booking/flights/deeplink?market=PT&language=pt&origin={origem_iata}&destination={destino_iata}&flexibleDates=false&flightType=single&adt={passageiros}&chd=0&inf=0&yth=0&depDate={data}&headerfooterhidden=false&x_tap_source=WEB'
    logging.info(f'Acessando URL: {url}')
    
    driver = get_driver()
    driver.get(url)
    
    try:
        WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, 'onetrust-accept-btn-handler'))
        ).click()
    except Exception as e:
        logging.warning(f'Erro ao aceitar cookies: {str(e)}')
    
    try:
        WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'app-flight-result')))
    except Exception as e:
        logging.error(f'Erro ao carregar a página: {str(e)}')
        driver.quit()
        return []
    
    html_content = driver.page_source
    driver.quit()
    
    soup = BeautifulSoup(html_content, 'html.parser')
    flight_cards = soup.find_all('app-flight-result')
    
    results = []
    for flight_card in flight_cards:
        try:
            flight_details = flight_card.find('div', class_='flight-details__route')
            departure_time = flight_details.find('div', class_='flight-details__time-location is-departure').find('p', class_='bold').get_text(strip=True)[:5]
            departure_location = flight_details.find('div', class_='flight-details__time-location is-departure').find('p', class_='muted').get_text(strip=True)
            arrival_time = flight_details.find('div', class_='flight-details__time-location is-arrival').find('p', class_='bold').get_text(strip=True)[:5]
            arrival_location = flight_details.find('div', class_='flight-details__time-location is-arrival').find('p', 'muted').get_text(strip=True)
            departure = datetime.strptime(departure_time, '%H:%M').replace(year=partida.year, month=partida.month, day=partida.day)
            arrival = datetime.strptime(arrival_time, '%H:%M').replace(year=partida.year, month=partida.month, day=partida.day)
            if (departure < partida or arrival > chegada):
                continue

            duration_details = flight_card.find('div', class_='flight-details__duration-connections')
            duration = duration_details.find('p').get_text(strip=True)
            stops = duration_details.find_all('p')[1].get_text(strip=True)
            
            price = flight_card.find('div', class_='flight__cabin-right').find('p', class_='price').get_text(strip=True)
            price = price.replace(',', '.').replace('EUR', '').strip()  

            flight_info = {
                'origem': origem["coordenadas"],
                'destino': destino["coordenadas"],
                'partida': departure.strftime('%Y-%m-%d %H:%M:%S'),
                'chegada': arrival.strftime('%Y-%m-%d %H:%M:%S'),
                'fornecedor': 'TAP',
                'preco': float(price),
                'moeda': 'EUR',
                'transporte': 'airplane'
            }
            results.append(flight_info)
        except AttributeError as e:
            logging.warning(f'Erro ao extrair informações do voo: {str(e)}')

    return results

if __name__ == '__main__':
    origem = {
        "place_id": "ChIJwUqMhBYzGQ0RIkWqnDL2Al0",
        "fornecedor_id" : "LIS",
        "formatted_address": "Av. José Malhoa 16, 1070-159 Lisboa, Portugal",
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
        "place_id": "ChIJibOS4k2tGg0RF1lU7gZRZ-o",
        "fornecedor_id" : "FAO",
        "formatted_address": "Estr. da Penha, 8005-139 Faro, Portugal",
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
    passageiros = 1
    origem["coordenadas"] = origem["geometry"]["location"]
    destino["coordenadas"] = destino["geometry"]["location"]
    print(plane(origem, destino, datetime.now(), datetime.now() + timedelta(days=1), passageiros))
