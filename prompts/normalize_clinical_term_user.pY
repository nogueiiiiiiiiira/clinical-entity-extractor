USER_TEMPLATE = """Normalize o termo clínico a seguir removendo doses, unidades, frequências e deixando apenas o conceito principal. 

Exemplo: 

"enalapril 10mg" -> "enalapril". 

Retorne apenas o termo normalizado.
Termo: {term}"""