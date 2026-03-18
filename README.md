# MailAI – Classificador Inteligente de Emails

Uma aplicação web com IA para classificar emails corporativos como **Produtivo** ou **Improdutivo** e gerar respostas automáticas.

## 🚀 Stack Técnica

- **Backend**: Python 3.11 + Flask
- **NLP**: NLTK (tokenização, stop words, stemming RSLP, lemmatização)
- **IA**: Google Gemini 1.5 Flash
- **Frontend**: HTML5 + CSS3 (glassmorphism) + JavaScript Vanilla
- **Deploy**: Render / Heroku / Railway

## ⚙️ Configuração Local

### 1. Clone e crie o ambiente virtual

```bash
cd /Users/erislandiosoares/projects/java/python
python3 -m venv venv
source venv/bin/activate
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure a chave da API Gemini

```bash
cp .env.example .env
# Edite .env e insira sua GEMINI_API_KEY
```

> Obtenha sua chave gratuita em: https://aistudio.google.com/app/apikey

### 4. Execute a aplicação

```bash
python app.py
```

Acesse: http://localhost:5000

## 🌐 Deploy na Nuvem (Render – Gratuito)

1. Crie conta em https://render.com
2. Conecte o repositório GitHub
3. Crie um **Web Service** com:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
4. Adicione a variável de ambiente: `GEMINI_API_KEY=sua_chave`
5. Deploy! 🎉

## 📁 Estrutura do Projeto

```
.
├── app.py              # Backend Flask + NLP + Gemini AI
├── requirements.txt    # Dependências Python
├── Procfile            # Configuração para deploy
├── runtime.txt         # Versão Python
├── .env.example        # Template de variáveis de ambiente
└── static/
    ├── index.html      # Interface Web
    ├── style.css       # Estilos (glassmorphism, dark mode)
    └── app.js          # Lógica do frontend
```

## 🧠 Como Funciona

1. **Recepção**: Texto direto ou upload de `.txt`/`.pdf`
2. **Pré-processamento NLP**: Tokenização → remoção de stop words → stemming (RSLP) → lemmatização
3. **Classificação IA**: Gemini 1.5 Flash analisa o contexto e classifica
4. **Resposta**: Resposta profissional gerada automaticamente
5. **Fallback**: Se a API não estiver disponível, usa classificação baseada em regras/palavras-chave

## 🔑 Variáveis de Ambiente

| Variável | Obrigatória | Descrição |
|---|---|---|
| `GEMINI_API_KEY` | Sim* | Chave da API Google Gemini |
| `FLASK_DEBUG` | Não | Modo debug (padrão: True) |
| `PORT` | Não | Porta do servidor (padrão: 5000) |

*Sem a chave, o sistema usa classificação por regras (funciona, mas com menor precisão)
