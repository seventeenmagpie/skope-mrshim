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

EXTERN int ShimRealtime(float analogValue, float** output);