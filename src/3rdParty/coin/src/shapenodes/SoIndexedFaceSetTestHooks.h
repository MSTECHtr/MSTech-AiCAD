#ifndef COIN_SOINDEXEDFACESET_TEST_HOOKS_H
#define COIN_SOINDEXEDFACESET_TEST_HOOKS_H

#ifdef COIN_FACE_MATERIAL_TESTING

// Internal interface compiled only for Coin's face-material tests. This is
// deliberately not part of the public Coin API or normal renderer builds.
#include <Inventor/C/basic.h>

#include <cstdint>

enum CoinFaceMaterialTestStrategy {
  COIN_FACE_MATERIAL_TEST_UNKNOWN = 0,
  COIN_FACE_MATERIAL_TEST_FALLBACK,
  COIN_FACE_MATERIAL_TEST_OVERALL,
  COIN_FACE_MATERIAL_TEST_GROUPED,
  COIN_FACE_MATERIAL_TEST_UNIFIED
};

struct CoinFaceMaterialTestState {
  CoinFaceMaterialTestStrategy lastStrategy;
  uint64_t unifiedCacheHits;
  uint64_t unifiedCacheBuilds;
};

COIN_DLL_API void coinResetFaceMaterialTestState(void);
COIN_DLL_API CoinFaceMaterialTestState coinGetFaceMaterialTestState(void);

#endif // COIN_FACE_MATERIAL_TESTING

#endif // COIN_SOINDEXEDFACESET_TEST_HOOKS_H
