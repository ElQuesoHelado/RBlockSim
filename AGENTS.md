# AGENTS.md — Contexto Completo para Agente Implementador

Este documento contiene todo el contexto necesario para que un agente pueda
implementar las mejoras propuestas al proyecto **RBlockSim Reproducibility**
sin necesidad de leer el paper original ni explorar el codebase desde cero.

---

## 1. Qué es este proyecto

**RBlockSim** es un simulador de redes blockchain que usa _Parallel Discrete Event Simulation_ (PDES) especulativa con Time Warp sobre el runtime **ROOT-Sim**. El paper fue presentado en ACM SIGSIM PADS 2025.

Este repositorio contiene el **artefacto de reproducibilidad** del paper:
scripts para compilar el simulador, correr los experimentos y generar las figuras.

### Qué hace el simulador

- Simula redes Bitcoin-like con PoW y gossip propagation
- Soporta ataques: **51%** y **selfish mining**
- La simulación es paralela: múltiples hilos procesan eventos con rollback cuando hay conflictos causales (Time Warp)
- Genera estadísticas por nodo y plots comparativos con CBlockSim (baseline secuencial)

---

## 2. Estructura de archivos clave

```
RBlockSim_Reproducibility/
├── paper.pdf                        # El paper original (usar pdftotext para leer)
├── README.md                        # Instrucciones de reproducción
├── reproducibility_config.json      # Config usada para los runs principales
├── entrypoint.py                    # Orquesta toda la reproducción (builds + runs + plots)
├── reproduce.sh                     # Script shell que lanza Docker con entrypoint.py
│
├── RBlockSim/                       # El simulador principal
│   ├── src/
│   │   ├── RBlockSim.c              # ⭐ Main: ProcessEvent(), maneja todos los eventos
│   │   ├── Block.c                  # ⭐ Blockchain: addBlock, fork resolution, scoring
│   │   ├── Block.h                  # ⭐ Structs: Block, ChainNode, Blockchain, MiningState
│   │   ├── Config.h                 # ⭐ Constantes: BLOCK_INTERVAL, DEPTH_TO_KEEP, etc.
│   │   ├── Config.c                 # ⭐ Valores: latencias, bandwidths (SIN USAR), seed
│   │   ├── Network.c                # ⭐ getTransmissionDelay() — data_size IGNORADO aquí
│   │   ├── Network.h
│   │   ├── Attacks.c                # Inicializa atacantes, is_attacker()
│   │   ├── Attacks.h                # attack_config struct, tipos de ataque
│   │   ├── Statistics.c             # Dump de stats a JSON
│   │   ├── Statistics.h             # Structs de stats por tipo de simulación
│   │   ├── Transaction.c/h          # Gestión de transacciones (bitmap-based)
│   │   ├── Topology.c/h             # Generado automáticamente por generate_topology.py
│   │   ├── generate_topology.py     # ⭐ Genera topología — tiene random Y small-world
│   │   └── util.c/h
│   ├── scripts/
│   │   ├── repro_runner.py          # ⭐ Lanza el ejecutable con distintas configs
│   │   └── repro_plotter.py         # ⭐ Lee JSONs de resultados y genera figuras (.eps)
│   └── Makefile
│
├── reproduced/                      # Datos YA reproducidos (usar estos)
│   ├── results_attacks_0/           # Ataques: 51% y selfish, redes 100/1k/10k nodos
│   ├── results_attacks_1/           # Segunda ejecución de ataques
│   ├── results_performance_0/       # Performance: wall time y RAM
│   └── plots/plots_1/
│       └── jsons/                   # ⭐ JSONs procesados listos para analizar
│           ├── 100_51_c1.json       # 51% attack, 100 nodos, catchup=1
│           ├── 100_selfish_c1_d2.json  # Selfish mining, 100 nodos, catchup=1, depth=2
│           └── ...                  # Mismo para 1000 y 10000 nodos
│
└── ROOT-Sim_core/                   # El runtime de simulación (no modificar)
```

---

## 3. Cómo correr el simulador (fuera del contenedor Docker)

> El flujo normal usa Docker (`reproduce.sh`), pero para experimentos rápidos
> se puede correr directamente si ROOT-Sim está compilado.

```bash
# 1. Generar topología para N nodos (escribe Topology.c y Topology.h en src/)
cd RBlockSim/src/
python3 generate_topology.py --n_nodes 1000 --min_peers 2 --max_peers 6

# 2. Compilar
cd ../
make rblocksim

# 3. Correr (dentro de Docker o con ROOT-Sim instalado)
./rblocksim -w 8 -i 600         # benchmark, 8 hilos, block interval 600s
./rblocksim -w 8 -i 600 -a 51 -h 0.3 -c 1 -o out -r 1234   # ataque 51%
./rblocksim -w 8 -i 600 -a selfish -h 0.3 -c 1 -d 2 -s 0 -o out -r 1234  # selfish
```

**Parámetros del ejecutable:**
- `-w N` → número de worker threads
- `-i F` → block interval en segundos (13 o 600)
- `-a [51|selfish]` → tipo de ataque
- `-h F` → fracción de hash rate del atacante (0.0–1.0)
- `-c N` → catchup tolerance (1 o 2)
- `-d N` → depth para selfish mining (1, 2, o 3)
- `-r N` → semilla RNG
- `-o prefix` → prefijo del archivo de salida

---

## 4. Formato de los datos reproducidos

### JSONs de ataques (en `reproduced/plots/plots_1/jsons/`)

```json
// Ejemplo: 100_selfish_c1_d2.json — lista de runs
[
  {
    "stats": {
      "header": ["attackerBlocksInMainChain","totalBlocksInMainChain",
                 "totalBlocksMined","ownBlocksInMainChain","switchesToSelfishChain"],
      "data": [[0,146,1,1,0], [0,146,1,1,0], ...]   // una entrada por nodo
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
  },
  ...  // más runs con distintos hash rates
]
```

**Campos de stats por nodo** (`data[node_id]`):
- `[0]` = `attackerBlocksInMainChain` — bloques del atacante en la main chain (vista de este nodo)
- `[1]` = `totalBlocksInMainChain` = altura de la main chain
- `[2]` = `totalBlocksMined` = bloques minados por este nodo
- `[3]` = `ownBlocksInMainChain` = bloques de este nodo que están en su main chain
- `[4]` = `switchesToSelfishChain` = veces que este nodo cambió a la cadena del atacante

### Raw results (en `reproduced/results_attacks_0/results_100/`)

```
Results_sz100_w8_bi600.000000_a51_h0.010000_c1_d0_rng3512506141_0/
├── attack_info.json    # metadata del run
└── stats_sz100_...json # stats brutas (misma estructura que arriba)
out_sz100_w8_bi600_a51_h0.01_c1_d0_rng..._it0.txt  # stdout: "Height: 146", "Simulation completed in X.XXX seconds"
```

---

## 5. Funciones clave del codebase (con ubicación exacta)

### `Block.c` — Fork resolution y scoring

```c
// Línea ~195: así se inicializa el score de un bloque nuevo
// AQUÍ está la clave para implementar GHOST
void populateChainNode(const struct Block *block, struct ChainNode *chainNode) {
    chainNode->score = 0;          // ← ACTUALMENTE siempre 0 al crear
    chainNode->ancestorsMined = 0; // ← campo ya existe, se usa para tiebreaking
    // ...
}

// Línea ~236: comparación de scores para selección de fork
static inline struct ChainNode *chainNodeMaxHonest(struct ChainNode *nodeA, struct ChainNode *nodeB) {
    if (nodeA->score > nodeB->score) return nodeA;
    if (nodeA->score < nodeB->score) return nodeB;
    // Si empatan en score, usa ancestorsMined como tiebreaker
    if (nodeA->ancestorsMined > nodeB->ancestorsMined) return nodeA;
    // ...
}
```

¿Dónde se asigna el score definitivo? Buscar `addBlock()` en `Block.c` (~línea 440):

```c
// En addBlock(), después de populateChainNode():
struct ChainNode *parent = /* parent del bloque */;
new_node->score = parent->score + 1;  // ← Longest-chain: score = height
// Para GHOST habría que hacer: new_node->score = subtree_weight
```

### `Network.c` — Latencia ignorando bandwidth

```c
// Línea 43 — data_size llega pero NO se usa:
simtime_t getTransmissionDelay(node_id_t src, node_id_t dst,
                                size_t data_size, struct rng_t *rng) {
    if (!rng) {
        return LATENCIES[getRegion(src)][getRegion(dst)]; // sin bandwidth
    }
    return Expent(rng, LATENCIES[getRegion(src)][getRegion(dst)]); // sin bandwidth
}
```

### `Config.c` — Bandwidths definidos pero sin usar

```c
// Líneas 27-30: existen pero NUNCA se referencian en Network.c
const double DOWNLOAD_BANDWIDTHS[REGIONS_NUM + 1] = { 52, 40, 18, 22.8, 22.8, 29.9, 6 }; // Mbps
const double UPLOAD_BANDWIDTHS[REGIONS_NUM + 1]   = { 19.2, 20.7, 5.8, 15.7, 10.2, 11.3, 6 }; // Mbps
```

### `Config.h` — Constantes importantes

```c
#define BLOCK_SIZE 0.18          // Mb (megabytes) — tamaño fijo de bloque
#define GOSSIP_FANOUT 80         // peers a los que re-enviar un bloque
#define DEPTH_TO_KEEP 200        // profundidad máxima del árbol
#define TERMINATION_TIME (60*60*24)  // 24h de tiempo simulado
```

### `generate_topology.py` — DOS modelos implementados

```python
# Modelo 1 — USADO en reproducción:
generate_symmetric_topology(n_nodes, min_peers, max_peers, seed)

# Modelo 2 — IMPLEMENTADO pero NUNCA LLAMADO:
generate_small_world_topology(n_nodes, dens, prop, max_dis, seed)
# dens: densidad de conexiones locales (0–1)
# prop: proporción de conexiones aleatorias (0–1)
# max_dis: distancia máxima para considerar conexión "local"
```

### `repro_plotter.py` — Funciones de análisis

```python
# Columnas de stats (índices en data[node_id]):
STATS_ATTACKER_BLOCKS_COMMITTED_TO_MC = 0
STATS_MC_HEIGHT = 1
STATS_BLOCKS_MINED_BY_ME = 2
STATS_OWN_BLOCKS_IN_MC = 3
STATS_SWITCHES_TO_SELFISH = 4

# Funciones principales a modificar:
extract_plot_data_for_average_attacker_committed_percentage(runs_data)  # → (x, y) sin IC
extract_plot_data_for_attack_success_rate(runs_data)                    # → (x, y) sin IC
plot_51(size, out_path)         # genera figura 4a-c
plot_selfish(size, out_path)    # genera figura 4d-f
plot_selfish_success_rate(size, out_path)  # genera figura 5
```

---

## 6. Propuestas de mejora — Prioridad y detalle de implementación

Las propuestas están divididas en dos categorías.

### CATEGORÍA A: Completar limitaciones del paper (menor novedad, mayor seguridad)

---

#### Propuesta A1 — Intervalos de Confianza en Figuras de Ataques

**Qué hace:** Añade bandas de confianza (IC 95%) a las Figuras 4 y 5 del paper.

**Por qué:** El paper promedia múltiples iteraciones pero nunca muestra la varianza.
Para un paper de simulación con RNG, la varianza es información esencial.

**Hardware:** < 500 MB RAM. Correr `iterations=5` con redes 100–1,000 nodos: ~10 min.

**Archivos a modificar:**
- `RBlockSim/scripts/repro_plotter.py` — solo Python

**Cambios exactos en `repro_plotter.py`:**

```python
# 1. Importar numpy al inicio (ya importado como np)

# 2. Modificar extract_plot_data_for_average_attacker_committed_percentage:
def extract_plot_data_for_average_attacker_committed_percentage(runs_data):
    hash_to_committed = {}
    for run in runs_data:
        committed_percent = compute_percentage_of_attacker_committed_blocks(run["stats"]["data"])
        hash_power = run["attack_info"]["attacker_hashpower"]
        if hash_power not in hash_to_committed:
            hash_to_committed[hash_power] = []
        hash_to_committed[hash_power].append(committed_percent)

    x, y, y_err = [], [], []
    for h in sorted(hash_to_committed.keys()):
        vals = hash_to_committed[h]
        x.append(h)
        y.append(float(np.mean(vals)))
        ci = float(np.std(vals, ddof=1) / np.sqrt(len(vals)) * 1.96) if len(vals) > 1 else 0.0
        y_err.append(ci)
    return x, y, y_err   # antes retornaba (x, y)

# 3. Modificar plot_51 para usar y_err:
def plot_51(size, out_path=None):
    # ...
    for i, r in enumerate(runs_51):
        x, y, y_err = extract_plot_data_for_average_attacker_committed_percentage(r)
        plt.plot(x, y, label=labels[i])
        plt.fill_between(x, np.array(y)-np.array(y_err),
                            np.array(y)+np.array(y_err), alpha=0.15)
    # ...

# 4. Mismo cambio en plot_selfish y plot_selfish_success_rate
# (extract_plot_data_for_attack_success_rate también necesita el mismo tratamiento)
```

**Config para correr con más iteraciones:**
```json
// reproducibility_config.json — cambiar:
{
  "what_to_reproduce": "attacks",
  "network_sizes_attacks": [100, 1000],
  "worker_threads_attacks": 8,
  "iterations": 5
}
```

---

#### Propuesta A2 — Orphan Rate como Métrica de Validación

**Qué hace:** Calcula el orphan rate por red y lo compara con el valor empírico de Bitcoin.

**Por qué:** El orphan rate es una métrica estándar en literatura blockchain.
Gervais et al. 2016 (referencia [11] del paper) reporta ~0.41% para Bitcoin con BI=600s.
El simulador tiene todos los datos para calcular esto sin modificar C.

**Fórmula directa:**
```
orphan_rate = (total_mined - mc_height) / total_mined
```
Donde:
- `total_mined = sum(data[node][STATS_BLOCKS_MINED_BY_ME] for all nodes)`
- `mc_height = data[0][STATS_MC_HEIGHT]`  (es igual para todos los nodos)

**Hardware:** < 500 MB. Trabaja sobre datos ya en `/reproduced/`.

**Implementación (nuevo script `scripts/analyze_orphan_rate.py`):**

```python
import json, os, glob
import numpy as np
import matplotlib.pyplot as plt

STATS_MC_HEIGHT = 1
STATS_BLOCKS_MINED_BY_ME = 2

def compute_orphan_rate(stats_data):
    """Calcula orphan rate desde stats de un run."""
    total_mined = sum(node[STATS_BLOCKS_MINED_BY_ME] for node in stats_data)
    mc_height = stats_data[0][STATS_MC_HEIGHT]
    if total_mined == 0:
        return None
    orphans = total_mined - mc_height
    return orphans / total_mined

def analyze_orphan_rates(json_folder, network_sizes):
    """Lee los JSONs procesados y calcula orphan rate por tamaño de red."""
    results = {}  # {network_size: [orphan_rate, ...]}

    for size in network_sizes:
        results[size] = []
        # Usar todos los archivos de ese tamaño (selfish y 51%)
        pattern = os.path.join(json_folder, f"{size}_*.json")
        for fpath in glob.glob(pattern):
            with open(fpath) as f:
                runs = json.load(f)
            for run in runs:
                rate = compute_orphan_rate(run["stats"]["data"])
                if rate is not None:
                    results[size].append(rate)

    return results

def plot_orphan_rate(results, out_path):
    sizes = sorted(results.keys())
    means = [np.mean(results[s]) * 100 for s in sizes]
    errs  = [np.std(results[s], ddof=1) / np.sqrt(len(results[s])) * 1.96 * 100
             for s in sizes]

    plt.figure()
    plt.errorbar(sizes, means, yerr=errs, marker='o', capsize=5, label='RBlockSim (BI=600s)')
    # Referencia empírica de Bitcoin (Gervais et al. 2016)
    plt.axhline(y=0.41, color='r', linestyle='--', label='Bitcoin real ~0.41% (Gervais 2016)')
    plt.xscale('log')
    plt.xlabel('Network size (nodes)')
    plt.ylabel('Orphan rate (%)')
    plt.legend()
    plt.savefig(out_path, bbox_inches='tight')
    plt.clf()

if __name__ == "__main__":
    json_folder = "reproduced/plots/plots_1/jsons"
    out_path = "reproduced/plots/plots_1/orphan_rate.eps"
    results = analyze_orphan_rates(json_folder, [100, 1000, 10000])
    plot_orphan_rate(results, out_path)
    for size, rates in results.items():
        print(f"Network {size}: mean orphan rate = {np.mean(rates)*100:.3f}% ± {np.std(rates)*100:.3f}%")
```

**Validación esperada:** Para BI=600s con 1,000 nodos: orphan rate ~0.3–0.5%.

---

### CATEGORÍA B: Contribuciones nuevas más allá del paper

---

#### Propuesta B1 — Topología Small-World vs. Aleatoria

**Por qué es nueva:** El paper **solo usa topología aleatoria**. La topología small-world
ya está implementada en `generate_topology.py` pero **nunca se activa**.
En la red Bitcoin real, la topología tiene propiedades small-world.

**Hipótesis a verificar:** Con topología small-world, la propagación de bloques
es más rápida (menor diámetro efectivo), lo que reduce el orphan rate y
dificulta el selfish mining.

**Hardware:** < 2 GB RAM. Compilar + correr redes 100–1k nodos: ~15 min total.

**Archivos a modificar:**
1. `RBlockSim/src/generate_topology.py` — añadir argumento CLI
2. Script de orquestación nuevo para correr ambas topologías y comparar

**Cambio en `generate_topology.py`:**

```python
# En main(), añadir argumentos:
parser.add_argument("--topology", choices=["random", "small_world"],
                    default="random",
                    help="Topology model to use")
parser.add_argument("--sw_density", type=float, default=0.1,
                    help="[small_world] Local connection density (0–1)")
parser.add_argument("--sw_propagation", type=float, default=0.5,
                    help="[small_world] Long-range connection probability (0–1)")
parser.add_argument("--sw_max_dis", type=int, default=None,
                    help="[small_world] Max local distance (default: n_nodes//4)")

# Cambiar la generación:
if args.topology == "small_world":
    max_dis = args.sw_max_dis if args.sw_max_dis else args.n_nodes // 4
    topology = generate_small_world_topology(
        args.n_nodes, args.sw_density, args.sw_propagation, max_dis, args.seed
    )
    # Ajustar MAX_PEERS para small_world (puede ser mayor que en random)
    max_peers_for_header = max(len(peers) for peers in topology)
    # Crear args_for_header con el max real
    class SmArgs:
        n_nodes = args.n_nodes
        min_peers = 1
        max_peers = max_peers_for_header
    topology_to_c(SmArgs(), topology)
else:
    topology = generate_symmetric_topology(
        args.n_nodes, args.min_peers, args.max_peers, args.seed
    )
    topology_to_c(args, topology)
```

**Script de comparación (`scripts/compare_topologies.py`):**

```python
"""
Compara métricas de ataque (orphan rate, selfish mining success)
bajo topología aleatoria vs. small-world.
Genera 2 compilaciones del simulador y corre los mismos experimentos en ambas.
"""
import subprocess, os, json, shutil

NETWORK_SIZES = [100, 1000]
RNG_SEEDS = [42, 123, 999, 7777, 12345]  # 5 repeticiones
RBLOCKSIM_SRC = "RBlockSim/src"
RBLOCKSIM_BIN = "RBlockSim/rblocksim"

topologies = {
    "random":      ["python3", "generate_topology.py", "--topology", "random",
                    "--min_peers", "2", "--max_peers", "6"],
    "small_world": ["python3", "generate_topology.py", "--topology", "small_world",
                    "--sw_density", "0.1", "--sw_propagation", "0.5"],
}

results = {"random": {}, "small_world": {}}

for size in NETWORK_SIZES:
    for topo_name, topo_cmd in topologies.items():
        # Generar topología
        os.chdir(RBLOCKSIM_SRC)
        subprocess.run(topo_cmd + ["--n_nodes", str(size)])
        os.chdir("../")
        subprocess.run(["make", "rblocksim"])

        orphan_rates = []
        for seed in RNG_SEEDS:
            # Correr ataque selfish con 30% hash rate
            cmd = [RBLOCKSIM_BIN, "-w", "4", "-i", "600",
                   "-a", "selfish", "-h", "0.3", "-c", "1", "-d", "2",
                   "-r", str(seed), "-o", f"out_{topo_name}_{size}"]
            result = subprocess.run(cmd, capture_output=True, text=True)
            # Parsear orphan rate del output
            # (Total mined blocks y Height están en stdout)
            # ...

        results[topo_name][size] = orphan_rates
```

**Resultado esperado:** Nueva figura comparando orphan rate y success rate de selfish mining bajo ambas topologías para 100 y 1,000 nodos.

---

#### Propuesta B2 — GHOST Fork Rule

**Por qué es nueva y por qué es la más interesante:**

El paper dice explícitamente en §4.6:
> *"For other algorithms like GHOST, the amount of work done by the ancestors
> can be considered, taking into account the inclusion of uncle blocks."*

Y en `Block.h` los campos ya existen pero con valores placeholder:
```c
uint32_t score;         // "For longest chain: height. For GHOST: amount of work done."
uint32_t ancestorsMined; // ya se usa como tiebreaker, no como score principal
```

**GHOST** (Greedy Heaviest-Observed SubTree, Sompolinsky & Zohar 2013) selecciona
el fork con mayor "peso" (número total de bloques en el subárbol), no el más largo.
Es el fork rule de Ethereum pre-Merge.

**Hipótesis:** El selfish miner tiene menos ventaja bajo GHOST porque los bloques
ocultos "pierden peso" en la competencia, mientras los bloques honestos acumulan peso.
(Resultado teórico de Sapirshtein et al. 2016, verificable con simulación.)

**Hardware:** < 2 GB RAM. Compilar con y sin flag + redes 100–1k nodos.

**Archivos a modificar:**
- `RBlockSim/src/Block.c` — asignación de score en `addBlock()`
- `RBlockSim/Makefile` — añadir target `rblocksim_ghost`

**Cambio exacto en `Block.c`:**

Primero localizar la función `addBlock()` (~línea 440 en Block.c) y la asignación de score.
La función `populateChainNode` inicializa `score=0`; luego en `addBlock()` se asigna el score
definitivo cuando el nodo queda conectado a su padre.

```c
// En addBlock(), justo después de conectar new_node a su parent:
// ACTUAL (Longest Chain):
new_node->score = new_node->height;  // ← buscar esta línea exacta

// REEMPLAZAR POR (compilar con -DUSE_GHOST para activar GHOST):
#ifdef USE_GHOST
    // GHOST simplificado: score = score del padre + 1
    // La clave es que TODOS los bloques (incluidos orphans/uncle) contribuyen al peso
    // del subárbol cuando se reciben. Esto requiere propagar el peso hacia arriba.
    // Versión simplificada: score acumula bloques en la cadena + uncle blocks vistos.
    struct ChainNode *parent_node = getChainNode(chain, new_node->height - 1,
                                                  new_node->parent_index);
    // Incrementar score del parent y todos sus ancestros (peso del subárbol)
    // En GHOST real se haría upward propagation; versión simplificada:
    new_node->score = parent_node->score + 1;
    // Uncle contribution: si hay bloques hermanos en height-1, incrementar score
    struct ChainLevel *sibling_level = getChainLevel(chain, new_node->height - 1);
    new_node->score += sibling_level->size - 1; // -1 porque el parent ya cuenta
#else
    new_node->score = new_node->height;
#endif
```

**Makefile — añadir target:**
```makefile
rblocksim_ghost: CFLAGS += -DUSE_GHOST
rblocksim_ghost: rblocksim
```

**Script de comparación (`scripts/compare_fork_rules.py`):**

```python
"""
Compara longest-chain vs GHOST en resultados de selfish mining.
Genera dos binarios (rblocksim y rblocksim_ghost) y corre los mismos
experimentos de selfish mining, comparando success rate y orphan rate.
"""
# Similar a compare_topologies.py pero cambiando el binario
BINARIES = {
    "longest_chain": "RBlockSim/rblocksim",
    "ghost":         "RBlockSim/rblocksim_ghost"
}
```

**Resultado esperado:** Nueva figura: tasa de éxito del selfish miner (Figura 5 del paper)
bajo Longest-Chain vs. GHOST, para α ∈ [0.01, 0.99].
La curva GHOST debería mostrar menor ventaja para el atacante, especialmente para α < 0.5.

---

#### Propuesta B3 — Umbral Teórico de Eyal & Sirer + parámetro γ

**Por qué es nueva:**

Eyal & Sirer (2014) demostraron que el selfish mining es rentable cuando:
```
α > (1 - γ) / (3 - 2γ)
```
donde:
- **α** = fracción de hash rate del atacante
- **γ** = fracción de mineros honestos que adoptan el bloque del atacante en caso de tie

Para γ=0 (ningún honesto adopta el bloque del atacante en empate): **umbral = 1/3**
Para γ=0.5: **umbral ≈ 0.25**
Para γ=1.0: **umbral = 0** (siempre rentable)

El paper **no muestra estas líneas de referencia teórica** en la Figura 5 ni analiza γ.

**Implementación en dos partes:**

**Parte 1 — Análisis puro Python (datos ya existentes, sin compilar):**

```python
# scripts/compare_eyal_sirer.py

import json, os, glob
import numpy as np
import matplotlib.pyplot as plt

STATS_BLOCKS_MINED_BY_ME = 2
STATS_OWN_BLOCKS_IN_MC = 3

def eyal_sirer_threshold(gamma):
    """Umbral teórico de hash rate para rentabilidad de selfish mining."""
    return (1 - gamma) / (3 - 2 * gamma)

def compute_profitability(runs_data):
    """
    Un atacante es rentable si su 'relative revenue' > su alpha.
    relative_revenue = own_blocks_in_MC / total_MC_height
    """
    results = {}
    for run in runs_data:
        alpha = run["attack_info"]["attacker_hashpower"]
        attacker_id = run["attack_info"]["attacker_id"]
        stats = run["stats"]["data"]
        
        own_in_mc = stats[attacker_id][STATS_OWN_BLOCKS_IN_MC]
        mc_height = stats[attacker_id][1]  # STATS_MC_HEIGHT
        
        if mc_height == 0:
            continue
        
        relative_revenue = own_in_mc / mc_height
        is_profitable = relative_revenue > alpha  # gana más de lo esperado
        
        if alpha not in results:
            results[alpha] = []
        results[alpha].append((relative_revenue, is_profitable))
    
    return results

def plot_with_theoretical_threshold(json_folder, network_size, out_path):
    # Cargar datos selfish de profundidad 2 (el más interesante)
    for catchup in [1, 2]:
        fname = os.path.join(json_folder, f"{network_size}_selfish_c{catchup}_d2.json")
        with open(fname) as f:
            runs = json.load(f)
        
        profitability = compute_profitability(runs)
        alphas = sorted(profitability.keys())
        rel_revenues = [np.mean([r[0] for r in profitability[a]]) for a in alphas]
        
        plt.plot(alphas, rel_revenues, label=f"Simulated (catchup={catchup})")
    
    # Línea de referencia: si revenue == alpha, es el esperado (curva diagonal)
    alphas_ref = np.linspace(0, 1, 100)
    plt.plot(alphas_ref, alphas_ref, 'k--', alpha=0.4, label='Expected (honest)')
    
    # Umbrales teóricos de Eyal & Sirer
    for gamma, color in [(0.0, 'red'), (0.5, 'orange'), (1.0, 'green')]:
        threshold = eyal_sirer_threshold(gamma)
        plt.axvline(x=threshold, color=color, linestyle=':', alpha=0.7,
                    label=f'E&S threshold γ={gamma:.1f} (α={threshold:.2f})')
    
    plt.xlabel('Attacker hash rate (α)')
    plt.ylabel('Relative revenue (own blocks in MC / MC height)')
    plt.title(f'Selfish Mining Profitability vs. Eyal & Sirer Threshold\n({network_size} nodes)')
    plt.legend(fontsize=9)
    plt.savefig(out_path, bbox_inches='tight')
    plt.clf()

if __name__ == "__main__":
    json_folder = "reproduced/plots/plots_1/jsons"
    for size in [100, 1000, 10000]:
        plot_with_theoretical_threshold(
            json_folder, size,
            f"reproduced/plots/plots_1/eyal_sirer_comparison_{size}.eps"
        )
```

**Parte 2 — Implementar γ variable en C (opcional, mayor impacto):**

Actualmente el tiebreaking honesto ante scores iguales usa `timestamp` y `miner ID`
(ver `chainNodeMaxHonest()` en `Block.c`). Nunca favorece aleatoriamente al atacante.
Esto equivale a γ=0 implícito.

```c
// Config.h — añadir:
#define GAMMA 0.0   // fracción de honestos que eligen el bloque del atacante en empate

// Block.c — en chainNodeMaxHonest(), cuando scores son iguales:
if (nodeA->score == nodeB->score && nodeA->ancestorsMined == nodeB->ancestorsMined) {
    // Tiebreaking con γ: con prob GAMMA favorecer el bloque más reciente
    // (asumiendo que el atacante libera el bloque recién, timestamp > honest)
    #if GAMMA > 0.0
    // extern struct rng_t *current_rng; // necesita acceso al RNG del nodo actual
    if (Random(current_rng) < GAMMA) {
        return (nodeA->timestamp > nodeB->timestamp) ? nodeA : nodeB;
    }
    #endif
    // Default: favorecer el más antiguo (γ=0)
    if (nodeA->timestamp < nodeB->timestamp) return nodeA;
    // ...
}
```

> **Nota:** Implementar γ requiere acceso al RNG del nodo actual desde `chainNodeMaxHonest()`.
> La variable `current_rng` necesita ser un thread-local o pasarse como parámetro.
> Ver cómo `currentNode` es un `__thread` en `RBlockSim.c` para el patrón a seguir.

---

## 7. Resumen de propuestas y orden de implementación

| ID | Nombre | Novedad | Archivos | Hardware | Esfuerzo | Prioridad |
|----|--------|---------|----------|----------|----------|-----------|
| A1 | IC en figuras de ataques | Baja | repro_plotter.py | < 500MB | 0.5 día | Alta (fácil) |
| A2 | Orphan rate vs. referencia | Media | nuevo script | < 500MB | 1 día | Alta (fácil) |
| B1 | Small-world vs. aleatorio | Alta | generate_topology.py + scripts | < 2GB | 2 días | Media |
| B2 | GHOST fork rule | Muy alta | Block.c + Makefile + scripts | < 2GB | 3 días | Alta (impacto) |
| B3 parte 1 | Umbral Eyal & Sirer (Python) | Alta | nuevo script | < 500MB | 1 día | Alta (fácil) |
| B3 parte 2 | Parámetro γ (C) | Alta | Block.c + Config.h | < 2GB | 2 días | Media |

**Orden recomendado de implementación:**
1. **A2 + B3-parte1** primero (puro Python, datos existentes, resultado inmediato)
2. **A1** (Python, requiere rerunear con iterations=5)
3. **B2 (GHOST)** (el aporte más interesante, requiere C)
4. **B1 (topologías)** o **B3-parte2 (γ)** según tiempo disponible

---

## 8. Verificación de cada propuesta

### A1 (IC)
```bash
# Correr con más iteraciones
# Editar reproducibility_config.json: "iterations": 5, "network_sizes_attacks": [100, 1000]
# Dentro del contenedor Docker o con entorno configurado:
python3 entrypoint.py
# Verificar: plots_N/Figure_4_*.eps deben tener bandas de color semitransparentes
```

### A2 (Orphan Rate)
```bash
python3 scripts/analyze_orphan_rate.py
# Verificar: imprime mean orphan rate por tamaño de red
# Esperado para BI=600s: ~0.3-0.5% para 1000 nodos
```

### B1 (Small-World)
```bash
# Generar topología small-world
cd RBlockSim/src/
python3 generate_topology.py --n_nodes 1000 --topology small_world \
    --sw_density 0.1 --sw_propagation 0.5
cd ../
make rblocksim
# Correr selfish mining y comparar con topología aleatoria
./rblocksim -w 4 -i 600 -a selfish -h 0.3 -c 1 -d 2 -r 42
# Verificar: orphan rate debe ser MENOR con small_world
```

### B2 (GHOST)
```bash
# Compilar versión GHOST
cd RBlockSim/
make rblocksim_ghost
# Correr mismo experimento con ambos binarios, misma semilla
./rblocksim       -w 4 -i 600 -a selfish -h 0.4 -c 1 -d 2 -r 42
./rblocksim_ghost -w 4 -i 600 -a selfish -h 0.4 -c 1 -d 2 -r 42
# Verificar: attackerBlocksInMainChain debe ser MENOR con GHOST para alpha < 0.5
```

### B3 parte 1 (Eyal & Sirer)
```bash
python3 scripts/compare_eyal_sirer.py
# Verificar: en la gráfica, el punto donde revenue > alpha cruza ~ alpha=0.33 (1/3)
# Si el cruce es cerca de 1/3, el modelo es consistente con la teoría
```

---

## 9. Contexto adicional sobre el paper

**Figuras del paper y qué miden:**
- **Figura 3:** Mining rate observado vs. esperado (validación estadística del modelo)
- **Figura 4a-c:** 51% attack — % de bloques del atacante en main chain vs. hash rate
- **Figura 4d-f:** Selfish mining — % de bloques del atacante en main chain vs. hash rate
- **Figura 5:** Tasa de éxito del selfish mining (ataque con concealment) vs. hash rate
- **Figura 6:** Wall clock time vs. worker threads para distintas redes y block intervals
- **Figura 7:** Peak RAM vs. worker threads
- **Figura 8:** RAM usage a lo largo de la simulación

**Parámetros de los experimentos de ataque (hardcodeados en repro_runner.py):**
- `catchup_tolerances = [1, 2]`
- `depth = [1, 2, 3]` (para selfish)
- `hashrates = range(1, 100, 5)` → [0.01, 0.06, 0.11, ..., 0.96]
- Block interval: 600 segundos (Bitcoin-like)

**Referencias teóricas clave:**
- Eyal & Sirer 2014: *"Majority is not enough"* — umbral de selfish mining
- Sompolinsky & Zohar 2013: *"Accelerating bitcoin's transaction processing"* — GHOST
- Gervais et al. 2016: *"On the Security and Performance of PoW Blockchains"* — orphan rates empíricos de Bitcoin (~0.41%)
