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
Você é um assistente especialista em processos comerciais, ciclo de vendas e análise de reuniões comerciais. Seu objetivo é garantir que NENHUMA informação relevante seja omitida ao criar um mapa mental da transcrição abaixo. 

**INSTRUÇÕES OBRIGATÓRIAS:**
- Analise toda a transcrição e mapeie absolutamente todos os temas, assuntos, clientes, oportunidades, decisões, dúvidas, processos, participantes e próximos passos discutidos.
- Para cada tema ou subtema abordado, identifique e crie um subtópico SEPARADO para cada participante que falou sobre o tema, SEM agrupamento de falas diferentes no mesmo item. 
- Sempre que houver participação de mais de uma pessoa sobre o mesmo tema, crie ramificações distintas com o nome do participante, detalhando individualmente sua contribuição, status, observação ou decisão.
- Nunca omita falas, clientes, oportunidades, temas, dúvidas ou decisões relevantes, mesmo que sejam citados brevemente.
- NÃO use cabeçalhos Markdown (`##`, `###` etc.) ou linhas separadoras (`---`): use apenas listas aninhadas (bullets) compatíveis com Markmap.
- Organize o mapa mental SEMPRE nesta estrutura lógica e hierárquica:
    - Reunião (título/assunto/data)
        - Tema ou cliente tratado
            - Subtema/Oportunidade/Status (se houver)
                - Participante 1
                    - Fala/contribuição/resumo
                - Participante 2
                    - Fala/contribuição/resumo
                - Participante ...
                    - Fala/contribuição/resumo

**Exemplo obrigatório:**

# Reunião Comercial 21.07.2025
- Oportunidades Hunting
  - SAFRA
    - Status da PoC
      - Lucas Almeida
        - Está tentando contato com os responsáveis.
      - Douglas Costa
        - Indicou que a PoC está em análise desde Outubro/2024.
  - Ambev
    - Processo de Renovação
      - Marcos Paschoal
        - Detalhou avanços do contrato.
      - Daniela Sampaio
        - Comentou feedback recebido do cliente.
- Propostas em Andamento
  - Rede D'Or
    - Negociação Comercial
      - Monica Oliveira
        - Explicou condições da proposta.

**Regras finais:**
- Represente todos os temas, clientes, oportunidades, processos e participantes ativos exatamente como aparecem na transcrição.
- Mantenha clareza e objetividade, resuma cada fala em uma frase curta, mas NUNCA omita participantes ou o conteúdo real de suas falas.
- Utilize apenas listas aninhadas compatíveis com Markmap, exatamente como no exemplo acima.

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
