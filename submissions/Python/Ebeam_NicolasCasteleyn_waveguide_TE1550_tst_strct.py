from siepic import all as pdk
from ipkiss3 import all as i3
from ipkiss.technology import get_technology

TECH = get_technology()


class waveguide_tst_structure(i3.Circuit):
    bend_radius = i3.PositiveNumberProperty(default=5.0, doc="Bend radius of the waveguides")
    fgc_spacing_y = i3.PositiveNumberProperty(default=127.0, doc="Spacing between the fiber grating couplers in the y-direction")
    fgc = i3.ChildCellProperty(doc="PCell for the fiber grating coupler")

    delay_length = i3.PositiveNumberProperty(default=60.0, doc="length difference between the arms of the MZI")

    def _default_fgc(self):
        return pdk.EbeamGCTE1550()

    def _default_insts(self):

        return {
            "fgc_1": self.fgc,
            "fgc_2": self.fgc,
        }

    def _default_specs(self):
        placement = [
            i3.Place("fgc_1", (0, 0)),
            i3.Place("fgc_2", (0, self.fgc_spacing_y)),
            i3.ConnectManhattan(
                [("fgc_1:opt1", "fgc_2:opt1", "fgc_1_opt1_to_fgc_1"),],
                bend_radius=self.bend_radius,
            ),
        ]
        return placement

    class Layout(i3.Circuit.Layout):

        def _generate_elements(self, elems):

            elems += i3.Label(
                layer=i3.TECH.PPLAYER.Text,
                coordinate=(0.0, self.fgc_spacing_y),
                text="opt_in_TE_1550_FC",
                alignment=(
                    i3.TEXT.ALIGN.LEFT,
                    i3.TEXT.ALIGN.BOTTOM
                ),
                font=i3.TEXT.FONT.DEFAULT,
                height=0.1,
            )

            return elems

    def _default_exposed_ports(self):
        exposed_ports = {
                            "fgc_2:fib1": "in",
                            "fgc_1:fib1": "out",
        }
        return exposed_ports
    
    
    def annotate_trace_template(trace):
        return {"trace template": trace.trace_template.cell.__class__.__name__}
dut=waveguide_tst_structure
if __name__ == "__main__":

    # Create the MZI with a custom delay
    el_dut = dut(bend_radius=8.0, fgc_spacing_y=127.0)
    el_dut = dut(bend_radius=5.0, fgc_spacing_y=127.0)

    # Generate the layout
    dut_layout = el_dut.Layout()

    # Visualize
    dut_layout.visualize(annotate=True)

    dut_layout.write_gdsii("EBeam_NicolasCasteleyn_waveguide_TE1550_tst_strct.gds")