"""Configurações centrais para o pipeline de extração e mapeamento de termos clínicos."""

import os


class Config:
    """Armazena todos os parâmetros de configuração, caminhos e credenciais de API."""

    _REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    OLLAMA_MODEL = "hf.co/althayr/Gemma-3-Gaia-PT-BR-4b-it-GGUF:latest"
    TEMPERATURE = 0.0
    TOP_P = 0.9
    MAX_TOKENS = 8192
    REPEAT_PENALTY = 1.1

    # Paths absolutos (evita dependência do cwd ao executar scripts)
    NARRATIVES_FOLDER = os.path.join(_REPO_ROOT, "data", "narr")
    GOLDSTANDARD_FOLDER = os.path.join(_REPO_ROOT, "data", "goldstandard")
    OUTPUT_BASE = os.path.join(_REPO_ROOT, "data", "output")
    CSV_INDIVIDUAL_FOLDER = os.path.join(OUTPUT_BASE, "csv_individual")
    LOGS_FOLDER = os.path.join(OUTPUT_BASE, "logs")
    DICIONARIOS_FOLDER = os.path.join(_REPO_ROOT, "data", "dicionarios")
    PROMPTS_FOLDER = os.path.join(_REPO_ROOT, "prompts")
    CLEAN_TEXTS_FOLDER = os.path.join(OUTPUT_BASE, "textos_limpos")

    RETRIES = 1
    EXTRA_RETRIES = 1
    MAX_WORKERS = None
    FUZZY_THRESHOLD = 65
    TFIDF_SIMILARITY_THRESHOLD = 0.7

    BIOPORTAL_API_KEY = "09b5677b-aa9d-4e32-b509-bfccfe44c479"
    BIOPORTAL_URL = "http://data.bioontology.org/search"
    SNOMED_ONTOLOGY = "SNOMEDCT"

    ICD_CLIENT_ID = "afb2f66b-de75-4d66-8681-34e43d850e7f_2d7236dc-d3fb-4a0c-b82d-1df68052cc34"
    ICD_CLIENT_SECRET = "mMQOGiELy99d3yU0KcXbM0NGw52zNbExxfdgaIBoMAw="
    ICD_TOKEN_URL = "https://icdaccessmanagement.who.int/connect/token"
    ICD_SEARCH_URL = "https://id.who.int/icd/release/11/2024-01/mms/search"

    CACHE_FILE = "api_cache.json"
    VALIDATION_CACHE_FILE = "validation_cache.json"
    EXPANSION_CACHE_FILE = "expansion_cache.json"
    NORM_CACHE_FILE = "norm_cache.json"
    FP_VALIDATION_CACHE_FILE = "fp_validation_cache.json"

