"""Documento .txt → dict no contrato de saída (schema 1.2)."""
from pathlib import Path

from .extract import extrair
from .kb import KB
from .resolve import decidir


def ler_texto(caminho: str | Path) -> str:
    # newline="" preserva \r\n: offsets em codepoints sobre o texto exatamente como distribuído
    with open(caminho, encoding="utf-8", newline="") as f:
        return f.read()


def processar(documento_id: str, texto: str, kb: KB, debug: bool = False) -> dict:
    citacoes = []
    for c in extrair(texto):
        d = decidir(c, kb)
        if d is None:
            continue
        item = {
            "inicio": c.inicio,
            "fim": c.fim,
            "trecho": texto[c.inicio:c.fim],
            "tipo": d.tipo,
            "classificacao": d.classe,
            "resolucao": {"id_canonico": str(d.id_canonico)} if d.classe == "real" else None,
            "confianca": round(d.confianca, 4),
        }
        if debug:
            item["_regra"] = d.regra
            item["_kind"] = c.kind
        citacoes.append(item)
    return {"documento_id": documento_id, "citacoes": citacoes}
