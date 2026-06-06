"""Junta os textos originais, anonimizados, regex, metadados e gabaritos em um único arquivo JSONL."""

import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config


def main() -> None:
    """Gera final_results.jsonl com todos os campos necessários para avaliação."""
    clean_folder = Config.CLEAN_TEXTS_FOLDER
    llm_folder = Config.LLM_OUTPUT_FOLDER
    regex_folder = Config.REGEX_OUTPUT_FOLDER
    meta_folder = Config.METADATA_FOLDER
    gabarito_folder = Config.GABARITOS_FOLDER

    clean_files = [f for f in os.listdir(clean_folder) if f.endswith('.txt')]
    results = []

    for clean_file in clean_files:
        base = clean_file.replace('.txt', '')
        with open(os.path.join(clean_folder, clean_file), 'r', encoding='utf-8') as f:
            original_txt = f.read()

        llm_path = os.path.join(llm_folder, f"{base}.txt")
        if os.path.exists(llm_path):
            with open(llm_path, 'r', encoding='utf-8') as f:
                llm_txt = f.read()
        else:
            llm_txt = ""

        regex_path = os.path.join(regex_folder, f"{base}.txt")
        if os.path.exists(regex_path):
            with open(regex_path, 'r', encoding='utf-8') as f:
                regex_txt = f.read()
        else:
            regex_txt = ""

        meta_path = os.path.join(meta_folder, f"{base}.meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        else:
            meta = {"processing_time": 0, "placeholder_changes": {}}

        # base é o nome do arquivo .txt dentro de textos_limpos; nos gabaritos os nomes são <ID>_gabarito.txt
        # (ex: 2697.txt -> gabarito/2697_gabarito.txt)
        gabarito_path = os.path.join(gabarito_folder, f"{base}_gabarito.txt")
        if os.path.exists(gabarito_path):
            with open(gabarito_path, 'r', encoding='utf-8') as f:
                gabarito_txt = f.read()
        else:
            # DEBUG: não falhar silenciosamente — mas também não travar execução inteira
            print(f"[WARN] Gabarito não encontrado para {base}. Esperado em: {gabarito_path}")
            gabarito_txt = ""



        record = {
            "filename": f"{base}.xml",
            "original_txt": original_txt,
            "llm_anonymized_txt": llm_txt,
            "with_regex_txt": regex_txt,
            "gabarito_txt": gabarito_txt,
            "processing_time": meta.get("processing_time", 0),
            "placeholder_changes": meta.get("placeholder_changes", {})
        }
        results.append(record)

    output_path = os.path.join(Config.OUTPUT_BASE, "final_results.jsonl")
    with open(output_path, 'w', encoding='utf-8') as f:
        for rec in results:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nMerge concluído. {len(results)} registros salvos em {output_path}")


if __name__ == "__main__":
    main()