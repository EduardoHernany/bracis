"""Modo --adv do gerador de estresse: moldes, distratores e ruídos que o dev não mostra.

Tudo aqui é escrito de forma independente do extrator, com um RNG próprio (a saída sem --adv não muda):
  - cabeçalho e fecho novos: número do próprio processo (às vezes uma chave real da base), "Ref.: Autos nº",
    "Classe: … nº", OAB com UF que colide com sigla de classe (MS, RO, AC, AP, RR), "Cidade/UF, data", endereço;
  - ruído de número: NBSP, quebra de linha antes do separador, "-\\n", hífen não-quebrável, letra-OCR no primeiro
    e no último dígito (só letra↔dígito, nunca dígito↔dígito);
  - OCR no início da palavra ("5TF", "T5E", "lsabel");
  - variantes de súmula, tema e lei, súmula de tribunal fora da base, acórdãos com chave compartilhada;
  - subconjunto "novo": frases com slots inéditos, preenchidos com citação ou com frase vaga inédita.
"""
import random
import re

UFS_COLIDEM = ["MS", "RO", "AC", "AP", "RR"]
CIDADES = [("Campo Grande", "MS"), ("Porto Velho", "RO"), ("Rio Branco", "AC"), ("Macapá", "AP"), ("Boa Vista", "RR"),
           ("Curitiba", "PR"), ("Goiânia", "GO"), ("Belém", "PA"), ("Manaus", "AM"), ("Natal", "RN")]
MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]
NOMES = ["Mariana Costa Albuquerque", "Rafael Tavares Linhares", "Helena Duarte Figueiredo", "Otávio Brandão Leite",
         "Lúcia Menezes Prado", "Caio Henrique Sampaio", "Beatriz Nogueira Faria", "Tiago Moura Rezende"]
TITULOS = ["MEMORIAL", "CONTRARRAZÕES", "PARECER", "RAZÕES DE APELAÇÃO", "AGRAVO INTERNO", "MANIFESTAÇÃO"]
CABECAS = ["EXCELENTÍSSIMO SENHOR MINISTRO RELATOR", "COLENDA TURMA", "EGRÉGIO TRIBUNAL", "SENHOR MINISTRO PRESIDENTE"]

# slots inéditos (fora dos moldes do dev) — {A} é o artigo; a citação entra logo depois
SLOTS_NOVOS = [
    "Na mesma linha, cite-se {A} {CIT}, cuja ratio se amolda ao caso.",
    "Consoante assentado n{A} {CIT}, a tese recursal não prospera.",
    "Tal compreensão encontra eco n{A} {CIT}.",
    "Em reforço, traz-se à colação {A} {CIT}, de todo pertinente.",
    "Sobre o ponto, é elucidativ{A} {A} {CIT}.",
    "Aplica-se, ademais, {A} {CIT} à hipótese dos autos.",
    "No mesmo diapasão, {A} {CIT} afastou pretensão idêntica.",
    "Destaca-se, ainda, {A} {CIT}, amplamente citad{A} pela doutrina.",
    "Por fim, mencione-se {A} {CIT}, que encerra a discussão.",
    "Não por acaso, {A} {CIT} é reiteradamente invocad{A} nesta Corte.",
]
# frases vagas inéditas (gênero, texto)
VAGAS_NOVAS = [
    ("o", "entendimento remansoso deste Sodalício"), ("a", "firme jurisprudência da Corte Especial"),
    ("os", "precedentes invocados pela parte recorrente"), ("a", "legislação processual aplicável"),
    ("a", "norma de regência da espécie"), ("a", "orientação consolidada das Turmas"),
    ("a", "súmula aplicável ao caso concreto"), ("a", "jurisprudência dominante do Tribunal Superior Eleitoral"),
    ("o", "dispositivo legal pertinente"), ("os", "julgados colacionados na inicial"),
]


class Adv:
    def __init__(self, ger, rng: random.Random):
        self.ger, self.rng = ger, rng
        kb = ger.kb
        # chaves compartilhadas por acórdãos com cadeias de classe diferentes (o desempate por classe resolve)
        self.compartilhadas = [k for k, ids in kb.por_chave.items() if len(ids) > 1
                               and len({tuple(kb.registros[i].classes) for i in ids}) == len(ids)]

    # --------------------------------------------------------------------- distratores
    def numero_proprio(self) -> str:
        rng = self.rng
        if rng.random() < 0.3:     # uma chave real da base: mesmo assim é o processo do próprio documento
            return rng.choice([k for k in self.ger.kb.por_chave if "-" in k and "." in k])
        j = rng.choice(["5", "6", "7", "8"])
        return (f"{rng.randint(1, 9_999_999):07d}-{rng.randint(10, 99)}.{rng.randint(2010, 2025)}.{j}."
                f"{rng.randint(1, 27):02d}.{rng.randint(1, 9999):04d}")

    def oab(self) -> str:
        rng = self.rng
        uf = rng.choice(UFS_COLIDEM + ["SP", "MG"])
        num = f"{rng.randint(1, 99)}.{rng.randint(100, 999)}" if rng.random() < 0.5 else str(rng.randint(1000, 99999))
        return rng.choice([f"OAB/{uf} {num}", f"OAB-{uf} {num}", f"OAB/{uf} nº {num}", f"OAB {uf} {num}"])

    def cabecalho(self) -> tuple[str, str]:
        rng, own = self.rng, self.numero_proprio()
        linhas = [rng.choice(CABECAS), ""]
        linhas.append(rng.choice([f"AUTOS DO PROCESSO Nº {own}", f"Ref.: Autos nº {own}", f"Processo nº {own}",
                                  f"Classe: Apelação Criminal nº {own}", f"Referência: autos nº {own}"]))
        if rng.random() < 0.5:
            linhas.append(f"Recorrente: {rng.choice(NOMES)}")
        linhas.append(f"Advogado: {rng.choice(NOMES)} ({self.oab()})")
        if rng.random() < 0.5:
            linhas.append(f"Protocolo nº {rng.randint(2019, 2025)}.{rng.randint(1_000_000, 9_999_999)}")
        linhas += ["", rng.choice(TITULOS), "", ""]
        return "\n".join(linhas), own

    def frase_autos(self, own: str) -> str:
        return self.rng.choice([f" Nos autos do processo nº {own}, em trâmite, a defesa reiterou os pedidos.",
                                f" Consta dos autos nº {own} que a intimação foi regular."])

    def fecho(self) -> str:
        rng = self.rng
        cidade, uf = rng.choice(CIDADES)
        sep = rng.choice(["/", " - ", "/"])
        data = f"{rng.randint(1, 28)} de {rng.choice(MESES)} de {rng.randint(2020, 2025)}"
        end = f"Endereço para intimações: Rua das Palmeiras, nº {rng.randint(10, 999)}, Ap. {rng.randint(101, 1504)}."
        return f"\n\n{end}\n\n{cidade}{sep}{uf}, {data}.\n\n{rng.choice(NOMES)}\n{self.oab()}\n"

    # --------------------------------------------------------------------- ruídos de número e de palavra
    def ruido_numero(self, s: str) -> str:
        """Só letra↔dígito, NBSP, hífens e quebras; o dígito em si nunca muda."""
        rng = self.rng
        m = list(re.finditer(r"\d[\d.\-]*\d", s))
        if not m:
            return s
        m = max(m, key=lambda x: len(x.group()))
        num = m.group()
        op = rng.choice(["nbsp_marcador", "nbsp_milhar", "nl_antes", "hifen_nl", "u2011", "ocr_borda", "nada"])
        if op == "nbsp_marcador" and m.start() > 0 and s[m.start() - 1] == " ":
            return s[:m.start() - 1] + " " + s[m.start():]
        if op == "nbsp_milhar" and "." in num and "-" not in num:
            num = num.replace(".", " ")
        elif op == "nl_antes":
            pos = [i for i, ch in enumerate(num) if ch in ".-" and i > 0]
            if pos:
                i = rng.choice(pos)
                num = num[:i] + "\n" + num[i:]
        elif op == "hifen_nl":
            pos = [i for i, ch in enumerate(num) if ch in ".-"]
            if pos:
                i = rng.choice(pos)
                num = num[:i + 1] + "\n" + num[i + 1:]
        elif op == "u2011" and "-" in num:
            num = num.replace("-", "‑", 1)
        elif op == "ocr_borda":
            ocr = {"0": "O", "1": "l", "5": "S", "6": "G", "8": "B", "9": "g"}
            i = rng.choice([0, len(num) - 1])
            if num[i] in ocr:
                num = num[:i] + ocr[num[i]] + num[i + 1:]
        return s[:m.start()] + num + s[m.end():]

    def ruido_inicial(self, s: str) -> str:
        """OCR na primeira letra da palavra: STF→5TF, TSE→T5E, Isabel→lsabel, Sérgio→5érgio."""
        rng = self.rng
        opcoes = [(r"\bST([FJM])\b", r"5T\1"), (r"\bTS([ET])\b", r"T5\1"), (r"\bI(?=[a-zà-ÿ])", "l"),
                  (r"\bS(?=[a-zà-ÿ])", "5")]
        rng.shuffle(opcoes)
        for pad, rep in opcoes:
            if re.search(pad, s):
                return re.sub(pad, rep, s, count=1)
        return s

    # --------------------------------------------------------------------- variantes de citação
    def variante(self, t: str, tipo: str, classe: str, ids: str, ruido: bool) -> tuple[str, str, str, str]:
        rng, kb = self.rng, self.ger.kb
        if classe == "real" and tipo == "jurisprudencia" and "úmula" in t.lower() and rng.random() < 0.6:
            rid = int(ids)
            (trib, n, vinc) = next(k for k, v in kb.sumulas.items() if v == rid)
            formas = [f"Súmula {n} do c. {trib}", f"Súmula nº {n} do col. {trib}", f"Enunciado {n} da Súmula do {trib}",
                      f"Súmula do {trib} nº {n}", f"Súmula {n}/{trib}"]
            if vinc:
                formas = [f"SV {n}", f"Súmula Vinculante nº {n}", f"Enunciado {n} da Súmula Vinculante"]
            if (trib, n) == ("TST", 331):
                formas += ["Súmula 331, IV, do TST", "Súmula nº 331, item IV, do TST"]
            return rng.choice(formas), tipo, classe, ids
        if classe == "inventada" and tipo == "jurisprudencia" and rng.random() < 0.12:
            outro = rng.choice(["TJSP", "TJMG", "TRF-1", "TRF-4", "TRT-2", "TNU"])
            return f"Súmula {rng.randint(1, 700)} do {outro}", tipo, "inventada", ""
        if classe == "inventada" and t.lower().startswith("tema") and rng.random() < 0.7:
            n = re.sub(r"\D", "", t)
            return rng.choice([f"Tema Repetitivo {n}", f"Tema RG {n}", f"Tema {n}/STF",
                               f"Tema de Repercussão Geral nº {n}"]), tipo, classe, ids
        if classe == "real" and tipo == "lei" and rng.random() < 0.3:
            rid = int(ids)
            (lei, art) = next(k for k, v in kb.dispositivos.items() if v == rid)
            if lei == "CF":
                a = f"{art}º" if art < 10 else str(art)
                return rng.choice([f"art. {a}, CF/88", f"art. {a} da Lei Maior", f"art. {a} da Carta da República"]), \
                    tipo, classe, ids
        if classe == "inventada" and tipo == "lei" and rng.random() < 0.2:
            return rng.choice(["art. 896-A da CLT", "art. 41-A da Lei nº 9.504/1997", "art. 373 do CPC/73",
                               "art. 186 do CC/16"]), tipo, "inventada", ""
        if classe == "real" and tipo == "jurisprudencia" and self.compartilhadas and rng.random() < 0.08:
            cit = self.compartilhada(ruido)
            if cit:
                return cit
        if tipo == "jurisprudencia" and ruido:
            t = self.ruido_numero(t)
            if classe == "incompleta" and rng.random() < 0.3:
                t = self.ruido_inicial(t)
        return t, tipo, classe, ids

    def compartilhada(self, ruido: bool):
        """Acórdão cuja chave é compartilhada por outro com cadeia diferente: o desempate por classe decide."""
        from stress_gen import cadeia_do_cabecalho, fmt_cnj, fmt_plain, marcador, renderizar_cadeia, uf_do_cabecalho
        rng, ger = self.rng, self.ger
        chave = rng.choice(self.compartilhadas)
        rid = rng.choice(sorted(ger.kb.por_chave[chave]))
        r = ger.kb.registros[rid]
        cadeia = cadeia_do_cabecalho(ger.textos[rid], r.tribunal)
        rend = renderizar_cadeia(cadeia, rng) if cadeia else None
        if not rend:
            return None
        num = fmt_cnj(chave, rng, ruido) if ("-" in chave and "." in chave) else fmt_plain(chave, rng)
        uf = uf_do_cabecalho(ger.textos[rid], r.tribunal)
        return f"{rend} {marcador(rng, ruido)}{num}{'/' + uf if uf else ''}", "jurisprudencia", "real", str(rid)

    # --------------------------------------------------------------------- subconjunto "novo"
    def frase_nova(self, citacao: tuple | None) -> tuple[str, int, int, tuple]:
        """Frase com slot inédito. Se `citacao` for None, o slot recebe uma frase vaga inédita.
        Devolve (frase, início e fim do preenchimento dentro da frase, (tipo, classe, ids))."""
        rng = self.rng
        molde = rng.choice(SLOTS_NOVOS)
        if citacao is None:
            art, texto = rng.choice(VAGAS_NOVAS)
            meta = ("lei" if re.search(r"legisla|norma|dispositivo", texto) else "jurisprudencia", "incompleta", "")
        else:
            texto, tipo, classe, ids = citacao
            art, meta = ("a" if re.match(r"(?i)s[úu]mula|rcl|reclama|apela|a[çc][ãa]o", texto) else "o"), (tipo, classe, ids)
        antes, depois = molde.split("{CIT}")
        antes, depois = antes.replace("{A}", art), depois.replace("{A}", art)
        frase = " " + antes + texto + depois
        ini = 1 + len(antes)
        return frase, ini, ini + len(texto), meta
