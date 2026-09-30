PY ?= python3
TXT ?= data/txt
OUT ?= out/final

.PHONY: data reproduce reproduce-vagas dev stress test clean vagas-check kb-audit blind-watch fetch-models adv calib reproduce-llm ab

# baixa os dados da competição (exige KAGGLE_TOKEN no ambiente)
data:
	$(PY) scripts/kaggle.py download-all data
	mv -f data/kaggle_metric.py data/json_to_submission.py vendor/ 2>/dev/null || true

# o comando exato que gera as saídas submetidas: $(TXT)/*.txt → $(OUT)/json/*.json + $(OUT)/submission.csv
reproduce:
	$(PY) scripts/run.py $(TXT) $(OUT)
	sha256sum $(OUT)/submission.csv

# variante V: também emite as frases vagas como incompleta (convenção da página de Dados do Kaggle)
reproduce-vagas:
	$(PY) scripts/run.py $(TXT) $(OUT)-vagas --vagas
	sha256sum $(OUT)-vagas/submission.csv

# variante com o Sistema 2 (LLM de pesos abertos; exige requirements-ml.txt e `make fetch-models`)
GGUF ?= models/s2/Qwen3-4B-Instruct-2507-Q4_K_M.gguf
GPU_LAYERS ?= 0
reproduce-llm:
	$(PY) scripts/run.py $(TXT) $(OUT)-llm --s2 $(GGUF) --s2-gpu-layers $(GPU_LAYERS) --s2-cache none
	sha256sum $(OUT)-llm/submission.csv

# A/B das camadas (regras × +S2) nas convenções R e V → out/ab/report.md
ab:
	$(PY) scripts/ab.py --variants rules,vagas,s2,vagas+s2 --sets dev,st1,hd11,adv21-24 --s2 $(GGUF) --s2-gpu-layers $(GPU_LAYERS)

# confere as frases vagas contra as lacunas de citacao_id do gabarito (17 no N1, 16 no N2)
vagas-check:
	$(PY) scripts/vagas_check.py

# audita as chaves do KB (o que identifica cada acórdão)
kb-audit:
	$(PY) scripts/kb_audit.py --curtas

# vigia a publicação do conjunto cego (exige KAGGLE_TOKEN); prepara R e V, não submete
blind-watch:
	$(PY) scripts/blind.py watch --interval 120 --release-dir release

# pesos das camadas opcionais (S1 Laya, S2 Qwen), na revisão de models.lock.json
fetch-models:
	$(PY) scripts/fetch_models.py all

# avaliação na amostra de desenvolvimento (gabarito aberto), com a métrica oficial
dev:
	$(PY) scripts/run.py data/txt out/dev
	$(PY) scripts/evaluate.py out/dev/submission.csv --erros

# conjunto de estresse cego (base inteira, ruído aleatório) — o teste de generalização
stress:
	@for s in 1 2 3 4 5; do \
	  $(PY) scripts/stress_gen.py --n 4 --seed $$s --out out/st$$s > /dev/null && \
	  $(PY) scripts/run.py out/st$$s/txt out/st$$s-pred > /dev/null && \
	  echo "seed $$s" && $(PY) scripts/evaluate.py out/st$$s-pred/submission.csv --gold out/st$$s/gold.csv --erros; \
	done
	@for s in 11 12 13; do \
	  $(PY) scripts/stress_gen.py --n 4 --seed $$s --hard 3 --out out/hd$$s > /dev/null && \
	  $(PY) scripts/run.py out/hd$$s/txt out/hd$$s-pred > /dev/null && \
	  echo "hard seed $$s" && $(PY) scripts/evaluate.py out/hd$$s-pred/submission.csv --gold out/hd$$s/gold.csv --erros; \
	done

# estresse adversarial: moldes, distratores e ruídos que o dev não mostra (+ gabarito V das frases vagas)
adv:
	@test -f out/vagas/vagas_dev.csv || $(PY) scripts/vagas_check.py > /dev/null
	@for s in 21 22 23 24; do \
	  $(PY) scripts/stress_gen.py --n 4 --seed $$s --adv --vagas-gold out/vagas/vagas_dev.csv --out out/adv$$s > /dev/null && \
	  $(PY) scripts/run.py out/adv$$s/txt out/adv$$s-pred > /dev/null && \
	  echo "adv seed $$s" && $(PY) scripts/evaluate.py out/adv$$s-pred/submission.csv --gold out/adv$$s/gold.csv --erros; \
	done

# recalibra a confiança por regra (grava src/citeverify/conf_calibrada.py)
calib:
	$(PY) scripts/calibrate.py --sets dev,devV,st1-8,hd11-13,adv21-24

test:
	$(PY) -m pytest -q tests

clean:
	rm -rf out
