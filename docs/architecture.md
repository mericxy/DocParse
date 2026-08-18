# Arquitetura

## Componentes

| Área | Tecnologia |
|---|---|
| Backend | Python 3, FastAPI, Pydantic e SQLAlchemy |
| PDF e OCR | PyMuPDF e Tesseract |
| Persistência | SQLite em modo WAL e PDF original no filesystem |
| Processamento | Worker Python separado com fila persistente no SQLite |
| Exportação | openpyxl e suporte nativo a CSV/JSON |
| Frontend | React, TypeScript e Vite, servido por Nginx |
| Deploy | Docker Compose em servidor próprio, publicado por Cloudflare Tunnel |

Backend e worker compartilham o mesmo banco, o diretório de uploads e a política
de retenção de 24 horas.

## Fluxo

```text
Cloudflare Tunnel
  -> frontend / Nginx
       -> upload validado
       -> job e PDF persistidos
       -> worker
       -> leitura do PDF
            -> texto nativo útil
            -> OCR com Tesseract quando necessário
       -> extrator selecionado pelo tipo
       -> JSON persistido
       -> revisão e correção via PUT
       -> exportação XLSX, CSV ou JSON
       -> download
```

A descrição completa das decisões, limitações e configuração operacional está
em [`SOLUCAO.md`](../SOLUCAO.md).
