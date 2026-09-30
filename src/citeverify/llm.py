"""LLM do Sistema 2: Qwen3-4B-Instruct-2507 (Apache-2.0), GGUF Q4_K_M na revisão fixada em models.lock.json.

Só é carregado com --s2 (exige llama-cpp-python, ver requirements-ml.txt); o pipeline padrão não o importa.

Determinismo: decodificação gulosa (temperature=0, top_k=1, seed=0), threads e lotes fixos, e o estado do prefixo
(instrução + exemplos) avaliado uma vez e restaurado antes de cada frase — a saída de uma frase não depende da
ordem em que as frases são processadas. A saída é restrita por gramática a {"citacoes": [str, …]}.
Cache em JSONL, chaveado por hash(versão do prompt | sha256 do GGUF | backend | frase).
"""
import hashlib
import json
from pathlib import Path

PROMPT_VERSAO = "s2-v1"

SISTEMA = (
    "Você recebe UMA frase de uma peça processual brasileira, que pode ter ruído de OCR (letras trocadas, "
    "quebras de linha, espaços). Liste as citações de fontes do direito que a frase INVOCA, copiando cada trecho "
    "EXATAMENTE como aparece na frase, sem corrigir nada.\n"
    "É citação: (1) processo ou recurso com número (ex.: 'AgRg no REsp 1.234.567/SP', 'RR-1000-10.2019.5.02.0001'); "
    "(2) súmula, enunciado ou tema com número; (3) artigo de lei ou da Constituição (ex.: 'art. 5º, LV, da CF'); "
    "(4) julgado identificado por tribunal, ano ou relator, mesmo sem número "
    "(ex.: 'precedente do STJ de 2020, da relatoria de Nancy Andrighi'); "
    "(5) referência vaga a jurisprudência ou lei que a frase usa como fundamento "
    "(ex.: 'jurisprudência pacífica desta Corte', 'dispositivo legal de regência').\n"
    "NÃO é citação: número dos autos do próprio processo, OAB, protocolo, folhas (fls.), datas, valores, "
    "e frases que só comentam o tema sem invocar uma fonte (ex.: 'a orientação dos tribunais superiores é firme "
    "no ponto').\n"
    "Não inclua o artigo inicial (o, a, os, as) nem a pontuação final. Responda só com o JSON pedido; "
    "lista vazia se a frase não invocar nenhuma fonte."
)

# exemplos tirados dos documentos de desenvolvimento (formato e ruído do gerador)
EXEMPLOS = [
    ("Reforça o argumento o AgRg no Rec. Esp. n. 1.522.200 (SC), de resto amplamente conhecido no foro.",
     ["AgRg no Rec. Esp. n. 1.522.200 (SC)"]),
    ("Ampara a pretensão a jurisprudência pacífica desta Corte, à qual se remete desde logo.",
     ["jurisprudência pacífica desta Corte"]),
    ("Os documentos de fls. 495/928 foram juntados pelo advogado (OAB/MG 241945) em 3 de abril de 2019, "
     "no valor de R$ 168.772,18.", []),
    ("A tese encontra respaldo no precedente do STM de 2023, da relatoria de Marco Antonio, precedente que "
     "dirimiu controvérsia idêntica.", ["precedente do STM de 2023, da relatoria de Marco Antonio"]),
    ("Cumpre observar que a orientação dos tribunais superiores é firme no ponto.", []),
    ("Impõe-se a obscrvância do art 189 da Lei nº 9.504/1997 e da Súm. 166 do TSE, sob pena de nulidade.",
     ["art 189 da Lei nº 9.504/1997", "Súm. 166 do TSE"]),
    ("Como se depreendc do REspe. n° 0600216-46.2020- .6.14.0022, a matéria já foi exaustivamente examinada.",
     ["REspe. n° 0600216-46.2020- .6.14.0022"]),
    ("A leitura conjunta dos dispositivos invocados conduz à mesma conclusão.", []),
]

SCHEMA = {"type": "object",
          "properties": {"citacoes": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": 5}},
          "required": ["citacoes"], "additionalProperties": False}


def _chatml(msgs: list[tuple[str, str]]) -> str:
    return "".join(f"<|im_start|>{papel}\n{conteudo}<|im_end|>\n" for papel, conteudo in msgs)


class Sistema2:
    def __init__(self, model_path: str | Path, n_gpu_layers: int = 0, n_threads: int = 6,
                 cache: str | Path | None = None, gguf_sha: str | None = None):
        from llama_cpp import Llama, LlamaGrammar
        self.llm = Llama(model_path=str(model_path), n_ctx=4096, n_batch=512, n_ubatch=512, n_threads=n_threads,
                         n_threads_batch=n_threads, n_gpu_layers=n_gpu_layers, seed=0, verbose=False)
        self.gramatica = LlamaGrammar.from_json_schema(json.dumps(SCHEMA), verbose=False)
        msgs = [("system", SISTEMA)]
        for f, trechos in EXEMPLOS:
            msgs += [("user", f), ("assistant", json.dumps({"citacoes": trechos}, ensure_ascii=False))]
        self.prefixo = _chatml(msgs)
        self.llm.reset()
        self.llm.eval(self.llm.tokenize(self.prefixo.encode("utf-8"), add_bos=False, special=True))
        self.estado = self.llm.save_state()
        self.id_modelo = f"{gguf_sha or Path(model_path).name}|{'gpu' if n_gpu_layers else 'cpu'}|{n_threads}"
        self.cache_path = Path(cache) if cache else None
        self.cache: dict[str, list[str]] = {}
        self.chamadas = 0
        if self.cache_path and self.cache_path.exists():
            for linha in self.cache_path.read_text(encoding="utf-8").splitlines():
                item = json.loads(linha)
                self.cache[item["k"]] = item["v"]

    def _chave(self, frase: str) -> str:
        return hashlib.sha256(f"{PROMPT_VERSAO}|{self.id_modelo}|{frase}".encode("utf-8")).hexdigest()

    def extrair(self, frase: str) -> list[str]:
        k = self._chave(frase)
        if k in self.cache:
            return self.cache[k]
        self.llm.load_state(self.estado)
        prompt = self.prefixo + f"<|im_start|>user\n{frase}<|im_end|>\n<|im_start|>assistant\n"
        r = self.llm.create_completion(prompt, max_tokens=256, temperature=0.0, top_k=1, top_p=1.0, min_p=0.0,
                                       repeat_penalty=1.0, seed=0, grammar=self.gramatica, stop=["<|im_end|>"])
        self.chamadas += 1
        try:
            itens = [s for s in json.loads(r["choices"][0]["text"])["citacoes"] if isinstance(s, str)]
        except (json.JSONDecodeError, KeyError, TypeError):
            itens = []
        self.cache[k] = itens
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "a", encoding="utf-8") as f:
                f.write(json.dumps({"k": k, "v": itens}, ensure_ascii=False) + "\n")
        return itens


def carregar_sistema2(model_path: str | Path, n_gpu_layers: int = 0, n_threads: int = 6,
                      cache: str | Path | None = None) -> Sistema2:
    """Confere o GGUF pelo tamanho contra models.lock.json (o sha256 é conferido por scripts/fetch_models.py)."""
    raiz = Path(__file__).resolve().parents[2]
    sha = None
    lock = raiz / "models.lock.json"
    if lock.exists():
        spec = json.loads(lock.read_text())["s2"]
        sha = spec["files"].get(Path(model_path).name)
    return Sistema2(model_path, n_gpu_layers=n_gpu_layers, n_threads=n_threads, cache=cache, gguf_sha=sha)
