# Desafio Técnico — Quick Filler

## Contexto

A Quick Filler transcreve documentos trabalhistas em PDF — cartões de ponto e holerites — para planilhas estruturadas. Na prática isso significa lidar com centenas de layouts diferentes, documentos escaneados, OCR imperfeito e a exigência de que **um número errado nunca passe despercebido**.

Este desafio é uma versão reduzida do nosso produto.

## O que você vai construir

Uma aplicação web publicada na internet que faz o caminho completo, para **cartão de ponto** e **holerite**:

```
enviar PDF  →  processar  →  revisar a transcrição  →  baixar a planilha
```

Exatamente o fluxo do produto real:

1. **Envio** — o usuário escolhe o PDF e o tipo de documento
2. **Processamento** — leva tempo; a interface acompanha até terminar
3. **Revisão** — a transcrição aparece numa tabela editável, ao lado do PDF, com os problemas destacados
4. **Download** — a planilha sai com os dados já corrigidos

**Um pipeline, dois extratores.** Os dois tipos compartilham envio, processamento, revisão e download — o que muda é a leitura do documento e a forma da planilha. Se você acabar com duas aplicações paralelas, provavelmente errou a divisão.

## Tempo esperado

**Cerca de 14 horas.**

Não é prova de resistência, e não recompensamos volume de código. Se estiver estourando, **corte escopo e escreva em `SOLUCAO.md` o que cortou e por quê**. Decidir o que sacrificar sob prazo é parte do que avaliamos — uma entrega menor e honesta vale mais que uma grande e frágil.

Se for cortar, corte **profundidade de um tipo de documento**, não o ciclo. Preferimos os dois tipos lidos parcialmente com o fluxo inteiro funcionando do que um tipo perfeito sem interface e sem deploy.

## Os documentos

Os PDFs de exemplo estão em `exemplos/`.

**Cartão de ponto** tem uma linha por dia do período e, em cada linha, as batidas do funcionário em pares entrada/saída.

**Holerite** tem uma tabela de verbas (vencimentos e descontos) e, numa seção separada, as bases e totais — Base INSS, Base IR, FGTS, Total Vencimentos, Valor Líquido.

Em nenhum dos dois todos os registros seguem o padrão, e o que fazer com as exceções é parte do desafio — não vamos enumerá-las aqui.

**Parte dos exemplos é escaneada**: imagem pura, sem camada de texto. Extrair só o texto embutido devolve vazio nesses arquivos, então sua solução precisa reconhecer o caso e passar por OCR. A ferramenta é escolha sua — Tesseract, um serviço de nuvem, o que preferir — e a escolha entra no `SOLUCAO.md`. É assim que a maior parte do que recebemos chega.

Duas regras não negociáveis, para os dois tipos:

- **Nunca invente um valor.** Se um caractere não deu para ler, ele vai como `?`. Um valor errado com aparência de certo é o pior resultado possível neste domínio — pior que um campo vazio.
- **Nunca produza uma data impossível.** `38/07` ou o mês `13` significam erro de leitura, não uma data.

---

# Formato de saída

Estes são os formatos **reais** que usamos em produção. São obrigatórios e literais: é por eles que comparamos as entregas de todo mundo pelo mesmo critério, independente da linguagem escolhida.

## Cartão de ponto

```jsonc
{
  "pages": [
    {
      "page": 1,
      "days": [
        {
          "date_raw": "21/05/2019",
          "punches": [
            { "kind": "IN",  "time_raw": "08:25", "time_hhmm": "08:25" },
            { "kind": "OUT", "time_raw": "18:25", "time_hhmm": "18:25" }
          ]
        },
        { "date_raw": "25/05/2019", "punches": [] }
      ]
    }
  ]
}
```

| Campo | Significado |
|---|---|
| `pages[].page` | Número da página no PDF, começando em 1 |
| `days[]` | Um item por linha do documento, **na ordem em que aparecem** — não ordene por data |
| `date_raw` | A data exatamente como está impressa, sem normalizar |
| `punches[]` | As batidas na ordem do documento; lista vazia quando o dia não tem batida |
| `kind` | `IN` ou `OUT` |
| `time_raw` | O horário exatamente como está impresso |
| `time_hhmm` | O horário normalizado para `HH:MM`, 24 horas |

## Holerite

```jsonc
{
  "pages": [
    {
      "page": 1,
      "year": "2020",
      "month": "01",
      "fields": [
        { "code": "0010", "label": "Salário Base",     "reference": "220,00", "value": "2.389,77" },
        { "code": "5560", "label": "Horas Extras - 50%", "reference": "8,00",  "value": "155,91" },
        { "code": "0998", "label": "INSS",              "reference": "",      "value": "262,87" }
      ],
      "bases": [
        { "label": "Base INSS",        "value": "2.545,68" },
        { "label": "Total Vencimentos", "value": "2.545,68" },
        { "label": "Valor Líquido",     "value": "2.282,81" }
      ]
    }
  ]
}
```

| Campo | Significado |
|---|---|
| `page` | Número da página no PDF, começando em 1 |
| `year` / `month` | Competência, como string. `month` de `"01"` a `"12"`, com zero à esquerda |
| `fields[]` | **Somente** as verbas da tabela principal de vencimentos e descontos |
| `code` | Código da verba, se o documento mostrar. String vazia quando não houver |
| `label` | Descrição da verba exatamente como impressa, **sem o código** |
| `reference` | A coluna de quantidade/referência (QTDE, REF), se existir. String vazia quando não houver |
| `value` | Valor monetário |
| `bases[]` | **Somente** as bases e totais da seção separada, abaixo da tabela de verbas |

A separação entre `fields` e `bases` é a decisão central aqui. `Base INSS` e `Valor Líquido` não são verbas — não entram em `fields`. Errar essa divisão contamina a planilha inteira.

**Valores monetários são string, no formato brasileiro** — `"2.389,77"`, não `2389.77`. Guardamos o que estava impresso; converter para float perde informação e introduz erro de arredondamento.

## Para os dois: `_raw` e normalizado

Repare no par `date_raw` / `time_raw` versus `time_hhmm`: guardamos **o que o documento diz** e **o que você interpretou**, separadamente. Quando os dois divergem, dá para auditar. Não descarte o original.

## Incerteza

Quando um caractere não deu para ler com segurança, use `?` no lugar dele:

```jsonc
{ "kind": "IN", "time_raw": "0?:25", "time_hhmm": "0?:25" }
{ "code": "0010", "label": "Salário Base", "reference": "", "value": "2.3?9,77" }
```

Isso é melhor que descartar o registro e infinitamente melhor que chutar. A incerteza é **por caractere**, não por linha — dizer "esse dígito eu não li" é informação útil; "essa linha inteira é duvidosa" quase nunca é.

## Avisos são derivados, não armazenados

Cada tipo tem duas situações que merecem destaque na tabela e na planilha:

**Cartão de ponto**
- **Batidas ímpares** — o dia tem número ímpar de batidas, então falta uma entrada ou uma saída
- **Data não sequencial** — a data da linha quebra a sequência do documento, o que costuma indicar erro de leitura

**Holerite**
- **Página vazia** — a página existe no PDF mas nenhum dado saiu dela
- **Mês não sequencial** — a competência não é exatamente o mês seguinte à página anterior. Dezembro → janeiro conta como consecutivo; páginas cuja competência não deu para ler não quebram a cadeia, comparam-se as próximas legíveis entre si

Nenhum deles é campo no JSON: todos saem **do próprio dado**, calculados na hora de exibir. Um holerite com 12 competências em ordem e um `13` no meio não precisa de flag — precisa de alguém que compare com as vizinhas.

---

# As planilhas

Formato real dos nossos exports. Em ambos, cabeçalho em negrito branco sobre o fundo `#173772`.

## Cartão de ponto

- Coluna `Data`, seguida de `Entrada 1`, `Saída 1`, `Entrada 2`, `Saída 2`, … alternando, com tantos pares quantos o dia com mais batidas exigir
- Uma linha por dia, na ordem do documento

## Holerite

- Colunas fixas `Pág.`, `Mês`, `Ano`
- Depois, **uma coluna por verba distinta**, formada pela união de todos os `label` de `fields`, na ordem de primeira aparição no documento
- Uma linha por página. Na célula, o valor daquela verba naquela página; vazio quando a verba não aparece ali

Ou seja: o documento é uma lista vertical de verbas por página, e a planilha é uma matriz larga. Essa transposição é o trabalho.

## Destaques de linha

| Situação | Preenchimento | Extra |
|---|---|---|
| Batidas ímpares, página vazia, ou algum `?` na linha | `#FFF3CD` (amarelo) | — |
| Data ou mês não sequencial | `#F8D7DA` (vermelho) | Borda esquerda `#DC3545` na primeira célula |

Quando as duas valem para a mesma linha, **vermelho ganha**.

Formatos aceitos para download: `.xlsx` (preferido), `.csv` ou `.json`.

---

# API HTTP

O contrato abaixo é obrigatório e literal — é por ele que avaliamos a precisão automaticamente, independente da linguagem que você escolher. Divergir dele significa nota zero em precisão, mesmo com a extração perfeita.

#### `POST /api/transcricoes`

`multipart/form-data` com dois campos:

- `arquivo` — o PDF
- `tipo` — `cartao-ponto` ou `holerite`

```http
HTTP/1.1 202 Accepted
{ "id": "abc123" }
```

#### `GET /api/transcricoes/:id`

```http
HTTP/1.1 200 OK
{
  "id": "abc123",
  "tipo": "cartao-ponto",
  "status": "concluido",
  "erro": null,
  "value": { "pages": [ ... ] }
}
```

`status` é um de `processando`, `concluido`, `erro`. Enquanto for `processando`, `value` é `null`. Em `erro`, `erro` traz mensagem legível.

#### `PUT /api/transcricoes/:id`

Recebe `{ "value": { ... } }` com as correções feitas na interface e substitui a transcrição.

#### `GET /api/transcricoes/:id/planilha`

Devolve a planilha já com as correções aplicadas. Aceita `?formato=xlsx|csv|json`.

#### `GET /healthz`

`200 OK` quando a aplicação está de pé.

---

# A interface

O que precisa existir:

- **Envio do PDF** com escolha do tipo e feedback de progresso — processar leva tempo, e a tela não pode parecer travada
- **Tabela editável** com a transcrição, seguindo as colunas da planilha do tipo correspondente
- **Problemas destacados** — os quatro avisos acima visualmente marcados, com o motivo legível, nas mesmas cores da planilha
- **PDF visível ao lado da tabela**, para conferir sem trocar de janela
- **Botão de download**, refletindo as edições

Não precisa de login nem de design elaborado. Precisa ser honesta sobre o que a máquina não conseguiu ler, e precisa deixar corrigir.

# Operação

- **`Dockerfile` + `docker-compose.yml`**: `docker compose up` sobe tudo. Este é o requisito duro.
- **Aplicação publicada**, com URL acessível. Qualquer plataforma gratuita serve, e não tem problema se ela dormir por inatividade — a URL é a demonstração, o `docker compose` é o que garante a avaliação.
- Configuração por variável de ambiente. Nenhum segredo no repositório.
- CI mínima (lint + testes) é diferencial.

## Execução desta solução com Docker

Na raiz do repositório:

```bash
docker compose up --build
```

A aplicação fica disponível em `http://localhost:8080`. O Compose inicia o
frontend Nginx, a API FastAPI e o worker, sem comandos adicionais. Para parar:

```bash
docker compose down
```

Banco e PDFs ficam no volume nomeado `docparse_data`; `docker compose down`
preserva esse volume. Use `docker compose down -v` somente quando quiser apagar
deliberadamente todas as transcrições e uploads. Variáveis e defaults seguros
para o Compose estão em `.env.example`.

# Segurança e privacidade

Você vai colocar na internet um endpoint público que recebe documento com nome, CPF, matrícula, salário e jornada de pessoas reais:

- Limite de tamanho de upload
- Validação de que o arquivo é mesmo um PDF
- Comportamento definido para arquivo corrompido, PDF gigante e uploads simultâneos
- Política de retenção explícita em `SOLUCAO.md`: o que guarda, onde, por quanto tempo
- Sem PII nos logs

# Tecnologia

**Linguagem e bibliotecas livres.** Nos interessam fundamentos e raciocínio, não uma stack específica. A única coisa fechada é o contrato HTTP.

# Sobre uso de IA

**Use os agentes e assistentes que quiser.** É assim que trabalhamos aqui, e fingir o contrário não ajudaria ninguém.

Em compensação, queremos ver como você conduz. Entregue um `PROCESSO.md` com:

- Que ferramentas usou e para quê
- Dois ou três pontos em que o agente errou ou pegou o caminho errado, e como você percebeu
- O que reescreveu à mão, e por quê

E responda, no mesmo arquivo:

1. Cite 3 decisões em que havia mais de uma resposta razoável. Por que escolheu essa?
2. O que na sua solução quebra primeiro em produção?
3. Onde você não confia no que entregou?

Essas respostas pesam. Código impecável com `PROCESSO.md` vago é sinal ruim.

# Bônus

Nenhum é necessário para uma entrega forte. Só faça se sobrar tempo.

- **Rastreabilidade visual** — clicar numa célula da tabela e ver destacado, no PDF, o trecho exato de onde aquele valor saiu. É a funcionalidade central do nosso produto, e exige carregar as coordenadas do texto por todo o pipeline.
- **Detecção do tipo** — descobrir sozinho se o PDF é cartão de ponto ou holerite, em vez de depender do campo `tipo`.
- **Ficha financeira** — um holerite anual, com uma coluna por mês de janeiro a dezembro, vira uma entrada por mês compartilhando o mesmo `page`, ignorando a coluna `Total`.
- **Layout desconhecido** — o que sua aplicação faz ao receber um documento de um layout que ela não conhece? Responder "não sei ler este documento" é melhor que devolver lixo.

# Propriedade do que você entrega

**A sua solução é sua.** Você mantém todos os direitos sobre o código que
escrever, pode publicá-lo, reaproveitá-lo, colocá-lo no portfólio e licenciá-lo
como quiser — independentemente do resultado do processo.

O que pedimos é permissão para **avaliar** a entrega: executar, ler e discutir
internamente o seu código durante o processo seletivo. Nada além disso. Não
usamos solução de candidato em produção, não incorporamos trechos ao nosso
código, e não repassamos a terceiros.

O material **deste repositório** — enunciado, instruções, script de avaliação e
documentos de exemplo — é CC0 1.0 (ver [`LICENSE`](LICENSE)). Use como quiser,
inclusive para montar o processo seletivo da sua própria empresa.

Se você preferir entregar num repositório privado e nos dar acesso em vez de
publicar, tudo bem — avise o recrutador.

# Entregáveis

1. Link do repositório
2. URL da aplicação publicada
3. `SOLUCAO.md` — como rodar, decisões técnicas, o que ficou de fora
4. `PROCESSO.md` — conforme a seção sobre uso de IA
5. As planilhas geradas a partir dos PDFs em `exemplos/`

# Como vamos avaliar

Pesos e detalhes em [`INSTRUCOES.md`](INSTRUCOES.md).

Depois da entrega, quem avançar faz uma sessão de ~40 minutos com a gente, ao vivo, estendendo a própria solução para um layout novo — com agente liberado.

# Dúvidas

Fale com o recrutador responsável. Perguntar quando o enunciado está ambíguo é comportamento desejável, não sinal de fraqueza.

---

**Boa sorte! 🚀**
