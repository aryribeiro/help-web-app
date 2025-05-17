# Aplicativo de Dúvidas para Cursos

Este é um aplicativo Streamlit que permite aos alunos enviarem dúvidas durante aulas.

## Como configurar

1. Clone este repositório
2. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```
3. Configure o arquivo `.env` com suas credenciais de email e a senha de acesso ao formulário:
   - `EMAIL_USER`: Seu endereço de email (preferencialmente Gmail)
   - `EMAIL_PASSWORD`: Sua senha de aplicativo (não sua senha normal do Gmail)
   - `FORM_PASSWORD`: Senha que será compartilhada com os alunos durante a aula

   Para o Gmail, você precisa criar uma senha de aplicativo:
   - Acesse sua Conta Google > Segurança 
   - Ative a autenticação de dois fatores se ainda não estiver ativa
   - Procure por "Senhas de app" e crie uma nova para este aplicativo

4. Execute o aplicativo:
   ```
   streamlit run app.py
   ```

## Funcionalidades

- Sistema de proteção por senha para controlar acesso ao formulário
- Formulário para alunos enviarem dúvidas durante a aula
- Validação de campos obrigatórios e formato de email
- Envio automático das dúvidas para o email do professor
- Upload de anexos (imagens, PDFs, áudios, vídeos) até 30 MB
- Prévia dos arquivos enviados
- CAPTCHA matemático para evitar spam e robôs
- Interface simples e intuitiva

## Nota de Segurança

Nunca compartilhe seu arquivo `.env` ou coloque suas credenciais em sistemas de controle de versão como o Git.