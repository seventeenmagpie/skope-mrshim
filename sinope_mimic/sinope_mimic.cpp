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

    int number_of_channels = 0;
    int i;

    while (analog <= 1000) {
        // read in the currents from the realtime device.
        updated = false;

        number_of_channels = ShimRealtime(analog, &currents);

        std::cout << "Currents as recieved by sinope_mimic: ";

        for (i = 0; i < number_of_channels; i++) {
            std::cout << currents[i] << " ";
            if ((int) (currents[i]*1000) != (int) (prev_currents[i]*1000)) {
                prev_currents[i] = currents[i];
                updated = true;
            }
        }

        std::cout << std::endl;

        if (updated) {
            std::cout << "New currents are: ";
            for (i = 0; i < number_of_channels; i++) {
                std::cout << currents[i] << " ";
            }
            std::cout << std::endl;
        } else {  // this loop goes very fast so this will spam.
            std::cout << "Currents did not change." << std::endl;
        }
    }

    return 0;
}