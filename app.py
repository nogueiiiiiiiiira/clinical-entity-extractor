# app.py
"""Ponto de entrada principal do pipeline de extração e mapeamento de termos clínicos.

Executa sequencialmente todos os scripts do pipeline, na ordem correta:
00_preprocess.py -> 01_extract_terms.py -> 02_map_terminology.py -> 03_merge_results.py -> 04_evaluate.py -> 05_audit_report.py
"""

import sys
import os
import subprocess
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent / "scripts"

def run_script(script_name: str) -> bool:
    """Executa um script Python e retorna True se bem-sucedido."""
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        print(f"\n\n[ERRO] Script não encontrado: {script_path}")
        return False

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=SCRIPT_DIR,
        capture_output=False,
        text=True
    )
    if result.returncode != 0:
        print(f"\n\n[ERRO] {script_name} falhou com código {result.returncode}")
        return False

    return True

def main():
    """Orquestra a execução do pipeline completo."""
    
    steps = [
        "00_preprocess.py",
        "01_extract_terms.py",
        "02_map_terminology.py",
        "03_merge_results.py",
        "04_evaluate.py",
        "05_audit_report.py",
    ]

    total_steps = len(steps)
    
    for i, script_name in enumerate(steps, 1):
        print(f"\n{'='*60}")
        print(f"Executando passo {i}/{total_steps}: {script_name}")
        print(f"{'='*60}")
        
        success = run_script(script_name)
        if not success:
            print(f"\n\nPipeline interrompido na etapa {script_name}.")
            sys.exit(1)
    
    print(f"\n{'='*60}")
    print("Pipeline concluído com sucesso!")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()