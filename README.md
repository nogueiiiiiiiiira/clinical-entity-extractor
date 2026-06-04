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
- [8. Exemplo de Uso](#8-exemplo-de-uso)
- [9. Troubleshooting](#9-troubleshooting)
- [10. Citação](#10-citação)

## 1. Sobre o Pipeline

O Clinical Term Mapper é um pipeline modular para extração e mapeamento de entidades clínicas em narrativas médicas em português brasileiro. Utiliza modelos de linguagem de grande escala (LLMs) via Ollama para identificar termos clínicos (doenças, sintomas, medicamentos, exames, procedimentos) e expandir abreviações, seguido de um mapeamento automático para códigos padronizados:

- **SNOMED CT**: via BioPortal API
- **CID-11**: via API oficial da Organização Mundial da Saúde

O pipeline inclui também uma etapa de validação semântica dos mapeamentos usando LLM, garantindo alta precisão nas anotações.

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
```

## 7. Saídas Geradas

| Arquivo | Descrição |
|---------|-----------|
| `output/csv_individual/{id}/extracted_terms.csv` | Termos extraídos e mapeados por narrativa |
| `output/logs/log_execucao.txt` | Log completo da execução |
| `output/logs/filtered_terms_log.txt` | Termos rejeitados pela validação de FP |
| `output/consolidated_terms.csv` | Tabela consolidada com todos os termos |
| `output/evaluation/avaliacao_detalhada_{sufixo}.xlsx` | Avaliação detalhada (Excel) |
| `output/evaluation/tabela*.csv` | Tabelas de métricas (contagem, precisão, recall, F1) |
| `output/evaluation/erros_classificados.csv` | Análise qualitativa dos erros |


## 8. Troubleshooting

| Problema | Solução |
|----------|---------|
| `ModuleNotFoundError: No module named 'config'` | Execute os scripts a partir da raiz do projeto ou ajuste `sys.path` nos scripts. |
| Ollama não responde | Verifique se o serviço está ativo: `ollama serve`. Teste com `curl http://localhost:11434/api/tags`. |
| Erro de autenticação nas APIs | Confirme as credenciais no `config/config.py`. Verifique sua conexão com a internet. |
| Tempo de execução muito longo | Reduza `MAX_WORKERS` para 2 ou 1, ou aumente `MAX_TOKENS` (mais lento, porém mais preciso). |
| Baixa acurácia nos mapeamentos | Aumente o número de `RETRIES` (ex.: 7) e utilize um modelo LLM mais robusto (ex.: `llama3.1:70b`). |
| `KeyError: 'expansao_correta'` | Certifique-se de que a coluna foi gerada no `01_extract_terms.py`. Verifique os logs. |

## 9. Referências

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