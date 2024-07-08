from pathlib import PureWindowsPath

shimming_filepath = PureWindowsPath("../sinope_mimic/bin/shimsph.txt") 

def _write_currents_to_file(shim_currents: list[int]):
        with open(shimming_filepath, 'w', encoding='ascii') as f:
                # overwrite rest of file
            f.seek(0)
    
            # write currents to file
            for current in shim_currents:
                f.write(str(current))
                f.write("\n")

            # flush buffer to actually put currents in file.
            f.flush()

current = 0

while True:
    current = int(input())
    if current < 5000:
        shim_currents = [current for _ in range(1, 24)]
        _write_currents_to_file(shim_currents)
    else:
        print("Maximum current is 5000mA.")