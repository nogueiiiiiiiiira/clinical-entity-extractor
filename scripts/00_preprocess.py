"""Extrai texto limpo de arquivos XML (removendo tags) e salva em txt para uso posterior."""

import sys
import os
import re
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

def clean_xml_text(xml_path: str) -> str:
    """Extrai o conteúdo da tag TEXT, remove tags XML/HTML e normaliza espaços."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        text_elem = root.find('.//TEXT')
        if text_elem is None or not text_elem.text:
            return ""
        raw = text_elem.text
        raw = re.sub(r'\s+', ' ', raw).strip()
        return raw
    except Exception as e:
        print(f"\n\nErro ao processar {xml_path}: {e}")
        return ""

def main() -> None:
    """Executa a limpeza de todos os arquivos XML da pasta de narrativas."""
    os.makedirs(Config.CLEAN_TEXTS_FOLDER, exist_ok=True)
    
    xml_files = [f for f in os.listdir(Config.NARRATIVES_FOLDER) if f.endswith('.xml') and not f.endswith('_goldstandard.xml')]
    print(f"\n\nEncontrados {len(xml_files)} arquivos XML")
    for xml_file in xml_files:
        xml_path = os.path.join(Config.NARRATIVES_FOLDER, xml_file)
        clean_text = clean_xml_text(xml_path)
        if not clean_text:
            print(f"\n\n  AVISO: texto vazio em {xml_file}")
            continue
        base = xml_file.replace('.xml', '')
        txt_path = os.path.join(Config.CLEAN_TEXTS_FOLDER, f"{base}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(clean_text)

if __name__ == "__main__":
    main()