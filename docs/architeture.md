Backend:
Python 3
FastAPI
Pydantic
SQLAlchemy
SQLite (WAL)

PDF:
PyMuPDF

OCR:
Tesseract através do PyMuPDF

Export:
openpyxl
csv/json nativos

Async:
worker Python separado
fila persistente no próprio SQLite

Frontend:
React
TypeScript
Vite

Persistência:
JSON da transcrição → SQLite
PDF original → filesystem

Retenção:
24 horas

Deploy:
Docker Compose:
- frontend
- backend
- worker

Pipeline:
upload
 → persistir
 → worker
 → ler PDF
 → OCR fallback
 → selecionar extractor pelo tipo
 → persistir JSON
 → revisão
 → PUT
 → exportador pelo tipo
 → download