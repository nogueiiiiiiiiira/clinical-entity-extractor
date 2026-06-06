def get_prompt(text: str) -> str:
    return f"""
Você é um sistema de anonimização de textos clínicos. Sua tarefa é identificar **TODOS** os nomes próprios de pessoas no texto e retornar um array JSON com os termos exatos que devem ser substituídos pelo placeholder [NOME].

**O QUE ANONIMIZAR (incluir na lista):**
- Nomes completos ou parciais (com ou sem sobrenome) que identificam uma pessoa. Exemplos reais: "Amanda Silva", "João Martins", "Maria Aparecida Pereira", "Marco Silva", "André Menezes", "Paulo Andrade Neves", "Joaquim Pereira", "Julia Vasconcelos", "Lívia Barros Monteiro", "Beatriz Faria", "Paulo Sérgio Alencar", "Jorge Almeida", "Rafael Ferreira", "Renata Costa", "Marília Nunes", "Lucas Pereira", "Luana Santos", "Carlos Eduardo Rocha", "Miguel Andrade Gomes", "Pedro Alcantara Silva", "João Pereira Gomes", "João Francisco Martins", "Marina Ferreira Lima", "Joaquim Almeida Souza", "Maria Antonieta de Almeida", "Joana Ferreira Matos", "Roberto Carlos Alves", "Patricia Fernandes Louzada", "Marcos Ribeiro Alencar", "Antônia Lúcia Ferreira", "Roberto Nunes da Rocha", "João Ferreira Lima", "Antônio Figueiredo Barros", "Clara Rodrigues Gonçalves".
- Nomes precedidos ou seguidos por: paciente, Dr., Dra., Sr., Sra., enfermeiro, técnico, médico, psicólogo, nutricionista, residente (R1, R2, R3). Inclua apenas o nome, não o título (ex: para "Dr. André Menezes", liste "André Menezes").
- Nomes que aparecem após: "ID:", "Paciente:", "Responsável:", "Acompanhante:", "Familiar:", "Contato:", "Esposo:", "Filho:".
- Nomes em assinaturas.
- Cada aparição conta separadamente.

**O QUE NÃO INCLUIR NA LISTA:**
- Títulos de tratamento sozinhos (Dr., Dra., Sr., Sra., Enf., Téc.) – eles serão tratados pela categoria PROFISSÃO.
- Nomes de organizações, cidades, ruas.
- Nomes de medicamentos, doenças, exames.
- Dias da semana, meses, feriados.
- Siglas como "HIV", "DM", "HAS".

**REGRAS RÍGIDAS:**
- Retorne APENAS um array JSON. Exemplo: ["Amanda Silva", "João Martins", "André Menezes"]
- Não retorne o texto modificado. Não adicione explicações.
- Preserve placeholders já existentes.
- Se nenhum nome for encontrado, retorne [].

**TEXTO ATUAL:**
{text}

**SUA RESPOSTA DEVE SER APENAS O JSON ARRAY.**
"""