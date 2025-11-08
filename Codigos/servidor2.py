import re
from flask import Flask, request, jsonify
import os
import requests
from bs4 import BeautifulSoup
import json
from google.cloud import vision
import pokemontcgsdk
import openai
from openai import OpenAI
from pokemontcgsdk import Card, RestClient, Set
from pokemontcgsdk import Card, RestClient, Set
from dotenv import load_dotenv
load_dotenv()
# Configuración de la API Key de Pokémon TCG SDK
pokemon_api_key = os.environ.get("POKEMON_TCG_API_KEY")
# Configuración de Google Vision
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"/home/ubuntu/FAST-TRADE/gen-lang-client-0273690567-b1f17b82b8d6.json"
client = openai.OpenAI()
expansion_dict = {102: ['base1', 'hgss4'], 64: ['base2', 'neo3', 'sv6pt5'], 62: ['base3'], 130: ['base4', 'dp1'], 82: ['base5'], 132: ['gym1', 'gym2', 'dp3'], 111: ['neo1', 'pl2', 'xy3', 'sm4'], 75: ['neo2'], 18: ['si1', 'det1'], 105: ['neo4'], 165: ['ecard1', 'sv3pt5'], 147: ['ecard2', 'pl3', 'sm3'], 144: ['ecard3'], 109: ['ex1', 'ex7'], 100: ['ex2', 'ex14', 'dp5', 'dp7'], 97: ['ex3'], 95: ['ex4', 'hgss2', 'col1'], 101: ['ex5', 'ex15', 'bw3', 'bw10'], 112: ['ex6'], 17: ['pop1', 'pop2', 'pop3', 'pop4', 'pop5', 'pop6', 'pop7', 'pop8', 'pop9'], 107: ['ex8'], 106: ['ex9', 'dp4', 'xy2'], 115: ['ex10'], 113: ['ex11', 'bw11'], 92: ['ex12'], 110: ['ex13'], 108: ['ex16', 'bw5', 'xy6', 'xy12'], 123: ['dp2', 'hgss1'], 146: ['dp6', 'xy1'], 127: ['pl1'], 99: ['pl4', 'bw4'], 16: ['ru1'], 90: ['hgss3'], 114: ['bw1', 'xy11'], 98: ['bw2', 'xy7'], 124: ['bw6', 'xy10'], 20: ['dv1'], 149: ['bw7', 'sm1'], 135: ['bw8'], 116: ['bw9'], 39: ['xy0'], 119: ['xy4'], 160: ['xy5'], 34: ['dc1'], 162: ['xy8', 'sv5'], 122: ['xy9', 'swsh45sv'], 83: ['g1'], 145: ['sm2'], 73: ['sm35', 'swsh35'], 156: ['sm5'], 131: ['sm6', 'sv8pt5'], 168: ['sm7'], 70: ['sm75'], 214: ['sm8', 'sm10'], 181: ['sm9'], 236: ['sm11', 'sm12'], 68: ['sm115'], 94: ['sma'], 202: ['swsh1'], 192: ['swsh2'], 189: ['swsh3', 'swsh10'], 185: ['swsh4'], 72: ['swsh45'], 163: ['swsh5'], 198: ['swsh6', 'sv1'], 203: ['swsh7'], 25: ['cel25'], 9: ['bp'], 264: ['swsh8'], 10: ['tk1a', 'tk1b'], 12: ['tk2a', 'tk2b'], 172: ['swsh9'], 78: ['pgo'], 196: ['swsh11'], 195: ['swsh12'], 159: ['swsh12pt5', 'sv9'], 193: ['sv2'], 8: ['sve'], 197: ['sv3'], 182: ['sv4'], 91: ['sv4pt5'], 167: ['sv6'], 142: ['sv7'], 191: ['sv8']}
promos_dict= {53: 'basep', 40: 'np', 56: 'dp', 25: 'hgss', 101: 'bw', 211: 'xy', 248: 'sm', 307: 'swsh', 102: 'svp'}
inverse_expansion_dict = {}
# Convertir listas a tuplas y luego invertir el diccionario
for k, v_list in expansion_dict.items():
    for v in v_list:
        inverse_expansion_dict[v] = k
inverse_promos_dict = {v: k for k, v in promos_dict.items()}
# Relación de códigos de expansión
expansion_promos_codes = {
    "dp": "dpp",
    "hgss": "hsp",
    "bw": "bwp",
    "xy": "xyp",
    "sm": "smp",
    "swsh": "swshp",
    "svp": "svp"
}
app = Flask(__name__)
def detectar_texto_google_vision(image_path):
    """Detecta texto en una imagen usando Google Vision API"""
    client = vision.ImageAnnotatorClient()
    with open(image_path, "rb") as image_file:
        content = image_file.read()
    
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    if texts:
        return texts[0].description  # Texto detectado
    return ""

def identificar_nombre_carta(texto_detectado):
    try:
        response_openai = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "Eres un experto en cartas TCG de Pokémon."},
                      {
                "role": "user",
                "content": f"""Instrucciones para el Modelo:

                Tienes conocimiento sobre todos los nombres de cartas tcg de pokemon existente, por lo que puedes detectar el nombre de la carta si se te da información como el nombre y descripción de la carta.
                Dame como respuesta el nombre de la carta encerrado con ** evita agregar caracteres innecesarios como guiones y no omitas los espacios que son importantes para detectar la carta que es por ejemplo radiant charizard o greninja ex
                {texto_detectado}"""
            }],
        )
        respuesta_completa = response_openai.choices[0].message.content
        nombre_carta = respuesta_completa.split("**")[1] if len(respuesta_completa.split("**")) > 1 else "No encontrado"       
        return nombre_carta  # Se toma la primera palabra en mayúscula como el nombre
    
    except Exception as e:
        return f"Error: {str(e)}"

def extraer_codigo(texto):
    """
    Extrae el código de la carta y el código de expansión del texto.
    
    :param texto: str - Texto que contiene el código de la carta.
    :return: tuple - (código de carta, código de expansión) o (None, None) si no se encuentra.
    """
    match = re.search(r'(\S+?)/(\S+)', texto)  # Captura cualquier texto antes y después del primer "/"
    if match:
        codigo_carta, codigo_expansion = match.groups()
        return codigo_carta, codigo_expansion
    return None, None
def identificar_expansion_promo(texto):
    """
    Busca en el texto los códigos de expansión (svpxxx, swshxxx, SMxx, XYxx, BWXX, HGSSxx, dpxx)
    y devuelve el código de la carta junto con su expansión correspondiente.
    """
    # Expresión regular para encontrar los códigos de expansión seguidos de un número
    patrones_expansion = "|".join(inverse_promos_dict.keys())  # "dp|hgss|bw|xy|sm|swsh|svp"
    # Expresión regular para buscar (expansión + 3 dígitos)
    patron = rf"\b[G|H|I]?\s*({patrones_expansion})\s*(?:IN|EN)?\s*(\d{{3}})\b"
    coincidencias = re.findall(patron, texto, re.IGNORECASE)  # Ignora mayúsculas/minúsculas
    for expansion, numero in coincidencias:
        expansion = expansion.lower()  # Convertir a minúsculas para uniformidad
        if expansion in inverse_promos_dict:
            return f"{expansion}{numero}", expansion_promos_codes[expansion]
    return None, None  # Si no encuentra coincidencias
def buscar_carta_promo(card_id):  
    try:
        carta = Card.find(card_id)
        return carta.set.id,carta.name,carta.number,carta.images.large
    except Exception as e:
        return {"error": str(e)}
   
import re

def generar_posibles_codigos(codigo_carta_str):
    """
    Genera una lista de posibles códigos de carta a partir de la cadena dada.
    Si la cadena tiene un prefijo (como 'gg'), se consideran:
      - El código completo (ej. "gg20")
      - La parte numérica solamente (ej. "20")
    Para códigos puramente numéricos, se generan todas las subcadenas posibles (como en el código original).
    """
    # Verificar si el código tiene letras seguidas de dígitos (ej. "gg20")
    match = re.match(r"([a-zA-Z]+)(\d+)", codigo_carta_str)
    if match:
        # Si hay prefijo, generamos dos opciones: el código completo y solo la parte numérica.
        prefix, number_part = match.groups()
        return [codigo_carta_str, number_part]
    else:
        # Si no tiene prefijo, se genera la lista de subcadenas como antes.
        return [codigo_carta_str[j:] for j in range(len(codigo_carta_str)) if codigo_carta_str[j:]]

# Ejemplo de uso dentro de la función buscar_carta
def buscar_carta(codigo_expansion, codigo_carta, nombre_carta):
    """Busca carta en la API de Pokémon TCG con filtros aplicados para optimizar la búsqueda"""
    
    # Convertimos los códigos a string
    codigo_expansion_str = str(codigo_expansion)  # ej. "167*"
    codigo_carta_str = str(codigo_carta)  # ej. "gg20" o "51"

    # Limpiar el código de expansión para que contenga solo dígitos
    codigo_expansion_str = ''.join(filter(str.isdigit, codigo_expansion_str))

    # Buscar todas las combinaciones posibles de expansiones (de izquierda a derecha)
    expansiones_encontradas = []
    for i in range(1, len(codigo_expansion_str) + 1):
        sub_codigo = int(codigo_expansion_str[:i])  # Extrae desde el inicio hasta `i`
        if sub_codigo in expansion_dict:
            expansiones_encontradas.append((sub_codigo, expansion_dict[sub_codigo]))

    if not expansiones_encontradas:
        return "❌ No se encontró ninguna expansión dentro del código."

    print(f"🔍 Expansiones candidatas: {expansiones_encontradas}")

    # Generar posibles códigos de carta, considerando el caso de prefijos (ej. 'gg')
    posibles_codigos_carta = generar_posibles_codigos(codigo_carta_str)
    print(f"🔍 Posibles códigos de carta: {posibles_codigos_carta}")

    # Explorar cada expansión encontrada
    for sub_codigo, expansion_id in expansiones_encontradas:
        print(f"🔍 Probando expansión: {expansion_id}")

        # Buscar las cartas que cumplan con el número y la expansión
        for num in posibles_codigos_carta:
            print(f"🔎 Buscando en API -> Expansión: {expansion_id}, Número: {num}")  # DEBUG
            try:
                cartas_encontradas = Card.where(q=f"set.id:{expansion_id} number:{num}")
            except Exception as e:
                print(f"⚠ Error al obtener cartas de la expansión {expansion_id}: {e}")
                continue  # Si falla una, continúa con la siguiente expansión

            # Filtrar por nombre después de obtener las cartas necesarias
            for carta in cartas_encontradas:
                print(f"🔎 Revisando carta: {carta.name} (Número: {carta.number})")  # DEBUG
                if nombre_carta.lower() in carta.name.lower():
                    return expansion_id, carta.name, carta.number, carta.images.large

    return f"❌ No se encontró la carta '{nombre_carta}' con código {codigo_carta} en las expansiones detectadas."

def search_trollandtoad(card_name, card_code,expansion_code):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        # Lista de variantes del código de carta a probar
        search_variants = [card_code, f"0{card_code}", f"00{card_code}"]

        all_results = []  # 🔹 Lista para acumular los resultados

        for variant in search_variants:
            search_url = f"https://www.trollandtoad.com/category.php?selected-cat=0&search-words={variant}%2F{expansion_code}"
            
            try:
                response = requests.get(search_url, headers=headers, timeout=10)
                response.raise_for_status()  # 🔹 Lanza un error si la respuesta no es 200
            except requests.RequestException as req_err:
                print(f"Error en la búsqueda con {variant}: {req_err}")
                continue  # 🔹 Si hay error, pasa a la siguiente variante

            soup = BeautifulSoup(response.content, 'html.parser')
            card_rows = soup.find_all('div', class_='product-col col-12 p-0 my-1 mx-sm-1 mw-100')

            if card_rows:  # 🔹 Si encuentra resultados, los procesa
                for row in card_rows:
                    title_div = row.find('div', class_='col-11 prod-title')
                    card_text = title_div.find('a', class_='card-text') if title_div else None
                    price_row = row.find('div', class_='row position-relative align-center py-2 m-auto')
                    price_div = price_row.find('div', class_='col-2 text-center p-1') if price_row else None

                    # 🔹 Filtrar por nombre de carta si se proporciona
                    if card_name and card_text and card_name.lower() not in card_text.get_text(strip=True).lower():
                        continue
                    # 🔹 Extraer el tipo de carta y precio
                    # 🔹 Extraer solo la parte del tipo de carta después del código
                    if card_text:
                        card_full_text = card_text.get_text(strip=True)  # "Duraludon - 069/131"
                        card_type = card_full_text.split('-')[-1].strip() if '-' in card_full_text else "Tipo no encontrado"  # "Common Pokeball Reverse Holo"
                    else:
                        card_type = "Tipo no encontrado"
                    
                    price = price_div.get_text(strip=True) if price_div else "Precio no encontrado"
             
                    # Agregar el tipo de carta y su precio a los resultados
                    all_results.append({
                        "type": card_type,
                        "price": price
                    })

        # 🔹 Devolver resultados si se encontraron cartas
        if all_results:
            return {"Troll": all_results}

        # 🔹 Si ninguna variante tuvo resultados, devolver error
        return {"error": "No se encontraron resultados en Troll and Toad con ninguna variante del código de carta."}

    except Exception as e:
        return {"error": f"Error en la búsqueda en Troll and Toad: {e}"}
def search_trollandtoad_promo(nombre_carta,codigo_promo):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        search_url = f"https://www.trollandtoad.com/category.php?selected-cat=0&search-words={codigo_promo}"
        try:
            response = requests.get(search_url, headers=headers, timeout=10)
            response.raise_for_status()  # 🔹 Lanza un error si la respuesta no es 200
        except requests.RequestException as req_err:
            print(f"Error en la búsqueda con {codigo_promo}: {req_err}")
        soup = BeautifulSoup(response.content, 'html.parser')
        card_rows = soup.find_all('div', class_='product-col col-12 p-0 my-1 mx-sm-1 mw-100')
        all_results = []  # 🔹 Lista para acumular los resultados

        if card_rows:  # 🔹 Si encuentra resultados, los procesa
            for row in card_rows:
                title_div = row.find('div', class_='col-11 prod-title')
                card_text = title_div.find('a', class_='card-text') if title_div else None
                price_row = row.find('div', class_='row position-relative align-center py-2 m-auto')
                price_div = price_row.find('div', class_='col-2 text-center p-1') if price_row else None

                # 🔹 Filtrar por nombre de carta si se proporciona
                if nombre_carta and card_text and nombre_carta.lower() not in card_text.get_text(strip=True).lower():
                    continue

                all_results.append({
                    "name": card_text.get_text(strip=True) if card_text else "Nombre no encontrado",
                    "price": price_div.get_text(strip=True) if price_div else "Precio no encontrado",
                })

        # 🔹 Devolver resultados si se encontraron cartas
        if all_results:
            return {"cards": all_results}

        # 🔹 Si ninguna variante tuvo resultados, devolver error
        return {"error": "No se encontraron resultados en Troll and Toad con ninguna variante del código de carta."}

    except Exception as e:
        return {"error": f"Error en la búsqueda en Troll and Toad: {e}"}
def get_tcgplayer_prices(nombre_carta, codigo_carta):
    try:
        # Construir la URL de búsqueda en TCGPlayer
        url = f"https://www.tcgplayer.com/search/all/product?q={nombre_carta}-{codigo_carta}&view=grid"
        
        # Hacer la solicitud HTTP
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # Lanza un error si la respuesta no es 200
        
        # Procesar la respuesta HTML con BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Buscar los productos en la página de TCGPlayer
        products = soup.find_all('div', {'class': 'product-card'})

        all_results = []  # Lista para almacenar los resultados
        
        # Filtrar las cartas que coinciden con el nombre
        for product in products:
            title = product.find('span', {'class': 'product-card_title'}).get_text(strip=True)
            if nombre_carta.lower() in title.lower():  # Comparar sin importar mayúsculas/minúsculas
                # Extraer expansión y precio
                expansion = product.find('h4', {'class': 'product-card_set-name'}).get_text(strip=True)
                price = product.find('span', {'class': 'product-card_market-price-value'}).get_text(strip=True)
                all_results.append({
                    "name": title,
                    "expansion": expansion,
                    "price": price
                })

        # Si se encontraron resultados, devolverlos
        if all_results:
            return {"cards": all_results}

        # Si no se encontraron resultados, devolver un mensaje de error
        return {"error": "No se encontraron cartas coincidentes en TCGPlayer."}
    
    except requests.RequestException as req_err:
        # Manejar errores de solicitud
        return {"error": f"Error en la búsqueda con TCGPlayer: {req_err}"}
    except Exception as e:
        # Manejar cualquier otro tipo de error
        return {"error": f"Error al procesar los resultados de TCGPlayer: {e}"}


def tcgplayer_search(expansionf, codigof):
    try:
        # Formar el ID de la carta en el formato correcto
        card_id = f"{expansionf}-{codigof}"
        card = Card.find(card_id)
        # Verificar si se encontró la carta y tiene información de precios
        if card and hasattr(card, 'tcgplayer') and card.tcgplayer and hasattr(card.tcgplayer, 'prices'):
            prices = card.tcgplayer.prices
            if isinstance(prices, bytes):
                prices = prices.decode("utf-8")  # Decodificar a UTF-8
            # Diccionario con los precios disponibles
            market_prices = {
                "Normal": prices.normal.market if hasattr(prices, 'normal') and prices.normal else None,
                "Reverse Holofoil": prices.reverseHolofoil.market if hasattr(prices, 'reverseHolofoil') and prices.reverseHolofoil else None,
                "Holofoil": prices.holofoil.market if hasattr(prices, 'holofoil') and prices.holofoil else None,
                "First Edition Holofoil": prices.firstEditionHolofoil.market if hasattr(prices, 'firstEditionHolofoil') and prices.firstEditionHolofoil else None,
                "First Edition Normal": prices.firstEditionNormal.market if hasattr(prices, 'firstEditionNormal') and prices.firstEditionNormal else None,
            }

            # Filtrar solo los precios que existen (diferentes de None)
            available_prices = {k: v for k, v in market_prices.items() if v is not None}

            # Si hay precios disponibles, devolverlos en JSON
            if available_prices:
                return jsonify(available_prices)
            else:
                return jsonify({
                    "error": "No hay precios disponibles para esta carta."
                })

        else:
            return jsonify({
                "error": f"No se encontró información de precios para la carta con ID '{card_id}'."
            })

    except Exception as e:
        return jsonify({
            "error": f"Error en la búsqueda en TCGPlayer: {e}"
        })
def no_promo_card(texto_detectado):
    nombre_carta = identificar_nombre_carta(texto_detectado)
    print(nombre_carta)
    if not nombre_carta:
        return jsonify({"error": "No se detectó el nombre de la carta"}), 400

    codigo_carta, codigo_expansion = extraer_codigo(texto_detectado)
    print(codigo_carta, codigo_expansion)
    if not codigo_carta or not codigo_expansion:
        return jsonify({"error": "No se pudo extraer el código de la carta"}), 400

    # Buscar la carta en la API
    expansionf, nombref, codigof, imagenf = buscar_carta(codigo_expansion, codigo_carta,nombre_carta)
    trollandtoad_results = search_trollandtoad(nombref,codigof,inverse_expansion_dict.get(expansionf))
    tcgplayer_results = tcgplayer_search(expansionf,codigof).json
            # Simplificar la respuesta
    return expansionf,nombref,tcgplayer_results,trollandtoad_results,imagenf

@app.route("/process_image", methods=["POST"])
def procesar_imagen():
    try:
        if "image" not in request.files:
            return jsonify({"error": "No image provided"}), 400
        
        image = request.files["image"]
        image_path = "temp.png"
        image.save(image_path)

        """Procesa la imagen, detecta el texto, extrae códigos y busca la carta"""
        texto_detectado = detectar_texto_google_vision(image_path)
        texto_min = texto_detectado.lower()
        expansion_detectada = next((exp for exp in inverse_promos_dict if exp in texto_min), None)
        if not texto_detectado:
            return jsonify({"error": "No se detectó texto en la imagen"}), 400
        if expansion_detectada:
            # Lógica específica cuando se detecta "promo"
            nombre_carta = identificar_nombre_carta(texto_detectado.lower())
            if not nombre_carta:
                return jsonify({"error": "No se detectó el nombre de la carta"}), 400
            codigo_promo,codigo_exp_promo=identificar_expansion_promo(texto_detectado)
            print(codigo_promo,codigo_exp_promo)
            if not codigo_promo or not codigo_exp_promo:  # Si no se detecta algún código, va al else
                print("No se detectó código de promo válido.")
                expansionf,nombref,tcgplayer_results,trollandtoad_results,imagenf = no_promo_card(texto_detectado)
                print(trollandtoad_results)
                response = {
                    "nombre": nombref,
                    "expansionf": expansionf,
                    "tcg": tcgplayer_results,
                    "troll": trollandtoad_results,
                    "url": imagenf
                }
                return jsonify(response)
            trollandtoad_results_promo = search_trollandtoad_promo(nombre_carta,codigo_promo)
            numero_promo = re.findall(r"\d+", codigo_promo)
            numero_real_promo ="".join(numero_promo).lstrip("0")
            card_id = f"{codigo_exp_promo}-{numero_real_promo}"
            card = Card.find(card_id)
            if not card:
                tcgplayer_results_promo = get_tcgplayer_prices(nombre_carta, numero_real_promo).json
                if 'error' in tcgplayer_results_promo:
                    return jsonify(tcgplayer_results_promo)
                else:
                    return jsonify(tcgplayer_results_promo)
            else:
                tcgplayer_results_promo = tcgplayer_search(codigo_exp_promo,numero_real_promo).json
            expansionf, nombref, codigof, imagenf = buscar_carta_promo(card_id)
            print(expansionf, nombref, codigof, imagenf)
            response = {
                    "nombre": nombref,
                    "expansionf": expansionf,
                    "tcg": tcgplayer_results_promo,
                    "troll": trollandtoad_results_promo,
                    "url": imagenf
            }

            return jsonify(response)
        else:
            expansionf,nombref,tcgplayer_results,trollandtoad_results,imagenf=no_promo_card(texto_detectado)
            # Estructura del JSON simplificado
            print(trollandtoad_results)
            response = {
                    "nombre": nombref,
                    "expansionf": expansionf,
                    "tcg": tcgplayer_results,
                    "troll": trollandtoad_results,
                    "url": imagenf
            }

            return jsonify(response)

    except Exception as e:
        return jsonify({"error": f"Error en el servidor: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
