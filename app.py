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
    max_chars=100,
    placeholder="Digite sua pergunta (máx. 100 caracteres)"
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
                max_tokens=2000
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
                   Você é um assistente especialista em processos comerciais, ciclo de vendas e organização de reuniões comerciais. Seu papel é **sintetizar, de maneira executiva e assertiva, TODOS os pontos relevantes tratados na transcrição de uma reunião comercial** — sempre focando em temas essenciais para acompanhamento de ações, decisões, oportunidades, clientes, prospects, propostas, parcerias, acordos, processos e gestão da equipe de vendas.

Sua missão é garantir que **nenhum tema, ação, decisão, oportunidade, cliente, participante ativo ou ponto relevante** da reunião seja omitido do mapa mental, respeitando o limite de 2000 tokens de retorno.

**Orientações obrigatórias:**
- Analise minuciosamente toda a transcrição. Mapeie todos os temas tratados, decisões, dúvidas, propostas, acordos, status, próximos passos, participantes ativos (quem falou), clientes, prospects, oportunidades e qualquer outro elemento relevante do ciclo comercial.
- NUNCA omita temas, clientes, oportunidades, propostas ou participantes que tenham sido mencionados, mesmo que brevemente.
- Associe cada tema discutido aos participantes corretos, de forma fiel e coerente ao que foi dito.
- Mantenha o máximo de integridade das discussões, sem suprimir tópicos relevantes para o acompanhamento ou gestão comercial.

**Regras para geração do mapa mental:**
- Utilize apenas listas aninhadas em Markdown (bullets) — NUNCA utilize cabeçalhos Markdown (`##`, `###`, etc.) ou linhas separadoras (`---`).
- Estruture o mapa mental EXATAMENTE na seguinte ordem hierárquica (padrão "Logic Chart"):
    - Reunião (título/assunto/data)
        - Participantes (listar todos que falaram)
        - Tema Discutido 1
            - Participante (quem falou sobre este tema)
                - Palavra-chave do conteúdo/contribuição
                    - Resumo & Decisão (primeiro resumo, depois decisão/encaminhamento/status)
        - Tema Discutido 2
            - ...
- Agrupe todas as falas de acordo com esta estrutura, sendo fiel ao conteúdo da transcrição.
- Só inclua informações realmente presentes no documento — NUNCA invente ou generalize.
- Siga SEMPRE o exemplo abaixo, sem alterar a estrutura:

# Reunião de Vendas 21.07.2025
- Participantes
  - Marcos Roberto Paschoal
  - Daniela Sampaio
- Oportunidades do CRM
  - Marcos Roberto Paschoal
    - Claro
      - Continua em negociação com horizonte de fechamento em Agosto/2025
- Pipeline
  - Daniela Sampaio
    - Novos Leads
      - Serão apresentados na próxima semana

**IMPORTANTE:**  
- A integridade de todos os temas tratados na reunião deve estar preservada no mapa mental, mesmo que resuma cada um em poucas palavras para respeitar o limite de tokens.
- Não omita tópicos, clientes, nomes ou decisões.
- O resultado DEVE ser totalmente compatível com Markmap (listas aninhadas).

Transcrição a ser analisada:
'''{transcricao}'''
        """
        with st.spinner('Gerando mapa mental...'):
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=2000
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
