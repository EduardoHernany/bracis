"""Base de conhecimento offline construída a partir do SQLite canônico.

Para cada acórdão, extrai os números que o *identificam* (o processo que ele é),
e não os que ele apenas cita: o cabeçalho (até "RELATOR") nos tribunais em geral,
e a frase "autos de … nº TST-…"/"PROCESSO Nº TST-…" no TST, cujo cabeçalho não traz número.
Súmulas e dispositivos de lei viram índices próprios.
"""
import hashlib
import pickle
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .aliases import codigos, lei_canonica
from .textnorm import RE_NUMERO, H, chave_numero

_RELATOR = re.compile(r"\bRELATORA?\b|\bRelatora?\b|\bRelator\s+origin", re.I)
_CNJ_TST = r"(?:[A-Za-z]+\s*-\s*)*(\d{1,7}\s*-\s*\d{2}\s*\.\s*\d{4}\s*\.\s*5\s*\.\s*\d{2}\s*\.\s*\d{4})"
# "Vistos, relatados e discutidos estes autos de <Classe> nº TST-X" — é o próprio processo
_TST_AUTOS = re.compile(r"\bautos\s+de\s+[^.]{0,200}?n\s*\.?\s*[º°o]s?\s*TST\s*-\s*" + _CNJ_TST, re.I | re.S)
# rodapé "PROCESSO Nº TST-X" (último do documento); no corpo pode ser só citação
_TST_PROCESSO = re.compile(r"PROCESSO\s*N[º°o]?\s*:?\s*TST\s*-\s*" + _CNJ_TST)
_BARRAS = "/\u2044\u2215\uff0f"          # "/" e as barras de fração do STJ: "(2016⁄0199049-5)"
_MESES = "janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro"
_LETRA = re.compile(r"[A-Za-zÀ-ÿ]")

# registros cujo cabeçalho está corrompido pelo OCR: o número real aparece dezenas de vezes no próprio texto
# (conferido com scripts/kb_audit.py; nenhum outro registro usa essas chaves)
CHAVES_MANUAIS = {
    568736504: {"185-05.2016.6.25.0024"},    # TSE, cabeçalho "Nº 185-05. 20.16.6. , 250024"
    576309534: {"598-49.2012.6.08.0018"},    # TSE, cabeçalho "Nº 598- 2012 6 08 0018 - CLASSE 32 49"
    2381771667: {"234-73.2016.7.11.0211"},   # STM, começa pelo "EXTRATO DA ATA"; é a APELAÇÃO Nº 234-73…
}
CLASSES_MANUAIS = {2381771667: ["APL"]}


@dataclass
class Registro:
    id: int
    documento_id: str
    tribunal: str | None
    natureza: str
    ano: int | None
    relator: str | None
    classes: list[str] = field(default_factory=list)   # cadeia de classes do cabeçalho
    chaves: set[str] = field(default_factory=set)       # números próprios (canônicos)


@dataclass
class KB:
    registros: dict[int, Registro]
    por_chave: dict[str, set[int]]
    sumulas: dict[tuple[str, int, bool], int]           # (tribunal, número, vinculante) → id
    dispositivos: dict[tuple[str, int], int]            # (lei canônica, artigo) → id
    citadas: set[str]                                   # chaves que aparecem em qualquer texto (diagnóstico)


def _cabecalho(texto: str) -> str:
    m = _RELATOR.search(texto, 10)
    fim = m.start() if m and m.start() < 450 else 400
    return texto[:fim]


def _chaves_cabecalho(cab: str) -> set[str]:
    out = set()
    for m in RE_NUMERO.finditer(cab):
        s, e = m.start(), m.end()
        antes, depois = cab[max(0, s - 1):s], cab[e:e + 1]
        if any(b in antes + depois for b in _BARRAS):          # datas e o "(2018/0116304-1)" do STJ
            continue
        if re.search(r"CLASSE\s*$", cab[max(0, s - 8):s], re.I):
            continue
        if re.search(r"(?:R\$\s*[\d.,]*|OAB[\s:/\-]*)\s*$", cab[max(0, s - 20):s]):   # valor da causa, OAB
            continue
        if _LETRA.match(antes) or _LETRA.match(depois):        # colado a letra: lixo de OCR ("20s", "52a SESSÃO")
            continue
        if (re.match(rf"{H}+DE{H}+(?:{_MESES})\b", cab[e:], re.I)
                or re.search(rf"\b(?:{_MESES}){H}+DE{H}+$", cab[:s], re.I)):   # data por extenso
            continue
        k = chave_numero(m.group())
        if not k or len(re.sub(r"\D", "", m.group())) < 2 or k[0] == "0":
            continue
        if k[1] is None and len(k[0]) <= 4 and re.search(r"[^\d\s.\-]", m.group()):   # curto e com letra-OCR
            continue
        out.add(k[0])
    return out


def _classes_cabecalho(cab: str) -> list[str]:
    # remove o preâmbulo ("TRIBUNAL SUPERIOR ELEITORAL ACÓRDÃO", "PRIMEIRA TURMA"…) antes de ler as classes
    cab = re.split(r"AC[ÓO€]?RD[ÃA]?O|TURMA|PLEN[ÁA]RIO|Pleno", cab)[-1]
    num = RE_NUMERO.search(cab)
    return codigos(cab[:num.start()] if num else cab)


def construir(db_path: str | Path) -> KB:
    con = sqlite3.connect(db_path)
    registros, por_chave = {}, defaultdict(set)
    sumulas, dispositivos, citadas = {}, {}, set()
    for rid, did, trib, ano, rel, nat, texto in con.execute(
            "SELECT id, documento_id, tribunal, ano, relator, natureza, texto FROM documentos"):
        r = Registro(rid, did, trib, nat, ano, rel)
        registros[rid] = r
        if nat == "sumula":
            m = re.match(r"Súmula\s+(Vinculante\s+)?n\.\s*(\d+)\s+do\s+(\w+)", texto)
            sumulas[(m.group(3), int(m.group(2)), bool(m.group(1)))] = rid
            continue
        if nat == "dispositivo":
            m = re.match(r"Artigo\s+(\d+)º?\s+d[ao]s?\s+(.+)", texto)
            lei = "CF" if "Constituição" in m.group(2) else lei_canonica(m.group(2).split("\n")[0])
            dispositivos[(lei, int(m.group(1)))] = rid
            continue
        cab = _cabecalho(texto)
        # o cabeçalho do TST não traz o número do processo (só ementa), então ele não conta
        r.chaves = _chaves_cabecalho(cab) if trib != "TST" else set()
        r.classes = _classes_cabecalho(cab)
        if trib == "TST" or not r.chaves:
            m = _TST_AUTOS.search(texto)
            if not m:
                ms = list(_TST_PROCESSO.finditer(texto))
                m = ms[-1] if ms else None
            if m and (k := chave_numero(m.group(1))):
                r.chaves.add(k[0])
        if not r.chaves:   # último recurso: primeiro "Nº <número>" do documento
            m = re.search(r"N[º°]\s*(" + RE_NUMERO.pattern + ")", texto[:3000])
            if m:
                r.chaves.add(chave_numero(m.group(1))[0])
        if rid in CHAVES_MANUAIS:
            r.chaves = set(CHAVES_MANUAIS[rid])
        r.classes = CLASSES_MANUAIS.get(rid, r.classes)
        for k in r.chaves:
            por_chave[k].add(rid)
        for m in RE_NUMERO.finditer(texto):
            k = chave_numero(m.group())
            if k and len(k[0]) >= 4:
                citadas.add(k[0])
    return KB(registros, dict(por_chave), sumulas, dispositivos, citadas)


def _assinatura(db_path: str | Path) -> str:
    """Hash do código que constrói o KB + conteúdo da base: cache velho nunca é reaproveitado."""
    h = hashlib.sha256()
    for mod in ("kb.py", "aliases.py", "textnorm.py"):
        h.update((Path(__file__).parent / mod).read_bytes())
    with open(db_path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()[:12]


def carregar(db_path: str | Path, cache: str | Path | None = None) -> KB:
    if cache:
        cache = Path(cache).with_name(f"{Path(cache).stem}-{_assinatura(db_path)}.pkl")
    if cache and Path(cache).exists():
        with open(cache, "rb") as f:
            return pickle.load(f)
    kb = construir(db_path)
    if cache:
        Path(cache).parent.mkdir(parents=True, exist_ok=True)
        with open(cache, "wb") as f:
            pickle.dump(kb, f)
    return kb
