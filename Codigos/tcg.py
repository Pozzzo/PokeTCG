import re
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import time
import requests
from bs4 import BeautifulSoup
import json
from google.cloud import vision
import pokemontcgsdk
import openai
from openai import OpenAI
from pokemontcgsdk import Card, RestClient, Set
from dotenv import load_dotenv
# --- IMPORTACIONES DE CONCURRENCIA ELIMINADAS ---
# (ya no se usan ThreadPoolExecutor ni as_completed)

load_dotenv()

# --- Configuración ---
pokemon_api_key = os.environ.get("POKEMON_TCG_API_KEY")
RestClient.configure(pokemon_api_key) 
RestClient.timeout = 30
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

# --- FUNCIÓN AYUDANTE PARA MANEJAR ERRORES DE BYTES (CORREGIDA) ---
def handle_exception_message(e):
    """Decodifica un mensaje de excepción si es de tipo bytes, de forma segura."""
    try:
        if hasattr(e, 'args') and e.args:
            arg = e.args[0]
            if isinstance(arg, bytes):
                return arg.decode('utf-8', errors='ignore')
        return str(e)
    except Exception as str_e:
        return f"Error de excepción no decodificable: {str_e}"

# --- FUNCIÓN AYUDANTE PARA CONVERTIR OBJETO CARTA A DICCIONARIO ---
def convert_card_to_dict(carta):
    """Convierte un objeto Card del SDK a un diccionario JSON-safe."""
    if not carta:
        return None
    
    def to_dict_safe(obj):
        if isinstance(obj, list):
            return [to_dict_safe(item) for item in obj]
        if hasattr(obj, '__dict__'):
            return {k: to_dict_safe(v) for k, v in obj.__dict__.items()}
        return obj

    data = {
        "id": getattr(carta, 'id', None),
        "name": getattr(carta, 'name', None),
        "number": getattr(carta, 'number', None),
        "rarity": getattr(carta, 'rarity', None),
        "artist": getattr(carta, 'artist', None),
        "hp": getattr(carta, 'hp', None),
        "types": getattr(carta, 'types', None),
        "subtypes": getattr(carta, 'subtypes', None),
        "retreatCost": getattr(carta, 'retreatCost', None),
        "set": to_dict_safe(getattr(carta, 'set', None)),
        "images": to_dict_safe(getattr(carta, 'images', None)),
        "tcgplayer": to_dict_safe(getattr(carta, 'tcgplayer', None)),
        "cardmarket": to_dict_safe(getattr(carta, 'cardmarket', None)),
        "attacks": to_dict_safe(getattr(carta, 'attacks', None)),
        "abilities": to_dict_safe(getattr(carta, 'abilities', None)),
        "weaknesses": to_dict_safe(getattr(carta, 'weaknesses', None)),
        "resistances": to_dict_safe(getattr(carta, 'resistances', None))
    }
    return data

def detectar_texto_google_vision(image_path):
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
    match = re.search(r'(\S+?)/(\S+)', texto)
    if match:
        codigo_carta, codigo_expansion = match.groups()
        return codigo_carta, codigo_expansion
    return None, None

def identificar_expansion_promo(texto):
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
    """Busca una carta promo por su ID y devuelve el objeto Card."""
    try:
        carta = Card.find(card_id)
        return carta
    except Exception as e:
        print(f"Error en buscar_carta_promo: {handle_exception_message(e)}")
        return None

def generar_posibles_codigos(codigo_carta_str):
    """Genera dos listas de códigos: obvios y desesperados (para OCR fallidos)."""
    obvios = []
    desesperados = []

    match = re.match(r"([a-zA-Z]+)(\d+)", codigo_carta_str)
    if match:
        prefix, number_part = match.groups()
        obvios.append(codigo_carta_str) # 'gg20'
        obvios.append(number_part)      # '20'
    else:
        if codigo_carta_str:
            obvios.append(codigo_carta_str) # '234'
        for j in range(1, len(codigo_carta_str)):
            if codigo_carta_str[j:]:
                desesperados.append(codigo_carta_str[j:])
    return obvios, desesperados

def buscar_carta(codigo_expansion, codigo_carta, nombre_carta):
    """
    Busca la carta en la API (SERIALMENTE) con lógica de reintentos para errores 504.
    """
    
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
        return None

    print(f"🔍 Expansiones candidatas: {expansiones_encontradas}")
    
    codigos_obvios, codigos_desesperados = generar_posibles_codigos(codigo_carta_str)
    print(f"🔍 Posibles códigos (Obvios): {codigos_obvios}")
    print(f"🔍 Posibles códigos (Desesperados, por fallo de OCR): {codigos_desesperados}")

    expansiones_a_probar = []
    for sub_codigo, expansion_ids in expansiones_encontradas:
        if not isinstance(expansion_ids, list):
            expansion_ids = [expansion_ids]
        expansiones_a_probar.extend(expansion_ids)
    
    # --- Función interna con lógica de reintentos ---
    def run_serial_search(codigos_a_probar):
        for expansion_id in expansiones_a_probar:
            for num in codigos_a_probar:
                if not num: continue

                print(f"🔎 [SERIAL] Buscando en API -> Expansión: {expansion_id}, Número: {num}")
                
                cartas_encontradas = None
                intentos_maximos = 3 # Intentar cada búsqueda 3 veces

                for intento in range(intentos_maximos):
                    try:
                        # --- Intento de Búsqueda ---
                        cartas_encontradas = Card.where(q=f'set.id:"{expansion_id}" number:"{num}"')
                        
                        # --- Éxito ---
                        # Si la búsqueda NO lanzó excepción, salimos del bucle de reintentos
                        break 
                    
                    except Exception as e:
                        # --- Fallo ---
                        error_msg = handle_exception_message(e)
                        print(f"⚠ [SERIAL] Intento {intento + 1}/{intentos_maximos} falló: {error_msg}")
                        
                        # Si NO es un error 504/timeout, O si es el último intento, no reintentamos.
                        if ("504" not in error_msg and "timeout" not in error_msg.lower()) or (intento == intentos_maximos - 1):
                            cartas_encontradas = None # Asegurarse de que sea None
                            break # Salir del bucle de reintentos
                        
                        # Si es un 504 y no es el último intento, esperar y reintentar
                        print(f"   ...Error 504/Timeout. Esperando 1 seg...")
                        time.sleep(1) 

                # --- Revisión de Resultados ---
                # Este 'if' se ejecuta *después* del bucle de reintentos
                if cartas_encontradas is not None:
                    for carta in cartas_encontradas:
                        if nombre_carta.lower() in carta.name.lower():
                            print(f"✅ [SERIAL] ¡ÉXITO! Encontrada: {carta.name} ({expansion_id}-{num})")
                            return carta # Devuelve el objeto Card
                
                # Si 'cartas_encontradas' es None (por error) o no hubo match, el bucle for principal continúa
        
        return None # No se encontró nada en este grupo

    # 1er Intento: Búsqueda con códigos OBVIOS
    print("--- 1er Intento (Códigos Obvios) ---")
    resultado = run_serial_search(codigos_obvios)
    if resultado:
        return resultado

    # 2do Intento: Búsqueda con códigos DESESPERADOS
    print("--- 2do Intento (Códigos Desesperados por OCR) ---")
    resultado_desesperado = run_serial_search(codigos_desesperados)
    if resultado_desesperado:
        return resultado_desesperado

    print(f"❌ No se encontró la carta '{nombre_carta}' ({codigo_carta}) en expansiones detectadas.")
    return None


def get_tcgplayer_prices(nombre_carta, codigo_carta):
    """Busca precios en TCGPlayer por scraping (como fallback)."""
    try:
        url = f"https://www.tcgplayer.com/search/all/product?q={nombre_carta}%2F{codigo_carta}&view=grid"
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

def no_promo_card(texto_detectado):
    """Lógica de procesamiento para cartas que NO son promos."""
    nombre_carta = identificar_nombre_carta(texto_detectado)
    print(f"🔎 [DEBUG] Nombre carta: {nombre_carta}")
    if not nombre_carta or "Error" in nombre_carta:
        return (jsonify({"error": f"No se detectó el nombre de la carta: {nombre_carta}"}), 400)

    codigo_carta, codigo_expansion = extraer_codigo(texto_detectado)
    print(f"🔎 [DEBUG] Código extraído: {codigo_carta} / {codigo_expansion}")
    if not codigo_carta or not codigo_expansion:
        return (jsonify({"error": "No se pudo extraer el código de la carta (ej. 123/456)"}), 400)

    carta_encontrada = buscar_carta(codigo_expansion, codigo_carta, nombre_carta)

    if not carta_encontrada:
        return (jsonify({"error": f"No se pudo encontrar la carta '{nombre_carta}' con el código {codigo_carta}/{codigo_expansion} en la API."}), 404)

    expansionf = carta_encontrada.set.id
    nombref = carta_encontrada.name
    codigof = carta_encontrada.number

    print("⚡ Buscando precios en TCGPlayer (SDK)...")
    tcgplayer_results = tcgplayer_search(expansionf, codigof)

    if "error" in tcgplayer_results:
        print(f"⚠️ SDK falló ({tcgplayer_results.get('error')}). Intentando scraping de TCGPlayer...")
        tcgplayer_results = get_tcgplayer_prices(nombref, codigof)
    
    print("⚡ Búsqueda de precios completada.")
    
    full_card_data = convert_card_to_dict(carta_encontrada)
            
    return full_card_data, tcgplayer_results

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
                full_card_data, tcgplayer_results = resultado
            
            else:
                # --- PROMO DETECTADA CORRECTAMENTE ---
                numero_promo = re.findall(r"\d+", codigo_promo)
                numero_real_promo = "".join(numero_promo).lstrip("0")
                if not numero_real_promo: numero_real_promo = "1"
                
                card_id = f"{codigo_exp_promo}-{numero_real_promo}"
                
                carta_encontrada = buscar_carta_promo(card_id)

                if not carta_encontrada:
                    print(f"API SDK falló para {card_id}, usando scraping TCGPlayer...")
                    tcgplayer_results = get_tcgplayer_prices(nombre_carta, numero_real_promo)
                    full_card_data = {
                        "id": card_id,
                        "name": nombre_carta,
                        "number": numero_real_promo,
                        "set": {"id": codigo_exp_promo},
                        "images": None,
                        "rarity": "Promo"
                    }
                else:
                    expansionf = carta_encontrada.set.id
                    codigof = carta_encontrada.number
                    nombref = carta_encontrada.name
                    
                    print("⚡ Buscando precios en TCGPlayer (Promo)...")
                    tcgplayer_results = tcgplayer_search(expansionf, codigof)
                    if "error" in tcgplayer_results:
                        print(f"⚠️ SDK falló. Intentando scraping...")
                        tcgplayer_results = get_tcgplayer_prices(nombref, codigof)
                    
                    full_card_data = convert_card_to_dict(carta_encontrada)

                response = {
                    "card_info": full_card_data,
                    "tcg": tcgplayer_results
                }
                return jsonify(response)

        else:
            # --- LÓGICA NO PROMO ---
            resultado = no_promo_card(texto_detectado)
            if isinstance(resultado, tuple) and len(resultado) == 2 and isinstance(resultado[1], int):
                 return resultado
            
            full_card_data, tcgplayer_results = resultado
            
            response = {
                "card_info": full_card_data,
                "tcg": tcgplayer_results
            }
            return jsonify(response)

    except Exception as e:
        error_message = handle_exception_message(e)
        print(f"Error fatal en procesar_imagen: {error_message}")
        return jsonify({"error": f"Error fatal en el servidor: {error_message}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
