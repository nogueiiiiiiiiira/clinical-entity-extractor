def get_prompt(text: str) -> str:
    return f"""
Você é um sistema de anonimização de textos clínicos. Sua tarefa é identificar **TODAS** as ocorrências de profissões, títulos de tratamento, cargos e funções no texto e retornar um array JSON com os termos exatos que devem ser substituídos pelo placeholder [PROFISSÃO].

**O QUE ANONIMIZAR (incluir na lista):**
- Títulos de tratamento: Sr., Sra., Srta., Dr., Dra., Prof., Profª., Enf., Téc., Tec. Inclua o ponto se presente (ex: "Dr.", "Dra.", "Drª.").
- Profissões e cargos: médico, enfermeiro, técnico de enfermagem, psicólogo, nutricionista, assistente social, advogado, engenheiro, professor, contador, jornalista, designer, comerciante, eletricista, aposentado.
- Especialidades médicas: cardiologista, pneumologista, endocrinologista, nefrologista, neurologista, psiquiatra, oncologista, cirurgião, infectologista.
- Cargos hierárquicos: chefe, supervisor, coordenador, diretor, plantonista, residente (R1, R2, R3).
- Formas abreviadas mesmo sem ponto ou com ponto extra: "Dr", "Dr.", "dra", "Dra.", "sr", "Sr.", "enf", "Enf.", "tec", "Téc.".
- Profissões compostas devem ser incluídas como um único termo: "médico cardiologista", "técnico de enfermagem", "R2 ENDO", "R3 GST", "R1 CAR", "R2 PNEU", "R3 PNEUM", "R2 GAST", "R1 ORT", "R2 CDL", "R3 Car INT", "R2 END", "R2 PN", "R2 PNL", "R1 CLC".

**O QUE NÃO INCLUIR NA LISTA:**
- Palavras como "paciente", "familiar", "acompanhante", "responsável" – não são profissões.
- Nomes de pessoas (já [NOME]).
- Nomes de organizações, hospitais, clínicas.
- Nomes de medicamentos, doenças, exames.
- Nomes de cidades, ruas, bairros (já [LOCAL]).

**REGRAS RÍGIDAS:**
- Retorne APENAS um array JSON. Exemplo: ["Dr.", "médico cardiologista", "técnico de enfermagem", "R2 ENDO"]
- Não retorne o texto modificado. Não adicione explicações.
- Preserve placeholders já existentes.
- Se nenhuma profissão/título for encontrado, retorne [].

**TEXTO ATUAL:**
{text}

**SUA RESPOSTA DEVE SER APENAS O JSON ARRAY.**
"""