import logging
import json
import urllib.parse
import time
import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import re
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

def setup_logging():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def get_driver(headless=True):
    chrome_options = Options()
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=chrome_options)

def carregar_localizacoes():
    """Carrega as localizações do ficheiro todos.json."""
    try:
        todos_path = os.path.join(os.path.dirname(__file__), "transport_data", "todos.json")
        with open(todos_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Erro ao carregar o ficheiro todos.json: {str(e)}")
        return []

def procura_localizacao(nome, localizacoes):
    """Busca a localização pelo nome no ficheiro todos.json."""
    for local in localizacoes:
        if local["nome"].lower() == nome.lower():
            return local
    return None

def gerar_url(origem_nome, destino_nome, coord_origem, coord_destino, modo="CAR", carro="Clio V", combustivel="GASOLINE"):
    itinerary = (
        f'%7B%22t%22%3A3%2C%22l%22%3A%22{urllib.parse.quote(origem_nome)}%22%2C%22c%22%3A%7B%22lng%22%3A{coord_origem[1]}%2C%22lat%22%3A{coord_origem[0]}%7D%7D'
        f'~%7B%22t%22%3A3%2C%22l%22%3A%22{urllib.parse.quote(destino_nome)}%22%2C%22c%22%3A%7B%22lng%22%3A{coord_destino[1]}%2C%22lat%22%3A{coord_destino[0]}%7D%2C%22isArrival%22%3Atrue%7D'
    )
    return (
        f"https://www.viamichelin.pt/itinerarios/resultados?"
        f"bounds={coord_origem[0]}~{coord_origem[1]}~{coord_destino[0]}~{coord_destino[1]}"
        f"&car=29074~{urllib.parse.quote(carro)}~true~false~{combustivel}"
        f"&currency=eur&distanceSystem=METRIC&energyPrice=1.786"
        f"&from={urllib.parse.quote(origem_nome)}&itinerary={itinerary}"
        f"&poiCategories=0&selectedRoute=0&showPolandModal=false"
        f"&to={urllib.parse.quote(destino_nome)}&traffic=CLOSINGS&travelMode={modo}"
        f"&tripConstraint=NONE&withCaravan=false&zoiSettings=false~20"
    )

def aceitar_cookies(driver):
    try:
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
        )
        ActionChains(driver).move_to_element(button).click().perform()
        logging.info("Cookies aceites.")
    except Exception as e:
        logging.warning(f"Erro ao aceitar cookies: {str(e)}")

def carro_proprio(origem, destino, coord_origem, coord_destino, modo="CAR", headless=True, departure=None):
    origem_nome = origem["formatted_address"]
    destino_nome = destino["formatted_address"]
    
    logging.info("Método 'carro_proprio' chamado com os seguintes parâmetros:")
    logging.info(f"Origem: {origem}, Destino: {destino}, Coordenadas Origem: {coord_origem}, Coordenadas Destino: {coord_destino}")
    
    setup_logging()
    url = gerar_url(origem_nome, destino_nome, coord_origem, coord_destino, modo)
    logging.info(f"Acessando URL: {url}")
    driver = get_driver(headless)
    driver.get(url)
    logging.info("Página carregada com sucesso.")

    aceitar_cookies(driver)

    try:
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "route-card")))
        time.sleep(5)
    except Exception as e:
        logging.error(f"Erro ao carregar os dados da viagem: {str(e)}")
        driver.quit()
        return []

    html_content = driver.page_source
    driver.quit()
    soup = BeautifulSoup(html_content, "html.parser")
    rotas = []

    localizacoes = carregar_localizacoes()

def aceitar_cookies(driver):
    try:
        button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.ID, "didomi-notice-agree-button"))
        )
        ActionChains(driver).move_to_element(button).click().perform()
        logging.info("Cookies aceites.")
    except Exception as e:
        logging.warning(f"Erro ao aceitar cookies: {str(e)}")

def carro_proprio(origem, destino, coord_origem, coord_destino, modo="CAR", headless=True, departure=None):
    origem_nome = origem["formatted_address"]
    destino_nome = destino["formatted_address"]
    
    logging.info("Método 'carro_proprio' chamado com os seguintes parâmetros:")
    logging.info(f"Origem: {origem}, Destino: {destino}, Coordenadas Origem: {coord_origem}, Coordenadas Destino: {coord_destino}")
    
    setup_logging()
    url = gerar_url(origem_nome, destino_nome, coord_origem, coord_destino, modo)
    logging.info(f"Acessando URL: {url}")
    driver = get_driver(headless)
    driver.get(url)
    logging.info("Página carregada com sucesso.")

    aceitar_cookies(driver)

    try:
        WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CLASS_NAME, "route-card")))
        time.sleep(5)
    except Exception as e:
        logging.error(f"Erro ao carregar os dados da viagem: {str(e)}")
        driver.quit()
        return []

    html_content = driver.page_source
    driver.quit()
    soup = BeautifulSoup(html_content, "html.parser")
    rotas = []

    localizacoes = carregar_localizacoes()

    for card in soup.find_all("div", class_="route-card"):
        try:
           
            tipos = [span.text.strip() for span in card.find_all("span") if span.text.strip()]
            tipo = ", ".join([t for t in tipos if t in ["Económico", "Curto", "Rápido", "Ecológico"]]) or "Desconhecido"

            # duração da viagem
            duracao_element = card.find("div", {"data-testid": "route-card-duration"})
            duracao_texto = duracao_element.get_text(strip=True).replace("h", "h ").replace("min", "min") if duracao_element else "0h0m"

            # preço total
            preco_element = card.find("span", {"data-testid": "route-card-costs"})
            assert preco_element, "Elemento de preço não encontrado"
            preco = float(preco_element.get_text(strip=True).replace("€", "").replace(",", "."))

            # custo das portagens
            portagens_element = card.find("div", {"data-testid": "route-card-included-costs-mobile"})
            if portagens_element:
                portagens_texto = portagens_element.get_text(strip=True)
                match = re.search(r"[\d.,]+", portagens_texto)   # regex extrai apenas o número
                custo_portagens = float(match.group(0).replace(",", ".")) if match else 0.0
            else:
                custo_portagens = 0.0

            total_minutos = 0
            horas = re.search(r"(\d+)h", duracao_texto)
            minutos = re.search(r"(\d+)m", duracao_texto)

            if horas:
                total_minutos += int(horas.group(1)) * 60
            if minutos:
                total_minutos += int(minutos.group(1))

            logging.info(f"Duração em minutos: {total_minutos}")

            # hora de partida e chegada
            partida = departure.replace(hour=9, minute=0, second=0, microsecond=0) if departure else datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
            chegada = partida + timedelta(minutes=total_minutos)

            logging.info(f"Partida: {partida.strftime('%Y-%m-%d %H:%M:%S')}, Chegada: {chegada.strftime('%Y-%m-%d %H:%M:%S')}")

            
            rotas.append({
                "origem": {"lat": origem["geometry"]["location"]["lat"],"lng": origem["geometry"]["location"]["lng"]},
                "destino":{"lat": destino["geometry"]["location"]["lat"],"lng": destino["geometry"]["location"]["lng"]},
                "partida": partida.strftime("%Y-%m-%d %H:%M:%S"),
                "chegada": chegada.strftime("%Y-%m-%d %H:%M:%S"),
                "tipo": tipo,
                "moeda": "EUR",
                "preco": preco,
                "custo dos quais portagens": custo_portagens,
                "transporte": "car"
            })
        except Exception as e:
            logging.warning(f"Erro ao extrair dados de uma rota: {str(e)}")


    logging.info(f"Rotas extraídas: {json.dumps(rotas, indent=2, ensure_ascii=False)}")
    return rotas

if __name__ == "__main__":
    origem = {
        "formatted_address": "Av. José Malhoa 16, 1070-159 Lisboa, Portugal",
        "fornecedor_id": "000",
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
                "types": ["street_number"]
            },
            {
                "long_name": "Avenida José Malhoa",
                "short_name": "Av. José Malhoa",
                "types": ["route"]
            },
            {
                "long_name": "Lisboa",
                "short_name": "Lisboa",
                "types": ["locality", "political"]
            },
            {
                "long_name": "Campolide",
                "short_name": "Campolide",
                "types": ["administrative_area_level_3", "political"]
            },
            {
                "long_name": "Lisboa",
                "short_name": "Lisboa",
                "types": ["administrative_area_level_2", "political"]
            },
            {
                "long_name": "Lisboa",
                "short_name": "Lisboa",
                "types": ["administrative_area_level_1", "political"]
            },
            {
                "long_name": "Portugal",
                "short_name": "PT",
                "types": ["country", "political"]
            },
            {
                "long_name": "1070-159",
                "short_name": "1070-159",
                "types": ["postal_code"]
            }
        ]
    }

    destino = {
        "formatted_address": "Estr. da Penha, 8005-139 Faro, Portugal",
        "fornecedor_id": "0000",
        "address_components": [
            {
                "long_name": "Estrada da Penha",
                "short_name": "Estr. da Penha",
                "types": ["route"]
            },
            {
                "long_name": "Faro",
                "short_name": "Faro",
                "types": ["locality", "political"]
            },
            {
                "long_name": "União das freguesias de Faro (Sé e São Pedro)",
                "short_name": "União das freguesias de Faro (Sé e São Pedro)",
                "types": ["administrative_area_level_3", "political"]
            },
            {
                "long_name": "Faro",
                "short_name": "Faro",
                "types": ["administrative_area_level_2", "political"]
            },
            {
                "long_name": "Faro",
                "short_name": "Faro",
                "types": ["administrative_area_level_1", "political"]
            },
            {
                "long_name": "Portugal",
                "short_name": "PT",
                "types": ["country", "political"]
            },
            {
                "long_name": "8005-139",
                "short_name": "8005-139",
                "types": ["postal_code"]
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

    resultado = carro_proprio(origem, destino,
                                    (origem["geometry"]["location"]["lat"], origem["geometry"]["location"]["lng"]),
                                    (destino["geometry"]["location"]["lat"], destino["geometry"]["location"]["lng"]),
                                    modo="CAR", headless=True)

    print(json.dumps(resultado, indent=2, ensure_ascii=False))