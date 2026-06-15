# Scripts (Pipeline)

Esta pasta contém os **scripts executáveis** do pipeline, além de utilitários compartilhados.

## Ordem de execução (pipeline completo)
Os scripts devem ser executados na ordem:
1. `00_preprocess.py` — extrai/limpa texto de XMLs e gera arquivos `.txt`
2. `01_extract_terms.py` — extrai termos clínicos com LLM, valida FP e consolida anotações
3. `02_map_terminology.py` — mapeia termos para **SNOMED CT** e **CID-11**
4. `03_merge_results.py` — consolida resultados e gera `data/output/consolidated_terms.csv`
5. `04_evaluate.py` — avalia resultados vs. gold standard
6. `05_audit_report.py` — cria relatórios/auditoria dos erros

O orquestrador `app.py` executa esses passos sequencialmente e permite `--start-at` / `--stop-after`.

## Utilitários
- `utils.py`: funções compartilhadas (logs, normalização, chamadas de APIs, helpers LLM e caches)

## Saídas esperadas (visão geral)
- `data/output/` contém CSVs consolidados, logs e artefatos de avaliação.

## Observação
Os scripts usam configurações de `config/config.py` (pastas, credenciais de APIs e parâmetros do pipeline).

