# Clinical Term Mapper – Extração e Mapeamento de Termos Clínicos

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## Sumário
- [1. Sobre o Pipeline](#1-sobre-o-pipeline)
- [2. Dataset](#2-dataset)
- [3. Pré-requisitos e Instalação](#3-pré-requisitos-e-instalação)
- [4. Estrutura do Projeto](#4-estrutura-do-projeto)
- [5. Configuração](#5-configuração)
- [6. Execução](#6-execução)
- [7. Saídas Geradas](#7-saídas-geradas)
- [8. Referências](#8-referências)

## 1. Sobre o Pipeline

O **Clinical Term Mapper** é um pipeline (automatizado) para:
1) extrair entidades clínicas (termos) de narrativas médicas em XML; 
2) expandir abreviações quando aplicável; 
3) mapear cada termo para códigos padronizados (SNOMED CT e CID-11); 
4) auditar/avaliar a qualidade vs. um **gold standard**.

O pipeline roda com **LLMs via Ollama** em duas “funções” distintas:

- **LLM avaliado (extração / normalização / expansão):** é o modelo que produz hipóteses (ex.: lista de termos e expansões).
- **LLM juiz (JUDGE_MODEL):** é usado como “validador”/“comparador semântico” para decidir se uma hipótese deve ser aceita (ex.: se um termo é clínico/útil, se a expansão faz sentido, se o mapeamento para um código está correto).

> Importante: a execução é orquestrada pelo `app.py` e os scripts são executados **sequencialmente** (não há paralelismo que “pausa o pipeline”). O que existe é auditoria/log detalhados para posterior verificação humana.

### 1.1. Etapas automáticas (end-to-end)

O pipeline completo segue esta ordem (definida pelo `app.py` e documentada também em `scripts/README.md`):

1. **`00_preprocess.py`**: limpa XMLs e gera texto em `data/output/textos_limpos/`.
2. **`01_extract_terms.py`**: chama o LLM para extrair termos; depois usa o **LLM juiz** para validar “falsos positivos” (FP) e, quando necessário, também valida expansões de abreviações.
   - Saída principal: CSVs por narrativa em `data/output/csv_individual/{id}/extracted_terms.csv` (e logs).
3. **`02_map_terminology.py`**: para cada termo extraído, consulta as APIs de **SNOMED CT (BioPortal)** e **CID-11 (WHO)**; aplica **ranking** e então usa o **LLM juiz** para validar se o candidato de código está correto.
   - Saída principal: atualiza os CSVs com `SCTID`, `CID11`, e flags de correção (`SCTID_correto`, `CID11_correto`).
4. **`03_merge_results.py`**: consolida todos os CSVs em `data/output/consolidated_terms.csv` e calcula estatísticas de mapeamento.
5. **`04_evaluate.py`**: compara predições vs. gold standard e produz métricas (VP/FP/FN) em modo **exato (strict)** e **relaxado**.
6. **`05_audit_report.py`**: gera relatórios de auditoria e arquivos auxiliares para inspeção humana (ex.: lista de rejeitados pelo juiz, comparativos VP/FP/FN).

### 1.2. Como o “LLM juiz” funciona (decisões)

O projeto implementa o “LLM juiz” via chamadas ao modelo configurado em `Config.JUDGE_MODEL`.

Na prática, o juiz aparece em três usos principais:

1) **Validação de termo clínico / rejeição de FP** (no `01_extract_terms.py`)
- Função: `is_valid_clinical_term_llm(term, contexto)`.
- O juiz recebe um prompt que contém:
  - `term` (o termo candidato)
  - `contexto` (um snippet do texto ao redor do termo, quando há correspondência)
- A decisão retornada pelo juiz é interpretada como “SIM/NAO” (string contendo “SIM” => aceita; caso contrário => rejeita).
- Resultado é armazenado em cache para reduzir custo (`fp_validation_cache.json`).

2) **Validação de expansão de abreviação** (também no `01_extract_terms.py`)
- Função: `verificar_expansao_llm(abrev, expandido)`.
- O juiz retorna `1` ou `0` para dizer se a expansão está correta.
- Resultado fica em `expansion_cache.json`.

3) **Validação do mapeamento para códigos** (em `02_map_terminology.py` / `utils.py`)
- Função: `validar_mapeamento_llm(termo_original, codigo, label_conceito, ...)`.
- O juiz recebe o termo, o código e o “label/descrição” do conceito.
- Opcionalmente, inclui `contexto_adicional` (trecho do texto original) para ajudar na decisão.
- Retorna `1` (aceito) ou `0` (rejeitado).
- Resultado é cacheado em `validation_cache.json`.

Além disso, quando existem conflitos de expansão ou de mapeamento, o projeto usa o juiz para resolver:
- `resolver_conflito_expansao(...)`
- `resolver_conflito_mapeamento(...)`

### 1.3. Como o “LLM avaliado” funciona (extração/hypotheses)

O LLM que é “avaliado” (isto é: gera a hipótese que depois será julgada) é o modelo configurado como `Config.OLLAMA_MODEL`.

No pipeline atual, a extração acontece no `01_extract_terms.py` por `PesquisaClin_Llama(textoClinico)`:
- O prompt (template em `prompts/pesquisa_clin_llama_system.py`) pede para extrair **termos clínicos** em formato JSON.
- A saída é parseada para obter `entities` com campos como:
  - `text` (termo)
  - `original` (variante original quando houver)
  - `abbreviation` (boolean)
  - `category` (Problema/Teste/Tratamento)
  - `polarity` (Positiva/Negativa)

Depois disso, o pipeline:
- remove entidades que não batem com o snippet encontrado;
- usa o **LLM juiz** para rejeitar falsos positivos;
- consolida entidades duplicadas e resolve conflitos de expansão quando existirem;
- salva logs e CSVs.

### 1.4. “Hierarquia” e organização/normalização das terminologias

O projeto não implementa uma hierarquia manual tipo “termo > sinônimo > pai” como uma árvore fixa. O que existe, na prática, é uma **normalização + resolução por caches e validação por modelo**, que funciona como uma “camada de organização” para reduzir variações:

- **Normalização de texto** (`padronizar_string`, `normalizar_termo_texto`, `normalizar_para_match` em `scripts/utils.py`).
- **Normalização com LLM** (quando usada): `normalize_with_llm` / `normalize_clinical_term`.
- **Determinismo por regras de conflito**: ao consolidar expansões, o sistema chama o juiz para decidir entre candidatos.
- **Ranking de candidatos de APIs**: ao mapear, `02_map_terminology.py` faz ranking por similaridade e então valida com o juiz.

Em outras palavras: a “hierarquia” de decisão é:
1) gerar candidatos (LLM avaliado e/ou APIs);
2) normalizar e consolidar (regras + caches);
3) validar/selecionar final com o **LLM juiz**.

### 1.5. Como o usuário pode verificar X respostas / auditar correção

O projeto gera artefatos para inspeção humana. Para checar “X respostas” de forma direta, os caminhos mais úteis são:

1) **Resposta bruta do LLM de extração por narrativa**
- `data/output/logs/{id}/llm_response_{id}.json`
- Contém o prompt e a resposta bruta do modelo (útil para auditoria do que foi extraído).

2) **Lista de termos rejeitados pelo juiz (FP)**
- `data/output/logs/filtered_terms_log.txt`

3) **Decisões individuais do “LLM juiz” (estrutura JSON)**
- `data/output/logs/decisions/`
- Cada arquivo JSON registra:
  - `decision_type` (ex.: `fp_validation`, `semantic_match`, `mapping_validation`, etc.)
  - `input` (termo/código/conteúdo usado)
  - `output` (SIM/NAO ou 1/0)
  - `cache_hit` (se veio de cache)

4) **Resultados por narrativa (CSV)**
- `data/output/csv_individual/{id}/extracted_terms.csv`
- Colunas principais incluem `textoAnalisado`, `categoria`, `abreviacao`, `SCTID`, `CID11` e flags `SCTID_correto`/`CID11_correto`.

5) **Consolidação global e avaliação vs gold standard**
- `data/output/consolidated_terms.csv`
- XLSX/CSV de avaliação:
  - `data/output/evaluation/avaliacao_exata/avaliacao_detalhada_exata.xlsx`
  - `data/output/evaluation/avaliacao_relaxada/avaliacao_detalhada_relaxada.xlsx`

6) **Arquivos de comparação VP/FP/FN para inspeção (auditoria)**
- `data/output/auditoria/comparacao/acertos_vp.csv`
- `data/output/auditoria/comparacao/falsos_positivos_fp.csv`
- `data/output/auditoria/comparacao/falsos_negativos_fn.csv`

7) **Amostra de erros classificada**
- `data/output/evaluation/avaliacao_* /erros_classificados_{sufixo}.csv` (gerado em `04_evaluate.py`).

#### “Verificar X respostas” (na prática)
Você pode escolher X linhas diretamente dos CSVs/arquivos acima (ex.: pegar as primeiras 50 FP) e comparar:
- `termoAnalisado` vs `semClin_textoAnalisado` (para FP/FN);
- `SCTID/CID11` vs `SCTID_correto/CID11_correto`;
- e abrir o arquivo JSON de decisão correspondente em `data/output/logs/decisions/` para ver a entrada e a saída do juiz.

> O projeto não “para” o pipeline: a checagem humana acontece **depois** via esses artefatos.



## 2. Dataset

O pipeline foi desenvolvido e validado utilizando o corpus **SemClin-Br** (Semantic Clinical Corpus for Brazilian Portuguese) (Oliveira et al., 2022). O corpus é composto por 1.000 anotações clínicas anotadas manualmente por especialistas de diferentes especialidades médicas e instituições. O SemClin-Br inclui 65.117 entidades anotadas, 11.263 relações semânticas, além de dicionários de abreviações médicas e pistas de negação. Ele serve como ground-truth para a extração de entidades e para a avaliação da acurácia dos mapeamentos.

Para utilizar o corpus, é necessário preencher e assinar um termo de solicitação disponível no repositório oficial do projeto. Mais informações podem ser obtidas em:

- **Artigo original**: [SemClinBr - a multi-institutional and multi-specialty semantically annotated corpus for Portuguese clinical NLP tasks](https://doi.org/10.1186/s13326-022-00269-1)
- **Repositório GitHub**: [HAILab-PUCPR/SemClinBr](https://github.com/HAILab-PUCPR/SemClinBr)

## 3. Pré-requisitos e Instalação

### 3.1. Requisitos de sistema
- Python 3.8 ou superior
- Ollama instalado e em execução
- Acesso à internet para consultas às APIs de mapeamento
- Espaço em disco: aproximadamente 5 GB (modelos, caches e dados)

### 3.2. Instalação do Ollama

```bash
# Baixar e instalar o Ollama (Linux, macOS, WSL)
curl -fsSL https://ollama.com/install.sh | sh

# ou acesse https://ollama.com/download para outras plataformas

# Baixar o modelo Llama 3.1 8B (recomendado)
ollama pull llama3.1:8b

# Iniciar o servidor (geralmente já inicia automaticamente)
ollama serve
```

### 3.3. Configuração do ambiente Python

```bash
# Criar e ativar ambiente virtual (recomendado)
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

# Instalar dependências
pip install -r requirements.txt
```

Conteúdo do `requirements.txt`:

```text
pandas
openpyxl
unidecode
scikit-learn
rapidfuzz
requests
ollama
```

### 3.4. Configuração das APIs de mapeamento

O pipeline utiliza as seguintes APIs públicas:

- **BioPortal** (SNOMED CT): requer uma chave de API gratuita. Obtenha em [https://bioportal.bioontology.org/](https://bioportal.bioontology.org/)
- **CID-11 API**: requer credenciais de cliente. Obtenha em [https://icd.who.int/icdapi](https://icd.who.int/icdapi)

As credenciais devem ser inseridas no arquivo `config/config.py`.

## 4. Estrutura do Projeto

```text
clinical-term-mapper/
├── config/
│   └── config.py                 # Configurações centralizadas
├── scripts/
│   ├── 00_preprocess.py          # Limpeza e extração de texto dos XMLs
│   ├── 01_extract_terms.py       # Extração de entidades via LLM
│   ├── 02_map_terminology.py     # Mapeamento SNOMED e CID-11
│   ├── 03_merge_results.py       # Consolidação e estatísticas
│   ├── 04_evaluate.py            # Avaliação contra gold standard
│   └── utils.py                  # Funções utilitárias
├── prompts/                      # Templates de prompts para LLM
├── data/
│   ├── narrativas/               # Arquivos XML originais
│   ├── goldstandard/             # Anotações de referência
│   ├── dicionarios/              # Caches das APIs
│   └── output/                   # Resultados gerados
├── app.py                        # Orquestrador do pipeline
├── requirements.txt
└── README.md
```

## 5. Configuração

### 5.1. Arquivo `config/config.py`

Edite as variáveis conforme sua instalação:

```python
class Config:
    # Modelo Ollama
    OLLAMA_MODEL = "llama3.1:8b"
    TEMPERATURE = 0.0
    TOP_P = 0.9
    MAX_TOKENS = 8192
    REPEAT_PENALTY = 1.1

    # Pastas
    NARRATIVES_FOLDER = "../data/narrativas"
    GOLDSTANDARD_FOLDER = "../data/goldstandard"
    OUTPUT_BASE = "../data/output"
    CSV_INDIVIDUAL_FOLDER = "../data/output/csv_individual"
    LOGS_FOLDER = "../data/output/logs"
    DICIONARIOS_FOLDER = "../data/dicionarios"
    PROMPTS_FOLDER = "../prompts"

    # Processamento
    RETRIES = 5
    EXTRA_RETRIES = 3
    MAX_WORKERS = 4               # Ajuste conforme sua CPU/GPU
    FUZZY_THRESHOLD = 65

    # APIs
    BIOPORTAL_API_KEY = "sua_chave_aqui"
    ICD_CLIENT_ID = "seu_client_id_aqui"
    ICD_CLIENT_SECRET = "seu_client_secret_aqui"
```

### 5.2. Dados de entrada

- **Narrativas**: Coloque os arquivos XML originais (com tag `<TEXT>`) em `data/narrativas/`.
- **Gold standard**: Coloque os arquivos XML anotados (com tags `<EVENT>`) em `data/goldstandard/`.
- **Prompts**: A pasta `prompts/` contém os templates LLM para cada etapa. Não altere a menos que saiba o que está fazendo.

## 6. Execução

### 6.1. Execução completa

```bash
python app.py
```

### 6.2. Execução parcial (a partir de uma etapa)

```bash
python app.py --start-at 02 --stop-after 03
```

### 6.3. Execução manual (script por script)

```bash
cd scripts
python 00_preprocess.py
python 01_extract_terms.py
python 02_map_terminology.py
python 03_merge_results.py
python 04_evaluate.py
python 05_audit_report.py
```


## 7. Saídas Geradas

| Arquivo | Descrição |
|---------|-----------|
| `data/output/csv_individual/{id}/extracted_terms.csv` | Termos extraídos e mapeados por narrativa |
| `data/output/logs/log_execucao.txt` | Log completo da execução |
| `data/output/logs/filtered_terms_log.txt` | Termos rejeitados pela validação de FP |
| `data/output/consolidated_terms.csv` | Tabela consolidada com todos os termos |

| `data/output/evaluation/avaliacao_detalhada_{sufixo}.xlsx` | Avaliação detalhada (Excel) |
| `data/output/evaluation/metricas/*` | Tabelas de métricas (contagem, precisão, recall, F1) |
| `data/output/evaluation/*/erros_classificados_{sufixo}.csv` | Análise qualitativa dos erros (por modo) |



## 8. Referências

```bibtex
@article{Oliveira2022,
  doi = {10.1186/s13326-022-00269-1},
  year = {2022},
  month = may,
  publisher = {Springer Science and Business Media {LLC}},
  volume = {13},
  number = {1},
  author = {Lucas Emanuel Silva e Oliveira and Ana Carolina Peters and Adalniza Moura Pucca da Silva and Caroline Pilatti Gebeluca and Yohan Bonescki Gumiel and Lilian Mie Mukai Cintho and Deborah Ribeiro Carvalho and Sadid Al Hasan and Claudia Maria Cabral Moro},
  title = {{SemClinBr} - a multi-institutional and multi-specialty semantically annotated corpus for Portuguese clinical {NLP} tasks},
  journal = {Journal of Biomedical Semantics}
}
```