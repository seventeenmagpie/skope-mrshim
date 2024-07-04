// sinope_mimic.cpp : This file contains the 'main' function. Program execution begins and ends there.
//

#include <iostream>
#include <sstream>
#include "shimplugin.h"

int main()
{
    //std::cout << "In main of SinopeMimic." << std::endl;

    int analog = 50;
    float* currents;
    float* prev_currents;
    bool updated = false;

    // this line is important because it pre-allocates prev_currents
    // otherwise it crashes when we try and read prev_currents[1]
    // which wouldn't exist.
    // we can't allocate it normally because we don't know how many 
    // channels there should be
    int number_of_channels = ShimRealtime(analog, &prev_currents);
    //if (prev_currents[4]) {
    //    std::cout << "prev_currents was populated" << std::endl;
    //}
    int i;

    while (analog <= 1000) {
        // read in the currents from the realtime device.
        updated = false;

        number_of_channels = ShimRealtime(analog, &currents);
        //if (currents[4]) {
        //    std::cout << "currents was populated" << std::endl;
        //}

        for (i = 0; i < number_of_channels; i++) {
            if ((int)(currents[i] * 1000) != (int)(prev_currents[i] * 1000)) {
                prev_currents[i] = currents[i];
                updated = true;
            }

        }

        if (updated) {
            std::cout << "New currents are: ";
            for (i = 0; i < number_of_channels; i++) {
                std::cout << currents[i] << " ";
            }
            std::cout << std::endl;
        } 
        //else {  // this loop goes very fast so this will spam.
        //    std::cout << "Currents did not change." << std::endl;
        //}

        std::cout << "Press enter." << std::endl;
        std::cin.get();
    }

    return 0;
}