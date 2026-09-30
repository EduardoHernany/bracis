"""Segmentação em frases que respeita as abreviações do texto jurídico (art., nº, Min., Rel., fls., Ag.…)."""
import re

_ABREV = {"art", "arts", "n", "nº", "no", "min", "rel", "rec", "esp", "fls", "fl", "ag", "int", "reg", "crim", "emb",
          "decl", "dcl", "c", "col", "e", "eg", "egr", "ap", "sr", "sra", "dr", "dra", "p", "pp", "inc", "al", "v",
          "cf", "ex", "des", "proc", "resp", "pet", "rcl", "recl", "súm", "sum", "j", "dje", "dj", "a", "s"}
# candidato a fim de frase: . ; ! ? seguido de espaço e maiúscula (ou do fim do texto), ou parágrafo em branco
_FIM = re.compile(r"[.;!?](?=\s+[A-ZÀ-Ý\"“(]|\s*$)|\n[ \t]*\n")


def segmentar(texto: str) -> list[tuple[int, int]]:
    """[(início, fim)] das frases, sem os espaços das bordas."""
    cortes = []
    for m in _FIM.finditer(texto):
        if m.group() == ".":
            palavra = re.search(r"([A-Za-zÀ-ÿº]+)\.?$", texto[max(0, m.start() - 12):m.start() + 1])
            w = palavra.group(1) if palavra else ""
            sigla = len(w) >= 2 and w.isupper()          # "da CF." termina frase; "cf." (confira) não
            if w and not sigla and (w.lower() in _ABREV or len(w) == 1):
                continue
        cortes.append(m.end())
    out, ini = [], 0
    for fim in cortes + [len(texto)]:
        a, b = ini, fim
        while a < b and texto[a].isspace():
            a += 1
        while b > a and texto[b - 1].isspace():
            b -= 1
        if b > a:
            out.append((a, b))
        ini = fim
    return out
