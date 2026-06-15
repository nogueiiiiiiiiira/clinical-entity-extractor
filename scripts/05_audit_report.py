"""Gera relatorios de auditoria para validar as decisoes do LLM."""

import sys
import os
import json
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config


def gerar_relatorio_auditoria():
    """Gera um relatorio legivel para humanos sobre as decisoes do LLM."""
    
    output_dir = os.path.join(Config.OUTPUT_BASE, "auditoria")
    os.makedirs(output_dir, exist_ok=True)
    
    fp_rejected_path = os.path.join(Config.LOGS_FOLDER, "filtered_terms_log.txt")
    if os.path.exists(fp_rejected_path):
        with open(fp_rejected_path, 'r', encoding='utf-8') as f:
            rejected = [line.strip() for line in f.readlines()]
        
        print(f"\nTermos rejeitados pelo juiz: {len(rejected)}")
        
        termos_curtos = []
        termos_estranhos = []
        termos_normais = []
        
        for item in rejected:
            if '|' in item:
                parts = item.split('|')
                termo = parts[1] if len(parts) > 1 else item
            else:
                termo = item
            
            if len(termo) < 4:
                termos_curtos.append(termo)
            elif any(c in termo for c in '!@#$%^&*'):
                termos_estranhos.append(termo)
            else:
                termos_normais.append(termo)
        
        print(f"  - Termos muito curtos (<4 chars): {len(set(termos_curtos))}")
        print(f"  - Termos com caracteres estranhos: {len(set(termos_estranhos))}")
        print(f"  - Termos normais (podem precisar de contexto): {len(set(termos_normais))}")
        
        df_rejected = pd.DataFrame({
            "termo_rejeitado": rejected,
            "possivel_causa": [
                "termo_curto" if len(t) < 4 else "caractere_estranho" if any(c in t for c in '!@#$%^&*') else "sem_contexto"
                for t in rejected
            ]
        })
        df_rejected.to_csv(os.path.join(output_dir, "termos_rejeitados.csv"), 
                           index=False, encoding='utf-8')
    
    llm_responses_dir = Config.LLM_RESPONSES_FOLDER
    if os.path.exists(llm_responses_dir):
        extracoes = []
        for filename in os.listdir(llm_responses_dir):
            if 'extraction' in filename and filename.endswith('.json'):
                filepath = os.path.join(llm_responses_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    extracoes.append({
                        "arquivo": filename,
                        "modelo": data.get("model", ""),
                        "tamanho_prompt": len(data.get("prompt", "")),
                        "tamanho_resposta": len(data.get("response", "")),
                        "timestamp": data.get("timestamp", "")
                    })
        
        print(f"\nRespostas do LLM de extracao: {len(extracoes)}")
        if extracoes:
            df_extractions = pd.DataFrame(extracoes)
            df_extractions.to_csv(os.path.join(output_dir, "respostas_llm_extracao.csv"), 
                                  index=False, encoding='utf-8')
    
    decisions_dir = os.path.join(Config.LOGS_FOLDER, "decisions")
    if os.path.exists(decisions_dir):
        mapeamentos = []
        for filename in os.listdir(decisions_dir):
            if 'mapping_validation' in filename and filename.endswith('.json'):
                filepath = os.path.join(decisions_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    mapeamentos.append({
                        "timestamp": data.get("timestamp", ""),
                        "termo": data.get("input", {}).get("termo_original", ""),
                        "codigo": data.get("input", {}).get("codigo", ""),
                        "resultado": data.get("output", ""),
                        "cache_hit": data.get("cache_hit", False)
                    })
        
        print(f"\nValidacoes de mapeamento: {len(mapeamentos)}")
        if mapeamentos:
            df_mappings = pd.DataFrame(mapeamentos)
            df_mappings.to_csv(os.path.join(output_dir, "validacoes_mapeamento.csv"), 
                               index=False, encoding='utf-8')
            
            aceitos = df_mappings[df_mappings['resultado'] == '1']
            rejeitados = df_mappings[df_mappings['resultado'] == '0']
            print(f"  - Mapeamentos aceitos: {len(aceitos)}")
            print(f"  - Mapeamentos rejeitados: {len(rejeitados)}")
    
    resumo = {
        "data_geracao": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_termos_rejeitados_fp": len(rejected) if 'rejected' in dir() else 0,
        "total_respostas_llm_extracao": len(extracoes) if 'extracoes' in dir() else 0,
        "total_validacoes_mapeamento": len(mapeamentos) if 'mapeamentos' in dir() else 0
    }
    
    df_resumo = pd.DataFrame([resumo])
    df_resumo.to_csv(os.path.join(output_dir, "resumo_auditoria.csv"), 
                     index=False, encoding='utf-8')
    
    print(f"\nRelatorios salvos em: {output_dir}")
    
    return output_dir


def gerar_comparacao_gold_vs_predito():
    """Gera uma comparacao entre o que o LLM extraiu e o gold standard, usando o arquivo de avaliacao relaxada."""
    
    avaliacao_path = os.path.join(Config.EVALUATION_RELAXADA, "avaliacao_detalhada_relaxada.xlsx")
    if not os.path.exists(avaliacao_path):
        avaliacao_path = os.path.join(Config.EVALUATION_RELAXADA, "avaliacao_detalhada_relaxada.csv")
        if not os.path.exists(avaliacao_path):
            print("\nArquivo de avaliacao relaxada nao encontrado. Execute 04_evaluate.py primeiro.")
            return
    
    if avaliacao_path.endswith('.xlsx'):
        df = pd.read_excel(avaliacao_path, engine='openpyxl')
    else:
        df = pd.read_csv(avaliacao_path)
    
    if 'classificacao' not in df.columns:
        print("\nArquivo de avaliacao nao contem coluna 'classificacao'.")
        return
    
    output_dir = os.path.join(Config.OUTPUT_BASE, "auditoria", "comparacao")
    os.makedirs(output_dir, exist_ok=True)
    
    vp_df = df[df['classificacao'] == 'VP']
    if not vp_df.empty:
        vp_df[['termoAnalisado', 'semClin_textoAnalisado', 'categoria']].to_csv(
            os.path.join(output_dir, "acertos_vp.csv"), index=False, encoding='utf-8'
        )
        print(f"\nAcertos (VP): {len(vp_df)}")
    
    fp_df = df[df['classificacao'] == 'FP']
    if not fp_df.empty:
        fp_df[['termoAnalisado', 'categoria', 'textoPrompt']].to_csv(
            os.path.join(output_dir, "falsos_positivos_fp.csv"), index=False, encoding='utf-8'
        )
        print(f"\nFalsos positivos (extraiu errado): {len(fp_df)}")
    
    fn_df = df[df['classificacao'] == 'FN']
    if not fn_df.empty:
        fn_df[['semClin_textoAnalisado', 'semClin_categoria']].to_csv(
            os.path.join(output_dir, "falsos_negativos_fn.csv"), index=False, encoding='utf-8'
        )
        print(f"\nFalsos negativos (deixou de extrair): {len(fn_df)}")


def main():
    gerar_relatorio_auditoria()
    gerar_comparacao_gold_vs_predito()

if __name__ == "__main__":
    main()