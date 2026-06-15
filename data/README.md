# Data

Pasta responsável por armazenar **entradas, caches e saídas** do pipeline.

## Subpastas
- `narrativas/` — XMLs originais com textos clínicos (entrada)
- `goldstandard/` — XMLs com anotações de referência (ground truth)
- `dicionarios/` — caches gerados durante execução (ex.: caches de API e validações)
- `output/` — resultados finais e artefatos (CSV consolidado, logs e avaliação)

## Importante
Não altere manualmente os caches em `dicionarios/` sem entender o impacto (eles controlam resultados e repetição de chamadas às APIs/LLMs).

