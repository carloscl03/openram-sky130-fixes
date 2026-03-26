# SRAM Configuration Guide — sky130

A configuration file is a plain Python script that sets variables consumed by OpenRAM.
Run it with:

```bash
export PATH=/foss/tools/bin:$PATH
cd /foss/designs/OpenRAM
python3 sram_compiler.py sky130/configs/my_sram.py
```

---

## Minimal template

```python
import os, sys

# ── 1. MEMORY DIMENSIONS ────────────────────────────────────────────────────
# These are the only values you need to change between designs.

word_size    = 8      # bits per word  (multiples of 8 recommended)
num_words    = 8      # number of words (powers of 2 recommended)
num_banks    = 1      # 1 or 2

# sky130 arrays require even column/row counts.
# Add 1 spare col/row when word_size or num_words would otherwise be odd.
num_spare_cols = 1
num_spare_rows = 1

# Port configuration — choose exactly one mode:
num_rw_ports = 1   # single-port read/write (most common)
num_r_ports  = 0   # read-only port
num_w_ports  = 0   # write-only port

output_name  = "sram_{}x{}_sky130".format(num_words, word_size)
output_path  = "temp/"

# ── 2. TECHNOLOGY ────────────────────────────────────────────────────────────
# Do not modify for sky130.

tech_name        = "sky130"
bitcell          = "sky130_fd_bd_sram__openram_sp_cell"
replica_bitcell  = "sky130_fd_bd_sram__openram_sp_cell_replica"
dummy_bitcell    = "sky130_fd_bd_sram__openram_sp_cell_dummy"
sp_factory_name  = "sky130"
nominal_corner_only = True
use_max_current  = False

process_corners  = ["TT"]
supply_voltages  = [1.8]
temperatures     = [25]

_tech_path = "/foss/designs/OpenRAM/technology"
if _tech_path not in sys.path:
    sys.path.insert(0, _tech_path)

# ── 3. VALIDATION ────────────────────────────────────────────────────────────
# Runs Magic DRC + KLayout DRC + Netgen LVS automatically after GDS generation.
# Do not modify.

drc_name      = "magic"
lvs_name      = "netgen"
check_lvsdrc  = True    # enable DRC + LVS
inline_lvsdrc = False   # top-level only (avoids black-box errors in sub-cells)

# ── 4. COMPILATION FLAGS ─────────────────────────────────────────────────────

netlist_only     = False   # False = generate GDS; True = netlist only (faster)
analytical_delay = True    # True = math model; False = Xyce simulation (slow)
characterize     = False   # True = full electrical characterisation (very slow)
trim_spice       = False

# Verbosity: 0 = errors+warnings only; 1 = milestones+DRC detail; 2 = full debug
verbose_level    = 0

# ── 5. DOCKER / ENVIRONMENT WORKAROUNDS ──────────────────────────────────────
# Do not modify.

os.environ.setdefault("OPENRAM_MAGIC_NO_USER_RC", "1")
os.environ.setdefault("OPENRAM_SKIP_CONDA", "1")
use_conda = False
```

---

## Key options explained

| Option | Values | Effect |
|--------|--------|--------|
| `word_size` | integer | Bits per word. Use multiples of 8. |
| `num_words` | integer | Number of addressable words. Use powers of 2. |
| `num_spare_cols` | 0 or 1 | Set to 1 if `word_size + num_spare_cols` would be odd. |
| `num_spare_rows` | 0 or 1 | Set to 1 if `num_words + num_spare_rows` would be odd. |
| `num_rw_ports` | 1 | Single-port (1RW). For dual-port set `num_r_ports=1, num_w_ports=1`. |
| `process_corners` | `["TT"]`, `["FF","SS","TT"]` | Corners to characterise. More corners = slower. |
| `supply_voltages` | `[1.8]` | Nominal sky130 supply. |
| `check_lvsdrc` | `True` / `False` | `False` skips DRC+LVS for faster iteration. |
| `netlist_only` | `True` / `False` | `True` skips GDS generation entirely. |
| `verbose_level` | 0, 1, 2 | 1 shows Magic DRC breakdown and routing details. |

---

## Sizing rules for sky130

- `word_size` and `num_words` must each result in an **even** number of columns/rows
  after accounting for spare and replica columns. The easiest rule: always add
  `num_spare_cols = 1` and `num_spare_rows = 1`.
- The bitcell pitch is fixed by the PDK cell. Typical area scales as
  `~(word_size + 2) × (num_words + 2) × bitcell_area`.
- Larger memories increase compilation time roughly linearly.
