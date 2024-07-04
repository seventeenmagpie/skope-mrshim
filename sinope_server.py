from pathlib import PureWindowsPath

# path to shim current file, ensure is in the same directory as shimplugin.dll
p = PureWindowsPath("../sinope_mimic/bin/shimsph.txt")  
file_handle = open(p, 'w', encoding ="ascii")

factor = 4

while (factor != 0):
    factor = int(input())

    # overwrite rest of file
    file_handle.seek(0)
    
    # write currents to file
    for i in range(1, 24):
        file_handle.write(str(factor*i))
        file_handle.write("\n")

    # flush buffer to actually put currents in file.
    file_handle.flush()

file_handle.close()