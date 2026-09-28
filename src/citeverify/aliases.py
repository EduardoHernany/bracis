"""Vocabulário de classes processuais, tribunais e leis.

Derivado das classes que aparecem nos cabeçalhos dos 998 acórdãos da base (não só
da amostra de dev), com as variantes de superfície do nível 2: sigla, extenso,
com/sem pontos, caixa alta, e ruído de OCR nas palavras por extenso.
"""
import re

from .textnorm import frase

# ----------------------------------------------------------------------------- classes
# (código canônico, [formas por extenso], [siglas — regex, case-sensitive])
# A ordem importa pouco: o regex final prefere o match mais longo.
CLASSES = [
    ("AREspE", ["agravo em recurso especial eleitoral"], [r"AREspE[l1]?", r"AREspe", r"ARESPE", r"AREspEl"]),
    ("REspE", ["recurso especial eleitoral"], [r"R\.?\s?Esp\.?\s?e\b\.?", r"REspe\.?", r"RESPE\.?", r"REspE[l1]", r"REsp\.?\s?El\.?", r"RESPE"]),
    ("AREsp", ["agravo em recurso especial"], [r"A\.?\s?R\.?\s?Esp\.?", r"ARESP", r"AResp", r"AgREsp", r"AgResp", r"AGRESP", r"Ag\.?\s?REsp"]),
    ("REsp", ["recurso especial"], [r"R\.?\s?Esp\.?", r"RESP", r"Resp\.?", r"Rec\.?\s?Esp\.?", r"R\.\s?E\.?\s?sp\.?"]),
    ("ARE", ["recurso extraordinário com agravo", "agravo em recurso extraordinário"], [r"ARE\b"]),
    ("RE", ["recurso extraordinário"], [r"RE\b\.?", r"R\.E\.", r"Rext", r"RExt"]),
    ("RHC", ["recurso em habeas corpus", "recurso ordinário em habeas corpus"], [r"RHC", r"R\.?\s?H\.?\s?C\.?", r"RHc"]),
    ("RMS", ["recurso em mandado de segurança", "recurso ordinário em mandado de segurança",
             "recurso ord. em mandado de segurança"], [r"RMS", r"R\.?\s?M\.?\s?S\.?", r"ROMS"]),
    ("RSE", ["recurso em sentido estrito"], [r"RSE", r"R\.?\s?S\.?\s?E\.?", r"RESE"]),
    ("RR", ["recurso de revista"], [r"RR\b"]),
    ("ARR", ["recurso de revista com agravo"], [r"ARR\b"]),
    ("AIRR", ["agravo de instrumento em recurso de revista"], [r"AIRR"]),
    ("RRAg", [], [r"RRAg"]),
    ("AgARR", [], [r"AgARR"]),
    ("RO", ["recurso ordinário eleitoral", "recurso ordinário"], [r"RO\b", r"ROE[l1]?", r"R\.O\."]),
    ("RCED", ["recurso contra expedição de diploma"], [r"RCED"]),
    ("Rp", ["representação", "recurso na representação"], [r"R-?Rp", r"Rp\b"]),
    ("HC", ["habeas corpus criminal", "habeas corpus"], [r"HC\b", r"H\.\s?C\.", r"Hc\b"]),
    ("MS", ["mandado de segurança cível", "mandado de segurança"], [r"MS\b", r"M\.S\."]),
    ("Rcl", ["reclamação constitucional", "reclamação"], [r"Rcl\.?", r"RCL\.?", r"Recl\.?", r"RECL\.?", r"Rc[l1]\.?"]),
    ("AR", ["ação rescisória"], [r"AR\b"]),
    ("AP", ["ação penal"], [r"AP\b", r"APn"]),
    ("ADI", ["ação direta de inconstitucionalidade"], [r"ADI", r"ADIn"]),
    ("APL", ["apelação criminal", "apelação"], [r"APL", r"Ap\.?\s?Crim\.?", r"ApCrim", r"Ap\b\.?", r"APELAÇÃO"]),
    ("AgInt", ["agravo interno criminal", "agravo interno"], [r"AgInt", r"AGINT", r"Ag\.?\s?Int\.?", r"AgInterno"]),
    ("AgRg", ["agravo regimental"], [r"AgRg", r"AGRG", r"Ag\.?\s?Rg\.?", r"AgR\b", r"AGR\b", r"Ag\.?\s?Reg\.?", r"AG\.?\s?REG\.?"]),
    ("AI", ["agravo de instrumento"], [r"AI\b", r"AG\b"]),
    ("Ag", ["agravo"], [r"Ag\b\.?"]),
    ("EDcl", ["embargos de declaração criminal", "embargos de declaração", "embargos declaratórios"],
     [r"EDcl", r"EDCL", r"ED\b", r"EDs\b", r"Emb\.?\s?Decl\.?", r"EMB\.?\s?DECL\.?", r"E\.?\s?Dcl\.?", r"EDecl"]),
    ("EDiv", ["embargos de divergência"], [r"EDiv", r"EREsp", r"ERESP", r"EDv", r"Emb\.?\s?Div\.?", r"EMB\.?\s?DIV\.?", r"EAREsp"]),
    ("EINul", ["embargos infringentes e de nulidade", "embargos infringentes"], [r"EIN", r"EI\b"]),
    ("E", ["recurso de embargos", "embargos"], [r"E\b"]),
    ("CC", ["conflito de competência"], [r"CC\b"]),
    ("CJ", ["conflito de jurisdição"], [r"CJ\b"]),
    ("SLS", ["suspensão de liminar e de sentença"], [r"SLS"]),
    ("SS", ["suspensão de segurança"], [r"SS\b"]),
    ("Pet", ["petição"], [r"Pet\.?", r"PET\b"]),
    ("PC", ["prestação de contas"], [r"PC\b", r"PCE\b"]),
    ("CorPar", ["correição parcial militar", "correição parcial"], [r"CorPar", r"CP\b"]),
    ("QO", ["questão de ordem"], [r"QO\b"]),
    ("TCA", ["tutela cautelar antecedente"], [r"TutCautAnt", r"TCA\b"]),
    ("AC", ["ação cautelar", "cautelar inominada criminal"], [r"AC\b"]),
    ("AIJE", ["ação de investigação judicial eleitoral"], [r"AIJE"]),
    ("PExt", ["pedido de extensão"], [r"PExt"]),
    # classes fora do acervo (citá-las é, na prática, sempre inventada), para não perder o span
    ("ADPF", ["arguição de descumprimento de preceito fundamental"], [r"ADPF"]),
    ("ADC", ["ação declaratória de constitucionalidade"], [r"ADC\b"]),
    ("ADO", ["ação direta de inconstitucionalidade por omissão"], [r"ADO\b"]),
    ("MI", ["mandado de injunção"], [r"MI\b"]),
    ("HD", ["habeas data"], [r"HD\b"]),
    ("Inq", ["inquérito"], [r"Inq\.?"]),
    ("Ext", ["extradição"], [r"Ext\b\.?"]),
    ("ACO", ["ação cível originária"], [r"ACO\b"]),
    ("RvC", ["revisão criminal"], [r"RvC", r"RvCr", r"RevCrim"]),
    ("Cta", ["consulta"], [r"Cta\b\.?"]),
    ("MC", ["medida cautelar"], [r"MC\b"]),
    ("TP", ["tutela provisória"], [r"TP\b"]),
    ("IRDR", ["incidente de resolução de demandas repetitivas"], [r"IRDR"]),
    ("IUJ", ["incidente de uniformização de jurisprudência", "pedido de uniformização de interpretação de lei"], [r"IUJ", r"PUIL"]),
    ("SL", ["suspensão de liminar"], [r"SL\b"]),
    ("STA", ["suspensão de tutela antecipada"], [r"STA\b"]),
    ("TST", [], [r"TST"]),
]

ORDINAIS = ["segundo", "segunda", "segundos", "terceiro", "terceira", "quarto", "quinto",
            "décimos", "décimo", "segundos"]

# classe principal → tribunal (só quando a classe é inequívoca)
TRIBUNAL_DA_CLASSE = {
    "ADPF": "STF", "ADC": "STF", "ADO": "STF", "Ext": "STF", "ACO": "STF", "STA": "STF",
    "REsp": "STJ", "AREsp": "STJ", "RHC": "STJ", "RMS": "STJ", "EDiv": "STJ", "SLS": "STJ", "CC": "STJ",
    "RE": "STF", "ARE": "STF", "ADI": "STF",
    "REspE": "TSE", "AREspE": "TSE", "RCED": "TSE", "AIJE": "TSE", "Rp": "TSE", "PC": "TSE",
    "RR": "TST", "ARR": "TST", "AIRR": "TST", "RRAg": "TST", "AgARR": "TST", "E": "TST",
    "APL": "STM", "RSE": "STM", "EINul": "STM", "CorPar": "STM", "CJ": "STM",
}
TRIBUNAL_DO_J = {"5": "TST", "6": "TSE", "7": "STM", "3": "STJ"}

TRIBUNAIS = ["STF", "STJ", "TSE", "TST", "STM"]
_TRIB_EXTENSO = {
    "STF": ["supremo tribunal federal", "excelso pretório", "suprema corte"],
    "STJ": ["superior tribunal de justiça"],
    "TSE": ["tribunal superior eleitoral"],
    "TST": ["tribunal superior do trabalho"],
    "STM": ["superior tribunal militar"],
}


def _alt(formas):
    return "|".join(sorted(formas, key=len, reverse=True))


_SIG_OCR = {"S": "S5", "s": "s5", "l": "l1I", "I": "I1l", "O": "O0", "o": "o0", "e": "ec", "c": "ce", "E": "E", "g": "g9"}


def sig(regex: str) -> str:
    """Torna uma sigla (regex) tolerante a OCR: letras literais viram classes, m→(m|rn), \\s? → \\s{0,3}."""
    out, i = [], 0
    while i < len(regex):
        ch = regex[i]
        if ch == "\\":
            nxt = regex[i + 1]
            if nxt == "s" and regex[i + 2:i + 3] == "?":
                out.append(r"\s{0,3}")
                i += 3
                continue
            out.append(regex[i:i + 2])
            i += 2
            continue
        if ch == "[":                      # classe já escrita à mão
            j = regex.index("]", i)
            out.append(regex[i:j + 1])
            i = j + 1
            continue
        if ch == "m":
            out.append("(?:m|rn)")
        elif ch in _SIG_OCR and len(_SIG_OCR[ch]) > 1:
            out.append("[" + _SIG_OCR[ch] + "]")
        else:
            out.append(ch)
        i += 1
    return "".join(out)


# átomo de classe com grupo nomeado por código
_atomos = []
for cod, extensos, siglas in CLASSES:
    # (?![\d\s.]*\d\b): a tolerância OCR (S↔5, l↔1, O↔0) não pode transformar um número em sigla
    formas = [frase(e) for e in extensos] + [rf"(?![\d.]*\d(?![A-Za-z]))(?-i:{sig(s)})" for s in siglas]
    _atomos.append(f"(?P<{cod}>{_alt(formas)})")
ATOMO = r"(?:" + "|".join(_atomos) + r")"
_ATOMO_SIMPLES = re.sub(r"\(\?P<\w+>", "(?:", ATOMO)

ORDINAL = r"(?:" + _alt([frase(o) for o in ORDINAIS]) + r")"
CONECTOR = r"(?:\s+(?:n[oaóãà0]s?|N[OA0]S?|[ec][mn]|ern|EM|d[oaóãà0]s?|D[OA]S?|d[ec]|DE)\s+|\s*[-–]\s*|\s+)"
# preposições com ruído de OCR, para os demais padrões
DO = r"(?:d[oaóãõà0]s?|D[OA]S?)"
EM = r"(?:[ec][mn]|ern|EM)"
# cadeia: [ordinal] ATOMO (conector [ordinal] ATOMO)*
CADEIA = (rf"(?:{ORDINAL}\s+)?{_ATOMO_SIMPLES}"
          rf"(?:{CONECTOR}(?:{ORDINAL}\s+)?{_ATOMO_SIMPLES})*")
RE_ATOMO = re.compile(ATOMO, re.I)

TRIB = r"(?:" + "|".join(
    [f"(?P<t_{t}>(?-i:{t}\\b)|{_alt([frase(x) for x in _TRIB_EXTENSO[t]])})" for t in TRIBUNAIS]) + r")"
_TRIB_SIMPLES = re.sub(r"\(\?P<\w+>", "(?:", TRIB)
RE_TRIB = re.compile(TRIB, re.I)

UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
       "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"]
UF = r"(?-i:" + "|".join(UFS) + r")"


def codigos(cadeia: str) -> list[str]:
    """'AgInt no Recurso Especial' → ['AgInt', 'REsp']"""
    out = []
    for m in RE_ATOMO.finditer(cadeia):
        cod = next(k for k, v in m.groupdict().items() if v is not None)
        out.append(cod)
    return out


def tribunal_de(texto: str) -> str | None:
    m = RE_TRIB.search(texto)
    if not m:
        return None
    return next(k[2:] for k, v in m.groupdict().items() if v is not None)


# ----------------------------------------------------------------------------- leis
# código canônico da lei → formas de citação
LEIS = {
    "CF": ["constituição federal de 1988", "constituição federal", "constituição da república federativa do brasil",
           "constituição da república", "carta magna", "constituição", "(?-i:CF/88)", "(?-i:CF/1988)", "(?-i:CRFB/88)",
           "(?-i:CRFB)", "(?-i:CF)"],
    "L13105/2015": ["código de processo civil", "(?-i:CPC/2015)", "(?-i:CPC/15)", "(?-i:NCPC)", "(?-i:CPC)"],
    "DL3689/1941": ["código de processo penal", "(?-i:CPP)"],
    "L10406/2002": ["código civil", "(?-i:CC/2002)", "(?-i:CC)"],
    "DL5452/1943": ["consolidação das leis do trabalho", "(?-i:CLT)"],
    "DL1001/1969": ["código penal militar", "(?-i:CPM)"],
    "DL1002/1969": ["código de processo penal militar", "(?-i:CPPM)"],
    "DL2848/1940": ["código penal", "(?-i:CP)"],
    "L8078/1990": ["código de defesa do consumidor", "(?-i:CDC)"],
    "L4737/1965": ["código eleitoral", "(?-i:CE)"],
    "LC64/1990": ["lei das inelegibilidades", "lei de inelegibilidade"],
    "L9504/1997": ["lei das eleições"],
    "L8069/1990": ["estatuto da criança e do adolescente", "(?-i:ECA)"],
    "L5172/1966": ["código tributário nacional", "(?-i:CTN)"],
}
# número/ano de cada código (para casar "Lei nº 13.105/2015" com o CPC etc.)
NUMERO_DA_LEI = {
    "13105": "L13105/2015", "3689": "DL3689/1941", "10406": "L10406/2002", "5452": "DL5452/1943",
    "1001": "DL1001/1969", "1002": "DL1002/1969", "2848": "DL2848/1940", "8078": "L8078/1990",
    "4737": "L4737/1965", "9504": "L9504/1997", "8069": "L8069/1990", "5172": "L5172/1966",
}
NUMERO_DA_LC = {"64": "LC64/1990"}


def _forma_lei(f):
    return f if f.startswith("(?-i:") else frase(f)


LEI_NOMEADA = r"(?:" + "|".join(
    f"(?P<l_{re.sub(r'[^A-Za-z0-9]', '_', k)}>{_alt([_forma_lei(f) for f in fs])})" for k, fs in LEIS.items()) + r")"
_LEI_NOMEADA_SIMPLES = re.sub(r"\(\?P<\w+>", "(?:", LEI_NOMEADA)
_NUM_LEI = r"\d{1,2}(?:\.\d{3}|\d{3})?|\d{1,5}"
LEI_NUMERADA = (rf"(?:{frase('lei complementar')}|(?-i:LC)|{frase('decreto-lei')}|(?-i:DL)|{frase('lei')}|(?-i:L\.))"
                rf"\s*(?:n[º°o.]*\s*)?(?:{_NUM_LEI})(?:\s*/\s*(?:\d{{4}}|\d{{2}})|,\s*de\s+\d{{1,2}}[º°]?\s+de\s+\w+\s+de\s+\d{{4}})?")
LEI = rf"(?:{LEI_NUMERADA}|{_LEI_NOMEADA_SIMPLES})"
RE_LEI_NOMEADA = re.compile(LEI_NOMEADA, re.I)


def lei_canonica(trecho: str) -> str | None:
    """'Lei nº 13.105/2015' → 'L13105/2015'; 'CLT' → 'DL5452/1943'; 'Lei nº 9.504/97' → 'L9504/1997'."""
    m = re.search(rf"(?:({frase('lei complementar')}|LC)|({frase('decreto-lei')}|DL)|{frase('lei')}|L\.)"
                  rf"\s*(?:n[º°o.]*\s*)?({_NUM_LEI})(?:\s*/\s*(\d{{4}}|\d{{2}})|,\s*de\s+\d{{1,2}}[º°]?\s+de\s+\w+\s+de\s+(\d{{4}}))?",
                  trecho, re.I)
    if m:
        num = re.sub(r"\D", "", m.group(3))
        ano = m.group(4) or m.group(5)
        if ano and len(ano) == 2:
            ano = ("19" if int(ano) > 30 else "20") + ano
        if m.group(1):
            if num in NUMERO_DA_LC and (not ano or NUMERO_DA_LC[num].endswith(ano)):
                return NUMERO_DA_LC[num]
            return f"LC{num}/{ano}" if ano else f"LC{num}"
        if num in NUMERO_DA_LEI and (not ano or NUMERO_DA_LEI[num].endswith(ano)):
            return NUMERO_DA_LEI[num]
        pref = "DL" if m.group(2) else "L"
        return f"{pref}{num}/{ano}" if ano else f"{pref}{num}"
    # nome do código: fica com o match MAIS LONGO ("Código de Processo Penal Militar" ≠ CPP)
    melhor, tam = None, 0
    for lei, formas in _LEIS_RE.items():
        for rx in formas:
            m = rx.search(trecho)
            if m and m.end() - m.start() > tam:
                melhor, tam = lei, m.end() - m.start()
    return melhor


_LEIS_RE = {k: [re.compile(rf"(?<![A-Za-z]){_forma_lei(f)}(?![A-Za-z])", re.I) for f in fs] for k, fs in LEIS.items()}
