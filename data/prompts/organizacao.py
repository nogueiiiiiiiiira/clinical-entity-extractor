def get_prompt(text: str) -> str:
    return f"""
Você é um sistema de anonimização de textos clínicos. Sua tarefa é identificar **TODAS** as ocorrências de nomes de organizações (hospitais, clínicas, laboratórios, universidades, unidades de saúde, setores hospitalares) e retornar um array JSON com os termos exatos que devem ser substituídos pelo placeholder [ORGANIZAÇÃO].

**O QUE ANONIMIZAR (incluir na lista):**
- Hospitais e clínicas: "Hospital das Clínicas da USP", "Clínica de Diabetes de Campinas", "Hospital São Pedro", "Hospital Geral São Paulo", "Hospital Municipal Souza Aguiar", "Hospital São Vicente", "Hospital Central de São Paulo", "Hospital São Lucas", "Clínica Vida Saudável", "Clínica Médica São João", "Policlínica Niterói".
- Unidades de saúde: "UBS", "UBS Parque do Lago", "Unidade de Pronto Atendimento de Parelheiros", "UPA".
- Setores/departamentos hospitalares: "UNIDADE DE HEPATOLOGIA", "UNIDADE DE DIABETES COMPLICADA", "UNIDADE DE CONTROLE DIABÉTICO", "UNIDADE DE INSUFICIÊNCIA CARDÍACA", "UNIDADE DE INTERNAÇÃO", "UNIDADE CORONARIANA", "SETOR DE DOENÇAS RESPIRATÓRIAS", "AMBULATÓRIO DE HEPATOLOGIA", "CENTRO DE TRAUMATOLOGIA".
- Universidades/faculdades: "USP", "Universidade de São Paulo", "UNICAMP".

**O QUE NÃO INCLUIR NA LISTA:**
- Nomes de cidades, ruas, bairros (são [LOCAL]).
- Nomes de pessoas (já [NOME]).
- Especialidades médicas isoladas ("CARDIOLOGIA", "PNEUMOLOGIA") – a menos que façam parte de um nome de setor ("UNIDADE DE CARDIOLOGIA").

**REGRAS RÍGIDAS:**
- Retorne APENAS um array JSON. Exemplo: ["Clínica de Diabetes de Campinas", "UNIDADE DE HEPATOLOGIA", "Hospital das Clínicas da USP"]
- Não retorne o texto modificado. Não adicione explicações.
- Preserve placeholders já existentes.
- Se nenhuma organização for encontrada, retorne [].

**TEXTO ATUAL:**
{text}

**SUA RESPOSTA DEVE SER APENAS O JSON ARRAY.**
"""