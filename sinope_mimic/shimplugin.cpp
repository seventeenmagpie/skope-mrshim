#include "shimplugin.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>

#define NUM_CHANNELS 24
float shimValues[NUM_CHANNELS];

EXTERN int ShimRealtime(float analogValue, float** output) {
	// custom code here

	std::cout << "ShimRealtime was called." << std::endl;

	std::string line;
	std::ifstream current_file;
	int this_current;

	// shimsph.tmp should be a file containing one set of currents
	// in milliamps
	// per line (channel)
	// lines past the number of channels are ignored.

	current_file.open("shimsph.txt", std::ifstream::in);

	if (current_file.is_open())
	{
		std::cout << "shimsph.txt is open" << std::endl;
		// reads the first 24 lines from shimsph.tmp
		for (int i = 0; i != NUM_CHANNELS; ++i) {
			getline(current_file, line);
			std::stringstream(line) >> this_current;
			shimValues[i] = ((float)this_current) / 1000;
		}
		current_file.close();
	}
	else {
		std::cout << "Unable to open file." << std::endl;
	}

	// do not change
	*output = &(shimValues[0]);
	return NUM_CHANNELS;
}