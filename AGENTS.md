# AGENTS.md — Contexto Operativo y Arquitectura para Agentes

Este documento contiene el contexto de arquitectura, entorno de ejecución y puntos de extensión en el codebase necesarios para operar sobre el proyecto **RBlockSim Reproducibility**.

> [!TIP]
> Para consultar el catálogo técnico de mejoras propuestas (con hipótesis, diffs de código y scripts de benchmarking), revisar directamente **[PROPUESTAS.md](file:///home/josealva/Projects/parale/RBlockSim_Reproducibility/PROPUESTAS.md)**.

---

## 1. Qué es este proyecto

**RBlockSim** es un simulador de redes blockchain que usa _Parallel Discrete Event Simulation_ (PDES) especulativa con Time Warp sobre el runtime **ROOT-Sim**. El paper fue presentado en ACM SIGSIM PADS 2025.

Este repositorio contiene el **artefacto de reproducibilidad** del paper:
scripts para compilar el simulador, correr los experimentos y generar las figuras.

### Capacidades del simulador

- Simula redes Bitcoin-like con Proof of Work (PoW) y propagación gossip.
- Soporta ataques adversariales: **51%** y **selfish mining**.
- Simulación paralela: múltiples worker threads procesan eventos concurrentemente con soporte de rollback ante violaciones de causalidad.
- Generación de estadísticas por nodo y gráficos comparativos frente a CBlockSim (baseline secuencial).

---

## 2. Estructura de archivos clave

```
RBlockSim_Reproducibility/
├── paper.pdf                        # Paper original (usar pdftotext para consultar)
├── README.md                        # Instrucciones oficiales de reproducción
├── AGENTS.md                        # ⭐ Este documento (contexto y arquitectura)
├── PROPUESTAS.md                    # ⭐ Catálogo detallado de propuestas de mejora
├── reproducibility_config.json      # Configuración de runs de reproducción
├── entrypoint.py                    # Orquestador principal (builds + runs + plots)
├── reproduce.sh                     # Wrapper Docker oficial
│
├── RBlockSim/                       # Simulador principal
│   ├── src/
│   │   ├── RBlockSim.c              # ⭐ ProcessEvent(): despachador de eventos principales
│   │   ├── Block.c                  # ⭐ Lógica de bloques, resolución de forks y cálculo de score
│   │   ├── Block.h                  # ⭐ Structs: Block, ChainNode, Blockchain, MiningState
│   │   ├── Config.h                 # ⭐ Parámetros globales: BLOCK_INTERVAL, DEPTH_TO_KEEP, etc.
│   │   ├── Config.c                 # ⭐ Latencias interregionales, anchos de banda, seeds
│   │   ├── Network.c                # ⭐ getTransmissionDelay() — cálculo de retraso
│   │   ├── Network.h
│   │   ├── Attacks.c                # Asignación de nodos atacantes (is_attacker)
│   │   ├── Attacks.h                # Struct attack_config y definiciones de ataque
│   │   ├── Statistics.c             # Volcado de métricas a JSON
│   │   ├── Statistics.h             # Structs de métricas por tipo de simulación
│   │   ├── Transaction.c/h          # Pool estático de transacciones (basado en bitmap)
│   │   ├── Topology.c/h             # Generado automáticamente por generate_topology.py
│   │   ├── generate_topology.py     # ⭐ Generador de topologías (aleatoria y small-world)
│   │   └── util.c/h
│   ├── scripts/
│   │   ├── repro_runner.py          # ⭐ Lanza ejecutable y monitorea RAM
│   │   └── repro_plotter.py         # ⭐ Procesa JSONs y genera figuras (.eps)
│   └── Makefile
│
├── reproduced/                      # Datos ya reproducidos (utilizables directamente)
│   ├── results_attacks_0/           # Resultados de ataques (100, 1k, 10k nodos)
│   ├── results_performance_0/       # Tiempos de pared y RAM
│   └── plots/plots_1/
│       └── jsons/                   # ⭐ JSONs procesados listos para análisis
│           ├── 100_51_c1.json
│           ├── 100_selfish_c1_d2.json
│           └── ... (1000 y 10000 nodos)
│
└── ROOT-Sim_core/                   # Runtime PDES Time Warp (no requiere modificación)
```

---

## 3. Guía de Ejecución y Compilación Rápida

Aunque el flujo oficial usa Docker (`reproduce.sh`), para pruebas de desarrollo e implementación es preferible compilar y ejecutar directamente:

```bash
# 1. Generar la topología de red para N nodos (escribe Topology.c y Topology.h en src/)
cd RBlockSim/src/
python3 generate_topology.py --n_nodes 1000 --min_peers 2 --max_peers 6

# 2. Compilar el simulador
cd ../
make rblocksim

# 3. Parámetros de ejecución CLI:
./rblocksim -w 8 -i 600                                                    # Benchmark general
./rblocksim -w 8 -i 600 -a 51 -h 0.3 -c 1 -o out -r 1234                   # Ataque 51% (30% hash)
./rblocksim -w 8 -i 600 -a selfish -h 0.3 -c 1 -d 2 -s 0 -o out -r 1234    # Selfish mining (depth=2)
```

**Banderas principales:**
- `-w N`: Número de worker threads (usar $\le 16$ para redes menores a 1,000 nodos para evitar thrashing).
- `-i F`: Block interval simulado en segundos (comúnmente 600 s o 13 s).
- `-a [51|selfish]`: Tipo de ataque.
- `-h F`: Fracción de hash power del atacante ($0.0 - 1.0$).
- `-c N`: Tolerancia de catchup ($1$ o $2$).
- `-d N`: Profundidad de bloques ocultos antes del release en selfish mining ($1, 2, 3$).
- `-r N`: Semilla del generador pseudoaleatorio.
- `-o prefix`: Prefijo de salida para archivos de métricas.

---

## 4. Estructura de los Datos Reproducidos

Los JSONs procesados en `reproduced/plots/plots_1/jsons/` tienen el siguiente formato:

```json
[
  {
    "stats": {
      "header": [
        "attackerBlocksInMainChain",
        "totalBlocksInMainChain",
        "totalBlocksMined",
        "ownBlocksInMainChain",
        "switchesToSelfishChain"
      ],
      "data": [
        [0, 146, 1, 1, 0],
        [0, 146, 3, 3, 0]
      ]
    },
    "attack_info": {
      "attack_type": "selfish",
      "attacker_id": 36,
      "attacker_hashpower": 0.01,
      "depth": 2,
      "catchup_tolerance": 1,
      "failed_attacks": 2,
      "successful_conceals": 0
    },
    "simulation_info": {
      "network_size": "100",
      "wts": "8",
      "block_interval": "600.000000"
    }
  }
]
```

**Índices en `data[node_id]`:**
- `0`: `attackerBlocksInMainChain` — Bloques del atacante en la cadena principal según la vista de este nodo.
- `1`: `totalBlocksInMainChain` — Altura total de la cadena principal.
- `2`: `totalBlocksMined` — Bloques totales minados por este nodo.
- `3`: `ownBlocksInMainChain` — Bloques minados por este nodo que quedaron en su cadena principal.
- `4`: `switchesToSelfishChain` — Veces que el nodo reorganizó su cadena hacia la bifurcación del atacante.

---

## 5. Ubicaciones Clave en el Código Fuente

### A. Fork Resolution y Scoring (`Block.c`)
- **Inicialización del nodo:** En `populateChainNode()` (~L190), el campo `score` se inicializa en `0` y `ancestorsMined` en `0`.
- **Desempate y selección:** `chainNodeMaxHonest()` (~L235) compara primero `score`, luego `ancestorsMined`, luego timestamp y finalmente miner ID.
- **Asignación del score:** En `addBlock()` (~L440), se conecta el bloque a su padre y se le asigna `score = parent->score + 1` (regla longest-chain). Este es el punto de inserción para reglas alternativas como GHOST.

### B. Cálculo de Retardo de Red (`Network.c`)
- En `getTransmissionDelay()` (~L43), el argumento `data_size` llega pero se ignora intencionalmente, aplicando únicamente la latencia base interregional mediante distribución exponencial.

### C. Constantes y Anchos de Banda (`Config.c` y `Config.h`)
- `Config.c` define `DOWNLOAD_BANDWIDTHS` y `UPLOAD_BANDWIDTHS` por región, pero no son leídos en `Network.c`.
- Constantes críticas: `BLOCK_INTERVAL` (13 o 600 s), `DEPTH_TO_KEEP` (200 niveles en buffer circular), `TERMINATION_TIME` (86400 s de tiempo virtual).

### D. Generador de Topología (`generate_topology.py`)
- Posee implementadas `generate_symmetric_topology()` (usada) y `generate_small_world_topology()` (lista para exponerse en CLI).

---

## 6. Catálogo de Propuestas de Mejora

Para ver la especificación completa, hipótesis, diffs de código y planes de verificación, consultar **[PROPUESTAS.md](file:///home/josealva/Projects/parale/RBlockSim_Reproducibility/PROPUESTAS.md)**.

| ID | Propuesta | Componente | Descripción Resumida |
|---|---|---|---|
| **A1** | Intervalos de Confianza (95%) | `repro_plotter.py` | Añade bandas de error semitransparentes en Figuras 4 y 5. |
| **A2** | Métrica de Orphan Rate | Python (script nuevo) | Compara tasa de huérfanos con el 0.41% empírico de Bitcoin (Gervais 2016). |
| **B1** | Topología Small-World | `generate_topology.py` | Activa el generador small-world y mide impacto en propagación y ataques. |
| **B2** | Regla de Consenso GHOST | `Block.c`, `Makefile` | Implementa score por peso de subárbol con flag `-DUSE_GHOST` para mitigar selfish mining. |
| **B3** | Umbral Teórico de Eyal & Sirer + $\gamma$ | Python + `Block.c` | Evalúa punto de cruce en $\alpha = (1-\gamma)/(3-2\gamma)$ y parametrización de desempate. |

---

## 7. Referencia de Figuras del Paper Original

- **Figura 3:** Tasa de minado empírica vs. hash rate teórico (validación estadística básica).
- **Figura 4a–c:** Ataque 51% (% bloques del atacante en main chain vs hash rate) para 100, 1k y 10k nodos.
- **Figura 4d–f:** Selfish mining (% bloques del atacante en main chain vs hash rate) para 100, 1k y 10k nodos.
- **Figura 5:** Tasa de éxito del ataque selfish mining (probabilidad de forzar reorganización) vs hash rate.
- **Figura 6:** Tiempo de ejecución (*Wall Clock Time*) vs cantidad de worker threads (1 a 88 hilos).
- **Figura 7:** Pico de consumo de memoria RAM vs worker threads.
- **Figura 8:** Evolución del consumo de RAM a lo largo del progreso de la simulación.
