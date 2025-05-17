import streamlit as st
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.mime.audio import MIMEAudio
from email.mime.image import MIMEImage
import os
import mimetypes
from dotenv import load_dotenv
import re
import random
import string
import datetime
import locale
import ntplib
import pytz
from time import ctime
import requests

# Carregar variáveis de ambiente
load_dotenv()

def get_public_ip():
    """Obtém o IP público do usuário."""
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        if response.status_code == 200:
            return response.json()['ip']
        return "IP não disponível"
    except Exception as e:
        return "IP não disponível"

def generate_captcha():
    """Gera um CAPTCHA simples de operação matemática."""
    operations = ['+', '-', '*']
    operation = random.choice(operations)
    
    if operation == '+':
        num1 = random.randint(1, 20)
        num2 = random.randint(1, 20)
        answer = num1 + num2
    elif operation == '-':
        num1 = random.randint(10, 30)
        num2 = random.randint(1, 9)
        answer = num1 - num2
    else:  # multiplicação
        num1 = random.randint(1, 10)
        num2 = random.randint(1, 10)
        answer = num1 * num2
    
    captcha_text = f"{num1} {operation} {num2} = ?"
    return captcha_text, answer

def is_valid_email(email):
    """Verifica se o email é válido."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

def send_email(name, email, question, date_time=None, uploaded_file=None, ip_address=None):
    """Envia email com a dúvida do aluno e anexo opcional."""
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")
    recipient_email = os.getenv("RECIPIENT_EMAIL")
    
    # Cria mensagem
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = recipient_email
    message["Subject"] = f"Mentoria AWS - Nova Dúvida de {name}"
    
    # Corpo do email
    body = f"""
    CONFIRA ABAIXO A MENSAGEM
    
    Nome: {name}
    Email: {email}
    
    Dúvida: 
    {question}
    """
    # Adiciona data e hora no rodapé do email, se fornecido
    if date_time:
        body += f"""
    
    ---
    Enviado: {date_time}"""
    
    # Adiciona IP público, se disponível
    if ip_address:
        body += f"""
    IP: {ip_address}"""
    
    message.attach(MIMEText(body, "plain"))
    
    # Adiciona anexo, se fornecido
    if uploaded_file is not None:
        file_data = uploaded_file.getvalue()
        file_name = uploaded_file.name
        
        # Detecta o tipo MIME do arquivo
        content_type, encoding = mimetypes.guess_type(file_name)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        main_type, sub_type = content_type.split('/', 1)
        
        # Cria o anexo apropriado baseado no tipo de arquivo
        if main_type == 'text':
            attachment = MIMEText(file_data.decode('utf-8'), _subtype=sub_type)
        elif main_type == 'image':
            attachment = MIMEImage(file_data, _subtype=sub_type)
        elif main_type == 'audio':
            attachment = MIMEAudio(file_data, _subtype=sub_type)
        elif main_type == 'application' and sub_type == 'pdf':
            attachment = MIMEApplication(file_data, _subtype=sub_type)
        else:
            attachment = MIMEApplication(file_data)
            
        # Adiciona cabeçalho com nome do arquivo
        attachment.add_header('Content-Disposition', 'attachment', filename=file_name)
        message.attach(attachment)
    
    try:
        # Conectar ao servidor SMTP
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(message)
        return True
    except Exception as e:
        st.error(f"Erro ao enviar email: {str(e)}")
        return False

def get_ntp_time():
    """Obtém a hora atual de um servidor NTP público."""
    try:
        c = ntplib.NTPClient()
        # Usando o pool NTP brasileiro
        response = c.request('pool.ntp.br', timeout=5)
        # Converte o tempo NTP para datetime
        ntp_time = datetime.datetime.fromtimestamp(response.tx_time, pytz.timezone('America/Sao_Paulo'))
        return ntp_time
    except Exception as e:
        # Em caso de falha na conexão com o servidor NTP, usa o horário local
        st.warning(f"Não foi possível sincronizar com o servidor NTP. Usando horário local. Erro: {e}")
        return datetime.datetime.now(pytz.timezone('America/Sao_Paulo'))

def format_brazilian_date(date):
    """Formata a data por extenso no formato brasileiro."""
    # Configurar o locale para português do Brasil
    try:
        locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'portuguese_brazil')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil')
            except locale.Error:
                # Fallback para formato manual se o locale não estiver disponível
                meses = {
                    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
                    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
                    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
                }
                dia_semana = [
                    'Segunda-feira', 'Terça-feira', 'Quarta-feira', 
                    'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'
                ]
                return f"{dia_semana[date.weekday()]}, {date.day} de {meses[date.month]} de {date.year}, {date.hour:02d}:{date.minute:02d}"
    
    # Tenta usar o locale para formatar a data
    try:
        return date.strftime("%A, %d de %B de %Y, %H:%M")
    except:
        # Se falhar, usa o formato manual
        meses = {
            1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
            5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
            9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
        }
        dia_semana = [
            'Segunda-feira', 'Terça-feira', 'Quarta-feira', 
            'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'
        ]
        return f"{dia_semana[date.weekday()]}, {date.day} de {meses[date.month]} de {date.year}, {date.hour:02d}:{date.minute:02d}"

def main():
    st.set_page_config(
        page_title="Help Web App: formulário tira dúvidas",
        page_icon="📧",
        layout="centered",
        initial_sidebar_state="collapsed"
    )
    
    # Obtém a data e hora atual do Brasil via servidor NTP
    current_time = get_ntp_time()
    formatted_date = format_brazilian_date(current_time)
    
    # Obtém o IP público do usuário
    if 'user_ip' not in st.session_state:
        st.session_state.user_ip = get_public_ip()
    
    # Centralizar com HTML + CSS
    st.markdown("""
    <div style="text-align: center;">
        <h1>📧 Help Web App</h1>
        <p>Use este formulário para enviar suas dúvidas durante os encontros online.<br>
        Suas questões serão respondidas por email, no momento correto.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Inicializa o estado de autenticação
    if 'is_authenticated' not in st.session_state:
        st.session_state.is_authenticated = False
        st.session_state.form_submitted = False  # Inicializa form_submitted
    
    # Formulário de login
    if not st.session_state.is_authenticated:
        with st.form("login_form"):
            st.subheader("🔐 Acesso ao Formulário")
            st.markdown("Digite a senha fornecida pelo preletor, durante o encontro...")
            
            password = st.text_input("Senha:", type="password")
            submit_login = st.form_submit_button("Acessar")
            
            if submit_login:
                form_password = os.getenv("FORM_PASSWORD")
                if password == form_password:
                    st.session_state.is_authenticated = True
                    st.rerun()
                else:
                    st.error("Senha incorreta: tente novamente!")
    
    # Inicializa variáveis de sessão para o CAPTCHA se autenticado
    elif st.session_state.is_authenticated:
        if 'captcha_text' not in st.session_state:
            captcha_text, captcha_answer = generate_captcha()
            st.session_state.captcha_text = captcha_text
            st.session_state.captcha_answer = captcha_answer
        
        # Botão para sair
        col1, col2 = st.columns([5, 1])
        with col2:
            if st.button("Sair"):
                st.session_state.is_authenticated = False
                st.session_state.form_submitted = False  # Reseta form_submitted ao sair
                if 'captcha_text' in st.session_state:
                    del st.session_state.captcha_text
                if 'captcha_answer' in st.session_state:
                    del st.session_state.captcha_answer
                st.rerun()
        
        # Verifica se o formulário já foi enviado com sucesso
        if st.session_state.form_submitted:
            st.success("✅ Sua dúvida foi enviada!")
            if st.button("Preencher novamente"):
                st.session_state.form_submitted = False
                st.rerun()
        else:
            with st.form("question_form"):
                name = st.text_input("Nome completo")
                email = st.text_input("Seu email")
                question = st.text_area("Descreva sua dúvida")
                
                # Adiciona o campo para upload de arquivo
                st.markdown("#### 📂 Anexo (opcional)")
                st.markdown("Envie imagens, documentos, áudio e/ou vídeo, que ajude a explicar sua dúvida (máximo 30 MB)")
                uploaded_file = st.file_uploader("Selecione um arquivo", type=["png", "jpg", "pdf", "docx", "mp3", "mp4"])
                
                # Mostra prévia do arquivo se for uma imagem
                if uploaded_file is not None:
                    file_details = {"Filename": uploaded_file.name, "FileType": uploaded_file.type, "Size": f"{uploaded_file.size / (1024*1024):.2f} MB"}
                    
                    # Verifica o tamanho do arquivo
                    if uploaded_file.size > 30 * 1024 * 1024:  # 30 MB em bytes
                        st.warning("⚠️ O arquivo excede o limite de 30 MB. Por favor, escolha um arquivo menor.")
                    else:
                        st.write(f"**Arquivo selecionado:** {file_details['Filename']} ({file_details['Size']} MB)")
                        
                        # Exibe prévia para imagens
                        if uploaded_file.type.startswith('image/'):
                            st.image(uploaded_file, caption=uploaded_file.name, use_container_width=True)
                        elif uploaded_file.type == 'application/pdf':
                            st.write("PDF selecionado (sem prévia)")
                        elif uploaded_file.type.startswith('audio/'):
                            st.audio(uploaded_file, format=uploaded_file.type)
                        elif uploaded_file.type.startswith('video/'):
                            st.video(uploaded_file)
                
                # CAPTCHA
                st.markdown("#### 🔐 Verificação de Segurança")
                st.markdown(f"**{st.session_state.captcha_text}**")
                captcha_response = st.text_input("Resolva a operação matemática acima")
                
                submitted = st.form_submit_button("Enviar Dúvida")
                
                if submitted:
                    if not name:
                        st.error("Por favor, informe seu nome.")
                    elif not email:
                        st.error("Por favor, informe seu email.")
                    elif not is_valid_email(email):
                        st.error("Por favor, informe um email válido.")
                    elif not question:
                        st.error("Por favor, descreva sua dúvida.")
                    elif uploaded_file is not None and uploaded_file.size > 30 * 1024 * 1024:
                        st.error("O arquivo excede o limite de 30 MB. Por favor, escolha um arquivo menor.")
                    elif not captcha_response:
                        st.error("Por favor, resolva o CAPTCHA.")
                    else:
                        # Verifica o CAPTCHA
                        try:
                            captcha_user_answer = int(captcha_response.strip())
                            if captcha_user_answer != st.session_state.captcha_answer:
                                st.error("CAPTCHA incorreto. Por favor, tente novamente.")
                                # Gera novo CAPTCHA
                                captcha_text, captcha_answer = generate_captcha()
                                st.session_state.captcha_text = captcha_text
                                st.session_state.captcha_answer = captcha_answer
                            else:
                                # CAPTCHA correto, enviar email
                                with st.spinner("Enviando sua dúvida..."):
                                    # Passa a data formatada e o IP para a função de envio de email
                                    success = send_email(name, email, question, formatted_date, uploaded_file, st.session_state.user_ip)
                                    
                                if success:
                                    # Gera novo CAPTCHA para próximo uso
                                    captcha_text, captcha_answer = generate_captcha()
                                    st.session_state.captcha_text = captcha_text
                                    st.session_state.captcha_answer = captcha_answer
                                    
                                    # Limpar formulário
                                    st.session_state.form_submitted = True
                                    
                                    # Mostra mensagem de confirmação
                                    st.success("✅ Dúvida enviada! Por favor aguarde.")
                        except ValueError:
                            st.error("Por favor, digite um número válido para o CAPTCHA.")
                            # Gera novo CAPTCHA
                            captcha_text, captcha_answer = generate_captcha()
                            st.session_state.captcha_text = captcha_text
                            st.session_state.captcha_answer = captcha_answer

    # Obtém a data e hora atual do Brasil via servidor NTP
    current_time = get_ntp_time()
    formatted_date = format_brazilian_date(current_time)
    
    # Adiciona rodapé com data, hora e IP
    
    st.markdown(f"<div style='text-align: center; color: black; font-size: 14px;'>{formatted_date}<br>IP: {st.session_state.user_ip}</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()

# Estilo personalizado - Remoção de elementos da interface do Streamlit
st.markdown("""
<style>
    .main {
        background-color: #ffffff;
        color: #333333;
    }
    .block-container {
        padding-top: 1rem;
        padding-bottom: 0rem;
    }
    /* Esconde completamente todos os elementos da barra padrão do Streamlit */
    header {display: none !important;}
    footer {display: none !important;}
    #MainMenu {display: none !important;}
    /* Remove qualquer espaço em branco adicional */
    div[data-testid="stAppViewBlockContainer"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0 !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }
    /* Remove quaisquer margens extras */
    .element-container {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# Informações de contato
st.markdown("""
<hr>
<div style="text-align: center;">
    <h4>Help Web App: formulário tira dúvidas.</h4>
    <p>Por Ary Ribeiro. Contato via email: <a href="mailto:aryribeiro@gmail.com">aryribeiro@gmail.com</a></p>
</div>
""", unsafe_allow_html=True)