"""Publica o Laya ajustado (models/s1_ft) no Hugging Face e fixa a revisão em models.lock.json.

As regras da competição exigem que pesos ajustados sejam publicados num repositório público, com link e revisão
fixa. Exige um token com permissão de escrita:  hf auth login

Uso:  python scripts/publish_laya.py [--repo EduardoHYM/citeverify-laya-s1] [--dir models/s1_ft]
"""
import argparse
import hashlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="EduardoHYM/citeverify-laya-s1")
    ap.add_argument("--dir", default=str(RAIZ / "models" / "s1_ft"))
    a = ap.parse_args()
    from huggingface_hub import HfApi
    api = HfApi()
    pasta = Path(a.dir)
    api.create_repo(a.repo, repo_type="model", private=False, exist_ok=True)
    commit = api.upload_folder(repo_id=a.repo, folder_path=str(pasta), repo_type="model",
                               commit_message="citeverify-laya-s1: ajuste fino do laya-multilingual (triagem A/B/C)",
                               ignore_patterns=[".cache/*"])
    revisao = commit.oid
    lock_path = RAIZ / "models.lock.json"
    lock = json.loads(lock_path.read_text())
    lock["s1_ft"] = {
        "repo": a.repo,
        "revision": revisao,
        "license": "apache-2.0",
        "base": {"repo": lock["s1"]["repo"], "revision": lock["s1"]["revision"]},
        "files": {
            "model.safetensors": sha256(pasta / "model.safetensors"),
            "tokenizer/tokenizer.json": sha256(pasta / "tokenizer" / "tokenizer.json"),
            "tokenizer/tokenizer_config.json": None,
            "encoder/config.json": None,
            "rl_agent_config.json": None,
        },
    }
    lock_path.write_text(json.dumps(lock, indent=2) + "\n")
    print(f"publicado: https://huggingface.co/{a.repo}/tree/{revisao}")
    print("models.lock.json atualizado; `python scripts/fetch_models.py s1_ft` baixa essa revisão.")


if __name__ == "__main__":
    main()
