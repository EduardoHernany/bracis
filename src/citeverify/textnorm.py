"""Normalização tolerante a ruído de OCR, sem reescrever o texto (offsets nativos).

Tudo aqui gera *regex* que casa as variantes sobre o texto original, ou converte
um trecho já casado para uma chave canônica. A garantia da organização — um
dígito nunca é trocado por outro dígito — é o que torna seguro corrigir só
letras parecidas com dígitos e depois exigir match exato.
"""
import re
import unicodedata

# letras que o OCR troca por dígitos (nunca dígito↔dígito)
OCR_DIGITO = {
    "O": "0", "o": "0", "Q": "0", "D": "0",
    "l": "1", "I": "1", "i": "1", "|": "1", "!": "1",
    "S": "5", "s": "5",
    "g": "9", "q": "9",
    "B": "8",
    "G": "6", "b": "6",
    "Z": "2", "z": "2",
}
_LET = "OoQDlIi|!SsgqBGbZz"
_LETRA = r"A-Za-zÀ-ÿ"

# um "caractere de número": dígito, ou letra-OCR colada a um dígito e sem letra do outro lado
_CH = (rf"(?:\d|(?<=\d)[{re.escape(_LET)}](?![{_LETRA}])"
       rf"|(?<![{_LETRA}])[{re.escape(_LET)}](?=\d))")
# separadores que o gerador usa dentro do número: . - – — espaço e quebra de linha
_SEP = r"(?:[ \t]*[.\-–—][ \t]*(?:\n[ \t]*)?(?:[.\-–—][ \t]*(?:\n[ \t]*)?)?|[ \t]*\n[ \t]*|[ \t]{1,2})"
NUMERO = rf"{_CH}+(?:{_SEP}{_CH}+)*"
RE_NUMERO = re.compile(NUMERO)


def digitos(trecho: str) -> str:
    """Só os dígitos do trecho, com letras-OCR convertidas."""
    out = []
    for i, ch in enumerate(trecho):
        if ch.isdigit():
            out.append(ch)
        elif ch in OCR_DIGITO:
            ant = trecho[i - 1] if i > 0 else ""
            prox = trecho[i + 1] if i + 1 < len(trecho) else ""
            if ant.isdigit() or prox.isdigit():
                out.append(OCR_DIGITO[ch])
    return "".join(out)


def chave_cnj(d: str) -> str | None:
    """Número no padrão CNJ/TST/TSE antigo (seq-DV.AAAA.J.TR.OOOO) → chave canônica."""
    if len(d) < 14:
        return None
    seq, dv, ano, j, tr, orig = d[:-13], d[-13:-11], d[-11:-7], d[-7], d[-6:-4], d[-4:]
    if not (1 <= len(seq) <= 7) or not (1940 <= int(ano) <= 2035) or j == "0":
        return None
    return f"{int(seq)}-{dv}.{ano}.{j}.{tr}.{orig}"


def chave_numero(trecho: str) -> tuple[str, str | None] | None:
    """(chave, justiça) — justiça é o dígito J do CNJ ('5' TST, '6' TSE, '7' STM) ou None."""
    d = digitos(trecho)
    if not d or len(d) > 24:
        return None
    cnj = chave_cnj(d)
    if cnj:
        return cnj, cnj.split(".")[2]
    return d.lstrip("0") or "0", None


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


# ----------------------------------------------------------------------------- fuzzy de palavras

_VARIANTES = {
    "a": "aáàâãä@", "e": "eéêèc", "i": "iíìîl1I|", "o": "oóôõò0", "u": "uúùûü",
    "c": "cçe", "ç": "çc", "l": "l1Ii|", "n": "nñ", "s": "s5", "g": "g9",
}


def fuzzy(palavra: str) -> str:
    """Regex de uma palavra tolerante a acentos, caixa e confusões de OCR (m↔rn, e↔c, i↔l…)."""
    partes = []
    for ch in sem_acento(palavra.lower()):
        if ch == "m":
            partes.append("(?:[mM]|[rR][nN])")
        elif ch == " ":
            partes.append(r"\s+")
        elif ch in _VARIANTES:
            vs = _VARIANTES[ch]
            vs = vs + "".join(sorted({x.upper() for x in vs if x.isalpha()} - set(vs)))
            partes.append("[" + re.escape(vs) + "]")
        elif ch.isalpha():
            partes.append(f"[{ch}{ch.upper()}]")
        else:
            partes.append(re.escape(ch))
    return "".join(partes)


def frase(texto: str) -> str:
    """Frase fuzzy: palavras separadas por qualquer espaço/quebra de linha."""
    return r"\s+".join(fuzzy(p) for p in texto.split())
