# Solução

## Estado atual

O projeto usa um único pipeline de documentos com extratores específicos para
cartão de ponto e holerite. Neste momento estão implementadas e testadas a
leitura de PDF, a escolha automática entre texto nativo e OCR, a representação
intermediária com geometria e os dois extratores.

FastAPI, persistência, revisão, exportação, frontend e empacotamento Docker
fazem parte da arquitetura escolhida, mas ainda não foram implementados nesta
fase. Essa distinção é intencional: este documento registra tanto o que existe
quanto as decisões que orientam as próximas etapas, sem apresentar trabalho
planejado como concluído.

## Como executar o que já está implementado

Requisitos de sistema:

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

## Stack escolhida

| Área | Escolha | Situação |
|---|---|---|
| Backend | Python, FastAPI e Pydantic | FastAPI planejado; extratores em Python implementados |
| PDF | PyMuPDF | Implementado |
| OCR | Tesseract por meio do PyMuPDF | Implementado |
| Persistência | SQLAlchemy e SQLite em modo WAL | Planejado |
| Assíncrono | Worker Python separado e fila no SQLite | Arquivo reservado; processamento planejado |
| Exportação | openpyxl, CSV e JSON nativos | Planejado |
| Frontend | React, TypeScript e Vite | Planejado |
| Deploy | Docker Compose com frontend, backend e worker | Planejado |

PyMuPDF foi escolhido porque fornece texto, palavras, bounding boxes e OCR na
mesma API. Tesseract é local, não envia PII para terceiros e é suficiente para
os documentos impressos dos exemplos. A contrapartida é menor qualidade em
manuscritos e imagens degradadas.

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

A arquitetura escolhe um worker Python separado, em vez de executar OCR e
parsing durante a requisição HTTP. O upload deve apenas validar, persistir e
enfileirar. O worker consulta e reivindica jobs persistidos no SQLite, processa
o PDF e grava o resultado ou o erro.

SQLite em modo WAL é suficiente para o volume e o escopo do desafio, mantém a
fila após reinicializações e evita a operação adicional de Redis, RabbitMQ e
Celery. Se o volume ou a concorrência crescerem, a fronteira do worker permite
migrar a fila e a persistência sem reescrever os extratores.

O PDF original fica no filesystem; estado do job e JSON revisável ficam no
SQLite. O JSON é a fonte da exportação, para que correções feitas na revisão
cheguem à planilha.

## Detecção de texto e OCR

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

## Política de retenção e privacidade

A retenção escolhida é de 24 horas a partir do upload.

Durante esse período serão mantidos:

- PDF original no filesystem;
- estado do job e JSON da transcrição no SQLite;
- arquivos de exportação eventualmente gerados.

Após 24 horas, um processo de limpeza deve remover arquivo original,
exportações e registros associados. Logs permanentes não devem conter nome,
CPF, matrícula, texto integral ou valores do documento. Diagnósticos usam
somente identificador técnico, página, fonte (`embedded`/`ocr`), contagens,
status, duração e erro sanitizado.

Essa política está definida, mas a rotina de persistência e limpeza ainda será
implementada junto da API e do worker.

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

Além das fixtures pequenas, os extratores foram executados e inspecionados nos
oito PDFs de cartão de ponto e holerite presentes em `exemplos/`.

## Limitações e cortes conscientes

### Cartão de ponto manuscrito

`exemplos/time-card-04.pdf` contém escrita manual degradada sobre uma grade
colorida. O Tesseract não reconhece datas, cabeçalho e batidas com confiança;
por isso as páginas retornam `days: []`. Fabricar as linhas visuais seria pior
que admitir a ausência de extração. Melhorias exigiriam deskew, remoção de
grade, pré-processamento de imagem ou OCR especializado em manuscrito.

### OCR imperfeito

No `payroll-04`, texto e valores impressos são extraídos, mas alguns labels
perdem caracteres e quatro competências permanecem com mês `??`. O texto lido
é preservado em vez de “corrigido” por aproximação léxica.

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

### Funcionalidades ainda fora desta fase

API completa, fila persistente, revisão, banco, exportação, frontend e Docker
não foram antecipados durante as fases de extração. Eles continuam necessários
para fechar o ciclo completo descrito no desafio.

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
