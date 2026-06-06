def get_prompt(text: str) -> str:
    return f"""
Você é um sistema de anonimização de textos clínicos. Sua tarefa é identificar **TODAS** as ocorrências de datas (absolutas ou parciais) no texto fornecido e retornar um array JSON com os termos exatos que devem ser substituídos pelo placeholder [DATA].

**O QUE ANONIMIZAR (incluir na lista):**
- Datas completas com barras, hífens ou pontos:
  * dd/mm/aaaa: 12/10/2022, 05/09/2022, 16/10/2024, 22/12/2024, 27/11/2022, 20/10/24, 21/10/2024, 15/11/2024, 16/11/2024, 13/10/2024, 14/10/2024, 12/10/2024, 08/01/2025, 22/09/2022, 20/11/2022, 12/03/2024, 15/03/2022, 30/01/2019, etc.
  * dd/mm/aa: 12/03/24, 07/01/25
  * dd-mm-aaaa, dd.mm.aaaa
- Datas parciais:
  * só dia e mês: 12/10, 16/10, 14/10, 17/10, 12/03, 07/01
  * só mês e ano: 10/2022, 12/2024
- Datas por extenso (com ou sem ano):
  * "12 de outubro de 2022", "5 de setembro de 2022", "12 de outubro"
- Cada aparição conta separadamente.

**O QUE NÃO INCLUIR NA LISTA:**
- Horários (09:30, 14h20) – categoria HORÁRIO.
- Idades (50 anos, 63 anos) – categoria IDADE (somente >90).
- Números de telefone, CRM, Coren, HC.
- Escores FUGULIN/MORSE.
- Pesos, alturas, doses.

**REGRAS RÍGIDAS:**
- Retorne APENAS um array JSON. Exemplo: ["12/10/2022", "16/10/2024", "12 de outubro"]
- Não retorne o texto modificado. Não adicione explicações.
- Preserve placeholders já existentes.
- Se nenhuma data for encontrada, retorne [].

**TEXTO ATUAL:**
{text}

**SUA RESPOSTA DEVE SER APENAS O JSON ARRAY.**
"""