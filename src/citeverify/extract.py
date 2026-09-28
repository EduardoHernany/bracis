"""Extração de candidatas a citação direto sobre o texto original (offsets nativos em codepoints)."""
import re
from dataclasses import dataclass, field

from .aliases import CADEIA, DO, EM, LEI, UF, _TRIB_SIMPLES
from .textnorm import NUMERO, frase, fuzzy


@dataclass
class Candidata:
    inicio: int
    fim: int
    kind: str                      # numerada | sumula | tema | lei | incompleta
    grupos: dict = field(default_factory=dict)
    prioridade: int = 0

    @property
    def tamanho(self):
        return self.fim - self.inicio


_MARCADOR = r"(?:(?-i:n)\.?\s*[º°oóò0]\.?|(?-i:N)\.?\s*[º°oOóÓ0]\.?|(?-i:n)\.|(?-i:N)\.|(?-i:No)\b\.?|(?-i:NO)\b\.?|n[uú]mero)"
_UF_SUFIXO = rf"(?:\s*[/\-–—]\s*|\s*\(\s*|[ \t]+)(?P<uf>{UF})\)?(?![A-Za-z])"
_DO_TRIB = rf"(?:\s*,?\s+{DO}\s+(?P<trib>{_TRIB_SIMPLES}))"

RE_NUMERADA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?P<cadeia>{CADEIA}){_DO_TRIB}?"
    rf"(?:\s*[-–]\s*|\s*,?\s*(?:{_MARCADOR}\s*)?)"
    rf"(?P<num>{NUMERO})(?:{_UF_SUFIXO})?",
    re.I)

# "TST-Ag-ROT-1005710-02.2023.5.02.0000", "processo nº TST-E-RR-…", "Ag-ROT-…": cadeia hifenizada livre,
# aceita só se o número tiver estrutura CNJ (verificado na resolução)
RE_HIFENIZADA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ\-])(?P<cadeia>(?:TST\s*-\s*)?(?:[A-Z][A-Za-z]{{0,7}}\s*-\s*)+)(?P<num>{NUMERO})")

RE_PROCESSO_CNJ = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?P<cadeia>{frase('processo')}|{frase('autos')}|{frase('feito')})\s*(?:{_MARCADOR}\s*)?(?P<num>{NUMERO})(?:{_UF_SUFIXO})?",
    re.I)
# linha de cabeçalho do próprio documento ("Autos nº …", "Processo nº …", "Referência: autos nº …") é distrator
_LINHA_CABECALHO = re.compile(r"^[ \t]*(?:[A-Za-zÀ-ÿ]+:\s*)?(?:autos|processo)\b", re.I | re.M)

_SUMULA = rf"(?:{fuzzy('súmula')}|{fuzzy('súm')}\.?|{frase('enunciado')}|(?-i:SÚMULA|SUMULA))"
RE_SUMULA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ]){_SUMULA}(?:\s*(?:{_MARCADOR}\s*)?(?P<vinc>{fuzzy('vinculante')}))?\s*(?:{_MARCADOR}\s*)?"
    rf"(?P<num>\d{{1,4}}(?![\d.]\d))"
    rf"(?:\s*(?:,\s*)?(?:{DO}\s+(?:(?:{frase('colendo')}|{frase('egrégio')}|{frase('excelso')})\s+)?|/\s*)(?P<trib>{_TRIB_SIMPLES}))?",
    re.I)

RE_TEMA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ]){fuzzy('tema')}\s*(?:{_MARCADOR}\s*)?(?P<num>{NUMERO})"
    rf"(?:\s+(?:{DO}|de)\s+(?:{frase('repercussão geral')}|{frase('recursos repetitivos')}|{frase('recurso repetitivo')}"
    rf"|{frase('recursos especiais repetitivos')}|{_TRIB_SIMPLES}))?",
    re.I)

_ROMANO = r"(?-i:[IVXLCDM]+)(?![A-Za-z])"
_COMP = (rf"(?:§+\s*\d+\s*[º°o]?(?:\s*-\s*[A-Z])?|{frase('parágrafo único')}|{fuzzy('caput')}"
         rf"|(?:{fuzzy('inciso')}|{fuzzy('inc')}\.)\s+{_ROMANO}|(?<=,\s)[a-z](?![A-Za-z])|{_ROMANO}|{fuzzy('alínea')}\s*['‘’\"]?[a-z]['‘’\"]?|['‘’\"][a-z]['‘’\"]|[a-z]\))")
RE_LEI = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?P<art>{fuzzy('artigo')}|{fuzzy('art')}\.?)\s*(?P<num>\d{{1,2}}(?:[.\s]\d{{3}})+|\d{{1,4}})\s*(?:[º°o](?![A-Za-z]))?"
    rf"(?P<comp>(?:\s*,?\s*(?:e\s+)?{_COMP})*)\s*,?\s*{DO}\s+(?P<lei>{LEI})",
    re.I)

_NOME = (r"(?:[A-ZÀ-Ý][A-Za-zÀ-ÿ'´`]+|[A-ZÀ-Ý]\.)"
         r"(?:[ \t]*\n?[ \t]*(?:(?:de|da|do|dos|das|e|De|Da|Do|Dos|Das|DE|DA|DO|DOS|DAS)[ \t]*\n?[ \t]*)?"
         r"(?:[A-ZÀ-Ý][A-Za-zÀ-ÿ'´`]+|[A-ZÀ-Ý]\.))*")
_CABECA = rf"(?:{frase('julgado')}|{frase('precedente')}|{frase('acórdão')}|{frase('aresto')}|{frase('decisão')}|{CADEIA})"
_VERBO = rf"(?:{frase('proferido')}|{frase('julgado')}|{frase('publicado')}|{frase('prolatado')}|{frase('decidido')}|{frase('firmado')})"
_RELATORIA = (rf"(?:(?:{fuzzy('pela')}|{fuzzy('sob')}|{DO}|{fuzzy('com')}|d[ec])\s+(?:a\s+)?{frase('relatoria')}\s+(?:{DO}|d[ec]\s+)?\s*(?:(?:{fuzzy('Min')}\.?|{fuzzy('Ministro')}|{fuzzy('Ministra')})\s+)?"
              rf"|{fuzzy('Rel')}\.?\s*(?:(?:{fuzzy('Min')}\.?|{fuzzy('Ministro')}|{fuzzy('Ministra')})\s*)?"
              rf"|{fuzzy('relator')}[ao]?\s*:?\s+(?:o\s+|a\s+)?(?:(?:{fuzzy('Min')}\.?|{fuzzy('Ministro')}|{fuzzy('Ministra')})\s+)?)")
RE_INCOMPLETA = re.compile(
    rf"(?<![A-Za-zÀ-ÿ])(?P<cabeca>{_CABECA})(?:\s+(?:recente|unânime|paradigma))?"
    rf"(?:\s*,?\s*(?:{DO}\s+(?P<trib>{_TRIB_SIMPLES})"
    rf"|(?:{_VERBO}\s+)?(?:{EM}|d[ec]|no\s+ano\s+d[ec])\s+(?P<ano>(?:19|20)\d\d))){{0,2}}\s*,?\s*"
    rf"(?P<rel>{_RELATORIA})(?P<nome>(?-i:{_NOME}))",
    re.I)


def _candidatas(texto: str) -> list[Candidata]:
    out = []
    for m in RE_NUMERADA.finditer(texto):
        out.append(Candidata(m.start(), m.end(), "numerada", m.groupdict(), 3))
    for m in RE_PROCESSO_CNJ.finditer(texto):
        inicio_linha = texto.rfind("\n", 0, m.start()) + 1
        if _LINHA_CABECALHO.match(texto, inicio_linha) and _LINHA_CABECALHO.match(texto, inicio_linha).end() >= m.start():
            continue
        out.append(Candidata(m.start(), m.end(), "processo_cnj", m.groupdict(), 1))
    for m in RE_HIFENIZADA.finditer(texto):
        out.append(Candidata(m.start(), m.end(), "hifenizada", m.groupdict(), 1))
    for m in RE_SUMULA.finditer(texto):
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
    while c.fim > c.inicio and texto[c.fim - 1] in " \t\n,;.-–":
        if texto[c.fim - 1] == "." and re.search(r"(?:\b[A-Z]|[Mm]in|[Rr]el)\.$", texto[c.inicio:c.fim]):
            break
        c.fim -= 1
    while c.inicio < c.fim and texto[c.inicio] in " \t\n,;":
        c.inicio += 1
    return c


def extrair(texto: str) -> list[Candidata]:
    cands = [_aparar(texto, c) for c in _candidatas(texto)]
    # resolve sobreposições: maior prioridade, depois maior span
    cands.sort(key=lambda c: (-c.prioridade, -c.tamanho, c.inicio))
    escolhidas: list[Candidata] = []
    for c in cands:
        if any(c.inicio < e.fim and e.inicio < c.fim for e in escolhidas):
            continue
        escolhidas.append(c)
    return sorted(escolhidas, key=lambda c: c.inicio)
