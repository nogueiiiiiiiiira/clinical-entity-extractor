"""Aplica expressões regulares para refinar a anonimização, protegendo palavras seguras e placeholders."""

import sys
import os
import re
import json
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

SAFE_WORDS = {
    "metformina", "insulina", "glimepirida", "levotiroxina", "eritropoetina",
    "ondansetron", "sertralina", "enalapril", "carvedilol", "furosemida",
    "losartana", "atorvastatina", "sinvastatina", "aspirina", "captopril",
    "propranolol", "omeprazol", "azatioprina", "budesonida", "formoterol",
    "salbutamol", "tiotrópio", "alendronato", "digoxina", "warfarina",
    "dobutamina", "lactulose", "ácido ursodesoxicólico", "clínica", "hospital",
    "crm", "coren", "hc", "nph", "regular", "glargina", "asparte", "aas",
    "paracetamol", "dipirona", "ibuprofeno", "amoxicilina", "azitromicina",
    "prednisona", "dexametasona", "hidrocortisona", "ranitidina", "clonazepam",
    "diazepam", "alprazolam", "fluoxetina", "citalopram", "escitalopram"
}


def collapse_consecutive_placeholders(text: str) -> str:
    """Substitui sequências repetidas do mesmo placeholder por um único."""
    pattern = re.compile(r'\[([A-Z_]+)\](?:\s+\[\1\])+')
    while True:
        new_text = pattern.sub(r'[\1]', text)
        if new_text == text:
            break
        text = new_text
    text = re.sub(r'\s+', ' ', text)
    return text


PATTERNS = {
    'CONTATO': [
        (r'\(\d{2,3}\)\s*\d{4,5}-\d{4}', '[CONTATO]'),
        (r'[\w\.-]+@[\w\.-]+\.\w{2,}', '[CONTATO]')
    ],
    'DATA': [
        (r'\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b', '[DATA]'),
        (r'\b\d{1,2}[/-]\d{1,2}\b', '[DATA]'),
        (r'\b\d{1,2}\s+de\s+[a-zÀ-ú]+\s+de\s+\d{2,4}\b', '[DATA]')
    ],
    'HORÁRIO': [
        (r'\b\d{1,2}:\d{2}(:\d{2})?\s*(?:h|horas?)?\b', '[HORÁRIO]'),
        (r'\b\d{1,2}h\d{2}\b', '[HORÁRIO]')
    ],
    'IDs': [
        (r'\bCRM\s+(\d{5,7})\b', 'CRM [IDs]'),
        (r'\bHC\s*:\s*(\d{5,7})\b', 'HC: [IDs]'),
        (r'\bCoren\s+(\d{5,7})\b', 'Coren [IDs]'),
        (r'\bIdentificador\s+do\s+(?:paciente|atendimento)\s*:\s*(\d{6,10})\b', 'Identificador do paciente: [IDs]'),
        (r'\b(?:ID|Id)\s*:\s*(\d{5,10})\b', 'ID: [IDs]'),
        (r'\b\d{7,10}\b', '[IDs]')
    ],
    'PROFISSÃO': [
        (r'\b(?:Dr\.?|Dra\.?|Drª\.?|Sr\.?|Sra\.?|Enf\.?|Prof\.?|Téc\.\s*Enf\.?)\s+', r'[PROFISSÃO] '),
        (r'\b(?:professor(?:a)?|advogado(?:a)?|médic(?:o|a)|enfermeir(?:o|a)|engenheir(?:o|a)|contador(?:a)?|aposentado(?:a)?|cardiologista|endocrinologista|pneumologista|técnico\s+de\s+enfermagem)\b', '[PROFISSÃO]')
    ],
    'NOME': [
        (r'\bPaciente\s+([A-Z][a-zÀ-ú]+(?:\s+[A-Z][a-zÀ-ú]+){1,2})\b', r'Paciente [NOME]'),
        (r'\[PROFISSÃO\]\s+([A-Z][a-zÀ-ú]+(?:\s+[A-Z][a-zÀ-ú]+){0,2})\b', r'[PROFISSÃO] [NOME]')
    ],
    'LOCAL': [
        (r'\b(?:residente em|mora em|endereço:)\s+([\wÀ-ú]+(?:\s+[\wÀ-ú]+){1,4})\b', r'[LOCAL]'),
        (r'\b(?:em|de)\s+(?:São Paulo|Campinas|Rio de Janeiro|Vinhedo|Niterói|Santo Amaro|Botafogo|Copacabana)\b', r'[LOCAL]'),
        (r'\b(?:Rua|Avenida|Travessa|Praça|Bairro|Vila)\s+[\wÀ-ú]+(?:\s+[\wÀ-ú]+)*\b', '[LOCAL]')
    ],
    'ORGANIZAÇÃO': [
        (r'\b(?:Hospital|Clínica|Unidade|Centro|UBS|Laboratório)\s+(?:de\s+)?(?:da\s+)?[A-Z][a-zÀ-ú]+(?:\s+(?:de|da|do|e)\s+[A-Z][a-zÀ-ú]+)*', '[ORGANIZAÇÃO]')
    ],
    'IDADE': [
        (r'\b(9[0-9]|[1-9][0-9]{2})\s+anos\b', '[IDADE] anos')
    ]
}


def compile_patterns():
    """Compila as expressões regulares em uma lista ordenada por categoria."""
    compiled = []
    order = ['CONTATO','DATA','HORÁRIO','IDs','PROFISSÃO','NOME','LOCAL','ORGANIZAÇÃO','IDADE']
    for cat in order:
        for regex_str, repl in PATTERNS.get(cat, []):
            compiled.append((re.compile(regex_str, re.IGNORECASE), repl, cat))
    return compiled


COMPILED_REGEX = compile_patterns()


def apply_regex_preserve_placeholders_and_safe_words(text: str) -> tuple:
    """Aplica todas as regex preservando placeholders existentes e palavras seguras."""
    safe_pattern = re.compile(r'\b(' + '|'.join(re.escape(w) for w in SAFE_WORDS) + r')\b', re.IGNORECASE)
    safe_tokens = {}
    safe_counter = 0

    def protect_safe(m):
        nonlocal safe_counter
        token = f'__SAFE_{safe_counter}__'
        safe_tokens[token] = m.group(0)
        safe_counter += 1
        return token

    temp = safe_pattern.sub(protect_safe, text)
    temp = collapse_consecutive_placeholders(temp)

    placeholder_re = re.compile(r'\[[A-Z_]+\]')
    existing = placeholder_re.findall(temp)
    ph_tokens = {}
    ph_counter = 0

    def tokenize_ph(m):
        nonlocal ph_counter
        token = f'__PH_{ph_counter}__'
        ph_tokens[token] = m.group(0)
        ph_counter += 1
        return token

    temp = placeholder_re.sub(tokenize_ph, temp)

    for regex, repl, _ in COMPILED_REGEX:
        temp = regex.sub(repl, temp)

    for token, original in ph_tokens.items():
        temp = temp.replace(token, original)
    for token, original in safe_tokens.items():
        temp = temp.replace(token, original)

    temp = collapse_consecutive_placeholders(temp)

    final_phs = placeholder_re.findall(temp)
    initial_count = Counter(existing)
    final_count = Counter(final_phs)
    added = {ph: final_count[ph] - initial_count.get(ph,0) for ph in final_count if final_count[ph] > initial_count.get(ph,0)}
    removed = {ph: initial_count[ph] - final_count.get(ph,0) for ph in initial_count if initial_count[ph] > final_count.get(ph,0)}
    changes = {"added": added, "removed": removed}
    return temp, changes


def main() -> None:
    """Aplica regex a todos os textos anonimizados pelo LLM e atualiza os metadados."""
    os.makedirs(Config.REGEX_OUTPUT_FOLDER, exist_ok=True)
    os.makedirs(Config.METADATA_FOLDER, exist_ok=True)

    llm_files = [f for f in os.listdir(Config.LLM_OUTPUT_FOLDER) if f.endswith('.txt')]
    print(f"\nEncontrados {len(llm_files)} arquivos do LLM")

    for filename in llm_files:
        base = filename.replace('.txt', '')
        llm_path = os.path.join(Config.LLM_OUTPUT_FOLDER, filename)
        with open(llm_path, 'r', encoding='utf-8') as f:
            llm_text = f.read()

        regex_text, changes = apply_regex_preserve_placeholders_and_safe_words(llm_text)

        out_path = os.path.join(Config.REGEX_OUTPUT_FOLDER, f"{base}.txt")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(regex_text)

        meta_path = os.path.join(Config.METADATA_FOLDER, f"{base}.meta.json")
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        else:
            meta = {}
        meta["placeholder_changes"] = changes
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        print(f"\n[{base}] Regex aplicado, alterações: {changes}")

    print("\nRegex aplicado a todos os arquivos.")


if __name__ == "__main__":
    main()