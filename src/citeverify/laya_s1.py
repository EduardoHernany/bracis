"""Sistema 1 neural (opcional): triagem por frase com o Laya (convaiinnovations/laya-multilingual, Apache-2.0).

O Laya é um classificador encoder não generativo ("System One"): recebe um estado (a frase) e perguntas tipadas,
e devolve probabilidades por opção. Aqui ele só decide QUAIS frases o Sistema 2 (LLM) examina — nunca decide a
classe de uma citação. Checkpoint na revisão fixada em models.lock.json (ou o ajuste fino publicado).
Determinismo: CPU, fp32, threads fixas, lote fixo.
"""
from pathlib import Path

QUESTAO = {"cita": {
    "type": "choice",
    "instructions": "A frase, de uma peça processual brasileira, invoca alguma fonte do direito como fundamento?",
    "criteria": {
        "A": "sim, identificada: processo ou recurso com número, súmula, tema, artigo de lei, "
             "ou julgado identificado por tribunal, ano ou relator",
        "B": "sim, mas vaga: invoca jurisprudência, precedentes, súmula ou lei sem identificá-los",
        "C": "não invoca nenhuma fonte do direito",
    }}}


class TriagemLaya:
    def __init__(self, caminho: str | Path, limiar: float = 0.5, threads: int = 6, lote: int = 16):
        import torch
        torch.set_num_threads(threads)
        import laya
        self.agent = laya.load(str(caminho), device="cpu")
        self.limiar, self.lote = limiar, lote
        self._cache: dict[str, float] = {}

    def probabilidades(self, frases: list[str]) -> list[dict[str, float]]:
        res = self.agent.predict_batch(frases, QUESTAO, batch_size=self.lote)
        return [r["answers"]["cita"]["probabilities"] if "answers" in r else r["cita"]["probabilities"] for r in res]

    def p_cita(self, frase: str) -> float:
        if frase not in self._cache:
            p = self.probabilidades([frase])[0]
            self._cache[frase] = p.get("A", 0.0) + p.get("B", 0.0)
        return self._cache[frase]

    def suspeita(self, frase: str) -> bool:
        return self.p_cita(frase) >= self.limiar
