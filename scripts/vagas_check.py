"""Confere o módulo de frases vagas contra o gabarito do dev e gera o gabarito na convenção V.

O gabarito distribuído tem 192 citações; a página de Dados fala em 225, com incompleta 32 (N1) e 33 (N2).
As 33 que faltam (17 no N1, 16 no N2) são as frases vagas, e deixaram buracos na numeração `citacao_id`.
Este script exige que cada frase vaga achada caia num desses buracos e que os totais batam.

Uso:  python3 scripts/vagas_check.py [--out out/vagas]
"""
import argparse
import collections
import csv
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from citeverify.extract import extrair  # noqa: E402
from citeverify.vagas import extrair_vagas  # noqa: E402

ESPERADO = {1: 17, 2: 16}


def janelas(cits: list[dict], tamanho: int) -> list[tuple[int, int, int]]:
    """(início, fim, nº de ids faltantes) entre citações consecutivas; a janela final tem contagem -1 (desconhecida)."""
    cits = sorted(cits, key=lambda r: int(re.sub(r"\D", "", r["citacao_id"])))
    ids = [int(re.sub(r"\D", "", r["citacao_id"])) for r in cits]
    out, ant_fim, ant_id = [], 0, min(ids[0], 1) - 1 if ids else 0
    for r, i in zip(cits, ids):
        if i - ant_id > 1:
            out.append((ant_fim, int(r["inicio"]), i - ant_id - 1))
        ant_fim, ant_id = int(r["fim"]), i
    out.append((ant_fim, tamanho, -1))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(RAIZ / "out" / "vagas"))
    a = ap.parse_args()
    gold = list(csv.DictReader(open(RAIZ / "data" / "goldenset_offsets.csv", encoding="utf-8-sig")))
    por = collections.defaultdict(list)
    for r in gold:
        por[r["documento_id"]].append(r)
    total, fora, divergentes, novas = collections.Counter(), [], [], []
    for txt in sorted((RAIZ / "data" / "txt").glob("*.txt")):
        doc = txt.stem
        texto = open(txt, encoding="utf-8", newline="").read()
        nivel = 2 if "_n2_" in doc else 1
        vagas = extrair_vagas(texto, [(c.inicio, c.fim) for c in extrair(texto)])
        total[nivel] += len(vagas)
        for ini, fim, n in janelas(por[doc], len(texto)):
            dentro = [v for v in vagas if ini <= v.inicio and v.fim <= fim]
            if n >= 0 and len(dentro) != n:
                divergentes.append(f"{doc} [{ini},{fim}) esperava {n}, achou {len(dentro)}")
        todas = janelas(por[doc], len(texto))
        for v in vagas:
            if not any(ini <= v.inicio and v.fim <= fim for ini, fim, _ in todas):
                fora.append(f"{doc} {texto[v.inicio:v.fim]!r}")
        for i, v in enumerate(vagas):
            novas.append({"nivel": nivel, "documento_id": doc, "citacao_id": f"v{i}", "inicio": v.inicio,
                          "fim": v.fim, "trecho": texto[v.inicio:v.fim], "tipo": v.grupos["tipo"],
                          "classificacao": "incompleta", "id_canonico": ""})
    for n in (1, 2):
        print(f"N{n}: {total[n]}/{ESPERADO[n]}")
    print(f"fora das lacunas: {len(fora)}")
    for x in fora + divergentes:
        print("  ", x)
    saida = Path(a.out)
    saida.mkdir(parents=True, exist_ok=True)
    with open(saida / "vagas_dev.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(novas[0]))
        w.writeheader()
        w.writerows(novas)
    with open(saida / "gold_dev_V.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(gold[0]))
        w.writeheader()
        w.writerows(gold + novas)
    ok = total[1] == ESPERADO[1] and total[2] == ESPERADO[2] and not fora and not divergentes
    print("OK" if ok else "DIVERGÊNCIA")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
