# Solução

## Links da entrega

- Aplicação publicada: [https://docparse.meric.dev.br/](https://docparse.meric.dev.br/)
- Repositório: [https://github.com/mericxy/docparse](https://github.com/mericxy/docparse)
- Planilhas de exemplo geradas: [`exemplos/planilhas/`](exemplos/planilhas/)

## Estado atual

O projeto usa um único pipeline de documentos com extratores específicos para
cartão de ponto e holerite. Estão implementados e testados a leitura híbrida de
PDF, os dois extratores, a API FastAPI, a fila persistida em SQLite, o worker
separado, a interface React de revisão, a correção do JSON e os downloads XLSX,
CSV e JSON. O empacotamento Docker com frontend, backend e worker também está
implementado e validado. A aplicação está publicada em servidor próprio e
acessível pela internet por meio de um Cloudflare Tunnel operado com
`cloudflared`.

## Como executar o que já está implementado

O caminho recomendado, sem depender de Python, Node ou Tesseract instalados no
host além do próprio Docker, é:

```bash
docker compose up --build
```

A interface fica em `http://localhost:8080`. `docker compose down` encerra os
serviços preservando o volume; `docker compose down -v` também apaga banco e
PDFs. O arquivo `.env.example` lista todas as opções do Compose.

Para execução local sem Docker, os requisitos de sistema são:

- Python 3;
- Tesseract com os idiomas português e inglês para processar páginas sem texto
  útil.

Instalação e testes:

```bash
python -m venv venv
source venv/bin/activate
pip install -r backend/requirements-dev.txt
python -m pytest -q
```

Uso independente da API:

```python
from backend.app.services.extraction import extract_cartao_ponto, extract_holerite

cartao = extract_cartao_ponto("arquivo.pdf")
holerite = extract_holerite("arquivo.pdf")
```

Execução do ciclo HTTP e do worker, em dois terminais com o ambiente virtual
ativado:

```bash
# terminal 1
uvicorn backend.app.main:app --reload

# terminal 2
python -m backend.worker
```

Instalação e execução do frontend em um terceiro terminal:

```bash
cd frontend
npm install
npm run dev
```

O Vite abre por padrão em `http://127.0.0.1:5173` e encaminha `/api` e
`/healthz` para a API local em `http://127.0.0.1:8000`. Assim, o desenvolvimento
local permanece same-origin e não exige ampliar o backend com CORS nesta fase.

Por padrão, banco e uploads são criados em `./data/`, diretório ignorado pelo
Git. A configuração operacional aceita:

```text
DATABASE_URL=sqlite:///./data/transcricoes.db
UPLOAD_DIR=./data/uploads
MAX_UPLOAD_SIZE_MB=10
JOB_STALE_AFTER_MINUTES=30
WORKER_POLL_INTERVAL_SECONDS=1
RETENTION_HOURS=24
```

## Stack escolhida

| Área | Escolha | Situação |
|---|---|---|
| Backend | Python, FastAPI e Pydantic | Implementado |
| PDF | PyMuPDF | Implementado |
| OCR | Tesseract por meio do PyMuPDF | Implementado |
| Persistência | SQLAlchemy síncrono e SQLite em modo WAL | Implementado |
| Assíncrono | Worker Python separado e fila no SQLite | Implementado |
| Exportação | openpyxl, CSV e JSON nativos | Implementado |
| Frontend | React, TypeScript e Vite | Implementado |
| Deploy | Servidor próprio, Docker Compose e Cloudflare Tunnel | Publicado e validado |

PyMuPDF foi escolhido porque fornece texto, palavras, bounding boxes e OCR na
mesma API. A escolha e as limitações do Tesseract estão detalhadas na seção de
OCR.

## Docker

O Compose possui três serviços:

```text
frontend (Nginx, porta 8080)
  -> /api e /healthz
backend (FastAPI/Uvicorn, porta 8000 apenas no loopback do host)
  -> volume docparse_data:/data
worker (mesma imagem Python e outro comando)
  -> volume docparse_data:/data
```

Backend e worker usam literalmente a mesma imagem. O primeiro executa Uvicorn;
o segundo troca apenas o comando para `python -m backend.worker`. Ambos recebem
`DATABASE_URL=sqlite:////data/transcricoes.db` e `UPLOAD_DIR=/data/uploads`,
portanto não existem bancos ou diretórios de upload isolados por container. O
volume nomeado sobrevive a restart, recreate e `docker compose down` sem `-v`.

A imagem Python usa Python 3.12 slim e instala Tesseract, `por` e `eng` pelo
gerenciador do sistema. Somente `backend/requirements.txt` entra na imagem;
pytest e httpx permanecem dependências de desenvolvimento. A imagem do
frontend usa Node 22 somente no estágio de build e copia o `dist` para Nginx.
O Vite não é executado em produção.

O frontend usa caminhos relativos. Nginx serve a SPA e encaminha `/api/*` e
`/healthz` ao serviço `backend` na rede privada do Compose. Isso mantém a
aplicação same-origin e evita liberar CORS. O limite do Nginx é configurado por
`NGINX_CLIENT_MAX_BODY_SIZE`, com default `11m` para permitir o multipart de um
PDF cujo limite de aplicação é 10 MB. Ao aumentar `MAX_UPLOAD_SIZE_MB`, esse
limite do proxy também precisa ser revisto.

O healthcheck do backend consulta apenas `/healthz`; o frontend só inicia após
a API ficar saudável. O worker também espera a API saudável, sem `sleep`
arbitrário. `.dockerignore` exclui ambientes virtuais, dependências locais,
artefatos, dados persistidos e `.env`. Os PDFs de `exemplos/` permanecem no
contexto porque o build do frontend os incorpora deliberadamente como assets
de demonstração; nenhuma imagem copia o restante do repositório por esse motivo.

### Validação do Compose

O build sem cache foi executado a partir de contexto limpo. O ciclo real pelo
proxy Nginx confirmou:

- frontend e health com HTTP 200;
- `time-card-01.pdf`: 202, worker, 5 páginas e 153 dias;
- `payroll-04.pdf`: 202, OCR no container, 5 blocos e 42 fields;
- PUT refletido no GET, JSON e XLSX para os dois tipos;
- Tesseract 5.3 com `por`, `eng` e `osd` disponíveis;
- jobs e correções preservados após restart/recreate de backend e worker;
- `RETENTION_HOURS`, banco e upload idênticos nos dois processos.

## Deploy

A aplicação está publicada em
[https://docparse.meric.dev.br/](https://docparse.meric.dev.br/) em um servidor
próprio. O frontend, o backend e o worker são executados pelo mesmo Docker
Compose validado localmente. A entrada pública é fornecida por um Cloudflare
Tunnel operado com `cloudflared`, que conecta o domínio à aplicação no servidor.

O deploy foi validado em 18 de agosto de 2026, inclusive por acesso sem sessão
prévia. Foram conferidos o carregamento público da interface e o ciclo completo
de upload, processamento pelo worker, revisão, salvamento e download. Backend e
worker compartilham o volume persistente descrito na seção de Docker; banco,
uploads e retenção usam a mesma configuração nos dois processos. Configurações
operacionais permanecem em variáveis de ambiente e nenhum segredo é versionado.

SQLite e os PDFs continuam dependendo do filesystem persistente desse servidor.
Essa implantação atende ao escopo da demonstração, mas não oferece alta
disponibilidade: uma indisponibilidade do host ou do túnel interrompe o acesso.
Uma operação distribuída exigiria migrar banco e arquivos para serviços
compartilhados, como PostgreSQL e armazenamento de objetos.

## Arquitetura do pipeline

O desenho é “um pipeline, extratores específicos”:

```text
upload validado
  -> PDF salvo no filesystem
  -> job persistido no SQLite
  -> worker separado
  -> leitura página a página com PyMuPDF
       -> texto nativo útil: preservar palavras e geometria
       -> texto insuficiente: OCR da página com Tesseract
  -> PdfPage / PdfWord / BoundingBox
  -> extrator selecionado pelo tipo informado no upload
       -> CartaoPontoExtractor
       -> HoleriteExtractor
  -> JSON literal persistido no SQLite
  -> revisão e correção pelo usuário
  -> exportador específico por tipo
  -> download
  -> limpeza pela política de retenção
```

OCR e texto nativo convergem para a mesma representação intermediária. Não
existem extratores paralelos como `HoleriteOcrExtractor` e
`HoleriteTextExtractor`. Assim, a diferença da fonte termina na camada de
leitura, e as regras de negócio são exercitadas da mesma forma.

As palavras preservam texto, página, bounding box, sequência de leitura e
origem. A informação geométrica permite localizar colunas pelo cabeçalho, sem
depender de coordenadas dos PDFs de exemplo.

## Processamento assíncrono e persistência

A arquitetura usa um worker Python separado, em vez de executar OCR e parsing
durante a requisição HTTP. O upload valida em chunks, confirma o PDF com magic
bytes e PyMuPDF, salva com UUID e cria o job; nenhum extrator é importado ou
executado pela rota de upload. O worker consulta e reivindica jobs persistidos
no SQLite, processa o PDF e grava o resultado ou erro em outra transação curta.

SQLite em modo WAL é suficiente para o volume e o escopo do desafio, mantém a
fila após reinicializações e evita a operação adicional de Redis, RabbitMQ e
Celery. Se o volume ou a concorrência crescerem, a fronteira do worker permite
migrar a fila e a persistência sem reescrever os extratores.

O PDF original fica no filesystem; estado do job e JSON revisável ficam no
SQLite. O JSON é a fonte da exportação, para que correções feitas na revisão
cheguem à planilha.

O claim é um único `UPDATE ... RETURNING`, condicionado a
`status = processando` e a `started_at` vazio ou vencido. Assim, dois workers
não selecionam normalmente o mesmo job. A recuperação de job zumbi usa o
timeout configurável `JOB_STALE_AFTER_MINUTES`: é deliberadamente simples e
pode duplicar processamento se uma extração legítima durar mais que esse
limite. A gravação final também confere o `started_at` do claim, impedindo que
um worker antigo sobrescreva o resultado de uma recuperação posterior.

SQLite usa `journal_mode=WAL`, `busy_timeout` e transações curtas. A sessão do
claim é encerrada antes de PyMuPDF/Tesseract e uma nova sessão é aberta somente
para persistir o resultado. Para a carga do desafio isso evita a complexidade
operacional de Redis/Celery; alta concorrência continua sendo um limite
consciente.

## API e exportação

A API implementa o contrato literal `POST /api/transcricoes`,
`GET/PUT /api/transcricoes/{id}`, download em
`GET /api/transcricoes/{id}/planilha` e `GET /healthz`. O `PUT` substitui o
`value` inteiro depois de validá-lo com o schema Pydantic do tipo persistido;
XLSX, CSV e JSON sempre usam esse valor corrigido e não reexecutam o extrator.

Os exports são montados em memória. No cartão, a largura vem do maior número de
batidas, dias vazios permanecem e as células usam `time_hhmm`; a leitura
literal `time_raw` continua preservada no JSON de auditoria. No holerite,
labels de `fields` viram colunas
na ordem da primeira aparição; `bases` não contaminam essa matriz. O XLSX usa
cabeçalho `#173772`, avisos amarelos `#FFF3CD`, avisos de sequência vermelhos
`#F8D7DA` e borda esquerda `#DC3545`; vermelho prevalece quando duas regras se
aplicam. Avisos são derivados no download, nunca persistidos no JSON.

O contrato tabular do holerite é ambíguo quando a mesma entrada de `pages[]`
contém mais de um field com o mesmo `label`. A matriz resolve essa ambiguidade
com uma identidade derivada `(label, ocorrência naquela entrada)`: a primeira
ocorrência usa o cabeçalho original, e as seguintes usam `(2)`, `(3)` etc.
Assim, `INSS`, `INSS`, `IRRF` vira `INSS`, `INSS (2)`, `IRRF`. A união dessas
identidades continua seguindo a primeira aparição no documento, e uma linha que
não possui determinada ocorrência recebe célula vazia.

Essa numeração existe somente em CSV/XLSX. O JSON persistido e baixado permanece
literal: nenhum `field.label` é reescrito e nenhum metadado de ocorrência é
adicionado. A estratégia preserva todos os valores, permite os três formatos,
evita concatenação e descarte silencioso e acomoda a ambiguidade observada em
blocos reais de `payroll-01` e `payroll-02`.

## Interface de revisão

O frontend é uma aplicação React/TypeScript única para os dois documentos.
Upload, feedback de estado, polling, visualização do PDF, estado dirty, salvar e
download são compartilhados. Apenas a matriz editável é específica: dias e
batidas para cartão; competências, fields e bases para holerite.

O PDF usa `URL.createObjectURL(file)` sobre o `File` selecionado. Essa foi a
alternativa de menor escopo: não exige endpoint para devolver PII, não expõe
caminho interno e cumpre o fluxo upload → revisão na mesma sessão. A limitação
consciente é que um refresh perde a referência local ao PDF e a tela não tenta
retomar um job apenas pelo ID. Como visualizadores nativos podem não renderizar
o blob em alguns navegadores integrados, a tela também oferece um link simples
para abrir o mesmo PDF local em nova aba; não foi adicionada uma dependência
pesada como PDF.js.

Após o `POST 202`, existe um único loop cancelável de polling. Ele consulta o
GET enquanto o status é `processando`, para imediatamente em `concluido` ou
`erro` e aborta requisições/timers ao desmontar ou iniciar outro documento. O
feedback é indeterminado; nenhum percentual artificial é exibido.

O `value` retornado é clonado para um draft editável. Warnings continuam fora
do contrato e são recalculados em renderização com as mesmas regras e cores do
XLSX. Um `PUT` explícito substitui o value inteiro. Downloads ficam desabilitados
enquanto o draft está dirty, evitando baixar silenciosamente a versão anterior;
depois de salvar, XLSX, CSV e JSON usam o valor persistido.

### Documentos de exemplo

A tela de upload oferece, como opção secundária, os oito PDFs versionados em
`exemplos/`. Essa pasta continua sendo a única fonte versionada. Antes de
`npm run dev` e `npm run build`, um script copia somente os nomes conhecidos
para `frontend/public/examples/`, diretório gerado e ignorado pelo Git. No
Docker, a raiz do repositório já é o contexto de build; o Dockerfile copia
`exemplos/` para a etapa Node, e o mesmo script produz `/examples/*.pdf` dentro
do `dist` servido pelo Nginx. Não existe caminho absoluto nem bind mount do host.

O navegador busca o asset estático uma vez, rejeita resposta vazia ou sem MIME
PDF e cria um `File` com o nome original. Seleção manual e exemplo convergem no
mesmo estado `file` e na mesma função `createTranscription`; portanto ambos usam
o POST multipart, validação, persistência, worker, extração e revisão existentes.
O prefixo do exemplo define automaticamente `cartao-ponto` ou `holerite`, mas a
seleção não dispara processamento sem a confirmação do usuário. O mesmo `File`
alimenta upload, blob do viewer e abertura em nova guia.

No cartão, editar a data altera somente `date_raw`. Ao editar um horário,
`time_raw` recebe literalmente o texto digitado. `time_hhmm` reaproveita apenas
as transformações inequívocas da regra do backend: zero à esquerda, separador e
marcadores comprovados `+`, `c` e `d`. Incerteza permanece e componentes
impossíveis viram `?`; texto fora do formato é preservado, não corrigido.
Batidas podem ser acrescentadas ao fim, alternando IN/OUT, ou removidas somente
do fim, preservando a ordem.

No holerite, `month`, `year`, os quatro atributos de cada field (`code`,
`label`, `reference`, `value`) e pares label/value de bases são editáveis como
strings. A edição detalhada identifica o field pelo índice original, não pelo
label. `bases` aparecem numa seção expansível separada e nunca
viram colunas de verba. A inspeção dos PDFs reais encontrou labels repetidos no
mesmo bloco em `payroll-01` e `payroll-02`; por isso uma célula pode conter
múltiplos editores identificados por código/referência. Cada editor atualiza o
field pelo índice original, sem sobrescrever o registro com label igual. A UI
informa, sem bloquear downloads, que CSV e XLSX representarão as ocorrências
em colunas adicionais como `INSS (2)`.

Cartões com páginas cujo `days[]` está vazio continuam com status concluído,
mas cada página ganha uma linha amarela “nenhum dia extraído”. Se todas as
páginas estiverem vazias, um aviso de alto nível explica que nenhuma linha foi
transcrita com segurança e que o download refletirá esse resultado vazio.
Nenhum warning é adicionado ao JSON.

## OCR

### Ferramenta

O OCR usa Tesseract local por meio de `page.get_textpage_ocr()` do PyMuPDF, com
idiomas `por+eng`, 300 DPI e `full=True`. O aplicativo não precisa gerar PNGs
temporários: o PyMuPDF rasteriza a página e integra o resultado do Tesseract em
uma `TextPage`, da qual são extraídas as mesmas palavras e bounding boxes do
caminho com texto nativo.

`full=True` é intencional. Quando o OCR é acionado, a camada existente já foi
classificada como ausente ou lixo e não deve ser misturada ao texto
reconhecido.

### Motivos da escolha

- operação simples e integração direta com a representação já usada pelo
  leitor;
- custo de licença e de uso zero;
- nenhuma API externa, chave ou segredo;
- nenhuma dependência de disponibilidade ou limite de um serviço cloud;
- maior privacidade para PDFs com nome, CPF, salário e jornada;
- compatibilidade com execução em worker e instalação em imagem Docker.

O processamento é local ao processo Python e não realiza chamadas de rede. Na
arquitetura completa ele será executado no worker, mantendo os documentos
dentro do ambiente controlado. Isso reduz exposição de PII e facilita uma
operação isolada de serviços externos; não substitui os demais controles de
LGPD, retenção e acesso.

### Dependências do host

Além do pacote Python PyMuPDF, o host precisa do executável Tesseract e dos
dados de idioma português e inglês. Exemplos de instalação:

```bash
# Debian/Ubuntu
apt-get install tesseract-ocr tesseract-ocr-por tesseract-ocr-eng

# macOS com Homebrew
brew install tesseract tesseract-lang
```

A instalação pode ser conferida com:

```bash
tesseract --version
tesseract --list-langs
```

A imagem Docker instala essas dependências de sistema explicitamente; não
basta declarar PyMuPDF em `requirements.txt`.

### Pipeline

```text
texto embedded
  -> validação de texto útil por página
  -> OCR local somente quando necessário
  -> PdfPage / PdfWord / BoundingBox
  -> mesmo extrator específico
```

Cada página tenta primeiro a camada nativa. Uma camada é útil quando possui ao
menos quatro tokens alfanuméricos e vinte caracteres alfanuméricos. Camadas
curtas, com menos de vinte tokens informativos, também precisam ocupar ao menos
três linhas visuais. Esse segundo critério rejeita, de forma genérica, carimbos
ou números de página sobrepostos a um documento escaneado.

OCR só é executado nas páginas que falham nessa verificação. Isso evita custo e
degradação desnecessários em documentos que já possuem texto confiável. A
heurística é deliberadamente genérica; o leitor compartilhado não procura
palavras como “Entrada”, “Verba” ou “Salário”.

Caracteres não reconhecidos não são completados por probabilidade. Quando a
incerteza pode ser localizada, ela é representada com `?`. Não existem
substituições globais como `O -> 0` ou `I -> 1`.

### Limitações

- Tesseract é imperfeito em imagens degradadas, inclinadas, manuscritas ou com
  grades fortes; aumentar indiscriminadamente os 300 DPI eleva custo sem
  resolver essas classes de problema.
- O caminho atual recebe a camada textual produzida pelo PyMuPDF, mas não uma
  confiança confiável por caractere. `PdfWord.confidence` permanece `None`; um
  score não é fabricado.
- `\ufffd` é convertido em `?`, e validações estruturais conseguem marcar como
  incertos alguns componentes impossíveis. Porém, se o Tesseract produzir um
  caractere errado e plausível, sem erro de Unicode e dentro do formato
  esperado, ele pode passar sem ser detectado.
- Os dados `por` e `eng` precisam estar instalados no sistema. Quando Tesseract
  ou os idiomas faltam, o pipeline encerra com `OcrError`, mensagem sanitizada
  e encadeamento da exceção original, sem incluir texto ou PII do documento.
- Não há correção global de caracteres, OCR especializado em manuscrito nem
  serviço cloud como fallback.

No recibo OCR de `payroll-04`, a inspeção geométrica mostrou uma falha mais
específica: labels impressos começam alinhados ao cabeçalho da coluna, mas o
primeiro token reconhecido de linhas como `DSR COMISSAO` aparece 4–5 pontos à
direita quando a primeira letra se perde junto à grade vertical. O parser de
recibo agora deriva o início e a largura de um glifo do próprio cabeçalho e,
somente quando esse deslocamento ocorre em palavra OCR, prefixa `?`. Ele não
inventa a letra: `SR COMISSAO` vira `?SR COMISSAO`. Labels alinhados como
`SALARIO` e `INSS MES` não recebem `?`. Se uma seção não possui âncora
geométrica equivalente, a omissão plausível continua sem correção automática.

## Decisões do cartão de ponto

- `date_raw` é transcrição literal. Uma data como `38/07/2025` continua sendo
  `38/07/2025`; plausibilidade é uma validação derivada e não pode reescrever o
  valor lido.
- Dias visualmente presentes são preservados mesmo sem batidas, com
  `punches: []`.
- Batidas mantêm a ordem visual e alternam `IN`, `OUT`, `IN`, `OUT`. Uma
  quantidade ímpar não é completada artificialmente.
- `time_raw` preserva a impressão, inclusive marcadores documentais como `+`,
  `c` e `d`. `time_hhmm` remove apenas decoração inequívoca e não torna um
  horário impossível válido.
- As colunas são localizadas semanticamente pelo cabeçalho. Horários nas
  colunas auxiliares, como `H.Ext`, `Ad.Not`, `Abono` e `Falta`, não entram em
  `punches`.
- A continuação de uma linha exige adjacência e geometria compatível. Igualdade
  de data, sozinha, não autoriza mesclar registros.
- Páginas, dias e punches nunca são ordenados por data ou horário.
- Datas compostas somente pelo dia (`01`, `02`, ...) são comparadas apenas
  dentro da mesma página física. Não se infere mês/ano e não se compara a
  virada entre páginas.

## Decisões do holerite

- `fields` contém apenas verbas da tabela principal. `bases` contém a seção
  separada de bases, totais e resultados.
- A separação é estrutural: cabeçalho, regiões de coluna e término da tabela são
  a regra principal. Listas de termos servem apenas como apoio.
- Código, label, referência e valor permanecem strings. Valores brasileiros,
  inclusive negativos como `-433,20`, nunca são convertidos para `float`.
- O código não é incorporado ao label. Quando um layout não imprime código ou
  referência, a saída usa `""`.
- Uma página pode conter vários blocos e competências, todos com o mesmo número
  físico de página e na ordem original. Fragmentos Ledger que atravessam a
  quebra de página são unidos apenas quando os totais mostram que o bloco
  anterior ainda estava aberto.
- No Ledger, uma verba real começa com código numérico. Linhas de resumo como
  `REMUNERAÇÃOMES` e `DIAS/HORASTRAB` não entram em `fields`.
- O recibo escaneado em duas vias é deduplicado pela estrutura de valores da
  mesma página.
- Nomes de mês degradados pelo OCR geram `month: "??"`; a competência não é
  inventada a partir das páginas vizinhas.
- Competências consecutivas idênticas representam blocos adicionais possíveis
  (por exemplo MÊS/ACERTO) e não geram warning. A próxima competência distinta
  é comparada com a última legível distinta.

## Política de retenção e privacidade

A retenção escolhida é de 24 horas a partir do upload.

Durante esse período serão mantidos:

- PDF original no filesystem;
- estado do job e JSON da transcrição no SQLite;

Os arquivos de exportação são gerados em memória e não são retidos. Após 24
horas, o worker remove o PDF original e o registro associado; arquivo já
ausente não interrompe a limpeza. Logs permanentes não devem conter nome,
CPF, matrícula, texto integral ou valores do documento. Diagnósticos usam
somente identificador técnico, tipo, status, tamanho, duração, contagens e tipo
da exceção. O nome original do upload não é persistido nem registrado.

## Testes escolhidos

Os testes protegem comportamentos que já falharam ou que alterariam o contrato:

- detecção de texto lixo e OCR somente quando necessário, inclusive o carimbo
  judicial sobre `payroll-04`;
- preservação de dias sem batida, batidas ímpares, ordem e `date_raw` literal;
- continuação legítima e rejeição de linhas incompatíveis;
- exclusão de colunas auxiliares e fallback conservador sem cabeçalho;
- valores monetários brasileiros e negativos como string;
- separação de `fields` e `bases`, código separado do label e campos ausentes
  representados por string vazia;
- páginas vazias, múltiplos blocos, códigos iniciados por `/`, OCR e
  deduplicação de vias;
- regressão real impedindo `REMUNERAÇÃOMES` e `DIAS/HORASTRAB` em `fields`.
- upload em chunks, validação real de PDF e garantia de que o `POST` não chama
  extratores;
- estados públicos, validação e substituição do `value`, inclusive a correção
  chegando ao download;
- claim atômico, recuperação de job zumbi, erro sanitizado e retenção;
- transposição CSV/XLSX, ordem de aparição e todas as prioridades de avisos.
- polling encerrando em sucesso/erro e cancelamento do ciclo compartilhado;
- regras de warning no frontend, inclusive vermelho prevalecendo sobre amarelo;
- edição literal de horário e dinheiro, labels repetidos e bases separadas;
- estado dirty bloqueando download até o PUT e payload sem flags derivadas.
- colunas de ocorrência para labels repetidos, inclusive união entre linhas e
  correção da segunda ocorrência chegando a JSON, CSV e XLSX;
- sequência day-only por página e competências repetidas legítimas;
- edição de `code`, `label`, `reference` e `value` pelo índice do field;
- representação explícita de todas as páginas de cartão com `days: []`;
- marcação geométrica conservadora das omissões de primeiro caractere no
  recibo OCR, sem falsos `?` em labels alinhados.

Além das fixtures pequenas, os extratores foram executados e inspecionados nos
oito PDFs de cartão de ponto e holerite presentes em `exemplos/`.

Na validação integrada da Fase 5, `time-card-01`, `time-card-02`, `payroll-03`
e `payroll-04` percorreram API e worker reais. Uma correção por PUT foi
confirmada no GET, no JSON e no XLSX. O upload/polling também foi exercitado
pelo proxy do Vite. Em 18 de agosto de 2026, a aplicação publicada também passou
por auditoria visual em navegador real. Landing page, tabelas largas, viewer
nativo de PDF e comportamento responsivo foram conferidos sem problemas visuais
pendentes.

## Limitações e cortes conscientes

### Cartão de ponto manuscrito

`exemplos/time-card-04.pdf` contém escrita manual degradada sobre uma grade
colorida. O Tesseract não reconhece datas, cabeçalho e batidas com confiança;
por isso as páginas retornam `days: []`. Fabricar as linhas visuais seria pior
que admitir a ausência de extração. Melhorias exigiriam deskew, remoção de
grade, pré-processamento de imagem ou OCR especializado em manuscrito.

### OCR imperfeito

No `payroll-04`, a omissão inicial detectável na tabela/total recebe `?`, mas
alguns labels de bases sem âncora equivalente ainda podem perder caracteres, e
quatro competências permanecem com mês `??`. Não há correção por aproximação
léxica.

### Fallback sem cabeçalho

Quando não existe cabeçalho reconhecível, o cartão de ponto só corta uma coluna
auxiliar se houver uma separação geométrica clara. Sem essa evidência, não é
possível distinguir de maneira confiável uma batida adicional de um horário
auxiliar. O fallback prefere ser conservador a fingir precisão.

### Variações de layout

Os extratores cobrem as famílias observadas nos exemplos, mas cabeçalhos muito
diferentes, tabelas rotacionadas, manuscritos e imagens de baixa resolução são
o ponto mais frágil. Uma camada extensa de texto lixo ainda pode superar a
heurística genérica e evitar OCR indevidamente.

### Disponibilidade do deploy

O servidor próprio e o Cloudflare Tunnel não possuem redundância ou failover.
Essa é uma decisão consciente para a demonstração: a URL é pública e o ciclo
completo está operacional, mas sua disponibilidade ainda depende de um único
host e da conexão do túnel.

### Retomada após refresh

A interface conserva o PDF somente no blob local da sessão atual. Recarregar a
página perde PDF, job e draft. Um endpoint autenticado de recuperação do PDF e
persistência segura do ID seriam necessários para retomada, mas aumentariam o
escopo e a superfície de exposição de PII.

## O que quebra primeiro em produção

OCR e heurísticas de layout quebram antes da camada de aplicação. Manuscritos,
digitalizações inclinadas, tabelas sem cabeçalho ou layouts muito diferentes
podem produzir extração parcial ou páginas vazias. Em seguida, numa escala
maior que a prevista, SQLite se torna o limite de concorrência da fila e deve
ser substituído por infraestrutura dedicada.

## Onde a solução ainda inspira menos confiança

A menor confiança está no OCR de documentos degradados/manuscritos e no
fallback quando o cabeçalho não pode ser identificado. Também merece auditoria
futura a deduplicação de recibos: duas vias idênticas são tratadas corretamente,
mas dois recibos distintos com a mesma sequência monetária exigiriam evidência
adicional para não serem confundidos.
