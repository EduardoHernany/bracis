"""Calibra a confiança de cada regra a partir dos pares casados com o gabarito.

A métrica só usa a confiança nos pares casados (Brier): uma predição espúria não entra no bônus, só no F1.
Por isso a estimativa é a taxa de acerto *dado que casou*:
  - regra sem nenhum erro em pelo menos MIN_EXATO pares → 1,0. Entre times perfeitos o score exato decide
    (o empate vai para a submissão mais antiga), e o custo de errar com 1,0 em vez de 0,999 é ~1e-4 por par;
  - demais → encolhimento para o valor a priori p0 de resolve.CONF: (acertos + 2·p0) / (n + 2), em [0,5; 1].
Regras nunca observadas mantêm p0.

Uso:  python3 scripts/calibrate.py [--sets dev,devV,st1-8,hd11-13] [--out src/citeverify/conf_calibrada.py]
      (nos conjuntos "V" só a regra `vaga` é contada, para não duplicar as demais)
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

PISO, MIN_EXATO = 0.5, 100


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sets", default="dev,devV,st1-8,hd11-13")
    ap.add_argument("--out", default=str(RAIZ / "src" / "citeverify" / "conf_calibrada.py"))
    ap.add_argument("--db", default=str(RAIZ / "data" / "desafio1_bracis.db"))
    a = ap.parse_args()
    kb = carregar(a.db, RAIZ / "out" / "kb.pkl")
    n, k, fp = Counter(), Counter(), Counter()
    usados = []
    for nome, pasta, gold in conjuntos(a.sets):
        if not gold.exists():
            print(f"pulando {nome}: sem gabarito em {gold}")
            continue
        so_vaga = nome.endswith("V")
        preds = prever(pasta, kb, vagas=so_vaga)
        for _, pares, _, espurias in casar(gold, preds):
            for g, p in pares:
                if so_vaga and p["regra"] != "vaga":
                    continue
                n[p["regra"]] += 1
                k[p["regra"]] += acertou(g, p)
            for p in espurias:
                if not so_vaga or p["regra"] == "vaga":
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
