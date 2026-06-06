# Clinical Text Deidentifier – Pipeline de Anonimização de Narrativas Clínicas

Este pipeline foi desenvolvido e utilizado no estudo comparativo entre dois grandes modelos de linguagem (LLMs) – **Llama 3.1 (8B)** e **Gemma-Gaia (4B)** – para anonimização de textos clínicos em português brasileiro, utilizando o corpus **AnonyMED-BR**. O sistema aplica uma estratégia de substituição de entidades sensíveis por placeholders padronizados (`[NOME]`, `[DATA]`, `[ORGANIZAÇÃO]`, etc.), preservando a estrutura sintática e o significado clínico do texto.

Os resultados obtidos, as métricas de precisão, recall e F1, bem como as análises de erros e correlações, são discutidos no artigo correspondente. Este README fornece todas as instruções necessárias para reproduzir o pipeline, desde a instalação de dependências até a execução completa e avaliação dos modelos.

## Sumário

- [Contexto e Fundamentação](#contexto-e-fundamentação)
- [O Corpus AnonyMED-BR e os Gabaritos Manuais](#o-corpus-anonymed-br-e-os-gabaritos-manuais)
- [Visão Geral do Pipeline](#visão-geral-do-pipeline)
- [Pré-requisitos](#pré-requisitos)
  - [Software Necessário](#software-necessário)
  - [Bibliotecas Python](#bibliotecas-python)
  - [Modelos Ollama](#modelos-ollama)
  - [Dados de Entrada](#dados-de-entrada)
- [Estrutura de Diretórios](#estrutura-de-diretórios)
- [Configuração](#configuração)
  - [Arquivo config.py](#arquivo-configpy)
  - [Arquivos de Prompt](#arquivos-de-prompt)
- [Execução Passo a Passo](#execução-passo-a-passo)
- [Descrição dos Scripts Utilitários](#descrição-dos-scripts-utilitários)
- [Avaliação e Métricas](#avaliação-e-métricas)
  - [Algoritmo de Alinhamento: Longest Common Subsequence (LCS)](#algoritmo-de-alinhamento-longest-common-subsequence-lcs)
- [Resolução de Problemas](#resolução-de-problemas)
- [Referências](#referências)

---

## Contexto e Fundamentação

A digitalização de informações clínicas e o avanço de modelos preditivos em saúde exigem mecanismos robustos de proteção de dados pessoais. No Brasil, a Lei Geral de Proteção de Dados (LGPD) e, internacionalmente, o GDPR e o HIPAA (Safe Harbor method) estabelecem diretrizes para a desidentificação de informações de saúde. Entretanto, a simples remoção de identificadores diretos não é suficiente para aplicações de aprendizado de máquina, pois modelos preditivos dependem de sequências temporais, contexto semântico e padrões relacionais.

Uma estratégia mais eficaz é a substituição de entidades sensíveis por placeholders semânticos, mantendo a estrutura textual. É nesse contexto que este pipeline foi desenvolvido, permitindo a comparação de dois LLMs em um corpus realista de português brasileiro: **AnonyMED-BR**.

Os modelos comparados foram:
- **Llama 3.1 (8B)** – modelo geral de grande porte.
- **Gemma-Gaia (4B)** – modelo otimizado para o português brasileiro (CEIA-UFG).

O pipeline descrito aqui foi utilizado para executar a anonimização, gerar os textos com placeholders e calcular as métricas de desempenho (precisão, recall, F1) por meio de anotação manual dos erros (TP, FP, FN).

---

## O Corpus AnonyMED-BR e os Gabaritos Manuais

**AnonyMED-BR** é um dataset público de narrativas clínicas em português brasileiro, disponibilizado pela Venturus no Hugging Face: [https://huggingface.co/datasets/Venturus/AnonyMED-BR](https://huggingface.co/datasets/Venturus/AnonyMED-BR). O corpus contém textos reais ou realisticamente simulados, anotados com múltiplas categorias de informações sensíveis, incluindo nomes de pacientes e profissionais, datas, contatos, identificadores profissionais (CRM, Coren), locais, organizações de saúde e idades. As anotações originais do dataset foram realizadas de forma semiautomática com revisão humana, mas para este estudo foi necessário construir **gabaritos de referência manual** específicos para a tarefa de anonimização por placeholders.

Os gabaritos utilizados neste pipeline (`data/textos_anonimizados/*_gabarito.txt`) foram criados **manualmente por especialistas** a partir dos textos originais do AnonyMED-BR. Cada gabarito consiste no mesmo texto original, porém com todas as entidades sensíveis substituídas pelos placeholders padronizados (`[NOME]`, `[DATA]`, `[CONTATO]`, etc.), seguindo as mesmas regras definidas nos prompts do LLM. Esse processo manual garante um padrão-ouro confiável para a avaliação, pois elimina vieses automáticos e permite a validação independente do desempenho dos modelos.

Além do dataset de textos, a Venturus também disponibiliza um modelo fine-tuned para reconhecimento de entidades sensíveis em português clínico: [BERTimbau-AnonyMED-BR](https://huggingface.co/Venturus/BERTimbau-AnonyMED-BR). Esse modelo serve como referência adicional para tarefas de NER, mas não foi utilizado diretamente neste pipeline, que foca na substituição por placeholders via LLMs.

---

## Visão Geral do Pipeline

O fluxo de processamento é composto por seis etapas principais (conforme Figura 3 do artigo):

1. **Seleção dos modelos e das narrativas** (definida pelo usuário).
2. **Pré-processamento** – limpeza dos XMLs e extração do texto puro.
3. **Inferência baseada em prompts** – anonimização iterativa via LLM (várias rodadas por categoria).
4. **Anotação manual** – comparação com gabaritos para classificação de TP, FP, FN (etapa essencial para avaliação).
5. **Cálculo das métricas** – precisão, recall, F1 por categoria e agregadas (micro e macro).
6. **Comparação final** – geração de relatórios e análises avançadas.

O pipeline é totalmente executado localmente, sem envio de dados para servidores externos, atendendo a requisitos de privacidade de ambientes hospitalares.

---

## Pré-requisitos

### Software Necessário

- **Python 3.8+** (recomendado 3.10)
- **Ollama** (versão mais recente) – [https://ollama.com/download](https://ollama.com/download)
- **Git** (opcional, para clonar o repositório)

### Bibliotecas Python

Instale as dependências com:

```bash
pip install requests numpy matplotlib
```

- `requests`: comunicação com a API do Ollama.
- `numpy`: cálculos estatísticos para análises avançadas.
- `matplotlib`: geração de gráficos (opcional, mas recomendada).

### Modelos Ollama

Faça o download dos modelos que deseja testar. No estudo, foram utilizados:

```bash
ollama pull llama3.1:8b
ollama pull hf.co/CEIA-UFG/Gemma-3-Gaia-PT-BR-4b-it-GGUF-F16:latest
```

Para usar um modelo diferente, altere a variável `OLLAMA_MODEL` no arquivo `config/config.py`.

Certifique-se de que o serviço Ollama esteja em execução:

```bash
ollama serve
```

Teste a conectividade:

```bash
curl http://localhost:11434/api/tags
```

### Dados de Entrada

- **Narrativas clínicas** em formato XML, contendo uma tag `<text>`. Os arquivos originais devem ser obtidos do dataset AnonyMED-BR (convertidos para XML conforme necessário). Coloque-os em `data/narrativas/`.

- **Gabaritos manuais** – arquivos de texto plano com os placeholders já aplicados por especialistas. Cada gabarito deve ter o nome `{id}_gabarito.txt`, onde `{id}` é o nome base do XML (ex.: `2697.xml` → `2697_gabarito.txt`). Os gabaritos devem estar em `data/textos_anonimizados/`. Se não existirem, a etapa de avaliação será pulada para os arquivos correspondentes.

- **Prompts** – arquivos Python (ex.: `contato.py`, `nome.py`) contendo a função `get_prompt(text: str) -> str`. Esses prompts são carregados dinamicamente e devem estar na pasta `data/prompts/`. Eles seguem o mesmo formato utilizado no estudo.

---

## Estrutura de Diretórios

Após clonar ou criar o projeto, a estrutura esperada é:

```
seu_projeto/
├── config/
│   └── config.py
├── scripts/
│   ├── 00_clean.py
│   ├── 01_anonymizer.py
│   ├── 02_apply_regex.py
│   ├── 03_merge.py
│   ├── 04_evaluate.py
│   ├── 05_advanced_analysis.py
│   ├── check_gabaritos.py
│   ├── extract_texts.py
│   └── count_placeholders.py
├── data/
│   ├── narrativas/               # XMLs originais (AnonyMED-BR)
│   ├── textos_anonimizados/      # Gabaritos manuais (*_gabarito.txt)
│   ├── prompts/                  # Arquivos de prompt (contato.py, etc.)
│   └── output/                   # Gerado automaticamente
│       ├── textos_limpos/
│       ├── LLM_only/
│       ├── REGEX_only/
│       ├── metadata/
│       ├── final_results.jsonl
│       └── evaluation/
└── README.md
```

Todos os caminhos podem ser ajustados no `config/config.py`.

---

## Configuração

### Arquivo config.py

O arquivo `config/config.py` contém todos os parâmetros do pipeline. Abaixo um exemplo completo:

```python
class Config:
    # Ollama
    OLLAMA_MODEL = "hf.co/CEIA-UFG/Gemma-3-Gaia-PT-BR-4b-it-GGUF-F16:latest"
    OLLAMA_API_URL = "http://localhost:11434/api/generate"
    TEMPERATURE = 0.0
    TOP_P = 0.95
    MAX_TOKENS = 256
    REQUEST_TIMEOUT = None

    # Pastas (caminhos relativos a partir do diretório scripts)
    NARRATIVES_FOLDER = "../data/narrativas"
    GABARITOS_FOLDER = "../data/textos_anonimizados"
    OUTPUT_BASE = "../data/output"
    CLEAN_TEXTS_FOLDER = "../data/output/textos_limpos"
    LLM_OUTPUT_FOLDER = "../data/output/LLM_only"
    REGEX_OUTPUT_FOLDER = "../data/output/REGEX_only"
    METADATA_FOLDER = "../data/output/metadata"
    PROMPTS_FOLDER = "../data/prompts"

    # Processamento
    ROUNDS_PER_CATEGORY = 6       # rodadas por categoria
    MAX_WORKERS = 3               # threads paralelas
    DEBUG = False
    BREAK_EVERY_N_FILES = 5
    BREAK_DURATION = 30           # segundos
    FILE_PAUSE = 2
    PROGRESSIVE_BREAK = True
```

Para testar outro modelo, altere `OLLAMA_MODEL`. Para desabilitar pausas, ajuste `BREAK_EVERY_N_FILES` para um valor alto (ex.: 9999).

### Arquivos de Prompt

Os prompts definem como o LLM deve anonimizar cada categoria. Cada arquivo `data/prompts/{categoria}.py` deve exportar uma função:

```python
def get_prompt(text: str) -> str:
    return f"""... {text} ..."""
```

Eles são carregados dinamicamente durante a execução do `01_anonymizer.py`. O estudo utilizou prompts que instruem o modelo a substituir **todas** as ocorrências de telefones, e-mails, nomes, datas, horários, IDs profissionais (CRM, Coren), locais, organizações e idades acima de 90 anos, preservando placeholders já existentes.

---

## Execução Passo a Passo

Navegue até a pasta `scripts/` e execute os comandos na ordem indicada.

### 1. Limpeza dos XMLs

```bash
python 00_clean.py
```

Extrai o texto da tag `<text>`, remove todas as tags XML/HTML e normaliza espaços. Gera arquivos `.txt` em `../data/output/textos_limpos/`.

### 2. Anonimização via LLM

```bash
python 01_anonymizer.py
```

- Processa em paralelo (respeitando `MAX_WORKERS`).
- Para cada arquivo, executa `ROUNDS_PER_CATEGORY` rodadas para cada categoria (ordem fixa: contato, ids, horario, data, idade, profissao, organizacao, nome, local).
- Utiliza os prompts da pasta `data/prompts/`.
- Salva o texto anonimizado em `../data/output/LLM_only/` e os metadados (tempo de processamento) em `../data/output/metadata/`.

### 3. Refinamento com Regex

```bash
python 02_apply_regex.py
```

Aplica expressões regulares para capturar entidades que o LLM pode ter perdido (telefones, e-mails, datas, IDs, etc.). Protege palavras seguras (medicamentos, siglas) e evita placeholders consecutivos. Atualiza os metadados com as mudanças (`placeholder_changes`). Saída em `../data/output/REGEX_only/`.

### 4. Merge para JSONL

```bash
python 03_merge.py
```

Consolida texto original, LLM, regex, metadados e gabarito (se existir) em um único arquivo `../data/output/final_results.jsonl`. Cada linha é um objeto JSON com os campos:
- `filename`
- `original_txt`
- `llm_anonymized_txt`
- `with_regex_txt`
- `gabarito_txt`
- `processing_time`
- `placeholder_changes`

### 5. Avaliação (comparação com gabaritos)

```bash
python 04_evaluate.py --input ../data/output/final_results.jsonl --model-field with_regex_txt
```

- `--model-field` pode ser `llm_anonymized_txt` ou `with_regex_txt`.
- Calcula TP, FP, FN, precisão, recall e F1 para cada categoria e para o total (micro e macro).
- Gera:
  - `evaluation/report_with_regex_txt.json` (ou `report_llm_anonymized_txt.json`)
  - `evaluation/metricas_completas.csv`
  - `evaluation/{id}_placeholders.csv` para cada arquivo

### 6. Análises Avançadas

```bash
python 05_advanced_analysis.py --eval-dir ../data/output/evaluation --original-dir ../data/output/textos_limpos
```

- Calcula intervalo de confiança (bootstrap) para o F1 macro.
- Constrói matriz de confusão a partir dos arquivos `*_placeholders.csv`.
- Correlaciona comprimento do texto (número de palavras) com o F1 macro.
- Gera `bootstrap_results.csv`, `confusion_matrix.csv` e (se `matplotlib` instalado) `length_vs_f1.png`.

---

## Descrição dos Scripts Utilitários

| Script | Finalidade | Exemplo de uso |
|--------|------------|----------------|
| `check_gabaritos.py` | Verifica se todos os XMLs possuem gabarito correspondente. | `python check_gabaritos.py` |
| `extract_texts.py` | Extrai um campo específico do `final_results.jsonl` para arquivos `.txt` individuais. | `python extract_texts.py --field with_regex_txt --suffix _regex` |
| `count_placeholders.py` | Conta a frequência de placeholders em arquivos `.txt` de um diretório. | `python count_placeholders.py --dir ../data/output/REGEX_only` |

Todos os utilitários herdam os caminhos do `config.py`, mas aceitam argumentos para sobrescrever.

---

## Avaliação e Métricas

### Definições básicas

- **True Positive (TP)**: placeholder correto, na posição correta, conforme o gabarito.
- **False Negative (FN)**: placeholder ausente no texto gerado, mas presente no gabarito.
- **False Positive (FP)**: placeholder presente no texto gerado, mas ausente no gabarito.

### Algoritmo de Alinhamento: Longest Common Subsequence (LCS)

Para comparar as sequências de placeholders do gabarito e do modelo de forma justa, é utilizado o algoritmo da **subsequência comum mais longa (LCS)**. Diferente de uma simples comparação de conjuntos, o LCS respeita a ordem linear dos placeholders no texto. Isso evita que placeholders deslocados sejam erroneamente contabilizados como corretos.

O funcionamento é o seguinte:

- Extraem-se duas listas ordenadas de placeholders: `G = [g1, g2, ..., gn]` do gabarito e `M = [m1, m2, ..., mk]` do modelo.
- O LCS encontra a maior sequência de placeholders que aparece em ambas as listas na mesma ordem.
- Os placeholders alinhados pelo LCS são considerados **TP**.
- Os placeholders do gabarito que não foram alinhados são **FN**.
- Os placeholders do modelo que não foram alinhados são **FP**.

Esse método garante que a avaliação seja sensível à posição dos placeholders, evitando falsos positivos por simples coincidência de categoria em locais diferentes do texto.

### Métricas calculadas

Por categoria e globalmente:

- **Precisão** = TP / (TP + FP)
- **Recall** = TP / (TP + FN)
- **F1** = 2 * (Precisão * Recall) / (Precisão + Recall)

**Micro average**: agrega todos os placeholders independentemente da categoria.
**Macro average**: média aritmética das métricas de cada categoria.

Os resultados são salvos em JSON e CSV, permitindo análise detalhada.

---

## Resolução de Problemas

### Erro: `ModuleNotFoundError: No module named 'config'`

Certifique-se de que:
- Você está executando os scripts de dentro da pasta `scripts/`.
- O arquivo `config/config.py` existe e contém a classe `Config`.
- O diretório `config` está no mesmo nível que `scripts`.

### Ollama não responde ou retorna vazio

- Verifique se o serviço está rodando: `curl http://localhost:11434/api/tags`.
- Inicie com `ollama serve` se necessário.
- Confirme que o modelo configurado foi baixado: `ollama list`.
- Aumente `REQUEST_TIMEOUT` no `config.py` (ex.: 120 segundos) se as respostas forem lentas.

### Os placeholders no gabarito não correspondem aos gerados

Os placeholders devem seguir exatamente os nomes usados pelo pipeline:
`[NOME]`, `[PROFISSÃO]`, `[CONTATO]`, `[IDs]`, `[DATA]`, `[HORÁRIO]`, `[LOCAL]`, `[ORGANIZAÇÃO]`, `[IDADE]`.  

O avaliador converte automaticamente `[ID]` para `[IDs]` para compatibilidade, mas recomenda-se usar `[IDs]`.

### O script `01_anonymizer.py` consome muita memória

- Diminua `MAX_WORKERS` (ex.: 1).
- Se possível, use um modelo menor (ex.: Gemma-Gaia 4B em vez de Llama 8B).
- Aumente `FILE_PAUSE` e `BREAK_DURATION` para dar tempo ao sistema.

### A análise avançada não gera gráfico

Instale `matplotlib`: `pip install matplotlib`. Se ainda assim não funcionar, o script continua sem gráfico.

---

## Referências

- Dataset AnonyMED-BR: [https://huggingface.co/datasets/Venturus/AnonyMED-BR]
- Llama 3.1 Model Card – AI@Meta, 2024.
- Gemma-3-Gaia-PT-BR-4b-it – CEIA-UFG, 2025.

