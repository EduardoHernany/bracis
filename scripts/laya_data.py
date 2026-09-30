"""Dados por frase para a triagem neural (Laya): A = citação identificada, B = referência vaga, C = nenhuma.

Rótulos derivados dos gabaritos (R para A; V para B). Treino: st1–8 (moldes do dev); avaliação: dev, hd11–13 e
adv21–24 (com slots e frases vagas inéditos). Estes dados derivam dos dados da competição e NÃO são publicados.

Uso:  python3 scripts/laya_data.py [--out out/laya] [--n-train 3000] [--seed 0]
"""
import argparse
import csv
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

from citeverify.extract import extrair  # noqa: E402
from citeverify.frases import segmentar  # noqa: E402
from citeverify.laya_s1 import QUESTAO  # noqa: E402
from citeverify.pipeline import ler_texto  # noqa: E402

UM = {"A": {"A": 1.0, "B": 0.0, "C": 0.0}, "B": {"A": 0.0, "B": 1.0, "C": 0.0}, "C": {"A": 0.0, "B": 0.0, "C": 1.0}}


def spans(gold_csv: Path) -> dict[str, list[tuple[int, int]]]:
    out: dict[str, list[tuple[int, int]]] = {}
    if gold_csv.exists():
        for r in csv.DictReader(open(gold_csv, encoding="utf-8-sig")):
            out.setdefault(r["documento_id"], []).append((int(r["inicio"]), int(r["fim"])))
    return out


def rotular(pasta: Path, gold_r: Path, gold_v: Path, conjunto: str) -> list[dict]:
    r, v = spans(gold_r), spans(gold_v)
    itens = []
    for txt in sorted((pasta).glob("*.txt")):
        texto = ler_texto(txt)
        s1 = [(c.inicio, c.fim) for c in extrair(texto)]
        for a, b in segmentar(texto):
            def toca(lst):
                return any(a < f and i < b for i, f in lst)
            rot = "A" if toca(r.get(txt.stem, [])) else ("B" if toca(v.get(txt.stem, [])) else "C")
            itens.append({"state": texto[a:b].replace("\n", " "), "rotulo": rot, "doc": txt.stem, "conjunto": conjunto,
                          "s1_cobre": toca(s1), "nivel": 2 if "_n2_" in txt.stem else 1})
    return itens


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RAIZ / "out" / "laya"))
    ap.add_argument("--n-train", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(a.seed)
    # treino: st1–8 (frases repetidas entre cópias são deduplicadas)
    treino, vistos = [], set()
    for s in range(1, 9):
        p = RAIZ / "out" / f"st{s}"
        for it in rotular(p / "txt", p / "gold.csv", p / "gold_V.csv", f"st{s}"):
            if it["state"] not in vistos:
                vistos.add(it["state"])
                treino.append(it)
    por = {k: [x for x in treino if x["rotulo"] == k] for k in "ABC"}
    quota = {"A": int(a.n_train * 0.35), "B": int(a.n_train * 0.25), "C": int(a.n_train * 0.40)}
    # B e C têm poucas frases únicas (os corpos do estresse repetem os do dev): completa com variantes ruidosas
    import stress_gen
    stress_gen.HARD = 2
    amostra = []
    for k, lst in por.items():
        rng.shuffle(lst)
        base = lst[:quota[k]]
        extra, i = [], 0
        while len(base) + len(extra) < quota[k] and lst:
            it = dict(lst[i % len(lst)])
            it["state"] = stress_gen.ruido_texto(it["state"], rng)
            extra.append(it)
            i += 1
        amostra += base + extra
    rng.shuffle(amostra)
    with open(out / "train.jsonl", "w", encoding="utf-8") as f:
        for it in amostra:
            f.write(json.dumps({"state": it["state"], "questions": QUESTAO,
                                "gold": {"cita": {"probabilities": UM[it["rotulo"]], "label": it["rotulo"]}}},
                               ensure_ascii=False) + "\n")
    print(f"treino: {len(amostra)} frases ({ {k: sum(x['rotulo'] == k for x in amostra) for k in 'ABC'} }), "
          f"únicas {({k: len(v) for k, v in por.items()})}")
    # avaliação
    aval = []
    aval += rotular(RAIZ / "data" / "txt", RAIZ / "data" / "goldenset_offsets.csv",
                    RAIZ / "out" / "vagas" / "gold_dev_V.csv", "dev")
    for s in (11, 12, 13):
        p = RAIZ / "out" / f"hd{s}"
        aval += rotular(p / "txt", p / "gold.csv", p / "gold_V.csv", f"hd{s}")
    for s in (21, 22, 23, 24):
        p = RAIZ / "out" / f"adv{s}"
        aval += rotular(p / "txt", p / "gold.csv", p / "gold_V.csv", f"adv{s}")
    with open(out / "eval.jsonl", "w", encoding="utf-8") as f:
        for it in aval:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
    cont = {}
    for it in aval:
        cont.setdefault(it["conjunto"][:3], {}).setdefault(it["rotulo"], 0)
        cont[it["conjunto"][:3]][it["rotulo"]] += 1
    print(f"avaliação: {len(aval)} frases {cont}")


if __name__ == "__main__":
    main()
