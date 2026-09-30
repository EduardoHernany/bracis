"""Documento .txt → dict no contrato de saída (schema 1.2)."""
from pathlib import Path

from .extract import extrair
from .kb import KB
from .resolve import decidir
from .vagas import extrair_vagas


def ler_texto(caminho: str | Path) -> str:
    # newline="" preserva \r\n: offsets em codepoints sobre o texto exatamente como distribuído
    with open(caminho, encoding="utf-8", newline="") as f:
        return f.read()


def processar(documento_id: str, texto: str, kb: KB, debug: bool = False, vagas: bool = False,
              s2=None, s1=None) -> dict:
    """vagas=True também emite as frases vagas ("jurisprudência pacífica desta Corte") como `incompleta`.
    s2 (Sistema2, opcional): LLM que propõe trechos nas frases que o S1 não resolveu; s1 (TriagemLaya, opcional,
    só com vagas=True): classificador por frase que aponta referências vagas, delimitadas por regra."""
    citacoes = []
    cands = extrair(texto)
    if vagas:
        cands += extrair_vagas(texto, [(c.inicio, c.fim) for c in cands])
    decisoes = [(c, decidir(c, kb)) for c in cands]
    if s2 is not None:
        from .sistema2 import aplicar
        decisoes += aplicar(texto, kb, [c for c, d in decisoes if d is not None], s2, vagas)
    if s1 is not None and vagas:
        from .laya_s1 import vagas_neurais
        decisoes += vagas_neurais(texto, [(c.inicio, c.fim) for c, d in decisoes if d is not None], s1)
    for c, d in decisoes:
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
    return {"documento_id": documento_id, "citacoes": sem_sobreposicao(citacoes)}


def sem_sobreposicao(citacoes: list[dict]) -> list[dict]:
    """Rede de segurança: duas predições sobrepostas (IoU >= 0,5) invalidam a submissão inteira."""
    out: list[dict] = []
    for c in sorted(citacoes, key=lambda c: (c["inicio"], -c["fim"])):
        if out and c["inicio"] < out[-1]["fim"]:
            continue
        out.append(c)
    return out
