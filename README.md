# citeverify — Verificação de citações jurídicas (Jusbrasil × BRACIS 2026)

Sistema que lê uma peça jurídica (`.txt`), encontra as citações de jurisprudência e lei
e classifica cada uma como **real** (com o `id_canonico` do registro na base congelada),
**inventada** ou **incompleta**.

**Totalmente determinístico, sem modelo de linguagem, sem GPU e sem rede.** Usa só a
biblioteca padrão do Python e roda os 26 documentos em cerca de 5 s numa CPU. Não há pesos
nem sementes: a mesma entrada gera sempre a mesma saída, byte a byte.

## Reprodução (comando exato)

```bash
# dados da competição em data/: data/txt/*.txt e data/desafio1_bracis.db
make reproduce TXT=data/txt OUT=out/final      # → out/final/json/*.json e out/final/submission.csv (+ sha256)

# ou, em container:
docker build -t citeverify .
docker run --rm -v "$PWD/data:/app/data:ro" -v "$PWD/out:/app/out" citeverify
```

Para o conjunto de avaliação final, aponte `TXT` para a pasta dos `.txt` publicados.

## Como funciona

```
txt ─► extract ─► normalize ─► resolve (KB offline) ─► decide ─► confiança ─► JSON ─► submission.csv
```

1. **KB offline** (`src/citeverify/kb.py`): para cada acórdão, extrai o número que o
   *identifica*, e não os que ele apenas cita:
   - nos tribunais em geral, os números do cabeçalho até "RELATOR";
   - no TST, cujo cabeçalho não tem número, a frase "autos de <Classe> nº TST-…".

   Súmulas e dispositivos de lei viram índices próprios, por (tribunal, número, vinculante)
   e por (lei canônica, artigo).
2. **Extração** (`extract.py`): regex tolerantes aplicadas ao texto original, com offsets
   em codepoints nativos.
   - **Tipos de citação:** citações numeradas (cadeias de classe como "EDcl nos EDcl no AgInt no AREsp",
     CNJ, UF em `/PR`, `- PR` ou `(PR)`), súmulas, temas, artigos de lei e incompletas
     (tribunal, ano e relator sem número).
   - **Distratores:** o número dos autos no cabeçalho, protocolo, OAB, `fls.` e `R$`
     não casam com nenhum padrão.
3. **Normalização** (`textnorm.py`, `aliases.py`):
   - o vocabulário de classes vem dos cabeçalhos dos 998 acórdãos da base;
   - palavras por extenso são tolerantes a acento e OCR (`m↔rn`, `e↔c`, `i↔l`);
   - siglas são tolerantes a OCR (`S↔5`, `l↔1`, `O↔0`);
   - números passam por correção **só de letra para dígito** (`O→0`, `l→1`, `S→5`, `g→9`, `G→6`, `B→8`),
     são reagrupados e depois casados **exatamente**.
4. **Decisão** (`resolve.py`):
   - número próprio de exatamente um registro de tribunal compatível → `real`;
   - número inexistente, ou que só aparece como citado → `inventada`;
   - sem número (tribunal, ano e relator) → `incompleta`.

   **Nunca há fuzzy em dígitos.** A organização garante que um dígito nunca vira outro,
   então essa política zera a penalidade τ (inventada predita como real).
5. **Confiança** por regra (tabela `CONF` em `resolve.py`), para o bônus de Brier.

## Resultados locais (métrica oficial, `vendor/kaggle_metric.py`)

| Conjunto | Score | macro-F1 N1 / N2 | τ |
|---|---|---|---|
| Amostra de dev (26 docs, 192 citações) | 1.09994 | 1.000 / 1.000 | 0 |
| Estresse, 8 seeds (832 docs, ~6.100 citações) | 1.09994–1.09995 | 1.000 / 1.000 | 0 |
| Estresse com ruído pesado, 3 seeds (`--hard 3`) | 1.09994–1.09995 | 1.000 / 1.000 | 0 |

O **conjunto de estresse** (`scripts/stress_gen.py`) troca cada citação do dev por outra
sorteada da **base inteira**. Cada troca é renderizada com um vocabulário escrito de forma
independente do extrator, mais ruído de OCR, quebras de linha e variantes de UF e marcador.
Serve para medir a generalização para documentos nunca vistos.

```bash
make test      # testes unitários
make dev       # score na amostra de dev, com relatório de erros
make stress    # score nos conjuntos de estresse
```

## Estrutura

```
src/citeverify/  textnorm.py aliases.py kb.py extract.py resolve.py pipeline.py
scripts/         run.py evaluate.py stress_gen.py kaggle.py
vendor/          kaggle_metric.py json_to_submission.py (cópias oficiais, sem edição)
tests/           test_citeverify.py
```

## Ambiente

- Python ≥ 3.11. O pipeline usa só a biblioteca padrão.
- `requirements.txt` fixa `numpy`, `pandas` e `pytest`, usados apenas na avaliação e nos testes.
- `Dockerfile`: `python:3.13.1-slim`, `PYTHONHASHSEED=0`.
- Nenhum modelo, chave de API ou serviço externo.
