"""A/B das camadas: regras × +S2 (LLM) × +S1 (Laya) nas convenções R (gabarito do dev) e V (com frases vagas).

Uso (no env com llama-cpp-python quando houver S2):
    python scripts/ab.py --variants rules,vagas,s2,vagas+s2 --sets dev,st1,hd11,adv21-24 \\
        --s2 models/s2/Qwen3-4B-Instruct-2507-Q4_K_M.gguf --s2-gpu-layers -1 [--s1 out/laya_ft] --md out/ab/report.md

Variantes: tokens separados por "+": `rules` (base), `vagas` (convenção V), `s2`, `s1`. Uma variante com `vagas`
é pontuada contra o gabarito V (devV / gold_V.csv); as demais, contra o gabarito R.
"""
import argparse
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from _avaliacao import GOLD_DEV_V, acertou, casar, conjuntos, pontuar, prever  # noqa: E402
from citeverify.kb import carregar  # noqa: E402


def gold_da_variante(nome: str, gold: Path, vagas: bool) -> Path | None:
    if not vagas:
        return gold
    if nome == "dev":
        return GOLD_DEV_V
    v = gold.with_name("gold_V.csv")
    return v if v.exists() else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variants", default="rules,vagas")
    ap.add_argument("--sets", default="dev,adv21-24")
    ap.add_argument("--s2", default=None)
    ap.add_argument("--s2-gpu-layers", type=int, default=0)
    ap.add_argument("--s2-threads", type=int, default=6)
    ap.add_argument("--s2-cache", default=str(RAIZ / "out" / "s2_cache.jsonl"))
    ap.add_argument("--s2-somente-cache", action="store_true",
                    help="não carrega o LLM: usa só as respostas já em cache (frase fora do cache → nenhuma)")
    ap.add_argument("--s1", default=None)
    ap.add_argument("--md", default=str(RAIZ / "out" / "ab" / "report.md"))
    ap.add_argument("--db", default=str(RAIZ / "data" / "desafio1_bracis.db"))
    a = ap.parse_args()
    kb = carregar(a.db, RAIZ / "out" / "kb.pkl")
    variantes = [v.strip() for v in a.variants.split(",")]
    s2 = s1 = None
    if any("s2" in v for v in variantes):
        from citeverify.llm import carregar_sistema2
        s2 = carregar_sistema2(a.s2, n_gpu_layers=a.s2_gpu_layers, n_threads=a.s2_threads,
                               cache=None if a.s2_cache == "none" else a.s2_cache,
                               somente_cache=a.s2_somente_cache)
    if any("s1" in v for v in variantes):
        from citeverify.laya_s1 import TriagemLaya
        s1 = TriagemLaya(a.s1)
    linhas = ["| conjunto | variante | gabarito | score | N1 macroF1 | N2 macroF1 | τ | FP | FN | classe errada "
              "| S2 certas | S2 erradas | chamadas LLM | s |", "|" + "---|" * 14]
    for nome, pasta, gold in conjuntos(a.sets):
        for v in variantes:
            toks = set(v.split("+"))
            vagas = "vagas" in toks
            g = gold_da_variante(nome, gold, vagas)
            if g is None or not g.exists():
                continue
            antes = s2.chamadas if s2 else 0
            t0 = time.time()
            preds = prever(pasta, kb, vagas=vagas, s2=s2 if "s2" in toks else None,
                           s1=s1 if "s1" in toks else None)
            dt = time.time() - t0
            r = pontuar(g, preds)
            fp = fn = cls = s2_ok = s2_err = 0
            for _, pares, g_sem, espurias in casar(g, preds):
                fn += len(g_sem)
                fp += len(espurias)
                for gg, p in pares:
                    ok = acertou(gg, p)
                    cls += not ok
                    if p["regra"].startswith("s2_"):
                        s2_ok += ok
                        s2_err += not ok
                s2_err += sum(p["regra"].startswith("s2_") for p in espurias)
            nv = r["niveis"]
            tau = max(d["tau"] for d in nv.values())
            linha = (f"| {nome} | {v} | {'V' if vagas else 'R'} | {r['score_final']:.5f} "
                     f"| {nv.get(1, {}).get('macro_f1', float('nan')):.4f} | {nv.get(2, {}).get('macro_f1', float('nan')):.4f} "
                     f"| {tau:.4f} | {fp} | {fn} | {cls} | {s2_ok} | {s2_err} | {(s2.chamadas - antes) if s2 else 0} | {dt:.0f} |")
            linhas.append(linha)
            print(linha, flush=True)
    if s2 is not None and hasattr(s2, "faltas"):
        print(f"frases fora do cache: {s2.faltas}")
    Path(a.md).parent.mkdir(parents=True, exist_ok=True)
    Path(a.md).write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"→ {a.md}")


if __name__ == "__main__":
    main()
