#include "shimplugin.h"
#include <iostream>
#include <fstream>
#include <sstream>
#include <string>

#define NUM_CHANNELS 24
float shimValues[NUM_CHANNELS];
int i;

EXTERN int ShimRealtime(float analogValue, float** output) {
	// std::cout << "ShimRealtime was called." << std::endl;
	
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
		std::cout << "Currents read from file: ";

		// reads the first 24 lines from shimsph.tmp
		for ( i = 0; i != NUM_CHANNELS; ++i) {
			getline(current_file, line);
			std::stringstream(line) >> this_current;
			std::cout << this_current << " ";
			shimValues[i] = ((float) this_current) / 1000;
		}
		std::cout << std::endl;

		current_file.close();

		std::cout << "Currents in shimValues: " << std::endl;
		for (i = 0; i < NUM_CHANNELS; i++) {
			std::cout << shimValues[i] << " ";
		}
		std::cout << std::endl;

	}
	else {
		std::cout << "Unable to open file." << std::endl;
	}

	// do not change
	*output = &(shimValues[0]);

	// crashes here. don't know why.
	std::cout << "output[1] is " << *(output[1]) << std::endl;

	std::cout << "Checking contents of shimvalues vs output array: " << std::endl;
	for (i = 0; i < NUM_CHANNELS; i++) {
		std::cout << shimValues[i] << " vs ";
		std::cout << *(output[i]) << std::endl;
	}

	std::cout << std::endl;
	return NUM_CHANNELS;
}