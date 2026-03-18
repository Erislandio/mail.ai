import os
import re
import json
import logging
from io import BytesIO
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import RSLPStemmer, WordNetLemmatizer
import PyPDF2
import google.generativeai as genai

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_nltk_data():
    packages = ["stopwords", "punkt", "punkt_tab", "wordnet", "omw-1.4", "rslp"]
    for pkg in packages:
        try:
            nltk.download(pkg, quiet=True)
        except Exception as e:
            logger.warning(f"Erro ao baixar pacote NLTK '{pkg}': {e}")

download_nltk_data()

app = Flask(__name__, static_folder="static", static_url_path="", template_folder="static")
CORS(app)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
gemini_model = None

if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel("gemini-1.5-flash")
        logger.info("Gemini configurado com sucesso.")
    except Exception as e:
        logger.error(f"Erro ao configurar Gemini: {e}")
else:
    logger.warning("GEMINI_API_KEY não configurada. Usando classificação por regras.")


def preprocess_text(text):
    text_lower = text.lower()
    text_clean = re.sub(r"[^a-záéíóúàâêôãõüçñ\s]", " ", text_lower)
    text_clean = re.sub(r"\s+", " ", text_clean).strip()

    try:
        tokens = word_tokenize(text_clean, language="portuguese")
    except Exception:
        tokens = text_clean.split()

    try:
        pt_stops = set(stopwords.words("portuguese"))
        en_stops = set(stopwords.words("english"))
        stop_words = pt_stops | en_stops
    except Exception:
        stop_words = set()

    filtered = [t for t in tokens if t not in stop_words and len(t) > 2]

    try:
        stemmer = RSLPStemmer()
        stems = [stemmer.stem(t) for t in filtered]
    except Exception:
        stems = filtered

    try:
        lemmatizer = WordNetLemmatizer()
        lemmas = [lemmatizer.lemmatize(t) for t in filtered]
    except Exception:
        lemmas = filtered

    return {
        "original": text,
        "clean": text_clean,
        "tokens": tokens,
        "filtered_tokens": filtered,
        "stems": stems,
        "lemmas": lemmas,
    }


PRODUCTIVE_KEYWORDS = {
    "suporte", "problema", "erro", "ajuda", "solicitação", "requisição",
    "pedido", "atualização", "status", "prazo", "urgente", "pendente",
    "contrato", "pagamento", "fatura", "boleto", "cobrança", "dúvida",
    "informação", "relatório", "reunião", "proposta", "orçamento",
    "sistema", "acesso", "senha", "bug", "falha", "incidente", "ticket",
    "reclamação", "cancelamento", "reembolso", "entrega",
    "support", "issue", "problem", "request", "help", "urgent", "payment",
    "invoice", "contract", "update", "error",
}

UNPRODUCTIVE_KEYWORDS = {
    "feliz", "natal", "ano", "novo", "parabéns", "aniversário", "obrigado",
    "obrigada", "grato", "grata", "abraço", "churrasco", "festa", "confraternização",
    "ótimo", "excelente", "maravilhoso", "boas", "festas", "sucesso",
    "felicidades", "alegria", "gratidão", "agradecimento",
    "congratulations", "happy", "birthday", "merry", "christmas", "thank",
    "thanks", "grateful", "awesome", "great", "party", "celebration",
}


def rule_based_classify(preprocessed):
    tokens = set(preprocessed["filtered_tokens"] + preprocessed["stems"])
    prod_hits = tokens & PRODUCTIVE_KEYWORDS
    unprod_hits = tokens & UNPRODUCTIVE_KEYWORDS

    if len(prod_hits) >= len(unprod_hits):
        category = "Produtivo"
        confidence = min(0.55 + len(prod_hits) * 0.05, 0.85)
        reason = f"Palavras-chave produtivas detectadas: {', '.join(list(prod_hits)[:5])}"
    else:
        category = "Improdutivo"
        confidence = min(0.55 + len(unprod_hits) * 0.05, 0.85)
        reason = f"Palavras-chave improdutivas detectadas: {', '.join(list(unprod_hits)[:5])}"

    return {"category": category, "confidence": round(confidence, 2), "reason": reason}


CLASSIFICATION_PROMPT = """
Você é um especialista em análise de emails corporativos para um setor financeiro.

Analise o email abaixo e responda EXCLUSIVAMENTE em JSON válido com a seguinte estrutura:
{{
  "category": "Produtivo" ou "Improdutivo",
  "confidence": número entre 0.0 e 1.0,
  "reason": "breve explicação da classificação em português",
  "key_topics": ["tópico1", "tópico2"],
  "priority": "Alta", "Média" ou "Baixa",
  "suggested_response": "resposta automática profissional e completa em português, adequada ao email recebido"
}}

Definições:
- Produtivo: email que requer ação, resposta ou acompanhamento (suporte, pendências, dúvidas, solicitações, relatórios, contratos, etc.)
- Improdutivo: email que NÃO requer ação imediata (felicitações, agradecimentos, mensagens sociais, spam)

EMAIL PARA ANÁLISE:
---
{email_text}
---

IMPORTANTE: Retorne APENAS o JSON, sem markdown, sem blocos de código, sem explicações adicionais.
"""


def classify_with_gemini(email_text):
    if not gemini_model:
        return None

    try:
        prompt = CLASSIFICATION_PROMPT.format(email_text=email_text[:4000])
        response = gemini_model.generate_content(prompt)
        raw = response.text.strip()

        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        result = json.loads(raw)
        required = {"category", "confidence", "reason", "suggested_response"}
        if not required.issubset(result.keys()):
            raise ValueError("Campos obrigatórios ausentes na resposta da IA")
        return result
    except Exception as e:
        logger.error(f"Erro na classificação Gemini: {e}")
        return None


RESPONSE_PROMPT = """
Você é um assistente de atendimento corporativo de uma empresa financeira.

O email abaixo foi classificado como "{category}".

Gere uma resposta automática profissional, empática e adequada em português brasileiro.
A resposta deve:
- Ser cordial e profissional
- Abordar o contexto do email
- Ser concisa (máximo 5 parágrafos)
- Incluir saudação e despedida

{additional_instruction}

EMAIL ORIGINAL:
---
{email_text}
---

Retorne SOMENTE o texto da resposta, sem formatação especial.
"""

ADDITIONAL_INSTRUCTIONS = {
    "Produtivo": (
        "Como é um email PRODUTIVO, confirme o recebimento, "
        "indique que o caso será tratado com prioridade e forneça um prazo estimado de retorno."
    ),
    "Improdutivo": (
        "Como é um email IMPRODUTIVO (social/felicitações), "
        "responda de forma calorosa, breve e agradecendo a mensagem."
    ),
}


def generate_response_with_gemini(email_text, category):
    if not gemini_model:
        return generate_fallback_response(category)

    try:
        prompt = RESPONSE_PROMPT.format(
            category=category,
            additional_instruction=ADDITIONAL_INSTRUCTIONS.get(category, ""),
            email_text=email_text[:3000],
        )
        response = gemini_model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Erro ao gerar resposta com Gemini: {e}")
        return generate_fallback_response(category)


def generate_fallback_response(category):
    if category == "Produtivo":
        return (
            "Prezado(a),\n\n"
            "Agradecemos o contato e confirmamos o recebimento de sua mensagem.\n\n"
            "Sua solicitação foi registrada em nosso sistema e será analisada pela equipe responsável. "
            "Retornaremos em até 2 dias úteis com uma atualização sobre o andamento do seu caso.\n\n"
            "Caso necessite de atendimento urgente, entre em contato pelo telefone (11) 0000-0000.\n\n"
            "Atenciosamente,\nEquipe de Atendimento Financeiro"
        )
    else:
        return (
            "Prezado(a),\n\n"
            "Muito obrigado pela gentil mensagem! "
            "É sempre um prazer receber palavras tão carinhosas da nossa comunidade.\n\n"
            "Desejamos a você também todo o sucesso e felicidades!\n\n"
            "Atenciosamente,\nEquipe de Atendimento Financeiro"
        )


def extract_text_from_pdf(file_bytes):
    try:
        reader = PyPDF2.PdfReader(BytesIO(file_bytes))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n".join(pages).strip()
    except Exception as e:
        raise ValueError(f"Falha ao ler PDF: {e}")


def extract_text_from_txt(file_bytes):
    for enc in ("utf-8", "latin-1", "cp1252"):
        try:
            return file_bytes.decode(enc).strip()
        except UnicodeDecodeError:
            continue
    raise ValueError("Não foi possível decodificar o arquivo de texto.")


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/api/classify", methods=["POST"])
def classify_email():
    email_text = ""

    if "file" in request.files:
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Nenhum arquivo selecionado."}), 400

        file_bytes = file.read()
        filename = file.filename.lower()

        if filename.endswith(".pdf"):
            try:
                email_text = extract_text_from_pdf(file_bytes)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
        elif filename.endswith(".txt"):
            try:
                email_text = extract_text_from_txt(file_bytes)
            except ValueError as e:
                return jsonify({"error": str(e)}), 400
        else:
            return jsonify({"error": "Formato não suportado. Use .txt ou .pdf"}), 400

    elif request.is_json:
        data = request.get_json()
        email_text = data.get("text", "").strip()
    else:
        email_text = request.form.get("text", "").strip()

    if not email_text:
        return jsonify({"error": "Nenhum texto de email fornecido."}), 400

    if len(email_text) < 5:
        return jsonify({"error": "O email é curto demais para análise."}), 400

    preprocessed = preprocess_text(email_text)
    ai_result = classify_with_gemini(email_text)

    if ai_result:
        category = ai_result.get("category", "Produtivo")
        confidence = ai_result.get("confidence", 0.75)
        reason = ai_result.get("reason", "")
        key_topics = ai_result.get("key_topics", [])
        priority = ai_result.get("priority", "Média")
        suggested_response = ai_result.get("suggested_response", "")
        ai_powered = True
    else:
        rb = rule_based_classify(preprocessed)
        category = rb["category"]
        confidence = rb["confidence"]
        reason = rb["reason"]
        key_topics = preprocessed["filtered_tokens"][:5]
        priority = "Média"
        suggested_response = generate_response_with_gemini(email_text, category)
        ai_powered = False

    return jsonify({
        "category": category,
        "confidence": confidence,
        "reason": reason,
        "key_topics": key_topics,
        "priority": priority,
        "suggested_response": suggested_response,
        "ai_powered": ai_powered,
        "preprocessing": {
            "original_length": len(email_text),
            "token_count": len(preprocessed["tokens"]),
            "filtered_token_count": len(preprocessed["filtered_tokens"]),
            "top_terms": preprocessed["filtered_tokens"][:10],
        },
    })


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "ai_enabled": gemini_model is not None,
        "version": "1.0.0",
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5001))
    debug = os.getenv("FLASK_DEBUG", "True").lower() == "true"
    app.run(host="0.0.0.0", port=port, debug=debug)
