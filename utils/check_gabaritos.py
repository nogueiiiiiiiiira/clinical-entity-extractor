"""Verifica se todos os arquivos XML possuem gabarito correspondente, usando pastas do config."""

import sys
import os
import argparse

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--narrativas', default=Config.NARRATIVES_FOLDER,
                        help=f'Pasta com XMLs originais (padrão: {Config.NARRATIVES_FOLDER})')
    parser.add_argument('--gabaritos', default=Config.GABARITOS_FOLDER,
                        help=f'Pasta com gabaritos .txt (padrão: {Config.GABARITOS_FOLDER})')
    args = parser.parse_args()

    xml_files = [f for f in os.listdir(args.narrativas) if f.endswith('.xml')]
    missing = []
    for xml in xml_files:
        base = xml.replace('.xml', '')
        gab_path = os.path.join(args.gabaritos, f"{base}_gabarito.txt")
        if not os.path.exists(gab_path):
            missing.append(xml)

    if missing:
        print(f"\nFALTAM GABARITOS para {len(missing)} arquivos:")
        for m in missing:
            print(f"\n  - {m}")
    else:
        print(f"\nTodos os {len(xml_files)} arquivos XML possuem gabarito correspondente.")


if __name__ == "__main__":
    main()