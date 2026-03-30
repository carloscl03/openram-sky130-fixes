# How to run OpenRAM without mixing the `pip` package with the repo

**Detailed report (Sky130, LVS, diagnostics, repo changes, `sky130_sram_macros_old` repo):** see **[README_SKY130.md](./README_SKY130.md)**.

---

If you installed `openram` with pip **and** have a copy of the code in `/foss/designs/OpenRAM`, Python may load the package from **`/usr/local/lib/.../site-packages/openram`**. This causes:

- `install_conda` trying to create `miniconda` in **non-writable** paths
- `OPENRAM_TECH` undefined or pointing to the pip package
- Empty bitcell SPICE → `Custom cell pin names do not match spice file ... vs []`

## Recommended solution

From the repository root:

```bash
cd /foss/designs/OpenRAM
python3 sram_compiler.py test_sky130.py
```

`sram_compiler.py` prepends the repo directory to `sys.path` so that **this** tree is **always** used.

Explicit alternative:

```bash
cd /foss/designs/OpenRAM
PYTHONPATH=/foss/designs/OpenRAM python3 sram_compiler.py test_sky130.py
```

## Conda in Docker (read-only)

In `test_sky130.py`, `use_conda = False` uses `magic`/`netgen` from `PATH` without installing Miniconda.

To force skipping conda from the environment:

```bash
export OPENRAM_SKIP_CONDA=1
```

## Useful variables

| Variable | Usage |
|----------|-------|
| `PDK_ROOT` | Root of open_pdks (required for sky130 `technology/__init__.py`) |
| `OPENRAM_TECH` | Set automatically when using the local repo via `sram_compiler.py` |
| `OPENRAM_MAGIC_NO_USER_RC` | Prevents loading another PDK from `~/.magicrc` before sky130 |
| `OPENRAM_TMP` | Magic/Netgen temporary directory (defaults to `/tmp/openram_designer_<pid>_temp/`). If you set it to the same path as `output_path` in the config (e.g. `.../OpenRAM/temp/`), verification artifacts stay there; otherwise, the compiler **also** copies `*.extracted.spice`, `*.lvs.report` and `*.lvs.out` alongside the `output_path` when it differs from `OPENRAM_TMP`. |
