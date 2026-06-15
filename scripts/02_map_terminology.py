"""Adiciona códigos SNOMED CT e CID-11 aos termos extraídos, usando APIs e validação por LLM (modelo juiz). Sem repetições."""

import sys
import os
import pandas as pd
import ollama

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config import Config
from utils import (
    normalize_term,
    query_snomed,
    query_icd11,
    rank_results,
    get_label_snomed,
    get_label_cid11,
    load_json_cache,
    save_json_cache,
    validar_mapeamento_llm,
    resolver_conflito_mapeamento,
)

API_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE))
VALIDATION_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.VALIDATION_CACHE_FILE))
NORM_CACHE = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.NORM_CACHE_FILE))


def extrair_contexto_para_termo(df: pd.DataFrame, termo: str) -> str:
    """Extrai o contexto original de onde o termo foi extraído."""
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
        return texto_prompt[:200]
    start = max(0, idx - 80)
    end = min(len(texto_prompt), idx + len(termo) + 80)
    return texto_prompt[start:end].replace("\n", " ").strip()


def mapear_termo_api(termo: str, df: pd.DataFrame = None) -> dict:
    termo_norm = normalize_term(
        termo, NORM_CACHE, os.path.join(Config.DICIONARIOS_FOLDER, Config.NORM_CACHE_FILE)
    )

    if termo_norm in API_CACHE:
        cached = API_CACHE[termo_norm]
        if cached.get("CID11") is not None:
            return cached

    contexto = ""
    if df is not None:
        contexto = extrair_contexto_para_termo(df, termo)

    snomed_res = query_snomed(
        termo_norm,
        API_CACHE,
        os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE),
    )
    icd_res = query_icd11(
        termo_norm,
        API_CACHE,
        os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE),
        force_refresh=(termo_norm in API_CACHE and API_CACHE[termo_norm].get("CID11") is None)
    )

    best_snomed = None
    best_icd = None
    snomed_correto = 0
    cid_correto = 0

    if snomed_res:
        ranked_snomed = rank_results(snomed_res, termo_norm, is_snomed=True)
        if ranked_snomed:
            cand = ranked_snomed[0][0]
            label = cand.get("label", "")
            codigo = cand.get("code", "")
            if label and codigo:
                label_detalhado = get_label_snomed(codigo) or label
                if validar_mapeamento_llm(
                    termo_norm,
                    codigo,
                    label_detalhado,
                    VALIDATION_CACHE,
                    os.path.join(
                        Config.DICIONARIOS_FOLDER,
                        Config.VALIDATION_CACHE_FILE,
                    ),
                    contexto_adicional=contexto
                ) == 1:
                    best_snomed = cand
                    snomed_correto = 1
                else:
                    best_snomed = cand
            else:
                best_snomed = cand

    if icd_res:
        ranked_icd = rank_results(icd_res, termo_norm, is_snomed=False)
        if ranked_icd:
            cand = ranked_icd[0][0]
            title = cand.get("title", "")
            codigo = cand.get("code", "")
            if codigo:
                title_detalhado = get_label_cid11(codigo) or title or ""
                if validar_mapeamento_llm(
                    termo_norm,
                    codigo,
                    title_detalhado,
                    VALIDATION_CACHE,
                    os.path.join(
                        Config.DICIONARIOS_FOLDER,
                        Config.VALIDATION_CACHE_FILE,
                    ),
                    contexto_adicional=contexto
                ) == 1:
                    best_icd = cand
                    cid_correto = 1
                else:
                    best_icd = cand
            else:
                best_icd = cand

    resultado = {
        "SCTID": best_snomed["code"] if best_snomed else None,
        "CID11": best_icd["code"] if best_icd else None,
        "SCTID_correto": snomed_correto,
        "CID11_correto": cid_correto,
    }

    API_CACHE[termo_norm] = resultado
    save_json_cache(API_CACHE, os.path.join(Config.DICIONARIOS_FOLDER, Config.CACHE_FILE))
    return resultado


def _mapear_csv(path_csv: str) -> None:
    df = pd.read_csv(path_csv)

    if "textoAnalisado" not in df.columns:
        print(
            f"\nAVISO: {path_csv} não contém coluna 'textoAnalisado' (provável falha na extração). Pulando."
        )
        return

    if "CID11" in df.columns and not df["CID11"].isna().all():
        print(f"\nArquivo {path_csv} já possui pelo menos um CID11. Pulando.")
        return

    termos_unicos = df["textoAnalisado"].dropna().unique()
    mapa_global = {}
    for termo in termos_unicos:
        termo_str = str(termo).strip()
        if termo_str:
            mapa_global[termo_str] = mapear_termo_api(termo_str, df)

    df["SCTID"] = df["textoAnalisado"].map(
        lambda x: mapa_global.get(str(x).strip(), {}).get("SCTID") if pd.notna(x) else None
    )
    df["CID11"] = df["textoAnalisado"].map(
        lambda x: mapa_global.get(str(x).strip(), {}).get("CID11") if pd.notna(x) else None
    )
    df["SCTID_correto"] = df["textoAnalisado"].map(
        lambda x: mapa_global.get(str(x).strip(), {}).get("SCTID_correto") if pd.notna(x) else None
    )
    df["CID11_correto"] = df["textoAnalisado"].map(
        lambda x: mapa_global.get(str(x).strip(), {}).get("CID11_correto") if pd.notna(x) else None
    )

    df.to_csv(path_csv, index=False, encoding="utf-8")


def main():
    csv_individual_dir = Config.CSV_INDIVIDUAL_FOLDER
    if not os.path.exists(csv_individual_dir):
        print(
            "\nPasta de CSVs individuais não encontrada. Execute 01_extract_terms.py primeiro."
        )
        return

    narrativas = [
        d
        for d in os.listdir(csv_individual_dir)
        if os.path.isdir(os.path.join(csv_individual_dir, d))
    ]

    for narrative_base in narrativas:
        csv_path = os.path.join(
            csv_individual_dir,
            narrative_base,
            "extracted_terms.csv",
        )
        if not os.path.exists(csv_path):
            continue
        _mapear_csv(csv_path)
        print(f"\nMapeamento concluído para {narrative_base}\n")

    print("\nTodos os CSVs foram atualizados com códigos.")


if __name__ == "__main__":
    main()