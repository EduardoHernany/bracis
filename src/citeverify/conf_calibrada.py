"""Gerado por scripts/calibrate.py — não editar à mão.

Confiança por regra: 1,0 se não errou em >= 100 pares; senão (acertos + 2·p0) / (n + 2).
Pares casados em:
dev, devV, st1, st2, st3, st4, st5, st6, st7, st8, hd11, hd12, hd13.
"""
CONF_CALIBRADA = {
    'incompleta': 1.0000,  # 1440/1440 acertos, 0 espúrias
    'inventada_ausente': 1.0000,  # 1832/1832 acertos, 0 espúrias
    'lei_inventada': 1.0000,  # 589/589 acertos, 0 espúrias
    'lei_real': 1.0000,  # 630/630 acertos, 0 espúrias
    'real_desempate': 0.9000,  # 1/1 acertos, 0 espúrias
    'real_unico': 1.0000,  # 3464/3464 acertos, 0 espúrias
    'sumula_inventada': 1.0000,  # 342/342 acertos, 0 espúrias
    'sumula_real': 1.0000,  # 225/225 acertos, 0 espúrias
    'tema': 1.0000,  # 117/117 acertos, 0 espúrias
    'vaga': 0.9983,  # 33/33 acertos, 0 espúrias
}
