"""Análises estatísticas avançadas: bootstrap, matriz de confusão, correlação com comprimento do texto."""

import sys
import os
import json
import csv
import numpy as np
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

try:
    import matplotlib.pyplot as plt
    HAS_MPL = True
except:
    HAS_MPL = False


def bootstrap_ci(metric_values, n_bootstrap=1000, ci=0.95):
    """Calcula intervalo de confiança bootstrap para a média dos valores fornecidos."""
    if len(metric_values) < 2:
        return {'mean': np.mean(metric_values) if metric_values else 0, 'ci_lower': 0, 'ci_upper': 0, 'std': 0}
    np.random.seed(42)
    boot_means = []
    for _ in range(n_bootstrap):
        sample = np.random.choice(metric_values, size=len(metric_values), replace=True)
        boot_means.append(np.mean(sample))
    lower = np.percentile(boot_means, (1-ci)/2*100)
    upper = np.percentile(boot_means, (1+ci)/2*100)
    return {'mean': np.mean(metric_values), 'ci_lower': lower, 'ci_upper': upper, 'std': np.std(boot_means)}


def confusion_matrix_from_details(eval_dir):
    """Constrói matriz de confusão a partir dos arquivos _placeholders.csv."""
    confusion = defaultdict(lambda: defaultdict(int))
    fn_by_cat = defaultdict(int)
    fp_by_cat = defaultdict(int)
    for fname in os.listdir(eval_dir):
        if not fname.endswith('_placeholders.csv'):
            continue
        path = os.path.join(eval_dir, fname)
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cat = row['categoria']
                tipo = row['tipo']
                if tipo == 'FN':
                    confusion[cat]['[NAO_ENCONTRADO]'] += 1
                    fn_by_cat[cat] += 1
                elif tipo == 'FP':
                    confusion['[NAO_DEVERIA]'][cat] += 1
                    fp_by_cat[cat] += 1
    return confusion, fn_by_cat, fp_by_cat


def length_analysis(metrics_csv, original_dir=None):
    """Correlaciona comprimento do texto original (palavras) com F1 macro médio."""
    lengths = []
    f1s = []
    file_f1 = defaultdict(list)
    with open(metrics_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            filename = row['filename']
            f1 = float(row['f1'])
            file_f1[filename].append(f1)
    for filename, f1_list in file_f1.items():
        avg_f1 = np.mean(f1_list)
        if original_dir:
            base = filename.replace('.xml', '')
            txt_path = os.path.join(original_dir, f"{base}.txt")
            if os.path.exists(txt_path):
                with open(txt_path, 'r', encoding='utf-8') as tf:
                    length = len(tf.read().split())
            else:
                length = 500
        else:
            length = 500
        lengths.append(length)
        f1s.append(avg_f1)
    if len(lengths) > 1:
        corr = np.corrcoef(lengths, f1s)[0,1]
    else:
        corr = 0
    return lengths, f1s, corr


def main() -> None:
    """Executa todas as análises avançadas e salva resultados na pasta evaluation."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--eval-dir', required=True, help='Diretório com saída do 04_evaluate.py')
    parser.add_argument('--original-dir', help='Pasta com textos limpos originais (para análise de comprimento)')
    args = parser.parse_args()

    print("\n\n=== ANÁLISE AVANÇADA ===\n")

    metrics_csv = os.path.join(args.eval_dir, 'metricas_completas.csv')
    if os.path.exists(metrics_csv):
        file_f1 = defaultdict(list)
        with open(metrics_csv, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                filename = row['filename']
                f1 = float(row['f1'])
                file_f1[filename].append(f1)
        f1_macro_per_file = [np.mean(v) for v in file_f1.values()]
        if f1_macro_per_file:
            ci = bootstrap_ci(f1_macro_per_file)
            print("\n1. INTERVALO DE CONFIANÇA (Bootstrap)")
            print(f"\n   F1 macro médio = {ci['mean']:.4f}")
            print(f"\n   IC 95%: [{ci['ci_lower']:.4f}, {ci['ci_upper']:.4f}]")
            print(f"\n   Desvio padrão = {ci['std']:.4f}")
            with open(os.path.join(args.eval_dir, 'bootstrap_results.csv'), 'w') as out:
                out.write(f"mean,{ci['mean']:.4f}\nci_lower,{ci['ci_lower']:.4f}\nci_upper,{ci['ci_upper']:.4f}\nstd,{ci['std']:.4f}")

    conf, fn_cat, fp_cat = confusion_matrix_from_details(args.eval_dir)
    print("\n\n2. MATRIZ DE CONFUSÃO (ERROS)")
    print("\n   Falsos Negativos por categoria:")
    for cat, cnt in sorted(fn_cat.items(), key=lambda x: -x[1]):
        print(f"\n     {cat}: {cnt}")
    print("\n   Falsos Positivos por categoria:")
    for cat, cnt in sorted(fp_cat.items(), key=lambda x: -x[1]):
        print(f"\n     {cat}: {cnt}")
    with open(os.path.join(args.eval_dir, 'confusion_matrix.csv'), 'w', newline='', encoding='utf-8') as cf:
        writer = csv.writer(cf)
        writer.writerow(["tipo","categoria_original","categoria_classificada","quantidade"])
        for orig, erros in conf.items():
            for clas, qtd in erros.items():
                writer.writerow(["FN" if orig!='[NAO_DEVERIA]' else "FP", orig, clas, qtd])

    if args.original_dir and os.path.exists(metrics_csv):
        lengths, f1s, corr = length_analysis(metrics_csv, args.original_dir)
        print(f"\n\n3. ANÁLISE POR COMPRIMENTO DO TEXTO")
        print(f"\n   Correlação (F1 vs palavras): {corr:.3f}")
        if HAS_MPL and len(lengths) > 1:
            plt.figure()
            plt.scatter(lengths, f1s, alpha=0.6)
            plt.xlabel('Número de palavras')
            plt.ylabel('F1 macro médio')
            plt.title('Desempenho vs Comprimento do Texto')
            plt.savefig(os.path.join(args.eval_dir, 'length_vs_f1.png'), dpi=150)
            plt.close()
            print("\n   Gráfico salvo: length_vs_f1.png")
    else:
        print("\n\n3. ANÁLISE POR COMPRIMENTO: forneça --original-dir e tenha metricas_completas.csv para ativar")

    print("\n\nAnálises concluídas.")


if __name__ == "__main__":
    main()