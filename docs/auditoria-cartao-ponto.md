# Auditoria da extração de cartão de ponto

Auditoria executada em 2026-08-12 sobre os PDFs reais de `exemplos/`.
As contagens de linhas reais foram feitas nas páginas renderizadas, e não a
partir do tamanho do JSON. Os diagnósticos contêm somente métricas agregadas.

| PDF | Pág. | Linhas visuais de registro | `days[]` | Dias sem punch | Punches | Leitura |
|---|---:|---:|---:|---:|---:|---|
| time-card-01 | 1 | 31 | 31 | 10 | 84 | texto nativo |
| time-card-01 | 2 | 31 | 31 | 13 | 70 | texto nativo |
| time-card-01 | 3 | 30 | 30 | 12 | 60 | texto nativo |
| time-card-01 | 4 | 31 | 31 | 9 | 81 | texto nativo |
| time-card-01 | 5 | 30 | 30 | 11 | 74 | texto nativo |
| time-card-02 | 1 | 31 | 31 | 20 | 44 | OCR |
| time-card-02 | 2 | 30 | 30 | 9 | 84 | OCR |
| time-card-02 | 3 | 31 | 31 | 10 | 84 | OCR |
| time-card-02 | 4 | 31 | 31 | 10 | 76 | OCR |
| time-card-02 | 5 | 30 | 30 | 9 | 84 | OCR |
| time-card-03 | 1 | 56 | 56 | 16 | 158 | OCR |
| time-card-03 | 2 | 56 | 56 | 14 | 168 | OCR |
| time-card-03 | 3 | 56 | 56 | 14 | 162 | OCR |
| time-card-03 | 4 | 56 | 56 | 14 | 166 | OCR |
| time-card-03 | 5 | 56 | 56 | 12 | 172 | OCR |
| time-card-04 | 1 | 15 | 0 | n/a | 0 | OCR insuficiente |
| time-card-04 | 2 | 16 | 0 | n/a | 0 | OCR insuficiente |
| time-card-04 | 3 | 15 | 0 | n/a | 0 | OCR insuficiente |
| time-card-04 | 4 | 16 | 0 | n/a | 0 | OCR insuficiente |
| time-card-04 | 5 | 15 | 0 | n/a | 0 | OCR insuficiente |

## Conferências específicas

- `time-card-01`, página 4, dia 29: o documento mostra somente `09:23`.
  O punch ímpar é real e não deve ser completado artificialmente.
- `time-card-03`: as páginas cobrem, respectivamente, `16/12/2019` a
  `09/02/2020`, `10/02/2020` a `05/04/2020`, `06/04/2020` a `31/05/2020`,
  `01/06/2020` a `26/07/2020` e `27/07/2020` a `20/09/2020`. Cada página tem
  56 datas consecutivas, sem lacunas ou duplicações.
- `time-card-03`, página 1, `24/12/2019`: `08:00` está em `Abono`, portanto o
  resultado possui zero punches.
- `time-card-03`, página 1, `26/12/2019`: `01:00` está em `Ad.Not`; somente
  `14:59d 19:00d 20:00d 23:00d` são punches.
- `time-card-03`, página 1, `01/01/2020`: `07:00` está em `H.Ext`; somente
  `07:00d 15:00d` são punches.
- `time-card-03`, página 1, `28/01/2020`: `00:29` e `01:24` estão em colunas
  auxiliares; somente `14:55c 19:00d 20:00d 23:24c` são punches.

## Limitação confirmada

`time-card-04` é manuscrito, degradado e sobreposto a uma grade colorida. O OCR
Tesseract atual não reconhece cabeçalho, rótulos de dia e horários com segurança.
Retornar `days: []` é mais honesto que fabricar as 77 linhas visuais. Tratamento
desse layout exigiria pré-processamento ou OCR especializado e ficou fora desta
fase.

O fallback sem cabeçalho só consegue separar uma coluna auxiliar quando existe
um vão horizontal claramente maior que o espaçamento das colunas anteriores.
Sem essa evidência, a distinção entre uma batida adicional e um horário auxiliar
é inerentemente ambígua e permanece uma limitação conhecida do fallback.

A heurística compartilhada de texto útil foi mantida genérica: quatro tokens e
vinte caracteres alfanuméricos. Ela distinguiu corretamente texto nativo e
imagem nas 20 páginas auditadas, mas uma camada extensa composta por texto lixo
ainda pode ser classificada como útil. Não foram adicionados termos específicos
de cartão de ponto ao leitor compartilhado.
