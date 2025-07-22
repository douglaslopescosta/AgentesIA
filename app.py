# =============================================================================
# euGenIA - Agente para Reunião Comercial - RAG + Mapa Mental (Doug Costa)
# Passo 1 - instalar as depenências
#  - pip install -r requirements.txt
#  - streamlit
#  - openai>=1.0.0
#  - streamlit-markmap
#  - python-docx
# Descrição das Funcionalidades
# - Layout wide para o mapa mental ocupar toda a tela
# - Mapa mental interativo mais alto (height ajustado)
# - Download do markdown do mapa mental
# - Link para Markmap REPL só para mapas pequenos (grandes, baixe e cole manualmente)
# - Prompt de mapa mental garante estrutura: Reunião > Tema > Participante > Conteúdo > Resumo & Decisão
# =============================================================================

import streamlit as st
import openai
import os
import json
from streamlit_markmap import markmap
import urllib.parse

try:
    from docx import Document
except ImportError:
    Document = None

st.set_page_config(layout="wide")

# 1. Carregar API KEY
api_key = None
if os.path.exists("config.json"):
    with open("config.json") as f:
        config = json.load(f)
        api_key = config.get("OPENAI_API_KEY")
if not api_key and "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    st.error("API KEY não encontrada. Defina em config.json, .streamlit/secrets.toml ou como variável de ambiente OPENAI_API_KEY.")
    st.stop()

client = openai.OpenAI(api_key=api_key)

st.title("euGenIA - Análise de Reunião Comercial")
st.write(
    "Faça upload da transcrição da reunião em arquivo (.txt, .docx ou .vtt). "
    "Interaja via chat (respostas sempre em tópicos/listas) e gere o mapa mental na estrutura hierárquica desejada."
)

# Função para extrair texto do arquivo
def extrair_texto(uploaded_file):
    if uploaded_file.name.lower().endswith('.txt'):
        return uploaded_file.read().decode("utf-8")
    elif uploaded_file.name.lower().endswith('.vtt'):
        lines = uploaded_file.read().decode("utf-8").splitlines()
        texto = []
        for l in lines:
            if l.strip() == "" or "-->" in l or l.startswith("WEBVTT"):
                continue
            texto.append(l)
        return "\n".join(texto)
    elif uploaded_file.name.lower().endswith('.docx'):
        if Document is None:
            st.error("python-docx não instalado. Instale com: pip install python-docx")
            return ""
        doc = Document(uploaded_file)
        return "\n".join([p.text for p in doc.paragraphs if p.text.strip() != ""])
    else:
        return ""

# Upload obrigatório da transcrição
uploaded_file = st.file_uploader(
    "Envie o arquivo da transcrição (.txt, .docx, .vtt) para continuar:",
    type=["txt", "docx", "vtt"]
)

if uploaded_file is not None:
    transcricao = extrair_texto(uploaded_file)
    st.session_state["transcricao"] = transcricao

    # --------------------------
    # 1. Chat contextualizado RAG (em tópicos/listas)
    # --------------------------
    if uploaded_file is not None:
        nome_arquivo = uploaded_file.name
        st.header(f"Chat - RAG: ({nome_arquivo})")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    pergunta = st.text_input(
    "Pergunte algo sobre a reunião:",
    key="pergunta",
    max_chars=60,
    placeholder="Digite sua pergunta (máx. 60 caracteres)"
    )

    if st.button("Perguntar") and pergunta and transcricao.strip():
        chat_messages = [
            {"role": "system", "content": (
                "Você é um assistente que responde perguntas EXCLUSIVAMENTE com base na transcrição abaixo. "
                "FORMATE todas as respostas em tópicos, listas e sublistas (use bullets e numerais), de modo claro e estruturado. "
                "Sempre use Markdown para listas, e cite ou indique o trecho exato da transcrição quando possível."
            )},
            {"role": "user", "content": f"Transcrição: '''{transcricao}'''\nPergunta: {pergunta}"}
        ]
        with st.spinner('Gerando resposta...'):
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=chat_messages,
                temperature=0.4,
                max_tokens=2500
            )
            resposta = response.choices[0].message.content
            st.session_state.chat_history.append((pergunta, resposta))
            st.success("Resposta registrada!")

    st.subheader("Histórico do Chat")
    for q, a in st.session_state.chat_history:
        titulo = q if len(q) <= 60 else q[:57] + "..."
        with st.expander(f"❓ {titulo}"):
            st.markdown(a)

    # -------------------------
    # 2. Geração de Mapa Mental Estruturado
    # -------------------------
    st.markdown("---")
    st.header("Mapa Mental Navegável")

    if st.button("Gerar Mapa Mental") and transcricao.strip():
        prompt = f"""
                    Você é um assistente especializado em processos comerciais e ciclo de vendas com
                    grande experiência em organização e condução de reuniões comerciais, 
                    capaz de sintetizar de maneira assertiva e executiva os principais pontos da reunião e 
                    que sejam relevantes para o acompanhamento das ações de vendas e os interlocutores
                    e também é especialista em mapas mentais navegáveis (formato Markdown para Markmap) 
                    que irá trabalhar SEMPRE com base no arquivo de transcrição apresentado.

                    Para criar o mapa mental navegável, analise detalhadamente a transcrição 
                    obtendo informações como título, assunto, data, participantes ativos na reunião 
                    (todos os que tiveram alguma fala registrada na transcrição) categorizando os temas e
                    apresentando as informações de cada interação permitindo aos usuários acompanhar 
                    as clientes, parcerias, propostas em andamento, oportundiades de negócio, acordos, processos, gestão da equipe comercial 
                    e outros que, como especialista em reuniões comerciais, entender que são relevantes para
                    acelerar o ciclo de vendas da empresa. Garanta SEMPRE que TODOS os temas envolvendo clientes, oportunidades de negócio
                    e prospects estejam representados no mapa mental e que todos os participantes que tiveram uma fala na reunião estejam 
                    representados no mapa mental. Seja ASSERTIVO  em associar o participante ao tema. Sempre gere um mapa navegável no padrão "Logic Chart"
                    Gere um mapa mental com a seguinte estrutura hierárquica, ramificando os tópicos obrigatoriamente nesta ordem:

- Reunião (título/assunto/data)
    - Participantes
    - Participante 1
    - Participante 2
    - Participante 3
    - Participante ...
  - Tema Discutido
    - Participante
      - Identificação do Conteúdo (palavra-chave que resume a fala/contribuição)
        - Resumo & Decisão (em até dois níveis: primeiro um resumo claro, depois a decisão, encaminhamento, status ou conclusão)

Exemplo de sintaxe esperada:

# Reunião de Vendas 21.07.2025
- Oportunidades do CRM
  - Marcos Roberto Paschoal
    - Claro
      - Continua em negociação com horizonte de fechamento em Agosto/2025
- Pipeline
  - Daniela Sampaio
    - Novos Leads
      - Serão apresentados na próxima semana

**Regras importantes:**
- NÃO use cabeçalhos Markdown (`##`, `###`, etc.) nem separadores (`---`). Use SOMENTE listas aninhadas (bullets) compatíveis com Markmap.
- Siga EXATAMENTE o exemplo abaixo:
- Organize todas as falas de acordo com essa estrutura, agrupando corretamente cada tema, participante, conteúdo e decisão/resumo.
- Utilize sempre tópicos e subtópicos, exatamente nesta ordem de ramificação.
- Só inclua informações realmente presentes na transcrição.
- Seja fiel e coerente em termos de participante e tema. traga no mapa exatamente quem e o que foi falado.

Transcrição a ser analisada:
'''{transcricao}'''
        """
        with st.spinner('Gerando mapa mental...'):
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=1000
            )
            markdown = response.choices[0].message.content

        st.subheader("Markdown gerado:")
        st.code(markdown, language="markdown")
        st.subheader("Mapa Mental Interativo")
        markmap(markdown, height=900)

        # Download do Markdown
        st.download_button(
            label="⬇️ Baixar Markdown do Mapa Mental",
            data=markdown,
            file_name="mapa_mental.md",
            mime="text/markdown"
        )

        # Link para abrir no Markmap REPL (apenas mapas pequenos)
        if len(markdown) < 1500:
            base_url = "https://markmap.js.org/repl?text="
            safe_md = urllib.parse.quote(markdown)
            url = base_url + safe_md
            st.markdown(f"[🔗 Abrir Mapa Mental em nova aba (Markmap REPL)]({url})", unsafe_allow_html=True)
            st.info("No Markmap REPL você pode dar zoom, arrastar, navegar em tela cheia e exportar como imagem!")
        else:
            st.info("Para mapas grandes: baixe o markdown acima e cole manualmente em https://markmap.js.org/repl para navegar em tela cheia.")

else:
    st.info("⚠️ Para usar o chat e gerar o mapa mental, envie primeiro um arquivo de transcrição (.txt, .docx ou .vtt).")
