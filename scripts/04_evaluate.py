"""Avalia a qualidade da anonimização comparando placeholders do modelo com gabaritos."""

import sys
import os
import json
import re
import csv
from collections import defaultdict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

CATEGORIAS = ["NOME", "PROFISSÃO", "CONTATO", "IDs", "DATA", "HORÁRIO", "LOCAL", "ORGANIZAÇÃO"]


def extract_placeholders_with_positions(text):
    """Retorna lista de dicionários com categoria e posição de cada placeholder."""
    if not text:
        return []
    matches = re.finditer(r'\[([A-Za-zÀ-ÖØ-öø-ÿÇ]+)\]', text)
    result = []
    for m in matches:
        cat = m.group(1).upper()
        if cat == "ID" or cat == "IDS":
            cat = "IDs"
        if cat in CATEGORIAS:
            result.append({
                'category': cat,
                'position': m.start(),
                'original': m.group(0)
            })
    return result


def evaluate_lcs(gabarito_phs, model_phs):
    """Calcula TP, FN, FP usando subsequência comum mais longa (LCS)."""
    resultados = {cat: {"TP": 0, "FN": 0, "FP": 0} for cat in CATEGORIAS}
    if not gabarito_phs or not model_phs:
        for g in gabarito_phs:
            resultados[g['category']]["FN"] += 1
        for m in model_phs:
            resultados[m['category']]["FP"] += 1
        return resultados, [False]*len(gabarito_phs), [False]*len(model_phs)

    n, m_len = len(gabarito_phs), len(model_phs)
    dp = [[0]*(m_len+1) for _ in range(n+1)]
    for i in range(1, n+1):
        for j in range(1, m_len+1):
            if gabarito_phs[i-1]['category'] == model_phs[j-1]['category']:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    i, j = n, m_len
    used_gt = [False]*n
    used_model = [False]*m_len
    while i > 0 and j > 0:
        if gabarito_phs[i-1]['category'] == model_phs[j-1]['category']:
            used_gt[i-1] = True
            used_model[j-1] = True
            i -= 1
            j -= 1
        elif dp[i-1][j] > dp[i][j-1]:
            i -= 1
        else:
            j -= 1

    for i, g in enumerate(gabarito_phs):
        if not used_gt[i]:
            resultados[g['category']]["FN"] += 1
        else:
            resultados[g['category']]["TP"] += 1
    for j, m_ph in enumerate(model_phs):
        if not used_model[j]:
            resultados[m_ph['category']]["FP"] += 1

    return resultados, used_gt, used_model


def generate_report(totais, resultados_por_arquivo, output_dir, prefix):
    """Imprime e salva relatório JSON com métricas agregadas."""
    print(f"\n{'Categoria':<15} {'TP':>6} {'FN':>6} {'FP':>6} {'GT':>6} {'Precision':>10} {'Recall':>10} {'F1':>10}")

    total_tp = total_fn = total_fp = total_gt = 0
    precisoes, recalls, f1s = [], [], []
    for cat in CATEGORIAS:
        tp = totais[cat]["TP"]
        fn = totais[cat]["FN"]
        fp = totais[cat]["FP"]
        gt = totais[cat]["GT"]
        total_tp += tp; total_fn += fn; total_fp += fp; total_gt += gt

        prec = tp/(tp+fp) if (tp+fp)>0 else 0
        rec = tp/(tp+fn) if (tp+fn)>0 else 0
        f1 = 2*prec*rec/(prec+rec) if (prec+rec)>0 else 0
        precisoes.append(prec); recalls.append(rec); f1s.append(f1)

        print(f"\n{cat:<15} {tp:>6} {fn:>6} {fp:>6} {gt:>6} {prec:>9.3f} {rec:>9.3f} {f1:>9.3f}")
    print(f"\n{'TOTAL':<15} {total_tp:>6} {total_fn:>6} {total_fp:>6} {total_gt:>6}")

    prec_micro = total_tp/(total_tp+total_fp) if (total_tp+total_fp)>0 else 0
    rec_micro = total_tp/(total_tp+total_fn) if (total_tp+total_fn)>0 else 0
    f1_micro = 2*prec_micro*rec_micro/(prec_micro+rec_micro) if (prec_micro+rec_micro)>0 else 0
    prec_macro = sum(precisoes)/len(precisoes) if precisoes else 0
    rec_macro = sum(recalls)/len(recalls) if recalls else 0
    f1_macro = sum(f1s)/len(f1s) if f1s else 0

    print(f"\n\nMicro: Precision={prec_micro:.3f} Recall={rec_micro:.3f} F1={f1_micro:.3f}")
    print(f"\nMacro: Precision={prec_macro:.3f} Recall={rec_macro:.3f} F1={f1_macro:.3f}")

    report_json = {
        "prefix": prefix,
        "micro": {"precision": prec_micro, "recall": rec_micro, "f1": f1_micro},
        "macro": {"precision": prec_macro, "recall": rec_macro, "f1": f1_macro},
        "por_categoria": {cat: {"TP": totais[cat]["TP"], "FN": totais[cat]["FN"], "FP": totais[cat]["FP"],
                                "precision": round(prec,4), "recall": round(rec,4), "f1": round(f1,4)}
                         for cat, prec, rec, f1 in zip(CATEGORIAS, precisoes, recalls, f1s)},
        "por_arquivo": resultados_por_arquivo
    }
    with open(os.path.join(output_dir, f"report_{prefix}.json"), 'w', encoding='utf-8') as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)
    print(f"\n\nRelatório salvo em {output_dir}/report_{prefix}.json")


def generate_per_file_csvs(details, output_dir):
    """Gera um CSV por arquivo com os placeholders TP, FN, FP."""
    per_file = defaultdict(list)
    for d in details:
        per_file[d['filename']].append(d)
    for fn, rows in per_file.items():
        base = fn.replace('.xml', '')
        csv_path = os.path.join(output_dir, f"{base}_placeholders.csv")
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['filename','termo_original','categoria','tipo'])
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
    print(f"\nCSVs individuais gerados em {output_dir}")


def generate_complete_csv(totais, resultados_por_arquivo, output_dir):
    """Gera um CSV consolidado com métricas por arquivo e categoria."""
    csv_path = os.path.join(output_dir, "metricas_completas.csv")
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["filename","gt_total","model_total","categoria","TP","FN","FP","precision","recall","f1"])
        for arq in resultados_por_arquivo:
            filename = arq['filename']
            gt_total = arq['gt_total']
            model_total = arq['model_total']
            for cat in CATEGORIAS:
                tp = arq['resultados'][cat]['TP']
                fn = arq['resultados'][cat]['FN']
                fp = arq['resultados'][cat]['FP']
                prec = tp/(tp+fp) if (tp+fp)>0 else 0
                rec = tp/(tp+fn) if (tp+fn)>0 else 0
                f1 = 2*prec*rec/(prec+rec) if (prec+rec)>0 else 0
                writer.writerow([filename, gt_total, model_total, cat, tp, fn, fp, round(prec,4), round(rec,4), round(f1,4)])
    print(f"\nCSV consolidado salvo em {csv_path}")


def evaluate_from_jsonl(jsonl_path, model_field='with_regex_txt', output_dir='evaluation'):
    """Função principal de avaliação a partir do JSONL gerado pelo merge."""
    os.makedirs(output_dir, exist_ok=True)
    entries = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            entries.append(json.loads(line))

    totais = {cat: {"TP":0,"FN":0,"FP":0,"GT":0} for cat in CATEGORIAS}
    resultados_por_arquivo = []
    details = []

    for entry in entries:
        filename = entry.get('filename')
        gabarito_txt = entry.get('gabarito_txt')
        model_text = entry.get(model_field)

        if not gabarito_txt or not model_text:
            print(f"\nAviso: pulando {filename} - gabarito ou modelo vazio")
            continue

        gab_phs = extract_placeholders_with_positions(gabarito_txt)
        mod_phs = extract_placeholders_with_positions(model_text)

        resultados, used_gt, used_model = evaluate_lcs(gab_phs, mod_phs)

        for i, g in enumerate(gab_phs):
            tipo = "TP" if used_gt[i] else "FN"
            details.append({
                "filename": filename,
                "termo_original": "",
                "categoria": g['category'],
                "tipo": tipo
            })
        for j, m in enumerate(mod_phs):
            if not used_model[j]:
                details.append({
                    "filename": filename,
                    "termo_original": "",
                    "categoria": m['category'],
                    "tipo": "FP"
                })

        for cat in CATEGORIAS:
            tp = resultados[cat]["TP"]
            fn = resultados[cat]["FN"]
            fp = resultados[cat]["FP"]
            totais[cat]["TP"] += tp
            totais[cat]["FN"] += fn
            totais[cat]["FP"] += fp
            totais[cat]["GT"] += (tp+fn)

        resultados_por_arquivo.append({
            "filename": filename,
            "resultados": resultados,
            "gt_total": len(gab_phs),
            "model_total": len(mod_phs)
        })

    generate_report(totais, resultados_por_arquivo, output_dir, model_field)
    generate_per_file_csvs(details, output_dir)
    generate_complete_csv(totais, resultados_por_arquivo, output_dir)


def main() -> None:
    """Ponto de entrada: lê argumentos e executa avaliação."""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True, help='JSONL gerado pelo 03_merge.py')
    parser.add_argument('--model-field', default='with_regex_txt', choices=['llm_anonymized_txt','with_regex_txt'])
    parser.add_argument('--output-dir', default=None, help='Pasta de saída (padrão: Config.OUTPUT_BASE/evaluation)')
    args = parser.parse_args()

    if args.output_dir is None:
        args.output_dir = os.path.join(Config.OUTPUT_BASE, 'evaluation')
    evaluate_from_jsonl(args.input, args.model_field, args.output_dir)


if __name__ == "__main__":
    main()