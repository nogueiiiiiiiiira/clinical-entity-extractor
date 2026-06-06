"""Extrai campos específicos de JSONs/JSONLs e salva como .txt individuais, usando caminhos do config."""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config


def extract_field(input_path, output_dir, field_name, output_suffix=''):
    os.makedirs(output_dir, exist_ok=True)

    with open(input_path, 'r', encoding='utf-8') as f:
        if input_path.endswith('.jsonl'):
            lines = f.readlines()
            data = [json.loads(line) for line in lines]
        else:
            data = json.load(f)

    if isinstance(data, dict) and 'files' in data:
        entries = data['files']
    elif isinstance(data, list):
        entries = data
    else:
        entries = [data]

    for entry in entries:
        filename = entry.get('filename', 'unknown').replace('.xml', '')
        text = entry.get(field_name, '')
        if text:
            out_name = f"{filename}{output_suffix}.txt"
            with open(os.path.join(output_dir, out_name), 'w', encoding='utf-8') as out:
                out.write(text)
            print(f"\nSaved {out_name}")
        else:
            print(f"\nField '{field_name}' not found for {filename}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', default=os.path.join(Config.OUTPUT_BASE, 'final_results.jsonl'),
                        help=f'Arquivo JSON/JSONL de entrada (padrão: {Config.OUTPUT_BASE}/final_results.jsonl)')
    parser.add_argument('--output-dir', default=os.path.join(Config.OUTPUT_BASE, 'extracted'),
                        help=f'Diretório de saída (padrão: {Config.OUTPUT_BASE}/extracted)')
    parser.add_argument('--field', default='with_regex_txt',
                        help='Nome do campo a extrair (ex: original_txt, llm_anonymized_txt, with_regex_txt, gabarito_txt)')
    parser.add_argument('--suffix', default='',
                        help='Sufixo para nome dos arquivos de saída (ex: _llm)')
    args = parser.parse_args()

    extract_field(args.input, args.output_dir, args.field, args.suffix)


if __name__ == "__main__":
    main()