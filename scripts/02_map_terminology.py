"""Adiciona códigos SNOMED CT e CID-11 aos termos extraídos, usando APIs e validação por LLM."""

import sys
import os
import time
import json
import pandas as pd
import ollama
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config
from utils import (
    normalize_term, query_snomed, query_icd11, rank_results, get_label_snomed, get_label_cid11,
    load_json_cache, save_json_cache, validar_mapeamento_llm, resolver_conflito_mapeamento
)

API_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE))
VALIDATION_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.VALIDATION_CACHE_FILE))
NORM_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.NORM_CACHE_FILE))

def mapear_termo_api(termo):
    termo_norm = normalize_term(termo, NORM_CACHE, os.path.join(Config.DICIONARIOS_FOLDER, Config.NORM_CACHE_FILE))
    if termo_norm in API_CACHE:
        return API_CACHE[termo_norm]
    snomed_res = query_snomed(termo_norm, API_CACHE, os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE))
    icd_res = query_icd11(termo_norm, API_CACHE, os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE))
    best_snomed = None
    best_icd = None
    snomed_correto = 0
    cid_correto = 0
    if snomed_res:
        ranked_snomed = rank_results(snomed_res, termo_norm, is_snomed=True)
        for i in range(min(3, len(ranked_snomed))):
            cand = ranked_snomed[i][0]
            label = cand.get("label", "")
            codigo = cand.get("code", "")
            if not label or not codigo:
                continue
            label_detalhado = get_label_snomed(codigo) or label
            if validar_mapeamento_llm(termo_norm, codigo, label_detalhado,
                                      VALIDATION_CACHE,
                                      os.path.join(Config.DICIONARIOS_FOLDER, Config.VALIDATION_CACHE_FILE)) == 1:
                best_snomed = cand
                snomed_correto = 1
                break
        if best_snomed is None and ranked_snomed:
            best_snomed = ranked_snomed[0][0]
    if icd_res:
        ranked_icd = rank_results(icd_res, termo_norm, is_snomed=False)
        for i in range(min(3, len(ranked_icd))):
            cand = ranked_icd[i][0]
            title = cand.get("title", "")
            codigo = cand.get("code", "")
            if not title or not codigo:
                continue
            title_detalhado = get_label_cid11(codigo) or title
            if validar_mapeamento_llm(termo_norm, codigo, title_detalhado,
                                      VALIDATION_CACHE,
                                      os.path.join(Config.DICIONARIOS_FOLDER, Config.VALIDATION_CACHE_FILE)) == 1:
                best_icd = cand
                cid_correto = 1
                break
        if best_icd is None and ranked_icd:
            best_icd = ranked_icd[0][0]
    resultado = {
        "SCTID": best_snomed["code"] if best_snomed else None,
        "CID10": best_icd["code"] if best_icd else None,
        "SCTID_correto": snomed_correto,
        "CID10_correto": cid_correto
    }
    API_CACHE[termo_norm] = resultado
    save_json_cache(API_CACHE, os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE))
    return resultado

def main():
    csv_individual_dir = Config.CSV_INDIVIDUAL_FOLDER
    if not os.path.exists(csv_individual_dir):
        print("Pasta de CSVs individuais não encontrada. Execute 01_extract_terms.py primeiro.")
        return
    narrativas = [d for d in os.listdir(csv_individual_dir) if os.path.isdir(os.path.join(csv_individual_dir, d))]
    for narrative_base in narrativas:
        csv_path = os.path.join(csv_individual_dir, narrative_base, "extracted_terms.csv")
        if not os.path.exists(csv_path):
            continue
        df = pd.read_csv(csv_path)
        if 'SCTID' in df.columns and df['SCTID'].notna().any():
            print(f"Arquivo {csv_path} já mapeado. Pulando.")
            continue
        termos_unicos = df["textoAnalisado"].dropna().unique()
        mapa_global = {}
        for termo in termos_unicos:
            termo_str = str(termo).strip()
            if termo_str:
                mapa_global[termo_str] = mapear_termo_api(termo_str)
        df["SCTID"] = df["textoAnalisado"].map(lambda x: mapa_global.get(str(x).strip(), {}).get("SCTID") if pd.notna(x) else None)
        df["CID10"] = df["textoAnalisado"].map(lambda x: mapa_global.get(str(x).strip(), {}).get("CID10") if pd.notna(x) else None)
        df["SCTID_correto"] = df["textoAnalisado"].map(lambda x: mapa_global.get(str(x).strip(), {}).get("SCTID_correto") if pd.notna(x) else None)
        df["CID10_correto"] = df["textoAnalisado"].map(lambda x: mapa_global.get(str(x).strip(), {}).get("CID10_correto") if pd.notna(x) else None)
        df.to_csv(csv_path, index=False, encoding='utf-8')
        print(f"Mapeamento concluído para {narrative_base}")
    print("Todos os CSVs foram atualizados com códigos.")

if __name__ == "__main__":
    main()