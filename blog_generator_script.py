import os
import time
import json
import re
import random
import base64
from anthropic import Anthropic
import requests
from dotenv import load_dotenv
from datetime import datetime, timedelta
from openai import OpenAI
import csv

load_dotenv()

# ========================================
# CONFIGURATION
# ========================================
SUJETS_CSV_FILE = "sujets.csv"
SUJETS_TRAITES_FILE = "sujets_traites.csv"

def marquer_sujet_comme_traite(sujet, statut="succès"):
    """Marque un sujet comme traité dans le fichier CSV"""
    if not os.path.exists(SUJETS_TRAITES_FILE):
        with open(SUJETS_TRAITES_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['sujet', 'date', 'statut'])
    
    with open(SUJETS_TRAITES_FILE, 'a', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([sujet, datetime.now().isoformat(), statut])

def charger_sujets_depuis_csv():
    """Charge les sujets depuis le fichier CSV avec gestion multi-encodage"""
    if not os.path.exists(SUJETS_CSV_FILE):
        print(f"ERREUR : Le fichier {SUJETS_CSV_FILE} n'existe pas")
        return []
    
    sujets = []
    encodages = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    
    for encoding in encodages:
        try:
            with open(SUJETS_CSV_FILE, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                all_rows = list(reader)
                
                if all_rows and all_rows[0]:
                    premiere_ligne = all_rows[0][0].strip().lower()
                    if premiere_ligne in ['sujet', 'sujets', 'titre', 'titres', 'topic', 'topics', 'article', 'articles']:
                        print(f"ℹ️ En-tête détecté et ignoré : '{all_rows[0][0]}'")
                        all_rows = all_rows[1:]
                
                for row in all_rows:
                    if row and row[0].strip() and len(row[0].strip()) > 5:
                        sujets.append(row[0].strip())
            
            print(f"✅ Fichier CSV chargé avec l'encodage : {encoding}")
            print(f"✅ {len(sujets)} sujet(s) valide(s) trouvé(s)")
            return sujets
        except (UnicodeDecodeError, UnicodeError):
            sujets = []
            continue
        except Exception as e:
            print(f"⚠️ Erreur avec l'encodage {encoding}: {e}")
            sujets = []
            continue
    
    print(f"ERREUR : Impossible de lire le fichier {SUJETS_CSV_FILE}")
    return []

def supprimer_sujet_du_csv(sujet_a_supprimer):
    """Supprime une ligne du fichier CSV"""
    if not os.path.exists(SUJETS_CSV_FILE):
        return
    
    encodages = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
    encoding_detecte = None
    lignes = []
    
    for encoding in encodages:
        try:
            with open(SUJETS_CSV_FILE, 'r', encoding=encoding) as f:
                reader = csv.reader(f)
                lignes = list(reader)
                encoding_detecte = encoding
                break
        except:
            continue
    
    if not encoding_detecte:
        print("⚠️ Impossible de lire le fichier pour supprimer le sujet")
        return
    
    nouvelles_lignes = []
    sujet_lower = sujet_a_supprimer.lower().strip()
    
    for ligne in lignes:
        if ligne and ligne[0].strip():
            if ligne[0].strip().lower() != sujet_lower:
                nouvelles_lignes.append(ligne)
    
    try:
        with open(SUJETS_CSV_FILE, 'w', encoding=encoding_detecte, newline='') as f:
            writer = csv.writer(f)
            writer.writerows(nouvelles_lignes)
        print(f"✅ Sujet supprimé du fichier CSV")
    except Exception as e:
        print(f"⚠️ Erreur lors de la suppression : {e}")

def charger_config():
    config = {
        'mots_minimum': '900',
        'mots_maximum': '1200',
        'url_lien': 'https://walensky-shop.fr/collections/tableau-paysages',
        'ancre_lien': 'tableaux de paysages',
        'tags': 'paysage, art',
        'collection_id': '',
        'theme': 'art et decoration',
        'BLOG_ID': '102910656846'
    }
    try:
        with open('config_articles.txt', 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()
    except:
        pass
    return config

CONFIG = charger_config()

CLAUDE_API_KEY = os.getenv('CLAUDE_API_KEY')
SHOPIFY_STORE = os.getenv('SHOPIFY_STORE')
SHOPIFY_TOKEN = os.getenv('SHOPIFY_TOKEN')
BLOG_ID = CONFIG.get('BLOG_ID', CONFIG.get('blog_id', '102910656846'))
GPT_API_KEY = os.getenv('GPT_API')

client = Anthropic(api_key=CLAUDE_API_KEY)

# ========================================
# GENERATION D'IMAGE DALL-E 3
# ========================================

def generer_image_dalle(sujet, article_data):
    """Génère une image avec DALL-E 3"""
    print("\n" + "=" * 60)
    print("GÉNÉRATION DE L'IMAGE DALL-E 3")
    print("=" * 60)
    
    if not GPT_API_KEY:
        print("ERREUR : Clé API GPT manquante")
        return None
    
    message_image = f"""ANALYSE D'ABORD LE SUJET, PUIS crée une image ULTRA-SPÉCIFIQUE.

ARTICLE :
Titre : {sujet}
Extrait : {article_data.get('extrait', '')}
Meta description : {article_data.get('meta_description', '')}

ÉTAPE 1 - ANALYSE OBLIGATOIRE DU SUJET :
Avant de créer le prompt, réponds à ces questions :
- Quel est le THÈME PRINCIPAL précis ? (pas juste "espace" mais "Romantisme du 19ème siècle + sublime cosmique")
- Quelle ÉPOQUE est concernée ? (années, siècle, période)
- Y a-t-il un ARTISTE/MOUVEMENT spécifique mentionné ? (nom, style)
- Quel est le CONCEPT CLÉ ? (symbolique, émotion, philosophie)
- Quels ÉLÉMENTS VISUELS sont caractéristiques de ce sujet précis ?

ÉTAPE 2 - CRÉER UN PROMPT UNIQUE basé sur cette analyse.

⚠️ RÈGLES CRITIQUES :
1. L'image doit illustrer LE SUJET PRÉCIS, pas le thème général
2. Si l'article parle d'une ÉPOQUE → l'image doit refléter cette époque spécifique
3. Si l'article parle d'un MOUVEMENT → l'image doit montrer le style visuel de ce mouvement
4. Si l'article parle d'un CONCEPT → l'image doit représenter CE concept, pas un concept voisin
5. JAMAIS de galeries de musée modernes avec plusieurs tableaux sauf si l'article parle spécifiquement de galeries

EXEMPLES CONCRETS DE SPÉCIFICITÉ :

❌ MAUVAIS pour "Le Sublime Cosmique : du Romantisme du 19ème siècle aux murs contemporains" :
"Modern art gallery with multiple cosmic paintings on walls, museum setting"
→ Problème : Galerie moderne générique, ne montre PAS le lien Romantisme 19ème/contemporain

✅ BON pour le même sujet :
"Romantic 19th century painting in Caspar David Friedrich style: lone figure in period clothing standing on rocky cliff, gazing at swirling cosmic nebula in dramatic night sky, oil painting technique, sublime aesthetic, contrast between human smallness and cosmic vastness, 1830s romantic period atmosphere"
→ Pourquoi c'est bon : Montre SPÉCIFIQUEMENT le romantisme du 19ème + le concept de sublime + l'aspect cosmique

❌ MAUVAIS pour "L'influence de Gustav Klimt sur la décoration Art Nouveau" :
"Elegant living room with golden abstract painting"

✅ BON pour le même sujet :
"Close-up of Art Nouveau decorative panel in Gustav Klimt style, intricate golden leaf patterns, Byzantine mosaic influences, organic flowing lines, ornamental spirals, rich gold and emerald colors, 1900s Vienna Secession aesthetic"

❌ MAUVAIS pour "Le mouvement Space Age des années 60" :
"Modern interior with space artwork"

✅ BON pour le même sujet :
"Vintage 1960s Space Age interior photograph, retro-futuristic design, white molded plastic furniture, chrome accents, orange and turquoise color scheme, geometric space-themed artwork, Sputnik chandelier, atomic age aesthetic, mid-century modern"

MÉTHODE POUR CRÉER UN PROMPT SPÉCIFIQUE :

1. IDENTIFIE LES MOTS-CLÉS ULTRA-PRÉCIS du titre :
   - Noms propres (artistes, lieux, mouvements)
   - Périodes exactes (années, siècles, époques)
   - Concepts philosophiques/artistiques
   - Styles visuels caractéristiques

2. CHOISIS LA REPRÉSENTATION VISUELLE APPROPRIÉE :
   
   Si l'article parle d'un MOUVEMENT HISTORIQUE :
   → Crée une scène/œuvre DANS CE STYLE D'ÉPOQUE (pas moderne)
   
   Si l'article parle d'un ARTISTE :
   → Montre son style SPÉCIFIQUE, ses œuvres emblématiques, sa technique
   
   Si l'article parle d'un CONCEPT (ex: le Sublime) :
   → Représentation visuelle de CE concept avec les codes de l'époque mentionnée
   
   Si l'article parle d'une ÉVOLUTION TEMPORELLE :
   → Focus sur l'époque ORIGINALE ou une fusion visible des époques
   
   Si l'article parle de SYMBOLIQUE :
   → Représentation iconographique précise du symbole

3. INTÈGRE DES DÉTAILS D'ÉPOQUE/STYLE :
   - Techniques artistiques de la période (huile, aquarelle, gravure, etc.)
   - Palette de couleurs caractéristique
   - Éléments architecturaux/décoratifs d'époque
   - Codes visuels du mouvement
   - Atmosphère spécifique

FORMATS DE PROMPTS EFFICACES :

Pour articles HISTORIQUES :
"[Period-specific scene/artwork], [artistic movement style], [characteristic colors], [era-specific elements], [authentic period atmosphere], [relevant technique], [key visual concepts]"

Pour articles sur ARTISTES :
"[Artwork type] in [Artist Full Name] distinctive style, [signature technique], [characteristic subject matter], [specific color palette], [period], [unique visual elements]"

Pour articles sur CONCEPTS :
"[Visual representation of concept], [relevant artistic style], [period-appropriate execution], [symbolic elements], [emotional atmosphere], [technical approach]"

CONSIGNES TECHNIQUES :
- Style : Photographie hyperréaliste OU peinture photographiée selon le sujet
- Qualité : Ultra-détaillée, textures authentiques
- Éclairage : Adapté au sujet (dramatique pour Romantisme, doux pour minimalisme, etc.)
- Ambiance : COHÉRENTE avec l'époque/mouvement
- Éviter : Anachronismes, mélanges d'époques incohérents, textes, logos
- Format : 1792x1024 paysage

CONSIGNES POUR L'ALT TEXT :
- Mentionne l'ÉPOQUE/MOUVEMENT/ARTISTE spécifique
- Décris les éléments visuels caractéristiques
- 10-15 mots précis
- En français

CONSIGNES POUR LE NOM DE FICHIER :
- Inclut les mots-clés SPÉCIFIQUES (noms, époques, mouvements)
- Pas d'accents, tirets entre les mots
- Exemple : sublime-cosmique-romantisme-19eme-siecle.jpg

Réponds au format JSON :
{{
    "analyse_sujet": "Analyse en 2-3 phrases des éléments clés spécifiques du sujet",
    "prompt_image": "Prompt ULTRA-SPÉCIFIQUE détaillé en anglais, parfaitement adapté",
    "alt_text": "Texte alternatif précis en français",
    "filename": "nom-fichier-specifique.jpg"
}}"""

    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=1000,
            messages=[{"role": "user", "content": message_image}]
        )
        
        image_info = None
        for block in response.content:
            if block.type == "text":
                texte = block.text
                try:
                    image_info = json.loads(texte)
                except:
                    json_match = re.search(r'```json\s*(\{.*?\})\s*```', texte, re.DOTALL)
                    if json_match:
                        image_info = json.loads(json_match.group(1))
                    else:
                        json_match = re.search(r'\{.*\}', texte, re.DOTALL)
                        if json_match:
                            image_info = json.loads(json_match.group(0))
        
        if not image_info:
            return None
        
        print(f"--- Génération en cours...")
        
        openai_client = OpenAI(api_key=GPT_API_KEY)
        response_image = openai_client.images.generate(
            model="dall-e-3",
            prompt=image_info['prompt_image'] + " | Photorealistic, ultra-detailed, professional photography, high-end editorial style, realistic textures and lighting, indistinguishable from real photo",
            size="1792x1024",
            quality="hd",
            n=1
        )
        
        if not response_image.data or not response_image.data[0].url:
            return None
        
        image_url = response_image.data[0].url
        image_response = requests.get(image_url)
        image_response.raise_for_status()
        image_b64 = base64.b64encode(image_response.content).decode('utf-8')
        
        print("--- Image générée avec succès !")
        
        return {
            "base64": image_b64,
            "alt_text": image_info['alt_text'],
            "filename": image_info['filename']
        }
        
    except Exception as e:
        print(f"ERREUR : {e}")
        return None

# ========================================
# GENERATION D'ARTICLE
# ========================================

INSTRUCTION_PERSONA = """
═══════════════════════════════════════════════════════════════
ÉTAPE 1 - CRÉATION DE TON PERSONA (OBLIGATOIRE AVANT D'ÉCRIRE)
═══════════════════════════════════════════════════════════════

Analyse le sujet et INVENTE le persona le plus pertinent pour en parler.

❌ PAS de persona générique comme :
- "décorateur d'intérieur"
- "passionné d'art"
- "expert en design"

✅ Crée un persona SPÉCIFIQUE et ORIGINAL adapté au sujet :

EXEMPLES PAR THÉMATIQUE (pour inspiration uniquement) :

Pour la décoration/aménagement :
- "architecte d'intérieur lyonnais, 15 ans rénovations appartements haussmanniens"
- "home stager parisienne, 300+ projets valorisation immobilière"
- "designer freelance, spécialiste optimisation petits espaces urbains"

Pour l'art/culture :
- "galeriste bruxelloise, 20 ans spécialisation art contemporain belge"
- "collectionneur passionné, 12 pays visités, consultant musées régionaux"
- "historien de l'art, doctorat sur les mouvements impressionnistes"

Pour le lifestyle/bien-être :
- "coach feng shui, formée Hong Kong, 8 ans pratique en Europe"
- "ergonome du habitat, spécialiste confort et santé domestique"
- "minimaliste convertie, blogueuse lifestyle depuis 10 ans"

Pour les styles spécifiques :
- "antiquaire 3ème génération, expert mobilier Art Déco"
- "restaurateur de patrimoine, 25 ans sur bâtiments classés"
- "designer industriel, spécialiste upcycling matériaux"

⚠️ IMPORTANT : Ces exemples sont juste pour te montrer le NIVEAU DE PRÉCISION attendu.
Tu dois inventer TON PROPRE persona parfaitement adapté au sujet traité.

Ton persona influence NATURELLEMENT :
→ Vocabulaire (technique/poétique/historique/sensoriel)
→ Structure (chronologique/analytique/anecdotique)
→ Exemples (personnels/académiques/pratiques)
→ Ton (précis/passionné/pédagogue/immersif)

⚠️ CRITIQUE : Écris TOUT l'article avec cette voix unique.
Ne mentionne JAMAIS ton persona dans l'article.
Le lecteur ne doit pas savoir que tu joues un rôle.

═══════════════════════════════════════════════════════════════

"""

PROMPT_TEMPLATE = f"""Tu écris pour un magazine de décoration lifestyle haut de gamme.

SUJET : {{sujet}}

═══════════════════════════════════════════════════════════════
TON RÔLE
═══════════════════════════════════════════════════════════════

Tu es un PASSIONNÉ qui raconte des histoires captivantes.
Ton lecteur ne connaît RIEN au sujet et cherche de l'inspiration.
Ton job : le captiver, le faire rêver, lui donner envie d'agir.

═══════════════════════════════════════════════════════════════
OPTIMISATION NATURELLE DU VOCABULAIRE
═══════════════════════════════════════════════════════════════

Le sujet doit être présent naturellement avec ses variations.
Vise 25-35 mentions organiques sur {CONFIG['mots_minimum']}-{CONFIG['mots_maximum']} mots.

═══════════════════════════════════════════════════════════════
STRUCTURE NARRATIVE ({CONFIG['mots_minimum']}-{CONFIG['mots_maximum']} mots)
═══════════════════════════════════════════════════════════════

PAS DE H1 - Shopify gère le titre.

INTRODUCTION (150-200 mots)
1. Accroche émotionnelle
2. RÉPONSE DIRECTE : "Voici ce que [sujet] apporte : [3 bénéfices]"
3. Frustration du lecteur
4. Rassurance
5. Promesse claire

CORPS (4-6 sections H2)
Alterne H2 créatifs/engageants (50%) et informatifs/optimisés (50%)

MISE EN FORME HTML :
- H2 : <h2 style='color: #1BA39C;'>Titre</h2>
- H3 : <h3 style='background: linear-gradient(90deg, #1BA39C, #4CAF50); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;'>Sous-titre</h3>
- Gras : <strong>concept</strong>
- Liens : <a href='URL' style='color: #1BA39C;'>texte</a>

⚠️ RÈGLE ABSOLUE HTML : UNIQUEMENT des guillemets simples ' dans TOUT le HTML
❌ INTERDIT : <a href="URL"> ou <p style="color: red;">
✅ OBLIGATOIRE : <a href='URL'> et <p style='color: red;'>

CALL-TO-ACTION (avant conclusion) :
<p style='text-align: center; margin: 40px 0; padding: 30px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); border-radius: 12px;'>
<strong style='font-size: 18px; color: #1BA39C;'>[Phrase accroche]</strong><br>
<span style='font-size: 16px; line-height: 1.6;'>Découvrez notre collection exclusive de <a href='{CONFIG['url_lien']}' style='color: #1BA39C; font-weight: bold; text-decoration: none;'>{CONFIG['ancre_lien']}</a> qui [bénéfice].</span>
</p>

CONCLUSION (100-150 mots)
Visualisation de la transformation + action concrète

FAQ (3 questions)
Questions de débutant avec réponses rassurantes (100-150 mots/réponse)

═══════════════════════════════════════════════════════════════
FORMAT JSON - RÈGLE ABSOLUE
═══════════════════════════════════════════════════════════════

⚠️ CRITIQUE : Le JSON échoue si tu utilises des guillemets doubles dans le HTML.

RÈGLE ABSOLUE SANS EXCEPTION :
- Dans article_html : UNIQUEMENT guillemets simples ' 
- JAMAIS de guillemets doubles "
- Vérifie CHAQUE attribut HTML avant d'envoyer

EXEMPLES :
✅ CORRECT : <h2 style='color: #1BA39C;'>Titre</h2>
✅ CORRECT : <a href='https://url.com' style='color: #1BA39C;'>Lien</a>
✅ CORRECT : <p style='font-size: 16px; line-height: 1.6;'>Texte</p>

❌ INCORRECT : <h2 style="color: #1BA39C;">Titre</h2>
❌ INCORRECT : <a href="https://url.com">Lien</a>

Si tu mets UN SEUL guillemet double, le JSON sera cassé et l'article sera perdu

```json
{{{{
  "article_html": "HTML complet sur une ligne",
  "meta_titre": "Max 60 caractères",
  "meta_description": "Max 160 caractères",
  "extrait": "200-250 caractères",
  "faq": [
    {{{{"question": "Question ?", "reponse": "Réponse"}}}},
    {{{{"question": "Question ?", "reponse": "Réponse"}}}},
    {{{{"question": "Question ?", "reponse": "Réponse"}}}}
  ]
}}}}
```

Maintenant, écris un article CAPTIVANT : {{sujet}}"""

def generer_article(sujet):
    """Génère un article"""
    print("\n" + "=" * 60)
    print("GÉNÉRATION DE L'ARTICLE")
    print("=" * 60)
    print(f"Sujet : {sujet}\n")
    
    if not sujet or len(sujet.strip()) < 5:
        return None
    
    prompt_complet = INSTRUCTION_PERSONA + PROMPT_TEMPLATE
    
    try:
        print("⏳ Envoi à Claude...")
        message = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=16000,
            messages=[{"role": "user", "content": prompt_complet.format(sujet=sujet)}],
            timeout=300.0
        )
        
        print("✅ Réponse reçue")
        response_text = message.content[0].text
        
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\{[\s\S]*"article_html"[\s\S]*\}', response_text)
            if json_match:
                json_str = json_match.group(0)
            else:
                json_str = response_text
        
        article_start = json_str.find('"article_html"')
        if article_start != -1:
            meta_titre_pos = json_str.find('"meta_titre"', article_start)
            if meta_titre_pos != -1:
                article_section = json_str[article_start:meta_titre_pos]
                article_section_clean = article_section.replace('\\"', "'")
                json_str = json_str[:article_start] + article_section_clean + json_str[meta_titre_pos:]
        
        try:
            article_data = json.loads(json_str, strict=False)
        except:
            json_str_clean = json_str.replace('\n', ' ').replace('\r', ' ')
            article_data = json.loads(json_str_clean, strict=False)
        
        text_content = re.sub(r'<[^>]+>', '', article_data['article_html'])
        word_count = len(text_content.split())
        print(f"✅ Article généré : ~{word_count} mots")
        
        return article_data
        
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return None

def recuperer_produits_aleatoires(collection_id, nombre=2):
    """Récupère des produits aléatoires"""
    if not collection_id:
        return []
    
    try:
        headers = {"X-Shopify-Access-Token": SHOPIFY_TOKEN}
        url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/2024-01/collections/{collection_id}/products.json?limit=250"
        
        response = requests.get(url, headers=headers)
        
        if response.status_code != 200:
            return []
        
        products = response.json().get('products', [])
        products_with_images = [p for p in products if p.get('images') and len(p['images']) > 0]
        
        if not products_with_images:
            return []
        
        selected = random.sample(products_with_images, min(nombre, len(products_with_images)))
        
        produits_info = []
        for product in selected:
            image = product['images'][0]
            produits_info.append({
                'image_url': image['src'],
                'image_alt': image.get('alt', product['title']),
                'product_url': f"https://walensky-shop.fr/products/{product['handle']}"
            })
        
        return produits_info
        
    except:
        return []

def inserer_images_produits(html_content, produits_info):
    """Insère les images produits après le 2ème H2 et le 4ème H2"""
    if not produits_info:
        return html_content
    
    h2_pattern = re.compile(r'<h2[^>]*>.*?</h2>', re.DOTALL)
    h2_matches = list(h2_pattern.finditer(html_content))
    
    if len(h2_matches) < 2:
        return html_content
    
    positions_insertion = []
    
    # Après le 2ème H2 : trouver le dernier </p> de cette section
    if len(h2_matches) >= 2:
        pos_apres_h2_2 = h2_matches[1].end()
        # Chercher jusqu'au prochain H2 ou la fin
        if len(h2_matches) >= 3:
            next_h2_pos = h2_matches[2].start()
            last_p = html_content.rfind('</p>', pos_apres_h2_2, next_h2_pos)
        else:
            last_p = html_content.rfind('</p>', pos_apres_h2_2)
        
        if last_p != -1:
            positions_insertion.append(last_p + 4)
    
    # Après le 4ème H2 : trouver le dernier </p> de cette section
    if len(h2_matches) >= 4 and len(produits_info) >= 2:
        pos_apres_h2_4 = h2_matches[3].end()
        # Chercher jusqu'au prochain H2 ou la fin
        if len(h2_matches) >= 5:
            next_h2_pos = h2_matches[4].start()
            last_p = html_content.rfind('</p>', pos_apres_h2_4, next_h2_pos)
        else:
            last_p = html_content.rfind('</p>', pos_apres_h2_4)
        
        if last_p != -1:
            positions_insertion.append(last_p + 4)
    
    # Insérer en ordre inverse pour ne pas décaler les positions
    for i, pos in enumerate(reversed(positions_insertion)):
        if i < len(produits_info):
            produit = produits_info[-(i+1)]
            image_html = f'\n<div style="text-align: center; margin: 40px 0;"><a href="{produit["product_url"]}" target="_blank"><img src="{produit["image_url"]}" alt="{produit["image_alt"]}" style="max-width: 640px; width: 100%; height: auto; border-radius: 8px; display: block; margin-left: auto; margin-right: auto;"></a></div>\n'
            html_content = html_content[:pos] + image_html + html_content[pos:]
    
    return html_content

def publier_sur_shopify(sujet, article_data, image_data=None):
    """Crée et publie l'article"""
    print("\n" + "=" * 60)
    print("PUBLICATION SUR SHOPIFY")
    print("=" * 60)
    
    collection_id = CONFIG.get('collection_id', '')
    produits_info = recuperer_produits_aleatoires(collection_id, 2) if collection_id else []
    
    article_html = inserer_images_produits(article_data['article_html'], produits_info)
    tags_string = CONFIG.get('tags', '')
    
    url = f"https://{SHOPIFY_STORE}.myshopify.com/admin/api/2024-10/blogs/{BLOG_ID}/articles.json"
    headers = {
        "X-Shopify-Access-Token": SHOPIFY_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "article": {
            "title": sujet,
            "author": "Walensky",
            "body_html": article_html,
            "summary_html": article_data['extrait'],
            "published": True,
            "tags": tags_string,
            "metafields": [
                {
                    "namespace": "global",
                    "key": "description_tag",
                    "value": article_data['meta_description'],
                    "type": "single_line_text_field"
                },
                {
                    "namespace": "global",
                    "key": "title_tag",
                    "value": article_data['meta_titre'],
                    "type": "single_line_text_field"
                }
            ]
        }
    }
    
    if image_data:
        payload["article"]["image"] = {
            "attachment": image_data['base64'],
            "alt": image_data['alt_text'],
            "filename": image_data['filename']
        }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 201:
            print(f"❌ Erreur Shopify ({response.status_code})")
            return False
        
        article_id = response.json()['article']['id']
        print(f"✅ Article publié (ID: {article_id})")
        return True
            
    except Exception as e:
        print(f"❌ Erreur : {e}")
        return False

def main():
    """Génère UN SEUL article"""
    print("=" * 60)
    print("GÉNÉRATEUR D'ARTICLE")
    print("=" * 60)
    
    if not CLAUDE_API_KEY or not SHOPIFY_TOKEN:
        print("ERREUR : Clés API manquantes")
        return
    
    tous_les_sujets = charger_sujets_depuis_csv()
    
    if not tous_les_sujets:
        print("\n✅ TERMINÉ : Aucun sujet restant !")
        return
    
    sujet = tous_les_sujets[0]
    
    print(f"\n📝 Sujet : {sujet}")
    print(f"📊 Restants : {len(tous_les_sujets) - 1}")
    
    print("\n" + "=" * 60)
    
    article_data = generer_article(sujet)
    
    if not article_data:
        print(f"\n❌ ÉCHEC génération")
        marquer_sujet_comme_traite(sujet, "échec_génération")
        return
    
    image_data = None
    if GPT_API_KEY:
        image_data = generer_image_dalle(sujet, article_data)
    
    if publier_sur_shopify(sujet, article_data, image_data):
        marquer_sujet_comme_traite(sujet, "succès")
        supprimer_sujet_du_csv(sujet)
        
        print("\n" + "=" * 60)
        print("✅ SUCCÈS COMPLET")
        print("=" * 60)
        print(f"📊 Sujets restants : {len(tous_les_sujets) - 1}")
        
        if len(tous_les_sujets) - 1 > 0:
            print(f"\n💡 Relancez pour le prochain !")
        else:
            print(f"\n🎉 Terminé !")
    else:
        marquer_sujet_comme_traite(sujet, "échec_publication")
        print("\n❌ ÉCHEC publication")

if __name__ == "__main__":
    main()