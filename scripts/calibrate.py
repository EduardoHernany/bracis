"""Calibra a confiança de cada regra a partir dos pares casados com o gabarito.

A métrica só usa a confiança nos pares casados (Brier): uma predição espúria não entra no bônus, só no F1.
Por isso a estimativa é a taxa de acerto *dado que casou*:
  - regra sem nenhum erro em pelo menos MIN_EXATO pares → 1,0. Entre times perfeitos o score exato decide
    (o empate vai para a submissão mais antiga), e o custo de errar com 1,0 em vez de 0,999 é ~1e-4 por par;
  - demais → encolhimento para o valor a priori p0 de resolve.CONF: (acertos + 2·p0) / (n + 2), em [0,5; 1].
Regras nunca observadas mantêm p0.

Uso:  python3 scripts/calibrate.py [--sets dev,devV,st1-8,hd11-13] [--sets-v st1-8,hd11-13,adv21-24]
                                   [--s1 models/s1_ft] [--s2 GGUF --s2-somente-cache] [--out …/conf_calibrada.py]
      Nos conjuntos da convenção V (devV e --sets-v, com gold_V.csv) só contam as regras de frase vaga (`vaga`,
      e `s1_vaga`/`s2_*` quando --s1/--s2 são dados), para não duplicar as demais.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

from _avaliacao import acertou, casar, conjuntos, prever  # noqa: E402
from citeverify.kb import carregar  # noqa: E402
from citeverify.resolve import CONF_PRIORI  # noqa: E402

PISO, MIN_EXATO = 0.5, 50


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="dev,devV,st1-8,hd11-13")
    ap.add_argument("--out", default=str(RAIZ / "src" / "citeverify" / "conf_calibrada.py"))
    ap.add_argument("--db", default=str(RAIZ / "data" / "desafio1_bracis.db"))
    ap.add_argument("--sets-v", default="", help="conjuntos avaliados também contra o gold_V.csv")
    ap.add_argument("--s1", default=None, help="checkpoint do Laya (regra s1_vaga)")
    ap.add_argument("--s2", default=None, help="GGUF do S2 (regras s2_*)")
    ap.add_argument("--s2-somente-cache", action="store_true")
    a = ap.parse_args()
    kb = carregar(a.db, RAIZ / "out" / "kb.pkl")
    s1 = s2 = None
    if a.s1:
        from citeverify.laya_s1 import TriagemLaya
        s1 = TriagemLaya(a.s1)
    if a.s2:
        from citeverify.llm import carregar_sistema2
        s2 = carregar_sistema2(a.s2, n_gpu_layers=-1, cache=str(RAIZ / "out" / "s2_cache.jsonl"),
                               somente_cache=a.s2_somente_cache)
    lista = list(conjuntos(a.sets))
    if a.sets_v:
        lista += [(f"{nome}V", pasta, gold.with_name("gold_V.csv")) for nome, pasta, gold in conjuntos(a.sets_v)]
    n, k, fp = Counter(), Counter(), Counter()
    usados = []
    for nome, pasta, gold in lista:
        if not gold.exists():
            print(f"pulando {nome}: sem gabarito em {gold}")
            continue
        so_vaga = nome.endswith("V")
        preds = prever(pasta, kb, vagas=so_vaga, **({"s1": s1, "s2": s2} if so_vaga else {}))

        def de_vaga(regra: str) -> bool:
            return regra == "vaga" or regra.startswith(("s1_", "s2_"))
        for _, pares, _, espurias in casar(gold, preds):
            for g, p in pares:
                if so_vaga and not de_vaga(p["regra"]):
                    continue
                n[p["regra"]] += 1
                k[p["regra"]] += acertou(g, p)
            for p in espurias:
                if not so_vaga or de_vaga(p["regra"]):
                    fp[p["regra"]] += 1
        usados.append(nome)
    linhas = ['"""Gerado por scripts/calibrate.py — não editar à mão.', "",
              f"Confiança por regra: 1,0 se não errou em >= {MIN_EXATO} pares; senão (acertos + 2·p0) / (n + 2).",
              "Pares casados em:",
              f"{', '.join(usados)}.", '"""', "CONF_CALIBRADA = {"]
    for regra in sorted(n):
        if k[regra] == n[regra] >= MIN_EXATO:
            c = 1.0
        else:
            c = max(PISO, (k[regra] + 2 * CONF_PRIORI.get(regra, 0.9)) / (n[regra] + 2))
        linhas.append(f"    {regra!r}: {c:.4f},  # {k[regra]}/{n[regra]} acertos, {fp[regra]} espúrias")
        print(f"{regra:24s} {k[regra]:6d}/{n[regra]:<6d} → {c:.4f}   espúrias: {fp[regra]}")
    linhas.append("}")
    Path(a.out).write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(f"→ {a.out}")


if __name__ == "__main__":
    main()
