"""Extrai termos clínicos de narrativas usando LLM, com validação de FP, expansão de abreviações, resolução de conflitos e geração de logs."""

import sys
import os
import re
import json
import time
import atexit
import concurrent.futures
import pandas as pd
import xml.etree.ElementTree as ET
import ollama

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config
from utils import (
    padronizar_string, normalizar_termo_texto, load_json_cache, save_json_cache,
    verificar_expansao_llm, resolver_conflito_expansao, salvar_annotations_json, Tee
)
from prompts.pesquisa_clin_llama_system import SYSTEM_PROMPT as EXTRACTION_SYSTEM_PROMPT

FP_VALIDATION_CACHE = {}
NORM_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.NORM_CACHE_FILE))
FP_CACHE_FILE = os.path.join(Config.DICIONARIOS_FOLDER, Config.FP_VALIDATION_CACHE_FILE)
FP_VALIDATION_CACHE.update(load_json_cache(FP_CACHE_FILE))
EXPANSION_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.EXPANSION_CACHE_FILE))
NOISE_LOG_GLOBAL = []

def is_valid_clinical_term_llm(term: str, contexto: str = None) -> bool:
    """Usa LLM para decidir se um termo é uma entidade clínica válida (evita FPs)."""
    cache_key = f"valid_{term}"
    if cache_key in FP_VALIDATION_CACHE:
        return FP_VALIDATION_CACHE[cache_key]
    if len(term) > 5 and not term.isupper() and not any(w in term.lower() for w in ['apresenta', 'refere', 'nega', 'paciente']):
        FP_VALIDATION_CACHE[cache_key] = True
        save_json_cache(FP_VALIDATION_CACHE, FP_CACHE_FILE)
        return True
    snippet = ""
    if contexto:
        ctx_norm = padronizar_string(contexto)
        t_norm = padronizar_string(term)
        if t_norm and t_norm in ctx_norm:
            idx = ctx_norm.find(t_norm)
            start = max(0, idx - 100)
            end = min(len(ctx_norm), idx + len(t_norm) + 100)
            snippet = f" no contexto: {ctx_norm[start:end]}"
    from prompts.validar_termo_clinico_user import USER_TEMPLATE as VALIDAR_TERMO_USER
    user_prompt = VALIDAR_TERMO_USER.format(term=term, contexto=snippet)
    try:
        resp = ollama.chat(model=Config.OLLAMA_MODEL,
                           messages=[{"role": "user", "content": user_prompt}],
                           options={"temperature": 0})
        result = "SIM" in resp["message"]["content"].upper()
    except:
        result = True
    FP_VALIDATION_CACHE[cache_key] = result
    save_json_cache(FP_VALIDATION_CACHE, FP_CACHE_FILE)
    return result

def extrair_annotations_validas(resposta_json: str, texto_original: str, narrative_name: str) -> list:
    """Extrai entidades do JSON do LLM, valida substring e aplica filtro de FP."""
    def parse_response(text):
        try:
            return json.loads(text)
        except:
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*$', '', text)
            matches = re.findall(r'\{.*?\}', text, re.DOTALL)
            for match in matches:
                try:
                    return json.loads(match)
                except:
                    continue
            return None
    data = parse_response(resposta_json)
    if not data:
        return []
    entities = data.get('entities', [])
    if not entities and isinstance(data, list):
        entities = data
    if not entities:
        return []
    validas = []
    texto_norm = padronizar_string(texto_original)
    for ent in entities:
        texto = (ent.get('text') or ent.get('term') or '').strip()
        if not texto:
            continue
        original_excerpt = ent.get('original', texto)
        excerpt_norm = padronizar_string(original_excerpt)
        if excerpt_norm and excerpt_norm not in texto_norm:
            continue
        if not is_valid_clinical_term_llm(texto, contexto=texto_original):
            NOISE_LOG_GLOBAL.append(f'{narrative_name}|{texto}|fp_llm_rejected')
            continue
        polaridade = ent.get('polarity', 'Positiva').strip().capitalize()
        if polaridade not in ('Positiva', 'Negativa'):
            polaridade = 'Positiva'
        abbreviation = ent.get('abbreviation', False)
        original = ent.get('original', texto if abbreviation else None)
        categoria = ent.get('category', 'Problema')
        if categoria not in ('Problema', 'Teste', 'Tratamento'):
            categoria = 'Problema'
        validas.append({
            "textoAnalisado": texto,
            "categoria": categoria,
            "abreviacao": abbreviation,
            "abreviacao_original": original if abbreviation else None,
            "polaridade": polaridade
        })
    return validas

def PesquisaClin_Llama(textoClinico: str, attempt: int = 1, extra: bool = False) -> str:
    """Envia prompt para o LLM e retorna a resposta JSON com entidades."""
    if extra:
        user_prompt = f"Tentativa especial. Extraia ABSOLUTAMENTE TODOS os termos clínicos. Retorne APENAS JSON. Texto: {textoClinico}\n\nJSON:"
    else:
        user_prompt = f"Texto clínico (tentativa {attempt}):\n{textoClinico}\n\nJSON:"
    try:
        response = ollama.chat(
            model=Config.OLLAMA_MODEL,
            messages=[{'role': 'system', 'content': EXTRACTION_SYSTEM_PROMPT},
                      {'role': 'user', 'content': user_prompt}],
            options={'temperature': 0.2, 'top_p': Config.TOP_P, 'num_predict': Config.MAX_TOKENS, 'repeat_penalty': Config.REPEAT_PENALTY}
        )
        raw_text = response['message']['content'].strip()
        json_match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                raw_text = json_match.group(0)
            else:
                raw_text = '{"entities": []}'
        try:
            json.loads(raw_text)
            return raw_text
        except:
            return '{"entities": []}'
    except Exception as e:
        print(f"Erro na chamada LLM: {e}")
        return '{"entities": []}'

def consolidar_annotations(lista_de_listas: list, narrative_name: str, texto_original: str) -> list:
    """Consolida múltiplas tentativas, resolvendo conflitos de expansão e removendo duplicatas."""
    melhores = {}
    for ann_list in lista_de_listas:
        for ann in ann_list:
            texto_norm = normalizar_termo_texto(ann["textoAnalisado"])
            polaridade = ann.get("polaridade", "Positiva")
            key = (texto_norm, polaridade)
            if key not in melhores:
                melhores[key] = ann.copy()
            else:
                existing = melhores[key]
                if len(ann["textoAnalisado"]) > len(existing["textoAnalisado"]):
                    melhores[key] = ann.copy()
                if (ann["abreviacao"] and existing["abreviacao"] and
                    ann["abreviacao_original"] == existing["abreviacao_original"] and
                    normalizar_termo_texto(ann["textoAnalisado"]) != normalizar_termo_texto(existing["textoAnalisado"])):
                    melhor_exp = resolver_conflito_expansao(
                        ann["abreviacao_original"],
                        [existing["textoAnalisado"], ann["textoAnalisado"]],
                        EXPANSION_CACHE,
                        os.path.join(Config.DICIONARIOS_FOLDER, Config.EXPANSION_CACHE_FILE)
                    )
                    if melhor_exp:
                        melhores[key]["textoAnalisado"] = melhor_exp
    lista_entidades = list(melhores.values())
    lista_entidades.sort(key=lambda x: len(x["textoAnalisado"].split()), reverse=True)
    filtered = []
    for i, ent in enumerate(lista_entidades):
        keep = True
        ent_norm = normalizar_termo_texto(ent["textoAnalisado"])
        for j, other in enumerate(lista_entidades):
            if i == j:
                continue
            other_norm = normalizar_termo_texto(other["textoAnalisado"])
            if ent_norm in other_norm and len(other["textoAnalisado"].split()) > len(ent["textoAnalisado"].split()):
                keep = False
                break
        if keep:
            filtered.append(ent)
    return filtered

def criar_dataframe_da_lista(annotations_consolidadas: list, narrative_name: str, texto_original: str, csv_filename: str):
    """Cria DataFrame a partir das anotações consolidadas e salva CSV individual."""
    if not annotations_consolidadas:
        empty_df = pd.DataFrame([{"nomeNarrativa": narrative_name, "erro": "Nenhuma anotação válida"}])
        empty_df.to_csv(csv_filename, index=False, encoding='utf-8')
        return None
    dados_extraidos = []
    for ann in annotations_consolidadas:
        dados_extraidos.append({
            "nomeNarrativa": narrative_name,
            "textoPrompt": texto_original,
            "categoria": ann["categoria"],
            "textoAnalisado": ann["textoAnalisado"],
            "abreviacao": ann["abreviacao"],
            "abreviacao_original": ann["abreviacao_original"] if ann["abreviacao"] else None,
            "polaridade": ann.get("polaridade", "Positiva")
        })
    df = pd.DataFrame(dados_extraidos)
    df = df[["nomeNarrativa", "textoPrompt", "categoria", "textoAnalisado", "abreviacao", "abreviacao_original", "polaridade"]]
    os.makedirs(os.path.dirname(csv_filename), exist_ok=True)
    df.to_csv(csv_filename, index=False, encoding='utf-8')
    return df

def processar_narrativa_completa(nome_narrativa: str):
    """Processa uma única narrativa: extrai termos, expande abreviações, valida expansões e salva CSV e JSON."""
    caminho_narrativa = os.path.join(Config.NARRATIVES_FOLDER, nome_narrativa)
    narrative_base = os.path.splitext(nome_narrativa)[0]
    narrative_output_dir = os.path.join(Config.CSV_INDIVIDUAL_FOLDER, narrative_base)
    output_csv_individual = os.path.join(narrative_output_dir, "extracted_terms.csv")
    if os.path.exists(output_csv_individual):
        df_existente = pd.read_csv(output_csv_individual)
        if not df_existente.empty and 'erro' not in df_existente.columns and 'SCTID' in df_existente.columns:
            print(f"Arquivo {output_csv_individual} já existe com mapeamento. Pulando {nome_narrativa}.")
            return df_existente
    os.makedirs(narrative_output_dir, exist_ok=True)
    try:
        tree = ET.parse(caminho_narrativa)
        root = tree.getroot()
        text_element = root.find('.//TEXT')
        if text_element is None:
            print(f"Elemento TEXT não encontrado em {nome_narrativa}. Pulando.")
            return None
        xml_text = text_element.text or ""
        xml_text = re.sub(r'\s+', ' ', xml_text).strip()
    except Exception as e:
        print(f"Erro ao ler XML {nome_narrativa}: {e}")
        return None
    todas_annotations_attempts = []
    sucesso_parcial = False
    for attempt in range(1, Config.RETRIES + 1):
        try:
            print(f"\nIniciando tentativa {attempt} para {nome_narrativa}")
            resposta_json = PesquisaClin_Llama(xml_text, attempt=attempt, extra=False)
            log_dir = os.path.join(Config.LOGS_FOLDER, narrative_base)
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f"llm_response_{narrative_base}_attempt{attempt}.json")
            with open(log_path, 'w', encoding='utf-8') as f:
                f.write(resposta_json)
            annotations_validas = extrair_annotations_validas(resposta_json, xml_text, nome_narrativa)
            if annotations_validas:
                todas_annotations_attempts.append(annotations_validas)
                sucesso_parcial = True
                print(f"Tentativa {attempt} gerou {len(annotations_validas)} termos válidos.")
            else:
                print(f"Tentativa {attempt} não gerou termos válidos.")
        except Exception as e:
            print(f"Erro na tentativa {attempt}: {e}")
        time.sleep(2)
    if not sucesso_parcial:
        print(f"Nenhuma tentativa gerou termos para {nome_narrativa}. Tentativas extras.")
        for extra_attempt in range(1, Config.EXTRA_RETRIES + 1):
            try:
                resposta_json = PesquisaClin_Llama(xml_text, attempt=extra_attempt, extra=True)
                annotations_validas = extrair_annotations_validas(resposta_json, xml_text, nome_narrativa)
                if annotations_validas:
                    todas_annotations_attempts.append(annotations_validas)
                    sucesso_parcial = True
                    print(f"Tentativa extra {extra_attempt} gerou {len(annotations_validas)} termos válidos.")
                    break
                else:
                    print(f"Tentativa extra {extra_attempt} não gerou termos.")
            except Exception as e:
                print(f"Erro na tentativa extra {extra_attempt}: {e}")
            time.sleep(2)
    if not sucesso_parcial:
        empty_df = pd.DataFrame([{"nomeNarrativa": nome_narrativa, "erro": "Nenhuma anotação mesmo após tentativas extras"}])
        empty_df.to_csv(output_csv_individual, index=False, encoding='utf-8')
        return None
    annotations_consolidadas = []
    if todas_annotations_attempts:
        melhor_attempt = max(todas_annotations_attempts, key=len)
        annotations_consolidadas = consolidar_annotations([melhor_attempt], nome_narrativa, xml_text)
    if not annotations_consolidadas:
        empty_df = pd.DataFrame([{"nomeNarrativa": nome_narrativa, "erro": "Nenhuma anotação válida após consolidação"}])
        empty_df.to_csv(output_csv_individual, index=False, encoding='utf-8')
        return None
    df = criar_dataframe_da_lista(annotations_consolidadas, nome_narrativa, xml_text, output_csv_individual)
    if df is None or df.empty:
        print(f"DataFrame vazio para {nome_narrativa}.")
        return None
    salvar_annotations_json(annotations_consolidadas, narrative_base, narrative_output_dir)
    print(f"Processado {nome_narrativa} -> {len(df)} termos únicos. Validando expansões...")
    for idx, row in df.iterrows():
        if row['abreviacao'] and pd.notna(row['abreviacao_original']):
            abrev = row['abreviacao_original']
            expandido = row['textoAnalisado']
            correto = verificar_expansao_llm(abrev, expandido, EXPANSION_CACHE,
                                             os.path.join(Config.DICIONARIOS_FOLDER, Config.EXPANSION_CACHE_FILE))
            df.at[idx, 'expansao_correta'] = correto
        else:
            df.at[idx, 'expansao_correta'] = None
    return df

def get_optimal_workers() -> int:
    """Determina o número ideal de workers para processamento paralelo."""
    cpu_count = os.cpu_count() or 2
    return min(cpu_count, 4) if Config.MAX_WORKERS is None else Config.MAX_WORKERS

def main() -> None:
    """Executa a extração paralela de termos para todos os arquivos XML da pasta narrativas."""
    log_file = open(os.path.join(Config.LOGS_FOLDER, "log_execucao.txt"), "w", encoding="utf-8")
    original_stdout = sys.stdout
    sys.stdout = Tee(sys.stdout, log_file)

    def cleanup_logging():
        global log_file
        if sys.stdout is not original_stdout:
            sys.stdout = original_stdout
        if log_file and not log_file.closed:
            log_file.close()
    atexit.register(cleanup_logging)

    os.makedirs(Config.CSV_INDIVIDUAL_FOLDER, exist_ok=True)
    os.makedirs(Config.LOGS_FOLDER, exist_ok=True)
    os.makedirs(Config.DICIONARIOS_FOLDER, exist_ok=True)
    arquivos_xml = [f for f in os.listdir(Config.NARRATIVES_FOLDER) if f.endswith('.xml') and not f.endswith('_goldstandard.xml')]
    max_workers = get_optimal_workers()
    print(f"Iniciando extração paralela com até {max_workers} threads.")
    lista_dataframes = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_narrative = {executor.submit(processar_narrativa_completa, nome): nome for nome in arquivos_xml}
        for future in concurrent.futures.as_completed(future_to_narrative):
            nome = future_to_narrative[future]
            try:
                df = future.result()
                if df is not None and not df.empty:
                    lista_dataframes.append(df)
            except Exception as e:
                print(f"Erro ao processar {nome}: {e}")
    if lista_dataframes:
        df_mestre = pd.concat(lista_dataframes, ignore_index=True)
        df_mestre.to_csv(os.path.join(Config.CSV_INDIVIDUAL_FOLDER, "all_extracted_terms.csv"), index=False, encoding='utf-8')
        print("Extração concluída.")
    else:
        print("Nenhum termo extraído.")
    if NOISE_LOG_GLOBAL:
        noise_log_path = os.path.join(Config.LOGS_FOLDER, "filtered_terms_log.txt")
        with open(noise_log_path, 'w', encoding='utf-8') as f:
            for entry in NOISE_LOG_GLOBAL:
                f.write(entry + "\n")
        print(f"Log de termos filtrados salvo em {noise_log_path}")

if __name__ == "__main__":
    main()