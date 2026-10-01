"""Banco extra de treino para o Laya: moldes e frases vagas escritos de forma independente, DISJUNTOS dos do
conjunto adversarial (stress_adv.SLOTS_NOVOS / VAGAS_NOVAS), para que o adversarial continue sendo teste honesto.
Gera frases A (citação identificada, renderizada pelo gerador de estresse), B (referência vaga) e C (negativos
difíceis: termos jurídicos sem invocar fonte). Uso: chamado por laya_data.py --extra.
"""
import random

MOLDES = [
    "Em abono dessa tese, colhe-se {A} {X}, cujo teor se aplica integralmente.",
    "A matéria foi bem equacionada n{A} {X}.",
    "Oportuno transcrever, nesse ponto, {A} {X}.",
    "Esse é o sentido d{A} {X}, que não comporta outra leitura.",
    "Conforme salientado n{A} {X}, o pedido merece acolhida.",
    "Remete-se, por brevidade, a{A} {X}.",
    "Tal entendimento harmoniza-se com {A} {X}.",
    "Calha lembrar {A} {X}, de todo aplicável ao caso.",
    "Dessume-se d{A} {X} que a pretensão é legítima.",
    "Mostra-se pertinente invocar {A} {X} na espécie.",
    "Como bem pontuado n{A} {X}, a questão está superada.",
    "Assim já se manifestou {A} {X}, com acerto.",
]
VAGAS = [
    ("a", "jurisprudência sedimentada deste Tribunal"), ("o", "entendimento predominante na Corte"),
    ("os", "precedentes da Terceira Turma"), ("a", "orientação jurisprudencial prevalente"),
    ("o", "enunciado sumular pertinente"), ("a", "legislação federal aplicável à matéria"),
    ("o", "diploma legal que rege a espécie"), ("a", "norma constitucional pertinente"),
    ("os", "julgados mais recentes desta Corte"), ("o", "precedente vinculante sobre o tema"),
    ("a", "súmula editada sobre a matéria"), ("o", "preceito legal invocado pela defesa"),
    ("os", "dispositivos legais indicados na petição"), ("a", "jurisprudência iterativa das Cortes Superiores"),
    ("o", "entendimento firmado pelo órgão especial"), ("a", "lei processual de regência"),
]
NEGATIVOS = [
    "A tese recursal não merece prosperar, pelos fundamentos a seguir expostos.",
    "O acórdão recorrido analisou detidamente a prova produzida nos autos.",
    "A decisão agravada deve ser mantida por seus próprios fundamentos.",
    "Não houve violação a qualquer dispositivo, como se demonstrará.",
    "A parte recorrente limita-se a reiterar os argumentos já rechaçados.",
    "A sentença examinou todas as teses deduzidas pela defesa.",
    "O julgamento observou o devido processo legal e a ampla defesa.",
    "A matéria de fundo não foi objeto de prequestionamento.",
    "A defesa apresentou memoriais tempestivamente.",
    "O Ministério Público opinou pelo desprovimento do recurso.",
    "Os embargos foram opostos dentro do prazo legal.",
    "A instrução processual transcorreu sem intercorrências.",
    "Cumpre examinar, agora, o mérito da controvérsia.",
    "A leitura atenta dos autos revela a fragilidade da acusação.",
]


def gerar(ger, rng: random.Random, n_a: int, n_b: int, n_c: int) -> list[tuple[str, str]]:
    out = []
    for _ in range(n_b):
        art, x = rng.choice(VAGAS)
        out.append((rng.choice(MOLDES).replace("{A}", art).replace("{X}", x), "B"))
    for _ in range(n_a):
        t = rng.choice([ger.real, ger.real, ger.inventada, ger.incompleta, ger.lei_real])(rng.random() < 0.5)[0]
        art = "a" if t.lower().startswith(("súm", "sum", "rcl", "recl", "apel")) else "o"
        out.append((rng.choice(MOLDES).replace("{A}", art).replace("{X}", t).replace("\n", " "), "A"))
    for _ in range(n_c):
        out.append((rng.choice(NEGATIVOS), "C"))
    return out
