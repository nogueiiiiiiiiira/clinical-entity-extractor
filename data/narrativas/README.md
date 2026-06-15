# Narrativas

Esta pasta contém os **XMLs de entrada** do corpus/pacientes/narrativas clínicas.

## Formato esperado
- Cada arquivo deve conter uma tag `<TEXT>` com o texto clínico.

## Uso no pipeline
- Etapa `00_preprocess.py`: lê os XMLs em `data/narrativas/` e extrai o conteúdo de `<TEXT>` para arquivos `.txt` em `data/output/textos_limpos/`.
- Etapa `01_extract_terms.py`: lê novamente os XMLs (em vez dos `.txt`), extraindo termos diretamente do `<TEXT>`.

## Observação
- Os arquivos que terminam com `*_goldstandard.xml` são tratados como **gold standard** e não como narrativa.

