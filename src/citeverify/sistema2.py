"""Sistema 2: o que fazer com as frases que o Sistema 1 não resolveu (gatilhos, re-ancoragem e decisão).

Este módulo é Python puro (testável sem o modelo). O LLM em si fica em llm.py.

Contrato anti-τ: o LLM só PROPÕE trechos literais. Cada trecho é re-ancorado no texto original e decidido pelas
mesmas regras e pelo mesmo KB do Sistema 1 — `real` continua exigindo chave exata no KB. O S2 nunca sobrescreve
uma citação do S1: qualquer sobreposição descarta a proposta.
"""
import re

from .aliases import RE_ATOMO, RE_TRIB
from .extract import Candidata, _aparar, _candidatas, _eh_distrator, chaves_proprias, zona_cabecalho
from .frases import segmentar
from .kb import KB
from .resolve import Decisao, _d, _numerada, decidir
from .textnorm import RE_NUMERO, chave_numero, frase
from .vagas import NUCLEOS, RE_SLOT_GENERICO, _NUCLEO

# pistas fortes de citação (fora de qualquer span do S1, fazem a frase escalar)
_PISTA = re.compile(
    r"(?i:\b(?:s[úu]mula|s[úu]m\.|enunciado|verbete|tema|art(?:igo)?s?\.?)\s*(?:n[º°o.]*\s*)?[\dOolISB]\d"
    r"|\b(?:rel\.|relator[a]?\b|relatoria\b|min\.|ministr[oa]\b))"
    r"|\b(?:[S5]T[FJM]|T[S5][ET])\b"
    r"|(?<![\d/])\d[\d.\-\s]{4,}\d(?![\d/])")
# números que não são citação: folhas, valores, OAB, protocolo, documentos pessoais, datas
_DISTRATOR_ANTES = re.compile(r"(?i)(?:fls?\.|R\$|OAB[\s/\-:A-Z]*|protocolo(?:\s*n[º°o.]*)?|CPF|CNPJ|CEP|RG)\s*$")
_NUCLEO_RX = re.compile(rf"(?<![A-Za-zÀ-ÿ])(?:o|a|os|as|no|na|nos|nas|do|da|dos|das|ao|à)\s+(?:\w+\s+)?{_NUCLEO}(?![A-Za-zÀ-ÿ])", re.I)
_NUCLEO_SIMPLES = re.compile(rf"(?<![A-Za-zÀ-ÿ]){_NUCLEO}(?![A-Za-zÀ-ÿ])", re.I)
_TITULO = re.compile(r"^[\sIVXLC\d.—–-]*[A-ZÀ-Ý\s—–\-,.:]+$")
# a partir daqui é fecho/pedido: não escala
_FECHO = re.compile(r"(?i)\b(?:termos em que|nestes termos|é o parecer|publique-se|por tais fundamentos|"
                    r"ante o exposto|pelo exposto|diante de todo o exposto|diante do exposto)\b")
_ANO = re.compile(r"\b(?:19|20)\d\d\b")
_RELATOR = re.compile(r"(?i)\b(?:rel\.|relator[a]?|relatoria|min\.|ministr[oa])")


def _coberto(a: int, b: int, ocupados: list[tuple[int, int]]) -> bool:
    return any(a < f and i < b for i, f in ocupados)


def escalar(texto: str, ocupados: list[tuple[int, int]], vagas: bool = False) -> list[tuple[int, int]]:
    """Frases a enviar ao LLM: têm uma pista forte ou um slot do gerador fora das citações já achadas; na
    convenção V (vagas=True), também um núcleo jurídico ("a jurisprudência…"). Cabeçalho, fecho e títulos
    ficam de fora."""
    fim_cab = zona_cabecalho(texto)
    fechos = list(_FECHO.finditer(texto))
    ini_fecho = fechos[-1].start() if fechos and fechos[-1].start() > len(texto) * 0.6 else len(texto)
    out = []
    for a, b in segmentar(texto):
        if a < fim_cab or a >= ini_fecho:
            continue
        trecho = texto[a:b]
        if _TITULO.match(trecho):
            continue
        achou = False
        for rx in (_PISTA, RE_SLOT_GENERICO) + ((_NUCLEO_RX,) if vagas else ()):
            for m in rx.finditer(trecho):
                ini, fim = (m.start("sn"), m.end("sn")) if rx is RE_SLOT_GENERICO else (m.start(), m.end())
                if rx is _PISTA and m.group()[0].isdigit() and _DISTRATOR_ANTES.search(trecho[:ini]):
                    continue
                if not _coberto(a + ini, a + fim, ocupados):
                    achou = True
                    break
            if achou:
                break
        if achou:
            out.append((a, b))
    return out


def ancorar(texto: str, a: int, b: int, trecho: str) -> tuple[int, int] | None:
    """Localiza no texto original, dentro da frase [a, b), o trecho devolvido pelo LLM. Nada de paráfrase:
    exato, depois insensível a espaço/quebra, depois tolerante a acento/OCR nas letras (dígitos exatos)."""
    trecho = trecho.strip().strip(".,;:")
    if len(trecho) < 3:
        return None
    i = texto.find(trecho, a, b)
    if i >= 0:
        return i, i + len(trecho)
    partes = trecho.split()
    for padrao in (r"\s+".join(re.escape(p) for p in partes), frase(trecho)):
        try:
            m = re.compile(padrao, re.I).search(texto, a, b)
        except re.error:
            continue
        if m:
            return m.start(), m.end()
    return None


def decidir_s2(texto: str, ini: int, fim: int, kb: KB, vagas: bool) -> tuple[Candidata, Decisao] | None:
    """Decide um trecho proposto pelo LLM. Primeiro tenta os regex do S1 dentro dele; senão, regras mínimas."""
    trecho = texto[ini:fim]
    # os mesmos filtros de distrator do S1: número do próprio processo (cabeçalho), OAB, cidade/UF, data
    proprias = chaves_proprias(texto, zona_cabecalho(texto))
    for m in RE_NUMERO.finditer(trecho):
        k = chave_numero(m.group())
        if k and k[0] in proprias:
            return None
    # 1) um candidato do S1 que cubra ≥ 80% do trecho (o LLM achou o que a frase escondia do regex)
    melhor = None
    for c in _candidatas(trecho):
        c = _aparar(trecho, c)
        if c.tamanho >= 0.8 * len(trecho.strip()) and (melhor is None or c.tamanho > melhor.tamanho):
            melhor = c
    if melhor:
        c = Candidata(ini + melhor.inicio, ini + melhor.fim, melhor.kind, melhor.grupos, melhor.prioridade)
        if _eh_distrator(texto, c):
            return None
        d = decidir(c, kb)
        if d:
            return c, d
    tem_classe = bool(RE_ATOMO.search(trecho)) or bool(RE_TRIB.search(trecho))
    # 2) número de processo: só com classe ou tribunal no trecho; `real` só com chave exata e compatível no KB
    nums = [m for m in RE_NUMERO.finditer(trecho) if len(re.sub(r"\D", "", m.group())) >= 3]
    if nums:
        if not tem_classe:
            return None
        # o número do processo é o primeiro depois da classe (ou do tribunal); números colados a "/" são
        # registro ou data ("2018/0116304-1")
        atomos = list(RE_ATOMO.finditer(trecho))
        trib_m = RE_TRIB.search(trecho)
        ref = atomos[-1].end() if atomos else (trib_m.end() if trib_m else 0)
        validos = [x for x in nums if x.start() >= ref
                   and "/" not in trecho[max(0, x.start() - 1):x.start()] + trecho[x.end():x.end() + 1]]
        if not validos:
            return None
        m = validos[0]
        k = chave_numero(m.group())
        if not k or _ANO.fullmatch(m.group().strip()):
            return None
        cadeia = trecho[:m.start()]
        trib = RE_TRIB.search(trecho)
        c = Candidata(ini, fim, "numerada", {"cadeia": cadeia, "num": m.group(), "trib": trib.group() if trib else None}, 3)
        d = _numerada(c, kb)
        if d is None:
            return None
        regra = "s2_real" if d.classe == "real" else "s2_inventada"
        return c, _d(d.classe, d.tipo, d.id_canonico, regra)
    # 3) julgado identificado sem número: tribunal/classe + ano ou relator
    if tem_classe and (_ANO.search(trecho) or _RELATOR.search(trecho)):
        c = Candidata(ini, fim, "incompleta", {}, 2)
        return c, _d("incompleta", "jurisprudencia", None, "s2_incompleta")
    # 4) referência vaga (só na convenção V)
    # como as frases vagas do gabarito: sintagma nominal curto (até 8 palavras), sem vírgula (não é descrição)
    # "acórdão recorrido", "decisão agravada": é o ato atacado, não uma fonte invocada
    ato_atacado = re.search(r"(?i)\b(?:recorrid|agravad|impugnad|hostilizad|embargad|guerread)[oa]s?\b", trecho)
    if (vagas and not ato_atacado and _NUCLEO_SIMPLES.search(trecho) and 2 <= len(trecho.split()) <= 8
            and "," not in trecho):
        tipo = "lei" if re.search(r"(?i)dispositiv|\blei|legisla|norma|artigo|preceito|diploma|c[óo]digo", trecho) \
            else "jurisprudencia"
        c = Candidata(ini, fim, "vaga", {"tipo": tipo}, 0)
        return c, _d("incompleta", tipo, None, "s2_vaga")
    return None


def aplicar(texto: str, kb: KB, cands: list[Candidata], s2, vagas: bool,
            extras: list[tuple[int, int]] | None = None) -> list[tuple[Candidata, Decisao]]:
    """Escala as frases suspeitas (gatilhos determinísticos ∪ `extras`, as frases que o Laya sinalizou), pede os
    trechos ao LLM e devolve só as decisões novas, sem sobreposição."""
    ocupados = [(c.inicio, c.fim) for c in cands]
    frases = sorted(set(escalar(texto, ocupados, vagas)) | set(extras or []))
    novas = []
    for a, b in frases:
        for trecho in s2.extrair(texto[a:b].replace("\n", " ")):
            pos = ancorar(texto, a, b, trecho)
            if not pos:
                continue
            ini, fim = pos
            if _coberto(ini, fim, ocupados):
                continue
            res = decidir_s2(texto, ini, fim, kb, vagas)
            if res:
                novas.append(res)
                ocupados.append((res[0].inicio, res[0].fim))
    return novas


__all__ = ["escalar", "ancorar", "decidir_s2", "aplicar", "NUCLEOS"]
