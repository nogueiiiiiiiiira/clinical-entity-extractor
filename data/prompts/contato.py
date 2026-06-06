def get_prompt(text: str) -> str:
    return f"""
Você é um sistema de anonimização de textos clínicos. Sua tarefa é identificar **TODAS** as ocorrências de informações de contato no texto fornecido e retornar um array JSON com os termos exatos que devem ser substituídos pelo placeholder [CONTATO].

**O QUE ANONIMIZAR (incluir na lista):**
- Telefones em qualquer formato:
  * Com DDD: (11) 98765-4321, (19) 99876-5432, (21) 99999-8888, (31) 99876-1234, (41) 98765-4321
  * Sem DDD: 98765-4321, 987654321, 98765.4321
  * Com código internacional: +55 11 98765-4321, 0055 11 987654321
  * Com ramal: (11) 98765-4321 ramal 123
  * Precedidos de palavras como "telefone:", "tel.:", "celular:", "whatsapp:", "contato:", "fone:"
- E-mails em qualquer formato:
  * nome@dominio.com, nome.sobrenome@empresa.com.br, nome_usuario@servico.net
  * Exemplos reais: joao.martins@example.com, julia.vasconcelos@gmail.com, jorge.almeida@gmail.com, marilia.nunes@example.com, luana.santos@example.com, carlos.rocha@gmail.com, miguel.gomes@medico.com.br, pedro.silva@example.com, joana.soares@hospital.org, contato.marinalima@gmail.com, joaquim.almeida@gmail.com, marialmeida@hotmail.com, joana.matos@mail.com, roberto.alves@gmail.com, patricia.louzada@gmail.com, roberto.nunes@advocacia.com, antonia.ferreira@mail.com, antonio.fig.barros@gmail.com, leticia.pn@gmail.com, joao.lima63@example.com, anacarolina@odontoclinica.com, joaquim.pereira@exemplo.com, elisa.machado@gmail.com

**O QUE NÃO INCLUIR NA LISTA:**
- Números que não sejam de contato: idades, pesos, alturas, doses, horários, datas, escores clínicos (FUGULIN, MORSE), IDs profissionais (CRM, Coren), números de quarto/leito, CEPs.
- Palavras que acompanham o contato (ex: "telefone:", "email:") – inclua apenas o número ou endereço em si.

**REGRAS RÍGIDAS:**
- Retorne APENAS um array JSON. Exemplo: ["(11) 98765-4321", "joao.martins@example.com"]
- Não retorne o texto modificado. Não adicione explicações.
- Preserve placeholders já existentes ([NOME], [DATA], etc.) – você não precisa fazer nada com eles.
- Se nenhum contato for encontrado, retorne uma lista vazia: []

**TEXTO ATUAL:**
{text}

**SUA RESPOSTA DEVE SER APENAS O JSON ARRAY.**
"""