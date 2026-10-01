"""Frases vagas: referência a jurisprudência ou lei sem identificador ("a jurisprudência pacífica desta Corte").

A página de Dados da competição chama essas referências de `incompleta` ("informação insuficiente para
formular a consulta"), mas o gabarito distribuído — e o scorer do dev — as exclui. Por isso ficam atrás da
flag --vagas: a variante V as emite, a R não, e o LB público do conjunto cego decide qual vale.

O gerador põe cada citação num "slot" de frase ("Reforça o argumento o {CIT}, de resto…"). Quando o slot
recebe uma referência vaga em vez de uma citação, o sintagma nominal do slot é a frase vaga. Duas fontes:
  1. inventário — as 15 frases vagas vistas no dev, tolerantes a acento/OCR/quebra de linha;
  2. generalização — o sintagma nominal depois de um slot conhecido, se o núcleo for um termo jurídico.
O span é o sintagma sem o artigo inicial.
"""
import re

from .extract import Candidata, zona_cabecalho
from .textnorm import frase, fuzzy

# frases vagas do dev (o conjunto de moldes do gerador)
FILLERS = [
    ("jurisprudência pacífica desta Corte", "jurisprudencia"),
    ("jurisprudência consolidada dos tribunais superiores", "jurisprudencia"),
    ("entendimento sumulado sobre a matéria", "jurisprudencia"),
    ("precedente firmado em sede de recurso repetitivo", "jurisprudencia"),
    ("orientação jurisprudencial da Corte Superior", "jurisprudencia"),
    ("precedentes desta Casa em situações análogas", "jurisprudencia"),
    ("recente acórdão da Segunda Turma", "jurisprudencia"),
    ("reiterados precedentes do Superior Tribunal de Justiça", "jurisprudencia"),
    ("verbete sumular aplicável à espécie", "jurisprudencia"),
    ("dispositivo constitucional invocado na origem", "lei"),
    ("dispositivo legal de regência", "lei"),
    ("lei que disciplina a prescrição no caso", "lei"),
    ("artigo correspondente do Código de Processo Civil", "lei"),
    ("legislação de regência da matéria", "lei"),
    ("normas de regência da matéria", "lei"),
]

# início de frase dos slots do gerador (minerados do contexto das citações do gabarito), sem o artigo final
SLOTS = [
    "A hipótese atrai a incidência", "A orientação firmada", "A parte recorrente apoia-se",
    "A pretensão encontra amparo expresso", "A propósito, veja-se", "A tese encontra respaldo",
    "A tese ora sustentada decorre diretamente", "Ampara a pretensão", "Ao apreciar",
    "Aplica-se à espécie, mutatis mutandis, o quanto decidido", "Como já se reconheceu", "Como se depreende",
    "Confira-se, a propósito,", "Corrobora essa leitura", "Cumpre destacar", "Cumpre lembrar",
    "Deixou o Tribunal de origem de aplicar", "Em caso análogo,", "Idêntica conclusão foi adotada",
    "Impõe-se a observância", "Incide, na espécie,", "Invoca-se, ainda,", "Merece registro",
    "Milita em favor da parte", "Nesse exato sentido caminha", "Nesse exato sentido caminham",
    "Nesse sentido, confira-se o julgamento", "Nos exatos termos", "Não destoa desse entendimento",
    "Não se pode ignorar", "O acórdão recorrido diverge frontalmente do que assentado",
    "O julgado hostilizado desconsiderou por completo", "Reforça o argumento", "Registre-se, por oportuno,",
    "Requer-se, com fundamento", "Também", "Toda a construção defensiva repousa", "Vale invocar",
    "Violou o acórdão recorrido",
]
_ARTIGOS = ["o", "a", "os", "as", "no", "na", "nos", "nas", "do", "da", "dos", "das", "ao", "à", "aos", "às"]

# núcleos de uma referência vaga (primeira ou segunda palavra do sintagma)
NUCLEOS = ["jurisprudência", "entendimento", "entendimentos", "precedente", "precedentes", "orientação",
           "verbete", "súmula", "enunciado", "dispositivo", "dispositivos", "lei", "leis", "legislação",
           "norma", "normas", "artigo", "acórdão", "acórdãos", "julgado", "julgados", "tese", "preceito",
           "diploma", "código", "decisão", "decisões", "jurisprudências"]

_ART = r"(?:" + "|".join(fuzzy(a) for a in sorted(_ARTIGOS, key=len, reverse=True)) + r")"
_SLOT = r"(?:" + "|".join(frase(s) for s in sorted(SLOTS, key=len, reverse=True)) + r")"
_FILLER = r"(?:" + "|".join(frase(f) for f, _ in sorted(FILLERS, key=lambda x: -len(x[0]))) + r")"
_NUCLEO = r"(?:" + "|".join(fuzzy(n) for n in sorted(NUCLEOS, key=len, reverse=True)) + r")"
# fronteira do sintagma: pontuação ou as continuações típicas dos slots
_FRONTEIRA = (r"(?:[,.;:()\n]|\s+(?:" + "|".join(frase(x) for x in [
    "para", "que", "sob pena", "à qual", "ao qual", "aos quais", "às quais", "de resto", "no ponto", "cuja", "cujo",
    "de clareza", "invocado", "invocada", "de aplicação", "embora", "em que", "onde", "segundo o qual",
    "segundo a qual", "a qual", "o qual"]) + r")\b)")

_PAL = r"[A-Za-zÀ-ÿ0-9'´`-]+"
RE_SLOT_FILLER = re.compile(rf"(?<![A-Za-zÀ-ÿ]){_SLOT}\s+{_ART}\s+(?P<sn>{_FILLER})(?![A-Za-zÀ-ÿ])", re.I)
RE_SLOT_GENERICO = re.compile(
    rf"(?<![A-Za-zÀ-ÿ]){_SLOT}\s+{_ART}\s+(?P<sn>(?:{_PAL}\s+)?{_NUCLEO}(?![A-Za-zÀ-ÿ])(?:(?!{_FRONTEIRA})\s+{_PAL}){{0,10}})",
    re.I)
RE_FILLER = re.compile(rf"(?<![A-Za-zÀ-ÿ]){_FILLER}(?![A-Za-zÀ-ÿ])", re.I)


def _tipo(trecho: str) -> str:
    return "lei" if re.search(r"(?i)\b(?:dispositiv|lei|legisla|norma|artigo|preceito|diploma|c[óo]digo)", trecho) \
        else "jurisprudencia"


def extrair_vagas(texto: str, ocupados: list[tuple[int, int]]) -> list[Candidata]:
    """Frases vagas fora do cabeçalho e que não se sobrepõem a nenhuma citação já extraída."""
    fim_cab = zona_cabecalho(texto)
    achadas: dict[int, Candidata] = {}

    def add(ini: int, fim: int, fonte: str) -> None:
        trecho = texto[ini:fim]
        if ini < fim_cab or re.search(r"\d", trecho) or len(trecho.split()) < 2:
            return
        if any(ini < f and i < fim for i, f in ocupados):
            return
        if ini not in achadas:
            achadas[ini] = Candidata(ini, fim, "vaga", {"tipo": _tipo(trecho), "fonte": fonte}, 0)

    for m in RE_SLOT_FILLER.finditer(texto):
        add(m.start("sn"), m.end("sn"), "inventario")
    for m in RE_SLOT_GENERICO.finditer(texto):
        add(m.start("sn"), m.end("sn"), "slot")
    for m in RE_FILLER.finditer(texto):
        add(m.start(), m.end(), "inventario")
    # a mesma frase achada por duas fontes: fica o primeiro início (spans podem diferir no fim)
    out = []
    for c in sorted(achadas.values(), key=lambda c: (c.inicio, -c.fim)):
        if out and c.inicio < out[-1].fim:
            continue
        out.append(c)
    return out
