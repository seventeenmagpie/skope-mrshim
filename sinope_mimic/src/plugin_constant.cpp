#pragma once
#ifdef __cplusplus
#ifdef _WIN32
#define EXTERN extern "C" __declspec(dllexport)
#else
#define EXTERN extern "C"
#endif
#else
#define EXTERN
#endif

#define NUM_CHANNELS 24
float shimValues[NUM_CHANNELS];  // array to store the current shim current values

EXTERN int ShimRealtime(float analogValue, float** output) {
	// custom code here

	for (int i = 0; i != NUM_CHANNELS; ++i) {
		shimValues[i] = 1;
	}

	// points to start of currents.
	*output = &(shimValues[0]);
	return NUM_CHANNELS;
}