# SRAM Configuration Guide — sky130

A configuration file is a plain Python script that sets variables consumed by OpenRAM.

> **Always run from the repo root** using `sram_compiler.py` — never run the config
> file directly with `python3`. `sram_compiler.py` sets `OPENRAM_HOME` to the local
> `compiler/` directory, which loads the patched code instead of any system-installed
> `openram` package.

```bash
# Generic (any machine, any clone location)
cd /path/to/OpenRAM        # wherever you cloned the repo
python3 sram_compiler.py sky130/configs/my_sram.py

# Docker (iic-osic-tools_chipathon_xserver)
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
output_path  = "temp/"   # relative to the repo root — auto-created, gitignored

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

# Path-relative: works wherever the repo is cloned.
# Layout: <repo>/sky130/configs/<file>.py  →  3 dirname() calls = repo root
_openram_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_tech_path = os.path.join(_openram_root, "technology")
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

---

## PDK location

OpenRAM needs the sky130A PDK at compile time. The `technology/sky130/` directory
inside this repo contains Python tech files and DRC scripts, but **not** the full
foundry PDK (GDS/SPICE/LVS cells). The PDK cells come from one of these sources:

| Scenario | What to do |
|----------|-----------|
| **Docker `iic-osic-tools_chipathon_xserver`** | PDK is pre-installed at `/foss/pdk`. Nothing to do. |
| **Volare (recommended outside Docker)** | `pip install volare && volare enable --pdk sky130 e8294524` |
| **Manual / already installed** | Set `PDK_ROOT=/path/to/pdks` before running. |
| **Bundled `ciel/` inside this repo** | The `ciel/` directory ships the exact PDK version (e8294524) used during development. OpenRAM will find it automatically if `PDK_ROOT` is not set and the standard paths are absent. |

The `ciel/sky130/versions/e8294524.../sky130A/` tree also contains `sky130A.lydrc`,
the KLayout DRC script. OpenRAM searches for it automatically — you do not need to
set any extra variable.

---

## Common errors and fixes

### `ModuleNotFoundError: No module named 'sky130'`

OpenRAM cannot find the `technology/sky130/` directory.

- Make sure you are running **from the repo root**, not from `sky130/configs/`.
- Check that `_tech_path` resolves correctly:
  ```bash
  python3 -c "import os; f=os.path.abspath('sky130/configs/sram_8x8_sky130.py'); \
  print(os.path.dirname(os.path.dirname(os.path.dirname(f))))"
  # should print the repo root
  ```

### `ModuleNotFoundError: No module named 'openram'` or wrong version loaded

You ran the config file directly instead of via `sram_compiler.py`.

```bash
# Wrong:
python3 sky130/configs/my_sram.py

# Correct:
python3 sram_compiler.py sky130/configs/my_sram.py
```

### `klayout: command not found` or `magic: command not found`

The EDA tools are not in your `PATH`.

- **Docker**: `export PATH=/foss/tools/bin:$PATH`
- **Manual install**: add the install prefix to `PATH`, or set `check_lvsdrc = False`
  to skip DRC/LVS for now.

### `KeyError` on startup (Docker with anonymous UID)

Fixed in `globals.py` (Fix 5 in [../docs/drc_fixes.md](../docs/drc_fixes.md)).
If you still see it, you are running against the upstream package — use
`sram_compiler.py` so the local patched code is loaded.

### `FileNotFoundError: sky130A.lydrc` (KLayout DRC script not found)

Set `PDK_ROOT` to point to your sky130A installation:
```bash
export PDK_ROOT=/path/to/pdks
python3 sram_compiler.py sky130/configs/my_sram.py
```
Or use the bundled `ciel/` PDK by leaving `PDK_ROOT` unset when the repo is the
working directory.

### DRC fails with `m1.2` / `m3.2` violations

You are running against upstream OpenRAM, not this patched version.
Confirm the fixes are active:
```bash
grep "top_inst.by()" compiler/modules/bank.py
# should print the clamp line — if empty, the patch was not applied
```
