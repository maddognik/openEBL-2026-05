from siepic import all as pdk # https://academy.lucedaphotonics.com/pdks/siepic/siepic
from ipkiss3 import all as i3
from ipkiss.technology import get_technology

TECH = get_technology()
class Layout_global(i3.Circuit.Layout):

    def __init__(self, text:str = "opt_in_TE_1550_Michelson", **kwargs):
        super().__init__(**kwargs)
        self.text = str(self.cell.name)

    def _generate_elements(self, elems):

        elems += i3.Label(
            layer=i3.TECH.PPLAYER.Text,
            coordinate=(0.0, self.fgc_spacing_y),
            text=f"{self.text}",
            alignment=(
                i3.TEXT.ALIGN.LEFT,
                i3.TEXT.ALIGN.BOTTOM
            ),
            font=i3.TEXT.FONT.DEFAULT,
            height=0.1,
        )

        return elems

class Michelson_TE1550(i3.Circuit):
    bend_radius = i3.PositiveNumberProperty(default=5.0, doc="Bend radius of the waveguides")
    fgc_spacing_y = i3.PositiveNumberProperty(default=127.0, doc="Spacing between the fiber grating couplers in the y-direction")
    fgc_dc_spacing = i3.PositiveNumberProperty(default=30.0, doc="Spacing between the fiber grating couplers in the y-direction")
    resonator_spacing = i3.PositiveNumberProperty(default=13.0, doc="Spacing between the resonators")

    fgc = i3.ChildCellProperty(doc="PCell for the fiber grating coupler")
    splitter = i3.ChildCellProperty(doc="PCell for the Y-Branch")
    dir_coupler = i3.ChildCellProperty(doc="PCell for the directional coupler")

    delay_length = i3.PositiveNumberProperty(default=60.0, doc="length difference between the arms of the MZI")

    def _default_fgc(self):
        return pdk.EbeamGCTE1550()

    def _default_splitter(self):
        return pdk.EbeamY1550()

    def _default_dir_coupler(self):
        return pdk.EbeamBDCTE1550()
    
    def _default_specs(self):
        instances = [
            i3.Inst(["fgc_1", "fgc_2"], self.fgc),
            i3.Inst("dc", self.dir_coupler),
            i3.Inst(["yb_1", "yb_2"], self.splitter),
        ]

        placement = [
            i3.Place("fgc_1", (0, 0)),
            i3.Place("fgc_2", (0, self.fgc_spacing_y)),
            i3.Place("dc", (self.fgc_dc_spacing, self.fgc_spacing_y * 0.45), angle=90),
            i3.FlipV("dc"),
            
            # mirror arms
            i3.Place("yb_1",(self.bend_radius*1.5 + self.resonator_spacing, -2.0), angle=-90, relative_to="dc:opt1"),
            i3.Place("yb_2",(self.bend_radius*1.5, -2.0), angle=-90, relative_to="dc:opt1"),
            i3.ConnectManhattan(
                [
                    ("fgc_1:opt1", "dc:opt1", "fgc_1_opt1_to_dc_opt1"),
                    ("fgc_2:opt1", "dc:opt2", "fgc_2_opt1_to_dc_opt2"),
                    
                ],
                bend_radius=self.bend_radius,  # if this value is to big the manhattan connection will not be able to fit in the layout, if it is too small the connection will be very sharp and might cause losses. You can adjust this value to find a good balance between compactness and performance.
            ),
            # reference arm
            i3.ConnectManhattan(
                [
                    # ("dc:opt4", "yb_1:opt1", "dc_opt4_to_yb_1_opt1",),
                    ("dc:opt3", "yb_2:opt1", "dc_opt3_to_yb_2_opt1",),
                    
                ],
                bend_radius=self.bend_radius,  # if this value is to big the manhattan connection will not be able to fit in the layout, if it is too small the connection will be very sharp and might cause losses. You can adjust this value to find a good balance between compactness and performance.
            # start_straight=5.0,  # add a straight section at the beginning of the connection to ensure that the waveguide is straight before it starts bending, this can help reduce losses and improve performance.
            ),

            # sensing arm
            i3.ConnectManhattan(
                "dc:opt4",
                "yb_1:opt1",
                "dc_opt4_to_yb_1_opt1",
            start_straight=15.0,  # add a straight section at the beginning of the connection to ensure that the waveguide is straight before it starts bending, this can help reduce losses and improve performance.
            control_points=[
                            i3.V(self.fgc_spacing_y * 0.5, flexible=True)
            ],
                match_path_length=i3.MatchLength(reference="dc_opt3_to_yb_2_opt1", delta=self.delay_length),
            ),

            # splitters loops
            i3.ConnectBend([
                            ("yb_1:opt2", "yb_1:opt3", "sensing_loop"), 
                            ("yb_2:opt2", "yb_2:opt3", "reference_loop"),
                ],
                bend_radius=self.bend_radius,
            ),
        ]

        specs = instances + placement
        return specs
    
    def get_connector_instances(self):
        lv_instances = self.get_default_view(i3.LayoutView).instances
        return [
            lv_instances["fgc_1_opt1_to_dc_opt1"],
            lv_instances["fgc_2_opt1_to_dc_opt2"],
            lv_instances["dc_opt4_to_yb_1_opt1"],
            lv_instances["dc_opt3_to_yb_2_opt1"],
        ]

    def _default_exposed_ports(self):
        exposed_ports = {
                            "fgc_2:fib1": "in",
                            "fgc_1:fib1": "out",
        }
        return exposed_ports
    
    def annotate_trace_template(trace):
        return {"trace template": trace.trace_template.cell.__class__.__name__}
    
    class Layout(Layout_global):

        def __init__(self, text = "opt_in_TE_1550_Michelson", **kwargs):
            super().__init__(text, **kwargs)

# WaveguideBraggGratingTemplate luceda - https://www.google.com/url?sa=t&source=web&rct=j&opi=89978449&url=https://www.youtube.com/watch%3Fv%3DU50iE6aBf2k&ved=2ahUKEwjSv4reh6eUAxWsRaQEHehGM90Q3aoNegQIFRAf&usg=AOvVaw2BqwCp0PiEEj26MnbEui9i
class Michelson_TE1550_wg(i3.Circuit):
    bend_radius = i3.PositiveNumberProperty(default=5.0, doc="Bend radius of the waveguides")
    fgc_spacing_y = i3.PositiveNumberProperty(default=127.0, doc="Spacing between the fiber grating couplers in the y-direction")
    fgc_dc_spacing = i3.PositiveNumberProperty(default=30.0, doc="Spacing between the fiber grating couplers in the y-direction")
    resonator_spacing = i3.PositiveNumberProperty(default=13.0, doc="Spacing between the resonators")

    fgc = i3.ChildCellProperty(doc="PCell for the fiber grating coupler")
    splitter = i3.ChildCellProperty(doc="PCell for the Y-Branch")
    dir_coupler = i3.ChildCellProperty(doc="PCell for the directional coupler")

    delay_length = i3.PositiveNumberProperty(default=60.0, doc="length difference between the arms of the MZI")

    def _default_fgc(self):
        return pdk.EbeamGCTE1550()

    def _default_splitter(self):
        return pdk.EbeamY1550()

    def _default_dir_coupler(self):
        return pdk.EbeamBDCTE1550()
    
    def _defaul_trace_template(self):
        return pdk.WaveguideBraggGratingTemplate()
    
    def _default_specs(self):
        instances = [
            i3.Inst(["fgc_1", "fgc_2"], self.fgc),
            i3.Inst("dc", self.dir_coupler),
            i3.Inst(["yb_1", "yb_2"], self.splitter),
        ]

        placement = [
            i3.Place("fgc_1", (0, 0)),
            i3.Place("fgc_2", (0, self.fgc_spacing_y)),
            i3.Place("dc", (self.fgc_dc_spacing, self.fgc_spacing_y * 0.45), angle=90),
            i3.FlipV("dc"),
            
            # mirror arms
            i3.Place("yb_1",(self.bend_radius*1.5 + self.resonator_spacing, -2.0), angle=-90, relative_to="dc:opt1"),
            i3.Place("yb_2",(self.bend_radius*1.5, -2.0), angle=-90, relative_to="dc:opt1"),
            i3.ConnectManhattan(
                [
                    ("fgc_1:opt1", "dc:opt1", "fgc_1_opt1_to_dc_opt1"),
                    ("fgc_2:opt1", "dc:opt2", "fgc_2_opt1_to_dc_opt2"),
                    
                ],
                bend_radius=self.bend_radius,  # if this value is to big the manhattan connection will not be able to fit in the layout, if it is too small the connection will be very sharp and might cause losses. You can adjust this value to find a good balance between compactness and performance.
            ),
            # reference arm
            i3.ConnectManhattan(
                [
                    # ("dc:opt4", "yb_1:opt1", "dc_opt4_to_yb_1_opt1",),
                    ("dc:opt3", "yb_2:opt1", "dc_opt3_to_yb_2_opt1",),
                    
                ],
                bend_radius=self.bend_radius,  # if this value is to big the manhattan connection will not be able to fit in the layout, if it is too small the connection will be very sharp and might cause losses. You can adjust this value to find a good balance between compactness and performance.
            # start_straight=5.0,  # add a straight section at the beginning of the connection to ensure that the waveguide is straight before it starts bending, this can help reduce losses and improve performance.
            ),

            # sensing arm
            i3.ConnectManhattan(
                "dc:opt4",
                "yb_1:opt1",
                "dc_opt4_to_yb_1_opt1",
            start_straight=15.0,  # add a straight section at the beginning of the connection to ensure that the waveguide is straight before it starts bending, this can help reduce losses and improve performance.
            control_points=[
                            i3.V(self.fgc_spacing_y * 0.5, flexible=True)
            ],
                match_path_length=i3.MatchLength(reference="dc_opt3_to_yb_2_opt1", delta=self.delay_length),
            ),

            # splitters loops
            i3.ConnectBend([
                            ("yb_1:opt2", "yb_1:opt3", "sensing_loop"), 
                            ("yb_2:opt2", "yb_2:opt3", "reference_loop"),
                ],
                bend_radius=self.bend_radius,
            ),
        ]

        specs = instances + placement
        return specs
    
    def get_connector_instances(self):
        lv_instances = self.get_default_view(i3.LayoutView).instances
        return [
            lv_instances["fgc_1_opt1_to_dc_opt1"],
            lv_instances["fgc_2_opt1_to_dc_opt2"],
            lv_instances["dc_opt4_to_yb_1_opt1"],
            lv_instances["dc_opt3_to_yb_2_opt1"],
        ]

    def _default_exposed_ports(self):
        exposed_ports = {
                            "fgc_2:fib1": "in",
                            "fgc_1:fib1": "out",
        }
        return exposed_ports
    
    def annotate_trace_template(trace):
        return {"trace template": trace.trace_template.cell.__class__.__name__}

    class Layout(Layout_global):

        def __init__(self, text = "opt_in_TE_1550_Michelson", **kwargs):
            super().__init__(text, **kwargs)
            
class Michelson_TE1550_adiabatic(i3.Circuit):
    bend_radius = i3.PositiveNumberProperty(default=5.0, doc="Bend radius of the waveguides")
    fgc_spacing_y = i3.PositiveNumberProperty(default=127.0, doc="Spacing between the fiber grating couplers in the y-direction")
    fgc_dc_spacing = i3.PositiveNumberProperty(default=30.0, doc="Spacing between the fiber grating couplers in the y-direction")

    fgc = i3.ChildCellProperty(doc="PCell for the fiber grating coupler")
    splitter = i3.ChildCellProperty(doc="PCell for the Y-Branch")
    dir_coupler = i3.ChildCellProperty(doc="PCell for the directional coupler")

    delay_length = i3.PositiveNumberProperty(default=60.0, doc="length difference between the arms of the MZI")

    def _default_fgc(self):
        return pdk.EbeamGCTE1550()

    def _default_splitter(self):
        return pdk.EbeamY1550()

    def _default_dir_coupler(self):
        return pdk.EbeamAdiabaticTE1550()
    
    def _default_specs(self):
        instances = [
            i3.Inst(["fgc_1", "fgc_2"], self.fgc),
            i3.Inst("dc", self.dir_coupler),
            i3.Inst(["yb_1", "yb_2"], self.splitter),
        ]

        placement = [
            i3.Place("fgc_1", (0, 0)),
            i3.Place("fgc_2", (0, self.fgc_spacing_y)),
            i3.Place("dc", (self.fgc_dc_spacing, self.fgc_spacing_y * 0.1), angle=90),
            i3.FlipV("dc"),

            # mirror arms
            i3.Place("yb_1", (self.fgc_dc_spacing+self.bend_radius*4.5, self.fgc_spacing_y* 0.15+self.bend_radius), angle=-90),
            i3.Place("yb_2", (self.fgc_dc_spacing+self.bend_radius*2, self.fgc_spacing_y* 0.15+self.bend_radius), angle=-90),
            i3.ConnectManhattan(
                [
                    ("fgc_1:opt1", "dc:opt1", "fgc_1_opt1_to_dc_opt1"),
                    ("fgc_2:opt1", "dc:opt2", "fgc_2_opt1_to_dc_opt2"),
                    ("dc:opt3", "yb_2:opt1", "dc_opt3_to_yb_2_opt1",),
                    
                ],
                bend_radius=self.bend_radius,  # if this value is to big the manhattan connection will not be able to fit in the layout, if it is too small the connection will be very sharp and might cause losses. You can adjust this value to find a good balance between compactness and performance.
            ),

            # sensing arm
            i3.ConnectManhattan(
                "dc:opt4",
                "yb_1:opt1",
                "dc_opt4_to_yb_1_opt1",
            start_straight=10.0,  # add a straight section at the beginning of the connection to ensure that the waveguide is straight before it starts bending, this can help reduce losses and improve performance.
            control_points=[
                            i3.V(self.fgc_spacing_y * 0.5, flexible=True)
            ],
                match_path_length=i3.MatchLength(reference="dc_opt3_to_yb_2_opt1", delta=self.delay_length),
            ),

            # splitters loops
            i3.ConnectBend([
                            ("yb_1:opt2", "yb_1:opt3", "sensing_loop"), 
                            ("yb_2:opt2", "yb_2:opt3", "reference_loop"),
                ],
                bend_radius=self.bend_radius,
            ),
        ]

        specs = instances + placement
        return specs
    
    def get_connector_instances(self):
        lv_instances = self.get_default_view(i3.LayoutView).instances
        return [
            lv_instances["fgc_1_opt1_to_dc_opt1"],
            lv_instances["fgc_2_opt1_to_dc_opt2"],
            lv_instances["dc_opt4_to_yb_1_opt1"],
            lv_instances["dc_opt3_to_yb_2_opt1"],
        ]

    def _default_exposed_ports(self):
        exposed_ports = {
                            "fgc_2:fib1": "in",
                            "fgc_1:fib1": "out",
        }
        return exposed_ports
    
    
    def annotate_trace_template(trace):
        return {"trace template": trace.trace_template.cell.__class__.__name__}
    
    class Layout(Layout_global):

        def __init__(self, text = "opt_in_TE_1550_Michelson", **kwargs):
            super().__init__(text, **kwargs)

dut = Michelson_TE1550_adiabatic
dut = Michelson_TE1550
dut = Michelson_TE1550_wg
#%%
if __name__ == "__main__":

    # Create the MZI with a custom delay
    el_dut = dut(bend_radius=8.0, fgc_dc_spacing=40.0, delay_length=150.0, fgc_spacing_y=127.0)
    el_dut = dut(bend_radius=5.0, fgc_dc_spacing=25.0, delay_length=200.0, fgc_spacing_y=127.0)
    el_dut = dut(bend_radius=5.0, fgc_dc_spacing=25.0, delay_length=50.0, fgc_spacing_y=127.0)
    el_dut = dut(bend_radius=5.0, fgc_dc_spacing=25.0, delay_length=200.0, fgc_spacing_y=127.0)
    el_dut = dut(bend_radius=5.0, fgc_dc_spacing=25.0, delay_length=50.0, fgc_spacing_y=127.0)

    # Generate the layout
    dut_layout = el_dut.Layout()

    # Visualize
    dut_layout.visualize(annotate=True)

    dut_layout.write_gdsii("EBeam_NicolasCasteleyn_michelson_TE1550.gds")