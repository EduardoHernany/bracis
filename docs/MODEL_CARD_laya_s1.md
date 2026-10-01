---
license: apache-2.0
language:
- pt
base_model: convaiinnovations/laya-multilingual
tags:
- laya
- system-one
- legal
- citation-verification
- brazilian-portuguese
pipeline_tag: text-classification
---

# citeverify-laya-s1 — triagem "System One" de citações jurídicas (pt-BR)

Ajuste fino de [`convaiinnovations/laya-multilingual`](https://huggingface.co/convaiinnovations/laya-multilingual)
(revisão `e4e9ddf21a7b1903b7acffd8814ad4307bf63a67`, mmBERT-base, ~322M parâmetros, Apache-2.0) para uma única
pergunta por frase de peça processual brasileira:

> A frase invoca alguma fonte do direito como fundamento?
> **A** — sim, identificada (processo com número, súmula, tema, artigo de lei, julgado com tribunal/ano/relator);
> **B** — sim, mas vaga ("a jurisprudência pacífica desta Corte", "o dispositivo legal de regência");
> **C** — não invoca nenhuma fonte.

É a camada neural opcional ("Sistema 1") do [citeverify](https://github.com/EduardoHernany/bracis), solução do
desafio Jusbrasil × BRACIS 2026. O modelo **não** decide se uma citação é real ou inventada — isso é consulta
exata a uma base congelada. Ele só aponta frases com referência vaga; o span é delimitado por uma regra
determinística.

## Uso

```python
import laya  # laya==0.3.22, torch 2.14 (CPU), transformers 5.17
agent = laya.load("EduardoHYM/citeverify-laya-s1", revision="<commit>", device="cpu")
questao = {"cita": {"type": "choice",
    "instructions": "A frase, de uma peça processual brasileira, invoca alguma fonte do direito como fundamento?",
    "criteria": {
        "A": "sim, identificada: processo ou recurso com número, súmula, tema, artigo de lei, "
             "ou julgado identificado por tribunal, ano ou relator",
        "B": "sim, mas vaga: invoca jurisprudência, precedentes, súmula ou lei sem identificá-los",
        "C": "não invoca nenhuma fonte do direito"}}}
r = agent.predict_batch(["Ampara a pretensão a jurisprudência pacífica desta Corte."], questao, batch_size=16)
print(r[0]["answers"]["cita"]["probabilities"])
```

A pergunta precisa ser exatamente essa (instrução e critérios), pois foi a usada no treino.

## Treino

- Script oficial do Laya: `research/scripts/finetune_single_device.py` (RLCD), commit `6d942c9` de
  `NandhaKishorM/laya`; 2 épocas, seed 0, CPU, ~1 h. Temperatura ajustada numa fatia separada (choice = 1,0).
- Dados (v2): 3.600 frases — 2.400 (840 A, 600 B, 960 C) de documentos sintéticos de estresse derivados da
  amostra de desenvolvimento da competição, com rótulos dos gabaritos, mais 1.200 de um banco escrito à mão
  (`scripts/laya_extra.py`: moldes e frases vagas disjuntos dos do conjunto adversarial de avaliação, e negativos
  difíceis). Os dados derivados da competição **não** são publicados.

## Avaliação (amostra estratificada de 2.099 frases; P(cita) = P(A) + P(B), limiar 0,5)

| | zero-shot (base) | ajustado: dev* | ajustado: ruído pesado* | ajustado: adversarial (inédito) |
|---|---|---|---|---|
| acurácia 3 classes | 0,25 | 1,000 | 1,000 | 0,979 (v1: 0,915) |
| precisão / recall de "cita" | 0,47 / 0,94 | 1,000 / 1,000 | 1,000 / 1,000 | 0,997 / 0,972 (v1: 0,989 / 0,904) |
| ECE (15 faixas) | 0,26 | 0,000 | 0,001 | 0,021 (v1: 0,072) |

\* corpos de frase vistos no treino (otimista); o conjunto adversarial tem moldes e frases vagas inéditos.
Latência: ~110–180 ms por frase em CPU (fp32). Determinismo: probabilidades idênticas em duas passadas.

No pipeline (convenção em que frases vagas contam como `incompleta`), a v2 recuperou 77–113 frases vagas
inéditas por conjunto adversarial de 104 documentos (v1: 53–68), sem nenhum falso positivo, e não mudou nada nos
conjuntos com os moldes de desenvolvimento.

## Limitações

Treinado só com o estilo do gerador da competição (pareceres, memoriais, contrarrazões sintéticos); não foi
avaliado em peças reais. Não usar para decidir a existência de uma citação.
