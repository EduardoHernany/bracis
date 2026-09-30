"""Vigia do conjunto final cego: detecta a publicação, baixa, roda as variantes e valida.

Nunca submete: deixa os CSVs validados e os comandos em out/blind/<ts>/STATUS.md.

Uso:
    KAGGLE_TOKEN=... python3 scripts/blind.py watch [--interval 120] [--release-dir release]
    KAGGLE_TOKEN=... python3 scripts/blind.py snapshot
    python3 scripts/blind.py simulate [--txt data/txt] [--release-dir release]
    python3 scripts/blind.py validate <submission.csv> [--sample <sample_submission.csv>]

Variantes (rodadas a partir da cópia de release, que é congelada numa tag validada):
    R — só regras, sem frases vagas (convenção do gabarito do dev);
    V — com --vagas (convenção da página de Dados), se a release já tiver a flag.
"""
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "scripts"))

import kaggle  # noqa: E402

# a publicação de dev (15/09): qualquer arquivo fora desta lista, ou com data/tamanho diferente, é novidade
_DATA_DEV = "2026-09-15T12:33:18"
_DEV = {"desafio1_bracis.db", "goldenset_offsets.csv", "json_to_submission.py", "kaggle_metric.py",
        "sample_submission.csv"} | {f"txt/gen_n{n}_{i:03d}.txt" for n in (1, 2) for i in range(1, 14)}


def _log(msg: str) -> None:
    print(f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%SZ}] {msg}", flush=True)


def arvore(path: str | None = None) -> dict[str, tuple[str, str]]:
    """relative_url → (bytes, data de criação), percorrendo diretórios e páginas."""
    out, token = {}, None
    while True:
        req = {"competitionName": kaggle.COMPETICAO, "pageSize": 200, "hasPageSize": True}
        if path:
            req.update(path=path, hasPath=True)
        if token:
            req.update(pageToken=token, hasPageToken=True)
        r = kaggle.call("list_competition_data_tree_files", req)
        for f in r.get("files", []):
            out[f["relative_url"]] = (f.get("total_bytes", ""), f.get("creation_date", ""))
        for d in r.get("directories", []):
            out.update(arvore(d["relative_url"]))
        token = r.get("next_page_token") or r.get("nextPageToken")
        if not token:
            return out


def novidades(snap: dict[str, tuple[str, str]]) -> list[str]:
    return sorted(k for k, (_, data) in snap.items() if k not in _DEV or not data.startswith(_DATA_DEV))


def sha256(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def ids_da_amostra(sample: Path) -> list[str]:
    with open(sample, encoding="utf-8-sig") as f:
        return [r["documento_id"] for r in csv.DictReader(f)]


def validar(csv_path: Path, esperados: list[str] | None) -> tuple[bool, list[str]]:
    """Checa o CSV com o parser oficial (inclui o erro de sobreposição IoU >= 0,5) e sanidade de volume."""
    sys.path.insert(0, str(RAIZ / "vendor"))
    import kaggle_metric
    msgs, ok = [], True
    with open(csv_path, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    ids = [r["documento_id"] for r in linhas]
    if len(ids) != len(set(ids)):
        ok = False
        msgs.append("documento_id duplicado")
    if esperados is not None:
        faltam, sobram = set(esperados) - set(ids), set(ids) - set(esperados)
        if faltam:
            ok = False
            msgs.append(f"faltam {len(faltam)} documentos, ex.: {sorted(faltam)[:3]}")
        if sobram:
            msgs.append(f"aviso: {len(sobram)} documentos fora da amostra, ex.: {sorted(sobram)[:3]}")
    contagens = []
    for r in linhas:
        try:
            contagens.append(len(kaggle_metric._parse_submission_cell(r["citacoes"], r["documento_id"])))
        except kaggle_metric.ParticipantVisibleError as e:
            ok = False
            msgs.append(f"inválido: {e}")
    if contagens:
        media = sum(contagens) / len(contagens)
        msgs.append(f"{len(contagens)} documentos, {sum(contagens)} citações, média {media:.2f}, máx {max(contagens)}")
        if not 3 <= media <= 15 or max(contagens) > 25:
            ok = False
            msgs.append("volume de citações fora do esperado (média 3–15, máx 25)")
    return ok, msgs


def completar(csv_path: Path, esperados: list[str]) -> None:
    """Acrescenta '-' para documentos da amostra sem .txt (a métrica exige uma linha por documento)."""
    with open(csv_path, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    tem = {r["documento_id"] for r in linhas}
    faltam = [d for d in esperados if d not in tem]
    if faltam:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([(d, "-") for d in faltam])


def rodar_variantes(entrada: Path, db: Path, saida: Path, release: Path,
                    esperados: list[str] | None) -> list[dict]:
    run = release / "scripts" / "run.py"
    tem_vagas = "--vagas" in run.read_text(encoding="utf-8")
    # cache do KB amarrado ao conteúdo da base: uma base nova nunca reaproveita o índice velho
    cache = RAIZ / "out" / "blind" / f"kb-{sha256(db)[:12]}.pkl"
    variantes = [("R", [], sys.executable)] + ([("V", ["--vagas"], sys.executable)] if tem_vagas else [])
    # V+S2 (opcional): só se a release tiver o S2 e houver o env ML e o GGUF; roda depois de R e V (é mais lento)
    gguf = RAIZ / "models" / "s2" / "Qwen3-4B-Instruct-2507-Q4_K_M.gguf"
    py_ml = Path(os.environ.get("CITEVERIFY_ML_PY", Path.home() / "miniforge3/envs/citeverify-ml/bin/python"))
    s1_ft = RAIZ / "models" / "s1_ft"
    codigo = run.read_text(encoding="utf-8")
    s2_args = ["--s2", str(gguf), "--s2-gpu-layers", os.environ.get("S2_GPU_LAYERS", "-1"),
               "--s2-cache", str(RAIZ / "out" / "blind" / "s2_cache.jsonl")]
    if tem_vagas and "--s1" in codigo and (s1_ft / "model.safetensors").exists() and py_ml.exists():
        variantes.append(("VS1", ["--vagas", "--s1", str(s1_ft)], str(py_ml)))            # Laya em CPU, rápido
        if "--s2" in codigo and gguf.exists():
            variantes.append(("VS1S2", ["--vagas", "--s1", str(s1_ft), *s2_args], str(py_ml)))  # melhor no A/B
    elif tem_vagas and "--s2" in codigo and gguf.exists() and py_ml.exists():
        variantes.append(("VS2", ["--vagas", *s2_args], str(py_ml)))
    res = []
    for nome, extra, python in variantes:
        destino = saida / nome
        t0 = time.time()
        p = subprocess.run([python, str(run), str(entrada), str(destino), "--db", str(db),
                            "--cache", str(cache), *extra],
                           capture_output=True, text=True)
        item = {"variante": nome, "retorno": p.returncode, "segundos": round(time.time() - t0, 1),
                "csv": destino / "submission.csv", "stderr": p.stderr[-2000:]}
        if p.returncode == 0:
            if esperados:
                completar(item["csv"], esperados)
            item["ok"], item["msgs"] = validar(item["csv"], esperados)
            item["sha256"] = sha256(item["csv"])
        else:
            item["ok"], item["msgs"] = False, ["falhou ao rodar"]
        res.append(item)
    if not tem_vagas:
        res.append({"variante": "V", "ok": False, "msgs": ["a release ainda não tem --vagas; só a R foi gerada"]})
    return res


def escrever_status(saida: Path, cabecalho: list[str], res: list[dict], release: Path) -> Path:
    git = subprocess.run(["git", "-C", str(release), "describe", "--tags", "--always"],
                         capture_output=True, text=True).stdout.strip()
    linhas = ["# Conjunto cego — status", "", *cabecalho, f"- release: `{git}`", ""]
    for r in res:
        linhas.append(f"## Variante {r['variante']} — {'OK' if r.get('ok') else 'ATENÇÃO'}")
        if "csv" in r:
            linhas += [f"- csv: `{r['csv'].relative_to(RAIZ)}`", f"- sha256: `{r.get('sha256', '-')}`",
                       f"- tempo: {r.get('segundos')} s"]
        linhas += [f"- {m}" for m in r["msgs"]]
        if r.get("stderr") and not r.get("ok"):
            linhas += ["```", r["stderr"], "```"]
        linhas.append("")
    prontas = [r for r in res if r.get("ok")]
    if prontas:
        linhas += ["## Submeter (nesta ordem; empate favorece a submissão mais antiga)", "", "```"]
        for r in prontas:
            linhas.append(f"KAGGLE_TOKEN=... python3 scripts/kaggle.py submit {r['csv'].relative_to(RAIZ)} "
                          f"\"citeverify v2 {r['variante']}\"")
        publicado = "s1_ft" in json.loads((RAIZ / "models.lock.json").read_text())
        linhas += ["```", "",
                   "VS1 (V + Laya) e VS1S2 (V + Laya + LLM) só valem se o LB mostrar que a convenção V é a certa.",
                   ("Os pesos do Laya ajustado estão publicados (models.lock.json → s1_ft)." if publicado else
                    "**ATENÇÃO: o Laya ajustado ainda NÃO foi publicado no HF — as regras exigem pesos públicos com "
                    "revisão fixa. Não submeta VS1/VS1S2 antes de rodar `hf auth login` e "
                    "`python scripts/publish_laya.py`.**"),
                   "Depois compare R e V no LB público: V − R > 0,02 → o gabarito inclui as frases vagas;",
                   "R − V > 0,02 → não inclui; diferença menor → selecione as duas."]
    status = saida / "STATUS.md"
    status.write_text("\n".join(linhas) + "\n", encoding="utf-8")
    return status


def preparar_entrada(pasta: Path, novos: list[str]) -> tuple[Path, Path, list[str] | None]:
    """Extrai zips, junta os .txt novos numa pasta plana e decide o .db e os ids esperados."""
    for z in pasta.rglob("*.zip"):
        with zipfile.ZipFile(z) as zf:
            zf.extractall(z.parent / z.stem)
    entrada = pasta / "entrada"
    entrada.mkdir(exist_ok=True)
    for t in sorted(pasta.rglob("*.txt")):
        if entrada not in t.parents:
            shutil.copy2(t, entrada / t.name)
    dbs = sorted(pasta.rglob("*.db"))
    db = dbs[0] if dbs else RAIZ / "data" / "desafio1_bracis.db"
    amostras = sorted(pasta.rglob("sample_submission*.csv"))
    esperados = ids_da_amostra(amostras[0]) if amostras else None
    if esperados:   # a amostra pode listar documentos antigos também
        for d in esperados:
            if not (entrada / f"{d}.txt").exists() and (RAIZ / "data" / "txt" / f"{d}.txt").exists():
                shutil.copy2(RAIZ / "data" / "txt" / f"{d}.txt", entrada / f"{d}.txt")
    return entrada, db, esperados


def tratar_publicacao(snap: dict, novos: list[str], release: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pasta = RAIZ / "data" / "blind" / ts
    for rel in novos:
        _log(f"baixando {rel}")
        kaggle.baixar(rel, pasta / rel)
    entrada, db, esperados = preparar_entrada(pasta, novos)
    n_txt = len(list(entrada.glob("*.txt")))
    saida = RAIZ / "out" / "blind" / ts
    res = rodar_variantes(entrada, db, saida, release, esperados)
    cab = [f"- detectado: {ts} (UTC)", f"- arquivos novos/alterados: {len(novos)} (ex.: {novos[:5]})",
           f"- documentos de entrada: {n_txt} em `{entrada.relative_to(RAIZ)}`",
           f"- base: `{db}`", f"- ids esperados (amostra): {len(esperados) if esperados else 'sem amostra nova'}"]
    return escrever_status(saida, cab, res, release)


def watch(intervalo: int, release: Path) -> int:
    _log(f"vigiando {kaggle.COMPETICAO} a cada {intervalo}s; release em {release}")
    espera, rodadas = intervalo, 0
    while True:
        try:
            snap = arvore()
            espera = intervalo
        except Exception as e:  # rede/MCP instável: tenta de novo com recuo
            _log(f"erro ao listar: {e!r}")
            time.sleep(min(espera, 900))
            espera = min(espera * 2, 900)
            continue
        novos = novidades(snap)
        if novos:
            _log(f"PUBLICAÇÃO DETECTADA: {len(novos)} arquivos novos/alterados")
            status = tratar_publicacao(snap, novos, release)
            _log(f"pronto: {status}")
            subprocess.run(["notify-send", "-u", "critical", "Conjunto cego publicado",
                            f"CSVs prontos em {status.parent}"], check=False)
            return 0
        rodadas += 1
        if rodadas % 15 == 0:
            _log(f"sem novidades ({len(snap)} arquivos)")
        time.sleep(intervalo)


def simulate(txt: Path, release: Path) -> Path:
    saida = RAIZ / "out" / "blind" / "simulacao"
    esperados = ids_da_amostra(RAIZ / "data" / "sample_submission.csv")
    res = rodar_variantes(txt, RAIZ / "data" / "desafio1_bracis.db", saida, release, esperados)
    return escrever_status(saida, [f"- simulação sobre `{txt}` (dev)"], res, release)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch")
    w.add_argument("--interval", type=int, default=120)
    w.add_argument("--release-dir", default=str(RAIZ / "release"))
    sub.add_parser("snapshot")
    s = sub.add_parser("simulate")
    s.add_argument("--txt", default=str(RAIZ / "data" / "txt"))
    s.add_argument("--release-dir", default=str(RAIZ / "release"))
    v = sub.add_parser("validate")
    v.add_argument("csv")
    v.add_argument("--sample", default=None)
    a = ap.parse_args()
    if a.cmd == "watch":
        sys.exit(watch(a.interval, Path(a.release_dir).resolve()))
    if a.cmd == "snapshot":
        snap = arvore()
        print(json.dumps({"arquivos": len(snap), "novidades": novidades(snap)}, ensure_ascii=False, indent=2))
    elif a.cmd == "simulate":
        status = simulate(Path(a.txt), Path(a.release_dir).resolve())
        print(status.read_text(encoding="utf-8"))
    elif a.cmd == "validate":
        ok, msgs = validar(Path(a.csv), ids_da_amostra(Path(a.sample)) if a.sample else None)
        print("\n".join(msgs))
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
