# citeverify — Verificação de citações jurídicas (Jusbrasil × BRACIS 2026)

Sistema que lê uma peça jurídica (`.txt`), encontra as citações de jurisprudência e lei e classifica cada uma
como **real** (com o `id_canonico` do registro na base congelada), **inventada** ou **incompleta**.

O núcleo (**Sistema 1**) é **determinístico, sem modelo de linguagem, sem GPU e sem rede**: só a biblioteca
padrão do Python, ~3 s para os 26 documentos numa CPU, mesma entrada → mesma saída, byte a byte. Duas camadas
neurais **opcionais**, de pesos abertos, foram construídas e avaliadas por A/B (seção [Camadas neurais](#camadas-neurais-opcionais)):
um LLM (**Sistema 2**, Qwen3-4B) e uma triagem "System One" (**Laya**). Elas ficam desligadas por padrão.

## Reprodução (comando exato)

```bash
# dados da competição em data/: data/txt/*.txt e data/desafio1_bracis.db
make reproduce TXT=data/txt OUT=out/final          # variante R → out/final/submission.csv (+ sha256)
make reproduce-vagas TXT=data/txt OUT=out/final    # variante V (com frases vagas) → out/final-vagas/submission.csv

# em container (imagem só com a stdlib, ~390 MB; reproduz o hash da execução local):
docker build -t citeverify .
mkdir -p out && docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/data:/app/data:ro" -v "$PWD/out:/app/out" citeverify
```

Para o conjunto de avaliação final, aponte `TXT` para a pasta dos `.txt` publicados. As variantes R e V
diferem só nas frases vagas (ver [Frases vagas](#frases-vagas-e-o-hedge-rv)).

## Arquitetura: Sistema 1 / Sistema 2

```
txt ─► S1 regras: extract (+ distratores, zona de cabeçalho) ─► resolve (KB offline, match exato) ─► decide ─┐
  │         └─► [--vagas] vagas.py: slot do gerador + inventário → incompleta                              │
  └─► [--s2] gatilhos determinísticos (slot sem citação, pista não coberta) ∪ [--s1] triagem Laya ──┐       ├─► sem sobreposição ─► confiança calibrada ─► JSON ─► CSV
            └─► S2: LLM (temp 0) devolve trechos literais ─► re-ancoragem ─► mesmas regras + KB ───┘
```

1. **KB offline** (`kb.py`): para cada acórdão, os números que o *identificam* (cabeçalho até "RELATOR";
   no TST, "autos de <Classe> nº TST-…"). Súmulas e dispositivos viram índices próprios.
2. **Extração** (`extract.py`): regex tolerantes aplicadas ao texto original (offsets em codepoints):
   citações numeradas (cadeias como "EDcl nos EDcl no AgInt no AREsp", CNJ, UF em `/PR`, `- PR`, `(PR)`),
   súmulas, temas, artigos de lei e incompletas (tribunal, ano e relator sem número).
3. **Normalização** (`textnorm.py`, `aliases.py`): vocabulário de classes dos 998 cabeçalhos da base; palavras
   tolerantes a acento e OCR; números com correção **só de letra para dígito** (`O→0`, `l→1`, `S→5`…), depois
   match **exato**.
4. **Decisão** (`resolve.py`): número próprio de um único registro compatível → `real`; número inexistente
   → `inventada`; sem número → `incompleta`. **Nunca há fuzzy em dígitos** — a organização garante que um
   dígito não vira outro, e essa política zera a penalidade τ (inventada predita como real).
5. **Confiança** por regra, calibrada nos pares casados (ver [Calibração](#confiança-calibrada)).

**Contrato das camadas neurais:** o LLM só *propõe* trechos literais; cada trecho é re-ancorado no texto e
decidido pelas mesmas regras e pelo mesmo KB. `real` continua exigindo chave exata; nenhuma camada neural
decide classe nem sobrescreve o Sistema 1.

## O que mudou na v2 (robustez para o conjunto cego)

Uma auditoria do código contra variações plausíveis do gerador achou lacunas que o dev não mostrava:

| Lacuna | Exemplo | Efeito antes | Correção |
|---|---|---|---|
| `\n` antes do separador, NBSP, hífen U+2011 dentro do número | `0600216-46.2020\n.6.14.0022`, `1 307 026` | real → inventada | `textnorm._SEP` |
| Letras-OCR na borda ou em sequência | `l.741.784`, `70007BO--27…`, `Súmula B3` | FN | `_CH` com sequências curtas |
| OAB/cidade/endereço com UF = sigla de classe | `OAB/MS 12.345`, `Campo Grande/MS, 12 de…`, `Ap. 302` | FP inventada | `extract._eh_distrator` |
| Número do próprio processo em cabeçalho novo | `AUTOS DO PROCESSO Nº …`, `Classe: … nº …` | FP (até `real`) | `zona_cabecalho` + chaves próprias |
| OCR no início da palavra | `5TF`, `lsabel Gallotti`, `2O19` | FN incompleta | tribunal, nome e ano tolerantes |
| Chaves espúrias no KB | `(2016⁄0199049-5)` virava as chaves `2016` e `1990495` | **risco τ** | barra de fração, R$, OAB, lixo de OCR |
| Súmula de tribunal fora da base | `Súmula 83 do TJSP` | **τ** (real) | `sumula_outro_tribunal` → inventada |
| Outra versão do código / artigo com sufixo | `art. 373 do CPC/73`, `art. 896-A da CLT` | real indevido | inventada |
| Prefixo do TST fora do span | `processo nº TST-Ag-EDCiv-AIRR-…` | IoU < 0,5 | span inclui o prefixo, como no gabarito |

Variantes novas aceitas: sufixo `-AgR-segundo` do STF, `Súmula 331, IV, do TST`, `do c. STJ`, `SV 10`,
`Enunciado 83 da Súmula do STJ`, `Súmula do STJ nº 83`, `Tema Repetitivo`, `art. 93, IX, CF/88`, `Lei Maior`,
`novo CPC`. Três registros com cabeçalho corrompido pelo OCR têm a chave corrigida à mão (`kb.CHAVES_MANUAIS`,
conferidas com `scripts/kb_audit.py`: o número aparece dezenas de vezes no próprio texto e em nenhum outro registro).

## Frases vagas e o hedge R/V

A página de Dados do Kaggle chama referências como "jurisprudência pacífica desta Corte" de `incompleta` e conta
**225** citações no dev (incompleta 32 no N1 e 33 no N2). O gabarito distribuído — e o scorer do dev — tem
**192** (incompleta 15 e 17): faltam exatamente as 33 frases vagas. `vagas.py` as encontra pelo inventário e
pelos "slots" do gerador ("Reforça o argumento o {CIT}…"), e `scripts/vagas_check.py` confere que as 33 achadas
caem **exatamente** nas lacunas da numeração `citacao_id` do gabarito (17 no N1, 16 no N2).

Como não se sabe se o gabarito cego as inclui, o pipeline gera as duas variantes:

| | gabarito sem vagas (R) | gabarito com vagas (V) |
|---|---|---|
| predição R (`make reproduce`) | **1.10000** | 0.97757 |
| predição V (`make reproduce-vagas`) | 0.97757 | **1.10000** |

Errar a convenção custa ~0,12. Quando o conjunto cego sair, submete-se R e V; o LB público (40% do cego) mostra
qual convenção vale (diferença > 0,02) e essa é a selecionada para o privado.

## Confiança calibrada

`scripts/calibrate.py` mede a taxa de acerto de cada regra **nos pares casados** (a única coisa que entra no
Brier) sobre dev, estresse e adversarial: regra sem nenhum erro em ≥ 100 pares vai a 1,0; as demais encolhem
para o valor a priori, `(acertos + 2·p0)/(n + 2)`. Entre times perfeitos o score exato decide, e o custo de
errar com 1,0 em vez de 0,999 é ~1e-4 por par. Resultado (`src/citeverify/conf_calibrada.py`):
11 regras, todas com 100% de acerto (ex.: `real_unico` 4905/4905, `inventada_ausente` 2479/2479,
`real_desempate` 56/56 → 0,9948). Dev: **1.10000**.

## Avaliação (métrica oficial, `vendor/kaggle_metric.py`)

| Conjunto | Docs | R (gabarito R) | V (gabarito V) | τ |
|---|---|---|---|---|
| Dev (26 docs, 192 citações; 225 na convenção V) | 26 | **1.10000** | **1.10000** | 0 |
| Estresse, 8 seeds (`make stress`) | 8 × 104 | 1.10000 em todas | 1.10000 em todas | 0 |
| Estresse com ruído pesado, 3 seeds (`--hard 3`) | 3 × 104 | 1.10000 em todas | 1.10000 em todas | 0 |
| **Adversarial**, 4 seeds (`make adv`) | 4 × 104 | 1.10000 em todas | 1.032–1.054 | 0 |

- **Estresse** (`scripts/stress_gen.py`): troca cada citação do dev por outra sorteada da base inteira, renderizada
  com um vocabulário escrito de forma independente do extrator, com ruído de OCR, quebras e variantes de UF.
- **Adversarial** (`--adv`, `scripts/stress_adv.py`): além disso, cabeçalhos e fechos novos com distratores (número
  próprio — às vezes uma chave real —, OAB/MS, cidade/UF, endereço), NBSP, `\n` antes do separador, U+2011,
  OCR nas bordas e no início da palavra, variantes de súmula/tema/lei, súmula de TJ, acórdãos com chave
  compartilhada e um subconjunto com **slots e frases vagas inéditos**. É só nesse subconjunto (frases vagas
  nunca vistas, relevantes apenas na convenção V) que as regras perdem pontos.

```bash
make test        # 75 testes (regras, distratores, vagas, S2 com dublê do LLM)
make dev         # dev, com relatório de erros
make stress adv  # estresse e adversarial
make vagas-check # confere as 33 frases vagas contra as lacunas de citacao_id
make calib       # recalibra a confiança por regra
```

## Camadas neurais (opcionais)

Regras da competição: só modelos de **pesos abertos** em repositório público (link + revisão fixa), executáveis
offline pela organização, dentro de 1 GPU de 24 GB / ~8 vCPU / 32 GB, com decodificação determinística; licenças
OSI com uso comercial. As duas camadas abaixo cumprem isso e ficam **desligadas por padrão**: só entram na
submissão se o A/B em dados não vistos mostrar ganho sem falso positivo novo e com τ = 0.

### Sistema 2: LLM (Qwen3-4B-Instruct-2507)

- **Modelo**: `unsloth/Qwen3-4B-Instruct-2507-GGUF`, arquivo Q4_K_M, revisão `a06e946…`, sha256 em
  `models.lock.json` (Apache-2.0). Roda via `llama-cpp-python` 0.3.35 em CPU ou GPU (~3 GB de VRAM).
- **Gatilhos** (`sistema2.escalar`, determinísticos): frase fora do cabeçalho/fecho com pista forte não coberta
  pelo S1 (súmula/tema/artigo com número, relator, sigla de tribunal, número longo que não seja fls./R$/OAB),
  ou slot do gerador sem citação; na convenção V, também núcleo jurídico ("a jurisprudência…").
- **Prompt** em português com 8 exemplos do dev; saída restrita por gramática a `{"citacoes": [...]}`.
- **Determinismo**: decodificação gulosa (`temperature=0`, `top_k=1`, `seed=0`), threads/lotes fixos e o
  estado do prefixo (instrução + exemplos) restaurado antes de cada frase — a resposta de uma frase não depende
  da ordem; duas execuções dão o mesmo `submission.csv`.

<!-- A/B do S2: preenchido com out/ab/report.md -->

### Sistema 1 neural: análise do Laya (`convaiinnovations/laya`)

**O que é.** O Laya é um modelo "System One" no sentido de Kahneman — rápido, intuitivo —, de código e pesos
Apache-2.0: um **classificador encoder não generativo** que recebe um estado (texto) e perguntas tipadas
(`choice`, `score`, `noul`) e devolve probabilidades por opção. Checkpoints: inglês (ModernBERT-large, 421M) e
`laya-multilingual` (mmBERT-base, ~322M, com português), usado aqui na revisão `e4e9ddf…` (`models.lock.json`).
Os próprios autores o descrevem como "uma base rápida para especializar, não um motor de decisão zero-shot".

**Regras da competição.** Cumpre todas: pesos abertos no HF com revisão fixa, licença Apache-2.0 (uso
comercial), roda offline em CPU (fp32) ou GPU, cabe folgado no envelope de 24 GB. O fine-tune é permitido desde
que os pesos resultantes sejam publicados (seria `EduardoHYM/citeverify-laya-s1`). Riscos: o pacote `laya` teve
30 versões em 11 dias — só é reprodutível com `laya==0.3.22`, torch 2.14/transformers 5.17, revisão, fp32,
threads e lote fixos.

**Em qual camada ele cabe.** Não serve para decidir `real`/`inventada` (isso é consulta ao KB, e o Laya não
conhece a base), nem para delimitar spans (não tem saída por token), nem para calibrar (a calibração por regra
já é exata e determinística). O único papel coerente é o que o nome sugere: **triagem Sistema 1 por frase** —
"esta frase invoca uma fonte do direito que o S1 não achou?" — decidindo quais frases vão ao LLM (Sistema 2).
Foi avaliado exatamente nesse papel (`scripts/laya_data.py`, `scripts/laya_eval.py`): pergunta `choice`
com A (citação identificada), B (referência vaga) e C (nenhuma), por frase.

<!-- métricas do Laya: preenchidas com out/laya/metricas_*.json -->

## Conjunto cego: vigia e runbook

`scripts/blind.py watch` consulta a árvore de dados do Kaggle a cada 2 min. Quando o conjunto cego aparece,
baixa para `data/blind/<ts>/`, roda as variantes R e V a partir de uma cópia congelada do código (`release/`,
um git worktree na última tag validada), valida os CSVs com o parser oficial (inclusive o erro de sobreposição) e
escreve `out/blind/<ts>/STATUS.md` com os sha256 e os comandos de submissão. **Não submete sozinho.**

```bash
KAGGLE_TOKEN=... make blind-watch                                   # vigia (prepara e avisa)
KAGGLE_TOKEN=... python3 scripts/kaggle.py submit out/blind/<ts>/R/submission.csv "citeverify v2 R"
KAGGLE_TOKEN=... python3 scripts/kaggle.py submit out/blind/<ts>/V/submission.csv "citeverify v2 V"
```

Ordem: R primeiro (empate favorece a submissão mais antiga), depois V; o LB público decide qual selecionar.

## Estrutura

```
src/citeverify/  textnorm.py aliases.py kb.py extract.py resolve.py pipeline.py conf_calibrada.py
                 vagas.py (frases vagas) · frases.py sistema2.py llm.py (S2) · laya_s1.py (triagem Laya)
scripts/         run.py evaluate.py stress_gen.py stress_adv.py calibrate.py vagas_check.py kb_audit.py
                 blind.py kaggle.py ab.py laya_data.py laya_eval.py fetch_models.py _avaliacao.py
vendor/          kaggle_metric.py json_to_submission.py (cópias oficiais, sem edição)
tests/           test_citeverify.py test_sistema2.py
```

## Ambiente

- Python ≥ 3.11; o pipeline padrão usa só a biblioteca padrão. `requirements.txt` fixa `numpy`, `pandas` e
  `pytest` (avaliação e testes). `Dockerfile`: `python:3.13.1-slim`, `PYTHONHASHSEED=0`.
- Camadas opcionais: `requirements-ml.txt` (llama-cpp-python compilado com instruções portáveis — a roda pronta
  exige AVX-512 —, torch CPU, transformers, laya), `Dockerfile.llm`, pesos por `scripts/fetch_models.py` na
  revisão de `models.lock.json`. Nenhuma chave de API ou serviço externo em tempo de inferência.
