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
Você é um assistente especializado em análise de emails corporativos de uma empresa financeira.

Analise o email abaixo e responda SOMENTE em JSON válido com a seguinte estrutura:
{{
  "categoria": "Produtivo" ou "Improdutivo",
  "motivo": "Justificativa detalhada em 2 a 4 frases. Mencione especificamente o que no email levou à classificação: cite o assunto principal, a intenção do remetente, e por que isso requer (ou não) uma ação da equipe.",
  "resposta": "Resposta automática profissional em português, adequada ao contexto específico do email analisado, com saudação, corpo e assinatura."
}}

Critérios de classificação:
- Produtivo: requer ação da equipe (ex: suporte técnico, dúvidas sobre produtos/serviços, reclamações, pagamentos, pendências, solicitações de cancelamento ou atualização).
- Improdutivo: não requer ação operacional (ex: felicitações, agradecimentos, emails promocionais sem solicitação, mensagens de cortesia).

Email:
---
{texto[:3000]}
---

Retorne apenas o JSON, sem texto extra.
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

    palavras_produtivas = {
        "suporte", "problema", "erro", "ajuda", "solicitação", "pedido",
        "atualização", "urgente", "pagamento", "fatura", "boleto", "dúvida",
        "sistema", "acesso", "bug", "falha", "reclamação", "cancelamento",
    }
    palavras_improdutivas = {
        "feliz", "natal", "parabéns", "obrigado", "obrigada", "festa",
        "felicidades", "gratidão", "agradecimento", "abraço",
    }
    todos = set(tokens)
    gatilhos = todos & (palavras_produtivas if categoria == "Produtivo" else palavras_improdutivas)
    gatilhos_str = ", ".join(f'"{g}"' for g in sorted(gatilhos)) if gatilhos else "contexto geral"

    if categoria == "Produtivo":
        motivo_auto = (
            f"O email foi classificado como Produtivo pela detecção das palavras-chave: {gatilhos_str}. "
            "Isso indica que o remetente possui uma demanda operacional que requer atenção da equipe. "
            "A mensagem foi encaminhada para análise e resposta dentro do prazo estabelecido."
        )
        resposta_auto = (
            "Prezado(a),\n\nAgradecemos o seu contato. Recebemos a sua mensagem e ela já foi "
            "registrada em nosso sistema. Nossa equipe responsável irá analisá-la e retornará "
            "em até 2 dias úteis com uma resposta ou solução.\n\n"
            "Caso sua solicitação seja urgente, por favor ligue para nosso canal de atendimento.\n\n"
            "Atenciosamente,\nEquipe de Atendimento"
        )
    else:
        motivo_auto = (
            f"O email foi classificado como Improdutivo pela detecção das palavras-chave: {gatilhos_str}. "
            "A mensagem tem caráter de cortesia ou agradecimento e não requer nenhuma ação operacional "
            "por parte da equipe. Uma resposta de agradecimento foi gerada automaticamente."
        )
        resposta_auto = (
            "Prezado(a),\n\nMuito obrigado pela sua mensagem! "
            "É sempre um prazer recebermos palavras tão gentis e motivadoras. "
            "Sua consideração é muito bem-vinda e nos inspira a continuar oferecendo o melhor serviço.\n\n"
            "Atenciosamente,\nEquipe de Atendimento"
        )

    return jsonify({
        "categoria": categoria,
        "motivo": motivo_auto,
        "resposta": resposta_auto,
        "motor": "Regras",
    })


@app.route("/status")
def status():
    return jsonify({"gemini": gemini_model is not None})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5002))
    app.run(host="0.0.0.0", port=port, debug=True)
