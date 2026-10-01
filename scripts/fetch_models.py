"""Baixa os pesos das camadas opcionais (S1 Laya, S2 Qwen) na revisão fixada em models.lock.json.

Uso:  python scripts/fetch_models.py [s1|s1_ft|s2|all] [--dir models]

Cada arquivo com hash no lock é conferido por sha256; divergência aborta.
Exige `huggingface_hub` (requirements-ml.txt). O pipeline padrão não usa nada disto.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def baixar(nome: str, spec: dict, destino: Path) -> Path:
    from huggingface_hub import hf_hub_download
    pasta = destino / nome
    for arquivo, esperado in spec["files"].items():
        alvo = pasta / arquivo
        if not (alvo.exists() and (esperado is None or sha256(alvo) == esperado)):
            hf_hub_download(spec["repo"], arquivo, revision=spec["revision"], local_dir=pasta)
        if esperado is not None and sha256(alvo) != esperado:
            sys.exit(f"sha256 divergente em {alvo}")
        print(f"ok {nome}: {arquivo}")
    return pasta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("quais", nargs="?", default="all", choices=["s1", "s1_ft", "s2", "s2_14b", "all"])
    ap.add_argument("--dir", default=str(RAIZ / "models"))
    a = ap.parse_args()
    lock = json.loads((RAIZ / "models.lock.json").read_text())
    for nome in ([k for k in ("s1", "s1_ft", "s2") if k in lock] if a.quais == "all" else [a.quais]):
        baixar(nome, lock[nome], Path(a.dir))


if __name__ == "__main__":
    main()
