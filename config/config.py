"""Configurações globais do pipeline de anonimização."""

class Config:
    """Armazena parâmetros de execução, caminhos e configurações do modelo."""

    OLLAMA_MODEL = "llama3.1:8b"
    OLLAMA_API_URL = "http://localhost:11434/api/generate"
    TEMPERATURE = 0.0
    TOP_P = 0.95
    MAX_TOKENS = 256
    REQUEST_TIMEOUT = None

    NARRATIVES_FOLDER = "../data/narrativas"
    GABARITOS_FOLDER = "data/gabarito"
    OUTPUT_BASE = "data/output"
    CLEAN_TEXTS_FOLDER = "data/output/textos_limpos"
    LLM_OUTPUT_FOLDER = "data/output/LLM_only"
    REGEX_OUTPUT_FOLDER = "data/output/REGEX_only"
    METADATA_FOLDER = "../data/output/metadata"
    PROMPTS_FOLDER = "../data/prompts"

    ROUNDS_PER_CATEGORY = 6
    MAX_WORKERS = 3
    DEBUG = False
    BREAK_EVERY_N_FILES = 5
    BREAK_DURATION = 30
    FILE_PAUSE = 2
    PROGRESSIVE_BREAK = True