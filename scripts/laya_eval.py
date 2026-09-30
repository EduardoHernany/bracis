"""Métricas da triagem neural (Laya) por frase: zero-shot × ajustado, no papel de Sistema 1 do escalonamento.

Uso (env citeverify-ml):  python scripts/laya_eval.py --modelo models/s1 --nome zeroshot [--n 3000] [--limiar 0.5]

Métricas (em out/laya/metricas_<nome>.json/.md):
  - acurácia 3 classes (A identificada, B vaga, C nenhuma);
  - "cita" binário (A∪B × C): precisão, recall, F1 no limiar;
  - recall residual: das frases que o S1 NÃO cobre mas têm citação (o que o LLM precisaria ver), quantas o Laya
    sinaliza; taxa de escalonamento: das frases sem cobertura do S1, quantas vão ao LLM;
  - ECE (15 faixas) de P(cita); latência por frase (CPU, lote fixo); determinismo (2 passadas, |Δp| máx.).
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))


def ece(ps: list[float], ys: list[int], faixas: int = 15) -> float:
    tot, n = 0.0, len(ps)
    for b in range(faixas):
        lo, hi = b / faixas, (b + 1) / faixas
        idx = [i for i, p in enumerate(ps) if lo <= p < hi or (b == faixas - 1 and p == 1.0)]
        if idx:
            conf = sum(ps[i] for i in idx) / len(idx)
            acc = sum(ys[i] for i in idx) / len(idx)
            tot += len(idx) / n * abs(conf - acc)
    return tot


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--nome", required=True)
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--limiar", type=float, default=0.5)
    ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    from citeverify.laya_s1 import TriagemLaya
    itens = [json.loads(x) for x in open(RAIZ / "out" / "laya" / "eval.jsonl", encoding="utf-8")]
    rng = random.Random(a.seed)
    # amostra estratificada: todo o dev; em hd e adv, partes iguais de A, B e C (C = frases sem citação),
    # para que precisão e taxa de escalonamento tenham negativos de verdade
    dev = [x for x in itens if x["conjunto"] == "dev"]
    amostra = list(dev)
    por_conj = max(1, (a.n - len(dev)) // 2)
    for pref in ("hd", "adv"):
        grupo = [x for x in itens if x["conjunto"].startswith(pref)]
        for rot in "ABC":
            lst = [x for x in grupo if x["rotulo"] == rot]
            rng.shuffle(lst)
            amostra += lst[: por_conj // 3]
    t0 = time.time()
    tri = TriagemLaya(a.modelo, limiar=a.limiar, threads=a.threads)
    carga = time.time() - t0
    frases = [x["state"] for x in amostra]
    t0 = time.time()
    probs = tri.probabilidades(frases)
    dt = time.time() - t0
    # determinismo: segunda passada numa subamostra
    sub = frases[:200]
    p2 = tri.probabilidades(sub)
    delta = max(abs(p2[i][k] - probs[i][k]) for i in range(len(sub)) for k in "ABC")
    res = {"modelo": a.modelo, "n": len(amostra), "carga_s": round(carga, 1),
           "latencia_ms_por_frase": round(1000 * dt / len(frases), 1), "determinismo_delta_max": delta}
    for nome, filtro in [("todos", lambda x: True), ("dev", lambda x: x["conjunto"] == "dev"),
                         ("adv", lambda x: x["conjunto"].startswith("adv")), ("hd", lambda x: x["conjunto"].startswith("hd"))]:
        idx = [i for i, x in enumerate(amostra) if filtro(x)]
        if not idx:
            continue
        pred3 = [max("ABC", key=lambda k: probs[i][k]) for i in idx]
        ac3 = sum(p == amostra[i]["rotulo"] for p, i in zip(pred3, idx)) / len(idx)
        pc = [probs[i]["A"] + probs[i]["B"] for i in idx]
        y = [int(amostra[i]["rotulo"] in "AB") for i in idx]
        flag = [int(p >= a.limiar) for p in pc]
        tp = sum(f and t for f, t in zip(flag, y))
        prec = tp / max(1, sum(flag))
        rec = tp / max(1, sum(y))
        f1 = 2 * prec * rec / max(1e-9, prec + rec)
        resid = [j for j, i in enumerate(idx) if not amostra[i]["s1_cobre"]]
        resid_pos = [j for j in resid if y[j]]
        res[nome] = {"n": len(idx), "acuracia_3": round(ac3, 4), "precisao": round(prec, 4), "recall": round(rec, 4),
                     "f1": round(f1, 4), "ece": round(ece(pc, y), 4),
                     "recall_residual": round(sum(flag[j] for j in resid_pos) / max(1, len(resid_pos)), 4),
                     "n_residual_pos": len(resid_pos),
                     "escalonamento": round(sum(flag[j] for j in resid) / max(1, len(resid)), 4)}
    out = RAIZ / "out" / "laya"
    (out / f"metricas_{a.nome}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
