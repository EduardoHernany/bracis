"""Gerado por scripts/calibrate.py — não editar à mão.

Confiança por regra: 1,0 se não errou em >= 100 pares; senão (acertos + 2·p0) / (n + 2).
Pares casados em:
dev, devV, st1, st2, st3, st4, st5, st6, st7, st8, hd11, hd12, hd13, adv21, adv22, adv23, adv24.
"""
CONF_CALIBRADA = {
    'incompleta': 1.0000,  # 2096/2096 acertos, 0 espúrias
    'inventada_ausente': 1.0000,  # 2479/2479 acertos, 0 espúrias
    'lei_inventada': 1.0000,  # 811/811 acertos, 0 espúrias
    'lei_real': 1.0000,  # 1005/1005 acertos, 0 espúrias
    'real_desempate': 0.9948,  # 56/56 acertos, 0 espúrias
    'real_unico': 1.0000,  # 4905/4905 acertos, 0 espúrias
    'sumula_inventada': 1.0000,  # 468/468 acertos, 0 espúrias
    'sumula_outro_tribunal': 1.0000,  # 119/119 acertos, 0 espúrias
    'sumula_real': 1.0000,  # 305/305 acertos, 0 espúrias
    'tema': 1.0000,  # 159/159 acertos, 0 espúrias
    'vaga': 0.9983,  # 33/33 acertos, 0 espúrias
}
