# Config

Contém a configuração central do pipeline.

## Arquivo principal
- `config.py` — classe `Config` com:
  - parâmetros do modelo (Ollama e modelo juiz)
  - caminhos de entrada/saída (pastas em `data/`)
  - parâmetros de validação e thresholds
  - credenciais e URLs das APIs de mapeamento (BioPortal SNOMED CT e ICD-11)

## Boas práticas
- Evite commitar credenciais em repositórios públicos.
- Caso modifique valores de `Config`, mantenha consistência com as pastas esperadas.

