from siepic import all as pdk # https://academy.lucedaphotonics.com/pdks/siepic/siepic
from ipkiss3 import all as i3
from ipkiss.technology import get_technology

TECH = get_technology()

class waveguide_tst_structure(i3.Circuit):
    bend_radius = i3.PositiveNumberProperty(default=5.0, doc="Bend radius of the waveguides")
    fgc_spacing_y = i3.PositiveNumberProperty(default=127.0, doc="Spacing between the fiber grating couplers in the y-direction")
    fgc = i3.ChildCellProperty(doc="PCell for the fiber grating coupler")

    delay_length = i3.PositiveNumberProperty(default=60.0, doc="length difference between the arms of the MZI")

    def _default_fgc(self):
        return pdk.EbeamGCTM1550()

    def _default_specs(self):
        instances = [
            i3.Inst(["fgc_1", "fgc_2"], self.fgc),
        ]

        fgc_spacing_y = self.fgc_spacing_y

        placement = [
            i3.Place("fgc_1", (0, 0), angle=0),
            i3.Place("fgc_2", (0, fgc_spacing_y), angle=0),
            i3.ConnectManhattan(
                [("fgc_1:opt1", "fgc_2:opt1", "fgc_1_opt1_to_fgc_1"),],
                bend_radius=self.bend_radius,  # if this value is to big the manhattan connection will not be able to fit in the layout, if it is too small the connection will be very sharp and might cause losses. You can adjust this value to find a good balance between compactness and performance.
            ),

        ]

        specs = instances + placement
        return specs
    
    class Layout(i3.Circuit.Layout):

        def _generate_elements(self, elems):


            elems += i3.Label(
                layer=i3.TECH.PPLAYER.Text,
                coordinate=(0.0, self.fgc_spacing_y),
                text="opt_in_TM_1550_FC",
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

#%%
if __name__ == "__main__":

    # Create the MZI with a custom delay
    el_dut = dut(bend_radius=5.0, fgc_spacing_y=127.0)

    # Generate the layout
    dut_layout = el_dut.Layout()

    # Visualize
    dut_layout.visualize(annotate=True)

    dut_layout.write_gdsii("EBeam_NicolasCasteleyn_waveguide_TM1550_tst_strct.gds")