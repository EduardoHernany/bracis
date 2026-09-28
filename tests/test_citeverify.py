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
