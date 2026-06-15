# Prompts (LLM)

Esta pasta contém **templates de prompts** usados pelo pipeline para chamar LLMs via `ollama`.

## Como funciona
- Arquivos `*_system.py`: definem o **System Prompt** (instruções de alto nível).
- Arquivos `*_user.py`: definem o **User Prompt** (template com variáveis como `{term}`, `{abrev}`, etc.).
- Os scripts do pipeline importam essas constantes (ex.: `from prompts.normalize_with_llm_system import SYSTEM_PROMPT`).

## Padrões
- O conteúdo deve retornar **apenas o necessário para o próximo passo** (muitas vezes somente o termo ou um JSON), conforme instruções no prompt.
- Caso você altere prompts, pode afetar extração, normalização, validações e mapeamentos.

## Arquivos principais
- `normalize_*`: normalização e expansão de termos/abreviações
- `validar_*`: validação de termos e validações de mapeamento
- `resolver_conflito_*`: resolução de conflitos entre candidatos
- `semantic_match_*`: comparação semântica entre termos
- `pesquisa_clin_llama_*`: extração de termos clínicos

