import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from citeverify.aliases import codigos, lei_canonica  # noqa: E402
from citeverify.extract import extrair  # noqa: E402
from citeverify.kb import carregar  # noqa: E402
from citeverify.pipeline import processar  # noqa: E402
from citeverify.textnorm import chave_numero, digitos  # noqa: E402

DB = RAIZ / "data" / "desafio1_bracis.db"


@pytest.fixture(scope="module")
def kb():
    if not DB.exists():
        pytest.skip("base canônica ausente (rode `make data`)")
    return carregar(DB, RAIZ / "out" / "kb.pkl")


def _unica(kb, texto):
    doc = processar("t", texto, kb)
    assert len(doc["citacoes"]) == 1, doc
    return doc["citacoes"][0]


@pytest.mark.parametrize("trecho,esperado", [
    ("1.741.784", "1741784"),
    ("21737l8", "2173718"),        # l→1
    ("1.45g.779", "1459779"),      # g→9
    ("1.528.4S5", "1528455"),      # S→5
    ("170076O", "1700760"),        # O→0
])
def test_ocr_digitos(trecho, esperado):
    assert digitos(trecho) == esperado


@pytest.mark.parametrize("trecho,chave", [
    ("7000761-84 2021 7 00 0000", "7000761-84.2021.7.00.0000"),
    ("0600216-46.2020-\n.6.14.0022", "600216-46.2020.6.14.0022"),
    ("7001184-1520197000000", "7001184-15.2019.7.00.0000"),
    ("533-80. 2012.6.13.0029", "533-80.2012.6.13.0029"),
])
def test_cnj(trecho, chave):
    assert chave_numero(trecho)[0] == chave


def test_codigos_cadeia():
    assert codigos("EDcl nos EDcl no AgInt no Agravo em Recurso Especial") == ["EDcl", "EDcl", "AgInt", "AREsp"]
    assert codigos("AgRg no Rec. Esp.") == ["AgRg", "REsp"]


@pytest.mark.parametrize("texto,lei", [
    ("CPC", "L13105/2015"), ("Código de Processo Penal Militar", "DL1002/1969"),
    ("Código Penal Militar", "DL1001/1969"), ("LC 64/90", "LC64/1990"), ("Constituição da República", "CF"),
])
def test_lei_canonica(texto, lei):
    assert lei_canonica(texto) == lei


def test_distratores_nao_sao_citacao():
    texto = ("EGRÉGIO SUPERIOR TRIBUNAL DE JUSTIÇA\n\nAutos nº 8416083-51.2022.3.07.4978\n"
             "Protocolo nº 2023.1475691\n(OAB/MG 241945) às fls. 143/925, R$ 168.772,18.\n")
    assert extrair(texto) == []


def test_real_nivel2(kb):
    c = _unica(kb, "Reforça o argumento o AgRg no Rec. Esp. n. 1.522.200 (SC), de resto conhecido.")
    assert c["classificacao"] == "real" and c["resolucao"]["id_canonico"] == "192165489"


def test_real_ocr(kb):
    c = _unica(kb, "Nesse sentido, o AgInt no RESP 21737l8 - SP.")
    assert c["classificacao"] == "real"


def test_apenas_citado_e_inventada(kb):
    # o RE 1.276.977 é mencionado em vários acórdãos, mas não é registro da base
    c = _unica(kb, "Conforme o RE 1.276.977/DF, a tese foi fixada.")
    assert c["classificacao"] == "inventada"


def test_inventada_numero(kb):
    assert _unica(kb, "Veja-se a Rcl 88.178/RS, cuja ratio se aplica.")["classificacao"] == "inventada"


def test_incompleta(kb):
    c = _unica(kb, "o julgado do STF proferido em 2024 pela relatoria de Dias Toffoli, no ponto")
    assert c["classificacao"] == "incompleta"
    assert c["trecho"].endswith("Toffoli")


def test_sumula(kb):
    assert _unica(kb, "Incide a 5úmula 211 do STJ.")["classificacao"] == "real"
    assert _unica(kb, "Incide a Súmula 935 do STF.")["classificacao"] == "inventada"


def test_lei(kb):
    assert _unica(kb, "Incide o art. 373, I, do CPC.")["resolucao"]["id_canonico"] == "28893055"
    assert _unica(kb, "Incide o art. 158 do Código de Defesa do Consumidor.")["classificacao"] == "inventada"


def test_tst(kb):
    c = _unica(kb, "Conforme o processo nº TST-E-RR-173000-49.2008.5.15.0024, a matéria")
    assert c["classificacao"] == "real"


# ----------------------------------------------------------------------------- v2: lacunas do conjunto cego

@pytest.mark.parametrize("trecho,chave", [
    ("0600216-46.2020\n.6.14.0022", "600216-46.2020.6.14.0022"),    # \n antes do separador
    ("1.880\n.529", "1880529"),
    ("7000171\n--39.2023.7.00.0000", "7000171-39.2023.7.00.0000"),
    ("1\xa0307\xa0026", "1307026"),                                 # NBSP como separador de milhar
    ("7000171‑39.2023.7.00.0000", "7000171-39.2023.7.00.0000"),  # hífen não-quebrável
    ("l.741.784", "1741784"),                                       # letra-OCR no primeiro dígito
])
def test_separadores_v2(trecho, chave):
    assert chave_numero(trecho)[0] == chave


def test_real_com_nbsp_e_quebra(kb):
    assert _unica(kb, "Vale invocar o Rec. Esp. nº 1.880\n.529 - SP, de clareza solar.")["resolucao"]["id_canonico"] == "1915411053"
    assert _unica(kb, "Vale invocar o Rec. Esp. nº 1\xa0880\xa0529/SP, de clareza solar.")["resolucao"]["id_canonico"] == "1915411053"


@pytest.mark.parametrize("texto", [
    "Advogado: Fulano de Tal (OAB/MS 12.345).", "Advogada: Beltrana (OAB-RO 4321).", "OAB/AC nº 1.234",
    "inscrito na OAB/AP 998", "OAB RR 1234", "Campo Grande/MS, 12 de março de 2024.",
    "Rio Branco - AC, 3 de junho de 2024.", "residente na Rua das Flores, nº 100, Ap. 302, Centro",
])
def test_distratores_v2(texto):
    assert extrair(texto) == []


def test_mandado_de_seguranca_nao_e_uf(kb):
    assert len(processar("t", "Veja-se o MS 12.345/DF, de clareza solar.", kb)["citacoes"]) == 1
    assert len(processar("t", "Veja-se a Rcl 33.132/AC, cuja ratio se aplica.", kb)["citacoes"]) == 1


def test_cabecalho_proprio(kb):
    texto = ("EXCELENTÍSSIMO SENHOR MINISTRO RELATOR\n\nAUTOS DO PROCESSO Nº 1292746-27.2020.7.13.1173\n"
             "Ref.: Autos nº 1292746-27.2020.7.13.1173\nClasse: Apelação Criminal nº 1292746-27.2020.7.13.1173\n"
             "RECURSO ESPECIAL Nº 1.205.500 - SC (2019/0123456-7)\n\nMEMORIAL\n\n"
             "Cuida-se de apelação interposta contra a sentença que julgou procedente a ação penal, conforme segue.\n"
             "Nos autos do processo nº 1292746-27.2020.7.13.1173, em trâmite, a defesa sustenta a nulidade. "
             "Reforça o argumento o AgRg no Rec. Esp. n. 1.522.200 (SC), de resto conhecido.\n")
    cits = processar("t", texto, kb)["citacoes"]
    assert [c["trecho"] for c in cits] == ["AgRg no Rec. Esp. n. 1.522.200 (SC)"]


def test_zona_cabecalho_dev():
    import csv
    from citeverify.extract import zona_cabecalho
    gold = RAIZ / "data" / "goldenset_offsets.csv"
    if not gold.exists():
        pytest.skip("gabarito ausente")
    primeiro = {}
    for r in csv.DictReader(open(gold, encoding="utf-8-sig")):
        primeiro[r["documento_id"]] = min(primeiro.get(r["documento_id"], 10**9), int(r["inicio"]))
    for doc, ini in primeiro.items():
        texto = open(RAIZ / "data" / "txt" / f"{doc}.txt", encoding="utf-8", newline="").read()
        assert zona_cabecalho(texto) <= ini, doc


@pytest.mark.parametrize("texto,fim", [
    ("o julgado do 5TF proferido em 2024 pela relatoria de Dias Toffoli, no ponto", "Toffoli"),
    ("o precedente do STJ de 2020, da relatoria de lsabel Gallotti, no ponto", "Gallotti"),
    ("o julgado do STF proferido em 2O19 pela relatoria de Dias Toffoli, no ponto", "Toffoli"),
])
def test_incompleta_ocr_inicial(kb, texto, fim):
    c = _unica(kb, texto)
    assert c["classificacao"] == "incompleta" and c["trecho"].endswith(fim)


def test_kb_sem_chaves_espurias(kb):
    for k in ["0", "11", "14", "111", "205", "201", "417", "2010", "2015", "2016", "2017", "1465857", "1990495"]:
        assert k not in kb.por_chave, k
    assert kb.por_chave["185-05.2016.6.25.0024"] == {568736504}
    assert kb.por_chave["598-49.2012.6.08.0018"] == {576309534}
    assert kb.por_chave["234-73.2016.7.11.0211"] == {2381771667}
    assert "2785" in kb.por_chave and "2883" in kb.por_chave


@pytest.mark.parametrize("texto,classe", [
    ("Incide a Súmula 83 do TJSP.", "inventada"),           # τ: tribunal fora da base
    ("Incide a Súmula 83 do TRF-1.", "inventada"),
    ("Incide o art. 896-A da CLT.", "inventada"),           # artigo com sufixo não é o 896
    ("Incide o art. 373 do CPC/73.", "inventada"),          # CPC revogado não é o da base
    ("Incide o art. 373 do CPC.", "real"),
    ("Incide o art. 93, IX, CF/88.", "real"),
    ("Incide o art. 5º da Lei Maior.", "real"),
    ("Incide a Súmula 331, IV, do TST.", "real"),
    ("Incide a SV 10.", "real"),
    ("Incide o Enunciado 83 da Súmula do STJ.", "real"),
    ("Incide a Súmula do STJ nº 83.", "real"),
    ("Incide o Tema Repetitivo 1.076.", "inventada"),
])
def test_variantes_v2(kb, texto, classe):
    assert _unica(kb, texto)["classificacao"] == classe


def test_spans_v2(kb):
    assert _unica(kb, "Incide a Súmula 331, IV, do TST.")["trecho"] == "Súmula 331, IV, do TST"
    assert _unica(kb, "Veja-se o ARE 1.465.332-AgR-segundo/SP, no ponto.")["trecho"] == "ARE 1.465.332-AgR-segundo/SP"
    c = _unica(kb, "Como se depreende do prócesso nº TST-E-RR-173000-49.2008.5.15.0024, a matéria")
    assert c["trecho"] == "prócesso nº TST-E-RR-173000-49.2008.5.15.0024" and c["classificacao"] == "real"


# ----------------------------------------------------------------------------- v2: frases vagas (--vagas)

def test_vaga_so_com_flag(kb):
    texto = "Reforça o argumento a jurisprudência pacífica desta Corte, de resto amplamente conhecida no foro."
    assert processar("t", texto, kb)["citacoes"] == []
    c = processar("t", texto, kb, vagas=True)["citacoes"]
    assert [(x["trecho"], x["classificacao"]) for x in c] == [("jurisprudência pacífica desta Corte", "incompleta")]


def test_vaga_generaliza_pelo_slot(kb):
    texto = "Vale invocar o entendimento consolidado da Corte Especial, de clareza solar quanto ao ponto."
    c = processar("t", texto, kb, vagas=True)["citacoes"]
    assert [x["trecho"] for x in c] == ["entendimento consolidado da Corte Especial"]


def test_vaga_nao_pega_frase_de_enchimento(kb):
    texto = "Cumpre observar que a orientação dos tribunais superiores é firme no ponto. Nada mais."
    assert processar("t", texto, kb, vagas=True)["citacoes"] == []


def test_vaga_nao_duplica_citacao_real(kb):
    texto = "Reforça o argumento o AgRg no Rec. Esp. n. 1.522.200 (SC), de resto conhecido."
    c = processar("t", texto, kb, vagas=True)["citacoes"]
    assert [x["classificacao"] for x in c] == ["real"]


@pytest.mark.parametrize("trecho,chave", [
    ("70007BO--27.2020.7.00.0000", "7000780-27.2020.7.00.0000"),   # duas letras-OCR seguidas
    ("8gg24", "89924"),
    ("7000966--84.2019.7.00.OO00", "7000966-84.2019.7.00.0000"),
])
def test_ocr_sequencia(trecho, chave):
    assert chave_numero(trecho)[0] == chave


def test_sumula_numero_ocr(kb):
    assert _unica(kb, "Incide a SÚMULA B3 do STJ.")["resolucao"]["id_canonico"] == "1289710642"
    assert _unica(kb, "Incide a Súm. 21l do STJ.")["resolucao"]["id_canonico"] == "1289710776"
