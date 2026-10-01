"""Extração de candidatas a citação direto sobre o texto original (offsets nativos em codepoints)."""
import re
from dataclasses import dataclass, field

from .aliases import CADEIA, DO, EM, LEI, UF, UFS, _TRIB_SIMPLES
from .textnorm import CH, NUMERO, RE_NUMERO, H, chave_numero, frase, fuzzy


@dataclass
class Candidata:
    inicio: int
    fim: int
    kind: str                      # numerada | processo_cnj | hifenizada | sumula | tema | lei | incompleta | vaga
    grupos: dict = field(default_factory=dict)
    prioridade: int = 0

    @property
    def tamanho(self):
        return self.fim - self.inicio


_MARCADOR = r"(?:(?-i:n)\.?\s*[º°oóò0]\.?|(?-i:N)\.?\s*[º°oOóÓ0]\.?|(?-i:n)\.|(?-i:N)\.|(?-i:No)\b\.?|(?-i:NO)\b\.?|n[uú]mero)"
_UF_SUFIXO = rf"(?:\s*[/\-–—]\s*|\s*\(\s*|{H}+)(?P<uf>{UF})\)?(?![A-Za-z])"
_DO_TRIB = rf"(?:\s*,?\s+{DO}\s+(?P<trib>{_TRIB_SIMPLES}))"
# sufixo de incidente do STF colado ao número: "ARE 1.465.332-AgR-segundo/SP", "RE 123456 AgR"
_SUFIXO_STF = (rf"(?P<sufixo>(?:(?:{H}*[-–]{H}*|{H}+)(?-i:AgR|ED|QO|MC|EDv)"
               rf"(?:{H}*[-–]{H}*(?:segundo|terceiro|quarto|quinto))?(?![A-Za-z]))+)?")

RE_NUMERADA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?P<cadeia>{CADEIA}){_DO_TRIB}?"
    rf"(?:\s*[-–]\s*|\s*,?\s*(?:{_MARCADOR}\s*)?)"
    rf"(?P<num>{NUMERO}){_SUFIXO_STF}(?:{_UF_SUFIXO})?",
    re.I)

# "TST-Ag-ROT-1005710-02.2023.5.02.0000", "processo nº TST-E-RR-…", "Ag-ROT-…": cadeia hifenizada livre,
# aceita só se o número tiver estrutura CNJ (verificado na resolução)
RE_HIFENIZADA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ\-])(?P<cadeia>(?:T[S5]T\s*-\s*)?(?:[A-Z][A-Za-z]{{0,7}}\s*-\s*)+)(?P<num>{NUMERO})")

RE_PROCESSO_CNJ = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?P<cadeia>{frase('processo')}|{frase('autos')}|{frase('feito')})\s*(?:{_MARCADOR}\s*)?(?P<num>{NUMERO})(?:{_UF_SUFIXO})?",
    re.I)

_ROMANO = r"(?-i:[IVXLCDM]+)(?![A-Za-z])"
_SUMULA = rf"(?:{fuzzy('súmula')}|{fuzzy('súm')}\.?|{frase('enunciado')}|(?-i:SÚMULA|SUMULA))"
_QUALIF = rf"(?:{frase('colendo')}|{frase('egrégio')}|{frase('excelso')}|(?-i:c|col|e|eg|egr|C|E)\.)"
# tribunais fora da base (súmula deles nunca é `real`)
_OUTRO_TRIB = (rf"(?:(?-i:TJ[A-Z]{{2,3}}|TRF{H}?-?{H}?\d|TRT{H}?-?{H}?\d{{1,2}}|TRE{H}?-?{H}?[A-Z]{{2}}|TNU|TCU|TJ)(?![A-Za-z])"
               rf"|{frase('tribunal de justiça')}|{frase('tribunal regional')}|{frase('turma nacional de uniformização')}"
               rf"|{frase('tribunal de contas')})")
_SUM_TRIB = rf"(?:(?P<trib>{_TRIB_SIMPLES})|(?P<outro>{_OUTRO_TRIB}))"
_ITEM = rf"(?:\s*,\s*(?:{fuzzy('item')}\s+)?{_ROMANO}(?:\s*,)?)"
_NUM_SUMULA = rf"(?=\S{{0,3}}\d)(?:{CH}){{1,4}}(?![\d.]\d)(?![A-Za-zÀ-ÿ])"   # "83", "B3", "21l"
RE_SUMULA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?:(?P<sv>(?-i:SV))\.?|{_SUMULA}(?:\s*(?:{_MARCADOR}\s*)?(?P<vinc>{fuzzy('vinculante')}))?)"
    rf"\s*(?:{_MARCADOR}\s*)?(?P<num>{_NUM_SUMULA}){_ITEM}?"
    rf"(?:\s*(?:,\s*)?(?:{DO}\s+(?:{_QUALIF}\s*)?|/\s*){_SUM_TRIB})?",
    re.I)
# "Enunciado 83 da Súmula do STJ", "verbete 10 da Súmula Vinculante"
RE_SUMULA_ENUNCIADO = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?:{frase('enunciado')}|{frase('verbete')})\s*(?:{_MARCADOR}\s*)?(?P<num>{_NUM_SUMULA})"
    rf"\s+{DO}\s+{fuzzy('súmula')}(?:\s+(?P<vinc>{fuzzy('vinculante')}))?"
    rf"(?:\s*,?\s*{DO}\s+(?:{_QUALIF}\s*)?{_SUM_TRIB})?",
    re.I)
# tribunal antes do número: "Súmula STJ 83", "Súmula do STJ nº 83"
RE_SUMULA_TRIB_ANTES = re.compile(
    rf"(?<![A-Za-zÀ-ÿ]){_SUMULA}(?:\s+(?P<vinc>{fuzzy('vinculante')}))?\s+(?:{DO}\s+)?{_SUM_TRIB}"
    rf"\s*,?\s*(?:{_MARCADOR}\s*)?(?P<num>{_NUM_SUMULA})",
    re.I)

_TEMA_QUALIF = (rf"(?:\s+(?:{frase('repetitivo')}|(?-i:RG)|{frase('de repercussão geral')}|{frase('da repercussão geral')}"
                rf"|{frase('de recursos repetitivos')}|{frase('dos recursos repetitivos')}|{frase('de recurso repetitivo')}))")
RE_TEMA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ]){fuzzy('tema')}{_TEMA_QUALIF}?\s*(?:{_MARCADOR}\s*)?(?P<num>{NUMERO})"
    rf"(?:\s*/\s*{_TRIB_SIMPLES}"
    rf"|\s+(?:{DO}|de)\s+(?:{frase('sistemática da repercussão geral')}|{frase('sistemática dos recursos repetitivos')}"
    rf"|{frase('repercussão geral')}|{frase('recursos repetitivos')}|{frase('recurso repetitivo')}"
    rf"|{frase('recursos especiais repetitivos')}|{_TRIB_SIMPLES}))?",
    re.I)

_COMP = (rf"(?:§+\s*\d+\s*[º°o]?(?:\s*-\s*[A-Z])?|{frase('parágrafo único')}|{fuzzy('caput')}"
         rf"|(?:{fuzzy('inciso')}|{fuzzy('inc')}\.)\s+{_ROMANO}|(?<=,\s)[a-z](?![A-Za-z])|{_ROMANO}|{fuzzy('alínea')}\s*['‘’\"“”]?[a-z]['‘’\"“”]?|['‘’\"“”][a-z]['‘’\"“”]|[a-z]\))")
RE_LEI = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?P<art>{fuzzy('artigo')}|{fuzzy('art')}\.?)\s*(?P<num>\d{{1,2}}(?:[.\s]\d{{3}})+|\d{{1,4}})\s*(?:\.?[º°o](?![A-Za-z]))?"
    rf"(?P<suf>\s*-\s*[A-Z](?![A-Za-z]))?"
    rf"(?P<comp>(?:\s*,?\s*(?:e\s+)?{_COMP})*)(?:\s*,?\s*{DO}\s+|\s*,\s*)(?P<lei>{LEI})"
    rf"(?:\s*/\s*(?P<leiano>\d{{4}}|\d{{2}})(?!\d))?",
    re.I)

# nome de relator: iniciais maiúsculas, com o OCR do início da palavra ("5érgio", "lsabel") e dígitos-OCR no meio
_INICIAL = r"(?:[A-ZÀ-Ý]|5(?=[a-zà-ÿ])|[l1|](?=[b-df-hj-np-tv-zç]))"
_PALAVRA = rf"(?:{_INICIAL}[A-Za-zÀ-ÿ'´`015]+|[A-ZÀ-Ý]\.)"
_NOME = (rf"{_PALAVRA}(?:{H}*\n?{H}*(?:(?:de|da|do|dos|das|e|De|Da|Do|Dos|Das|DE|DA|DO|DOS|DAS){H}*\n?{H}*)?{_PALAVRA})*")
_CABECA = rf"(?:{frase('julgado')}|{frase('precedente')}|{frase('acórdão')}|{frase('aresto')}|{frase('decisão')}|{CADEIA})"
_VERBO = rf"(?:{frase('proferido')}|{frase('julgado')}|{frase('publicado')}|{frase('prolatado')}|{frase('decidido')}|{frase('firmado')})"
_RELATORIA = (rf"(?:(?:{fuzzy('pela')}|{fuzzy('sob')}|{DO}|{fuzzy('com')}|d[ec])\s+(?:a\s+)?{frase('relatoria')}\s+(?:{DO}|d[ec]\s+)?\s*(?:(?:{fuzzy('Min')}\.?|{fuzzy('Ministro')}|{fuzzy('Ministra')})\s+)?"
              rf"|{fuzzy('Rel')}\.?\s*(?:(?:{fuzzy('Min')}\.?|{fuzzy('Ministro')}|{fuzzy('Ministra')})\s*)?"
              rf"|{fuzzy('relator')}[ao]?\s*:?\s+(?:o\s+|a\s+)?(?:(?:{fuzzy('Min')}\.?|{fuzzy('Ministro')}|{fuzzy('Ministra')})\s+)?)")
_ANO = r"(?:1[9g]|2[0OoQD])[\dOoQDlI|SsgqBGbZz]{2}(?![\dA-Za-z])"
RE_INCOMPLETA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?P<cabeca>{_CABECA})(?:\s+(?:recente|unânime|paradigma))?"
    rf"(?:\s*,?\s*(?:{DO}\s+(?P<trib>{_TRIB_SIMPLES})"
    rf"|(?:{_VERBO}\s+)?(?:{EM}|d[ec]|no\s+ano\s+d[ec])\s+(?P<ano>{_ANO}))){{0,2}}\s*,?\s*"
    rf"(?P<rel>{_RELATORIA})(?P<nome>(?-i:{_NOME}))",
    re.I)


# ----------------------------------------------------------------------------- distratores

_OAB_ANTES = re.compile(r"OAB\s*[/\-–:]?\s*$", re.I)
_MESES = "janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
_DATA_DEPOIS = re.compile(rf"{H}*,?{H}*de{H}+(?:{_MESES})\b", re.I)
_UFS = set(UFS)
_NUMERADAS = ("numerada", "processo_cnj", "hifenizada")


def _eh_distrator(texto: str, c: Candidata) -> bool:
    """Números que a regex aceita mas não são citação: OAB, 'Cidade/UF, 12 de março', endereço 'Ap. 302'."""
    antes = texto[max(0, c.inicio - 12):c.inicio]
    if _OAB_ANTES.search(antes):
        return True
    if c.kind != "numerada":
        return False
    cadeia = c.grupos.get("cadeia", "").strip()
    if cadeia in _UFS and re.search(r"[/\-–]\s*$", antes):     # "Campo Grande/MS, 12 de…"
        return True
    if _DATA_DEPOIS.match(texto, c.fim):                         # "…MS, 12 de março de 2024"
        return True
    if re.fullmatch(r"Ap\.?", cadeia):                           # "nº 100, Ap. 302" (endereço)
        k = chave_numero(c.grupos["num"])
        return not (k and k[1])
    return False


# o gabarito do TST inclui o "processo nº TST-Ag-EDCiv-" que antecede a classe reconhecida
_PREFIXO_TST = re.compile(rf"(?:{frase('processo')}\s*(?:{_MARCADOR}\s*)?)?(?-i:(?:T[S5]T\s*-\s*)?(?:[A-Z][A-Za-z]{{0,7}}\s*-\s*)*)$", re.I)


def _estender_tst(texto: str, c: Candidata) -> Candidata:
    if c.kind in ("numerada", "hifenizada"):
        k = chave_numero(c.grupos["num"])
        if k and k[1] == "5":
            janela = texto[max(0, c.inicio - 80):c.inicio]
            m = _PREFIXO_TST.search(janela)
            if m and m.start() < len(janela):
                c.inicio -= len(janela) - m.start()
    return c


# ----------------------------------------------------------------------------- cabeçalho do próprio documento

_ROTULO = re.compile(r"[ \t]*[A-ZÀ-Ý][A-Za-zÀ-ÿ .\-/]{0,40}:\s")


def zona_cabecalho(texto: str, limite: int = 2000) -> int:
    """Fim do bloco de cabeçalho: a primeira linha de prosa (5+ palavras, metade ou mais em minúscula, sem 'Rótulo:').

    O limiar é baixo de propósito: com quebra de linha estreita a prosa tem poucas palavras por linha, e errar
    para o lado do cabeçalho descartaria citações reais do corpo.
    """
    pos = 0
    for linha in texto.splitlines(keepends=True):
        p = re.findall(r"[A-Za-zÀ-ÿ]+", linha)
        if len(p) >= 5 and 2 * sum(w[0].islower() for w in p) >= len(p) and not _ROTULO.match(linha):
            return pos
        pos += len(linha)
        if pos >= limite:
            break
    return min(pos, limite)


def chaves_proprias(texto: str, fim: int) -> set[str]:
    """Números (7+ dígitos) do cabeçalho: o processo do próprio documento, distrator em qualquer lugar do texto."""
    out = set()
    for m in RE_NUMERO.finditer(texto, 0, fim):
        k = chave_numero(m.group())
        if k and len(re.sub(r"\D", "", k[0])) >= 7:
            out.add(k[0])
    return out


# ----------------------------------------------------------------------------- extração

def _candidatas(texto: str) -> list[Candidata]:
    out = []
    for m in RE_NUMERADA.finditer(texto):
        out.append(Candidata(m.start(), m.end(), "numerada", m.groupdict(), 3))
    for m in RE_PROCESSO_CNJ.finditer(texto):
        out.append(Candidata(m.start(), m.end(), "processo_cnj", m.groupdict(), 1))
    for m in RE_HIFENIZADA.finditer(texto):
        out.append(Candidata(m.start(), m.end(), "hifenizada", m.groupdict(), 1))
    for rx in (RE_SUMULA, RE_SUMULA_ENUNCIADO, RE_SUMULA_TRIB_ANTES):
        for m in rx.finditer(texto):
            out.append(Candidata(m.start(), m.end(), "sumula", m.groupdict(), 5))
    for m in RE_TEMA.finditer(texto):
        out.append(Candidata(m.start(), m.end(), "tema", m.groupdict(), 4))
    for m in RE_LEI.finditer(texto):
        out.append(Candidata(m.start(), m.end(), "lei", m.groupdict(), 5))
    for m in RE_INCOMPLETA.finditer(texto):
        g = m.groupdict()
        if not (g.get("ano") or g.get("trib")):
            continue
        out.append(Candidata(m.start(), m.end(), "incompleta", g, 2))
    return out


def _aparar(texto: str, c: Candidata) -> Candidata:
    while c.fim > c.inicio and texto[c.fim - 1] in " \t\n,;.-– ":
        if texto[c.fim - 1] == "." and re.search(r"(?:\b[A-Z]|[Mm]in|[Rr]el)\.$", texto[c.inicio:c.fim]):
            break
        c.fim -= 1
    while c.inicio < c.fim and texto[c.inicio] in " \t\n,; ":
        c.inicio += 1
    return c


def resolver_sobreposicoes(cands: list[Candidata]) -> list[Candidata]:
    """Maior prioridade, depois maior span; nenhuma escolhida se sobrepõe a outra."""
    cands = sorted(cands, key=lambda c: (-c.prioridade, -c.tamanho, c.inicio))
    escolhidas: list[Candidata] = []
    for c in cands:
        if any(c.inicio < e.fim and e.inicio < c.fim for e in escolhidas):
            continue
        escolhidas.append(c)
    return sorted(escolhidas, key=lambda c: c.inicio)


def extrair(texto: str) -> list[Candidata]:
    fim_cab = zona_cabecalho(texto)
    proprias = chaves_proprias(texto, fim_cab)
    cands = []
    for c in _candidatas(texto):
        c = _aparar(texto, _estender_tst(texto, c))
        if c.kind in _NUMERADAS:
            k = chave_numero(c.grupos["num"])
            if c.inicio < fim_cab or (k and k[0] in proprias):   # número do próprio processo
                continue
        if _eh_distrator(texto, c):
            continue
        cands.append(c)
    return resolver_sobreposicoes(cands)
