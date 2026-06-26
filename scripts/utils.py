"""Funções utilitárias compartilhadas entre todos os scripts do pipeline, incluindo redirecionamento de log."""

import sys
import os
import re
import json
import time
import threading
import requests
import unidecode
import pandas as pd
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import ollama


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config


cache_lock = threading.Lock()
_icd_token = None
_token_expiry = 0


class Tee:
    """Redireciona a saída padrão para múltiplos arquivos ao mesmo tempo."""

    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            try:
                f.write(obj)
                f.flush()
            except ValueError:
                pass

    def flush(self):
        for f in self.files:
            try:
                f.flush()
            except ValueError:
                pass


def _save_llm_response(model: str, prompt: str, response: str, response_type: str, identifier: str = ""):
    """Salva a resposta do LLM em um arquivo de log com timestamp."""
    os.makedirs(Config.LLM_RESPONSES_FOLDER, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe_type = re.sub(r'[^a-zA-Z0-9_]', '_', response_type)
    filename = f"{timestamp}_{safe_type}_{identifier}.json"
    filepath = os.path.join(Config.LLM_RESPONSES_FOLDER, filename)
    log_data = {
        "timestamp": timestamp,
        "model": model,
        "type": response_type,
        "identifier": identifier,
        "prompt": prompt,
        "response": response
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(log_data, f, indent=2, ensure_ascii=False)


def load_json_cache(filepath: str) -> dict:
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_json_cache(cache: dict, filepath: str) -> None:
    with cache_lock:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)


def padronizar_string(string) -> str:
    if isinstance(string, str):
        return unidecode.unidecode(string.lower().strip())
    return str(string) if string is not None else ""


def normalize_basic(term: str) -> str:
    t = padronizar_string(term)
    t = ''.join(c for c in t if c.isalnum() or c.isspace())
    return t


def normalize_with_llm(term: str, norm_cache: dict, norm_cache_file: str) -> str:
    if term in norm_cache:
        return norm_cache[term]
    from prompts.normalize_with_llm_user import USER_TEMPLATE
    from prompts.normalize_with_llm_system import SYSTEM_PROMPT as NORM_SYSTEM
    user_prompt = USER_TEMPLATE.format(term=term)
    try:
        resp = ollama.chat(model=Config.OLLAMA_MODEL,
                           messages=[{"role": "system", "content": NORM_SYSTEM},
                                     {"role": "user", "content": user_prompt}],
                           options={"temperature": 0.0})
        normalized = resp["message"]["content"].strip()
        normalized = normalized.split('.')[0].strip()
        normalized = normalized.split('\n')[0].strip()
        if len(normalized) > 100:
            normalized = term
        result = normalized if normalized else term
        _save_llm_response(Config.OLLAMA_MODEL, user_prompt, resp["message"]["content"], "normalize_with_llm", term)
    except:
        result = term
    norm_cache[term] = result
    save_json_cache(norm_cache, norm_cache_file)
    return result


def normalize_term(term: str, norm_cache: dict, norm_cache_file: str) -> str:
    return normalize_with_llm(term, norm_cache, norm_cache_file)


def normalize_clinical_term(term: str, norm_cache: dict, norm_cache_file: str) -> str:
    from prompts.normalize_clinical_term_user import USER_TEMPLATE
    from prompts.normalize_clinical_term_system import SYSTEM_PROMPT as NORM_CLIN_SYSTEM
    user_prompt = USER_TEMPLATE.format(term=term)
    try:
        resp = ollama.chat(model=Config.OLLAMA_MODEL,
                           messages=[{"role": "system", "content": NORM_CLIN_SYSTEM},
                                     {"role": "user", "content": user_prompt}],
                           options={"temperature": 0})
        normalized = resp["message"]["content"].strip()
        _save_llm_response(Config.OLLAMA_MODEL, user_prompt, resp["message"]["content"], "normalize_clinical_term", term)
        if normalized:
            return normalized
    except:
        pass
    t = term.lower()
    t = re.sub(r'\b\d+[.,]?\d*\s*(mg|g|ui|mcg|ml|cp|%|x/?dia|cp/dia|/dia|cp ao dia|vezes ao dia|gotas?/?semana|comp|comprimidos?)\b', '', t)
    t = re.sub(r'\b\d+\s*-\s*\d+\s*(mg|g|ui|mcg|ml)\b', '', t)
    t = re.sub(r'\b\d+\s*x\s*/?\s*dia\b', '', t)
    t = re.sub(r'\b\d+/\d+\s*(h|hora)?\b', '', t)
    t = re.sub(r'\b\d+\s*cp\b', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t if t else term


def query_snomed(query: str, api_cache: dict, cache_file: str) -> list:
    norm_q = normalize_basic(query)
    if norm_q in api_cache:
        return api_cache[norm_q].get("snomed_results", [])
    params = {"q": query, "ontologies": Config.SNOMED_ONTOLOGY}
    headers = {"Authorization": f"apikey token={Config.BIOPORTAL_API_KEY}"}
    try:
        r = requests.get(Config.BIOPORTAL_URL, params=params, headers=headers, timeout=None)
        if r.status_code != 200:
            return []
        data = r.json()
        results = []
        for item in data.get("collection", []):
            label = item.get("prefLabel", "")
            concept_id = item.get("@id", "")
            code = concept_id.split("/")[-1] if concept_id else ""
            if label and code:
                results.append({"code": code, "label": label})
        if norm_q not in api_cache:
            api_cache[norm_q] = {}
        api_cache[norm_q]["snomed_results"] = results
        save_json_cache(api_cache, cache_file)
        return results
    except:
        return []


def get_label_snomed(code: str) -> str:
    url = f"http://data.bioontology.org/ontologies/SNOMEDCT/classes?include=prefLabel&conceptid={code}"
    headers = {"Authorization": f"apikey token={Config.BIOPORTAL_API_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=None)
        if r.status_code == 200:
            data = r.json()
            return data.get("prefLabel", "")
    except:
        pass
    return ""


def get_icd_token() -> str:
    global _icd_token, _token_expiry
    if _icd_token and time.time() < _token_expiry:
        return _icd_token
    data = {"client_id": Config.ICD_CLIENT_ID, "client_secret": Config.ICD_CLIENT_SECRET, "grant_type": "client_credentials"}
    try:
        r = requests.post(Config.ICD_TOKEN_URL, data=data, timeout=None)
        if r.status_code != 200:
            print(f"ICD token error: {r.status_code} - {r.text[:200]}")
            return None
        token_data = r.json()
        _icd_token = token_data["access_token"]
        _token_expiry = time.time() + token_data.get("expires_in", 3600) - 60
        return _icd_token
    except Exception as e:
        print(f"ICD token exception: {e}")
        return None


def query_icd11(query: str, api_cache: dict, cache_file: str, force_refresh: bool = False) -> list:
    norm_q = normalize_basic(query)
    if not force_refresh and norm_q in api_cache:
        cached = api_cache[norm_q].get("icd11_results")
        if cached is not None:
            return cached
    token = get_icd_token()
    if not token:
        print(f"ICD-11: no token for query '{query}'")
        return []
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Language": "pt",
        "API-Version": "v2"
    }
    params = {"q": query, "useFlexisearch": "true"}
    try:
        r = requests.get(Config.ICD_SEARCH_URL, headers=headers, params=params, timeout=30)
        print(f"ICD-11 query: '{query}' | status={r.status_code}")
        if r.status_code != 200:
            print(f"ICD-11 error body: {r.text[:300]}")
            return []
        data = r.json()
        results = []
        for item in data.get("destinationEntities", []):
            code = item.get("thematicCode") or item.get("code")
            if not code:
                id_url = item.get("id", "")
                if id_url:
                    code = id_url.rstrip('/').split('/')[-1]
            title = item.get("title")
            if isinstance(title, dict):
                title = title.get("@value")
            if code and title:
                results.append({"code": code, "title": title})
        if norm_q not in api_cache:
            api_cache[norm_q] = {}
        api_cache[norm_q]["icd11_results"] = results
        save_json_cache(api_cache, cache_file)
        return results
    except Exception as e:
        print(f"ICD-11 exception: {e}")
        return []


def get_label_cid11(code: str) -> str:
    token = get_icd_token()
    if not token:
        return ""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Accept-Language": "pt",
        "API-Version": "v2"
    }
    url = f"https://id.who.int/icd/release/11/2024-01/mms/{code}"
    try:
        r = requests.get(url, headers=headers, timeout=None)
        if r.status_code == 200:
            data = r.json()
            title = data.get("title", {})
            if isinstance(title, dict):
                return title.get("@value", "")
            return str(title)
    except:
        pass
    return ""


def similarity(a: str, b: str) -> float:
    vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(2,4), lowercase=True)
    try:
        tfidf = vectorizer.fit_transform([a, b])
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
    except:
        sim = 0.0
    return sim


def rank_results(results: list, query: str, is_snomed: bool = True) -> list:
    scored = []
    query_norm = normalize_basic(query)
    for res in results:
        label = normalize_basic(res.get("label" if is_snomed else "title", ""))
        sim = similarity(query_norm, label)
        scored.append((res, min(1.0, sim)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def normalizar_termo_texto(termo: str) -> str:
    if not isinstance(termo, str):
        termo = str(termo)
    sem_parenteses = re.sub(r'\s*\([^)]*\)', '', termo)
    normalizado = unidecode.unidecode(sem_parenteses.lower().strip())
    normalizado = re.sub(r'[^\w\s]', '', normalizado)
    normalizado = re.sub(r'\s+', ' ', normalizado).strip()
    return normalizado


def expansion_of(expanded: str, abbr: str) -> bool:
    cleaned = re.sub(r'\s*\([^)]*\)', '', expanded)
    exp_norm = padronizar_string(cleaned)
    abbr_norm = padronizar_string(abbr)
    if len(abbr_norm) < 2 or len(abbr_norm) > 6:
        return False
    words = exp_norm.split()
    initials = ''.join(w[0] for w in words if w)
    return initials == abbr_norm


def fuzzy_partial_match(str1: str, str2: str, threshold: int = Config.FUZZY_THRESHOLD) -> bool:
    from rapidfuzz import fuzz
    s1 = padronizar_string(str1)
    s2 = padronizar_string(str2)
    if len(s1) < 3 or len(s2) < 3:
        return False
    if s1 in s2 or s2 in s1:
        return True
    tokens1 = [t for t in s1.split() if t]
    tokens2 = [t for t in s2.split() if t]
    if len(tokens1) <= 1 or len(tokens2) <= 1:
        return False
    overlap = set(tokens1).intersection(set(tokens2))
    if len(overlap) < 1:
        return False
    return fuzz.token_sort_ratio(s1, s2) >= threshold


def llm_semantic_match(term1: str, term2: str) -> bool:
    """Usa o modelo JUIZ para comparar semanticamente dois termos."""
    from prompts.semantic_match_user import USER_TEMPLATE
    from prompts.semantic_match_system import SYSTEM_PROMPT as SEMANTIC_SYSTEM
    user_prompt = USER_TEMPLATE.format(term1=term1, term2=term2)
    try:
        resp = ollama.chat(model=Config.JUDGE_MODEL,
                           messages=[{"role": "system", "content": SEMANTIC_SYSTEM},
                                     {"role": "user", "content": user_prompt}],
                           options={"temperature": 0})
        _save_llm_response(Config.JUDGE_MODEL, user_prompt, resp["message"]["content"], "semantic_match", f"{term1}_{term2}")
        return "SIM" in resp["message"]["content"].upper()
    except:
        return False


def verificar_expansao_llm(abrev: str, expandido: str, expansion_cache: dict, expansion_cache_file: str) -> int:
    """Usa o modelo JUIZ para verificar expansão de abreviação."""
    cache_key = f"{abrev}|{expandido}"
    if cache_key in expansion_cache:
        return expansion_cache[cache_key]
    from prompts.verificar_expansao_llm_user import USER_TEMPLATE
    from prompts.verificar_expansao_llm_system import SYSTEM_PROMPT as VERIFICAR_EXPANS_SYSTEM
    user_prompt = USER_TEMPLATE.format(abrev=abrev, expandido=expandido)
    try:
        resp = ollama.chat(model=Config.JUDGE_MODEL,
                           messages=[{"role": "system", "content": VERIFICAR_EXPANS_SYSTEM},
                                     {"role": "user", "content": user_prompt}],
                           options={"temperature": 0.0})
        _save_llm_response(Config.JUDGE_MODEL, user_prompt, resp["message"]["content"], "verify_expansion", f"{abrev}_{expandido}")
        resultado = resp["message"]["content"].strip()
        if resultado in ["1", "0"]:
            resposta = int(resultado)
        else:
            resposta = 0
    except:
        resposta = 0
    expansion_cache[cache_key] = resposta
    save_json_cache(expansion_cache, expansion_cache_file)
    return resposta


def resolver_conflito_expansao(abrev: str, expansoes_candidatas: list, expansion_cache: dict, expansion_cache_file: str) -> str:
    """Usa o modelo JUIZ para resolver conflito entre duas expansões."""
    cache_key = f"conflito_{abrev}|{expansoes_candidatas[0]}|{expansoes_candidatas[1]}"
    if cache_key in expansion_cache:
        idx = expansion_cache[cache_key]
        return expansoes_candidatas[idx]
    from prompts.resolver_conflito_expansao_user import USER_TEMPLATE
    from prompts.resolver_conflito_expansao_system import SYSTEM_PROMPT as RESOLVE_CONFLITO_EXP_SYSTEM
    user_prompt = USER_TEMPLATE.format(abrev=abrev, exp1=expansoes_candidatas[0], exp2=expansoes_candidatas[1])
    try:
        resp = ollama.chat(model=Config.JUDGE_MODEL,
                           messages=[{"role": "system", "content": RESOLVE_CONFLITO_EXP_SYSTEM},
                                     {"role": "user", "content": user_prompt}],
                           options={"temperature": 0.0})
        _save_llm_response(Config.JUDGE_MODEL, user_prompt, resp["message"]["content"], "resolve_expansion_conflict", abrev)
        escolha = resp["message"]["content"].strip()
        if escolha == "1":
            resultado = 0
        elif escolha == "2":
            resultado = 1
        else:
            resultado = 0
    except:
        resultado = 0
    expansion_cache[cache_key] = resultado
    save_json_cache(expansion_cache, expansion_cache_file)
    return expansoes_candidatas[resultado]


def validar_mapeamento_llm(termo_original: str, codigo: str, label_conceito: str,
                          validation_cache: dict, validation_cache_file: str,
                          contexto_adicional: str = "") -> int:
    """Usa o modelo JUIZ para validar mapeamento (sem repetições)."""
    cache_key = f"{termo_original}|{codigo}"
    if cache_key in validation_cache:
        return validation_cache[cache_key]
    from prompts.validar_mapeamento_llm_user import USER_TEMPLATE as VALIDAR_MAP_USER
    from prompts.validar_mapeamento_llm_system import SYSTEM_PROMPT as VALIDAR_MAP_SYSTEM
    user_prompt = VALIDAR_MAP_USER.format(termo_original=termo_original, label_conceito=label_conceito, codigo=codigo)
    if contexto_adicional:
        user_prompt = f"{user_prompt}\n\nContexto do termo no texto original: \"{contexto_adicional}\""
    try:
        resp = ollama.chat(model=Config.JUDGE_MODEL,
                           messages=[{"role": "system", "content": VALIDAR_MAP_SYSTEM},
                                     {"role": "user", "content": user_prompt}],
                           options={"temperature": 0.0})
        _save_llm_response(Config.JUDGE_MODEL, user_prompt, resp["message"]["content"], "validate_mapping", f"{termo_original}_{codigo}")
        resultado = resp["message"]["content"].strip().lower()
        if resultado in ["1", "sim", "verdadeiro", "true", "yes"]:
            final = 1
        else:
            final = 0
    except:
        final = 0

    log_decision(
        decision_type="mapping_validation",
        input_data={"termo_original": termo_original, "codigo": codigo, "label": label_conceito[:100]},
        output="1" if final == 1 else "0",
        reason="LLM_judge",
        cache_hit=(cache_key in validation_cache)
    )

    validation_cache[cache_key] = final
    save_json_cache(validation_cache, validation_cache_file)
    return final


def resolver_conflito_mapeamento(termo_original: str, codigo: str, label_conceito: str,
                                 validation_cache: dict, validation_cache_file: str) -> int:
    """Usa o modelo JUIZ para resolver conflito de mapeamento (sem repetições)."""
    cache_key = f"conflito_{termo_original}|{codigo}"
    if cache_key in validation_cache:
        return validation_cache[cache_key]
    from prompts.resolver_conflito_mapeamento_user import USER_TEMPLATE as RESOLVE_CONFLITO_MAP_USER
    from prompts.resolver_conflito_mapeamento_system import SYSTEM_PROMPT as RESOLVE_CONFLITO_MAP_SYSTEM
    user_prompt = RESOLVE_CONFLITO_MAP_USER.format(termo_original=termo_original, label_conceito=label_conceito, codigo=codigo)
    try:
        resp = ollama.chat(model=Config.JUDGE_MODEL,
                           messages=[{"role": "system", "content": RESOLVE_CONFLITO_MAP_SYSTEM},
                                     {"role": "user", "content": user_prompt}],
                           options={"temperature": 0.0})
        _save_llm_response(Config.JUDGE_MODEL, user_prompt, resp["message"]["content"], "resolve_mapping_conflict", f"{termo_original}_{codigo}")
        resultado = resp["message"]["content"].strip()
        final = 1 if resultado == "1" else 0
    except:
        final = 0
    validation_cache[cache_key] = final
    save_json_cache(validation_cache, validation_cache_file)
    return final


def salvar_annotations_json(annotations: list, narrative_name: str, output_dir: str) -> None:
    json_path = os.path.join(output_dir, f"annotations_{narrative_name}.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)


def log_decision(decision_type: str, input_data: dict, output: str, confidence: float = None,
                 reason: str = None, cache_hit: bool = False):
    """Registra decisoes do LLM de forma estruturada para auditoria."""
    log_dir = os.path.join(Config.LOGS_FOLDER, "decisions")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{timestamp}_{decision_type}.json"
    filepath = os.path.join(log_dir, filename)

    log_entry = {
        "timestamp": timestamp,
        "decision_type": decision_type,
        "cache_hit": cache_hit,
        "input": input_data,
        "output": output,
        "confidence": confidence,
        "reason": reason
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(log_entry, f, indent=2, ensure_ascii=False)


def get_snomed_semantic_type(code: str) -> str:
    """
    Obtém o tipo semântico de um código SNOMED CT via BioPortal.
    Retorna uma string como 'Disorder', 'Finding', 'Substance', etc.
    """
    url = f"http://data.bioontology.org/ontologies/SNOMEDCT/classes/{code}"
    headers = {"Authorization": f"apikey token={Config.BIOPORTAL_API_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json()
            semantic_type = data.get("semanticType")
            if not semantic_type:
                types = data.get("types", [])
                if types and isinstance(types, list):
                    semantic_type = types[0].get("name", "")
            return semantic_type if semantic_type else ""
    except Exception as e:
        print(f"Erro ao buscar tipo semântico para {code}: {e}")
    return ""


def normalizar_para_match(termo: str) -> str:
    if not isinstance(termo, str):
        termo = str(termo)
    return normalizar_termo_texto(termo)
