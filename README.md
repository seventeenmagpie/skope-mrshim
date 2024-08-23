# Mags' 2024 Summer Project
---------------------------
This repository contains all the code and documentation I wrote for my 2024 summer project at the SPMIC at the University of Nottingham. This project was supervised by Prof. Richard Bowtell and Dr. Laura Bortolotti at the centre, and I also worked with Dr. Rashed Sobhan.

## Introduction
MRI scanning requires very uniform magnetic field in order to eliminate spurious signals (artefacts). The main factor affecting field homogeneity is motion, but this can be compensated by, for example, specialised k-space sampling trajectories. Another source is due to the differing magnetic susceptibilities of different parts of the body, which cause inhomogeneities which cannot be corrected during the scan. They can, however, be eliminated by using shim coils to create an additional magnetic field which is the opposite of the inhomogeneity. This usually requires taking a B0 map and calculating the necessary fields, and currents, from there. This takes a considerable amount of time and is specific to a particular field. If the field changes, the process, including the B0 map, needs to be repeated. This is not appropriate for fields which change during the scan --- for example a change in the amount of air in the lungs as in breath-hold scans or other physiological motion. This would require quicker, dynamic, shimming, which is what this project helps to implement.

It would be desireable to measure the magnetic field distribution in the imaging region without needing a time-consuming B0 map. The Skope field camera uses nuclear magnetic resonant free induction decay to provide a highly sensitive measure of the field at the probe. In previous work (Dr. Bortolotti and Prof. Bowtell) probes are positioned around the skull which are capable of measuring the field change due to breathing (or other physiological motion). We then assume that the field which created these signals can be described using low order spherical harmonics (IE, linear x, y and z) and that, furthermore, the field inside the imaging region is the same. Once the correct spherical harmonics are found which would create the measured field at the probes, the currents necessary for the shims to cancel out such a field (IE, produce its negative) are calculated. These are then applied.

## My Work
Previously this process was completed manually, and because the Skope and shims were controlled by different computers, was tedious and time consuming. My project was to automate the acquisition of skope data, calculation of corrective currents and the application of those currents. This repository contains the software I wrote to automate such a process, as well as the documentation and manuals I used in the process.

The main work is in the `./shimmer/` directory, which contains the code for a number of clients which can collect the Skope data, calculate the currents (`matlab\_client.m`), apply them (`mrshim_client.py`), and send controls (`console_client.py`). It also contains a server (`shimming_server.py`) which coordinates the transfer of data between them. Instructions on how to use the system are in the `./shimmer/docs/` directory.

`./manuals/` contains the documentation for the Skope system. There were a number of manuals which were all over the place, so I collected them here.

`./shimming_comparison/` contains code for comparing two B0 field maps to quantify the effect of the shimming.

## Get in touch
If you for some reason find this and do not already know what it is, you can contact me via GitHub, or reach out to my supervisors at the University, who can put you in touch with me.
