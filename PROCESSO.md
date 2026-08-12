# Processo de desenvolvimento

## Ferramentas usadas e finalidade

| Ferramenta | Papel no projeto |
|---|---|
| Codex | Agente principal de implementação: leitura do repositório, alterações incrementais, execução de testes, inspeção programática dos PDFs e validação dos contratos JSON |
| Antigravity | Auditor visual independente dos PDFs reais, usado para levantar famílias de layout, exemplos de verbas/bases, páginas com OCR e hipóteses de falha a serem reproduzidas |
| ChatGPT | Apoio conversacional para organizar requisitos, preparar checklists de auditoria e discutir alternativas de arquitetura e de tratamento de incerteza |

Nenhuma saída de agente foi tratada como fonte de verdade. O critério final foi
sempre a combinação de contrato do desafio, PDF renderizado, geometria extraída
e teste reproduzível. Relatórios dos agentes serviram como evidência
complementar e direcionaram a investigação.

## Divisão de papéis

O Codex atuou como agente principal e manteve a implementação. Antes de alterar
os parsers, ele leu a documentação e o código existente, executou a suíte e
gerou diagnósticos agregados. Depois comparou os JSONs temporários com páginas
renderizadas e transformou apenas falhas confirmadas em regressões.

O Antigravity fez uma leitura independente, especialmente útil no holerite:
identificou quatro famílias de layout, o falso texto nativo causado pelo carimbo
judicial no `payroll-04`, múltiplos blocos por página, valores negativos e
códigos iniciados por `/`.

O ChatGPT foi usado para decompor os requisitos do desafio em verificações
objetivas e para confrontar decisões com alternativas razoáveis. Não foi usado
para “embelezar” valores OCR nem para substituir inspeção dos documentos.

A decisão final permaneceu humana: os agentes propuseram e executaram, mas
contrato, escopo e aceitação foram revisados contra os arquivos reais.

## Onde os agentes erraram e como isso foi percebido

### 1. `date_raw` estava sendo corrigido indevidamente

Uma versão inicial possuía uma função/teste que transformava datas impossíveis:

```text
38/07/2025 -> ??/07/2025
31/02/2025 -> ??/??/2025
```

O teste estava verde, mas validava o comportamento errado. A falha apareceu ao
reler o contrato: `date_raw` é transcrição literal, não uma data normalizada.
A correção separou transcrição de plausibilidade e adicionou regressão para
garantir que valores impossíveis continuem literais.

### 2. A continuação de dias estava permissiva demais

O parser anexava horários de uma linha sem nova data ao último dia conhecido.
Isso podia capturar um horário de seção posterior ou mesclar duas ocorrências
iguais do mesmo dia. Testes pequenos não demonstravam o problema até a regra
ser confrontada com a geometria das tabelas reais.

A lógica foi reescrita para exigir adjacência, distância vertical compatível,
posição dentro das colunas de punch, ausência de marcador de nova seção e
ausência de conteúdo incompatível. Uma data repetida deixou de ser, sozinha,
prova de continuação.

### 3. Metadados do Ledger entravam como verbas

No holerite `payroll-01`, `REMUNERAÇÃOMES` e `DIAS/HORASTRAB` apareciam em
`fields`, embora fossem linhas de resumo do bloco. A auditoria independente
levantou o caso e a execução local reproduziu 48 falsos fields: 24 de cada
label.

Foi criado primeiro um teste que falhou no PDF real. Em seguida,
`_ledger_field()` passou a exigir o código numérico que identifica todas as
verbas reais desse layout. O teste direcionado e a suíte completa passaram, e
os 48 registros de metadados desapareceram sem alterar os outros layouts.

## O que foi reescrito manualmente

Não houve reescrita integral dos extratores após cada revisão. Foram feitas
intervenções pequenas, guiadas por evidência:

- a regra e o teste de `date_raw` foram reescritos para preservar o texto
  literal;
- a continuação do cartão foi substituída por uma verificação explícita de
  adjacência e geometria;
- o reconhecimento de verba Ledger foi restringido estruturalmente ao código
  numérico;
- a heurística de texto útil ganhou diversidade mínima de linhas para rejeitar
  o carimbo judicial sem tornar o leitor específico de holerite;
- testes artificiais foram evitados quando um PDF real fornecia uma regressão
  curta e estável.

O motivo dessas reescritas foi o mesmo: um teste verde não prova fidelidade ao
documento. Cada mudança precisava preservar a informação original, não apenas
produzir um JSON plausível.

## Três decisões com mais de uma resposta razoável

### 1. Worker Python e SQLite, em vez de Celery e Redis

Celery/Redis seria uma escolha válida para alto volume e vários workers. Para o
escopo do desafio, porém, adicionaria dois componentes operacionais antes de
haver necessidade comprovada. Um worker separado evita timeout HTTP, e a fila
persistente no SQLite sobrevive a reinício com implantação simples. A fronteira
do worker deixa aberta uma migração posterior.

### 2. OCR automático por página, em vez de OCR sempre

Executar Tesseract em todas as páginas simplificaria o fluxo, mas seria mais
lento e poderia degradar texto que o PDF já fornece com precisão. O pipeline
tenta texto nativo e aplica OCR apenas quando a camada não é útil. A decisão é
por página porque um mesmo PDF pode misturar páginas digitais e escaneadas.

### 3. Separação estrutural de `fields` e `bases`, em vez de whitelist rígida

Uma lista de nomes como “Base INSS” e “Valor Líquido” seria rápida, mas quebraria
com abreviações, acentos e novos layouts. O holerite localiza semanticamente o
cabeçalho, deriva regiões de coluna, encerra a tabela principal e só então lê a
seção de resultados. Termos conhecidos são apoio, não a arquitetura principal.

## O que quebra primeiro em produção?

O primeiro ponto de falha é OCR e detecção de layout. Documentos manuscritos,
degradados, inclinados, com grades fortes ou cabeçalhos muito diferentes podem
resultar em extração parcial ou página vazia. `time-card-04` já demonstra esse
limite: retornar `days: []` é mais honesto que fabricar datas e horários.

Em volume maior, o próximo limite é operacional. SQLite é adequado ao desafio,
mas contenção de escrita e vários workers exigiriam migrar fila e persistência
para serviços próprios.

## Onde eu não confio no que entreguei?

Principalmente no OCR de documentos degradados/manuscritos e no fallback quando
o cabeçalho da tabela não é identificado. Sem cabeçalho, um horário auxiliar
pode ser geometricamente indistinguível de uma batida adicional.

Também há confiança menor em layouts nunca vistos e na deduplicação de duas
vias baseada na sequência monetária: ela funciona nos exemplos, mas dois
recibos diferentes com os mesmos valores pediriam mais evidência estrutural.

Essa incerteza não é escondida. Caracteres duvidosos usam `?`, páginas não são
fabricadas e as limitações estão registradas em `SOLUCAO.md`.
