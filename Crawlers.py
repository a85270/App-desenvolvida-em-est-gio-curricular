import itertools
from playwright.sync_api import sync_playwright
import logging
from playwright_stealth import stealth_sync
import random
from datetime import datetime, timedelta

from app.utils import cached_time_margin
from app.transport_data import CP_helper as CP
from functools import wraps

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15",
]

def aceitar_cookies(page):
    page.evaluate("""
        let btn = document.querySelector("#onetrust-accept-btn-handler");
        if (btn) btn.click();
    """)
    logging.info("Cookies OK")

def nearest_CP_stations(search_func):
    @wraps(search_func)
    def wrapper(*args, **kwargs):
        # Set nearest station keys of origin and destination
        origin, destination = args[:2]
        origin["nearest_cp_station"] = CP.get_nearest_station(
            origin["geometry"]["location"])
        destination["nearest_cp_station"] = CP.get_nearest_station(
            destination["geometry"]["location"])
        
        try:
            # Set this key to facilitate caching in cached_search
            origin["coordenadas"] = origin["nearest_cp_station"]["location"]
            destination["coordenadas"] = destination["nearest_cp_station"]["location"]
        except KeyError:
            return []
        
        return search_func(*args, **kwargs)
    return wrapper

@nearest_CP_stations
@cached_time_margin
def verificar_cp(origem, destino, partida, chegada, passageiros=1):
    estacao_origem = origem["nearest_cp_station"]
    estacao_destino = destino["nearest_cp_station"]
    
    # Input para CP
    try:
        origem_cp = estacao_origem["name"]
        destino_cp = estacao_destino["name"]
        assert origem_cp != destino_cp
    except (KeyError, AssertionError):
        return []
    
    data_cp = partida.strftime('%Y-%m-%d')
    
    logging.info(f"Partida estação: {origem_cp}")
    logging.info(f"Chegada estação: {destino_cp}")

    # Definir alternativas possíveis para tentar de novo
    # se não encontrar resultados
    alternativas = {"origem": {origem_cp}, "destino": {destino_cp}}

    # Switch hyphens with/out surrounding spaces as alternative names
    hifens = dict([(" - ", "-"), ("-", " - ")])
    for nome, key in [(origem_cp, "origem"), (destino_cp, "destino")]:
        tem_hifen = next((hifen for hifen in hifens if hifen in nome), False)
        if tem_hifen:
            alternativas[key].add( nome.replace(tem_hifen, hifens[tem_hifen]))
    
    alternativas = [dict(zip(alternativas.keys(), combination)) for combination
                    in itertools.product(*alternativas.values())]
    resultados = []
    while not resultados and len(alternativas) > 0:
        alt = alternativas.pop()
        resultados = verificar_transporte(
            url="https://www.cp.pt/passageiros/pt/consultar-horarios",
            partida=alt["origem"],
            chegada=alt["destino"],
            tipo_transporte="train",
            data=data_cp,
            partida_selector='#depart',
            chegada_selector='#arrival',
            confirm_names=True,
            data_selector='#datepicker-first',
            botao_selector='input[type="submit"][value="Pesquisar »"]',
            resultado_selector='table tbody tr',
            fornecedor="CP"
        )

    resultados_cp = []
    for resultado in resultados:
        # Convertir origem e destino para as coordenadas
        resultado["origem"] = estacao_origem["location"]
        resultado["destino"] = estacao_destino["location"]

        cp_departure = resultado["partida"]
        cp_arrival = resultado["chegada"]
        if cp_departure == "N/A" or cp_arrival == "N/A":
            continue

        # Converter as strings para datetime
        cp_departure = datetime.strptime(cp_departure, '%Y-%m-%d %H:%M:%S')
        cp_arrival = datetime.strptime(cp_arrival, '%Y-%m-%d %H:%M:%S')

        # Filtrar pelas datas
        if partida <= cp_departure and cp_arrival <= chegada:
            resultados_cp.append(resultado)

    return resultados_cp

def verificar_transporte(url, fornecedor, tipo_transporte,
    partida, chegada, partida_selector, chegada_selector,
    data, data_selector, botao_selector, resultado_selector,
    confirm_names = False):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=['--disable-blink-features=AutomationControlled'])
            user_agent = random.choice(user_agents)
            context = browser.new_context(user_agent=user_agent)
            page = context.new_page()

            stealth_sync(page)
            page.goto(url)
            page.wait_for_load_state('networkidle')

            aceitar_cookies(page)
            
            logging.info(f"Preenchendo data: {data}")
            page.fill(data_selector, data)
            if not page.query_selector(data_selector):
                logging.error(f"Seletor de data não encontrado: {data_selector}")
                return []

            origin = page.query_selector(partida_selector)
            if not origin:
                logging.error(f"Seletor de partida não encontrado: {partida_selector}")
                return []
            else:
                logging.info(f"Preenchendo partida: {partida}")
            origin.type(partida)
            if confirm_names:
                origin.press("Enter")

            destination = page.query_selector(chegada_selector)
            if not destination:
                logging.error(f"Seletor de chegada não encontrado: {chegada_selector}")
                return []
            else:
                logging.info(f"Preenchendo chegada: {chegada}")
            destination.type(chegada)
            if confirm_names:
                destination.press("Enter")

            search_button = page.locator(botao_selector)
            if search_button.count():
                # Click if present
                logging.info("Clicando no botão de pesquisa")
                search_button.click()

            page.wait_for_load_state('domcontentloaded')

            linhas = page.query_selector_all(resultado_selector)
            logging.info(f"Número de linhas encontradas: {len(linhas)}")

            resultados = []
            for linha in linhas:
                try:
                    servico = linha.query_selector('td:nth-child(2)')
                    partida_hora = linha.query_selector('td:nth-child(3)')
                    chegada_hora = linha.query_selector('td:nth-child(4)')
                    preco_padrao = linha.query_selector('td:nth-child(6)')

                    partida_hora_texto = partida_hora.inner_text().strip() if partida_hora else "N/A"
                    chegada_hora_texto = chegada_hora.inner_text().strip() if chegada_hora else "N/A"

                    logging.info(f"Partida: '{partida_hora_texto}', Chegada: '{chegada_hora_texto}'")

                    if "Entre as" in partida_hora_texto or partida_hora_texto == "N/A":
                        continue

                    partida_hora_obj = formatar_hora_obj(data, partida_hora_texto)
                    chegada_hora_obj = formatar_hora_obj(data, chegada_hora_texto)

                    if chegada_hora_obj and partida_hora_obj and chegada_hora_obj < partida_hora_obj:
                        chegada_hora_obj += timedelta(days=1)

                    preco_normal_texto = preco_padrao.inner_text().strip() if preco_padrao else "N/A"
                    preco_normal = formatar_preco(preco_normal_texto)

                    fornecedor_viagem = fornecedor
                    if servico:
                        fornecedor_viagem = fornecedor + ": {}".format(servico.inner_text().strip())
                    
                    resultados.append({
                        "fornecedor": fornecedor_viagem,
                        "origem": partida,
                        "destino": chegada,
                        "transporte": tipo_transporte,
                        "partida": formatar_data_hora(partida_hora_obj) if partida_hora_obj else partida_hora_texto,
                        "chegada": formatar_data_hora(chegada_hora_obj) if chegada_hora_obj else chegada_hora_texto,
                        "preco": float(preco_normal),
                        "moeda": "EUR",
                    })
                except Exception as e:
                    logging.warning(f"Erro ao extrair linha: {e}")

            context.close()
            browser.close()

            if not resultados:
                logging.warning("Nenhum resultado encontrado!")

            return resultados

    except Exception as e:
        logging.exception(f"Erro ao verificar transporte: {e}")
        return {"erro": str(e)}

def formatar_hora_obj(data, hora_texto):
    try:
        if 'h' in hora_texto:
            hora_obj = datetime.strptime(hora_texto, "%Hh%M")
        else:
            hora_obj = datetime.strptime(hora_texto, "%H:%M")

        data_obj = datetime.strptime(data, "%Y-%m-%d")
        return datetime(data_obj.year, data_obj.month, data_obj.day, hora_obj.hour, hora_obj.minute)
    except ValueError:
        return None

def formatar_preco(preco_texto):
    try:
        preco_parts = preco_texto.split("/")[0]
        if "€" in preco_parts:
            preco = preco_parts.split("€")[1].replace(",", ".")
            return preco
        else:
            return "N/A"
    except (ValueError, IndexError):
        return "N/A"

def formatar_data_hora(data_hora_obj):
    return data_hora_obj.strftime("%Y-%m-%d %H:%M:%S")
