"""Roda o pipeline completo: pasta de .txt → um JSON por documento + submission.csv.

Uso:  python scripts/run.py <pasta_txt> <pasta_saida> [--db data/desafio1_bracis.db] [--debug]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from citeverify.kb import carregar  # noqa: E402
from citeverify.pipeline import ler_texto, processar  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("txt")
    ap.add_argument("saida")
    ap.add_argument("--db", default=str(RAIZ / "data" / "desafio1_bracis.db"))
    ap.add_argument("--cache", default=str(RAIZ / "out" / "kb.pkl"))
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()

    kb = carregar(a.db, a.cache)
    saida = Path(a.saida)
    (saida / "json").mkdir(parents=True, exist_ok=True)
    for txt in sorted(Path(a.txt).glob("*.txt")):
        doc = processar(txt.stem, ler_texto(txt), kb, debug=a.debug)
        (saida / "json" / f"{txt.stem}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(RAIZ / "vendor" / "json_to_submission.py"),
                    str(saida / "json"), str(saida / "submission.csv")], check=True)


if __name__ == "__main__":
    main()
