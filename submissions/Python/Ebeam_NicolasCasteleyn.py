import numpy as np
from Ebeam_NicolasCasteleyn_michelson_TE1550_pcell import Michelson_TE1550
from Ebeam_NicolasCasteleyn_waveguide_TE1550_tst_strct import waveguide_tst_structure as wg_tst_TE
from Ebeam_NicolasCasteleyn_michelson_TM1550_pcell import Michelson_TM1550_adiabatic as Michelson_TM1550
from Ebeam_NicolasCasteleyn_waveguide_TM1550_tst_strct import waveguide_tst_structure as wg_tst_TM
from siepic import all as pdk
from ipkiss3 import all as i3
import matplotlib.pyplot as plt
from scipy.signal import find_peaks
from ipkiss.technology import get_technology
TECH = get_technology()

# opt_in_TE_1550_device_NicolasCasteleyn_michelson1

# Parameters for the MZI sweep
enable_TE_line = True
enable_TM_line = False
enable_dummy = True
enable_plotting = False
visualize = True
delay_lengths = [50.0, 75.0, 100.0, 125.0, 150.0]  # Desired delay lengths in micrometers
delay_lengths_1 = [50.0, 75.0, 150.0, 100.0,][0]  # Desired delay lengths in micrometers
fgc_spacing_y = 127.0
bend_radius = 5.0
x0, y0 = 40.0, 15.0
x1, y1 = 75.0, y0 + fgc_spacing_y + 23.0  # Add some extra spacing between the MZI and the test structure
spacing_x = [100.0, 100.0, 100.0, 100.0, 85.0]
spacing_x1 = [130.0, 170.0, 170.0, 170.0, 0.0]  # Variable spacing for the TM MZIs to accommodate the test structure

insts = dict()
specs = []

# Create the floorplan
x_floorplan, y_floorplan = 605.0, 410.0
floorplan = pdk.FloorPlan(name="FLOORPLAN", size=(x_floorplan, y_floorplan))

# Add the floorplan to the instances dict and place it at (0.0, 0.0)
specs.append(i3.Inst("floorplan", floorplan))
specs.append(i3.Place("floorplan", (0.0, 0.0)))

#%%
# instance the test structure
wg_test_TE = wg_tst_TE(name="wg_tst_TE", bend_radius=bend_radius, fgc_spacing_y=fgc_spacing_y)
wg_test_TM = wg_tst_TM(name="wg_tst_TM", bend_radius=bend_radius, fgc_spacing_y=fgc_spacing_y)

# Add the test structure to the instances dict and place it
if enable_dummy:
    dummy_name = f"wg_test_TM"
    specs.append(i3.Inst(dummy_name, wg_test_TM))
    # specs.append(i3.Place(dummy_name, (x_floorplan-50, y1)))
    specs.append(i3.Place(dummy_name, (263, y1+65)))
    # specs.append(i3.FlipH(dummy_name))

#%%
# Create the MZI sweep
if enable_TE_line:
    for ind, delay_length in enumerate(delay_lengths):

        # Instantiate the MZI
        mzi = Michelson_TE1550(
            name=f"opt_in_TE_1550_Michelson_{ind}",
            fgc_spacing_y=fgc_spacing_y,
            bend_radius=bend_radius,
            delay_length=delay_length,
        )

        # Calculate the actual delay length and print the results
        right_arm_length = mzi.get_connector_instances()[1].reference.trace_length()
        left_arm_length = mzi.get_connector_instances()[0].reference.trace_length()
        actual_delay_length = right_arm_length - left_arm_length

        print(mzi.name, f"Desired delay length = {delay_length} um", f"Actual delay length = {actual_delay_length} um")

        # Add the MZI to the instances dict and place it
        mzi_cell_name = f"michelsonTE1550_{ind}"
        specs.append(i3.Inst(mzi_cell_name, mzi))
        specs.append(i3.Place(mzi_cell_name, (x0, y0)))

        x0 += spacing_x[ind]
if enable_TM_line:
    for ind, delay_length in enumerate(delay_lengths_1):

        # Instantiate the MZI
        mzi = Michelson_TM1550(
            name=f"MichelsonTM1550_{ind}",
            fgc_spacing_y=fgc_spacing_y,
            bend_radius=bend_radius,
            delay_length=delay_length,
        )

        # Calculate the actual delay length and print the results
        right_arm_length = mzi.get_connector_instances()[1].reference.trace_length()
        left_arm_length = mzi.get_connector_instances()[0].reference.trace_length()
        actual_delay_length = right_arm_length - left_arm_length

        print(mzi.name, f"Desired delay length = {delay_length} um", f"Actual delay length = {actual_delay_length} um")

        # Add the MZI to the instances dict and place it
        mzi_cell_name = f"michelsonTM1550_{ind}"
        specs.append(i3.Inst(mzi_cell_name, mzi))
        specs.append(i3.Place(mzi_cell_name, (x1, y1)))

        x1 += spacing_x1[ind]

wg_test_TE_name = f"wg_test_TE"
specs.append(i3.Inst(wg_test_TE_name, wg_test_TE))
specs.append(i3.Place(wg_test_TE_name, (x0+30, y0+5)))
# specs.append(i3.Place(dummy_name, (x0, y0+5)))


# Create the final design with i3.Circuit
circuit_name="EBeam_NicolasCasteleyn_v2"
cell = i3.Circuit(
    name=circuit_name,
    specs=specs,
)

# Layout
cell_lv = cell.Layout()
if visualize:
    cell_lv.visualize(annotate=False)
cell_lv.write_gdsii(f"{circuit_name}.gds")

# Circuit model
cell_cm = cell.CircuitModel()
wavelengths = np.linspace(1.52, 1.58, 4001)
S_total = cell_cm.get_smatrix(wavelengths=wavelengths)

if __name__ == "__main__":
    # Plotting
    if enable_plotting:

        FSR_buffer = []

        for ind, delay_length in enumerate(delay_lengths):
            if visualize:
                S_total.visualize(
                    term_pairs=[(f"michelson{ind}_in:0", f"michelson{ind}_out:0")],
                    title=f"MZI{ind} - Delay length {delay_length} um",
                    scale="dB",
                )

            transmission = i3.signal_power_dB(S_total[f"michelson{ind}_in:0", f"michelson{ind}_out:0"])
            
            ## PLOT TRANSMISSION
            plt.figure(num=1,figsize=(8, 6))
            plt.plot(wavelengths, transmission, label=f"delay_length = {delay_length} um")   
            plt.xlabel("Wavelength (μm)")
            plt.ylabel("Power (dB)")
            plt.title("MZI Transmission")
            plt.grid()
            plt.legend()

            peaks, _ = find_peaks(transmission)
            peak_wavelengths = wavelengths[peaks]

            ## Calculate FSR
            fsr = np.diff(peak_wavelengths)
            fsr_mean = np.mean(fsr)
            # print(f"FSR: {fsr_mean*1e3} nm")
            FSR_buffer.append(fsr_mean*1e3)

        plt.savefig("C:\\Users\\admin\\OneDrive - UPV\\EDX_140425\\EDX_140425\\edx\\2_fabrication\\michelson_spectrums_vs_delay_length.png")
        print("FSR_buffer:", FSR_buffer)
        
        ## PLOT FSR vs Delay Length
        plt.figure(num=2,figsize=(8, 6))
        plt.plot(delay_lengths, FSR_buffer, "o-")
        [plt.annotate('(%.2f, %.2f)' % (delay_lengths[i], FSR_buffer[i]), xy=(delay_lengths[i], FSR_buffer[i])) for i in range(len(delay_lengths))]
        plt.xlabel("Delay Length (um)")
        plt.ylabel("FSR (nm)")
        plt.title("FSR vs Delay Length")
        plt.grid()
        plt.savefig("C:\\Users\\admin\\OneDrive - UPV\\EDX_140425\\EDX_140425\\edx\\2_fabrication\\michelson_dsn_fsr_vs_delay_length.png")

    print("Done")