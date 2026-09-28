"""Avalia um submission.csv contra um gabarito no formato do goldenset, com a métrica oficial.

Uso:  python scripts/evaluate.py <submission.csv> [--gold data/goldenset_offsets.csv] [--erros]
"""
import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "vendor"))

import kaggle_metric  # noqa: E402


def carregar_gold(caminho) -> tuple[pd.DataFrame, list[dict]]:
    with open(caminho, encoding="utf-8-sig") as f:
        linhas = list(csv.DictReader(f))
    por_doc, nivel = defaultdict(list), {}
    for r in linhas:
        nivel[r["documento_id"]] = int(r["nivel"])
        ids = r.get("id_canonico") or "-"
        por_doc[r["documento_id"]].append(f"{r['inicio']},{r['fim']},{r['classificacao']},{ids or '-'}")
    docs = sorted(nivel)
    sol = pd.DataFrame({"documento_id": docs, "nivel": [nivel[d] for d in docs],
                        "citacoes": ["|".join(por_doc[d]) or "-" for d in docs]})
    return sol, linhas


def relatorio_erros(sub: pd.DataFrame, linhas: list[dict]) -> None:
    preds = {}
    for _, r in sub.iterrows():
        preds[r["documento_id"]] = kaggle_metric._parse_submission_cell(r["citacoes"], r["documento_id"])
    golds = defaultdict(list)
    for r in linhas:
        golds[r["documento_id"]].append(dict(inicio=int(r["inicio"]), fim=int(r["fim"]),
                                             classe=r["classificacao"], ids=r.get("id_canonico") or "",
                                             trecho=r["trecho"]))
    for doc in sorted(set(golds) | set(preds)):
        g, p = golds.get(doc, []), preds.get(doc, [])
        pares, gs, ps = kaggle_metric._casar(g, p)
        for gi, pi in pares:
            a, b = g[gi], p[pi]
            if a["classe"] != b["classe"] or (a["classe"] == "real" and str(b["id_canonico"]) not in a["ids"].split(":")):
                print(f"[CLASSE] {doc} {a['trecho']!r}: gold={a['classe']}/{a['ids']} pred={b['classe']}/{b['id_canonico']}")
        for gi in gs:
            print(f"[FN]     {doc} {g[gi]['trecho']!r} ({g[gi]['classe']}) {g[gi]['inicio']}-{g[gi]['fim']}")
        matched = [g[gi] for gi, _ in pares]
        for pi in ps:
            if not any(kaggle_metric._contida(p[pi], x) for x in matched):
                print(f"[FP]     {doc} {p[pi]['inicio']}-{p[pi]['fim']} {p[pi]['classe']}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("submission")
    ap.add_argument("--gold", default=str(RAIZ / "data" / "goldenset_offsets.csv"))
    ap.add_argument("--erros", action="store_true")
    a = ap.parse_args()
    sol, linhas = carregar_gold(a.gold)
    sub = pd.read_csv(a.submission, dtype=str, keep_default_na=False)
    r = kaggle_metric.avaliar(sol, sub)
    for n, d in r["niveis"].items():
        f1 = " ".join(f"{k}={v:.4f}" for k, v in d["f1_por_classe"].items())
        print(f"nível {n}: score={d['score']:.4f} macroF1={d['macro_f1']:.4f} tau={d['tau']:.4f} bonus={d['b']:.4f} | {f1}")
    print(f"SCORE FINAL: {r['score_final']:.5f}")
    if a.erros:
        relatorio_erros(sub, linhas)


if __name__ == "__main__":
    main()
