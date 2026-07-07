
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

---


## Hierarquia terminológica (o que é o quê)

O pipeline trabalha com **2 artefatos principais**:

1) **Extração (texto → entidades)**
   - Resultado por narrativa: CSV com `textoAnalisado`, `categoria`, `abreviacao`, `abreviacao_original`, `polaridade`.

2) **Mapeamento (entidade → códigos)**
   - Resultado no mesmo CSV: `SCTID`, `CID11` e flags `SCTID_correto`/`CID11_correto` (decisão do LLM juiz após rankeamento nas APIs).


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
- Lê cada arquivo `.xml` da pasta configurada em `Config.NARRATIVES_FOLDER`.
- Extrai o conteúdo da tag XML: `.//TEXT`.
- Remove quebras e múltiplos espaços (normaliza `\s+` → espaço).
- Salva em:
  - `data/output/textos_limpos/{NOME}.txt`

### Saída
- Um `.txt` por narrativa.

---

## Passo 01 — Extração de termos (`scripts/01_extract_terms.py`)


### Objetivo
Extrair entidades clínicas do texto com LLM e gerar um CSV por narrativa.

### O que faz (na prática)
- Usa o **LLM extrator** (`Config.OLLAMA_MODEL`) para gerar JSON com entidades.
- Faz validações/limpeza dos campos retornados (ex.: `polarity` e `categoria`).
- Consolida/deduplica e resolve conflitos de expansão de abreviações (LLM juiz).
- Valida expansão de abreviação (quando o termo parece abreviação) usando função híbrida (SNOMED + LLM + dicionário local + caches).
- Salva logs/artefatos por narrativa.


### Entradas
- Usados: conteúdo dentro de `.//TEXT`.

### Saídas principais (por narrativa)
Para cada narrativa `XXXX.xml`:
- `data/output/csv_individual/XXXX/extracted_terms.csv`
- `data/output/csv_individual/XXXX/extracted_terms.csv`
- `data/output/logs/<narrative_base>/llm_response_<narrative_base>.json` (resposta bruta do LLM)
- Colunas típicas no CSV do passo 01 incluem: `nomeNarrativa`, `textoPrompt`, `categoria`, `textoAnalisado`, `original`, `abreviacao`, `abreviacao_original`, `polaridade` e (para abreviações curtas) `expansao_correta`.



E no final:
- `data/output/csv_individual/all_extracted_terms.csv` (consolidado)

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
- Faz parse robusto do JSON (aceita JSON rodeado por texto).
- Para cada entidade:
  - pega `text`/`original`/campos equivalentes
  - valida `original` (quando existe) para estar contido no texto (via normalização)
  - normaliza `polarity` para `Positiva`/`Negativa`
  - normaliza `category` para `Problema`/`Teste`/`Tratamento`
- Retorna objetos com:
  - `textoAnalisado`, `categoria`, `abreviacao`, `abreviacao_original`, `polaridade`

#### 3) `consolidar_annotations(lista_de_listas, narrative_name, texto_original)`
- Deduplica por `(normalizado(textoAnalisado), polaridade)` e mantém a versão com span maior.
- Se houver conflito para expansão de abreviação, resolve com `utils.resolver_conflito_expansao(...)` (LLM juiz).

#### 4) `criar_dataframe_da_lista(...)`
- Converte as anotações consolidadas em DataFrame e salva `extracted_terms.csv`.
- Colunas: `nomeNarrativa`, `textoPrompt`, `categoria`, `textoAnalisado`, `abreviacao`, `abreviacao_original`, `polaridade`

#### 5) Validação de expansão de abreviações (pós-CSV)
- Para linhas com `abreviacao=True` e abreviações curtas (`len<=6` e sem espaço), chama `utils.verificar_expansao_hibrida(...)`.
- Salva a flag `expansao_correta` (0/1 ou vazio).

#### 6) Logs
- `data/output/logs/log_execucao.txt` (stdout espelhado)
- `data/output/logs/<ID>/llm_response_<ID>.json`
- caches em `data/dicionarios/` (normalização, expansão e decisões).


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
Mapear cada `textoAnalisado` para códigos **SNOMED CT** e **CID-11**, preenchendo o CSV com:
- `SCTID` e `CID11`
- `SCTID_correto` e `CID11_correto` (decisão do LLM juiz)

### O que faz (na prática)
- Lê cada `extracted_terms.csv` em `data/output/csv_individual/*/`.
- Para cada `textoAnalisado` único:
  1) normaliza o termo com cache (`utils.normalize_term`) 
  2) tenta mapeamento local em `data/dicionarios/mapeamento_local.json`
  3) se não achar localmente, consulta APIs:
     - SNOMED (BioPortal)
     - CID-11 (WHO / token + busca)
  4) rankeia candidatos por similaridade (TF-IDF char n-grams)
  5) valida o melhor candidato com o LLM juiz (`utils.validar_mapeamento_llm`) e grava as flags `*_correto`
- Atualiza o CSV no mesmo local.

### Caches usados
- Cache de APIs (resultados brutos)
- Cache de normalização
- Cache de validação do juiz (por `termo_original|codigo`)


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
Gera arquivos para revisar decisões do pipeline.

### O que gera (na prática)
- Lê `data/output/logs/filtered_terms_log.txt` (se existir) e salva:
  - `data/output/auditoria/termos_rejeitados.csv`
- Resume respostas do LLM de extração, se existirem logs em `Config.LLM_RESPONSES_FOLDER`.
  - salva `respostas_llm_extracao.csv`
- Resume validações de mapeamento, se existirem em `Config.LOGS_FOLDER/decisions/`.
  - salva `validacoes_mapeamento.csv`
- Tenta ler o arquivo de avaliação gerado no passo 04 e salva listas:
  - `.../auditoria/comparacao/acertos_vp.csv`
  - `.../auditoria/comparacao/falsos_positivos_fp.csv`
  - `.../auditoria/comparacao/falsos_negativos_fn.csv`

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
