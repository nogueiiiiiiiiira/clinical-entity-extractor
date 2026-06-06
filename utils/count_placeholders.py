"""Conta placeholders em arquivos de gabarito ou saída do modelo, usando diretório padrão configurável."""

import sys
import os
import re
import argparse
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config


def count_placeholders_in_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()
    # Aceita placeholders com acentos (ex: [PROFISSÃO], [HORÁRIO], [ORGANIZAÇÃO])
    matches = re.findall(r'\[([A-Za-zÀ-ÖØ-öø-ÿ_]+)\]', text, re.IGNORECASE)
    return Counter([m.upper() for m in matches])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dir', default=Config.GABARITOS_FOLDER,
                        help=f'Diretório com arquivos .txt (padrão: {Config.GABARITOS_FOLDER})')
    parser.add_argument('--pattern', default='*.txt',
                        help='Padrão de arquivos (ex: *gabarito.txt)')
    args = parser.parse_args()

    import glob
    total = Counter()
    for path in glob.glob(os.path.join(args.dir, args.pattern)):
        cnt = count_placeholders_in_file(path)
        total.update(cnt)
        print(f"\n{os.path.basename(path)}: {dict(cnt)}")
    print("\n\nTOTAL:", dict(total))
    print(f"\nSoma: {sum(total.values())} placeholders")


if __name__ == "__main__":
    main()