import os
import streamlit as st
import PyPDF2
import docx
import openai
from openai import OpenAIError
from pathlib import Path
import nltk
from nltk.tokenize import sent_tokenize

# Baixar recursos necessários do NLTK (se ainda não baixados)
nltk.download('punkt', quiet=True)
nltk.download('punkt_tab', quiet=True)

# Configuração da API OpenAI usando secrets do Streamlit
openai.api_type = "azure"
openai.api_key = os.environ.get("AZURE_OPENAI_API_KEY")
openai.api_base = os.environ.get("AZURE_OPENAI_API_BASE")
openai.api_version = os.environ.get("AZURE_OPENAI_API_VERSION")

# implantação--deployment_name
nome_da_implantacao = 'jjf'

# Caminho da pasta que contem os documentos de treino
pasta_arquivos = Path('documentos')

def ler_conteudo_arquivo(caminho_arquivo):
    ext = caminho_arquivo.suffix.lower()
    conteudo = ''
    try:
        if ext == '.txt':
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                conteudo = f.read()
        elif ext == '.pdf':
            with open(caminho_arquivo, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    texto_pagina = page.extract_text()
                    if texto_pagina:
                        conteudo += texto_pagina
        elif ext == '.docx':
            doc = docx.Document(caminho_arquivo)
            for para in doc.paragraphs:
                conteudo += para.text + '\n'
        return {'nome': caminho_arquivo.name, 'conteudo': conteudo}
    except Exception as e:
        st.error(f'Erro ao ler o arquivo {caminho_arquivo.name}: {e}')
        return {'nome': caminho_arquivo.name, 'conteudo': ''}

def resumir_texto(texto, num_sentencas=2):
    sentencas = sent_tokenize(texto)
    resumo = ' '.join(sentencas[:num_sentencas])
    return resumo

def processar_pergunta(pergunta, mensagens_previas):
    # Adiciona a nova mensagem do usuário ao histórico
    mensagens_previas.append({"role": "user", "content": pergunta})
    try:
        resposta = openai.ChatCompletion.create(
            engine=nome_da_implantacao,
            messages=mensagens_previas,
            max_tokens=500,
            temperature=0.2,
            n=1,
        )
        resposta_texto = resposta.choices[0].message.content.strip()
        # Adiciona a resposta do assistente ao histórico
        mensagens_previas.append({"role": "assistant", "content": resposta_texto})
        
        # Capturar informações de uso de tokens
        uso_tokens = resposta.get('usage', {})
        prompt_tokens = uso_tokens.get('prompt_tokens', 0)
        completion_tokens = uso_tokens.get('completion_tokens', 0)
        total_tokens = uso_tokens.get('total_tokens', 0)
        
        # Calcular o custo (exemplo: $0.002 por 1.000 tokens)
        custo_por_1000_tokens = 0.002  # Atualize conforme o preço real
        custo = (total_tokens / 1000) * custo_por_1000_tokens
        
        # Armazenar o uso e custo na sessão
        if 'total_tokens' not in st.session_state:
            st.session_state['total_tokens'] = 0
        if 'total_custo' not in st.session_state:
            st.session_state['total_custo'] = 0.0
        
        st.session_state['total_tokens'] += total_tokens
        st.session_state['total_custo'] += custo
        
        # Armazenar os detalhes da última interação
        st.session_state['ultimo_uso_tokens'] = {
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'total_tokens': total_tokens,
            'custo': custo
        }
        
        return resposta_texto, mensagens_previas
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar sua pergunta: {e}")
        return "Desculpe, ocorreu um erro ao processar sua pergunta.", mensagens_previas


# Lendo e armazenando o conteúdo dos arquivos com seus nomes e resumos
arquivos_conteudos = []
for arquivo in pasta_arquivos.iterdir():
    if arquivo.is_file():
        arquivo_conteudo = ler_conteudo_arquivo(arquivo)
        resumo = resumir_texto(arquivo_conteudo['conteudo'])
        arquivo_conteudo['resumo'] = resumo
        arquivos_conteudos.append(arquivo_conteudo)

# Criar o contexto com os nomes dos arquivos e seus resumos
contexto = "Documentos utilizados e seus resumos:\n"
for arquivo in arquivos_conteudos:
    contexto += f"- **{arquivo['nome']}**: {arquivo['resumo']}\n"

# Limitar o tamanho do contexto se necessário
limite_de_caracteres = 3000
if len(contexto) > limite_de_caracteres:
    contexto = contexto[:limite_de_caracteres]

# Inicializar o histórico de mensagens na sessão
if 'mensagens' not in st.session_state:
    st.session_state['mensagens'] = [
        {"role": "system", "content": "Você é um assistente inteligente da Universidade Insper que ajuda a responder perguntas dos colaboradores Insper com base nos dados disponíveis nos 11 documentos de treino."},
        {"role": "system", "content": contexto}
    ]

# Função para enviar mensagem
def enviar_mensagem():
    if st.session_state['nova_pergunta']:
        pergunta = st.session_state['nova_pergunta']
        with st.spinner('Processando...'):
            resposta, st.session_state['mensagens'] = processar_pergunta(pergunta, st.session_state['mensagens'])
        st.session_state['nova_pergunta'] = ''  # Limpa o campo de entrada

# Interface do Streamlit
st.title('[insper]chat: processos da graduação 🦊')
st.write('E aí! Como podemos te ajudar hoje?')

# Exibir perguntas pré-definidas como botões
st.markdown("**Experimente perguntar:**")

col1, col2 = st.columns(2)

with col1:
    if st.button('ⓘ Indique quais foram os documentos de gradu que você utilizou para o treino'):
        st.session_state['nova_pergunta'] = 'Indique quais foram os documentos de gradu que você utilizou para o treino'
        enviar_mensagem()

with col2:
    if st.button('💬 Faça um resumo com 3 pontos principais sobre o processo de rematrícula'):
        st.session_state['nova_pergunta'] = 'Faça um resumo com 3 pontos principais sobre o processo de rematrícula'
        enviar_mensagem()

# Exibir o histórico de mensagens
if 'mensagens' in st.session_state:
    for msg in st.session_state['mensagens'][2:]:  # Pula as duas primeiras mensagens do 'system'
        if msg['role'] == 'user':
            st.markdown(
                f"""
                <div style='padding: 10px; border-radius: 5px; margin-bottom: 5px; background-color: rgba(0, 0, 0, 0.05);'>
                    🦊 Você:<br>{msg['content']}
                </div>
                """,
                unsafe_allow_html=True
            )
        elif msg['role'] == 'assistant':
            st.markdown(
                f"""
                <div style='padding: 10px; border-radius: 5px; margin-bottom: 5px;'>
                    🤖 [insper]chat:<br>{msg['content']}
                </div>
                """,
                unsafe_allow_html=True
            )

# Exibir informações de uso de tokens e custo
if 'ultimo_uso_tokens' in st.session_state:
    with st.expander("🔎 Informações de Uso de Tokens e Custo"):
        ultimo_uso = st.session_state['ultimo_uso_tokens']
        st.write(f"**Tokens da Última Interação:**")
        st.write(f"- Tokens do Prompt: {ultimo_uso['prompt_tokens']}")
        st.write(f"- Tokens da Resposta: {ultimo_uso['completion_tokens']}")
        st.write(f"- Tokens Totais: {ultimo_uso['total_tokens']}")
        st.write(f"- Custo Estimado: ${ultimo_uso['custo']:.6f}")
        
        st.write(f"**Total Acumulado na Sessão:**")
        st.write(f"- Tokens Totais: {st.session_state['total_tokens']}")
        st.write(f"- Custo Total Estimado: ${st.session_state['total_custo']:.6f}")

# Determinar o placeholder dependendo se é a primeira interação ou não
if len(st.session_state['mensagens']) <= 2:  # Apenas as mensagens do 'system'
    placeholder_text = 'faça sua pergunta...'
else:
    placeholder_text = 'responda aqui ao [chat]insper...'

# Campo de entrada de texto com placeholder e sem label
st.text_input('', key='nova_pergunta', on_change=enviar_mensagem, placeholder=placeholder_text)



