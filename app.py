# app.py
"""Ponto de entrada principal do pipeline de extração e mapeamento de termos clínicos.

Executa sequencialmente todos os scripts do pipeline, na ordem correta:
00_preprocess.py -> 01_extract_terms.py -> 02_map_terminology.py -> 03_merge_results.py -> 04_evaluate.py -> 05_audit_report.py
"""

import sys
import os
import subprocess
import threading
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent / "scripts"
LOG_FILE = os.path.join(os.path.dirname(SCRIPT_DIR), "data", "output", "logs", "log_execucao.txt")

def ensure_log_dir():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

def run_script(script_name: str, log_file_handle) -> bool:
    """Executa um script Python, redirecionando stdout/stderr para o terminal e para o log."""
    script_path = SCRIPT_DIR / script_name
    if not script_path.exists():
        print(f"\n\n[ERRO] Script não encontrado: {script_path}")
        log_file_handle.write(f"\n\n[ERRO] Script não encontrado: {script_path}\n")
        log_file_handle.flush()
        return False

    print(f"\nExecutando {script_name}...")
    log_file_handle.write(f"\n--- Início: {script_name} ---\n")
    log_file_handle.flush()

    process = subprocess.Popen(
        [sys.executable, str(script_path)],
        cwd=SCRIPT_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    def output_reader(process, log_file):
        for line in process.stdout:
            print(line, end="")
            log_file.write(line)
            log_file.flush()

    thread = threading.Thread(target=output_reader, args=(process, log_file_handle))
    thread.start()
    process.wait()
    thread.join()

    if process.returncode != 0:
        print(f"\n\n[ERRO] {script_name} falhou com código {process.returncode}")
        log_file_handle.write(f"\n\n[ERRO] {script_name} falhou com código {process.returncode}\n")
        log_file_handle.flush()
        return False

    log_file_handle.write(f"\n--- Fim: {script_name} ---\n")
    log_file_handle.flush()
    return True

def main():
    """Orquestra a execução do pipeline completo."""
    ensure_log_dir()
    
    steps = [
        "00_preprocess.py",
        "01_extract_terms.py",
        "02_map_terminology.py",
        "03_merge_results.py",
        "04_evaluate.py",
        "05_audit_report.py",
    ]

    total_steps = len(steps)

    with open(LOG_FILE, "w", encoding="utf-8") as log_file:
        log_file.write(f"{'='*60}\n")
        log_file.write(f"Início da execução do pipeline\n")
        log_file.write(f"{'='*60}\n\n")
        
        for i, script_name in enumerate(steps, 1):
            print(f"\n{'='*60}")
            print(f"Executando passo {i}/{total_steps}: {script_name}")
            print(f"{'='*60}")
            log_file.write(f"\n{'='*60}\n")
            log_file.write(f"Executando passo {i}/{total_steps}: {script_name}\n")
            log_file.write(f"{'='*60}\n")
            log_file.flush()

            success = run_script(script_name, log_file)
            if not success:
                print(f"\n\nPipeline interrompido na etapa {script_name}.")
                log_file.write(f"\n\nPipeline interrompido na etapa {script_name}.\n")
                sys.exit(1)

        print(f"\n{'='*60}")
        print("Pipeline concluído com sucesso!")
        print(f"{'='*60}")
        log_file.write(f"\n{'='*60}\n")
        log_file.write("Pipeline concluído com sucesso!\n")
        log_file.write(f"{'='*60}\n")

if __name__ == "__main__":
    main()