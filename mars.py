import requests

API_KEY = "uU0HtIuSrObhlCycbYJGo2NhSph7mBOVnj8j05Jc"

# APOD - Foto astronômica do dia (esse funciona sempre)
url = "https://api.nasa.gov/planetary/apod"

params = {
    "api_key": API_KEY,
    "count": 5  # retorna 5 fotos aleatórias
}

response = requests.get(url, params=params)
print(f"Status code: {response.status_code}")

dados = response.json()

for foto in dados:
    print(f"Título: {foto['title']}")
    print(f"Data: {foto['date']}")
    print(f"URL: {foto['url']}")
    print("---")