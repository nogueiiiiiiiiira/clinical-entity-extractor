#!/usr/bin/env python3
"""
app.py – Orquestrador completo do pipeline de anonimizacao.

Executa todas as etapas sequencialmente:
1. Limpeza dos XMLs
2. Anonimizacao via LLM (Ollama)
3. Refinamento com Regex
4. Merge para JSONL
5. Avaliacao do LLM puro
6. Avaliacao do LLM + Regex
7. Analises avancadas para ambas as versoes

Uso:
    python app.py # executa todas as etapas
    python app.py --skip-clean # pula limpeza
    python app.py --skip-llm # pula anonimizacao LLM
    python app.py --skip-regex # pula aplicacao de regex
    python app.py --skip-merge # pula merge
    python app.py --skip-eval # pula avaliacao (ambas)
    python app.py --skip-advanced # pula analises avancadas (ambas)
"""

import subprocess
import sys
import os
import argparse
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SCRIPTS_DIR = os.path.join(ROOT_DIR, "scripts")
DATA_OUTPUT = os.path.join(ROOT_DIR, "data", "output")
FINAL_JSONL = os.path.join(DATA_OUTPUT, "final_results.jsonl")
BASE_EVAL_DIR = os.path.join(DATA_OUTPUT, "evaluation")
EVAL_DIR_LLM = os.path.join(BASE_EVAL_DIR, "llm_only")
EVAL_DIR_REGEX = os.path.join(BASE_EVAL_DIR, "with_regex")
ORIGINAL_TEXTS = os.path.join(DATA_OUTPUT, "textos_limpos")


def run_script(script_name, cwd=SCRIPTS_DIR, args=None, env=None):
    """
    Executa um script Python no diretorio especificado.
    Retorna True se bem-sucedido, False caso contrario.
    """
    script_path = os.path.join(cwd, script_name)
    if not os.path.exists(script_path):
        print(f"\nErro: script nao encontrado – {script_path}")
        return False

    cmd = [sys.executable, script_name]
    if args:
        cmd.extend(args)

    try:
        result = subprocess.run(cmd, cwd=cwd, env=env, check=False)
        if result.returncode == 0:
            print(f"\n\n{script_name} concluido com sucesso.")
            return True
        else:
            print(f"\n\n{script_name} falhou com codigo {result.returncode}.")
            return False
    except Exception as e:
        return False


def check_ollama():
    """Verifica se o Ollama está acessivel e se o modelo configurado existe."""
    import requests
    try:
        sys.path.insert(0, ROOT_DIR)
        from config.config import Config
        model = Config.OLLAMA_MODEL
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code != 200:
            print("\nOllama nao respondeu corretamente. Verifique se o servico esta rodando.")
            return False
        models = resp.json().get("models", [])
        model_names = [m.get("name") for m in models]
        if model not in model_names:
            return False
        return True
    except Exception as e:
        print(f"\nErro ao verificar Ollama: {e}")
        return False


def ensure_directories():
    """Cria os diretorios necessarios, se nao existirem."""
    dirs = [
        os.path.join(ROOT_DIR, "data", "narrativas"),
        os.path.join(ROOT_DIR, "data", "textos_anonimizados"),
        os.path.join(ROOT_DIR, "data", "prompts"),
        os.path.join(ROOT_DIR, "data", "output"),
        DATA_OUTPUT,
        BASE_EVAL_DIR,
        EVAL_DIR_LLM,
        EVAL_DIR_REGEX,
        ORIGINAL_TEXTS,
        os.path.join(DATA_OUTPUT, "LLM_only"),
        os.path.join(DATA_OUTPUT, "REGEX_only"),
        os.path.join(DATA_OUTPUT, "metadata"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)


def step_clean():
    """00_clean.py – extrai texto dos XMLs."""
    return run_script("00_clean.py")


def step_anonymize():
    """01_anonymizer.py – anonimizacao via LLM."""
    return run_script("01_anonymizer.py")


def step_regex():
    """02_apply_regex.py – refinamento com regex."""
    return run_script("02_apply_regex.py")


def step_merge():
    """03_merge.py – consolida todos os resultados em JSONL."""
    return run_script("03_merge.py")


def step_evaluate(model_field, output_dir):
    """04_evaluate.py – compara placeholders com gabaritos."""
    args = ["--input", FINAL_JSONL, "--model-field", model_field, "--output-dir", output_dir]
    return run_script("04_evaluate.py", args=args)


def step_advanced(eval_dir):
    """05_advanced_analysis.py – bootstrap, matriz de confusao, correlacao."""
    args = ["--eval-dir", eval_dir, "--original-dir", ORIGINAL_TEXTS]
    return run_script("05_advanced_analysis.py", args=args)


def main():
    parser = argparse.ArgumentParser(description="Orquestrador do pipeline de anonimizacao clinica")
    parser.add_argument("--skip-clean", action="store_true", help="Pula a etapa de limpeza dos XMLs")
    parser.add_argument("--skip-llm", action="store_true", help="Pula a anonimizacao via LLM")
    parser.add_argument("--skip-regex", action="store_true", help="Pula a aplicacao de regex")
    parser.add_argument("--skip-merge", action="store_true", help="Pula o merge para JSONL")
    parser.add_argument("--skip-eval", action="store_true", help="Pula a avaliacao (ambas: LLM e regex)")
    parser.add_argument("--skip-advanced", action="store_true", help="Pula as analises avancadas (ambas)")
    parser.add_argument("--no-ollama-check", action="store_true", help="Nao verifica disponibilidade do Ollama")
    args = parser.parse_args()

    start_time = time.time()
    ensure_directories()

    if not args.no_ollama_check and not args.skip_llm:
        if not check_ollama():
            print("\n\nOllama nao esta pronto. Abortando.")
            sys.exit(1)

    if not args.skip_clean:
        if not step_clean():
            print("\n\nFalha na limpeza. Interrompendo pipeline.")
            sys.exit(1)
    else:
        print("\n\nPulando etapa de limpeza.")

    if not args.skip_llm:
        if not step_anonymize():
            print("\n\nFalha na anonimizacao via LLM. Interrompendo pipeline.")
            sys.exit(1)
    else:
        print("\n\nPulando anonimizacao via LLM.")

    if not args.skip_regex:
        if not step_regex():
            print("\n\nFalha na aplicacao de regex. Interrompendo pipeline.")
            sys.exit(1)
    else:
        print("\n\nPulando refinamento com regex.")

    if not args.skip_merge:
        if not step_merge():
            print("\n\nFalha no merge. Interrompendo pipeline.")
            sys.exit(1)
    else:
        print("\n\nPulando merge.")

    # Avaliacoes
    if not args.skip_eval:
        print("\n\n=== Avaliando LLM puro ===")
        if not step_evaluate("llm_anonymized_txt", EVAL_DIR_LLM):
            print("\nFalha na avaliacao do LLM puro. Interrompendo pipeline.")
            sys.exit(1)

        print("\n\n=== Avaliando LLM + Regex ===")
        if not step_evaluate("with_regex_txt", EVAL_DIR_REGEX):
            print("\n\nFalha na avaliacao do LLM+Regex. Interrompendo pipeline.")
            sys.exit(1)
    else:
        print("\n\nPulando avaliacao (ambas).")

    # Analises avancadas
    if not args.skip_advanced and not args.skip_eval:
        print("\n\n=== Analises avancadas: LLM puro ===")
        if not step_advanced(EVAL_DIR_LLM):
            print("\n\nFalha nas analises avancadas para LLM puro.")
        else:
            print("\n\nAnalises avancadas para LLM puro concluidas.")

        if not step_advanced(EVAL_DIR_REGEX):
            print("\nFalha nas analises avancadas para LLM+Regex.")
        else:
            print("\n\nAnalises avancadas para LLM+Regex concluidas.")
    elif not args.skip_advanced and args.skip_eval:
        print("\n\nPulando analises avancadas porque a avaliacao foi pulada.")
    else:
        print("\n\nPulando analises avancadas.")

    elapsed = time.time() - start_time
    print(f"\n\nPipeline concluido com sucesso em {elapsed:.2f} segundos.")


if __name__ == "__main__":
    main()