# Passo a passo — do zero ao painel no ar

Guia clicando na tela. **Você não precisa instalar Git nem saber usar Git.**
Tempo estimado: 30 minutos.

---

## Etapa 1 — Criar o repositório no GitHub

1. Entre em <https://github.com> e faça login (ou crie uma conta).
2. Clique no **+** no canto superior direito → **New repository**.
3. Preencha:
   - **Repository name**: `autonomia-marcas`
   - **Visibility**: **Public** (necessário para o GitHub Pages gratuito)
   - **NÃO** marque "Add a README file"
4. Clique em **Create repository**.

> **Importante sobre "Public":** o repositório público deixa o painel e os
> **números** visíveis para qualquer um que tenha o link. As **credenciais do
> Salesforce nunca ficam públicas** — elas vão em "Secrets", que o GitHub
> criptografa. Se os números de autonomia por marca forem sensíveis, fale com
> seu time de TI antes; nesse caso a alternativa é repositório privado com
> GitHub Pages (requer plano Team/Enterprise da organização).

---

## Etapa 2 — Subir os arquivos do projeto

1. Descompacte o `autonomia-marcas.zip` numa pasta do seu computador.
2. Na página do repositório recém-criado, clique em **uploading an existing file**
   (o link no meio da tela).
3. Abra a pasta descompactada, **selecione tudo (Ctrl+A)** e arraste para a
   área de upload do navegador.
4. Confira se apareceram, entre outros: `pyproject.toml`, `README.md`, a pasta
   `src`, a pasta `docs` e a pasta `.github`.
   - Se a pasta `.github` **não** aparecer: o Windows esconde pastas que
     começam com ponto. No Explorador de Arquivos, aba **Exibir** → marque
     **Itens ocultos**, e arraste a pasta `.github` separadamente.
5. Desça até o fim e clique em **Commit changes**.

---

## Etapa 3 — Ligar o GitHub Pages

1. No repositório, clique em **Settings** (engrenagem, no menu de cima).
2. No menu da esquerda, clique em **Pages**.
3. Em **Source**, escolha **Deploy from a branch**.
4. Em **Branch**, escolha `main` e, na caixa ao lado, escolha **/docs**.
5. Clique em **Save**.
6. Espere 1–2 minutos e recarregue a página. Vai aparecer a URL do painel:

   ```
   https://SEU-USUARIO.github.io/autonomia-marcas/
   ```

   **Guarde essa URL** — é o link que você vai compartilhar com o time.

---

## Etapa 4 — Ver o painel funcionando com dados de teste

Antes de ter as credenciais do Salesforce, dá para validar tudo:

1. **Settings** → menu da esquerda → **Secrets and variables** → **Actions**.
2. Clique na aba **Variables** → **New repository variable**.
3. Name: `MODO_DEMO` · Value: `1` → **Add variable**.
4. Vá na aba **Actions** (menu de cima) → clique em **Atualizar painel** na
   lista da esquerda → botão **Run workflow** → **Run workflow**.
5. Espere o ✅ verde (cerca de 1 minuto) e abra a URL da Etapa 3.

Você deve ver o painel com as duas abas e dados fictícios.

---

## Etapa 5 — Conectar no Salesforce de verdade

Quando o time do Salesforce te entregar as credenciais:

### 5.1 Cadastrar os segredos

**Settings** → **Secrets and variables** → **Actions** → aba **Secrets** →
**New repository secret**, um de cada vez:

| Name                | Value                                          |
|---------------------|------------------------------------------------|
| `SF_DOMAIN`         | `https://suaorg.my.salesforce.com`             |
| `SF_CLIENT_ID`      | o Consumer Key do Connected App                |
| `SF_CLIENT_SECRET`  | o Consumer Secret do Connected App             |

Se o time entregar **usuário e senha** em vez de client credentials, cadastre
também `SF_USERNAME`, `SF_PASSWORD` e `SF_SECURITY_TOKEN`, e crie a variável
`SF_AUTH_MODE` com o valor `password` (aba Variables).

### 5.2 Cadastrar os nomes dos campos

Aba **Variables** → **New repository variable**, conforme o que o time
confirmar. Só crie as que forem diferentes do padrão:

| Name                  | Padrão                    | O que é                        |
|-----------------------|---------------------------|--------------------------------|
| `SF_OBJETO`           | `OrderExportReport__c`    | objeto consultado              |
| `SF_CAMPO_MARCA`      | `Brand__c`                | campo que identifica a marca   |
| `SF_CAMPO_STATUS_NF`  | `InvoiceStatus__c`        | status da aprovação da NF      |
| `DATA_INICIO_PADRAO`  | `2026-08-01`              | início da janela de dados      |
| `MODO_AUTONOMIA`      | `dominio`                 | regra marca × time interno     |
| `DOMINIOS_INTERNOS`   | `privalia.com,veepee.com` | e-mails do time interno        |

E a mais importante — `SF_ETAPAS`, que liga cada etapa aos campos reais.
Cole **em uma linha só**, trocando os nomes que o time confirmar:

```json
{"recebimento_po":{"rotulo":"Recebimento/confirmação do PO","campo_data":"PODownloadDate__c","campo_executor":"PODownloadBy__c","campo_condicao":"Download__c"},"atualizacao_status":{"rotulo":"Atualização do status","campo_data":"EvaluationDate__c","campo_executor":"EvaluationBy__c"},"upload_nf":{"rotulo":"Upload da nota fiscal","campo_data":"NFSentDate__c","campo_executor":"NFSentBy__c"},"agendamento_coleta":{"rotulo":"Agendamento da coleta","campo_data":"PickupScheduledDate__c","campo_executor":"CreatedById"}}
```

### 5.3 Desligar o modo demo

Aba **Variables** → clique em `MODO_DEMO` → troque o valor para `0` (ou apague
a variável).

### 5.4 Rodar

**Actions** → **Atualizar painel** → **Run workflow**.

Se der ❌ vermelho, clique no run e depois no passo que falhou: a mensagem diz
exatamente qual campo ou credencial está errado.

---

## Pronto

A partir daqui o painel se atualiza **sozinho todo dia às 08:00 de Brasília**.
Você não precisa fazer mais nada.

Para mudar o horário: abra `.github/workflows/atualizar-painel.yml` no GitHub,
clique no lápis ✏️, altere `cron: "0 11 * * *"` e faça commit.
O horário é sempre em **UTC** = horário de Brasília **+ 3 horas**.

---

## O que pedir ao time do Salesforce

Copie e cole a lista abaixo para eles:

> Preciso de acesso de leitura via API ao objeto `OrderExportReport__c`,
> a partir de 01/08/2026. Podem me passar:
>
> 1. **Credenciais**: Connected App com client credentials flow (Consumer Key +
>    Secret) ou usuário de integração com senha + security token, e o domínio
>    `https://....my.salesforce.com`.
> 2. **Confirmação dos nomes de API** destes campos em `OrderExportReport__c`:
>    - campo que identifica a **marca**
>    - `Download__c` e `PODownloadDate__c` — e **qual campo guarda quem flegou**
>      o `Download__c`
>    - `NFSentDate__c` — e **qual campo guarda quem subiu a nota fiscal**
>    - `EvaluationDate__c` e `InvoiceapprovalDate__c`
>    - campo com as **etapas do processo de aprovação** (Pendente, Associado, …)
>    - campo de data do **agendamento da coleta** e quem agendou
> 3. **Como distinguir usuário da marca de usuário interno**: pelo domínio do
>    e-mail, pelo Profile ou por uma lista de usuários? Se for por Profile,
>    quais são os nomes dos Profiles internos?

---

## Problemas comuns

| Sintoma                                        | Causa provável                                               |
|------------------------------------------------|--------------------------------------------------------------|
| Página 404 no link do Pages                     | Pages ainda não publicou; espere 2 min e recarregue          |
| "Não consegui ler dashboard.json"               | o workflow ainda não rodou com sucesso — veja a aba Actions  |
| Workflow falha em "Gerar o painel"              | nome de campo errado no `SF_ETAPAS` ou credencial inválida   |
| Painel abre mas sem marcas                      | `SF_CAMPO_MARCA` errado, ou nenhum pedido no período         |
| Todas as marcas com 0% de autonomia             | `MODO_AUTONOMIA`/`DOMINIOS_INTERNOS` invertendo a regra      |
| Coluna "Sem executor" alta                      | o campo de executor daquela etapa está vazio no Salesforce   |
