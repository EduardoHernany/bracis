"""Gerado por scripts/calibrate.py — não editar à mão.

Confiança por regra: 1,0 se não errou em >= 50 pares; senão (acertos + 2·p0) / (n + 2).
Pares casados em:
dev, devV, st1, st2, st3, st4, st5, st6, st7, st8, hd11, hd12, hd13, adv21, adv22, adv23, adv24, st1V, st2V, st3V, st4V, st5V, st6V, st7V, st8V, hd11V, hd12V, hd13V, adv21V, adv22V, adv23V, adv24V.
"""
CONF_CALIBRADA = {
    'incompleta': 1.0000,  # 2096/2096 acertos, 0 espúrias
    'inventada_ausente': 1.0000,  # 2479/2479 acertos, 0 espúrias
    'lei_inventada': 1.0000,  # 811/811 acertos, 0 espúrias
    'lei_real': 1.0000,  # 1005/1005 acertos, 0 espúrias
    'real_desempate': 1.0000,  # 56/56 acertos, 0 espúrias
    'real_unico': 1.0000,  # 4905/4905 acertos, 0 espúrias
    's1_vaga': 1.0000,  # 132/132 acertos, 0 espúrias
    's2_vaga': 1.0000,  # 196/196 acertos, 0 espúrias
    'sumula_inventada': 1.0000,  # 468/468 acertos, 0 espúrias
    'sumula_outro_tribunal': 1.0000,  # 119/119 acertos, 0 espúrias
    'sumula_real': 1.0000,  # 305/305 acertos, 0 espúrias
    'tema': 1.0000,  # 159/159 acertos, 0 espúrias
    'vaga': 1.0000,  # 2013/2013 acertos, 0 espúrias
}
