# Gold standard

Esta pasta contém os **XMLs anotados manualmente** (ground truth) para avaliação.

## Formato esperado
- Os arquivos devem incluir marcações de eventos (por exemplo `<EVENT>`), conforme o formato do SemClin-Br (ou o utilizado pelo pipeline).

## Uso no pipeline
- Etapa `04_evaluate.py`: compara as previsões do pipeline com o gold standard para calcular métricas (precisão/recall/F1) e gerar relatórios.

## Boas práticas
- Não misture gold standard com narrativas de entrada.

