"""Helper mínimo para o MCP do Kaggle (HTTP stateless, JSON-RPC).

Uso:
    KAGGLE_TOKEN=... python scripts/kaggle.py files [path]
    KAGGLE_TOKEN=... python scripts/kaggle.py download <arquivo> <destino>
    KAGGLE_TOKEN=... python scripts/kaggle.py download-all <pasta>
    KAGGLE_TOKEN=... python scripts/kaggle.py submit <submission.csv> "<descrição>"
    KAGGLE_TOKEN=... python scripts/kaggle.py submissions
    KAGGLE_TOKEN=... python scripts/kaggle.py call <tool> '<json request>'
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

MCP_URL = "https://www.kaggle.com/mcp"
COMPETICAO = "desafio-jusbrasil-bracis-2026"


def call(tool: str, request: dict) -> dict:
    token = os.environ.get("KAGGLE_TOKEN")
    if not token:
        sys.exit("defina KAGGLE_TOKEN")
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                       "params": {"name": tool, "arguments": {"request": request}}}).encode()
    req = urllib.request.Request(MCP_URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": "2025-06-18",
    })
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read().decode()
    data = next(json.loads(l[6:]) for l in raw.splitlines() if l.startswith("data: "))
    if "error" in data:
        raise RuntimeError(data["error"])
    res = data["result"]
    texto = "".join(c.get("text", "") for c in res.get("content", []))
    if res.get("isError"):
        raise RuntimeError(texto)
    return json.loads(texto) if texto.strip().startswith(("{", "[")) else {"text": texto}


def listar(path: str | None = None) -> dict:
    req = {"competitionName": COMPETICAO, "pageSize": 200, "hasPageSize": True}
    if path:
        req.update(path=path, hasPath=True)
    return call("list_competition_data_tree_files", req)


def baixar(nome: str, destino: Path) -> None:
    url = call("download_competition_data_file",
               {"competitionName": COMPETICAO, "fileName": nome})["url"]
    destino.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, destino)


def baixar_tudo(pasta: Path, path: str | None = None) -> None:
    arvore = listar(path)
    for f in arvore.get("files", []):
        rel = f"{path}/{f['name']}" if path else f["name"]
        print("baixando", rel)
        baixar(rel, pasta / rel)
    for d in arvore.get("directories", []):
        baixar_tudo(pasta, f"{path}/{d['name']}" if path else d["name"])


def submeter(csv_path: Path, descricao: str) -> dict:
    st = csv_path.stat()
    up = call("start_competition_submission_upload", {
        "competitionName": COMPETICAO, "hasCompetitionName": True,
        "contentLength": st.st_size, "lastModifiedEpochSeconds": int(st.st_mtime),
        "fileName": csv_path.name})
    put = urllib.request.Request(up["create_url"], data=csv_path.read_bytes(), method="PUT",
                                 headers={"Content-Type": "application/octet-stream"})
    urllib.request.urlopen(put, timeout=120).read()
    return call("submit_to_competition", {
        "competitionName": COMPETICAO, "blobFileTokens": up["token"],
        "submissionDescription": descricao, "hasSubmissionDescription": True})


def main() -> None:
    cmd, *args = sys.argv[1:] or ["files"]
    if cmd == "files":
        out = listar(args[0] if args else None)
    elif cmd == "download":
        baixar(args[0], Path(args[1]))
        out = {"ok": args[1]}
    elif cmd == "download-all":
        baixar_tudo(Path(args[0]))
        out = {"ok": args[0]}
    elif cmd == "submit":
        out = submeter(Path(args[0]), args[1] if len(args) > 1 else "")
    elif cmd == "submissions":
        out = call("search_competition_submissions", {
            "competitionName": COMPETICAO, "sortBy": "Date", "group": "All"})
    elif cmd == "call":
        out = call(args[0], json.loads(args[1]) if len(args) > 1 else {})
    else:
        sys.exit(__doc__)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
