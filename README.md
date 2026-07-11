Obs.: caso o app esteja no modo "sleeping" (dormindo) ao entrar, basta clicar no botão que estará disponível e aguardar, para ativar o mesmo.
![print](https://github.com/user-attachments/assets/39b6f500-3da4-4b32-a9bb-e537d3fbe2cd)

# Aplicativo tira dúvidas para Cursos

Este é um aplicativo Streamlit que permite aos alunos enviarem dúvidas durante aulas.

## Como configurar

1. Clone este repositório
2. Instale as dependências:
   ```
   pip install -r requirements.txt
   ```
3. Configure o arquivo `.env` com suas credenciais de email:
   - `EMAIL_USER`: Seu endereço de email (preferencialmente Gmail)
   - `EMAIL_PASSWORD`: Sua senha de aplicativo (não sua senha normal do Gmail)
   - `RECIPIENT_EMAIL`: Email do professor que receberá as dúvidas

   Para o Gmail, você precisa criar uma senha de aplicativo:
   - Acesse sua Conta Google > Segurança 
   - Ative a autenticação de dois fatores se ainda não estiver ativa
   - Procure por "Senhas de app" e crie uma nova para este aplicativo

4. Execute o aplicativo:
   ```
   streamlit run app.py
   ```

## Como funciona o acesso (PIN por email)

1. O aluno informa o próprio email
2. Recebe um PIN de 6 dígitos por email (válido por 10 minutos)
3. Ao confirmar o PIN, fica liberado por **24 horas** para enviar dúvidas
4. Se recarregar a página dentro das 24 horas, basta digitar o email de novo — entra direto, sem novo PIN

Proteções embutidas: reenvio de PIN limitado a 1 por minuto, máximo de 5 tentativas erradas por código, e o email verificado é usado automaticamente nas dúvidas (o aluno não digita email no formulário).

## Funcionalidades

- Acesso por PIN enviado ao email do aluno, sem senha da turma e sem CAPTCHA
- Formulário para alunos enviarem dúvidas durante a aula
- Validação de campos obrigatórios e formato de email
- Envio automático das dúvidas para o email do professor
- Upload de anexos (imagens, PDFs, áudios, vídeos) até 30 MB
- Prévia dos arquivos enviados
- Interface simples e intuitiva

## Nota de Segurança

Nunca compartilhe seu arquivo `.env` ou coloque suas credenciais em sistemas de controle de versão como o Git.

## Por Ary Ribeiro
aryribeiro@gmail.com