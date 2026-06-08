"""Ponto de entrada principal do pipeline de extração e mapeamento de termos clínicos.

Executa sequencialmente todos os scripts do pipeline, na ordem correta:
00_preprocess.py -> 01_extract_terms.py -> 02_map_terminology.py -> 03_merge_results.py -> 04_evaluate.py

Para execução parcial, use os argumentos --start-at e --stop-after.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent / "scripts"

def run_script(script_name: str, step_num: int, total_steps: int) -> bool:
    """Executa um script Python e retorna True se bem-sucedido."""
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        print(f"\n\n[ERRO] Script não encontrado: {script_path}")
        return False

    print(f"\n\n{'='*80}")
    print(f"\nExecutando passo {step_num}/{total_steps}: {script_name}")
    print(f"\n{'='*80}\n")

    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=SCRIPT_DIR,
        capture_output=False,
        text=True
    )
    if result.returncode != 0:
        print(f"\n\n[ERRO] {script_name} falhou com código {result.returncode}")
        return False

    print(f"\n\n[OK] {script_name} concluído com sucesso.\n")
    return True

def main():
    """Orquestra a execução do pipeline conforme argumentos fornecidos."""
    parser = argparse.ArgumentParser(
        description="Executa o pipeline completo de extração e mapeamento de termos clínicos."
    )
    parser.add_argument(
        "--start-at",
        type=str,
        choices=["00", "01", "02", "03", "04"],
        default="00",
        help="Script a partir do qual iniciar (00, 01, 02, 03, 04). Padrão: 00"
    )
    parser.add_argument(
        "--stop-after",
        type=str,
        choices=["00", "01", "02", "03", "04"],
        default="04",
        help="Script após o qual parar (00, 01, 02, 03, 04). Padrão: 04"
    )
    args = parser.parse_args()

    steps = [
        ("00_preprocess.py", "00"),
        ("01_extract_terms.py", "01"),
        ("02_map_terminology.py", "02"),
        ("03_merge_results.py", "03"),
        ("04_evaluate.py", "04")
    ]

    start_index = None
    stop_index = None
    for i, (_, step_id) in enumerate(steps):
        if step_id == args.start_at:
            start_index = i
        if step_id == args.stop_after:
            stop_index = i

    if start_index is None or stop_index is None:
        sys.exit(1)

    total = stop_index - start_index + 1
    step_counter = 1

    for i in range(start_index, stop_index + 1):
        script_name, _ = steps[i]
        success = run_script(script_name, step_counter, total)
        if not success:
            print(f"\n\nPipeline interrompido na etapa {script_name}.")
            sys.exit(1)
        step_counter += 1

if __name__ == "__main__":
    main()