from flask import Flask, request, jsonify
import json
import redis
import time
import os
from pokemontcgsdk import Card
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import requests
import base64
from openai import OpenAI
from google.cloud import vision
import asyncio
from concurrent.futures import ThreadPoolExecutor

# Configuración de Google Vision
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:\Users\dpozo\OneDrive\Escritorio\google_cloud_vision_api\gen-lang-client-0273690567-b1f17b82b8d6.json"

# Configuración de Redis Labs
redis_client = redis.Redis(
    host='redis-15101.c240.us-east-1-3.ec2.redns.redis-cloud.com',  # Public endpoint de Redis Labs
    port=15101,
    password='Ptp5hTVvlyAqpMjmMHx2g7UJe1SK88aF',
    decode_responses=True
)

app = Flask(__name__)
client = OpenAI(api_key="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")

def get_cached_data(key):
    return redis_client.get(key)

def set_cached_data(key, value, timeout=3600):
    redis_client.set(key, value, ex=timeout)

def identificar_expansion_por_codigo_y_nombre(codigo_coleccion, nombre_carta):
    try:
        numero_carta, total_cartas = map(int, codigo_coleccion.split('/'))
        cartas_coincidentes = Card.where(q=f'number:{numero_carta} name:"{nombre_carta}"')
        
        posibles_expansiones = []
        for carta in cartas_coincidentes:
            if carta.set.printedTotal == total_cartas:
                posibles_expansiones.append({
                    'nombre': carta.name,
                    'set': carta.set.name,
                    'set_id': carta.set.id,
                })
        
        return posibles_expansiones if posibles_expansiones else "No se encontraron expansiones."
    
    except Exception as e:
        return f"Error al procesar el código de colección y nombre: {e}"

def search_TCGplayer(card_name, card_expansion):
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--enable-unsafe-swiftshader")

        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        search_url = f"https://www.tcgplayer.com/search/all/product?q={card_name}+{card_expansion}&view=grid"
        driver.get(search_url)
        time.sleep(5)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
        
        search_results_section = soup.find("section", class_="search-results")
        if not search_results_section:
            return "No se encontró la sección de resultados."
        
        card_rows = search_results_section.find_all("div", class_="product-card")
        if not card_rows:
            return "No se encontraron resultados."
        
        results = []
        for row in card_rows:
            name_tag = row.find("span", class_="product-card__title truncate")
            expansion_tag = row.find("h4", class_="product-card__set-name")
            price_tag = row.find("span", class_="product-card__market-price--value")
            
            results.append({
                "name": name_tag.get_text(strip=True) if name_tag else "Nombre no encontrado",
                "expansion": expansion_tag.get_text(strip=True) if expansion_tag else "Expansión no encontrada",
                "price": price_tag.get_text(strip=True) if price_tag else "Precio no encontrado",
            })
        
        return {"cards": results}
    
    except Exception as e:
        return f"Error en la búsqueda en TCGPlayer: {e}"

def search_trollandtoad(card_name, card_code):
    try:
        search_url = f"https://www.trollandtoad.com/category.php?selected-cat=0&search-words={card_code.replace('/', '%2F')}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        
        response = requests.get(search_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return f"Error al acceder a la página: Código de estado {response.status_code}"
        
        soup = BeautifulSoup(response.content, 'html.parser')
        card_rows = soup.find_all('div', class_='product-col col-12 p-0 my-1 mx-sm-1 mw-100')
        
        if not card_rows:
            return "No se encontraron resultados."
        
        results = []
        for row in card_rows:
            title_div = row.find('div', class_='col-11 prod-title')
            card_text = title_div.find('a', class_='card-text') if title_div else None
            price_row = row.find('div', class_='row position-relative align-center py-2 m-auto')
            price_div = price_row.find('div', class_='col-2 text-center p-1') if price_row else None
            
            if card_name and card_text and card_name.lower() not in card_text.get_text(strip=True).lower():
                continue
            
            results.append({
                "name": card_text.get_text(strip=True) if card_text else "Nombre no encontrado",
                "price": price_div.get_text(strip=True) if price_div else "Precio no encontrado",
            })
        
        return {"cards": results} if results else "No se encontraron cartas con ese nombre."
    
    except Exception as e:
        return f"Error en la búsqueda en Troll and Toad: {e}"

def encode_image(image_path):
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    except Exception as e:
        return f"Error al codificar la imagen: {e}"

def google_vision_api(image_path):
    try:
        client_vision = vision.ImageAnnotatorClient()
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        response = client_vision.text_detection(image=image)
        texts = response.text_annotations
        
        return texts[0].description if texts else None
    except Exception as e:
        return f"Error en Google Vision API: {e}"

# Para hacer llamadas asíncronas usando ThreadPoolExecutor (se usarán dentro de un loop síncrono)
def search_TCGplayer_async(card_name, card_expansion):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        return loop.run_in_executor(pool, search_TCGplayer, card_name, card_expansion)

def search_trollandtoad_async(card_name, card_code):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        return loop.run_in_executor(pool, search_trollandtoad, card_name, card_code)

@app.route("/process_image", methods=["POST"])
def process_image():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400
        
        image = request.files["image"]
        image_path = "temp.png"
        image.save(image_path)
        
        ocr_text = google_vision_api(image_path)
        base64_image = encode_image(image_path)
        
        response_openai = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""Instrucciones para el Modelo:

1. **Extracción de datos**:
   - Extrae el **nombre exacto** y el **código exacto** de la carta de Pokémon TCG.
   - El nombre debe ser preciso.
   - El código debe seguir el formato correcto (Ejemplo: 067/196, SM10-92, SWSH045).

2. **Limpieza del código**:
   - Elimina prefijos o sufijos no deseados.
   
3. **Validación**:
   - Valida el código utilizando la API de Pokémon TCG (https://pokemontcg.io/).
   - Si no es válido, responde "No encontrado".

4. **Formato de respuesta**:
   - Devuelve el nombre y el código encerrados en **, por ejemplo:
     **Pikachu**
     **227/193**
   
5. **Si no se extrae datos, devuelve "No encontrado".**

Texto extraído de la imagen:
{ocr_text}"""
            }],
        )
        respuesta_completa = response_openai.choices[0].message.content
        codigo_coleccion = respuesta_completa.split("**")[3] if len(respuesta_completa.split("**")) > 3 else "No encontrado"
        nombre_carta = respuesta_completa.split("**")[1] if len(respuesta_completa.split("**")) > 1 else "No encontrado"
        
        cache_key = f"{nombre_carta}:{codigo_coleccion}"
        cached_data = get_cached_data(cache_key)
        if cached_data:
            response_data = json.loads(cached_data)
            return jsonify(response_data)
        
        expansiones = identificar_expansion_por_codigo_y_nombre(codigo_coleccion, nombre_carta)
        if isinstance(expansiones, list) and expansiones:
            set_id1 = expansiones[0].get("set_id", "ID no disponible")
            
            # Usamos un loop de asyncio de forma síncrona
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            tcgplayer_future = search_TCGplayer_async(nombre_carta, set_id1)
            troll_future = search_trollandtoad_async(nombre_carta, codigo_coleccion)
            tcgplayer_data, resultados_trollandtoad = loop.run_until_complete(asyncio.gather(tcgplayer_future, troll_future))
            loop.close()
            
            formatted_pricestcg = [{"Nombre": card['name'], "Precio": card['price']} for card in tcgplayer_data.get("cards", [])] if isinstance(tcgplayer_data, dict) else []
            formatted_prices = [{"name": carta['name'], "price": carta['price']} for carta in resultados_trollandtoad.get("cards", [])] if isinstance(resultados_trollandtoad, dict) else []
            
            response_data = {
                "Card Name": nombre_carta,
                "Resultado TCG": formatted_pricestcg,
                "Resultado Troll": formatted_prices,
            }
            
            set_cached_data(cache_key, json.dumps(response_data))
            return jsonify(response_data)
        else:
            return jsonify({"error": "No se encontraron expansiones válidas."}), 404
    
    except Exception as e:
        return jsonify({"error": f"Error en el servidor: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
