"""Auditoria das chaves do KB: o que identifica cada acórdão.

Uso:
    python3 scripts/kb_audit.py --dump out/kb_keys_v0.json     # salva chaves por registro
    python3 scripts/kb_audit.py --diff out/kb_keys_v0.json     # mostra o que mudou desde o dump
    python3 scripts/kb_audit.py --curtas                       # chaves não-CNJ com até 4 dígitos, com contexto
"""
import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

from citeverify.kb import construir  # noqa: E402


def chaves(kb) -> dict[str, list[str]]:
    return {str(i): sorted(r.chaves) for i, r in sorted(kb.registros.items()) if r.natureza == "acordao"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(RAIZ / "data" / "desafio1_bracis.db"))
    ap.add_argument("--dump")
    ap.add_argument("--diff")
    ap.add_argument("--curtas", action="store_true")
    a = ap.parse_args()
    kb = construir(a.db)
    atual = chaves(kb)
    if a.dump:
        Path(a.dump).parent.mkdir(parents=True, exist_ok=True)
        Path(a.dump).write_text(json.dumps(atual, indent=1), encoding="utf-8")
        print(f"{a.dump}: {len(atual)} acórdãos, {sum(map(len, atual.values()))} chaves")
    if a.diff:
        antes = json.loads(Path(a.diff).read_text(encoding="utf-8"))
        for rid in sorted(set(antes) | set(atual), key=int):
            a_, b_ = set(antes.get(rid, [])), set(atual.get(rid, []))
            if a_ != b_:
                r = kb.registros[int(rid)]
                print(f"{rid} {r.tribunal}: -{sorted(a_ - b_)} +{sorted(b_ - a_)}")
        sem = [rid for rid, ks in atual.items() if not ks]
        print(f"registros sem chave: {sem}")
    if a.curtas:
        for rid, ks in atual.items():
            for k in ks:
                if "." not in k and len(k) <= 4:
                    r = kb.registros[int(rid)]
                    print(f"{rid} {r.tribunal} {k!r} classes={r.classes}")


if __name__ == "__main__":
    main()
