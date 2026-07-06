# 01_extract_terms.py
import sys
import os
import re
import json
import time
import atexit
import pandas as pd
import xml.etree.ElementTree as ET
import ollama
from utils import log_decision
from utils import load_abreviacoes
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config
from utils import (
    padronizar_string, normalizar_termo_texto, load_json_cache, save_json_cache,
    verificar_expansao_hibrida, resolver_conflito_expansao, salvar_annotations_json, Tee,
    _save_llm_response, query_snomed, query_snomed_by_code, load_abreviacoes
)
from prompts.pesquisa_clin_llama_system import SYSTEM_PROMPT as EXTRACTION_SYSTEM_PROMPT

NORM_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.NORM_CACHE_FILE))
EXPANSION_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.EXPANSION_CACHE_FILE))
API_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE))
ABREVIACOES_CACHE = load_abreviacoes(os.path.join(Config.DICIONARIOS_FOLDER, Config.ABREVIACOES_FILE))

def extrair_annotations_validas(resposta_json: str, texto_original: str, narrative_name: str) -> list:
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
        polaridade = ent.get('polarity', 'Positiva').strip().capitalize()
        if polaridade not in ('Positiva', 'Negativa'):
            polaridade = 'Positiva'
        abbreviation = ent.get('abbreviation', False)
        original = ent.get('original', texto if abbreviation else None)
        if original and (len(original) > 6 or ' ' in original):
            abbreviation = False
            original = None
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

def extrair_entidades_via_regex(raw_text: str) -> str:
    pattern = r'"text":\s*"([^"]+)"\s*,\s*"original":\s*"([^"]+)"\s*,\s*"polarity":\s*"([^"]+)"\s*,\s*"abbreviation":\s*(true|false)\s*,\s*"category":\s*"([^"]+)"'
    matches = re.findall(pattern, raw_text, re.DOTALL)
    entities = []
    for match in matches:
        entities.append({
            "text": match[0],
            "original": match[1],
            "polarity": match[2],
            "abbreviation": match[3].lower() == "true",
            "category": match[4]
        })
    return json.dumps({"entities": entities}, ensure_ascii=False)

def PesquisaClin_Llama(textoClinico: str) -> str:
    if Config.ENABLE_AGGRESSIVE_EXTRACTION:
        user_prompt = f"""Texto clínico (extraia ABSOLUTAMENTE TODOS os termos clínicos relevantes, incluindo doenças, sintomas, exames, medicamentos, procedimentos, achados físicos, resultados laboratoriais, mesmo que pareçam pouco relevantes ou estejam em negação complexa):

{textoClinico}

JSON:"""
    else:
        user_prompt = f"Texto clínico:\n{textoClinico}\n\nJSON:"
    try:
        response = ollama.chat(
            model=Config.OLLAMA_MODEL,
            messages=[{'role': 'system', 'content': EXTRACTION_SYSTEM_PROMPT},
                      {'role': 'user', 'content': user_prompt}],
            options={'temperature': 0.2, 'top_p': Config.TOP_P, 'num_predict': Config.MAX_TOKENS, 'repeat_penalty': Config.REPEAT_PENALTY}
        )
        raw_text = response['message']['content'].strip()
        _save_llm_response(Config.OLLAMA_MODEL, user_prompt, raw_text, "extraction", "main")
        json_match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
        if json_match:
            raw_text = json_match.group(1)
        else:
            json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if json_match:
                raw_text = json_match.group(0)
            else:
                return extrair_entidades_via_regex(raw_text)
        try:
            json.loads(raw_text)
            return raw_text
        except json.JSONDecodeError:
            if raw_text.strip().startswith('{"entities": ['):
                repaired = raw_text.strip()
                if not repaired.endswith(']'):
                    repaired += ']'
                if not repaired.endswith('}'):
                    repaired += '}'
                try:
                    json.loads(repaired)
                    return repaired
                except:
                    pass
            return extrair_entidades_via_regex(raw_text)
    except Exception as e:
        print(f"\n\nErro na chamada LLM: {e}")
        return '{"entities": []}'

def consolidar_annotations(lista_de_listas: list, narrative_name: str, texto_original: str) -> list:
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
                    
                    contexto = extrair_contexto_para_termo(pd.DataFrame([ann, existing]), ann["abreviacao_original"])
                    
                    melhor_exp = resolver_conflito_expansao(
                        ann["abreviacao_original"],
                        [existing["textoAnalisado"], ann["textoAnalisado"]],
                        EXPANSION_CACHE,
                        os.path.join(Config.DICIONARIOS_FOLDER, Config.EXPANSION_CACHE_FILE),
                        contexto
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

def extrair_contexto_para_termo(df: pd.DataFrame, termo: str) -> str:
    rows = df[df["textoAnalisado"] == termo]
    if rows.empty:
        return ""
    texto_prompt = rows.iloc[0].get("textoPrompt", "")
    if not texto_prompt:
        return ""
    termo_norm = termo.lower()
    texto_lower = texto_prompt.lower()
    idx = texto_lower.find(termo_norm)
    if idx == -1:
        return texto_prompt[:400] + "..." if len(texto_prompt) > 400 else texto_prompt
    start = max(0, idx - 150)
    end = min(len(texto_prompt), idx + len(termo) + 150)
    snippet = texto_prompt[start:end].replace("\n", " ")
    if start > 0:
        snippet = "..." + snippet
    if end < len(texto_prompt):
        snippet = snippet + "..."
    return snippet.strip()

def processar_narrativa_completa(nome_narrativa: str):
    caminho_narrativa = os.path.join(Config.NARRATIVES_FOLDER, nome_narrativa)
    narrative_base = os.path.splitext(nome_narrativa)[0]
    narrative_output_dir = os.path.join(Config.CSV_INDIVIDUAL_FOLDER, narrative_base)
    output_csv_individual = os.path.join(narrative_output_dir, "extracted_terms.csv")
    if os.path.exists(output_csv_individual):
        df_existente = pd.read_csv(output_csv_individual)
        if not df_existente.empty and 'erro' not in df_existente.columns and 'SCTID' in df_existente.columns:
            print(f"\n\nArquivo {output_csv_individual} já existe com mapeamento. Pulando {nome_narrativa}.")
            return df_existente
    os.makedirs(narrative_output_dir, exist_ok=True)
    try:
        tree = ET.parse(caminho_narrativa)
        root = tree.getroot()
        text_element = root.find('.//TEXT')
        if text_element is None:
            print(f"\n\nElemento TEXT não encontrado em {nome_narrativa}. Pulando.")
            return None
        xml_text = text_element.text or ""
        xml_text = re.sub(r'\s+', ' ', xml_text).strip()
    except Exception as e:
        print(f"\n\nErro ao ler XML {nome_narrativa}: {e}")
        return None
    print(f"Extraindo termos de {nome_narrativa}")
    resposta_json = PesquisaClin_Llama(xml_text)
    log_dir = os.path.join(Config.LOGS_FOLDER, narrative_base)
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"llm_response_{narrative_base}.json")
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(resposta_json)
    annotations_validas = extrair_annotations_validas(resposta_json, xml_text, nome_narrativa)
    if not annotations_validas:
        print(f"\nNenhum termo válido extraído para {nome_narrativa}.")
        empty_df = pd.DataFrame([{"nomeNarrativa": nome_narrativa, "erro": "Nenhuma anotação válida"}])
        empty_df.to_csv(output_csv_individual, index=False, encoding='utf-8')
        return None
    annotations_consolidadas = consolidar_annotations([annotations_validas], nome_narrativa, xml_text)
    if not annotations_consolidadas:
        empty_df = pd.DataFrame([{"nomeNarrativa": nome_narrativa, "erro": "Nenhuma anotação válida após consolidação"}])
        empty_df.to_csv(output_csv_individual, index=False, encoding='utf-8')
        return None
    df = criar_dataframe_da_lista(annotations_consolidadas, nome_narrativa, xml_text, output_csv_individual)
    if df is None or df.empty:
        print(f"\n\nDataFrame vazio para {nome_narrativa}.")
        return None
    salvar_annotations_json(annotations_consolidadas, narrative_base, narrative_output_dir)

    print(f"Processado {nome_narrativa} -> {len(df)} termos únicos. Validando expansões...\n")
    api_cache = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE))
    expansion_cache = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.EXPANSION_CACHE_FILE))
    for idx, row in df.iterrows():
        if row['abreviacao'] and pd.notna(row['abreviacao_original']):
            abrev = row['abreviacao_original']
            expandido = row['textoAnalisado']
            if len(abrev) <= 6 and ' ' not in abrev:
                print(f"\n[DEBUG] Validando expansão híbrida para '{abrev}' -> '{expandido}'")
                
                contexto = extrair_contexto_para_termo(df, expandido)
                
                correto = verificar_expansao_hibrida(
                    abrev, expandido, expansion_cache,
                    os.path.join(Config.DICIONARIOS_FOLDER, Config.EXPANSION_CACHE_FILE),
                    api_cache,
                    os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE),
                    ABREVIACOES_CACHE,
                    contexto
                )
                df.at[idx, 'expansao_correta'] = correto
                print(f"[DEBUG] Resultado validação híbrida: {correto}")
            else:
                print(f"[DEBUG] Ignorando validação para '{abrev}' - não parece ser uma abreviação (len={len(abrev)})")
                df.at[idx, 'expansao_correta'] = None
        else:
            df.at[idx, 'expansao_correta'] = None
    df.to_csv(output_csv_individual, index=False, encoding='utf-8')
    return df

def main() -> None:
    os.makedirs(Config.LOGS_FOLDER, exist_ok=True)
    log_file = open(os.path.join(Config.LOGS_FOLDER, "log_execucao.txt"), "w", encoding="utf-8")
    original_stdout = sys.stdout
    sys.stdout = Tee(sys.stdout, log_file)
    def cleanup_logging():
        nonlocal log_file, original_stdout
        if sys.stdout is not original_stdout:
            sys.stdout = original_stdout
        if log_file and not log_file.closed:
            log_file.close()
    atexit.register(cleanup_logging)
    os.makedirs(Config.CSV_INDIVIDUAL_FOLDER, exist_ok=True)
    os.makedirs(Config.LOGS_FOLDER, exist_ok=True)
    os.makedirs(Config.DICIONARIOS_FOLDER, exist_ok=True)
    arquivos_xml = []
    for root, _, files in os.walk(Config.NARRATIVES_FOLDER):
        for f in files:
            if not f.endswith('.xml'):
                continue
            if f.endswith('_goldstandard.xml'):
                continue
            arquivos_xml.append(f)
    lista_dataframes = []
    for nome in arquivos_xml:
        df = processar_narrativa_completa(nome)
        if df is not None and not df.empty:
            lista_dataframes.append(df)
        time.sleep(1)
    if lista_dataframes:
        df_mestre = pd.concat(lista_dataframes, ignore_index=True)
        df_mestre.to_csv(os.path.join(Config.CSV_INDIVIDUAL_FOLDER, "all_extracted_terms.csv"), index=False, encoding='utf-8')
    else:
        print("\nNenhum termo extraído.")

if __name__ == "__main__":
    main()