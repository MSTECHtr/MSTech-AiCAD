#ifndef COIN_SOINDEXEDFACESETFACEMATERIALP_H
#define COIN_SOINDEXEDFACESETFACEMATERIALP_H

#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>

#include <Inventor/SbVec3f.h>
#include <Inventor/system/gl.h>

#include "tidbitsp.h"

class SoCoordinateElement;
class SoGLRenderAction;
class SoLazyElement;
class SoMaterialBundle;
class SoState;
class SoVBO;
class SoVertexArrayIndexer;

// These types are private to SoIndexedFaceSet. They live in a separate
// internal header so the node implementation can focus on state collection
// and render dispatch.

enum FaceMaterialStrategy {
  FACE_MATERIAL_AUTO,
  FACE_MATERIAL_FALLBACK,
  FACE_MATERIAL_OVERALL,
  FACE_MATERIAL_GROUPED,
  FACE_MATERIAL_UNIFIED
};

struct FaceMaterialRenderState {
  SbBool opaque;
  FaceMaterialStrategy strategy;
  int representative;
  SbBool vertexArraysReady;

  FaceMaterialRenderState(void)
    : opaque(TRUE),
      strategy(FACE_MATERIAL_GROUPED),
      representative(0),
      vertexArraysReady(FALSE)
  {
  }
};

struct FaceMaterialSettings {
  int maximumGroups;
  int minimumTrianglesPerGroup;
  int minimumUnifiedTriangles;
  uint64_t maximumUnifiedBytes;
  FaceMaterialStrategy strategy;

  static int positiveInteger(const char * name, const int fallback)
  {
    const char * value = std::getenv(name);
    if (!value || !value[0]) return fallback;
    const int parsed = std::atoi(value);
    return parsed > 0 ? parsed : fallback;
  }

  static uint64_t byteLimit(const char * name, const uint64_t fallback)
  {
    const char * value = std::getenv(name);
    if (!value || !value[0]) return fallback;
    const uint64_t parsed = static_cast<uint64_t>(std::strtoull(value, NULL, 10));
    return parsed > 0 ? parsed : fallback;
  }

  static FaceMaterialStrategy parseStrategy()
  {
    const char * value = std::getenv("COIN_FACE_MATERIAL_STRATEGY");
    if (!value || !value[0]) return FACE_MATERIAL_GROUPED;
    if (std::strcmp(value, "auto") == 0) return FACE_MATERIAL_AUTO;
    if (std::strcmp(value, "overall") == 0) return FACE_MATERIAL_OVERALL;
    if (std::strcmp(value, "grouped") == 0) return FACE_MATERIAL_GROUPED;
    if (std::strcmp(value, "unified") == 0) return FACE_MATERIAL_UNIFIED;
    if (std::strcmp(value, "fallback") == 0) return FACE_MATERIAL_FALLBACK;
    return FACE_MATERIAL_GROUPED;
  }

  static FaceMaterialSettings fromEnvironment()
  {
    FaceMaterialSettings settings;
    settings.maximumGroups =
      positiveInteger("COIN_FACE_MATERIAL_MAX_GROUPS", 8);
    settings.minimumTrianglesPerGroup =
      positiveInteger("COIN_FACE_MATERIAL_MIN_TRIANGLES_PER_GROUP", 32);
    settings.minimumUnifiedTriangles =
      positiveInteger("COIN_FACE_MATERIAL_MIN_UNIFIED_TRIANGLES", 512);
    settings.maximumUnifiedBytes =
      byteLimit("COIN_FACE_MATERIAL_MAX_UNIFIED_BYTES", 64ULL * 1024ULL * 1024ULL);
    settings.strategy = parseStrategy();
    return settings;
  }
};

inline const FaceMaterialSettings & faceMaterialSettings()
{
  static const FaceMaterialSettings settings =
    FaceMaterialSettings::fromEnvironment();
  return settings;
}

struct FaceMaterialGeometry {
  const SoCoordinateElement *coordinates;
  const SbVec3f *normals;
  int normalCount;
  const int32_t *coordIndices;
  int numCoordIndices;
  const int32_t *normalIndices;
  const int32_t *materialIndices;
  int numMaterialIndices;
  SbUniqueId coordinateNodeId;
  SbUniqueId normalNodeId;
  SbUniqueId shapeNodeId;
  SbBool hasNormals;
};

struct FaceMaterialRenderInput {
  const SoLazyElement *materialElement;
  FaceMaterialGeometry geometry;
  SbBool doTextures;
  SbBool doAttributes;
  SbBool coordinatesAre3D;
  SbBool prepareVertexArrays;
};

// SoPackedColor swaps packed RGBA bytes before exposing them as a GL byte
// array. Keep the unified path consistent with that established convention.
inline uint32_t packedColorForVertexArray(const uint32_t color)
{
  if (coin_host_get_endianness() == COIN_HOST_IS_BIGENDIAN) {
    return color;
  }

  return (color << 24) |
         ((color & 0xff00) << 8) |
         ((color & 0xff0000) >> 8) |
         (color >> 24);
}

// A unified vertex is shared only when all indexed attributes represented by
// this path agree. Textures and custom attributes currently reject the path,
// so coordinate, normal, and logical (pre-endian-swap) color are sufficient.
struct UnifiedVertexKey {
  int coordindex;
  int normalindex;
  uint32_t color;

  bool operator<(const UnifiedVertexKey& other) const {
    if (coordindex != other.coordindex) return coordindex < other.coordindex;
    if (normalindex != other.normalindex) return normalindex < other.normalindex;
    return color < other.color;
  }
};

// Presents the separator-delimited coordIndex stream as validated face
// records. All face-material builders use this iterator so they agree on
// face boundaries and material-index advancement.
struct FaceMaterialFace {
  const int32_t *coordIndices;
  int indexOffset;
  int count;
  int materialIndex;
};

class FaceMaterialFaceIterator {
public:
  FaceMaterialFaceIterator(const int32_t *coordIndices,
                           const int coordIndexCount,
                           const int32_t *materialIndices,
                           const int materialIndexCount)
    : coordIndices(coordIndices),
      coordIndexCount(coordIndexCount),
      materialIndices(materialIndices),
      materialIndexCount(materialIndexCount),
      nextIndex(0),
      nextMaterial(0),
      valid(coordIndices != NULL && materialIndices != NULL &&
            coordIndexCount > 0 && materialIndexCount > 0)
  {
  }

  bool next(FaceMaterialFace &face)
  {
    while (nextIndex < coordIndexCount && coordIndices[nextIndex] < 0) {
      ++nextIndex;
    }
    if (nextIndex >= coordIndexCount) return false;

    const int start = nextIndex;
    while (nextIndex < coordIndexCount && coordIndices[nextIndex] >= 0) {
      ++nextIndex;
    }

    if (nextMaterial >= materialIndexCount) {
      valid = false;
      return false;
    }

    face.coordIndices = coordIndices + start;
    face.indexOffset = start;
    face.count = nextIndex - start;
    face.materialIndex = materialIndices[nextMaterial++];
    return true;
  }

  bool isValid() const
  {
    return valid;
  }

private:
  const int32_t *coordIndices;
  int coordIndexCount;
  const int32_t *materialIndices;
  int materialIndexCount;
  int nextIndex;
  int nextMaterial;
  bool valid;
};

class FaceMaterialRenderer {
public:
  FaceMaterialRenderer(void);
  ~FaceMaterialRenderer(void);

  FaceMaterialRenderer(const FaceMaterialRenderer &) = delete;
  FaceMaterialRenderer & operator=(const FaceMaterialRenderer &) = delete;

  void invalidateFaceMaterialCaches(void);

  FaceMaterialRenderState prepare(const FaceMaterialRenderInput &input);

  SbBool renderUnifiedFaceMaterial(SoGLRenderAction *action,
                                   SoState *state,
                                   uint32_t contextid);

  void renderGroupedFaceMaterial(SoMaterialBundle &materials,
                                 SoState *state,
                                 SbBool useVBO,
                                 uint32_t contextid);

private:
  class Impl;
  std::unique_ptr<Impl> impl;
};

#endif // COIN_SOINDEXEDFACESETFACEMATERIALP_H
