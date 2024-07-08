#include "shimplugin.h"
#include <iostream>  // for console writing
#include <fstream>  // for file writing
#include <sstream>  // string streams (conversion to integers)
#include <string>  // string data type

#define NUM_CHANNELS 24
float shimValues[NUM_CHANNELS];  // array to store the current shim current values

EXTERN int ShimRealtime(float analogValue, float** output) {
	// custom code here

	//std::cout << "ShimRealtime was called." << std::endl;

	std::string line;
	std::ifstream current_file;
	int this_current;

	// shimsph.txt should be a file with a list of shim currents in milliamps all
	// on their own lines.

	current_file.open("shimsph.txt", std::ifstream::in);

	if (current_file.is_open())
	{
		//std::cout << "shimsph.txt is open" << std::endl;
		for (int i = 0; i != NUM_CHANNELS; ++i) {
			getline(current_file, line);
			std::stringstream(line) >> this_current;
			shimValues[i] = ((float)this_current) / 1000;  // converts to a float of amps
		}
		current_file.close();
	}
	else {
		std::cout << "Unable to open file." << std::endl;
	}

	// points to start of currents.
	*output = &(shimValues[0]);
	return NUM_CHANNELS;
}
