#ifndef COIN_SOINDEXEDFACESETFACEMATERIALTESTP_H
#define COIN_SOINDEXEDFACESETFACEMATERIALTESTP_H

#ifdef COIN_FACE_MATERIAL_TESTING
#include "SoIndexedFaceSetTestHooks.h"

class FaceMaterialTestProbe {
public:
  FaceMaterialTestProbe(void)
  {
    this->reset();
  }

  void reset(void)
  {
    state.lastStrategy = COIN_FACE_MATERIAL_TEST_UNKNOWN;
    state.unifiedCacheHits = 0;
    state.unifiedCacheBuilds = 0;
  }

  void recordStrategy(const FaceMaterialStrategy strategy)
  {
    switch (strategy) {
    case FACE_MATERIAL_FALLBACK:
      state.lastStrategy = COIN_FACE_MATERIAL_TEST_FALLBACK;
      break;
    case FACE_MATERIAL_OVERALL:
      state.lastStrategy = COIN_FACE_MATERIAL_TEST_OVERALL;
      break;
    case FACE_MATERIAL_GROUPED:
      state.lastStrategy = COIN_FACE_MATERIAL_TEST_GROUPED;
      break;
    case FACE_MATERIAL_UNIFIED:
      state.lastStrategy = COIN_FACE_MATERIAL_TEST_UNIFIED;
      break;
    default:
      state.lastStrategy = COIN_FACE_MATERIAL_TEST_UNKNOWN;
      break;
    }
  }

  void recordUnifiedCacheHit(void)
  {
    ++state.unifiedCacheHits;
  }

  void recordUnifiedCacheBuild(void)
  {
    ++state.unifiedCacheBuilds;
  }

  CoinFaceMaterialTestState getState(void) const
  {
    return state;
  }

private:
  CoinFaceMaterialTestState state;
};

#else

class FaceMaterialTestProbe {
public:
  void reset(void) {}
  void recordStrategy(const FaceMaterialStrategy) {}
  void recordUnifiedCacheHit(void) {}
  void recordUnifiedCacheBuild(void) {}
};

#endif // COIN_FACE_MATERIAL_TESTING

static FaceMaterialTestProbe faceMaterialTestProbe;

#endif // COIN_SOINDEXEDFACESETFACEMATERIALTESTP_H
