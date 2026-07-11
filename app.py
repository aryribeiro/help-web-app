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
import ipaddress
import secrets
import sqlite3
import time
import datetime
import ntplib
import pytz
from streamlit_js_eval import streamlit_js_eval

# Carregar variáveis de ambiente
load_dotenv()

# ---------------- Controle de acesso por PIN ----------------
DB_PATH = os.getenv("HELP_DB_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "students.db"))

PIN_VALIDITY_SECONDS = 10 * 60        # PIN expira em 10 minutos
ACCESS_VALIDITY_SECONDS = 24 * 3600   # acesso liberado por 24 horas
RESEND_INTERVAL_SECONDS = 60          # intervalo mínimo entre envios de PIN
MAX_PIN_ATTEMPTS = 5                  # tentativas erradas antes de exigir novo PIN

def _db(query, params=(), fetch=False):
    """Executa uma query no SQLite, com commit e fechamento garantidos."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS students (
                email TEXT PRIMARY KEY,
                pin TEXT,
                pin_expires_at REAL DEFAULT 0,
                pin_sent_at REAL DEFAULT 0,
                pin_attempts INTEGER DEFAULT 0,
                verified_until REAL DEFAULT 0
            )
        """)
        cur = conn.execute(query, params)
        row = cur.fetchone() if fetch else None
        conn.commit()
        return row
    finally:
        conn.close()

def get_student(email):
    return _db("SELECT * FROM students WHERE email = ?", (email,), fetch=True)

def save_pin(email, pin):
    now = time.time()
    _db("""
        INSERT INTO students (email, pin, pin_expires_at, pin_sent_at, pin_attempts)
        VALUES (?, ?, ?, ?, 0)
        ON CONFLICT(email) DO UPDATE SET
            pin = excluded.pin,
            pin_expires_at = excluded.pin_expires_at,
            pin_sent_at = excluded.pin_sent_at,
            pin_attempts = 0
    """, (email, pin, now + PIN_VALIDITY_SECONDS, now))

def register_failed_attempt(email):
    _db("UPDATE students SET pin_attempts = pin_attempts + 1 WHERE email = ?", (email,))

def grant_access(email):
    _db("UPDATE students SET verified_until = ?, pin = NULL WHERE email = ?",
        (time.time() + ACCESS_VALIDITY_SECONDS, email))

def has_valid_access(email):
    row = get_student(email)
    return bool(row and row["verified_until"] > time.time())

def generate_pin():
    """Gera um PIN numérico de 6 dígitos criptograficamente seguro."""
    return f"{secrets.randbelow(1000000):06d}"

# ---------------- Utilitários ----------------
def _public_ip(value):
    """Retorna o IP público normalizado, ou None se o valor não for um IP
    público (descarta loopback e redes privadas como 192.168.x.x/10.x.x.x
    da infraestrutura do Streamlit Cloud)."""
    try:
        ip = ipaddress.ip_address(value)
        # Converte IPv4 mapeado em IPv6 (ex.: ::ffff:177.10.0.1) para IPv4 puro
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            ip = ip.ipv4_mapped
        return str(ip) if ip.is_global else None
    except ValueError:
        return None

def _pick_client_ip(headers, fallback_ip):
    """Escolhe o IP real do aluno: varre o X-Forwarded-For (preenchido pelo
    proxy reverso do Streamlit Cloud), depois X-Real-Ip e, por fim, a conexão
    direta — aceitando apenas o primeiro IP público encontrado."""
    candidates = []
    for header in ("X-Forwarded-For", "X-Real-Ip"):
        value = headers.get(header)
        if value:
            candidates.extend(part.strip() for part in value.split(","))
    if fallback_ip:
        candidates.append(fallback_ip)

    for candidate in candidates:
        public = _public_ip(candidate)
        if public:
            return public
    return "IP não disponível"

def get_client_ip():
    """Obtém o IP do aluno pelos headers/conexão (fallback: o proxy do
    Streamlit Cloud não repassa o IP público, então normalmente falha lá)."""
    try:
        return _pick_client_ip(st.context.headers, st.context.ip_address)
    except Exception:
        return "IP não disponível"

def get_browser_public_ip():
    """Obtém o IP público direto do NAVEGADOR do aluno via JS — funciona
    mesmo atrás do proxy do Streamlit Cloud, que esconde o IP do servidor.
    Retorna None no primeiro render (o valor chega num rerun seguinte)."""
    try:
        return streamlit_js_eval(
            js_expressions="fetch('https://api.ipify.org').then(r => r.text()).catch(() => null)",
            key="browser_public_ip",
        )
    except Exception:
        return None

def is_valid_email(email):
    """Verifica se o email é válido."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return re.match(pattern, email) is not None

def smtp_send(message):
    """Autentica no Gmail e envia a mensagem. Retorna True em caso de sucesso."""
    sender_email = os.getenv("EMAIL_USER")
    sender_password = os.getenv("EMAIL_PASSWORD")

    if not sender_email or not sender_password:
        st.error("Configuração de email incompleta. Defina EMAIL_USER e EMAIL_PASSWORD no arquivo .env.")
        return False

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(message)
        return True
    except Exception as e:
        st.error(f"Erro ao enviar email: {str(e)}")
        return False

def send_pin_email(recipient, pin):
    """Envia o PIN de acesso para o email do aluno."""
    message = MIMEMultipart()
    message["From"] = os.getenv("EMAIL_USER")
    message["To"] = recipient
    message["Subject"] = "Seu PIN de acesso - Help Web App"

    body = f"""
    Olá!

    Seu PIN de acesso ao formulário de dúvidas é: {pin}

    Ele é válido por 10 minutos. Após confirmar, seu acesso
    fica liberado por 24 horas.

    Se você não solicitou este código, ignore este email.
    """
    message.attach(MIMEText(body, "plain"))
    return smtp_send(message)

def send_email(name, email, question, date_time=None, uploaded_file=None, ip_address=None):
    """Envia email com a dúvida do aluno e anexo opcional."""
    recipient_email = os.getenv("RECIPIENT_EMAIL")

    if not recipient_email:
        st.error("Configuração de email incompleta. Defina RECIPIENT_EMAIL no arquivo .env.")
        return False

    # Cria mensagem
    message = MIMEMultipart()
    message["From"] = os.getenv("EMAIL_USER")
    message["To"] = recipient_email
    message["Subject"] = f"Mentoria AWS - Nova Dúvida de {name}"

    # Corpo do email
    body = f"""
    CONFIRA ABAIXO A MENSAGEM

    Nome: {name}
    Email: {email} (verificado por PIN)

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
        content_type, _ = mimetypes.guess_type(file_name)
        if content_type is None:
            content_type = 'application/octet-stream'

        main_type, sub_type = content_type.split('/', 1)

        # Cria o anexo apropriado baseado no tipo de arquivo
        if main_type == 'image':
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

    return smtp_send(message)

@st.cache_data(ttl=3600, show_spinner=False)
def get_ntp_offset():
    """Obtém a diferença entre o relógio local e o servidor NTP brasileiro.
    Cacheada por 1 hora para não bloquear o app a cada interação."""
    try:
        c = ntplib.NTPClient()
        response = c.request('pool.ntp.br', timeout=5)
        return response.offset
    except Exception:
        # Sem NTP, usa o relógio local (offset zero)
        return 0.0

def get_brazil_time():
    """Hora atual do Brasil, corrigida pelo offset NTP cacheado."""
    now = datetime.datetime.now(pytz.timezone('America/Sao_Paulo'))
    return now + datetime.timedelta(seconds=get_ntp_offset())

MESES = {
    1: 'Janeiro', 2: 'Fevereiro', 3: 'Março', 4: 'Abril',
    5: 'Maio', 6: 'Junho', 7: 'Julho', 8: 'Agosto',
    9: 'Setembro', 10: 'Outubro', 11: 'Novembro', 12: 'Dezembro'
}
DIAS_SEMANA = [
    'Segunda-feira', 'Terça-feira', 'Quarta-feira',
    'Quinta-feira', 'Sexta-feira', 'Sábado', 'Domingo'
]

def format_brazilian_date(date):
    """Formata a data por extenso no formato brasileiro."""
    return f"{DIAS_SEMANA[date.weekday()]}, {date.day:02d} de {MESES[date.month]} de {date.year}, {date.hour:02d}:{date.minute:02d}"

# ---------------- Telas ----------------
def show_flash():
    """Exibe mensagens definidas antes de um st.rerun()."""
    if 'flash_error' in st.session_state:
        st.error(st.session_state.pop('flash_error'))
    if 'flash_info' in st.session_state:
        st.info(st.session_state.pop('flash_info'))
    if 'flash_success' in st.session_state:
        st.success(st.session_state.pop('flash_success'))

def request_pin(email):
    """Gera, salva e envia um novo PIN. Retorna True para avançar à tela de PIN."""
    row = get_student(email)
    now = time.time()

    # Limite de reenvio: evita bombardear a caixa de entrada do aluno
    if row and now - row["pin_sent_at"] < RESEND_INTERVAL_SECONDS:
        wait = int(RESEND_INTERVAL_SECONDS - (now - row["pin_sent_at"]))
        st.session_state.flash_error = f"Um PIN já foi enviado há pouco. Aguarde {wait} segundo(s) para pedir outro."
        return True  # segue para a tela de PIN: o código anterior continua válido

    pin = generate_pin()
    if send_pin_email(email, pin):
        save_pin(email, pin)
        st.session_state.flash_info = f"📩 Enviamos um PIN de 6 dígitos para **{email}**. Confira sua caixa de entrada (e a pasta de spam)."
        return True
    return False

def email_screen():
    """Tela 1: aluno informa o email para receber o PIN (ou entrar direto se já verificado)."""
    show_flash()
    with st.form("email_form"):
        st.subheader("🔓 Acesso ao Formulário")
        st.markdown("Informe seu email para receber um **PIN de acesso**. Depois de confirmar, você fica liberado por **24 horas**.")

        row = st.container(key="email_row")
        with row:
            col1, col2 = st.columns([1, 1], vertical_alignment="bottom")
            with col1:
                email = st.text_input("Seu email")
            with col2:
                submitted = st.form_submit_button("Receber PIN", type="primary")

        if submitted:
            email = email.strip().lower()
            if not email or not is_valid_email(email):
                st.error("Por favor, informe um email válido.")
            elif has_valid_access(email):
                # Já verificado nas últimas 24h: entra direto, sem novo PIN
                st.session_state.auth_email = email
                st.session_state.flash_success = "✅ Você já está liberado! Pode enviar suas dúvidas."
                st.rerun()
            else:
                with st.spinner("Enviando PIN..."):
                    ok = request_pin(email)
                if ok:
                    st.session_state.pin_email = email
                    st.rerun()

def pin_screen():
    """Tela 2: aluno confirma o PIN recebido por email."""
    show_flash()
    email = st.session_state.pin_email

    with st.form("pin_form"):
        st.subheader("📩 Confirme seu PIN")
        st.markdown(f"Digite o PIN de 6 dígitos enviado para **{email}**. Ele vale por 10 minutos.")

        row = st.container(key="pin_row")
        with row:
            col1, col2 = st.columns([1, 1], vertical_alignment="bottom")
            with col1:
                pin_input = st.text_input("PIN", max_chars=6)
            with col2:
                submitted = st.form_submit_button("Confirmar", type="primary")

        if submitted:
            row = get_student(email)
            now = time.time()
            pin_clean = pin_input.strip()

            if not row or not row["pin"]:
                st.error("Nenhum PIN ativo para este email. Clique em 'Reenviar PIN'.")
            elif row["pin_attempts"] >= MAX_PIN_ATTEMPTS:
                st.error("Muitas tentativas erradas. Clique em 'Reenviar PIN' para receber um novo código.")
            elif now > row["pin_expires_at"]:
                st.error("Este PIN expirou. Clique em 'Reenviar PIN' para receber um novo código.")
            elif not pin_clean or not secrets.compare_digest(pin_clean, row["pin"]):
                register_failed_attempt(email)
                restantes = MAX_PIN_ATTEMPTS - row["pin_attempts"] - 1
                if restantes > 0:
                    st.error(f"PIN incorreto. Você ainda tem {restantes} tentativa(s).")
                else:
                    st.error("PIN incorreto. Tentativas esgotadas — clique em 'Reenviar PIN'.")
            else:
                grant_access(email)
                st.session_state.auth_email = email
                st.session_state.pin_email = None
                st.session_state.flash_success = "✅ Acesso liberado por 24 horas! Agora é só enviar sua dúvida."
                st.rerun()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reenviar PIN", use_container_width=True):
            request_pin(email)
            st.rerun()
    with col2:
        if st.button("Usar outro email", use_container_width=True):
            st.session_state.pin_email = None
            st.rerun()

def question_screen(formatted_date, user_ip):
    """Tela 3: formulário de dúvidas (email já verificado)."""
    show_flash()
    email = st.session_state.auth_email

    col1, col2 = st.columns([5, 1])
    with col1:
        st.markdown(f"<small>Enviando como <b>{email}</b></small>", unsafe_allow_html=True)
    with col2:
        if st.button("Sair"):
            st.session_state.auth_email = None
            st.session_state.form_submitted = False
            st.rerun()

    # Verifica se o formulário já foi enviado com sucesso
    if st.session_state.form_submitted:
        st.success("✅ Sua dúvida foi enviada!")
        if st.button("Enviar outra dúvida"):
            st.session_state.form_submitted = False
            st.rerun()
        return

    with st.form("question_form"):
        name = st.text_input("Nome completo", value=st.session_state.get('student_name', ''))
        question = st.text_area("Descreva sua dúvida")

        # Adiciona o campo para upload de arquivo
        st.markdown("#### 📂 Anexo (opcional)")
        st.markdown("Envie imagens, documentos, áudio e/ou vídeo, que ajude a explicar sua dúvida (máximo 30 MB)")
        uploaded_file = st.file_uploader("Selecione um arquivo", type=["png", "jpg", "jpeg", "pdf", "docx", "mp3", "mp4"])

        # Mostra prévia do arquivo se for uma imagem
        if uploaded_file is not None:
            file_details = {"Filename": uploaded_file.name, "FileType": uploaded_file.type, "Size": f"{uploaded_file.size / (1024*1024):.2f} MB"}

            # Verifica o tamanho do arquivo
            if uploaded_file.size > 30 * 1024 * 1024:  # 30 MB em bytes
                st.warning("⚠️ O arquivo excede o limite de 30 MB. Por favor, escolha um arquivo menor.")
            else:
                st.write(f"**Arquivo selecionado:** {file_details['Filename']} ({file_details['Size']})")

                # Exibe prévia para imagens
                if uploaded_file.type.startswith('image/'):
                    st.image(uploaded_file, caption=uploaded_file.name, use_container_width=True)
                elif uploaded_file.type == 'application/pdf':
                    st.write("PDF selecionado (sem prévia)")
                elif uploaded_file.type.startswith('audio/'):
                    st.audio(uploaded_file, format=uploaded_file.type)
                elif uploaded_file.type.startswith('video/'):
                    st.video(uploaded_file)

        submitted = st.form_submit_button("Enviar Dúvida", type="primary")

        if submitted:
            if not name:
                st.error("Por favor, informe seu nome.")
            elif not question:
                st.error("Por favor, descreva sua dúvida.")
            elif uploaded_file is not None and uploaded_file.size > 30 * 1024 * 1024:
                st.error("O arquivo excede o limite de 30 MB. Por favor, escolha um arquivo menor.")
            else:
                with st.spinner("Enviando sua dúvida..."):
                    success = send_email(name, email, question, formatted_date, uploaded_file, user_ip)

                if success:
                    # Lembra o nome para a próxima dúvida e vai à confirmação
                    st.session_state.student_name = name
                    st.session_state.form_submitted = True
                    st.rerun()

def main():
    st.set_page_config(
        page_title="Help Web App: formulário tira dúvidas",
        page_icon="📧",
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    # Obtém a data e hora atual do Brasil (offset NTP cacheado)
    current_time = get_brazil_time()
    formatted_date = format_brazilian_date(current_time)

    # IP público capturado no navegador do aluno (o proxy do Streamlit Cloud
    # não repassa o IP; o valor chega via JS após o primeiro render)
    browser_ip = get_browser_public_ip()
    if browser_ip:
        normalized = _public_ip(str(browser_ip).strip())
        if normalized:
            st.session_state.user_ip = normalized

    # Enquanto o navegador não responde, usa headers/conexão como fallback
    user_ip = st.session_state.get('user_ip') or get_client_ip()

    # Centralizar com HTML + CSS
    st.markdown("""
    <div style="text-align: center;">
        <h1>📧 Help Web App</h1>
        <p>Use este formulário para enviar suas dúvidas durante os encontros online.<br>
        Suas questões serão respondidas por email, no momento correto.</p>
    </div>
    """, unsafe_allow_html=True)

    # Inicializa o estado da autenticação
    if 'auth_email' not in st.session_state:
        st.session_state.auth_email = None   # email com acesso liberado nesta sessão
    if 'pin_email' not in st.session_state:
        st.session_state.pin_email = None    # email aguardando confirmação de PIN
    if 'form_submitted' not in st.session_state:
        st.session_state.form_submitted = False

    # Revalida o acesso: as 24 horas podem ter expirado durante a sessão
    if st.session_state.auth_email and not has_valid_access(st.session_state.auth_email):
        st.session_state.auth_email = None
        st.session_state.flash_error = "Seu acesso de 24 horas expirou. Informe seu email para receber um novo PIN."

    if st.session_state.auth_email:
        question_screen(formatted_date, user_ip)
    elif st.session_state.pin_email:
        pin_screen()
    else:
        email_screen()

    # Adiciona rodapé com data, hora e IP (reutiliza os valores calculados no início)
    st.markdown(f"<div style='text-align: center; font-size: 14px;'>{formatted_date}<br>IP: {user_ip}</div>", unsafe_allow_html=True)

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
    /* Esconde o iframe invisível do componente que captura o IP no navegador */
    iframe[title="streamlit_js_eval.streamlit_js_eval"] {
        display: none !important;
    }
    /* Campo + botão lado a lado, sem empilhar no mobile */
    .st-key-email_row [data-testid="stHorizontalBlock"],
    .st-key-pin_row [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
    }
    .st-key-email_row [data-testid="stColumn"],
    .st-key-pin_row [data-testid="stColumn"] {
        min-width: 0 !important;
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
