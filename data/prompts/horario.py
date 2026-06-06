def get_prompt(text: str) -> str:
    return f"""
Você é um sistema de anonimização de textos clínicos. Sua tarefa é identificar **TODAS** as ocorrências de horários absolutos (momentos específicos do dia) e retornar um array JSON com os termos exatos que devem ser substituídos pelo placeholder [HORÁRIO].

**O QUE ANONIMIZAR (incluir na lista):**
- Horários com dois pontos: 09:30, 15:30, 16:20, 14:50, 11:15, 21:45, 23:50, 03:27, 07:50, 08:15, 10:45, 11:35, 12:20, 13:30, 14:10, 14:25, 15:15, 16:10, 21:40, 21:50, 23:15, 02:30, 02:45, etc.
- Horários com "h" ou "hora": 10h, 14h, 09h, 16h, 10h30, 10h30min, 14h20, 11h45min, 12H10, 12H0, 12H15, 03h45min, 09h45min, 08h00min, 23h15.
- Horários com ":h" ou "hs": 14:20hs, 02:30hs.
- Horários precedidos de "às" ou "por volta das" – inclua o horário apenas (ex: "09:30" para "às 09:30").

**O QUE NÃO INCLUIR NA LISTA:**
- Durações: "por 2 horas", "jejum de 12h", "cirurgia durou 4h30". Não anonimize durações.
- Datas, idades, telefones, IDs.

**REGRAS RÍGIDAS:**
- Retorne APENAS um array JSON. Exemplo: ["09:30", "14h20", "11h45min", "21:45"]
- Não retorne o texto modificado. Não adicione explicações.
- Preserve placeholders já existentes.
- Se nenhum horário absoluto for encontrado, retorne [].

**TEXTO ATUAL:**
{text}

**SUA RESPOSTA DEVE SER APENAS O JSON ARRAY.**
"""