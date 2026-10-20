# Barrido de esfuerzo `retardo_v13a` (fase M2)

Ajuste fino de `rl_v1.1` con el castigo `esfuerzo_motor`. Bateria completa (44 corridas). Filtro duro: caida, salida o una articulacion con par RMS > 80 % del par continuo = falta; desde la fase M3, ademas, desvio maximo medio de las salidas normales <= 10 cm y, en la bateria del benchmark (sin perturbaciones), cada corrida con meta, <= 80 % y desvio <= 10 cm. Puntaje = tiempo medio + 1 sigma.

**Base `continua`:** faltas 0/44 (con el filtro del 80 %), esfuerzo maximo 77 % (LKneePitch), tiempo medio 12.44 s.

| # | Agente | Peso (modo) | Checkpoint | Pasa | Faltas | Sobre 80 % | Puntaje [s] | t medio [s] | Peor esfuerzo |
|---|---|---|---|---|---|---|---|---|---|
| 1 | agente_000 | -0.5 (instante) | 1M | no | 34 | 34 | — | 15.82 | 143 % (RKneePitch) |

Checkpoints de cada agente (faltas, corridas sobre 80 %, peor esfuerzo, desvio medio de las salidas normales, tiempo medio; y si se corrio, la bateria del benchmark):

- `agente_000` (esfuerzo -0.5, centrado -5.0): 1M: 34 faltas, 34 sobre 80 %, 143 %, desvio 16.9 cm, 15.82 s; 2M: 39 faltas, 34 sobre 80 %, 112 %, desvio 15.6 cm, 21.69 s; 3M: 36 faltas, 36 sobre 80 %, 106 %, desvio 15.4 cm, 17.32 s; 4M: 40 faltas, 35 sobre 80 %, 110 %, desvio 22.1 cm, 16.70 s; 5M: 41 faltas, 38 sobre 80 %, 116 %, desvio 17.3 cm, 14.34 s
