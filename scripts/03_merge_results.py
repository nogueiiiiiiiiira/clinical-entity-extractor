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
        print("Pasta de CSVs individuais não encontrada.")
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
        print("Nenhum CSV válido encontrado.")
        return
    df_mestre = pd.concat(lista_dfs, ignore_index=True)
    output_path = os.path.join(Config.OUTPUT_BASE, "consolidated_terms.csv")
    os.makedirs(Config.OUTPUT_BASE, exist_ok=True)
    df_mestre.to_csv(output_path, index=False, encoding='utf-8')
    print(f"Arquivo consolidado salvo em {output_path}")

    total_termos = len(df_mestre)
    termos_com_snomed = df_mestre["SCTID"].notna().sum()
    termos_com_cid = df_mestre["CID10"].notna().sum()
    snomed_corretos = df_mestre["SCTID_correto"].sum() if termos_com_snomed > 0 else 0
    cid_corretos = df_mestre["CID10_correto"].sum() if termos_com_cid > 0 else 0
    precisao_snomed = snomed_corretos / total_termos if total_termos > 0 else 0
    precisao_cid = cid_corretos / total_termos if total_termos > 0 else 0
    precisao_geral = (snomed_corretos + cid_corretos) / (2 * total_termos) if total_termos > 0 else 0

    print("\nRESULTADOS DO MAPEAMENTO")
    print(f"Total de termos avaliados: {total_termos}")
    print(f"Termos com código SNOMED: {termos_com_snomed} ({termos_com_snomed/total_termos:.2%})")
    print(f"Termos com código CID-11: {termos_com_cid} ({termos_com_cid/total_termos:.2%})")
    print(f"SNOMED - Acertos: {snomed_corretos}/{total_termos} -> Precisão: {precisao_snomed:.2%}")
    print(f"CID-11 - Acertos: {cid_corretos}/{total_termos} -> Precisão: {precisao_cid:.2%}")
    print(f"Precisão geral do mapeamento: {precisao_geral:.2%}")

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
                print(f"\nTAXA DE ACERTO DE EXPANSÃO DE ABREVIAÇÕES: {taxa_acerto:.2%} ({expansoes_corretas}/{expansoes_totais})")
                print(f"Expansões corretas (1): {expansoes_corretas}, incorretas (0): {expansoes_totais - expansoes_corretas}")
            else:
                print("\nNenhuma abreviação com validação de expansão encontrada.")
        else:
            print("\nNenhuma abreviação encontrada.")
    else:
        print("\nColuna 'expansao_correta' não encontrada – não foi possível calcular taxa de acerto de expansões.")

if __name__ == "__main__":
    main()