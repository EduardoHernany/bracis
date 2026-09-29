"""Decide a classe (real / inventada / incompleta), o id_canonico e a confiança de cada candidata.

Política anti-τ: só é `real` o que casa *exatamente* (após correção letra→dígito)
com o número próprio de um registro compatível. Nada de fuzzy em dígitos.
"""
import re
from dataclasses import dataclass

from .aliases import TRIBUNAL_DA_CLASSE, TRIBUNAL_DO_J, codigos, lei_canonica, tribunal_de
from .extract import Candidata
from .kb import KB
from .textnorm import chave_numero, digitos

# tabela de confiança por regra (calibrada no conjunto de estresse)
CONF = {
    "real_unico": 0.99,
    "real_desempate": 0.85,
    "real_duplicata": 0.6,
    "inventada_ausente": 0.98,
    "inventada_tribunal": 0.8,
    "lei_real": 0.99,
    "lei_inventada": 0.97,
    "sumula_real": 0.99,
    "sumula_inventada": 0.97,
    "sumula_ambigua": 0.6,
    "tema": 0.9,
    "incompleta": 0.97,
    "incompleta_parcial": 0.8,
}

_ACESSORIAS = {"AgRg", "AgInt", "EDcl", "Ag", "QO", "PExt", "TST", "EDiv"}


@dataclass
class Decisao:
    classe: str
    tipo: str
    id_canonico: int | None
    confianca: float
    regra: str


def _principal(cods: list[str]) -> str | None:
    base = [c for c in cods if c != "TST"]
    if not base:
        return None
    for c in reversed(base):
        if c not in _ACESSORIAS:
            return c
    return base[-1]


def _similaridade(a: list[str], b: list[str]) -> float:
    a2, b2 = [c for c in a if c != "TST"], [c for c in b if c != "TST"]
    if not a2 or not b2:
        return 0.0
    sa, sb = set(a2), set(b2)
    s = len(sa & sb) / len(sa | sb)
    if _principal(a2) == _principal(b2):
        s += 1
    if a2 == b2:
        s += 1
    return s


def _numerada(c: Candidata, kb: KB) -> Decisao | None:
    g = c.grupos
    k = chave_numero(g["num"])
    if not k:
        return None
    chave, j = k
    cods = codigos(g["cadeia"]) + codigos(g.get("sufixo") or "")
    principal = _principal(cods)
    trib = None
    if g.get("trib"):
        trib = tribunal_de(g["trib"])
    elif j:
        trib = TRIBUNAL_DO_J.get(j)
    elif principal in TRIBUNAL_DA_CLASSE:
        trib = TRIBUNAL_DA_CLASSE[principal]
    donos = kb.por_chave.get(chave, set())
    if trib:
        compat = {i for i in donos if kb.registros[i].tribunal == trib}
        if donos and not compat:
            return Decisao("inventada", "jurisprudencia", None, CONF["inventada_tribunal"], "tribunal_incompativel")
        donos = compat
    if not donos:
        return Decisao("inventada", "jurisprudencia", None, CONF["inventada_ausente"], "numero_ausente")
    if len(donos) == 1:
        return Decisao("real", "jurisprudencia", next(iter(donos)), CONF["real_unico"], "numero_unico")
    notas = sorted(((_similaridade(cods, kb.registros[i].classes), -i, i) for i in donos), reverse=True)
    if notas[0][0] > notas[1][0]:
        return Decisao("real", "jurisprudencia", notas[0][2], CONF["real_desempate"], "desempate_classe")
    # duplicatas do acervo: mesmo processo em vários registros — fica com o de menor id
    return Decisao("real", "jurisprudencia", min(donos), CONF["real_duplicata"], "duplicata")


def _sumula(c: Candidata, kb: KB) -> Decisao:
    g = c.grupos
    num = int(g["num"])
    if g.get("outro"):     # súmula de TJ/TRF/TRT/TRE/TNU/TCU: fora da base, nunca real
        return Decisao("inventada", "jurisprudencia", None, CONF["sumula_inventada"], "sumula_outro_tribunal")
    vinc = bool(g.get("vinc") or g.get("sv"))
    trib = tribunal_de(g["trib"]) if g.get("trib") else ("STF" if vinc else None)
    if trib:
        rid = kb.sumulas.get((trib, num, vinc))
        if rid:
            return Decisao("real", "jurisprudencia", rid, CONF["sumula_real"], "sumula")
        return Decisao("inventada", "jurisprudencia", None, CONF["sumula_inventada"], "sumula_ausente")
    cands = [rid for (t, n, v), rid in kb.sumulas.items() if n == num and v == vinc]
    if len(cands) == 1:
        return Decisao("real", "jurisprudencia", cands[0], CONF["sumula_ambigua"], "sumula_sem_tribunal")
    if not cands:
        return Decisao("inventada", "jurisprudencia", None, CONF["sumula_inventada"], "sumula_ausente")
    return Decisao("incompleta", "jurisprudencia", None, CONF["sumula_ambigua"], "sumula_ambigua")


def _outra_versao(lei: str, ano: str | None) -> bool:
    """'CPC/73', 'CC/16': o código citado não é o da base (L13105/2015, L10406/2002…)."""
    if not ano or "/" not in lei:
        return False
    if len(ano) == 2:
        ano = ("19" if int(ano) > 30 else "20") + ano
    return not lei.endswith(ano)


def _lei(c: Candidata, kb: KB) -> Decisao | None:
    g = c.grupos
    lei = lei_canonica(g["lei"])
    if not lei:
        return None
    art = int(re.sub(r"\D", "", digitos(g["num"])) or 0)
    if g.get("suf") or _outra_versao(lei, g.get("leiano")):
        return Decisao("inventada", "lei", None, CONF["lei_inventada"], "dispositivo_ausente")
    rid = kb.dispositivos.get((lei, art))
    if rid:
        return Decisao("real", "lei", rid, CONF["lei_real"], "dispositivo")
    return Decisao("inventada", "lei", None, CONF["lei_inventada"], "dispositivo_ausente")


def decidir(c: Candidata, kb: KB) -> Decisao | None:
    if c.kind == "numerada":
        return _numerada(c, kb)
    if c.kind in ("hifenizada", "processo_cnj"):
        k = chave_numero(c.grupos["num"])
        return _numerada(c, kb) if k and k[1] else None
    if c.kind == "sumula":
        return _sumula(c, kb)
    if c.kind == "lei":
        return _lei(c, kb)
    if c.kind == "tema":
        return Decisao("inventada", "jurisprudencia", None, CONF["tema"], "tema")
    if c.kind == "incompleta":
        completa = c.grupos.get("ano") and c.grupos.get("nome")
        return Decisao("incompleta", "jurisprudencia", None,
                       CONF["incompleta"] if completa else CONF["incompleta_parcial"], "incompleta")
    return None
