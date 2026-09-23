# Autonomia de Marcas

Aplicação Python que consulta eventos de pedidos no Salesforce e mede quanto
cada marca executa de forma independente as quatro etapas do fluxo:

1. Recebimento/confirmação do PO
2. Atualização do status
3. Upload da nota fiscal
4. Agendamento da coleta

Além disso, mede o tempo que o **backoffice** leva em cada etapa da aprovação
da nota fiscal (envio → avaliação → aprovação).

O resultado é um painel HTML de duas abas, publicado no GitHub Pages e
atualizado automaticamente todo dia.

> **Começando do zero?** Leia o [PASSO_A_PASSO.md](PASSO_A_PASSO.md) — é o guia
> clicando na tela, sem precisar saber Git.

## Instalação local (opcional)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
Copy-Item .env.example .env
```

Preencha no `.env` as credenciais Salesforce e substitua os nomes de objeto e
campos pelos nomes reais da organização. `SF_ETAPAS` é um JSON com os campos de
data e de executor das quatro etapas.

## Execução

```powershell
autonomia-marcas testar            # valida .env e conexão
autonomia-marcas executar          # roda o pipeline e gera os arquivos
autonomia-marcas executar --demo   # dados fictícios, não acessa o Salesforce
```

Período específico:

```powershell
autonomia-marcas executar --inicio 2026-09-01T00:00:00 --fim 2026-09-16T00:00:00
```

Evolução usando o histórico acumulado:

```powershell
autonomia-marcas evolucao --inicio 2026-09-01 --fim 2026-09-16
```

Para ver o painel localmente:

```powershell
python -m http.server 8000 --directory docs
# abra http://localhost:8000
```

Abrir o `index.html` com duplo clique **não funciona**: o navegador bloqueia a
leitura do `dashboard.json` em `file://`.

## Arquivos gerados

Em `OUTPUT_DIR` (padrão `output/`, e `dados/` quando roda no GitHub):

- `historico_autonomia.csv` — histórico de cada marca, etapa e execução.
- `status_atual.xlsx` — resumo atual, detalhe por etapa e aba do backoffice.
- `evolucao_periodo.xlsx` — score no começo e no fim de um período.

Em `DOCS_DIR` (padrão `docs/`, o que o GitHub Pages publica):

- `dashboard.json` — dados consumidos pelo HTML.
- `index.html` — o painel.

## Contrato do dashboard.json

```json
{
  "atualizado_em": "2026-09-22T12:00:00+00:00",
  "status_atual": [],
  "detalhes": [],
  "historico": [],
  "backoffice": {
    "total_notas": 0, "aprovadas": 0, "pendentes": 0,
    "media_total_horas": null,
    "por_perna": [], "ranking_marcas": [], "fila": [], "evolucao": []
  }
}
```

O HTML e o JSON ficam na mesma pasta `docs/`, publicados na mesma URL — por
isso não há problema de CORS, e o `fetch("dashboard.json")` funciona direto.

## Atualização automática

O arquivo `.github/workflows/atualizar-painel.yml` roda todo dia às **08:00 de
Brasília** (11:00 UTC), consulta o Salesforce, regrava `docs/dashboard.json` e
faz commit. O GitHub Pages republica sozinho em cerca de um minuto.

Para mudar o horário, edite a linha `cron: "0 11 * * *"` (sempre em UTC:
horário de Brasília + 3 horas).

Também dá para rodar na hora pelo botão **Run workflow** na aba **Actions**.

### Alternativa: Windows Task Scheduler

Se preferir rodar no seu computador:

- Programa: `C:\caminho\do\projeto\.venv\Scripts\python.exe`
- Argumentos: `-m autonomia_marcas.cli executar`
- Diretório inicial: `C:\caminho\do\projeto`

Nesse caso o painel só atualiza com o PC ligado, e você ainda precisa publicar
o `dashboard.json` em algum lugar acessível — por isso o GitHub Actions é a
opção recomendada.

## Classificação de autonomia

| Score      | Classificação          |
|------------|------------------------|
| >= 90%     | Autônomo               |
| 50% a 89%  | Parcialmente autônomo  |
| < 50%      | Em treinamento/suporte |

O score geral de uma marca é a **média simples das 4 etapas (peso igual)**.

Uma etapa só entra na conta quando foi concluída e o executor foi identificado.
Execução com executor desconhecido é **ignorada**, não contada como 0% — assim
uma falha de cadastro no Salesforce não pune a marca. A coluna "Sem executor"
no painel mostra quantas caíram nesse caso.

### Quem é "a marca" e quem é "time interno"

Configurável em `MODO_AUTONOMIA`:

| Modo      | Como decide                                                     |
|-----------|-----------------------------------------------------------------|
| `dominio` | e-mail do executor em `DOMINIOS_INTERNOS` → interno; resto → marca |
| `perfil`  | `Profile.Name` do executor em `PERFIS_INTERNOS` → interno        |
| `lista`   | Id ou e-mail listado em `config/usuarios_internos.txt` → interno  |

Comece com `dominio`; se os usuários das marcas tiverem e-mail corporativo da
Privalia, troque para `perfil` ou `lista`.

## Evolução dentro de um período

```
autonomia-marcas evolucao --inicio 2026-09-01 --fim 2026-09-16
```

Lê o `historico_autonomia.csv` (o pipeline precisa ter rodado mais de uma vez
no período) e gera `evolucao_periodo.xlsx` com, por marca: score no início,
score no fim, `delta` e a tendência (`Evoluindo` / `Estável` / `Regredindo`,
usando ±5 p.p. como limiar de "estável" — ajustável em `LIMIAR_EVOLUCAO` em
`evolucao.py`).

## Testes

```powershell
pip install -e ".[dev]"
pytest
```

## Estrutura

```
src/autonomia_marcas/
  config.py       lê o .env, valida e descreve as etapas
  salesforce.py   autenticação OAuth2 + SOQL paginado
  executores.py   decide marca x time interno (3 modos)
  metricas.py     autonomia por marca/etapa e score geral
  backoffice.py   tempos de aprovação da NF, fila e ranking
  evolucao.py     comparação início x fim do período
  saida.py        CSV, Excel e dashboard.json
  demo.py         dados fictícios para testar sem o Salesforce
  pipeline.py     orquestra tudo
  cli.py          comandos testar / executar / evolucao
docs/             o painel publicado (index.html + dashboard.json)
```

## O que ainda precisa vir do time do Salesforce

Confirme estes nomes de campo antes de rodar em produção:

- o campo da **marca** no `OrderExportReport__c` (`SF_CAMPO_MARCA`);
- **quem flegou** o `Download__c` — o campo lookup de User (ex.: `PODownloadBy__c`);
- **quem subiu a nota fiscal** — o campo lookup de User;
- o campo com o **status do processo de aprovação** (Pendente, Associado, …);
- o campo de data do **agendamento da coleta**.

Todos entram no `.env` (ou nas Variables do GitHub), sem mexer em código.
