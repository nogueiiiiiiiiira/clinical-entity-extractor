def get_prompt(text: str) -> str:
    return f"""
Você é um sistema de anonimização de textos clínicos. Sua tarefa é identificar **TODAS** as informações de localização geográfica (endereços, cidades, estados, bairros, ruas, CEPs, números de quarto/leito) no texto e retornar um array JSON com os termos exatos que devem ser substituídos pelo placeholder [LOCAL].

**O QUE ANONIMIZAR (incluir na lista):**
- Cidades: Vinhedo, Campinas, São Paulo, Rio de Janeiro, Belo Horizonte, Curitiba, Niterói, Santo Amaro, etc.
- Estados e siglas: SP, RJ, MG, PR, BA.
- Bairros, vilas, distritos: Centro, Vila Mariana, Copacabana, Botafogo, Santa Lúcia, São José, Nova Esperança, Parelheiros.
- Ruas e avenidas: Rua das Flores, Avenida Brasil, Rua Afonso Pena, Rua dos Jacarandás, Avenida Paulista, Rua da Paz, Rua das Acácias, Rua dos Álamos, Rua das Palmeiras (incluindo números e complementos: "123", "apto 201", "345", "520", "100", "45").
- CEPs: 20031-200, 01310-000.
- Números de quarto/leito: "quarto 405", "leito 204".

**O QUE NÃO INCLUIR NA LISTA:**
- Nomes de organizações (hospitais, clínicas, laboratórios) – eles serão tratados pela categoria ORGANIZAÇÃO.
- Nomes de pessoas, medicamentos, doenças.

**REGRAS RÍGIDAS:**
- Retorne APENAS um array JSON. Exemplo: ["Vinhedo", "Rua das Flores, 123, Centro, São Paulo, SP", "quarto 405"]
- Não retorne o texto modificado. Não adicione explicações.
- Preserve placeholders já existentes.
- Se nenhuma informação de local for encontrada, retorne [].

**TEXTO ATUAL:**
{text}

**SUA RESPOSTA DEVE SER APENAS O JSON ARRAY.**
"""