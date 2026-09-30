"""Sistema 2 sem o modelo: gatilhos, re-ancoragem e decisão (o LLM é substituído por um dublê)."""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from citeverify.frases import segmentar  # noqa: E402
from citeverify.kb import carregar  # noqa: E402
from citeverify.pipeline import processar  # noqa: E402
from citeverify.sistema2 import ancorar, decidir_s2, escalar  # noqa: E402

DB = RAIZ / "data" / "desafio1_bracis.db"
CORPO = "Cuida-se de recurso especial interposto contra acórdão do tribunal de origem, como se vê.\n"


@pytest.fixture(scope="module")
def kb():
    if not DB.exists():
        pytest.skip("base canônica ausente (rode `make data`)")
    return carregar(DB, RAIZ / "out" / "kb.pkl")


class Duble:
    """Faz o papel do LLM: devolve trechos pré-definidos por frase."""
    def __init__(self, respostas):
        self.respostas, self.chamadas = respostas, 0

    def extrair(self, frase):
        self.chamadas += 1
        return next((v for k, v in self.respostas.items() if k in frase), [])


def test_segmentar_respeita_abreviacoes():
    t = "Incide o art. 5º da CF. Rel. Min. Nancy Andrighi julgou. Nova frase aqui."
    assert [t[a:b] for a, b in segmentar(t)] == ["Incide o art. 5º da CF.", "Rel. Min. Nancy Andrighi julgou.",
                                                 "Nova frase aqui."]


def test_ancorar_literal_e_com_quebra():
    t = CORPO + "Consoante assentado no STJ - REsp: 1741784\nPR 2018/0116304-1, a tese não prospera."
    a, b = len(CORPO), len(t)
    assert ancorar(t, a, b, "STJ - REsp: 1741784 PR 2018/0116304-1") is not None
    assert ancorar(t, a, b, "algo que não está na frase") is None


def test_escalar_so_frase_nao_coberta():
    t = CORPO + "Reforça o argumento o AgRg no Rec. Esp. n. 1.522.200 (SC), de resto conhecido. " \
                "Consoante assentado no STJ - REsp: 1741784 PR 2018/0116304-1, a tese não prospera."
    from citeverify.extract import extrair
    oc = [(c.inicio, c.fim) for c in extrair(t)]
    frases = [t[a:b] for a, b in escalar(t, oc)]
    assert frases == ["Consoante assentado no STJ - REsp: 1741784 PR 2018/0116304-1, a tese não prospera."]


def test_decidir_s2_real_so_com_chave_exata(kb):
    t = CORPO + "Consoante assentado no STJ - REsp: 1741784 PR 2018/0116304-1, a tese não prospera."
    ini = t.index("STJ - REsp")
    fim = t.index(", a tese")
    c, d = decidir_s2(t, ini, fim, kb, vagas=False)
    assert d.classe == "real" and d.regra == "s2_real"
    t2 = t.replace("1741784", "1741785")
    c, d = decidir_s2(t2, ini, fim, kb, vagas=False)
    assert d.classe == "inventada"


def test_decidir_s2_vaga_so_na_convencao_v(kb):
    t = CORPO + "Na mesma linha, cite-se o entendimento remansoso deste Sodalício, cuja ratio se amolda ao caso."
    ini = t.index("entendimento")
    fim = t.index(", cuja")
    assert decidir_s2(t, ini, fim, kb, vagas=False) is None
    assert decidir_s2(t, ini, fim, kb, vagas=True)[1].classe == "incompleta"


def test_s2_nao_sobrescreve_s1(kb):
    t = CORPO + "Reforça o argumento o AgRg no Rec. Esp. n. 1.522.200 (SC), de resto conhecido."
    duble = Duble({"Reforça": ["AgRg no Rec. Esp. n. 1.522.200"]})
    c = processar("t", t, kb, s2=duble)["citacoes"]
    assert [x["trecho"] for x in c] == ["AgRg no Rec. Esp. n. 1.522.200 (SC)"] and duble.chamadas == 0


def test_s2_acha_formato_novo(kb):
    t = CORPO + "Consoante assentado no STJ - REsp: 1741784 PR 2018/0116304-1, a tese não prospera."
    duble = Duble({"Consoante": ["STJ - REsp: 1741784 PR 2018/0116304-1"]})
    c = processar("t", t, kb, s2=duble, debug=True)["citacoes"]
    assert [(x["classificacao"], x["_regra"]) for x in c] == [("real", "s2_real")]


def test_s2_descarta_parafrase(kb):
    t = CORPO + "Tal compreensão encontra eco no julgado do STF proferido em 2024 pela relatoria de Dias Toffoli."
    duble = Duble({"Tal": ["STF, 2024, relatoria de Dias Toffoli"]})   # paráfrase: não ancora
    c = processar("t", t, kb, s2=duble)["citacoes"]
    assert [x["trecho"] for x in c] == ["julgado do STF proferido em 2024 pela relatoria de Dias Toffoli"]


def test_s2_respeita_numero_proprio_e_ato_atacado(kb):
    t = ("Processo nº 7914012-80.2011.6.01.8633\n\nPARECER\n\n" + CORPO +
         "Invoca-se, ainda, a  Nos autos do processo nº 7914012-80.2011.6.01.8633, em trâmite, a defesa reiterou. "
         "O acórdão recorrido diverge frontalmente do que assentado na origem.")
    duble = Duble({"Nos autos": ["processo nº 7914012-80.2011.6.01.8633"], "O acórdão": ["acórdão recorrido"]})
    assert processar("t", t, kb, s2=duble, vagas=True)["citacoes"] == []
