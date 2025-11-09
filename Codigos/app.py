import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests
from bs4 import BeautifulSoup
import json
from google.cloud import vision
import pokemontcgsdk
import openai
from openai import OpenAI
from pokemontcgsdk import Card, RestClient, Set
from dotenv import load_dotenv
# <--- IMPORTACIÓN AÑADIDA ---
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

# --- Configuración ---
pokemon_api_key = os.environ.get("POKEMON_TCG_API_KEY")
RestClient.configure(pokemon_api_key) 
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"/home/ubuntu/gen-lang-client-0273690567-5fc84e7f3052.json"
client = openai.OpenAI()

# --- Diccionarios (sin cambios) ---
expansion_dict = {102: ['base1', 'hgss4'], 64: ['base2', 'neo3', 'sv6pt5'], 62: ['base3'], 130: ['base4', 'dp1'], 82: ['base5'], 132: ['gym1', 'gym2', 'dp3'], 111: ['neo1', 'pl2', 'xy3', 'sm4'], 75: ['neo2'], 18: ['si1', 'det1'], 105: ['neo4'], 165: ['ecard1', 'sv3pt5'], 147: ['ecard2', 'pl3', 'sm3'], 144: ['ecard3'], 109: ['ex1', 'ex7'], 100: ['ex2', 'ex14', 'dp5', 'dp7'], 97: ['ex3'], 95: ['ex4', 'hgss2', 'col1'], 101: ['ex5', 'ex15', 'bw3', 'bw10'], 112: ['ex6'], 17: ['pop1', 'pop2', 'pop3', 'pop4', 'pop5', 'pop6', 'pop7', 'pop8', 'pop9'], 107: ['ex8'], 106: ['ex9', 'dp4', 'xy2'], 115: ['ex10'], 113: ['ex11', 'bw11'], 92: ['ex12'], 110: ['ex13'], 108: ['ex16', 'bw5', 'xy6', 'xy12'], 123: ['dp2', 'hgss1'], 146: ['dp6', 'xy1'], 127: ['pl1'], 99: ['pl4', 'bw4'], 16: ['ru1'], 90: ['hgss3'], 114: ['bw1', 'xy11'], 98: ['bw2', 'xy7'], 124: ['bw6', 'xy10'], 20: ['dv1'], 149: ['bw7', 'sm1'], 135: ['bw8'], 116: ['bw9'], 39: ['xy0'], 119: ['xy4'], 160: ['xy5'], 34: ['dc1'], 162: ['xy8', 'sv5'], 122: ['xy9', 'swsh45sv'], 83: ['g1'], 145: ['sm2'], 73: ['sm35', 'swsh35'], 156: ['sm5'], 131: ['sm6', 'sv8pt5'], 168: ['sm7'], 70: ['sm75'], 214: ['sm8', 'sm10'], 181: ['sm9'], 236: ['sm11', 'sm12'], 68: ['sm115'], 94: ['sma'], 202: ['swsh1'], 192: ['swsh2'], 189: ['swsh3', 'swsh10'], 185: ['swsh4'], 72: ['swsh45'], 163: ['swsh5'], 198: ['swsh6', 'sv1'], 203: ['swsh7'], 25: ['cel25'], 9: ['bp'], 264: ['swsh8'], 10: ['tk1a', 'tk1b'], 12: ['tk2a', 'tk2b'], 172: ['swsh9'], 78: ['pgo'], 196: ['swsh11'], 195: ['swsh12'], 159: ['swsh12pt5', 'sv9'], 193: ['sv2'], 8: ['sve'], 197: ['sv3'], 182: ['sv4'], 91: ['sv4pt5'], 167: ['sv6'], 142: ['sv7'], 191: ['sv8']}
promos_dict= {53: 'basep', 40: 'np', 56: 'dp', 25: 'hgss', 101: 'bw', 211: 'xy', 248: 'sm', 307: 'swsh', 102: 'svp'}
inverse_expansion_dict = {}
for k, v_list in expansion_dict.items():
    for v in v_list:
        inverse_expansion_dict[v] = k
inverse_promos_dict = {v: k for k, v in promos_dict.items()}
expansion_promos_codes = {
    "dp": "dpp", "hgss": "hsp", "bw": "bwp", "xy": "xyp",
    "sm": "smp", "swsh": "swshp", "svp": "svp"
}

app = Flask(__name__)
CORS(app)

# --- FUNCIÓN AYUDANTE PARA MANEJAR ERRORES DE BYTES ---
def handle_exception_message(e):
    """Decodifica un mensaje de excepción si es de tipo bytes."""
    error_message = str(e)
    try:
        if hasattr(e, 'args') and e.args:
            arg = e.args[0]
            if isinstance(arg, bytes):
                error_message = arg.decode('utf-8', errors='ignore')
    except Exception:
        pass 
    return error_message
# ---------------------------------------------------------

def detectar_texto_google_vision(image_path):
    """Detecta texto en una imagen usando Google Vision API"""
    client = vision.ImageAnnotatorClient()
    with open(image_path, "rb") as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""

def identificar_nombre_carta(texto_detectado):
    """Identifica el nombre de la carta usando OpenAI."""
    try:
        response_openai = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Eres un experto en cartas TCG de Pokémon."},
                      {"role": "user", "content": f"Instrucciones: Tienes conocimiento de todos los nombres de cartas tcg de pokemon. Detecta el nombre de la carta. Dame como respuesta solo el nombre de la carta encerrado con **. Ejemplo: **Radiant Charizard**. Texto detectado: {texto_detectado}"
            }],
        )
        respuesta_completa = response_openai.choices[0].message.content
        nombre_carta = respuesta_completa.split("**")[1] if len(respuesta_completa.split("**")) > 1 else "No encontrado"       
        return nombre_carta
    except Exception as e:
        return f"Error: {handle_exception_message(e)}"

def extraer_codigo(texto):
    """Extrae el código de la carta (ej. '234') y el código de expansión (ej. '091')."""
    match = re.search(r'(\S+?)/(\S+)', texto)
    if match:
        codigo_carta, codigo_expansion = match.groups()
        return codigo_carta, codigo_expansion
    return None, None

def identificar_expansion_promo(texto):
    """Busca en el texto los códigos de expansión promo."""
    patrones_expansion = "|".join(inverse_promos_dict.keys())
    patron = rf"\b[G|H|I]?\s*({patrones_expansion})\s*(?:IN|EN)?\s*(\d{{1,3}})\b"
    coincidencias = re.findall(patron, texto, re.IGNORECASE)
    for expansion, numero in coincidencias:
        expansion = expansion.lower()
        if expansion in inverse_promos_dict:
            numero_formateado = numero.zfill(3) 
            return f"{expansion}{numero_formateado}", expansion_promos_codes[expansion]
    return None, None

def buscar_carta_promo(card_id):  
    """Busca una carta promo por su ID (ej. 'smp-SM10')"""
    try:
        carta = Card.find(card_id)
        return carta.set.id, carta.name, carta.number, carta.images.large
    except Exception as e:
        print(f"Error en buscar_carta_promo: {handle_exception_message(e)}")
        return None, None, None, None

def generar_posibles_codigos(codigo_carta_str):
    """Genera una lista de posibles códigos de carta (ej. 'gg20' -> ['gg20', '20'])"""
    match = re.match(r"([a-zA-Z]+)(\d+)", codigo_carta_str)
    if match:
        prefix, number_part = match.groups()
        return [codigo_carta_str, number_part]
    else:
        return [codigo_carta_str[j:] for j in range(len(codigo_carta_str)) if codigo_carta_str[j:]]

def buscar_carta(codigo_expansion, codigo_carta, nombre_carta):
    """Busca una carta regular en la API de Pokémon TCG."""
    codigo_expansion_str = str(codigo_expansion)
    codigo_carta_str = str(codigo_carta)
    codigo_expansion_str = ''.join(filter(str.isdigit, codigo_expansion_str))

    expansiones_encontradas = []
    for i in range(1, len(codigo_expansion_str) + 1):
        sub_codigo = int(codigo_expansion_str[:i])
        if sub_codigo in expansion_dict:
            expansiones_encontradas.append((sub_codigo, expansion_dict[sub_codigo]))

    if not expansiones_encontradas:
        print("No se encontró expansión en el código.")
        return None, None, None, None

    print(f"🔍 Expansiones candidatas: {expansiones_encontradas}")
    posibles_codigos_carta = generar_posibles_codigos(codigo_carta_str)
    print(f"🔍 Posibles códigos de carta: {posibles_codigos_carta}")

    for sub_codigo, expansion_ids in expansiones_encontradas:
        if not isinstance(expansion_ids, list):
            expansion_ids = [expansion_ids]
            
        for expansion_id in expansion_ids:
            print(f"🔍 Probando expansión: {expansion_id}")
            for num in posibles_codigos_carta:
                print(f"🔎 Buscando en API -> Expansión: {expansion_id}, Número: {num}")
                try:
                    cartas_encontradas = Card.where(q=f'set.id:"{expansion_id}" number:"{num}"')
                except Exception as e:
                    error_msg = handle_exception_message(e)
                    print(f"⚠ Error API TCG (set.id:{expansion_id} num:{num}): {error_msg}")
                    continue 

                for carta in cartas_encontradas:
                    print(f"🔎 Revisando carta: {carta.name} (Número: {carta.number})")
                    if nombre_carta.lower() in carta.name.lower():
                        return expansion_id, carta.name, carta.number, carta.images.large

    print(f"No se encontró la carta '{nombre_carta}' ({codigo_carta}) en expansiones detectadas.")
    return None, None, None, None

# --- MODIFICACIÓN: ACEPTA UNA LISTA DE CÓDIGOS DE EXPANSIÓN ---
def search_trollandtoad(card_name, card_code, expansion_codes_list):
    """Busca precios en Troll and Toad probando múltiples códigos de expansión."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        search_variants = [card_code, f"0{card_code}", f"00{card_code}"]
        all_results = []
        
        if not expansion_codes_list:
            return {"error": "Búsqueda de Troll cancelada: no se proporcionaron códigos de expansión."}
        
        # Elimina duplicados (ej. '91' y '091' pueden ser el mismo si el interno es 91)
        unique_expansion_codes = list(set(expansion_codes_list))
        print(f"🔎 Buscando en T&T con códigos de expansión: {unique_expansion_codes}")

        for expansion_code in unique_expansion_codes:
            if not expansion_code: # Saltar si uno de los códigos es None o ""
                continue
                
            for variant in search_variants:
                search_url = f"https://www.trollandtoad.com/search?q={variant}%2F{expansion_code}"
                
                try:
                    response = requests.get(search_url, headers=headers, timeout=10)
                    response.raise_for_status()
                except requests.RequestException as req_err:
                    error_msg = handle_exception_message(req_err)
                    print(f"Error en búsqueda T&T con {variant}/{expansion_code}: {error_msg}")
                    continue

                soup = BeautifulSoup(response.content, 'html.parser')
                card_rows = soup.find_all('div', class_='product-col col-12 p-0 my-1 mx-sm-1 mw-100')

                if card_rows:
                    for row in card_rows:
                        title_div = row.find('div', class_='col-11 prod-title')
                        card_text = title_div.find('a', class_='card-text') if title_div else None
                        price_row = row.find('div', class_='row position-relative align-center py-2 m-auto')
                        price_div = price_row.find('div', class_='col-2 text-center p-1') if price_row else None

                        if not (card_text and price_div):
                            continue

                        card_full_text = card_text.get_text(strip=True)
                        if card_name and card_name.lower() not in card_full_text.lower():
                            continue
                        
                        card_type = card_full_text.split('-')[-1].strip() if '-' in card_full_text else "Tipo no encontrado"
                        price = price_div.get_text(strip=True)
                        
                        all_results.append({"type": card_type, "price": price})
        
        # Si después de probar todas las combinaciones encontramos algo, lo devolvemos
        if all_results:
            return {"Troll": all_results}
        return {"error": "No se encontraron resultados en Troll and Toad."}
    except Exception as e:
        return {"error": f"Error en search_trollandtoad: {handle_exception_message(e)}"}

def search_trollandtoad_promo(nombre_carta, codigo_promo):
    """Busca precios de promos en Troll and Toad por scraping."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        search_url = f"https.www.trollandtoad.com/search?q={codigo_promo}"
        all_results = []

        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.RequestException as req_err:
            error_msg = handle_exception_message(req_err)
            print(f"Error en búsqueda T&T Promo {codigo_promo}: {error_msg}")
            return {"error": f"Error en búsqueda T&T Promo: {error_msg}"}

        soup = BeautifulSoup(response.content, 'html.parser')
        card_rows = soup.find_all('div', class_='product-col col-12 p-0 my-1 mx-sm-1 mw-100')

        if card_rows:
            for row in card_rows:
                title_div = row.find('div', class_='col-11 prod-title')
                card_text = title_div.find('a', class_='card-text') if title_div else None
                price_row = row.find('div', class_='row position-relative align-center py-2 m-auto')
                price_div = price_row.find('div', class_='col-2 text-center p-1') if price_row else None

                if not (card_text and price_div):
                    continue

                card_full_text = card_text.get_text(strip=True)
                if nombre_carta and nombre_carta.lower() not in card_full_text.lower():
                    continue

                all_results.append({
                    "name": card_full_text,
                    "price": price_div.get_text(strip=True),
                })
        if all_results:
            return {"cards": all_results}
        return {"error": "No se encontraron resultados en Troll and Toad para la promo."}
    except Exception as e:
        return {"error": f"Error en search_trollandtoad_promo: {handle_exception_message(e)}"}

def get_tcgplayer_prices(nombre_carta, codigo_carta):
    """Busca precios en TCGPlayer por scraping (como fallback)."""
    try:
        url = f"https.www.tcgplayer.com/search/all/product?q={nombre_carta}%20{codigo_carta}&view=grid"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        products = soup.find_all('div', {'class': 'product-card'})
        all_results = []
        
        for product in products:
            title_span = product.find('span', {'class': 'product-card_title'})
            expansion_h4 = product.find('h4', {'class': 'product-card_set-name'})
            price_span = product.find('span', {'class': 'product-card_market-price-value'})
            
            if not (title_span and expansion_h4 and price_span):
                continue

            title = title_span.get_text(strip=True)
            if nombre_carta.lower() in title.lower():
                expansion = expansion_h4.get_text(strip=True)
                price = price_span.get_text(strip=True)
                all_results.append({
                    "name": title,
                    "expansion": expansion,
                    "price": price
                })

        if all_results:
            return {"cards": all_results}
        return {"error": "No se encontraron cartas coincidentes en TCGPlayer (Scraping)."}
    except requests.RequestException as req_err:
        return {"error": f"Error en la búsqueda con TCGPlayer: {handle_exception_message(req_err)}"}
    except Exception as e:
        return {"error": f"Error al procesar los resultados de TCGPlayer: {handle_exception_message(e)}"}


def tcgplayer_search(expansionf, codigof):
    """Busca precios en TCGPlayer usando el SDK oficial (preferido)."""
    try:
        card_id = f"{expansionf}-{codigof}"
        print(f"🔎 Buscando en TCGPlayer SDK con ID: {card_id}")
        card = Card.find(card_id)
        if card and hasattr(card, 'tcgplayer') and card.tcgplayer and hasattr(card.tcgplayer, 'prices'):
            prices = card.tcgplayer.prices
            
            market_prices = {
                "Normal": prices.normal.market if hasattr(prices, 'normal') and prices.normal and hasattr(prices.normal, 'market') else None,
                "Reverse Holofoil": prices.reverseHolofoil.market if hasattr(prices, 'reverseHolofoil') and prices.reverseHolofoil and hasattr(prices.reverseHolofoil, 'market') else None,
                "Holofoil": prices.holofoil.market if hasattr(prices, 'holofoil') and prices.holofoil and hasattr(prices.holofoil, 'market') else None,
                "First Edition Holofoil": prices.firstEditionHolofoil.market if hasattr(prices, 'firstEditionHolofoil') and prices.firstEditionHolofoil and hasattr(prices.firstEditionHolofoil, 'market') else None,
                "First Edition Normal": prices.firstEditionNormal.market if hasattr(prices, 'firstEditionNormal') and prices.firstEditionNormal and hasattr(prices.firstEditionNormal, 'market') else None,
            }
            available_prices = {k: v for k, v in market_prices.items() if v is not None}

            if available_prices:
                return available_prices
            else:
                return {"error": "No hay precios disponibles (SDK) para esta carta."}
        else:
            return {"error": f"No se encontró información de precios (SDK) para la carta ID '{card_id}'."}
    except Exception as e:
        return {"error": f"Error en tcgplayer_search (SDK): {handle_exception_message(e)}"}

# --- MODIFICACIÓN: USA CONCURRENCIA ---
def no_promo_card(texto_detectado):
    """Lógica de procesamiento para cartas que NO son promos."""
    nombre_carta = identificar_nombre_carta(texto_detectado)
    print(nombre_carta)
    if not nombre_carta or "Error" in nombre_carta:
        return (jsonify({"error": f"No se detectó el nombre de la carta: {nombre_carta}"}), 400)

    codigo_carta, codigo_expansion = extraer_codigo(texto_detectado)
    print(codigo_carta, codigo_expansion)
    if not codigo_carta or not codigo_expansion:
        return (jsonify({"error": "No se pudo extraer el código de la carta (ej. 123/456)"}), 400)

    expansionf, nombref, codigof, imagenf = buscar_carta(codigo_expansion, codigo_carta, nombre_carta)

    if not expansionf:
        return (jsonify({"error": f"No se pudo encontrar la carta '{nombre_carta}' con el código {codigo_carta}/{codigo_expansion} en la API."}), 404)

    # --- INICIO DE CAMBIO: CONCURRENCIA ---
    
    # 1. Prepara las "posibilidades" para Troll and Toad
    expansion_number_str = ''.join(filter(str.isdigit, str(codigo_expansion)))
    internal_expansion_code = str(inverse_expansion_dict.get(expansionf))
    troll_codes_to_try = list(set([expansion_number_str, internal_expansion_code]))

    # 2. Ejecuta ambas búsquedas al mismo tiempo
    with ThreadPoolExecutor(max_workers=2) as executor:
        print("⚡ Ejecutando búsquedas de TCGPlayer y Troll&Toad en paralelo...")
        future_troll = executor.submit(search_trollandtoad, nombref, codigof, troll_codes_to_try)
        future_tcg = executor.submit(tcgplayer_search, expansionf, codigof)
        
        # 3. Espera y recoge los resultados
        trollandtoad_results = future_troll.result()
        tcgplayer_results = future_tcg.result()
    
    print("⚡ Búsquedas paralelas completadas.")
    # --- FIN DE CAMBIO: CONCURRENCIA ---
            
    return expansionf, nombref, tcgplayer_results, trollandtoad_results, imagenf

@app.route("/process_image", methods=["POST"])
def procesar_imagen():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400
        
        image = request.files["image"]
        image_path = "temp.png"
        image.save(image_path)

        texto_detectado = detectar_texto_google_vision(image_path)
        if not texto_detectado:
            return jsonify({"error": "No se detectó texto en la imagen"}), 400
        
        texto_min = texto_detectado.lower()
        expansion_detectada = next((exp for exp in inverse_promos_dict if exp in texto_min), None)

        if expansion_detectada:
            # --- LÓGICA PROMO ---
            nombre_carta = identificar_nombre_carta(texto_detectado)
            if not nombre_carta or "Error" in nombre_carta:
                return jsonify({"error": f"No se detectó el nombre de la carta (promo): {nombre_carta}"}), 400
            
            codigo_promo, codigo_exp_promo = identificar_expansion_promo(texto_detectado)
            
            if not codigo_promo or not codigo_exp_promo:
                print("No se detectó código de promo válido. Intentando como carta normal.")
                resultado = no_promo_card(texto_detectado)
                if isinstance(resultado, tuple) and len(resultado) == 2 and isinstance(resultado[1], int):
                     return resultado
                expansionf, nombref, tcgplayer_results, trollandtoad_results, imagenf = resultado
            
            else:
                # --- PROMO DETECTADA CORRECTAMENTE ---
                numero_promo = re.findall(r"\d+", codigo_promo)
                numero_real_promo = "".join(numero_promo).lstrip("0")
                if not numero_real_promo: numero_real_promo = "1"
                
                card_id = f"{codigo_exp_promo}-{numero_real_promo}"
                
                expansionf, nombref, codigof, imagenf = buscar_carta_promo(card_id)

                if not expansionf:
                    # Fallback si buscar_carta_promo falla
                    print(f"API SDK falló para {card_id}, usando scraping TCGPlayer...")
                    tcgplayer_results_promo = get_tcgplayer_prices(nombre_carta, numero_real_promo)
                    trollandtoad_results_promo = search_trollandtoad_promo(nombre_carta, codigo_promo) # Ejecutar T&T de todos modos
                    nombref = nombre_carta
                    expansionf = codigo_exp_promo
                    imagenf = None
                else:
                    # --- INICIO DE CAMBIO: CONCURRENCIA (PROMO) ---
                    with ThreadPoolExecutor(max_workers=2) as executor:
                        print("⚡ Ejecutando búsquedas de TCGPlayer (Promo) y Troll&Toad (Promo) en paralelo...")
                        future_troll_promo = executor.submit(search_trollandtoad_promo, nombre_carta, codigo_promo)
                        future_tcg_promo = executor.submit(tcgplayer_search, expansionf, codigof)
                        
                        trollandtoad_results_promo = future_troll_promo.result()
                        tcgplayer_results_promo = future_tcg_promo.result()
                    print("⚡ Búsquedas paralelas (Promo) completadas.")
                    # --- FIN DE CAMBIO: CONCURRENCIA (PROMO) ---

                response = {
                    "nombre": nombref,
                    "expansionf": expansionf,
                    "tcg": tcgplayer_results_promo,
                    "troll": trollandtoad_results_promo,
                    "url": imagenf
                }
                return jsonify(response)

        else:
            # --- LÓGICA NO PROMO ---
            resultado = no_promo_card(texto_detectado)
            if isinstance(resultado, tuple) and len(resultado) == 2 and isinstance(resultado[1], int):
                 return resultado
            
            expansionf, nombref, tcgplayer_results, trollandtoad_results, imagenf = resultado
            
            response = {
                "nombre": nombref,
                "expansionf": expansionf,
                "tcg": tcgplayer_results,
                "troll": trollandtoad_results,
                "url": imagenf
            }
            return jsonify(response)

    except Exception as e:
        error_message = handle_exception_message(e)
        print(f"Error fatal en procesar_imagen: {error_message}")
        return jsonify({"error": f"Error fatal en el servidor: {error_message}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
