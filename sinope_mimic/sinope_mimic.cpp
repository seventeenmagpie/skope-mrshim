// sinope_mimic.cpp
// this pretends to be the sinope shim coil driver software by calling
// ShimRealtime every iteration and writing the results to console if
// they are different to the previous values.
// this is sort of C-core because I know C first and also 
// the docs of real sinope say I have to use pointers rather than vectors.

#include <iostream>
#include "shimplugin.h"

#define NUM_CHANNELS 24

int main()
{
    //std::cout << "In main of SinopeMimic." << std::endl;

    int analog = 50;
    float* currents;  // points to the array of current shim currents
    float previous_currents [NUM_CHANNELS];  // used to store the first set of shim currents
    bool updated = false;  // flag for if currents have changed
    int i;

    // fills previous_currents with some non-garbage values.
    int number_of_channels = ShimRealtime(analog, &currents);
    for (i = 0; i != NUM_CHANNELS; ++i) {
        previous_currents[i] = currents[i];
    }

    while (true) {
        updated = false;

        // read in the currents from the ShimRealtime
        number_of_channels = ShimRealtime(analog, &currents);

        // goes over the new currents
        for (i = 0; i < number_of_channels; i++) {
            // compares to old currents. int conversion is because we are comparing
            // floats
            if ((int)(currents[i] * 1000) != (int)(previous_currents[i] * 1000)) {
                previous_currents[i] = currents[i];
                updated = true;
            }
        }

        // if the currents have changed, output it
        if (updated) {
            std::cout << "New currents are: ";
            for (i = 0; i < number_of_channels; i++) {
                std::cout << currents[i] << " ";
            }
            std::cout << std::endl;
        } 


        std::cout << "Press enter.";
        std::cin.get();
    }

    return 0;
}