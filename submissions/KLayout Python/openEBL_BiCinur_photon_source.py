"""
Paper-faithful photon-source microring DOE for the SiEPIC openEBL-2026-05 run.

This script is intentionally self-contained so it can be copied directly into
`submissions/KLayout Python/` in the openEBL repository and executed headlessly
by GitHub Actions.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Iterable

import pya
from pya import Box, CellInstArray, Path, Point, Polygon, Text, Trans

import SiEPIC
from SiEPIC._globals import Python_Env
from SiEPIC.extend import to_itype
from SiEPIC.scripts import connect_cell, connect_pins_with_waveguide, export_layout
from SiEPIC.utils.layout import floorplan, make_pin, new_layout
from SiEPIC.verification import layout_check

if Python_Env == "Script":
    import siepic_ebeam_pdk  # noqa: F401


DESIGNER = "BiCinur"
TECH_NAME = "EBeam"
TOP_CELL_NAME = "openEBL_BiCinur_photon_source"
EXPORT_TYPE = "static"
WAVEGUIDE_TYPE = "Strip TE 1550 nm, w=500 nm"
ACCESS_WIDTH_UM = 0.5
TAPER_LENGTH_UM = 20.0
BUS_TRANSITION_RADIUS_UM = 5.0
GC_PITCH_UM = 127.0
DEVICE_OFFSET_X_UM = 85.0
REFERENCE_OFFSET_X_UM = 50.0
CELL_WIDTH_UM = 605.0
CELL_HEIGHT_UM = 410.0
SEM_SIZE_UM = (24.0, 18.0)  # 4:3


@dataclass(frozen=True)
class DeviceSpec:
    device_id: str
    kind: str
    label_suffix: str
    radius_um: float | None = None
    ring_width_um: float | None = None
    bus_width_um: float | None = None
    gap_um: float | None = None
    theta_deg: float | None = None
    repeat_tag: str | None = None


DEVICES = [
    DeviceSpec("PP01", "custom_ring", "PP_R40_W1500_B856_G150_T30", 40, 1.5, 0.856, 0.150, 30),
    DeviceSpec("PP02", "custom_ring", "PP_R40_W1500_B856_G175_T30", 40, 1.5, 0.856, 0.175, 30),
    DeviceSpec("PP03", "custom_ring", "PP_R40_W1500_B856_G200_T30_REP1", 40, 1.5, 0.856, 0.200, 30, "anchor"),
    DeviceSpec("PP04", "custom_ring", "PP_R40_W1500_B856_G200_T30_REP2", 40, 1.5, 0.856, 0.200, 30, "anchor"),
    DeviceSpec("PP05", "custom_ring", "PP_R40_W1500_B856_G225_T30", 40, 1.5, 0.856, 0.225, 30),
    DeviceSpec("PP06", "custom_ring", "PP_R40_W1500_B856_G250_T30", 40, 1.5, 0.856, 0.250, 30),
    DeviceSpec("PP07", "straight_reference", "PP_REF_STRAIGHT500"),
    DeviceSpec("PP08", "taper_reference", "PP_REF_TAPER500_856", bus_width_um=0.856),
    DeviceSpec("PP09", "pdk_control_ring", "PP_CTRL_PDK_R40_W500_G200", 40, 0.5, 0.5, 0.200),
]


def um(value_um: float, dbu: float) -> int:
    return to_itype(value_um, dbu)


def polygon_from_um(points_um: Iterable[tuple[float, float]], dbu: float) -> Polygon:
    return Polygon([Point(um(x, dbu), um(y, dbu)) for x, y in points_um])


def annular_arc_polygon(
    center_x_um: float,
    center_y_um: float,
    radius_um: float,
    width_um: float,
    start_deg: float,
    stop_deg: float,
    dbu: float,
    points_per_turn: int = 256,
) -> Polygon:
    span = abs(stop_deg - start_deg)
    steps = max(16, int(points_per_turn * span / 360.0))
    outer_radius = radius_um + width_um / 2.0
    inner_radius = radius_um - width_um / 2.0
    pts: list[tuple[float, float]] = []
    for i in range(steps + 1):
        angle = math.radians(start_deg + (stop_deg - start_deg) * i / steps)
        pts.append(
            (
                center_x_um + outer_radius * math.cos(angle),
                center_y_um + outer_radius * math.sin(angle),
            )
        )
    for i in range(steps, -1, -1):
        angle = math.radians(start_deg + (stop_deg - start_deg) * i / steps)
        pts.append(
            (
                center_x_um + inner_radius * math.cos(angle),
                center_y_um + inner_radius * math.sin(angle),
            )
        )
    return polygon_from_um(pts, dbu)


def add_pin(
    cell: pya.Cell,
    layer: int,
    _text_layer: int,
    x_um: float,
    y_um: float,
    width_um: float,
    name: str,
    _dbu: float,
    direction: int,
) -> None:
    make_pin(cell, name, [x_um, y_um], width_um, layer, direction)


def taper_polygon(
    x0_um: float,
    x1_um: float,
    y_um: float,
    width0_um: float,
    width1_um: float,
    dbu: float,
) -> Polygon:
    return polygon_from_um(
        [
            (x0_um, y_um - width0_um / 2.0),
            (x0_um, y_um + width0_um / 2.0),
            (x1_um, y_um + width1_um / 2.0),
            (x1_um, y_um - width1_um / 2.0),
        ],
        dbu,
    )


def build_custom_ring_cell(layout: pya.Layout, spec: DeviceSpec) -> pya.Cell:
    assert spec.radius_um is not None
    assert spec.ring_width_um is not None
    assert spec.bus_width_um is not None
    assert spec.gap_um is not None
    assert spec.theta_deg is not None

    cell = layout.create_cell(f"{spec.device_id}_custom_ring")
    tech = layout.TECHNOLOGY
    si = layout.layer(tech["Si"])
    pinrec = layout.layer(tech["PinRec"])
    devrec = layout.layer(tech["DevRec"])
    text_layer = layout.layer(tech["Text"])
    dbu = layout.dbu

    radius = spec.radius_um
    ring_width = spec.ring_width_um
    bus_width = spec.bus_width_um
    gap = spec.gap_um
    bend_angle = spec.theta_deg / 2.0
    bus_radius = BUS_TRANSITION_RADIUS_UM
    coupling_radius = radius + ring_width / 2.0 + gap + bus_width / 2.0
    a = math.radians(bend_angle)

    # Full ring.
    cell.shapes(si).insert(annular_arc_polygon(0, 0, radius, ring_width, 0, 360, dbu))

    # Bent bus coupler: left transition arc, concentric coupling arc, right transition arc.
    x_left = -coupling_radius * math.sin(a) - bus_radius * math.sin(a)
    x_right = -x_left
    y_side = coupling_radius * math.cos(a) + bus_radius * math.cos(a)
    y_access = y_side - bus_radius

    cell.shapes(si).insert(
        annular_arc_polygon(x_left, y_side, bus_radius, bus_width, 270, 270 + bend_angle, dbu)
    )
    cell.shapes(si).insert(
        annular_arc_polygon(0, 0, coupling_radius, bus_width, 90 - bend_angle, 90 + bend_angle, dbu)
    )
    cell.shapes(si).insert(
        annular_arc_polygon(x_right, y_side, bus_radius, bus_width, 270 - bend_angle, 270, dbu)
    )

    # 500-nm access tapers.
    x_pin_left = x_left - TAPER_LENGTH_UM
    x_pin_right = x_right + TAPER_LENGTH_UM
    cell.shapes(si).insert(
        taper_polygon(x_pin_left, x_left, y_access, ACCESS_WIDTH_UM, bus_width, dbu)
    )
    cell.shapes(si).insert(
        taper_polygon(x_right, x_pin_right, y_access, bus_width, ACCESS_WIDTH_UM, dbu)
    )

    add_pin(cell, pinrec, text_layer, x_pin_left, y_access, ACCESS_WIDTH_UM, "opt1", dbu, 180)
    add_pin(cell, pinrec, text_layer, x_pin_right, y_access, ACCESS_WIDTH_UM, "opt2", dbu, 0)

    margin = 4.0
    dev_box = Box(
        um(x_pin_left, dbu),
        um(-radius - ring_width / 2.0 - margin, dbu),
        um(x_pin_right, dbu),
        um(y_side + bus_radius + margin, dbu),
    )
    cell.shapes(devrec).insert(dev_box)
    cell.shapes(devrec).insert(
        Text(
            f"Component=custom_bent_ring_{spec.device_id}",
            Trans(Trans.R0, um(x_pin_left, dbu), um(-radius - margin / 2.0, dbu)),
        )
    ).text_size = um(0.8, dbu)
    cell.shapes(devrec).insert(
        Text(
            (
                "Spice_param:"
                f"radius={radius:.3f}u "
                f"ring_width={ring_width:.3f}u "
                f"bus_width={bus_width:.3f}u "
                f"gap={gap:.3f}u "
                f"theta={spec.theta_deg:.3f}"
            ),
            Trans(Trans.R0, um(x_pin_left, dbu), um(-radius + margin / 2.0, dbu)),
        )
    ).text_size = um(0.8, dbu)
    return cell


def build_straight_reference_cell(layout: pya.Layout) -> pya.Cell:
    cell = layout.create_cell("straight_reference_500nm")
    tech = layout.TECHNOLOGY
    si = layout.layer(tech["Si"])
    pinrec = layout.layer(tech["PinRec"])
    devrec = layout.layer(tech["DevRec"])
    text_layer = layout.layer(tech["Text"])
    dbu = layout.dbu
    half_length_um = 35.0
    cell.shapes(si).insert(
        Box(
            um(-half_length_um, dbu),
            um(-ACCESS_WIDTH_UM / 2.0, dbu),
            um(half_length_um, dbu),
            um(ACCESS_WIDTH_UM / 2.0, dbu),
        )
    )
    add_pin(cell, pinrec, text_layer, -half_length_um, 0, ACCESS_WIDTH_UM, "opt1", dbu, 180)
    add_pin(cell, pinrec, text_layer, half_length_um, 0, ACCESS_WIDTH_UM, "opt2", dbu, 0)
    cell.shapes(devrec).insert(Box(um(-half_length_um, dbu), um(-3, dbu), um(half_length_um, dbu), um(3, dbu)))
    return cell


def build_taper_reference_cell(layout: pya.Layout, wide_width_um: float) -> pya.Cell:
    cell = layout.create_cell(f"taper_reference_{int(round(wide_width_um * 1000))}nm")
    tech = layout.TECHNOLOGY
    si = layout.layer(tech["Si"])
    pinrec = layout.layer(tech["PinRec"])
    devrec = layout.layer(tech["DevRec"])
    text_layer = layout.layer(tech["Text"])
    dbu = layout.dbu
    wide_length_um = 30.0
    x_left = -wide_length_um / 2.0 - TAPER_LENGTH_UM
    x_right = wide_length_um / 2.0 + TAPER_LENGTH_UM
    cell.shapes(si).insert(
        taper_polygon(x_left, -wide_length_um / 2.0, 0, ACCESS_WIDTH_UM, wide_width_um, dbu)
    )
    cell.shapes(si).insert(
        Box(
            um(-wide_length_um / 2.0, dbu),
            um(-wide_width_um / 2.0, dbu),
            um(wide_length_um / 2.0, dbu),
            um(wide_width_um / 2.0, dbu),
        )
    )
    cell.shapes(si).insert(
        taper_polygon(wide_length_um / 2.0, x_right, 0, wide_width_um, ACCESS_WIDTH_UM, dbu)
    )
    add_pin(cell, pinrec, text_layer, x_left, 0, ACCESS_WIDTH_UM, "opt1", dbu, 180)
    add_pin(cell, pinrec, text_layer, x_right, 0, ACCESS_WIDTH_UM, "opt2", dbu, 0)
    cell.shapes(devrec).insert(Box(um(x_left, dbu), um(-3, dbu), um(x_right, dbu), um(3, dbu)))
    return cell


def add_measurement_label(cell: pya.Cell, layout: pya.Layout, x_um: float, y_um: float, label: str) -> None:
    text_layer = layout.layer(layout.TECHNOLOGY["Text"])
    text = Text(label, Trans(Trans.R90, um(x_um, layout.dbu), um(y_um, layout.dbu)))
    text.halign = 1
    cell.shapes(text_layer).insert(text).text_size = um(5.0, layout.dbu)


def add_sem_window(cell: pya.Cell, layout: pya.Layout, center_x_um: float, center_y_um: float) -> None:
    sem = layout.layer(layout.TECHNOLOGY["SEM"])
    width_um, height_um = SEM_SIZE_UM
    cell.shapes(sem).insert(
        Box(
            um(center_x_um - width_um / 2.0, layout.dbu),
            um(center_y_um - height_um / 2.0, layout.dbu),
            um(center_x_um + width_um / 2.0, layout.dbu),
            um(center_y_um + height_um / 2.0, layout.dbu),
        )
    )


def place_two_port_device(
    cell: pya.Cell,
    layout: pya.Layout,
    gc_cell: pya.Cell,
    device_cell: pya.Cell,
    x_um: float,
    y_um: float,
    label: str,
    device_offset_x_um: float = DEVICE_OFFSET_X_UM,
) -> tuple[pya.Instance, pya.Instance, pya.Instance]:
    dbu = layout.dbu
    inst_gc_in = cell.insert(CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um, dbu))))
    inst_gc_out = cell.insert(
        CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um + GC_PITCH_UM, dbu)))
    )
    inst_device = cell.insert(CellInstArray(device_cell.cell_index(), Trans(Trans.R90, um(x_um + device_offset_x_um, dbu), um(y_um + GC_PITCH_UM / 2.0, dbu))))
    connect_pins_with_waveguide(inst_gc_in, "opt1", inst_device, "opt1", waveguide_type=WAVEGUIDE_TYPE)
    connect_pins_with_waveguide(inst_gc_out, "opt1", inst_device, "opt2", waveguide_type=WAVEGUIDE_TYPE)
    add_measurement_label(cell, layout, x_um, y_um + GC_PITCH_UM, label)
    return inst_gc_in, inst_gc_out, inst_device


def place_custom_ring_device(
    cell: pya.Cell,
    layout: pya.Layout,
    gc_cell: pya.Cell,
    spec: DeviceSpec,
    x_um: float,
    y_um: float,
    label: str,
) -> tuple[pya.Instance, pya.Instance, pya.Instance]:
    assert spec.radius_um is not None
    assert spec.ring_width_um is not None
    assert spec.bus_width_um is not None
    assert spec.gap_um is not None
    assert spec.theta_deg is not None

    dbu = layout.dbu
    inst_gc_in = cell.insert(CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um, dbu))))
    inst_gc_out = cell.insert(
        CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um + GC_PITCH_UM, dbu)))
    )

    bent = layout.create_cell(
        "DirectionalCoupler_Bent",
        "EBeam_Beta",
        {
            "radius": spec.radius_um,
            "bus_radius": BUS_TRANSITION_RADIUS_UM,
            "gap": spec.gap_um,
            "bus_width": spec.bus_width_um,
            "ring_width": spec.ring_width_um,
            "bend_angle": spec.theta_deg / 2.0,
        },
    )
    closing_arc = layout.create_cell(
        "Waveguide_Arc",
        "EBeam_Beta",
        {
            "radius": spec.radius_um,
            "wg_width": spec.ring_width_um,
            "start_angle": 180,
            "stop_angle": 360,
        },
    )
    taper_in = layout.create_cell(
        "ebeam_taper",
        "EBeam_Beta",
        {
            "wg_width1": ACCESS_WIDTH_UM,
            "wg_width2": spec.bus_width_um,
            "wg_length": TAPER_LENGTH_UM,
        },
    )
    taper_out = layout.create_cell(
        "ebeam_taper",
        "EBeam_Beta",
        {
            "wg_width1": spec.bus_width_um,
            "wg_width2": ACCESS_WIDTH_UM,
            "wg_length": TAPER_LENGTH_UM,
        },
    )

    ring_center = Trans(Trans.R0, um(x_um + DEVICE_OFFSET_X_UM, dbu), um(y_um + GC_PITCH_UM / 2.0, dbu))
    inst_bent = cell.insert(CellInstArray(bent.cell_index(), ring_center))
    cell.insert(CellInstArray(closing_arc.cell_index(), ring_center))
    inst_taper_in = connect_cell(inst_bent, "pin2", taper_in, "opt2")
    inst_taper_out = connect_cell(inst_bent, "pin1", taper_out, "opt1")

    connect_pins_with_waveguide(inst_gc_in, "opt1", inst_taper_in, "opt1", waveguide_type=WAVEGUIDE_TYPE)
    connect_pins_with_waveguide(inst_gc_out, "opt1", inst_taper_out, "opt2", waveguide_type=WAVEGUIDE_TYPE)
    add_measurement_label(cell, layout, x_um, y_um + GC_PITCH_UM, label)
    return inst_gc_in, inst_gc_out, inst_bent


def place_straight_reference(
    cell: pya.Cell,
    layout: pya.Layout,
    gc_cell: pya.Cell,
    x_um: float,
    y_um: float,
    label: str,
) -> None:
    dbu = layout.dbu
    inst_gc_in = cell.insert(CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um, dbu))))
    inst_gc_out = cell.insert(
        CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um + GC_PITCH_UM, dbu)))
    )
    connect_pins_with_waveguide(inst_gc_in, "opt1", inst_gc_out, "opt1", waveguide_type=WAVEGUIDE_TYPE)
    add_measurement_label(cell, layout, x_um, y_um + GC_PITCH_UM, label)


def place_taper_reference(
    cell: pya.Cell,
    layout: pya.Layout,
    gc_cell: pya.Cell,
    wide_width_um: float,
    x_um: float,
    y_um: float,
    label: str,
) -> None:
    dbu = layout.dbu
    inst_gc_in = cell.insert(CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um, dbu))))
    inst_gc_out = cell.insert(
        CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um + GC_PITCH_UM, dbu)))
    )
    taper_in = layout.create_cell(
        "ebeam_taper",
        "EBeam_Beta",
        {"wg_width1": ACCESS_WIDTH_UM, "wg_width2": wide_width_um, "wg_length": TAPER_LENGTH_UM},
    )
    taper_out = layout.create_cell(
        "ebeam_taper",
        "EBeam_Beta",
        {"wg_width1": wide_width_um, "wg_width2": ACCESS_WIDTH_UM, "wg_length": TAPER_LENGTH_UM},
    )
    inst_taper_in = cell.insert(
        CellInstArray(taper_in.cell_index(), Trans(Trans.R0, um(x_um + DEVICE_OFFSET_X_UM, dbu), um(y_um + GC_PITCH_UM / 2.0, dbu)))
    )
    inst_taper_out = connect_cell(inst_taper_in, "opt2", taper_out, "opt1")
    connect_pins_with_waveguide(inst_gc_in, "opt1", inst_taper_in, "opt1", waveguide_type=WAVEGUIDE_TYPE)
    connect_pins_with_waveguide(inst_gc_out, "opt1", inst_taper_out, "opt2", waveguide_type=WAVEGUIDE_TYPE)
    add_measurement_label(cell, layout, x_um, y_um + GC_PITCH_UM, label)


def place_pdk_control_ring(
    cell: pya.Cell,
    layout: pya.Layout,
    gc_cell: pya.Cell,
    x_um: float,
    y_um: float,
    label: str,
) -> None:
    dbu = layout.dbu
    inst_gc_in = cell.insert(CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um, dbu))))
    inst_gc_out = cell.insert(
        CellInstArray(gc_cell.cell_index(), Trans(Trans.R0, um(x_um, dbu), um(y_um + GC_PITCH_UM, dbu)))
    )
    dc = layout.create_cell("ebeam_dc_halfring_straight", "EBeam", {"r": 40, "w": 0.5, "g": 0.2})
    wg = layout.create_cell(
        "Waveguide_Arc",
        "EBeam_Beta",
        {"radius": 40, "wg_width": 0.5, "start_angle": 0, "stop_angle": 180},
    )
    inst_dc = cell.insert(CellInstArray(dc.cell_index(), Trans(Trans.R90, um(x_um + DEVICE_OFFSET_X_UM, dbu), um(y_um + GC_PITCH_UM / 2.0, dbu))))
    connect_cell(inst_dc, "pin2", wg, "pin1")
    connect_pins_with_waveguide(inst_gc_in, "opt1", inst_dc, "pin1", waveguide_type=WAVEGUIDE_TYPE)
    connect_pins_with_waveguide(inst_gc_out, "opt1", inst_dc, "pin3", waveguide_type=WAVEGUIDE_TYPE)
    add_measurement_label(cell, layout, x_um, y_um + GC_PITCH_UM, label)


def build_layout() -> tuple[pya.Layout, pya.Cell]:
    top_cell, layout = new_layout(TECH_NAME, TOP_CELL_NAME, GUI=True, overwrite=True)
    floorplan(top_cell, um(CELL_WIDTH_UM, layout.dbu), um(CELL_HEIGHT_UM, layout.dbu))

    gc_cell = layout.create_cell("GC_TE_1550_8degOxide_BB", "EBeam")
    positions = [
        (40.0, 20.0),
        (145.0, 20.0),
        (250.0, 20.0),
        (355.0, 20.0),
        (460.0, 20.0),
        (40.0, 220.0),
        (145.0, 220.0),
        (250.0, 220.0),
        (355.0, 220.0),
    ]

    anchor_instance = None
    sidewall_sem_center = None
    for spec, (x_um, y_um) in zip(DEVICES, positions):
        label = f"opt_in_TE_1550_device_{DESIGNER}_{spec.label_suffix}"
        if spec.kind == "custom_ring":
            device_cell = build_custom_ring_cell(layout, spec)
            _, _, inst_device = place_two_port_device(top_cell, layout, gc_cell, device_cell, x_um, y_um, label)
            if spec.device_id == "PP03":
                anchor_instance = inst_device
                sidewall_sem_center = (x_um + DEVICE_OFFSET_X_UM - spec.radius_um, y_um + GC_PITCH_UM / 2.0)
        elif spec.kind == "straight_reference":
            ref_cell = build_straight_reference_cell(layout)
            place_two_port_device(top_cell, layout, gc_cell, ref_cell, x_um, y_um, label, REFERENCE_OFFSET_X_UM)
        elif spec.kind == "taper_reference":
            assert spec.bus_width_um is not None
            ref_cell = build_taper_reference_cell(layout, spec.bus_width_um)
            place_two_port_device(top_cell, layout, gc_cell, ref_cell, x_um, y_um, label, REFERENCE_OFFSET_X_UM)
        elif spec.kind == "pdk_control_ring":
            place_pdk_control_ring(top_cell, layout, gc_cell, x_um, y_um, label)
        else:
            raise ValueError(f"Unknown device kind: {spec.kind}")

    if anchor_instance is not None:
        bbox = anchor_instance.bbox()
        center_x_um = (bbox.left + bbox.right) * layout.dbu / 2.0
        center_y_um = bbox.top * layout.dbu - 5.0
        add_sem_window(top_cell, layout, center_x_um, center_y_um)
    if sidewall_sem_center is not None:
        add_sem_window(top_cell, layout, *sidewall_sem_center)

    return layout, top_cell


def main() -> None:
    layout, cell = build_layout()
    num_errors = layout_check(cell=cell, verbose=False, GUI=True)
    print(f"Number of local pre-export layout-check errors: {num_errors}")

    path = os.path.dirname(os.path.realpath(__file__))
    filename = os.path.splitext(os.path.basename(__file__))[0]
    if EXPORT_TYPE == "static":
        file_out = export_layout(cell, path, filename, relative_path="..", format="oas", screenshot=True)
    else:
        file_out = os.path.join(path, "..", filename + ".oas")
        layout.write(file_out)
    print(f"Exported: {file_out}")


if __name__ == "__main__":
    main()
