#!/usr/bin/env python3
"""
gen_xschem_sym.py — Generate an xschem symbol (.sym) from an OpenRAM SPICE netlist.

Usage:
    python3 gen_xschem_sym.py <netlist.sp> [output.sym]

If output.sym is omitted, the symbol is written next to the .sp file.

Bus grouping (reduces visual pin count):
    Pins sharing a base name with sequential numeric indices are grouped into
    a single bus pin regardless of notation:
      din0[0]...din0[7]   → one bus pin  din0[7:0]
      addr0[0]...addr0[2] → one bus pin  addr0[2:0]
      dout0_0...dout0_8   → one bus pin  dout0[8:0]

    Singleton pins (clk0, csb0, web0, spare_wen0, vccd1, vssd1) remain individual.

SPICE correctness:
    xschem instantiates subcircuits by port position, so the bus expansion
    always maps correctly to the subckt port order regardless of pin naming style.
"""

import sys
import os
import re
from collections import defaultdict


# ── Pin classifier ─────────────────────────────────────────────────────────────

def classify_pin(name):
    n = name.lower()
    if any(p in n for p in ['vccd', 'vssd', 'vdd', 'vss', 'vpwr', 'vgnd', 'vcc', 'gnd']):
        return 'power'
    if n.startswith('dout'):
        return 'output'
    return 'input'


# ── SPICE parser ───────────────────────────────────────────────────────────────

def parse_top_subckt(sp_file, cell_name=None):
    with open(sp_file, 'r', errors='replace') as f:
        raw = f.read()
    collapsed = re.sub(r'\n\+\s*', ' ', raw)
    subckts = {}
    for line in collapsed.splitlines():
        m = re.match(r'^\.(subckt|SUBCKT)\s+(\S+)(.*)', line, re.IGNORECASE)
        if m:
            name = m.group(2)
            clean_pins = []
            for p in m.group(3).split():
                if p.startswith('*') or p.startswith('$'):
                    break
                clean_pins.append(p)
            subckts[name] = clean_pins
    if not subckts:
        return None, []
    if cell_name and cell_name in subckts:
        return cell_name, subckts[cell_name]
    last = list(subckts.keys())[-1]
    return last, subckts[last]


# ── Bus detector ───────────────────────────────────────────────────────────────

BRACKET_PAT    = re.compile(r'^(.+?)\[(\d+)\]$')
UNDERSCORE_PAT = re.compile(r'^(.+?)_(\d+)$')

def detect_groups(pins):
    """
    Return two structures:
      bus_groups   : {group_key: {'notation': 'bracket'|'underscore',
                                  'base': str, 'members': [(subckt_idx, pin, bit)]}}
      single_idxs  : set of subckt indices that are NOT part of any bus group
    """
    raw_groups = defaultdict(list)

    for i, pin in enumerate(pins):
        m = BRACKET_PAT.match(pin)
        if m:
            raw_groups[('bracket', m.group(1))].append((i, pin, int(m.group(2))))
            continue
        m = UNDERSCORE_PAT.match(pin)
        if m:
            raw_groups[('underscore', m.group(1))].append((i, pin, int(m.group(2))))
            continue

    # Only keep groups with ≥ 2 members
    bus_groups = {}
    grouped_idxs = set()
    for key, members in raw_groups.items():
        if len(members) >= 2:
            # Sort by subckt order (original index)
            bus_groups[key] = {
                'notation': key[0],
                'base':     key[1],
                'members':  sorted(members, key=lambda x: x[0]),
            }
            for idx, _, _ in members:
                grouped_idxs.add(idx)

    single_idxs = set(range(len(pins))) - grouped_idxs
    return bus_groups, single_idxs


# ── Format string builder ──────────────────────────────────────────────────────

def build_format(pins, bus_groups):
    """
    Build explicit format string that lists EVERY subckt port in order.
    All bus groups (bracket or underscore): @{base[lsb:msb]} — xschem expands LSB→MSB.
    Singles: @pinname.
    """
    # Map subckt_idx → group_key (if in a bus)
    idx_to_group = {}
    for key, g in bus_groups.items():
        for idx, pin, bit in g['members']:
            idx_to_group[idx] = key

    # Track which groups have already been emitted
    emitted_groups = set()
    parts = []

    for i, pin in enumerate(pins):
        if i in idx_to_group:
            key = idx_to_group[i]
            g = bus_groups[key]
            if key in emitted_groups:
                continue  # already written this bus expansion
            emitted_groups.add(key)

            bits = sorted([b for _, _, b in g['members']])
            lsb, msb = bits[0], bits[-1]
            parts.append(f'@{{{g["base"]}[{lsb}:{msb}]}}')
        else:
            parts.append(f'@{pin}')

    return '"@name ' + ' '.join(parts) + ' @symname"'


# ── Layout helpers ─────────────────────────────────────────────────────────────

def centered_ys(n, spacing):
    if n == 0:
        return []
    total = (n - 1) * spacing
    start = -total // 2
    return [start + i * spacing for i in range(n)]

def centered_xs(n, spacing=40):
    if n == 0:
        return []
    total = (n - 1) * spacing
    start = -total // 2
    return [start + i * spacing for i in range(n)]


# ── Symbol writer ──────────────────────────────────────────────────────────────

def generate_sym(cell_name, pins, output_file):

    bus_groups, single_idxs = detect_groups(pins)

    # ── Build visual element list ─────────────────────────────────────────────
    # Each element: {'kind': 'bus'|'single', 'cat': 'input'|'output'|'power',
    #                'label': str, 'members': [...], 'spacing': int}

    # Assign every pin to either a visual bus or a visual single
    idx_to_group = {}
    for key, g in bus_groups.items():
        for idx, _, _ in g['members']:
            idx_to_group[idx] = key

    left_elements  = []   # inputs
    right_elements = []   # outputs
    power_elements = []   # power

    emitted = set()

    for i, pin in enumerate(pins):
        cat = classify_pin(pin)

        if i in idx_to_group:
            key = idx_to_group[i]
            if key in emitted:
                continue
            emitted.add(key)
            g = bus_groups[key]
            bits = sorted([b for _, _, b in g['members']])
            lsb, msb = bits[0], bits[-1]

            # All groups — bracket or underscore — become a single bus pin
            label = f'{g["base"]}[{msb}:{lsb}]'
            elem  = {'kind': 'bus', 'cat': cat, 'label': label,
                     'pin_name': label}
        else:
            elem = {'kind': 'single', 'cat': cat, 'label': pin, 'pin_name': pin}

        if cat == 'power':
            power_elements.append(elem)
        elif cat == 'output':
            right_elements.append(elem)
        else:
            left_elements.append(elem)

    # ── Calculate y positions ─────────────────────────────────────────────────

    def element_height(e):
        return 0  # all elements (bus and single) occupy 1 slot

    SPACING   = 30   # normal inter-element gap
    BOX_X     = 130
    PIN_REACH = 150

    def layout_column(elements):
        """Return list of (element, y_center) pairs, column centered at y=0."""
        # Total height = sum of element heights + gaps between elements
        total = 0
        for e in elements:
            total += element_height(e)
        total += (len(elements) - 1) * SPACING

        y = -total // 2
        result = []
        for e in elements:
            result.append((e, y + element_height(e) // 2))
            y += element_height(e) + SPACING
        return result

    left_layout  = layout_column(left_elements)
    right_layout = layout_column(right_elements)

    all_ys = (
        [y for _, y in left_layout] +
        [y + element_height(e) // 2 for e, y in left_layout] +
        [y for _, y in right_layout] +
        [y + element_height(e) // 2 for e, y in right_layout]
    )
    box_top = (min(all_ys) - SPACING) if all_ys else -60
    box_bot = (max(all_ys) + SPACING) if all_ys else  60

    power_y_pin = box_top - 20
    power_xs    = centered_xs(len(power_elements), 40)

    # ── Format string ─────────────────────────────────────────────────────────
    fmt = build_format(pins, bus_groups)

    # ── Write file ────────────────────────────────────────────────────────────
    out = []

    out.append('v {xschem version=2.9.8 file_version=1.2}')
    out.append('K {type=subcircuit')
    out.append(f'format={fmt}')
    out.append('template="name=x1"')
    out.append('}')
    out.append('')
    out.append(f'T {{{cell_name}}} 0 -10 0 0 0.25 0.25 {{}}')
    out.append(f'T {{@name}} 0 {box_top - 15} 0 0 0.2 0.2 {{}}')
    out.append('')
    out.append(f'L 4 -{BOX_X} {box_top} {BOX_X} {box_top} {{}}')
    out.append(f'L 4 -{BOX_X} {box_bot} {BOX_X} {box_bot} {{}}')
    out.append(f'L 4 -{BOX_X} {box_top} -{BOX_X} {box_bot} {{}}')
    out.append(f'L 4 {BOX_X} {box_top} {BOX_X} {box_bot} {{}}')
    out.append('')

    pnum = [1]  # mutable counter

    def write_pin(name, cat, y, label=None):
        lbl = label or name
        if cat == 'input':
            out.append(f'B 5 -{PIN_REACH+2.5} {y-2.5} -{PIN_REACH-2.5} {y+2.5} '
                       f'{{name={name} dir=in}}')
            out.append(f'L 4 -{PIN_REACH} {y} -{BOX_X} {y} {{}}')
            out.append(f'T {{{lbl}}} -{BOX_X+5} {y-4} 0 1 0.2 0.2 {{}}')
        elif cat == 'output':
            out.append(f'B 5 {PIN_REACH-2.5} {y-2.5} {PIN_REACH+2.5} {y+2.5} '
                       f'{{name={name} dir=out}}')
            out.append(f'L 4 {BOX_X} {y} {PIN_REACH} {y} {{}}')
            out.append(f'T {{{lbl}}} {BOX_X+5} {y-4} 0 0 0.2 0.2 {{}}')
        out.append('')
        pnum[0] += 1

    # Left (inputs)
    for elem, y_center in left_layout:
        write_pin(elem['pin_name'], elem['cat'], y_center, elem['label'])

    # Right (outputs)
    for elem, y_center in right_layout:
        write_pin(elem['pin_name'], elem['cat'], y_center, elem['label'])

    # Power (top)
    for (elem, x) in zip(power_elements, power_xs):
        name = elem['label']
        out.append(f'B 5 {x-2.5} {power_y_pin-2.5} {x+2.5} {power_y_pin+2.5} '
                   f'{{name={name} dir=inout}}')
        out.append(f'L 4 {x} {box_top} {x} {power_y_pin} {{}}')
        out.append(f'T {{{name}}} {x} {power_y_pin-12} 0 0 0.15 0.15 {{}}')
        out.append('')
        pnum[0] += 1

    with open(output_file, 'w') as f:
        f.write('\n'.join(out))

    n_bus    = len(bus_groups)
    n_single = len(single_idxs)
    print(f"Symbol written: {output_file}")
    print(f"  {n_bus} bus pin(s), {n_single} singleton(s) — {len(pins)} SPICE ports total")


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    sp_file = sys.argv[1]
    if not os.path.isfile(sp_file):
        print(f"Error: file not found: {sp_file}")
        sys.exit(1)

    cell_name, pins = parse_top_subckt(sp_file)
    if not cell_name:
        print(f"Error: no .SUBCKT found in {sp_file}")
        sys.exit(1)

    print(f"Found subckt: {cell_name}  ({len(pins)} pins)")

    output_file = sys.argv[2] if len(sys.argv) >= 3 else \
        os.path.splitext(sp_file)[0] + '.sym'

    generate_sym(cell_name, pins, output_file)


if __name__ == '__main__':
    main()
