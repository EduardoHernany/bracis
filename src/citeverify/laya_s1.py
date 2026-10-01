"""Sistema 1 neural (opcional): o Laya (convaiinnovations/laya-multilingual, Apache-2.0, ajustado) por frase.

O Laya é um classificador encoder não generativo ("System One"): recebe um estado (a frase) e perguntas tipadas
e devolve probabilidades por opção. Aqui ele responde, para cada frase que o S1 não cobriu: "a frase invoca uma
fonte do direito — identificada (A), vaga (B) ou nenhuma (C)?".

Papel no pipeline (só na convenção V, --vagas): quando P(B) é alta, uma regra DETERMINÍSTICA delimita o sintagma
nominal da referência (artigo + núcleo jurídico + complementos, até vírgula/relativa/verbo). O Laya decide que há
uma referência vaga; o span nunca vem do modelo. Nunca decide `real` nem `inventada`.

Determinismo: CPU, fp32, threads fixas, lote fixo (mesma entrada → mesmas probabilidades, conferido em 2 passadas).
"""
import re
from pathlib import Path

from .extract import Candidata, zona_cabecalho
from .frases import segmentar
from .resolve import Decisao, _d
from .textnorm import fuzzy
from .vagas import _FRONTEIRA

QUESTAO = {"cita": {
    "type": "choice",
    "instructions": "A frase, de uma peça processual brasileira, invoca alguma fonte do direito como fundamento?",
    "criteria": {
        "A": "sim, identificada: processo ou recurso com número, súmula, tema, artigo de lei, "
             "ou julgado identificado por tribunal, ano ou relator",
        "B": "sim, mas vaga: invoca jurisprudência, precedentes, súmula ou lei sem identificá-los",
        "C": "não invoca nenhuma fonte do direito",
    }}}

# núcleos de FONTE invocada (sem "acórdão", "decisão", "tese": na peça, esses costumam ser o ato atacado)
_FONTES = ["jurisprudência", "entendimento", "precedente", "precedentes", "orientação", "verbete", "súmula",
           "enunciado", "dispositivo", "lei", "legislação", "norma", "normas", "julgados", "preceito", "diploma"]
_ART = r"(?:o|a|os|as|no|na|nos|nas|do|da|dos|das|ao|à|aos|às|pelo|pela|pelos|pelas)"
_NUC = r"(?:" + "|".join(fuzzy(n) for n in sorted(_FONTES, key=len, reverse=True)) + r")"
_VERBO = (r"(?:é|foi|são|foram|afastou|afasta|afastaram|encerra|encerrou|incide|incidem|dispõe|prevê|"
          r"determina|estabelece|assegura|impõe|autoriza|veda)")
_PAL = r"[A-Za-zÀ-ÿ'´`-]+"
RE_SN = re.compile(
    rf"(?<![A-Za-zÀ-ÿ]){_ART}\s+(?P<sn>(?:{_PAL}\s+)?{_NUC}(?![A-Za-zÀ-ÿ])"
    rf"(?:(?!{_FRONTEIRA}|\s+{_VERBO}\b)\s+{_PAL}){{0,7}})",
    re.I)
_ATO_ATACADO = re.compile(r"(?i)\b(?:recorrid|agravad|impugnad|hostilizad|embargad|guerread)[oa]s?\b")
_TITULO = re.compile(r"^[\sIVXLC\d.—–-]*[A-ZÀ-Ý\s—–\-,.:]+$")
_NUC_RX = re.compile(rf"(?<![A-Za-zÀ-ÿ]){_NUC}(?![A-Za-zÀ-ÿ])", re.I)


class TriagemLaya:
    def __init__(self, caminho: str | Path, limiar_b: float = 0.9, threads: int = 6, lote: int = 16):
        import torch
        torch.set_num_threads(threads)
        import laya
        self.agent = laya.load(str(caminho), device="cpu")
        self.limiar_b, self.lote = limiar_b, lote
        self.chamadas = 0

    def probabilidades(self, frases: list[str]) -> list[dict[str, float]]:
        if not frases:
            return []
        self.chamadas += len(frases)
        res = self.agent.predict_batch(frases, QUESTAO, batch_size=self.lote)
        return [r["answers"]["cita"]["probabilities"] for r in res]


def frases_identificadas(texto: str, ocupados: list[tuple[int, int]], s1: TriagemLaya,
                         limiar_a: float = 0.5) -> list[tuple[int, int]]:
    """Papel do Laya na convenção R (Sistema 1 → Sistema 2): frases fora do cabeçalho e não cobertas pelas regras
    em que P(A) — citação identificada — passa do limiar. Vão ao LLM, que propõe o trecho; as regras decidem."""
    fim_cab = zona_cabecalho(texto)
    alvo = [(a, b) for a, b in segmentar(texto)
            if a >= fim_cab and not _TITULO.match(texto[a:b]) and not any(a < f and i < b for i, f in ocupados)]
    probs = s1.probabilidades([texto[a:b].replace("\n", " ") for a, b in alvo])
    return [f for f, p in zip(alvo, probs) if p.get("A", 0.0) >= limiar_a]


def vagas_neurais(texto: str, ocupados: list[tuple[int, int]], s1: TriagemLaya) -> list[tuple[Candidata, Decisao]]:
    """Frases fora do cabeçalho, não cobertas e com núcleo de fonte: se o Laya der P(B) >= limiar, o primeiro
    sintagma nominal de fonte (2–8 palavras, sem dígito, que não seja o ato atacado) vira `incompleta`."""
    fim_cab = zona_cabecalho(texto)
    alvo = []
    for a, b in segmentar(texto):
        trecho = texto[a:b]
        if a < fim_cab or _TITULO.match(trecho) or not _NUC_RX.search(trecho):
            continue
        if any(a < f and i < b for i, f in ocupados):
            continue
        alvo.append((a, b))
    probs = s1.probabilidades([texto[a:b].replace("\n", " ") for a, b in alvo])
    out = []
    for (a, b), p in zip(alvo, probs):
        if p.get("B", 0.0) < s1.limiar_b:
            continue
        for m in RE_SN.finditer(texto, a, b):
            sn = m.group("sn")
            if re.search(r"\d", sn) or _ATO_ATACADO.search(sn) or not 2 <= len(sn.split()) <= 8:
                continue
            ini, fim = m.start("sn"), m.end("sn")
            tipo = "lei" if re.search(r"(?i)dispositiv|\blei|legisla|norma|preceito|diploma", sn) else "jurisprudencia"
            c = Candidata(ini, fim, "vaga", {"tipo": tipo}, 0)
            out.append((c, _d("incompleta", tipo, None, "s1_vaga")))
            break
    return out
