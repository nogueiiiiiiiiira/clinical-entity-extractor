"""Anonimização via LLM (Ollama) com múltiplas rodadas, paralelismo e salvamento em txt + metadados."""

import sys
import os
import re
import time
import json
import threading
import concurrent.futures
import requests
import importlib.util

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

CATEGORY_PLACEHOLDER = {
    "idade": "[IDADE]",
    "nome": "[NOME]",
    "profissao": "[PROFISSÃO]",
    "local": "[LOCAL]",
    "organizacao": "[ORGANIZAÇÃO]",
    "contato": "[CONTATO]",
    "ids": "[IDs]",
    "data": "[DATA]",
    "horario": "[HORÁRIO]",
}


class OllamaClient:
    """Cliente para comunicação com a API do Ollama."""

    def __init__(self):
        self.base_url = Config.OLLAMA_API_URL
        self.model = Config.OLLAMA_MODEL

    def check_availability(self) -> bool:
        """Verifica se o Ollama está disponível e se o modelo configurado existe."""
        try:
            resp = requests.get("http://localhost:11434/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name") for m in models]
                if self.model not in model_names:
                    print(f"\n  Aviso: modelo '{self.model}' não encontrado. Usando {model_names[0] if model_names else 'default'}")
                    if model_names:
                        self.model = model_names[0]
                return True
            return False
        except:
            return False

    def generate(self, prompt: str) -> str:
        """Envia um prompt ao Ollama e retorna a resposta gerada."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "temperature": Config.TEMPERATURE,
            "top_p": Config.TOP_P,
            "max_tokens": Config.MAX_TOKENS
        }
        try:
            resp = requests.post(self.base_url, json=payload, timeout=Config.REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.json().get("response", "").strip()
            return ""
        except Exception as e:
            print(f"\n    ERRO Ollama: {e}")
            return ""


def parse_llm_json(response: str) -> list:
    """Extrai uma lista de termos a partir da resposta JSON ou texto simples do LLM."""
    def flatten(lst):
        for item in lst:
            if isinstance(item, list):
                yield from flatten(item)
            else:
                yield str(item) if item is not None else ''

    def clean_term(term: str) -> str:
        if not term:
            return term
        term = term.strip()
        term = re.sub(r'\s+', ' ', term)
        return term

    try:
        start = response.find('[')
        end = response.rfind(']') + 1
        if start != -1 and end > start:
            data = json.loads(response[start:end])
            if isinstance(data, list):
                terms = [clean_term(x) for x in flatten(data) if x and clean_term(x)]
                if terms:
                    return terms
            else:
                return [clean_term(str(data))]
    except:
        pass

    terms = []
    for line in response.splitlines():
        line = line.strip()
        if not line:
            continue
        line = line.rstrip(',').strip('"').strip("'").strip('[]')
        if line and not line.startswith('//') and not line.startswith('#'):
            line = clean_term(line)
            if line:
                terms.append(line)
    return terms


def mask_placeholders(text: str) -> tuple:
    """Substitui placeholders existentes por tokens temporários para evitar substituições acidentais."""
    placeholders = re.findall(r'\[[A-ZÁÉÍÓÚÃÕÇ]+(?: [A-ZÁÉÍÓÚÃÕÇ]+)*\]', text, re.IGNORECASE)
    mapping = {}
    for ph in set(placeholders):
        token = f"###PH{len(mapping)}###"
        mapping[ph] = token
    for orig, tok in mapping.items():
        text = text.replace(orig, tok)
    return text, mapping


def unmask_placeholders(text: str, mapping: dict) -> str:
    """Restaura os placeholders originais a partir dos tokens temporários."""
    for orig, tok in mapping.items():
        text = text.replace(tok, orig)
    return text


def apply_replacements(text: str, replacements: list, placeholder: str) -> str:
    """Substitui cada termo da lista pelo placeholder, protegendo placeholders existentes."""
    if not replacements:
        return text
    replacements = sorted(set([r for r in replacements if isinstance(r, str) and r]), key=len, reverse=True)
    masked, mapping = mask_placeholders(text)
    for item in replacements:
        escaped = re.escape(item)
        pattern = rf'(?<![a-zA-ZÀ-ú0-9]){escaped}(?![a-zA-ZÀ-ú0-9])'
        masked = re.sub(pattern, placeholder, masked)
    return unmask_placeholders(masked, mapping)


def load_prompt_function(cat: str):
    """Carrega dinamicamente a função get_prompt do arquivo correspondente na pasta de prompts."""
    path = os.path.join(Config.PROMPTS_FOLDER, f"{cat}.py")
    if not os.path.exists(path):
        return None
    spec = importlib.util.spec_from_file_location(cat, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, 'get_prompt', None)


def process_single_file(base_name: str, clean_text: str, client: OllamaClient) -> tuple:
    """Executa todas as rodadas de anonimização para um arquivo e retorna (texto_anonimizado, tempo_processamento)."""
    start_time = time.time()
    llm_text = clean_text
    categories = ["contato", "ids", "horario", "data", "idade", "profissao", "organizacao", "nome", "local"]

    for cat in categories:
        prompt_func = load_prompt_function(cat)
        if not prompt_func:
            continue
        for round_num in range(1, Config.ROUNDS_PER_CATEGORY + 1):
            prompt = prompt_func(llm_text)
            response = client.generate(prompt)
            if not response:
                continue
            terms = parse_llm_json(response)
            placeholder = CATEGORY_PLACEHOLDER.get(cat)
            if cat == "idade":
                valid_terms = [t for t in terms if isinstance(t, str) and t.isdigit() and int(t) > 90]
                if valid_terms:
                    llm_text = apply_replacements(llm_text, [f"{t} anos" for t in valid_terms], placeholder)
            else:
                if terms:
                    llm_text = apply_replacements(llm_text, terms, placeholder)
            time.sleep(0.2)
        time.sleep(0.3)

    elapsed = time.time() - start_time
    return llm_text, elapsed


def worker(filename, client, lock, progress, total):
    """Função executada por cada thread para processar um arquivo individual."""
    base = filename.replace('.txt', '')
    clean_path = os.path.join(Config.CLEAN_TEXTS_FOLDER, filename)
    with open(clean_path, 'r', encoding='utf-8') as f:
        clean_text = f.read()

    print(f"\n\n[{base}] Iniciando anonimização...")
    anon_text, proc_time = process_single_file(base, clean_text, client)

    llm_out = os.path.join(Config.LLM_OUTPUT_FOLDER, f"{base}.txt")
    with open(llm_out, 'w', encoding='utf-8') as f:
        f.write(anon_text)

    meta = {
        "processing_time": proc_time,
        "placeholder_changes": {}
    }
    meta_path = os.path.join(Config.METADATA_FOLDER, f"{base}.meta.json")
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    with lock:
        progress[0] += 1
        print(f"\n[{base}] Concluído ({progress[0]}/{total}) em {proc_time:.2f}s")


def main() -> None:
    """Orquestra o processo de anonimização paralela para todos os arquivos de texto limpo."""
    client = OllamaClient()
    if not client.check_availability():
        print("\n\nOllama indisponível. Verifique se está rodando.")
        return

    os.makedirs(Config.LLM_OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(Config.METADATA_FOLDER, exist_ok=True)

    txt_files = [f for f in os.listdir(Config.CLEAN_TEXTS_FOLDER) if f.endswith('.txt')]
    total = len(txt_files)
    print(f"\n\nEncontrados {total} arquivos de texto limpo")

    progress = [0]
    lock = threading.Lock()

    with concurrent.futures.ThreadPoolExecutor(max_workers=Config.MAX_WORKERS) as executor:
        futures = []
        for idx, filename in enumerate(txt_files):
            if idx > 0 and idx % Config.BREAK_EVERY_N_FILES == 0:
                break_duration = Config.BREAK_DURATION
                if Config.PROGRESSIVE_BREAK:
                    break_duration = Config.BREAK_DURATION * ((idx // Config.BREAK_EVERY_N_FILES) + 1)
                print(f"\n\nPausa de {break_duration}s...")
                time.sleep(break_duration)
            if idx > 0:
                time.sleep(Config.FILE_PAUSE)

            future = executor.submit(worker, filename, client, lock, progress, total)
            futures.append(future)

        for future in concurrent.futures.as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"\nErro em worker: {e}")

    print("\n\nAnonimização concluída!")


if __name__ == "__main__":
    main()