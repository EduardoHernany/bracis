"""Roda o pipeline completo: pasta de .txt → um JSON por documento + submission.csv.

Uso:  python scripts/run.py <pasta_txt> <pasta_saida> [--db data/desafio1_bracis.db] [--vagas] [--debug]
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
    ap.add_argument("--vagas", action="store_true",
                    help="emite também as frases vagas como incompleta (convenção da página de Dados)")
    ap.add_argument("--s2", default=None, help="GGUF do Sistema 2 (LLM); exige llama-cpp-python")
    ap.add_argument("--s2-gpu-layers", type=int, default=0, help="camadas na GPU (-1 = todas; 0 = só CPU)")
    ap.add_argument("--s2-threads", type=int, default=6)
    ap.add_argument("--s2-cache", default=str(RAIZ / "out" / "s2_cache.jsonl"), help="'none' desliga o cache")
    ap.add_argument("--s1", default=None, help="pasta do checkpoint Laya da triagem neural (Sistema 1)")
    a = ap.parse_args()

    kb = carregar(a.db, a.cache)
    s2 = s1 = None
    if a.s2:
        from citeverify.llm import carregar_sistema2
        s2 = carregar_sistema2(a.s2, n_gpu_layers=a.s2_gpu_layers, n_threads=a.s2_threads,
                               cache=None if a.s2_cache == "none" else a.s2_cache)
    if a.s1:
        from citeverify.laya_s1 import TriagemLaya
        s1 = TriagemLaya(a.s1)
    saida = Path(a.saida)
    (saida / "json").mkdir(parents=True, exist_ok=True)
    for txt in sorted(Path(a.txt).glob("*.txt")):
        doc = processar(txt.stem, ler_texto(txt), kb, debug=a.debug, vagas=a.vagas, s2=s2, s1=s1)
        (saida / "json" / f"{txt.stem}.json").write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(RAIZ / "vendor" / "json_to_submission.py"),
                    str(saida / "json"), str(saida / "submission.csv")], check=True)


if __name__ == "__main__":
    main()
