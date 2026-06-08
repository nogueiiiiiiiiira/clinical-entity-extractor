"""Consolida todos os CSVs individuais em um arquivo mestre e calcula estatísticas de mapeamento e expansão."""

import sys
import os
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config


def main():
    """Executa a consolidação dos CSVs individuais e exibe estatísticas."""
    csv_individual_dir = Config.CSV_INDIVIDUAL_FOLDER
    if not os.path.exists(csv_individual_dir):
        print("\nPasta de CSVs individuais não encontrada.")
        return

    lista_dfs = []
    for narrative_base in os.listdir(csv_individual_dir):
        subdir = os.path.join(csv_individual_dir, narrative_base)
        if not os.path.isdir(subdir):
            continue

        csv_path = os.path.join(subdir, "extracted_terms.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            if 'erro' not in df.columns:
                lista_dfs.append(df)

    if not lista_dfs:
        print("\nNenhum CSV válido encontrado.")
        return

    df_mestre = pd.concat(lista_dfs, ignore_index=True)
    output_path = os.path.join(Config.OUTPUT_BASE, "consolidated_terms.csv")
    os.makedirs(Config.OUTPUT_BASE, exist_ok=True)
    df_mestre.to_csv(output_path, index=False, encoding='utf-8')
    print(f"\nArquivo consolidado salvo em {output_path}")

    total_termos = len(df_mestre)

    termos_com_snomed = df_mestre["SCTID"].notna().sum() if "SCTID" in df_mestre.columns else 0
    snomed_corretos = (
        df_mestre["SCTID_correto"].sum() if ("SCTID_correto" in df_mestre.columns and termos_com_snomed > 0) else 0
    )

    # Preferir CID11 se existir; senão usar CID10 como fallback (legado)
    cid_code_col = "CID11" if "CID11" in df_mestre.columns else "CID10"
    cid_correct_col = "CID11_correto" if "CID11_correto" in df_mestre.columns else "CID10_correto"

    termos_com_cid = df_mestre[cid_code_col].notna().sum() if cid_code_col in df_mestre.columns else 0
    cid_corretos = (
        df_mestre[cid_correct_col].sum() if (cid_correct_col in df_mestre.columns and termos_com_cid > 0) else 0
    )


    precisao_snomed = snomed_corretos / total_termos if total_termos > 0 else 0
    precisao_cid = cid_corretos / total_termos if total_termos > 0 else 0
    precisao_geral = (snomed_corretos + cid_corretos) / (2 * total_termos) if total_termos > 0 else 0

    print("\n\nRESULTADOS DO MAPEAMENTO")
    print(f"\nTotal de termos avaliados: {total_termos}")
    print(f"\nTermos com código SNOMED: {termos_com_snomed} ({termos_com_snomed/total_termos:.2%})")
    print(f"\nTermos com código CID-11: {termos_com_cid} ({termos_com_cid/total_termos:.2%})")
    print(f"\nSNOMED - Acertos: {snomed_corretos}/{total_termos} -> Precisão: {precisao_snomed:.2%}")
    print(f"\nCID-11 - Acertos: {cid_corretos}/{total_termos} -> Precisão: {precisao_cid:.2%}")
    print(f"\nPrecisão geral do mapeamento: {precisao_geral:.2%}")

    expansoes_corretas = 0
    expansoes_totais = 0
    if 'expansao_correta' in df_mestre.columns:
        mask = df_mestre['abreviacao'] == True
        df_abrev = df_mestre[mask]
        if not df_abrev.empty:
            expansoes_totais = df_abrev['expansao_correta'].notna().sum()
            if expansoes_totais > 0:
                expansoes_corretas = df_abrev['expansao_correta'].sum()
                taxa_acerto = expansoes_corretas / expansoes_totais
                print(f"\n\nTAXA DE ACERTO DE EXPANSÃO DE ABREVIAÇÕES: {taxa_acerto:.2%} ({expansoes_corretas}/{expansoes_totais})")
                print(f"\nExpansões corretas (1): {expansoes_corretas}, incorretas (0): {expansoes_totais - expansoes_corretas}")
            else:
                print("\n\nNenhuma abreviação com validação de expansão encontrada.")
        else:
            print("\n\nNenhuma abreviação encontrada.")
    else:
        print("\n\nColuna 'expansao_correta' não encontrada – não foi possível calcular taxa de acerto de expansões.")


if __name__ == "__main__":
    main()

