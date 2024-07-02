#include "shimplugin.h"
#include <iostream>

#define NUM_CHANNELS 24
float shimValues[NUM_CHANNELS];

EXTERN int ShimRealtime(float analogValue, float** output) {
	std::cout << "ShimRealtime was called.";

	// custom code here
	for (int i = 0; i != NUM_CHANNELS; ++i) {
		shimValues[i] = analogValue;
	}

	// do not change
	*output = &(shimValues[0]);
	return NUM_CHANNELS;
}