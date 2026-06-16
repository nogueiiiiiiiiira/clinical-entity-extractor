"""Avalia a qualidade da extração comparando com gold standard (XMLs anotados)."""

import sys
import os
import re
import pandas as pd
import xml.etree.ElementTree as ET
import openpyxl
import ollama

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config.config import Config
from utils import (
    padronizar_string,
    normalizar_termo_texto,
    normalizar_para_match,
    expansion_of,
    fuzzy_partial_match,
    llm_semantic_match,
    load_json_cache,
    save_json_cache,
    verificar_expansao_llm,
)
expansion_cache = load_json_cache(os.path.join(Config.DICIONARIOS_FOLDER, Config.EXPANSION_CACHE_FILE))


def extrair_gold_terms(root, narrativa_filename):
    achados = []
    relations_elem = root.find("RELATIONS")
    rel_dict = {}
    if relations_elem is not None:
        for rel in relations_elem:
            if rel.tag == "RELATION":
                an1 = rel.get("fromID")
                an2 = rel.get("toID")
                tipo = rel.get("Relação_Temporal")
                if an1 and an2:
                    rel_dict.setdefault(an1, []).append(
                        {"id_relacionado": an2, "tipo_relacionamento": tipo}
                    )

    tags_elem = root.find(".//TAGS")
    if tags_elem is None:
        return achados

    for annotation in tags_elem:
        if annotation.tag != "EVENT":
            continue
        tipo = annotation.get("Tipo")
        polaridade = annotation.get("Polaridade")
        if polaridade != "Positiva" or tipo not in ("Problema", "Tratamento", "Teste"):
            continue

        id_anot = annotation.get("id")
        dado = padronizar_string(annotation.get("text"))
        negado = False

        anot_principal = root.find(f".//EVENT[@id='{id_anot}']")
        if anot_principal is not None and anot_principal.get("Polaridade") == "Negativa":
            negado = True

        for key, value_list in rel_dict.items():
            for value in value_list:
                if id_anot == value["id_relacionado"]:
                    anot_rel = root.find(f".//EVENT[@id='{key}']")
                    if anot_rel is not None:
                        if (
                            anot_rel.get("Polaridade") == "Negativa"
                            or value["tipo_relacionamento"] == "negation_of"
                        ):
                            negado = True

        if not dado or negado:
            continue

        categoria = tipo
        achados.append(
            {
                "narrativa": os.path.basename(narrativa_filename),
                "termo": dado,
                "categoria": categoria,
            }
        )

    return achados


def classificar_erro(
    pred_term,
    gold_term,
    texto_narrativa,
    predicted_all,
    gold_all,
    tipo_erro,
    categoria_pred=None,
    categoria_gold=None,
):
    termo_alvo = pred_term if tipo_erro == "FP" else gold_term
    if tipo_erro == "VP" and categoria_pred != categoria_gold:
        return "Erro de classificação"
    if termo_alvo is None:
        return "Indeterminado"

    termo_norm = padronizar_string(termo_alvo)
    if len(termo_norm) <= 2 and not termo_norm.isalpha():
        return "Extração de verbo ou ruído"

    verbos_extras = [
        "apresenta",
        "refere",
        "relata",
        "queixa",
        "evoluiu",
        "nega",
        "sem",
        "ausência",
        "relatado",
        "descreve",
        "informa",
        "nota",
        "observa",
        "constata",
    ]

    if termo_norm in verbos_extras or (
        len(termo_norm) < 4 and termo_norm not in ["has", "icc", "dm", "da", "dc", "rv"]
    ):
        return "Extração de verbo ou ruído"

    if tipo_erro == "FP":
        for gt in gold_all:
            gt_norm = padronizar_string(gt)
            if gt_norm and (termo_norm in gt_norm or gt_norm in termo_norm):
                return "Termo fragmentado"

        if len(termo_norm) <= 6 and termo_norm.isupper():
            for gt in gold_all:
                if expansion_of(gt, termo_norm):
                    return "Abreviação não expandida"

        for gt in gold_all:
            if fuzzy_partial_match(termo_norm, gt, threshold=50):
                return "Variação lexical extrema"

    else:
        for pt in predicted_all:
            pt_norm = padronizar_string(pt)
            if pt_norm and (pt_norm in termo_norm or termo_norm in pt_norm):
                return "Termo fragmentado"

        if len(termo_norm) > 6 and " " in termo_norm:
            words = termo_norm.split()
            initials = "".join(w[0] for w in words if w)
            if len(initials) >= 2:
                for pt in predicted_all:
                    if padronizar_string(pt) == initials:
                        return "Abreviação não expandida"

        for pt in predicted_all:
            if fuzzy_partial_match(termo_norm, pt, threshold=50):
                return "Variação lexical extrema"

    return "Variação lexical extrema" if tipo_erro == "FN" else "Indeterminado"


def extrair_contexto(texto, termo, window=80):
    if not termo:
        return ""
    idx = texto.lower().find(padronizar_string(termo))
    if idx == -1:
        return texto[: window * 2] if texto else ""
    start = max(0, idx - window)
    end = min(len(texto), idx + len(termo) + window)
    snippet = texto[start:end].replace("\n", " ")
    return snippet.strip()


def avaliar_modo(csv_path, modo, output_suffix, output_dir):
    os.makedirs(output_dir, exist_ok=True)

    df_prompts = pd.read_csv(csv_path)
    if "polaridade" in df_prompts.columns:
        df_prompts = df_prompts[
            df_prompts["polaridade"].str.strip().str.lower() == "positiva"
        ]

    narrativas_unicas = df_prompts["nomeNarrativa"].unique()

    df_resultado = pd.DataFrame(
        columns=[
            "nomeNarrativa",
            "textoPrompt",
            "categoria",
            "termoAnalisado",
            "abreviacao",
            "CID11",
            "expansao_correta",
            "SCTID_correto",
            "CID11_correto",
            "semClin_nomeNarrativa",
            "semClin_textoAnalisado",
            "semClin_categoria",
            "classificacao",
        ]
    )

    metricas = {"VP": 0, "FP": 0, "FN": 0}
    categoria_stats = {}

    for narrativa_atual in narrativas_unicas:
        df_narr = df_prompts[df_prompts["nomeNarrativa"] == narrativa_atual].copy()
        if df_narr.empty:
            continue

        achados_prompt = df_narr[
            [
                "textoAnalisado",
                "textoPrompt",
                "categoria",
                "abreviacao",
                "SCTID",
                "CID11",
                "expansao_correta",
                "SCTID_correto",
                "CID11_correto",
            ]
        ].to_dict("records")

        nome_base = (
            narrativa_atual.replace(".xml", "")
            if narrativa_atual.endswith(".xml")
            else narrativa_atual[:4]
        )
        caminho_gold = os.path.join(Config.GOLDSTANDARD_FOLDER, f"{nome_base}_goldstandard.xml")
        if not os.path.exists(caminho_gold):
            print(f"\nGold standard não encontrado para {narrativa_atual}. Pulando.")
            continue

        try:
            tree = ET.parse(caminho_gold)
            root = tree.getroot()
            achados_semclin = extrair_gold_terms(root, caminho_gold)
        except Exception as e:
            print(f"\nErro ao ler gold standard {caminho_gold}: {e}")
            continue

        texto_prompt = df_narr.iloc[0]["textoPrompt"] if not df_narr.empty else ""

        for p in achados_prompt:
            p["termo_norm"] = normalizar_para_match(p["textoAnalisado"])
        for g in achados_semclin:
            g["termo_norm"] = normalizar_para_match(g["termo"])

        usado_prompt = [False] * len(achados_prompt)
        usado_semclin = [False] * len(achados_semclin)

        matches = []
        for i, pred in enumerate(achados_prompt):
            for j, gold in enumerate(achados_semclin):
                if not pred["termo_norm"] or not gold["termo_norm"]:
                    continue
                if pred["termo_norm"] == gold["termo_norm"]:
                    matches.append((3, i, j, "VP"))
                elif modo == "relaxed":
                    if expansion_of(pred["termo_norm"], gold["termo_norm"]) or expansion_of(
                        gold["termo_norm"], pred["termo_norm"]
                    ):
                        matches.append((2, i, j, "VP"))
                    elif verificar_expansao_llm(gold["termo_norm"], pred["termo_norm"], expansion_cache, os.path.join(Config.DICIONARIOS_FOLDER, Config.EXPANSION_CACHE_FILE)) == 1:
                        matches.append((2, i, j, "VP"))
                    else:
                        import re
                        def normalize_freq(t):
                            return re.sub(r'\s*\d+xd\s*', '', t)
                        pred_norm_freq = normalize_freq(pred["termo_norm"])
                        gold_norm_freq = normalize_freq(gold["termo_norm"])
                        if pred_norm_freq == gold_norm_freq:
                            matches.append((2, i, j, "VP"))
                        elif fuzzy_partial_match(pred["termo_norm"], gold["termo_norm"]):
                            matches.append((1, i, j, "VP"))
                        elif llm_semantic_match(pred["termo_norm"], gold["termo_norm"]):
                            matches.append((0.5, i, j, "VP"))

        matches.sort(key=lambda x: (-x[0], x[1], x[2]))

        for _, i, j, _ in matches:
            if usado_prompt[i] or usado_semclin[j]:
                continue

            pred = achados_prompt[i]
            gold = achados_semclin[j]

            nova = {
                "nomeNarrativa": narrativa_atual,
                "textoPrompt": pred["textoPrompt"],
                "categoria": pred["categoria"],
                "termoAnalisado": pred["textoAnalisado"],
                "abreviacao": pred["abreviacao"],
                "CID11": pred.get("CID11", ""),
                "expansao_correta": pred.get("expansao_correta", ""),
                "SCTID_correto": pred.get("SCTID_correto", ""),
                "CID11_correto": pred.get("CID11_correto", ""),
                "semClin_nomeNarrativa": gold["narrativa"],
                "semClin_textoAnalisado": gold["termo"],
                "semClin_categoria": gold["categoria"],
                "classificacao": "VP",
            }

            df_resultado = pd.concat([df_resultado, pd.DataFrame([nova])], ignore_index=True)
            usado_prompt[i] = True
            usado_semclin[j] = True
            metricas["VP"] += 1

            cat = pred["categoria"]
            categoria_stats.setdefault(cat, {"VP": 0, "FP": 0, "FN": 0})
            categoria_stats[cat]["VP"] += 1

        for i, pred in enumerate(achados_prompt):
            if not usado_prompt[i]:
                nova = {
                    "nomeNarrativa": narrativa_atual,
                    "textoPrompt": pred["textoPrompt"],
                    "categoria": pred["categoria"],
                    "termoAnalisado": pred["textoAnalisado"],
                    "abreviacao": pred["abreviacao"],
                    "CID11": pred.get("CID11", ""),
                    "expansao_correta": pred.get("expansao_correta", ""),
                    "SCTID_correto": pred.get("SCTID_correto", ""),
                    "CID11_correto": pred.get("CID11_correto", ""),
                    "semClin_nomeNarrativa": "",
                    "semClin_textoAnalisado": "",
                    "semClin_categoria": "",
                    "classificacao": "FP",
                }
                df_resultado = pd.concat([df_resultado, pd.DataFrame([nova])], ignore_index=True)
                metricas["FP"] += 1

                cat = pred["categoria"]
                categoria_stats.setdefault(cat, {"VP": 0, "FP": 0, "FN": 0})
                categoria_stats[cat]["FP"] += 1

        for j, gold in enumerate(achados_semclin):
            if not usado_semclin[j]:
                nova = {
                    "nomeNarrativa": narrativa_atual,
                    "textoPrompt": "",
                    "categoria": "",
                    "termoAnalisado": "",
                    "abreviacao": "",
                    "CID11": "",
                    "expansao_correta": "",
                    "SCTID_correto": "",
                    "CID11_correto": "",
                    "semClin_nomeNarrativa": gold["narrativa"],
                    "semClin_textoAnalisado": gold["termo"],
                    "semClin_categoria": gold["categoria"],
                    "classificacao": "FN",
                }
                df_resultado = pd.concat([df_resultado, pd.DataFrame([nova])], ignore_index=True)
                metricas["FN"] += 1

                cat = gold["categoria"]
                categoria_stats.setdefault(cat, {"VP": 0, "FP": 0, "FN": 0})
                categoria_stats[cat]["FN"] += 1

    excel_path = os.path.join(output_dir, f"avaliacao_detalhada_{output_suffix}.xlsx")
    df_resultado.to_excel(excel_path, index=False, engine="openpyxl")

    total_acertos = metricas["VP"]
    prec = total_acertos / (total_acertos + metricas["FP"]) if (total_acertos + metricas["FP"]) > 0 else 0
    rec = total_acertos / (total_acertos + metricas["FN"]) if (total_acertos + metricas["FN"]) > 0 else 0
    f1 = 2 * (prec * rec) / (prec + rec) if (prec + rec) > 0 else 0

    pd.DataFrame([metricas]).to_csv(
        os.path.join(output_dir, f"tabela2_contagem_geral_{output_suffix}.csv"),
        index=False,
    )
    pd.DataFrame(
        [{"Modelo": f"Extração - modo {modo}", "Precisão": prec, "Recall": rec, "F1": f1}]
    ).to_csv(
        os.path.join(output_dir, f"tabela5_comparacao_geral_{output_suffix}.csv"),
        index=False,
    )

    linhas_tabela3 = []
    linhas_tabela6 = []
    for cat, stats in categoria_stats.items():
        vp_cat = stats["VP"]
        fp_cat = stats["FP"]
        fn_cat = stats["FN"]
        prec_cat = vp_cat / (vp_cat + fp_cat) if (vp_cat + fp_cat) > 0 else 0
        rec_cat = vp_cat / (vp_cat + fn_cat) if (vp_cat + fn_cat) > 0 else 0
        f1_cat = 2 * (prec_cat * rec_cat) / (prec_cat + rec_cat) if (prec_cat + rec_cat) > 0 else 0

        linhas_tabela3.append({"Categoria": cat, "VP": vp_cat, "FP": fp_cat, "FN": fn_cat})
        linhas_tabela6.append({"Categoria": cat, "Precisão": prec_cat, "Recall": rec_cat, "F1": f1_cat})

    pd.DataFrame(linhas_tabela3).to_csv(
        os.path.join(output_dir, f"tabela3_contagem_por_categoria_{output_suffix}.csv"),
        index=False,
    )
    pd.DataFrame(linhas_tabela6).to_csv(
        os.path.join(output_dir, f"tabela6_detalhamento_categoria_{output_suffix}.csv"),
        index=False,
    )

    erros_por_tipo = {}
    for _, row in df_resultado.iterrows():
        classificacao = row["classificacao"]
        if classificacao not in ("FP", "FN"):
            continue

        pred_term = row["termoAnalisado"] if classificacao == "FP" else None
        gold_term = row["semClin_textoAnalisado"] if classificacao == "FN" else None

        texto = row["textoPrompt"]
        narrativa = row["nomeNarrativa"]

        categoria_pred = row["categoria"] if classificacao == "FP" else None
        categoria_gold = row["semClin_categoria"] if classificacao == "FN" else None

        todos_pred = (
            df_resultado[df_resultado["nomeNarrativa"] == narrativa]["termoAnalisado"]
            .dropna()
            .tolist()
        )
        todos_gold = (
            df_resultado[df_resultado["nomeNarrativa"] == narrativa]["semClin_textoAnalisado"]
            .dropna()
            .tolist()
        )

        tipo = classificar_erro(
            pred_term,
            gold_term,
            texto,
            todos_pred,
            todos_gold,
            classificacao,
            categoria_pred,
            categoria_gold,
        )
        erros_por_tipo.setdefault(tipo, []).append(row)

    resumo_erros = []
    for tipo, rows in erros_por_tipo.items():
        amostra = rows[0]
        termo_exibido = (
            amostra["termoAnalisado"] if amostra["classificacao"] == "FP" else amostra["semClin_textoAnalisado"]
        )
        contexto = (
            extrair_contexto(amostra["textoPrompt"], termo_exibido) if amostra["textoPrompt"] else ""
        )
        resumo_erros.append(
            {
                "Tipo de erro": tipo,
                "Termo extraído": termo_exibido,
                "FN ou FP": amostra["classificacao"],
                "Texto original": contexto,
                "Explicação": f"{len(rows)} ocorrências",
                "Contagem": len(rows),
            }
        )

    pd.DataFrame(resumo_erros).to_csv(
        os.path.join(output_dir, f"erros_classificados_{output_suffix}.csv"),
        index=False,
    )

    return {
        "modo": modo,
        "total_termos_avaliados": len(df_resultado),
        "VP": metricas["VP"],
        "FP": metricas["FP"],
        "FN": metricas["FN"],
        "precisao": prec,
        "recall": rec,
        "f1": f1
    }


def calcular_metricas_mapeamento(consolidated_csv):
    """Calcula métricas de mapeamento a partir do CSV consolidado."""
    df = pd.read_csv(consolidated_csv)

    total_termos = len(df)

    termos_com_snomed = df["SCTID"].notna().sum() if "SCTID" in df.columns else 0
    snomed_corretos = (
        df["SCTID_correto"].sum() if ("SCTID_correto" in df.columns and termos_com_snomed > 0) else 0
    )

    cid_code_col = "CID11" if "CID11" in df.columns else "CID10"
    cid_correct_col = "CID11_correto" if "CID11_correto" in df.columns else "CID10_correto"

    termos_com_cid = df[cid_code_col].notna().sum() if cid_code_col in df.columns else 0
    cid_corretos = (
        df[cid_correct_col].sum() if (cid_correct_col in df.columns and termos_com_cid > 0) else 0
    )

    precisao_snomed = snomed_corretos / total_termos if total_termos > 0 else 0
    precisao_cid = cid_corretos / total_termos if total_termos > 0 else 0
    precisao_geral = (snomed_corretos + cid_corretos) / (2 * total_termos) if total_termos > 0 else 0

    expansoes_corretas = 0
    expansoes_totais = 0
    taxa_expansao = 0
    if 'expansao_correta' in df.columns:
        mask = df['abreviacao'] == True
        df_abrev = df[mask]
        if not df_abrev.empty:
            expansoes_totais = df_abrev['expansao_correta'].notna().sum()
            if expansoes_totais > 0:
                expansoes_corretas = df_abrev['expansao_correta'].sum()
                taxa_expansao = expansoes_corretas / expansoes_totais

    return {
        "total_termos_avaliados": total_termos,
        "termos_com_snomed": termos_com_snomed,
        "termos_com_cid": termos_com_cid,
        "snomed_corretos": snomed_corretos,
        "cid_corretos": cid_corretos,
        "precisao_snomed": precisao_snomed,
        "precisao_cid": precisao_cid,
        "precisao_geral": precisao_geral,
        "expansoes_totais": expansoes_totais,
        "expansoes_corretas": expansoes_corretas,
        "taxa_expansao": taxa_expansao
    }


def salvar_metricas_consolidadas(metricas_avaliacao, metricas_mapeamento):
    """Salva todas as métricas em um CSV único."""
    os.makedirs(Config.METRICS_FOLDER, exist_ok=True)

    linhas = []

    linhas.append({
        "categoria": "avaliacao",
        "total_termos_avaliados": metricas_avaliacao["total_termos_avaliados"],
        "VP": metricas_avaliacao["VP"],
        "FP": metricas_avaliacao["FP"],
        "FN": metricas_avaliacao["FN"],
        "precisao": metricas_avaliacao["precisao"],
        "recall": metricas_avaliacao["recall"],
        "f1": metricas_avaliacao["f1"]
    })

    linhas.append({
        "categoria": "mapeamento",
        "total_termos_avaliados": metricas_mapeamento["total_termos_avaliados"],
        "termos_com_snomed": metricas_mapeamento["termos_com_snomed"],
        "termos_com_cid": metricas_mapeamento["termos_com_cid"],
        "snomed_corretos": metricas_mapeamento["snomed_corretos"],
        "cid_corretos": metricas_mapeamento["cid_corretos"],
        "precisao_snomed": metricas_mapeamento["precisao_snomed"],
        "precisao_cid": metricas_mapeamento["precisao_cid"],
        "precisao_geral": metricas_mapeamento["precisao_geral"],
        "expansoes_totais": metricas_mapeamento["expansoes_totais"],
        "expansoes_corretas": metricas_mapeamento["expansoes_corretas"],
        "taxa_expansao": metricas_mapeamento["taxa_expansao"]
    })

    df_metricas = pd.DataFrame(linhas)
    output_path = os.path.join(Config.METRICS_FOLDER, "metricas_consolidadas.csv")
    df_metricas.to_csv(output_path, index=False, encoding='utf-8')
    print(f"\nMétricas consolidadas salvas em {output_path}")


def main():
    consolidated_csv = os.path.join(Config.OUTPUT_BASE, "consolidated_terms.csv")
    if not os.path.exists(consolidated_csv):
        print("\nArquivo consolidado não encontrado. Execute 03_merge_results.py primeiro.")
        return

    metricas_mapeamento = calcular_metricas_mapeamento(consolidated_csv)

    metricas_avaliacao = avaliar_modo(consolidated_csv, modo="relaxed", output_suffix="avaliacao", output_dir=Config.EVALUATION_BASE)

    salvar_metricas_consolidadas(metricas_avaliacao, metricas_mapeamento)

    print("\n\n=== RESUMO DAS MÉTRICAS DE MAPEAMENTO ===")
    print(f"Total de termos avaliados: {metricas_mapeamento['total_termos_avaliados']}")
    print(f"Termos com código SNOMED: {metricas_mapeamento['termos_com_snomed']}")
    print(f"Termos com código CID-11: {metricas_mapeamento['termos_com_cid']}")
    print(f"SNOMED - Acertos: {metricas_mapeamento['snomed_corretos']}/{metricas_mapeamento['total_termos_avaliados']} -> Precisão: {metricas_mapeamento['precisao_snomed']:.2%}")
    print(f"CID-11 - Acertos: {metricas_mapeamento['cid_corretos']}/{metricas_mapeamento['total_termos_avaliados']} -> Precisão: {metricas_mapeamento['precisao_cid']:.2%}")
    print(f"Precisão geral do mapeamento: {metricas_mapeamento['precisao_geral']:.2%}")
    if metricas_mapeamento['expansoes_totais'] > 0:
        print(f"Taxa de acerto de expansão de abreviações: {metricas_mapeamento['taxa_expansao']:.2%} ({metricas_mapeamento['expansoes_corretas']}/{metricas_mapeamento['expansoes_totais']})")

    print("\n\n=== RESUMO AVALIAÇÃO ===")
    print(f"Precisão: {metricas_avaliacao['precisao']:.2%} | Recall: {metricas_avaliacao['recall']:.2%} | F1: {metricas_avaliacao['f1']:.2%}")


if __name__ == "__main__":
    main()