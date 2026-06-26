
# Clinical Entity Extractor + Terminology Mapper (SNOMED CT & CID-11)

Pipeline para:
1) extrair termos clínicos (texto→entidades) a partir de narrativas XML,
2) validar/filtrar falsos positivos de forma **objetiva via SNOMED CT** e resolver ambiguidades contextuais com LLM,
3) mapear cada termo para **SNOMED CT** e **CID-11**,
4) consolidar resultados,
5) avaliar contra **gold standard** e gerar relatórios.

> Linguagem do domínio: PT-BR.

---

## Como executar

### Dependências
- Python 3.x
- `ollama` funcionando localmente (modelo de extração e modelo “juiz” para tarefas contextuais)
- Acesso às APIs usadas no mapeamento:
  - BioPortal Search (SNOMED CT)
  - WHO ICD-11 Search + token endpoint

Instale pacotes:
```bash
pip install -r requirements.txt
```

### Pipeline completo
```bash
python app.py
```

### Execução parcial
O orquestrador `app.py` permite:
```bash
python app.py --start-at 00 --stop-after 02
```
Passos possíveis: `00`, `01`, `02`, `03`, `04`, `05`.

---

## Hierarquia terminológica (o que é o quê)

O pipeline trabalha com **3 níveis**:

1) **Termo clínico (texto)**
   - Saída do LLM de extração: entidade textual com `text`, `original`, `polarity`, `abbreviation`, `category`.

2) **Código de ontologia (conceito clínico normalizado)**
   - **SNOMED CT**: `SCTID` (code) + “label” consultado/validado.
   - **CID-11**: `CID11` (code) + “title” consultado/validado.

3) **Indicador de acerto (decisão do “juiz”)**
   - Para cada mapeamento, o pipeline armazena:
     - `SCTID_correto` ∈ {0,1}
     - `CID11_correto` ∈ {0,1}
   - Esses campos são decididos via LLM (“modelo juiz”) comparando:
     - termo original/label vs. significado do código sugerido.

---

## Visão geral do pipeline (passo a passo)

O `app.py` executa, na ordem:

1. `00_preprocess.py`
2. `01_extract_terms.py`
3. `02_map_terminology.py`
4. `03_merge_results.py`
5. `04_evaluate.py`
6. `05_audit_report.py`

---

## Passo 00 — Preprocessamento (`scripts/00_preprocess.py`)

### Objetivo
Transformar entradas XML em um texto “limpo” pronto para LLM.

### O que faz
- Lê cada arquivo `.xml` em `data/narrativas/`.
- Extrai o conteúdo da tag XML: `.//TEXT`.
- Remove quebras e múltiplos espaços (normaliza `\s+` → espaço).
- Salva em:
  - `data/output/textos_limpos/{NOME}.txt`

### Saída
- Um `.txt` por narrativa.

---

## Passo 01 — Extração de termos (`scripts/01_extract_terms.py`)

### Objetivo
Extrair entidades clínicas do texto usando:
- **LLM extrator** (`Config.OLLAMA_MODEL`)
- **Validação objetiva de Falsos Positivos** via **API SNOMED CT + Filtro Semântico** (substitui o antigo “juiz de FP” baseado em LLM)
- **LLM juiz** (`Config.JUDGE_MODEL`) mantido **apenas** para resolução de ambiguidades contextuais (expansão de abreviações e validação de mapeamento)
- Caches para evitar chamadas repetidas

### Entradas
- XMLs em `data/narrativas/`
- Usado: conteúdo dentro de `.//TEXT`

### Saídas principais (por narrativa)
Para cada narrativa `XXXX.xml`:
- `data/output/csv_individual/XXXX/extracted_terms.csv`
- `data/output/csv_individual/XXXX/annotations_XXXX.json` (annotations consolidadas)
- `data/output/logs/XXXX/llm_response_XXXX.json` (resposta bruta do LLM)

E no final:
- `data/output/csv_individual/all_extracted_terms.csv` (consolidado)
- `data/output/logs/filtered_terms_log.txt` (termos rejeitados pela validação)

### Funções-chave (como cada “peça” funciona)

#### 1) `PesquisaClin_Llama(textoClinico) -> str`
- Monta prompt:
  - Se `Config.ENABLE_AGGRESSIVE_EXTRACTION=True`, pede “extraia ABSOLUTAMENTE TUDO…”.
  - Caso contrário, prompt mais restrito.
- Chama o extrator via `ollama.chat`.
- Tenta obter JSON:
  1. procura bloco ```json ... ```
  2. procura a primeira ocorrência de `{...}`
  3. fallback para regex `extrair_entidades_via_regex`
- Se falhar, retorna `{"entities": []}`.

#### 2) `extrair_annotations_validas(resposta_json, texto_original, narrative_name)`
- Faz parse robusto do JSON (lida com JSON cercado por texto).
- Para cada entidade candidata, normaliza e valida:
  - Checa se `original` é substring contínua do `texto_original`.
  - Chama `is_valid_clinical_term_llm(texto, contexto)` **(agora baseada em API SNOMED)**.
  - Se inválido: adiciona em `NOISE_LOG_GLOBAL`.
- Normaliza campos:
  - `polarity`: garante “Positiva”/“Negativa”
  - `categoria`: garante “Problema”/“Teste”/“Tratamento”
- Retorna lista com:
  - `textoAnalisado`, `categoria`, `abreviacao`, `abreviacao_original`, `polaridade`

#### 3) `is_valid_clinical_term_llm(term, contexto) -> bool` (NOVA VERSÃO)
Esta função agora atua como um **filtro objetivo baseado em terminologia**, e **não** chama mais o LLM para decidir se o termo é ruído.

- Se `Config.PERMISSIVE_FP_VALIDATION=True`, aceita tudo (modo permissivo, desliga o filtro).
- Caso contrário (padrão `False`):
  - **Normaliza** o termo.
  - **Consulta a API SNOMED** (`utils.query_snomed`) para o termo.
  - Se não encontrar resultados no SNOMED, **rejeita**.
  - Se encontrar, para cada resultado, obtém o **tipo semântico** (`utils.get_snomed_semantic_type`).
  - Se o tipo semântico estiver em `TIPOS_SEMANTICOS_VALIDOS` (ex: `Disorder`, `Finding`, `Procedure`, `Substance`), **aceita**.
  - Caso contrário (ex: `Person`, `Environment`, `Qualifier`), **rejeita**.
- Resultados são cacheados em `fp_validation_cache.json` para evitar chamadas repetidas à API.

> **Impacto prático**: "HAS" agora é **mantido** (SNOMED retorna `Disorder`), enquanto "paciente" é **descartado** naturalmente (pois retorna `Person`, que não está na lista de tipos válidos). Não há interferência manual com listas de termos genéricos — a decisão é puramente baseada na ontologia SNOMED.

#### 4) `consolidar_annotations(lista_de_listas, narrative_name, texto_original)`
- Deduplica por `(normalizado, polaridade)`.
- Preferência por spans maiores.
- Se existirem expansões conflitantes para a mesma abreviação:
  - chama `utils.resolver_conflito_expansao(...)` (LLM juiz, mantido para esta tarefa contextual).

#### 5) `criar_dataframe_da_lista(...)`
- Converte anotações consolidadas em DataFrame com colunas:
  - `nomeNarrativa`, `textoPrompt`, `categoria`, `textoAnalisado`, `abreviacao`, `abreviacao_original`, `polaridade`
- Salva em `extracted_terms.csv`.

#### 6) Pós-processamento de abreviações (expansão)
Após salvar o CSV:
- Para cada linha com `abreviacao=True`:
  - chama `utils.verificar_expansao_llm(abrev, expandido, ...)` (LLM juiz mantido)
  - guarda em `expansao_correta`.

#### 7) Logs de debug pessoal (por que tudo é salvo)
O passo 01 gera:
- `logs/log_execucao.txt` (stdout espelhado via `Tee`)
- arquivos por narrativa:
  - `logs/XXXX/llm_response_XXXX.json` (prompt e resposta)
- `dicionarios/*.json` (caches de normalização, validação de FP via API, expansão)

Isso permite você:
- reproduzir decisões,
- inspecionar o que o LLM devolveu,
- comparar antes/depois de mudanças em prompts,
- medir hit de cache.

---

## Passo 02 — Mapeamento de terminologias (`scripts/02_map_terminology.py`)

### Objetivo
Para cada `textoAnalisado` extraído, obter:
- melhor candidato SNOMED CT → `SCTID`
- melhor candidato CID-11 → `CID11`
- e validar o acerto com o **modelo juiz** (LLM), que **continua atuando** nesta etapa para garantir a correção contextual do código.

### Entradas
- `data/output/csv_individual/*/extracted_terms.csv`

### O que faz (por termo)
Função principal: `mapear_termo_api(termo, df)`

1) **Normaliza o termo**
   - `utils.normalize_term(...)` (usa `normalize_with_llm_*` + cache)

2) **Consulta APIs**
   - `utils.query_snomed(...)`
     - BioPortal Search SNOMED CT
   - `utils.query_icd11(...)`
     - token WHO + busca ICD-11

3) **Ranking dos candidatos**
   - `utils.rank_results(...)`
     - usa similaridade baseada em TF-IDF char n-grams

4) **Validação com “juiz” (LLM)**
   - Para SNOMED:
     - pega `code` + `label`
     - chama `utils.validar_mapeamento_llm(...)`
       - prompt `prompts/validar_mapeamento_llm_*`
       - saída interpretada como 1 (correto) / 0 (incorreto)
   - Para CID-11:
     - pega `code` + `title`
     - chama `utils.validar_mapeamento_llm(...)` igualmente

5) **Retorna resultado**
- `SCTID`: código do melhor candidato (se validado)
- `CID11`: código do melhor candidato (se validado)
- `SCTID_correto`, `CID11_correto`: 0/1

### Caches envolvidos (por que existem)
- `api_cache.json`: salva resultados brutos de query SNOMED/CID
- `validation_cache.json`: salva decisão do juiz `(termo_original|codigo)`
- `norm_cache.json`: salva normalização do termo

---

## Passo 03 — Consolidação e métricas locais (`scripts/03_merge_results.py`)

### Objetivo
Juntar outputs individuais num arquivo mestre e imprimir estatísticas.

### O que faz
- Lê todos `extracted_terms.csv` dentro de `data/output/csv_individual/*/`
- Concatena em `data/output/consolidated_terms.csv`
- Imprime:
  - contagem de termos com `SCTID`
  - contagem de termos com `CID11`
  - precisão estimada via campos `*_correto`
  - taxa de acerto de `expansao_correta` (abreviações)

---

## Passo 04 — Avaliação vs Gold Standard (`scripts/04_evaluate.py`)

### Objetivo
Medir VP/FP/FN comparando `consolidated_terms.csv` com XMLs em `data/goldstandard/`.

### O que faz (alto nível)
1) Para cada narrativa:
   - extrai termos gold usando `extrair_gold_terms(root, narrativa_filename)`
     - filtra `EVENT` com `Tipo` {Problema, Tratamento, Teste}
     - respeita polaridade Negativa via regras do XML

2) Para cada termo predito:
   - compara com termos gold usando:
     - match exato por normalização (`termo_norm`)
     - modo `relaxed` (expansões/semelhança fuzzy/LLM semântico)
       - `expansion_of(...)`
       - `verificar_expansao_llm(...)` (quando aplicável)
       - `fuzzy_partial_match(...)`
       - `llm_semantic_match(...)`

3) Monta tabela de avaliação detalhada:
- classe `VP`, `FP`, `FN`
- salva planilha `.xlsx`

Também gera CSVs auxiliares:
- `tabela2_contagem_geral_*`
- `tabela5_comparacao_geral_*`
- `tabela3_contagem_por_categoria_*`
- `tabela6_detalhamento_categoria_*`

### Auditoria de erros
- `classificar_erro(...)` tenta rotular cada FP/FN com causa (ex.: fragmentado, abreviação não expandida, variação lexical extrema, etc.)
- `erros_classificados_*.csv` consolida exemplos com contexto.

---

## Passo 05 — Auditoria e comparação (`scripts/05_audit_report.py`)

### Objetivo
Gerar relatórios “humanos” para depurar decisões.

### Relatórios gerados
- `data/output/auditoria/termos_rejeitados.csv`
  - usa `logs/filtered_terms_log.txt`
- `data/output/auditoria/resumo_auditoria.csv`
- `data/output/auditoria/comparacao/*`
  - listas VP/FP/FN com termos e categorias

---

## Saídas (o que você deve encontrar no disco)

Principais:
- `data/output/textos_limpos/*.txt` (00)
- `data/output/csv_individual/*/extracted_terms.csv` (01, 02)
- `data/output/csv_individual/all_extracted_terms.csv` (01)
- `data/output/consolidated_terms.csv` (03)
- `data/output/avaliacao/*` (04)
- `data/output/auditoria/*` (05)

---

## Exemplo completo de narrativa (o fluxo inteiro)

Considere a narrativa (exemplo simplificado):
> “Paciente refere **has** (hipertensão arterial sistêmica) e **dor torácica**. Nega **dispneia**.”

### 1) Passo 00
- O XML é limpo: extrai o texto da tag `<TEXT>`.

### 2) Passo 01 (extração)
- O LLM extrator retorna entidades com JSON contendo, tipicamente:
  - `has` como `abbreviation=true`
  - `dor torácica` como `category=Problema`
  - `dispneia` como `polarity=Negativa` (por negação)
- Em seguida:
  - **Validação de FP (API SNOMED)**: 
    - `"paciente"` → consulta SNOMED, retorna `Person` (não está em `TIPOS_SEMANTICOS_VALIDOS`) → **rejeitado**.
    - `"has"` → consulta SNOMED, encontra `Disorder` → **mantido**.
    - `"dor torácica"` → consulta SNOMED, encontra `Finding` → **mantido**.
    - `"dispneia"` → consulta SNOMED, encontra `Finding` → **mantido** (a polaridade é tratada separadamente).
  - Expansão de abreviação (`has`): o LLM juiz valida a expansão "hipertensão arterial sistêmica" via `verificar_expansao_llm`.
- O CSV final da narrativa fica com:
  - `textoAnalisado`: expansão (ou termo normal)
  - `abreviacao_original`: “has”
  - `expansao_correta`: 0/1
  - **Nota**: "paciente" não aparece no CSV final.

### 3) Passo 02 (mapeamento SNOMED/CID-11)
Para cada `textoAnalisado` (ex: "has", "dor torácica", "dispneia"):
- consulta SNOMED e CID-11
- rankeia candidatos
- “juiz de mapeamento” (LLM) decide `SCTID_correto` e `CID11_correto`

### 4) Passo 03 (consolidação)
- O pipeline concatena todas as narrativas e salva `consolidated_terms.csv`.

### 5) Passo 04 (avaliação)
- Com gold standard:
  - se o termo normalizado bate, vira `VP`
  - se só bate por expansão/similaridade, continua sendo `VP` no modo `relaxed`
  - se não existe no gold → `FP`
  - se gold tem e o modelo não previu → `FN`

### 6) Passo 05 (auditoria)
- Gera listas de FP/FN e agrupa “por que errou” (por exemplo, abreviação não expandida).

---

## Debug: onde olhar

1) `data/dicionarios/*.json`
   - caches: normalização, expansão, validações de mapeamento e **validação de FP via API SNOMED** (`fp_validation_cache.json`).
2) `data/output/logs/llm_responses/*.json`
   - cada chamada do LLM salva prompt + resposta (extração, expansão, mapeamento).
3) `data/output/logs/decisions/*.json`
   - decisões estruturadas (cache_hit, motivo, input/output).

---

## Arquitetura

- **Extrator** (LLM): gera entidades em JSON.
- **Filtro de Falsos Positivos** (API SNOMED + Regras):
  - Valida se o termo existe no SNOMED e se possui tipo semântico clínico válido.
  - *Substitui o antigo LLM juiz de FP*, tornando a filtragem mais rápida, objetiva e confiável para siglas (ex: HAS, DM).
  - Não há interferência manual com listas de termos genéricos; a decisão é puramente baseada na ontologia SNOMED.
- **Juiz Contextual** (LLM):
  - **Mantido** para tarefas que exigem compreensão do texto:
    - Resolução de conflitos de expansão.
    - Validação de expansão de abreviação.
    - Validação de mapeamento SNOMED/CID-11 (passo 02).
- **Candidatos** (APIs): SNOMED/BioPortal e ICD-11.
- **Ranking**: similaridade TF-IDF char n-grams.
- **Consolidação**: concatena CSVs e gera métricas.
- **Avaliação**: VP/FP/FN vs gold.
