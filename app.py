import os
import re
import json
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import RSLPStemmer
import PyPDF2
from io import BytesIO
import google.generativeai as genai

load_dotenv()

nltk.download("stopwords", quiet=True)
nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)
nltk.download("rslp", quiet=True)

app = Flask(__name__, static_folder="static", static_url_path="")
CORS(app)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
gemini_model = None

if GEMINI_API_KEY and GEMINI_API_KEY != "your_gemini_api_key_here":
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-1.5-flash")


def preprocessar(texto):
    texto = texto.lower()
    texto = re.sub(r"[^a-záéíóúàâêôãõüç\s]", " ", texto)
    tokens = word_tokenize(texto, language="portuguese")
    stops = set(stopwords.words("portuguese")) | set(stopwords.words("english"))
    tokens = [t for t in tokens if t not in stops and len(t) > 2]
    stemmer = RSLPStemmer()
    stems = [stemmer.stem(t) for t in tokens]
    return tokens, stems


def classificar_por_regras(tokens, stems):
    palavras_produtivas = {
        "suporte", "problema", "erro", "ajuda", "solicitação", "pedido",
        "atualização", "urgente", "pagamento", "fatura", "boleto", "dúvida",
        "sistema", "acesso", "bug", "falha", "reclamação", "cancelamento",
    }
    palavras_improdutivas = {
        "feliz", "natal", "parabéns", "obrigado", "obrigada", "festa",
        "felicidades", "gratidão", "agradecimento", "abraço",
    }
    todos = set(tokens + stems)
    prod = len(todos & palavras_produtivas)
    improd = len(todos & palavras_improdutivas)
    return "Produtivo" if prod >= improd else "Improdutivo"


def analisar_com_gemini(texto):
    prompt = f"""
Você é um assistente de análise de emails de uma empresa financeira.

Analise o email abaixo e responda SOMENTE em JSON válido:
{{
  "categoria": "Produtivo" ou "Improdutivo",
  "motivo": "uma frase explicando",
  "resposta": "resposta automática profissional em português"
}}

- Produtivo: requer ação (suporte, dúvidas, pagamentos, pendências)
- Improdutivo: não requer ação (felicitações, agradecimentos)

Email:
---
{texto[:3000]}
---

Retorne apenas o JSON.
"""
    resposta = gemini_model.generate_content(prompt)
    raw = resposta.text.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/classificar", methods=["POST"])
def classificar():
    texto = ""

    if "arquivo" in request.files:
        arquivo = request.files["arquivo"]
        dados = arquivo.read()
        nome = arquivo.filename.lower()
        if nome.endswith(".pdf"):
            leitor = PyPDF2.PdfReader(BytesIO(dados))
            texto = "\n".join(p.extract_text() or "" for p in leitor.pages)
        elif nome.endswith(".txt"):
            texto = dados.decode("utf-8", errors="ignore")
        else:
            return jsonify({"erro": "Formato inválido. Use .txt ou .pdf"}), 400
    else:
        dados = request.get_json(silent=True) or {}
        texto = dados.get("texto", "").strip()

    if len(texto) < 10:
        return jsonify({"erro": "Texto muito curto para análise."}), 400

    tokens, stems = preprocessar(texto)

    if gemini_model:
        try:
            resultado = analisar_com_gemini(texto)
            return jsonify({
                "categoria": resultado.get("categoria", "—"),
                "motivo": resultado.get("motivo", "—"),
                "resposta": resultado.get("resposta", "—"),
                "motor": "Gemini AI",
            })
        except Exception as e:
            print("Erro Gemini:", e)

    categoria = classificar_por_regras(tokens, stems)
    if categoria == "Produtivo":
        resposta_auto = (
            "Prezado(a),\n\nAgradecemos o contato. Sua solicitação foi recebida e será "
            "analisada pela equipe responsável em até 2 dias úteis.\n\nAtenciosamente,\nEquipe de Atendimento"
        )
    else:
        resposta_auto = (
            "Prezado(a),\n\nMuito obrigado pela mensagem! "
            "É sempre um prazer receber palavras tão gentis.\n\nAtenciosamente,\nEquipe de Atendimento"
        )

    return jsonify({
        "categoria": categoria,
        "motivo": "Classificado por palavras-chave (sem IA).",
        "resposta": resposta_auto,
        "motor": "Regras",
    })


@app.route("/status")
def status():
    return jsonify({"gemini": gemini_model is not None})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=True)
