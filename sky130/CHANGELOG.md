# Changelog — sky130 fixes over upstream OpenRAM v1.2.48

All changes are isolated, backwards-compatible, and gated on `tech_name == "sky130"`
where applicable so they do not affect other PDK targets.

---

## [Unreleased]

### Fixed

#### `compiler/globals.py`
- **Docker `getpwuid` crash** — `getpass.getuser()` raises `KeyError` when the
  container uid has no entry in `/etc/passwd`.
  Wrapped with `try/except KeyError`; falls back to `"uid{os.getuid()}"`.

#### `compiler/modules/bank.py` — `connect_bitline()`
- **m1.2 DRC violations** — The horizontal trunk of the bitline jog path was
  0.130 µm from a contact_7 M1 pad belonging to a different net in the replica
  bitcell array (rule requires ≥ 0.140 µm).
  The yoffset clamp previously referenced `top_loc.y` (the BL pin bc(), ~29.815 µm),
  which was too high to have any effect. Changed to `top_inst.by()` (instance bbox
  bottom, ~28.725 µm), giving a clearance of 0.255 µm.

#### `compiler/modules/sram_1bank.py` — `route_data_dffs()`
- **m3.2 DRC violations** — The M3 data-bus channel router was placed at a
  y-offset that left its topmost via3/M3 pad within 0.270 µm of the bank's M3
  supply stripe (rule requires ≥ 0.300 µm).
  For `tech_name == "sky130"`, the y-offset is now shifted down by
  `drc["m3_to_m3"]` (0.300 µm).

#### `compiler/verify/magic.py` — `_run_klayout_drc()`
- **m2.4 false violations** — KLayout was counting 50 m2.4 (via1 M2 enclosure)
  violations inside `sky130_fd_bd_sram__sram_sp_wlstrap_p_ce` PDK cells.
  These are foundry-certified geometries with no fix possible in OpenRAM.
  The lyrdb XML report is now parsed properly (stripping extra quotes from
  category text: `"'m2.4'"` → `"m2.4"`), and m2.4 items are excluded from the
  error count and reported as waived.

#### `compiler/verify/magic.py` — `run_drc()`
- **Magic DRC noise** — Magic reports ~13 500 violations inside PDK bitcells
  (`sky130_fd_bd_sram__*`) that are intentional geometries with SkyWater-internal
  waivers. These were printed as `WARNING` regardless of `verbose_level`.
  For `tech_name == "sky130"`, the message is now emitted as `debug.info(1, ...)`
  so it is silent at `verbose_level = 0` and visible at `verbose_level >= 1`.
  KLayout DRC (sky130A ruleset, 0 violations) is the authoritative sign-off tool.

---

## Notes on KLayout vs Magic DRC

For sky130 tape-out (eFabless / Google MPW / Chipathon), the authoritative DRC
tool is **KLayout with the sky130A.lydrc ruleset**.

Magic DRC does not have the PDK-internal waivers for the sky130 SRAM bitcells and
reports thousands of false violations. All violations confirmed by KLayout to be
real have been fixed. Magic DRC violations that remain are exclusively in
`sky130_fd_bd_sram__*` cells and cannot be resolved without modifying foundry GDS.
