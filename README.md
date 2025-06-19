# TravelManager Backend

Este backend permite obter opções de viagem entre dois pontos, integrando diferentes fornecedores e meios de transporte (avião, autocarro, carro alugado, carro próprio).

## Funcionalidades

- **tap.py**: Pesquisa voos da TAP entre aeroportos.
- **flixbus.py**: Pesquisa viagens de autocarro FlixBus.
- **Rent_car.py**: Pesquisa carros de aluguer Europcar.
- **carro_proprio.py**: Calcula custos e tempos de viagem de carro próprio (via ViaMichelin).
- **utils.py**: Funções utilitárias (ex: cache).
- **suggestor.py**: Lógica de sugestão e combinação de viagens.

## Pré-requisitos

- Python 3.10+
- [Selenium](https://selenium-python.readthedocs.io/)
- [webdriver-manager](https://github.com/SergeyPirogov/webdriver_manager)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/)
- [Flask](https://flask.palletsprojects.com/)
- Outras dependências em `requirements.txt`

## Instalação

1. Clone o repositório:
    ```sh
    git clone https://github.com/seu-usuario/seu-repo-backend.git
    cd seu-repo-backend
    ```

2. Crie e ative um ambiente virtual:
    ```sh
    python -m venv .venv
    .venv\Scripts\activate
    ```

3. Instale as dependências:
    ```sh
    pip install -r requirements.txt
    ```

## Como usar

Cada ficheiro pode ser executado individualmente para testar a integração com o respetivo fornecedor. Por exemplo:

```sh
python app/tap.py
python app/flixbus.py
python app/Rent_car.py
python app/carro_proprio.py
```

Os ficheiros usam exemplos de origem/destino no final do código para facilitar testes.

## Estrutura dos ficheiros

- `app/tap.py` — Scraper de voos TAP.
- `app/flixbus.py` — Scraper de autocarros FlixBus.
- `app/Rent_car.py` — Consulta à API Europcar.
- `app/carro_proprio.py` — Scraper de custos de viagem de carro próprio.
- `app/suggestor.py` — Lógica de sugestão de viagens (combina segmentos).
- `app/utils.py` — Utilitários (ex: cache).

## Observações

- O scraping pode falhar se o site do fornecedor mudar o layout.
- Para scraping, é necessário o Chrome instalado.
- Algumas funções usam variáveis de ambiente ou ficheiros auxiliares (ex: `todos.json`).

