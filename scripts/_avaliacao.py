"""Helpers de avaliação compartilhados por evaluate.py, calibrate.py e ab.py (métrica oficial, sem edição)."""
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "vendor"))
sys.path.insert(0, str(RAIZ / "src"))

import kaggle_metric  # noqa: E402
from json_to_submission import encode  # noqa: E402

GOLD_DEV = RAIZ / "data" / "goldenset_offsets.csv"
GOLD_DEV_V = RAIZ / "out" / "vagas" / "gold_dev_V.csv"


def carregar_gold(caminho) -> tuple[pd.DataFrame, list[dict]]:
    """Gabarito no formato do goldenset → (solution no formato da métrica, linhas cruas)."""
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


def conjuntos(spec: str) -> list[tuple[str, Path, Path]]:
    """'dev,devV,st1-8,hd11-13,adv21-24' → [(nome, pasta_txt, gold_csv)]."""
    out = []
    for parte in spec.split(","):
        parte = parte.strip()
        if parte == "dev":
            out.append(("dev", RAIZ / "data" / "txt", GOLD_DEV))
        elif parte == "devV":
            out.append(("devV", RAIZ / "data" / "txt", GOLD_DEV_V))
        else:
            m = re.fullmatch(r"([a-z]+)(\d+)(?:-(\d+))?", parte)
            if not m:
                raise SystemExit(f"conjunto inválido: {parte}")
            pref, a, b = m.group(1), int(m.group(2)), int(m.group(3) or m.group(2))
            for s in range(a, b + 1):
                pasta = RAIZ / "out" / f"{pref}{s}"
                out.append((f"{pref}{s}", pasta / "txt", pasta / "gold.csv"))
    return out


def prever(pasta_txt: Path, kb, **flags) -> dict[str, dict]:
    """Roda o pipeline em processo (debug=True, para ter a regra de cada predição)."""
    from citeverify.pipeline import ler_texto, processar
    return {t.stem: processar(t.stem, ler_texto(t), kb, debug=True, **flags) for t in sorted(pasta_txt.glob("*.txt"))}


def submissao(preds: dict[str, dict]) -> pd.DataFrame:
    docs = sorted(preds)
    return pd.DataFrame({"documento_id": docs, "citacoes": [encode(preds[d]) for d in docs]})


def pontuar(gold_csv: Path, preds: dict[str, dict]) -> dict:
    sol, _ = carregar_gold(gold_csv)
    return kaggle_metric.avaliar(sol, submissao(preds))


def casar(gold_csv: Path, preds: dict[str, dict]):
    """Para cada documento: (pares [(gold, pred)], golds sem par, preds espúrias). Preds trazem `_regra`."""
    sol, _ = carregar_gold(gold_csv)
    out = []
    for _, linha in sol.iterrows():
        doc = linha["documento_id"]
        golds = kaggle_metric._parse_solution_cell(linha["citacoes"], doc)
        cits = preds.get(doc, {"citacoes": []})["citacoes"]
        ps = [dict(inicio=c["inicio"], fim=c["fim"], classe=c["classificacao"],
                   id_canonico=(c["resolucao"] or {}).get("id_canonico"), confianca=c["confianca"],
                   regra=c.get("_regra", "?"), trecho=c["trecho"]) for c in cits]
        pares, g_sem, p_sem = kaggle_metric._casar(golds, ps)
        casados = [golds[gi] for gi, _ in pares]
        espurias = [ps[pi] for pi in p_sem if not any(kaggle_metric._contida(ps[pi], g) for g in casados)]
        out.append((doc, [(golds[gi], ps[pi]) for gi, pi in pares], [golds[gi] for gi in g_sem], espurias))
    return out


def acertou(g: dict, p: dict) -> bool:
    if g["classe"] != p["classe"]:
        return False
    return g["classe"] != "real" or str(p["id_canonico"]) in g["doc_ids"]
