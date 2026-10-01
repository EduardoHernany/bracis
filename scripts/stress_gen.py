"""Gera um conjunto de estresse "cego" com gabarito conhecido.

Pega os documentos de dev e troca cada citação do gabarito por outra, sorteada da
base INTEIRA (não só dos acórdãos que o dev cita), renderizada com variantes de
superfície e ruído de OCR. O vocabulário daqui é escrito de forma independente
do extrator — de propósito — para que o teste não seja circular.

Uso:  python scripts/stress_gen.py --n 3 --seed 7 --out out/stress
      (n = cópias de cada documento de dev; gera txt/ e gold.csv)
"""
import argparse
import csv
import random
import re
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))
from citeverify.kb import carregar  # noqa: E402

UF_NOME = {"ACRE": "AC", "ALAGOAS": "AL", "AMAPÁ": "AP", "AMAZONAS": "AM", "BAHIA": "BA", "CEARÁ": "CE",
           "DISTRITO FEDERAL": "DF", "ESPÍRITO SANTO": "ES", "GOIÁS": "GO", "MARANHÃO": "MA", "MATO GROSSO DO SUL": "MS",
           "MATO GROSSO": "MT", "MINAS GERAIS": "MG", "PARÁ": "PA", "PARAÍBA": "PB", "PARANÁ": "PR", "PERNAMBUCO": "PE",
           "PIAUÍ": "PI", "RIO DE JANEIRO": "RJ", "RIO GRANDE DO NORTE": "RN", "RIO GRANDE DO SUL": "RS", "RONDÔNIA": "RO",
           "RORAIMA": "RR", "SANTA CATARINA": "SC", "SÃO PAULO": "SP", "SERGIPE": "SE", "TOCANTINS": "TO"}
UFS = sorted(set(UF_NOME.values()))

# formas de citação por classe (independentes do extrator)
FORMAS = {
    "RECURSO ESPECIAL ELEITORAL": ["REspe", "REspEl", "RESPE", "Recurso Especial Eleitoral", "REspe."],
    "AGRAVO EM RECURSO ESPECIAL ELEITORAL": ["AREspE", "AREspEl", "Agravo em Recurso Especial Eleitoral"],
    "AGRAVO EM RECURSO ESPECIAL": ["AREsp", "ARESP", "Agravo em Recurso Especial", "A.REsp", "AgREsp"],
    "RECURSO ESPECIAL": ["REsp", "RESP", "R.Esp.", "Rec. Esp.", "Recurso Especial", "Resp"],
    "RECURSO EXTRAORDINÁRIO COM AGRAVO": ["ARE", "Recurso Extraordinário com Agravo"],
    "RECURSO EXTRAORDINÁRIO": ["RE", "Recurso Extraordinário", "RE."],
    "RECURSO EM HABEAS CORPUS": ["RHC", "Recurso em Habeas Corpus", "R.H.C."],
    "RECURSO EM MANDADO DE SEGURANÇA": ["RMS", "Recurso em Mandado de Segurança"],
    "RECURSO ORD. EM MANDADO DE SEGURANÇA": ["RMS", "Recurso Ordinário em Mandado de Segurança"],
    "RECURSO EM SENTIDO ESTRITO": ["RSE", "Recurso em Sentido Estrito", "RESE"],
    "RECURSO ORDINÁRIO ELEITORAL": ["RO", "Recurso Ordinário Eleitoral", "ROEl"],
    "RECURSO ORDINÁRIO": ["RO", "Recurso Ordinário"],
    "HABEAS CORPUS CRIMINAL": ["HC", "Habeas Corpus"],
    "HABEAS CORPUS": ["HC", "Habeas Corpus", "H.C."],
    "MANDADO DE SEGURANÇA CÍVEL": ["MS", "Mandado de Segurança"],
    "MANDADO DE SEGURANÇA": ["MS", "Mandado de Segurança"],
    "RECLAMAÇÃO": ["Rcl", "RCL", "Recl.", "Reclamação"],
    "AÇÃO RESCISÓRIA": ["AR", "Ação Rescisória"],
    "AÇÃO PENAL": ["AP", "Ação Penal", "APn"],
    "APELAÇÃO CRIMINAL": ["APL", "Apelação Criminal", "Ap. Crim.", "Apelação"],
    "APELAÇÃO": ["APL", "Apelação"],
    "AGRAVO INTERNO CRIMINAL": ["AgInt", "Agravo Interno"],
    "AGRAVO INTERNO": ["AgInt", "Agravo Interno", "Ag. Int.", "AGINT"],
    "AGRAVO REGIMENTAL": ["AgRg", "AgR", "Agravo Regimental", "Ag.Reg."],
    "AG.REG.": ["AgR", "AgRg", "Ag.Reg.", "Agravo Regimental"],
    "AgRg": ["AgRg", "AgR", "Agravo Regimental"],
    "AgInt": ["AgInt", "Agravo Interno", "Ag. Int."],
    "EDcl": ["EDcl", "ED", "Embargos de Declaração", "EDs"],
    "EMB.DECL.": ["ED", "EDcl", "Embargos de Declaração"],
    "EMBARGOS DE DECLARAÇÃO CRIMINAL": ["ED", "Embargos de Declaração"],
    "EMBARGOS DE DECLARAÇÃO": ["ED", "EDcl", "Embargos de Declaração"],
    "EMBARGOS DE DIVERGÊNCIA EM RESP": ["EREsp", "Embargos de Divergência em REsp"],
    "EMBARGOS INFRINGENTES E DE NULIDADE": ["EIN", "Embargos Infringentes e de Nulidade", "Embargos Infringentes"],
    "AGRAVO DE INSTRUMENTO": ["AI", "Agravo de Instrumento"],
    "CONFLITO DE COMPETÊNCIA": ["CC", "Conflito de Competência"],
    "CONFLITO DE JURISDIÇÃO": ["CJ", "Conflito de Jurisdição"],
    "SUSPENSÃO DE LIMINAR E DE SENTENÇA": ["SLS", "Suspensão de Liminar e de Sentença"],
    "SUSPENSÃO DE SEGURANÇA": ["SS", "Suspensão de Segurança"],
    "PETIÇÃO": ["Pet", "Petição"],
    "PRESTAÇÃO DE CONTAS": ["PC", "Prestação de Contas"],
    "REPRESENTAÇÃO": ["Rp", "Representação"],
    "CORREIÇÃO PARCIAL MILITAR": ["Correição Parcial"],
    "RECURSO DE REVISTA COM AGRAVO": ["ARR"],
    "RECURSO DE REVISTA": ["RR"],
    "AGRAVO": ["Ag", "Agravo"],
}
_CHAVES_FORMAS = sorted(FORMAS, key=len, reverse=True)
ORDINAL = {"SEGUNDO": "Segundo", "TERCEIRO": "Terceiro"}


def cadeia_do_cabecalho(texto: str, tribunal: str) -> str | None:
    """Recupera a cadeia de classes (em caixa alta) que precede o número no cabeçalho."""
    cab = texto[:400]
    cab = re.split(r"AC[ÓO]RD[ÃA]O|TURMA|PLEN[ÁA]RIO|Pleno|Justiça", cab)[-1]
    m = re.search(r"([A-Za-zÁÉÍÓÚÂÊÔÃÕÇ.\s\-]{2,160}?)\s*(?:N[º°o]\.?|n\.\s*º)?\s*\d", cab)
    if not m:
        return None
    s = re.sub(r"\s+", " ", m.group(1)).strip()
    s = re.sub(r"^(?:EXTRATO.*?|Secretaria do Tribunal Pleno|Poder Judiciário STM|SUPERIOR TRIBUNAL MILITAR)\s*", "", s)
    return s or None


def renderizar_cadeia(cadeia: str, rng: random.Random) -> str | None:
    """'AgInt no AGRAVO EM RECURSO ESPECIAL' → 'AgInt no AREsp' (formas aleatórias)."""
    partes, s = [], cadeia
    while s:
        s = s.strip()
        m = re.match(r"(?i)(no|na|nos|nas|em)\s+", s)
        if m and partes:
            partes.append(m.group(1).lower())
            s = s[m.end():]
            continue
        m = re.match(r"(SEGUNDO|TERCEIRO)\s+", s)
        if m:
            partes.append(ORDINAL[m.group(1)])
            s = s[m.end():]
            continue
        for k in _CHAVES_FORMAS:
            if s.upper().startswith(k.upper()):
                partes.append(rng.choice(FORMAS[k]))
                s = s[len(k):]
                break
        else:
            return None
    if not partes or partes[-1] in ("no", "na", "nos", "nas", "em"):
        return None
    return " ".join(partes)


def uf_do_cabecalho(texto: str, tribunal: str) -> str | None:
    cab = texto[:400]
    if tribunal == "STJ":
        m = re.search(r"\d\s*-\s*([A-Z]{2})\b", cab)
        return m.group(1) if m else None
    if tribunal == "STM":
        m = re.search(r"\d{4}/([A-Z]{2})\b", cab)
        return m.group(1) if m else None
    for nome in sorted(UF_NOME, key=len, reverse=True):
        if nome in cab.upper():
            return UF_NOME[nome]
    return None


# ----------------------------------------------------------------------------- números

def fmt_plain(d: str, rng) -> str:
    grupos = []
    x = d
    while len(x) > 3:
        grupos.insert(0, x[-3:])
        x = x[:-3]
    grupos.insert(0, x)
    return rng.choice([".".join(grupos), d, " ".join(grupos) if len(grupos) > 1 else d])


def fmt_cnj(k: str, rng, ruido: bool) -> str:
    seq, resto = k.split("-")
    dv, ano, j, tr, orig = resto.split(".")
    seq_fmt = seq.zfill(7) if len(seq) > 5 or rng.random() < 0.5 else seq
    base = f"{seq_fmt}-{dv}.{ano}.{j}.{tr}.{orig}"
    if ruido:
        base = rng.choice([base, f"{seq_fmt}-{dv}{ano}{j}{tr}{orig}", f"{seq_fmt}-{dv} {ano} {j} {tr} {orig}",
                           f"{seq_fmt}-{dv}. {ano}.{j}.{tr}.{orig}", base.replace("-", "--", 1)])
    return base


OCR_NUM = {"0": "O", "1": "l", "5": "S", "9": "g", "6": "G", "8": "B"}
OCR_TXT = [("m", "rn"), ("e", "c"), ("i", "l"), ("c", "e"), ("S", "5"), ("a", "ã"), ("o", "ó")]


def ruido_numero(s: str, rng) -> str:
    chars = list(s)
    idx = [i for i, ch in enumerate(chars) if ch in OCR_NUM and 0 < i < len(chars) - 1 and chars[i - 1].isdigit()]
    if idx and rng.random() < 0.35:
        i = rng.choice(idx)
        chars[i] = OCR_NUM[chars[i]]
    s = "".join(chars)
    if rng.random() < 0.2 and "." in s:               # espaço após ponto
        i = s.index(".")
        s = s[:i + 1] + " " + s[i + 1:]
    return s


HARD = 1   # --hard N: aplica cada tipo de ruído N vezes


def ruido_texto(s: str, rng) -> str:
    for _ in range(HARD - 1):
        s = _ruido_texto(s, rng)
    return _ruido_texto(s, rng)


def _ruido_texto(s: str, rng) -> str:
    if rng.random() < 0.3:
        a, b = rng.choice(OCR_TXT)
        pos = [m.start() for m in re.finditer(re.escape(a), s)]
        pos = [p for p in pos if p > 0 and s[p - 1].isalpha()]
        if pos:
            p = rng.choice(pos)
            s = s[:p] + b + s[p + len(a):]
    return s


def quebra_linha(s: str, rng) -> str:
    for _ in range(HARD - 1):
        s = _quebra_linha(s, rng)
    return _quebra_linha(s, rng)


def _quebra_linha(s: str, rng) -> str:
    esp = [m.start() for m in re.finditer(" ", s)]
    if esp and rng.random() < 0.3:
        p = rng.choice(esp)
        s = s[:p] + "\n" + s[p + 1:]
    return s


def sufixo_uf(uf: str | None, rng, ruido: bool) -> str:
    if not uf or rng.random() < 0.15:
        return ""
    opcoes = [f"/{uf}"] + ([f" - {uf}", f" ({uf})", f"/ {uf}", f"-{uf}", f" – {uf}"] if ruido else [])
    return rng.choice(opcoes)


def marcador(rng, ruido: bool) -> str:
    return rng.choice(["nº ", "", "n. ", "Nº "] + (["n° ", "No ", "N° ", "nº  "] if ruido else []))


# ----------------------------------------------------------------------------- geradores por classe

class Gerador:
    def __init__(self, db: str, rng: random.Random):
        self.rng = rng
        self.kb = carregar(db, RAIZ / "out" / "kb.pkl")
        con = sqlite3.connect(db)
        self.textos = {rid: t for rid, t in con.execute("SELECT id, texto FROM documentos")}
        unicos = {next(iter(v)) for v in self.kb.por_chave.values() if len(v) == 1}
        self.acordaos = [r for r in self.kb.registros.values()
                         if r.natureza == "acordao" and r.id in unicos
                         and all(len(self.kb.por_chave[k]) == 1 for k in r.chaves)]
        self.todas_chaves = set(self.kb.por_chave) | self.kb.citadas

    def real(self, ruido: bool, tribunal: str | None = None):
        rng = self.rng
        for _ in range(200):
            r = rng.choice(self.acordaos)
            if tribunal and r.tribunal != tribunal and rng.random() < 0.7:
                continue
            chave = sorted(r.chaves, key=len, reverse=True)[0]
            cadeia = cadeia_do_cabecalho(self.textos[r.id], r.tribunal)
            if r.tribunal == "TST":
                m = re.search(r"autos\s+de\s+[^.]{0,200}?n\s*\.?\s*[º°o]s?\s*TST\s*-\s*((?:[A-Za-z]+\s*-\s*)*)\d",
                              self.textos[r.id], re.I | re.S)
                if not m:
                    continue
                classes = re.sub(r"\s", "", m.group(1))
                pref = rng.choice(["TST-", "processo nº TST-", "", "Processo n° TST- "]) if ruido else rng.choice(["TST-", "processo nº TST-", ""])
                num = fmt_cnj(chave, rng, ruido)
                txt = f"{pref}{classes}{num}"
            else:
                if not cadeia:
                    continue
                rend = renderizar_cadeia(cadeia, rng)
                if not rend:
                    continue
                if "-" in chave and "." in chave:
                    num = fmt_cnj(chave, rng, ruido)
                else:
                    num = fmt_plain(chave, rng)
                uf = uf_do_cabecalho(self.textos[r.id], r.tribunal)
                txt = f"{rend} {marcador(rng, ruido)}{num}{sufixo_uf(uf, rng, ruido)}"
            if ruido:
                txt = ruido_texto(txt, rng)
                txt = re.sub(r"[\d.\-]+", lambda m: ruido_numero(m.group(), rng), txt, count=1)
                txt = quebra_linha(txt, rng)
            return txt, "jurisprudencia", "real", str(r.id)
        raise RuntimeError("sem acórdão")

    def inventada(self, ruido: bool):
        rng = self.rng
        tipo = rng.random()
        if tipo < 0.12:
            n = rng.randint(12, 999)
            if any(num == n for (_, num, _) in self.kb.sumulas):
                n += 1000
            trib = rng.choice(["STF", "STJ", "TST", "TSE"])
            vinc = trib == "STF" and rng.random() < 0.5
            txt = f"{rng.choice(['Súmula', 'Súm.', 'SÚMULA', 'Súmula nº'])}{' Vinculante' if vinc else ''} {n} do {trib}"
            if vinc and rng.random() < 0.5:
                txt = f"Súmula Vinculante {n}"
            return (ruido_texto(txt, rng) if ruido else txt), "jurisprudencia", "inventada", ""
        if tipo < 0.16:
            return f"Tema {fmt_plain(str(rng.randint(100, 1400)), rng)} da repercussão geral", "jurisprudencia", "inventada", ""
        if tipo < 0.35:
            lei, nome = rng.choice([("CF", "da Constituição Federal"), ("CPC", "do Código de Processo Civil"),
                                    ("CPC", "do CPC"), ("CLT", "da CLT"), ("CDC", "do Código de Defesa do Consumidor"),
                                    ("L9504", "da Lei nº 9.504/1997"), ("L13467", "da Lei nº 13.467/2017"),
                                    ("CE", "do Código Eleitoral"), ("CC", "do Código Civil"),
                                    ("CPM", "do Código Penal Militar"), ("LC64", "da Lei Complementar nº 64/1990")])
            reais = {("CF", 5), ("CF", 7), ("CF", 93), ("CPC", 373), ("CLT", 896), ("CLT", 818), ("CLT", 477),
                     ("CDC", 14), ("CE", 276), ("CC", 186), ("CPM", 290), ("LC64", 1)}
            while True:
                art = rng.randint(2, 1200)
                if (lei, art) not in reais:
                    break
            a = fmt_plain(str(art), rng) if art >= 1000 else str(art)
            txt = f"{rng.choice(['art.', 'art', 'artigo'])} {a} {nome}"
            if ruido:
                txt = quebra_linha(ruido_texto(txt, rng), rng)
            return txt, "lei", "inventada", ""
        # número de processo inexistente
        for _ in range(100):
            estilo = rng.choice(["STJ", "STF", "STM", "TSE", "TST"])
            if estilo in ("STJ", "STF"):
                cls = rng.choice(["REsp", "AgInt no REsp", "AREsp", "RHC", "Rcl", "Reclamação", "RE", "HC",
                                  "Recurso Especial", "AgRg no AREsp", "RMS"])
                d = str(rng.randint(10_000, 2_300_000))
                num = fmt_plain(d, rng)
                chave = d
            else:
                j = {"STM": "7", "TSE": "6", "TST": "5"}[estilo]
                seq = rng.randint(1, 7_099_999)
                chave = f"{seq}-{rng.randint(10, 99)}.{rng.randint(2008, 2025)}.{j}.{rng.randint(0, 27):02d}.{rng.randint(0, 9999):04d}"
                num = fmt_cnj(chave, rng, ruido)
                cls = {"STM": ["APL", "RSE", "AgInt", "Apelação"], "TSE": ["REspe", "AgR-REspe", "AI", "RO"],
                       "TST": ["RR", "TST-RR", "AIRR", "TST-E-RR"]}[estilo]
                cls = rng.choice(cls)
            if chave in self.todas_chaves:
                continue
            sep = "-" if cls.endswith(("RR",)) and estilo == "TST" else " "
            txt = f"{cls}{sep}{marcador(rng, ruido) if sep == ' ' else ''}{num}{sufixo_uf(rng.choice(UFS), rng, ruido) if estilo != 'TST' else ''}"
            if ruido:
                txt = ruido_texto(txt, rng)
                txt = re.sub(r"[\d.\-]+", lambda m: ruido_numero(m.group(), rng), txt, count=1)
                txt = quebra_linha(txt, rng)
            return txt, "jurisprudencia", "inventada", ""
        raise RuntimeError

    def incompleta(self, ruido: bool):
        rng = self.rng
        r = rng.choice([r for r in self.acordaos if r.relator and r.ano])
        nome = re.sub(r"^(?:Min\.|Ministr[oa]|MIN\.)\s*", "", r.relator).strip()
        if rng.random() < 0.5:
            nome = nome.upper() if rng.random() < 0.5 else nome.title()
        cls = rng.choice(["julgado", "precedente", "acórdão"])
        modelos = [
            f"{cls} do {r.tribunal} proferido em {r.ano} pela relatoria de {nome}",
            f"precedente do {r.tribunal} de {r.ano}, da relatoria de {nome}",
            f"acórdão do {r.tribunal} julgado em {r.ano} sob relatoria de {nome}",
            f"{rng.choice(['Reclamação', 'Recurso Especial', 'Agravo em Recurso Especial', 'Habeas Corpus', 'Apelação'])} do {r.tribunal}, de {r.ano}, Rel. Min. {nome}",
            f"{rng.choice(['Rcl', 'REsp', 'AREsp', 'APL', 'RHC', 'HC'])} de {r.ano}, Rel. Min. {nome}",
        ]
        txt = rng.choice(modelos)
        if ruido:
            txt = quebra_linha(ruido_texto(txt, rng), rng)
        return txt, "jurisprudencia", "incompleta", ""

    def lei_real(self, ruido: bool):
        rng = self.rng
        (lei, art), rid = rng.choice(list(self.kb.dispositivos.items()))
        nomes = {"CF": ["da Constituição Federal", "da CF", "da Constituição da República", "da CF/88"],
                 "L13105/2015": ["do CPC", "do Código de Processo Civil", "da Lei nº 13.105/2015"],
                 "DL5452/1943": ["da CLT", "da Consolidação das Leis do Trabalho"],
                 "L8078/1990": ["do CDC", "do Código de Defesa do Consumidor"],
                 "L4737/1965": ["do Código Eleitoral"], "L10406/2002": ["do Código Civil", "do CC"],
                 "DL1001/1969": ["do Código Penal Militar", "do CPM"], "DL3689/1941": ["do Código de Processo Penal", "do CPP"],
                 "LC64/1990": ["da Lei Complementar nº 64/1990", "da LC 64/1990"]}[lei]
        comp = rng.choice(["", "", ", I,", ", § 1º,", ", IX,", ", caput,"])
        a = f"{art}º" if art < 10 else str(art)
        txt = f"{rng.choice(['art.', 'artigo', 'art'])} {a}{comp} {rng.choice(nomes)}"
        if ruido:
            txt = quebra_linha(ruido_texto(txt, rng), rng)
        return txt, "lei", "real", str(rid)

    def sumula_real(self, ruido: bool):
        rng = self.rng
        (trib, n, vinc), rid = rng.choice(list(self.kb.sumulas.items()))
        txt = f"{rng.choice(['Súmula', 'Súmula nº', 'SÚMULA', 'Súm.', 'enunciado da Súmula'])}{' Vinculante' if vinc else ''} {n} do {trib}"
        if ruido and rng.random() < 0.4:
            txt = txt.replace("Súmula", "5úmula")
        return txt, "jurisprudencia", "real", str(rid)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default=str(RAIZ / "out" / "stress"))
    ap.add_argument("--db", default=str(RAIZ / "data" / "desafio1_bracis.db"))
    ap.add_argument("--hard", type=int, default=1)
    ap.add_argument("--adv", action="store_true", help="moldes, distratores e ruídos novos (stress_adv.py)")
    ap.add_argument("--vagas-gold", default=None,
                    help="CSV das frases vagas do dev (out/vagas/vagas_dev.csv): também grava gold_V.csv")
    a = ap.parse_args()
    global HARD
    HARD = a.hard
    rng = random.Random(a.seed)
    ger = Gerador(a.db, rng)
    adv = None
    if a.adv:
        from citeverify.extract import zona_cabecalho
        from stress_adv import Adv
        adv = Adv(ger, random.Random(a.seed * 1000 + 17))
    vagas = {}
    if a.vagas_gold:
        for r in csv.DictReader(open(a.vagas_gold, encoding="utf-8")):
            vagas.setdefault(r["documento_id"], []).append((int(r["inicio"]), int(r["fim"]), r["tipo"]))
    gold = list(csv.DictReader(open(RAIZ / "data" / "goldenset_offsets.csv", encoding="utf-8-sig")))
    out = Path(a.out)
    (out / "txt").mkdir(parents=True, exist_ok=True)
    linhas, linhas_v = [], []
    for txt_path in sorted((RAIZ / "data" / "txt").glob("*.txt")):
        doc = txt_path.stem
        original = open(txt_path, encoding="utf-8", newline="").read()
        cits = sorted([g for g in gold if g["documento_id"] == doc], key=lambda g: int(g["inicio"]))
        nivel = int(cits[0]["nivel"]) if cits else (2 if "_n2_" in doc else 1)
        ruido = nivel == 2
        for k in range(a.n):
            novo, gid, gid_v = [], [], []

            def pos() -> int:
                return sum(len(x) for x in novo)

            def copiar(ini: int, fim: int, inserir: bool = False) -> None:
                """Copia original[ini:fim] (levando as frases vagas); no --adv, pode inserir uma frase nova."""
                corte = None
                if inserir and adv and adv.rng.random() < 0.35:
                    bordas = [m.end() for m in re.finditer(r"\. (?=[A-ZÁÉÍÓÚ])", original[ini:fim])]
                    bordas = [ini + b - 1 for b in bordas
                              if not any(s <= ini + b <= e for s, e, _ in vagas.get(doc, []))]
                    corte = adv.rng.choice(bordas) if bordas else None
                partes = [(ini, corte), (corte, fim)] if corte else [(ini, fim)]
                for j, (x, y) in enumerate(partes):
                    base = pos()
                    for s_, e_, tipo_ in vagas.get(doc, []):
                        if x <= s_ and e_ <= y:
                            gid_v.append((base + s_ - x, base + e_ - x, original[s_:e_], tipo_, "incompleta", ""))
                    novo.append(original[x:y])
                    if j == 0 and corte:
                        nova()

            def nova() -> None:
                """Frase com slot inédito: citação renderizada ou frase vaga inédita (esta só no gabarito V)."""
                sorteio = adv.rng.random()
                cit = None
                if sorteio < 0.6:
                    gerar = adv.rng.choice([ger.real, ger.real, ger.inventada, ger.incompleta, ger.lei_real])
                    cit = gerar(ruido)
                frase, i0, i1, (tipo_, classe_, ids_) = adv.frase_nova(cit)
                base = pos()
                alvo = gid if cit else gid_v
                alvo.append((base + i0, base + i1, frase[i0:i1], tipo_, classe_, ids_))
                novo.append(frase)

            cursor = 0
            if adv:
                cab, own = adv.cabecalho()
                novo.append(cab)
                cursor = zona_cabecalho(original)
                vistos_autos = adv.rng.random() < 0.5
            for g in cits:
                ini, fim = int(g["inicio"]), int(g["fim"])
                copiar(cursor, ini, inserir=True)
                if adv and vistos_autos and ini > cursor:
                    novo.append(adv.frase_autos(own))
                    vistos_autos = False
                classe = g["classificacao"]
                if classe == "real" and g["tipo"] == "lei":
                    t, tipo, cl, ids = ger.lei_real(ruido)
                elif classe == "real" and "úmula" in g["trecho"].lower():
                    t, tipo, cl, ids = ger.sumula_real(ruido)
                elif classe == "real":
                    t, tipo, cl, ids = ger.real(ruido)
                elif classe == "inventada":
                    t, tipo, cl, ids = ger.inventada(ruido)
                else:
                    t, tipo, cl, ids = ger.incompleta(ruido)
                if adv:
                    t, tipo, cl, ids = adv.variante(t, tipo, cl, ids, ruido)
                p0 = pos()
                novo.append(t)
                gid.append((p0, p0 + len(t), t, tipo, cl, ids))
                cursor = fim
            copiar(cursor, len(original), inserir=True)
            if adv:
                novo.append(adv.fecho())
            texto = "".join(novo)
            nome = f"{doc}_s{k}"
            (out / "txt" / f"{nome}.txt").write_text(texto, encoding="utf-8", newline="")
            for destino, itens in ((linhas, gid), (linhas_v, sorted(gid + gid_v))):
                for i, (s, e, t, tipo, cl, ids) in enumerate(sorted(itens)):
                    assert texto[s:e] == t, (nome, t)
                    destino.append({"nivel": nivel, "documento_id": nome, "citacao_id": f"g{i}", "inicio": s,
                                    "fim": e, "trecho": t, "tipo": tipo, "classificacao": cl, "id_canonico": ids})
    with open(out / "gold.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas[0]))
        w.writeheader()
        w.writerows(linhas)
    if a.vagas_gold:
        with open(out / "gold_V.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas_v[0]))
            w.writeheader()
            w.writerows(linhas_v)
    print(f"{out}: {len(list((out / 'txt').glob('*.txt')))} documentos, {len(linhas)} citações"
          + (f" ({len(linhas_v)} na convenção V)" if a.vagas_gold else ""))


if __name__ == "__main__":
    main()
