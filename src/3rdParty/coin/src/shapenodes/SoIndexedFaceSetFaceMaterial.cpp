/* Private implementation of Coin's adaptive face-material renderer. */

#include <cstdint>
#include <map>
#include <memory>
#include <vector>

#include <Inventor/SbColor.h>
#include <Inventor/SbVec3f.h>
#include <Inventor/actions/SoGLRenderAction.h>
#include <Inventor/bundles/SoMaterialBundle.h>
#include <Inventor/elements/SoCoordinateElement.h>
#include <Inventor/elements/SoGLLazyElement.h>
#include <Inventor/elements/SoGLVertexAttributeElement.h>
#include <Inventor/elements/SoLazyElement.h>
#include <Inventor/misc/SoState.h>
#include <Inventor/system/gl.h>

#include "SoIndexedFaceSetFaceMaterialP.h"
#include "SoIndexedFaceSetFaceMaterialTestP.h"
#include "rendering/SoGL.h"
#include "rendering/SoVBO.h"
#include "rendering/SoVertexArrayIndexer.h"

#ifdef COIN_FACE_MATERIAL_TESTING
COIN_DLL_API void coinResetFaceMaterialTestState(void)
{
  faceMaterialTestProbe.reset();
}

COIN_DLL_API CoinFaceMaterialTestState coinGetFaceMaterialTestState(void)
{
  return faceMaterialTestProbe.getState();
}
#endif

struct FaceMaterialAnalysisKey {
  const int32_t *coordIndices;
  const int32_t *materialIndices;
  int numCoordIndices;
  int numMaterialIndices;
  int numColors;
  uint64_t colorHash;
  SbUniqueId shapeNodeId;

  bool operator==(const FaceMaterialAnalysisKey &other) const
  {
    return coordIndices == other.coordIndices &&
      materialIndices == other.materialIndices &&
      numCoordIndices == other.numCoordIndices &&
      numMaterialIndices == other.numMaterialIndices &&
      numColors == other.numColors &&
      colorHash == other.colorHash &&
      shapeNodeId == other.shapeNodeId;
  }
};

struct FaceMaterialGroupedKey {
  const int32_t *coordIndices;
  const int32_t *materialIndices;
  int numCoordIndices;
  int numColors;
  uint64_t colorHash;
  SbUniqueId shapeNodeId;

  bool operator==(const FaceMaterialGroupedKey &other) const
  {
    return coordIndices == other.coordIndices &&
      materialIndices == other.materialIndices &&
      numCoordIndices == other.numCoordIndices &&
      numColors == other.numColors &&
      colorHash == other.colorHash &&
      shapeNodeId == other.shapeNodeId;
  }
};

struct FaceMaterialUnifiedKey {
  const SbVec3f *coordinatePointer;
  const SbVec3f *normalPointer;
  SbUniqueId coordinateNodeId;
  SbUniqueId normalNodeId;
  SbUniqueId shapeNodeId;
  const int32_t *coordIndices;
  const int32_t *normalIndices;
  const int32_t *materialIndices;
  const uint32_t *colorsPointer;
  int numCoordIndices;
  int coordinateCount;
  int numColors;
  int normalCount;
  uint64_t colorHash;
  SbBool hasNormals;

  bool operator==(const FaceMaterialUnifiedKey &other) const
  {
    return coordinatePointer == other.coordinatePointer &&
      normalPointer == other.normalPointer &&
      coordinateNodeId == other.coordinateNodeId &&
      normalNodeId == other.normalNodeId &&
      shapeNodeId == other.shapeNodeId &&
      coordIndices == other.coordIndices &&
      normalIndices == other.normalIndices &&
      materialIndices == other.materialIndices &&
      colorsPointer == other.colorsPointer &&
      numCoordIndices == other.numCoordIndices &&
      coordinateCount == other.coordinateCount &&
      numColors == other.numColors &&
      normalCount == other.normalCount &&
      colorHash == other.colorHash &&
      hasNormals == other.hasNormals;
  }
};


// Private implementation of the adaptive face-material renderer. The public
// node only collects Coin state and dispatches to this owner.

class FaceMaterialRenderer::Impl {
public:
  Impl(void)
  {
    unifiedMaterialKey = FaceMaterialUnifiedKey();
    unifiedMaterialHasNormals = FALSE;
    unifiedMaterialReady = FALSE;

    faceMaterialGroupedKey = FaceMaterialGroupedKey();
    faceMaterialNumColors = 0;
    faceMaterialColorHash = 0;
    faceMaterialPackedPointer = NULL;
    faceMaterialDiffusePointer = NULL;
    faceMaterialTransparencyPointer = NULL;
    faceMaterialNumTransparencies = 0;
    faceMaterialDiffuseNodeId = 0;
    faceMaterialTransparencyNodeId = 0;
    faceMaterialPacked = FALSE;
    faceMaterialOpaque = TRUE;
    this->clearFaceMaterialAnalysis();
  }

  ~Impl(void)
  {
    this->clearFaceMaterialIndexers();
    this->clearUnifiedFaceMaterialData();
  }

private:
  std::vector<std::unique_ptr<SoVertexArrayIndexer> > faceMaterialIndexers;
  std::vector<int> faceMaterialRepresentatives;
  std::vector<SbVec3f> unifiedMaterialCoords;
  std::vector<SbVec3f> unifiedMaterialNormals;
  std::vector<uint32_t> unifiedMaterialColors;
  std::vector<GLint> unifiedMaterialIndices;
  std::unique_ptr<SoVBO> unifiedMaterialCoordVBO;
  std::unique_ptr<SoVBO> unifiedMaterialNormalVBO;
  std::unique_ptr<SoVBO> unifiedMaterialColorVBO;
  std::unique_ptr<SoVBO> unifiedMaterialIndexVBO;
  FaceMaterialUnifiedKey unifiedMaterialKey;
  SbBool unifiedMaterialHasNormals;
  SbBool unifiedMaterialReady;
  FaceMaterialGroupedKey faceMaterialGroupedKey;
  int faceMaterialNumColors;
  uint64_t faceMaterialColorHash;
  std::vector<uint32_t> faceMaterialColors;
  const uint32_t * faceMaterialPackedPointer;
  const SbColor * faceMaterialDiffusePointer;
  const float * faceMaterialTransparencyPointer;
  int faceMaterialNumTransparencies;
  SbUniqueId faceMaterialDiffuseNodeId;
  SbUniqueId faceMaterialTransparencyNodeId;
  SbBool faceMaterialPacked;
  SbBool faceMaterialOpaque;
  // Analysis describes only materials referenced by the current face set.
  // It is separate from the extracted material array and from built groups so
  // each cache has an unambiguous invalidation key.
  FaceMaterialAnalysisKey faceMaterialAnalysisKey;
  SbBool faceMaterialAnalysisReady;
  SbBool faceMaterialAnalysisValid;
  SbBool faceMaterialAnalysisUniform;
  int faceMaterialAnalysisRepresentative;
  int faceMaterialAnalysisDistinctColorCount;
  uint64_t faceMaterialAnalysisTriangles;
  uint64_t faceMaterialAnalysisCorners;

private:
  void clearFaceMaterialAnalysis(void) {
    faceMaterialAnalysisKey = FaceMaterialAnalysisKey();
    faceMaterialAnalysisReady = FALSE;
    faceMaterialAnalysisValid = FALSE;
    faceMaterialAnalysisUniform = FALSE;
    faceMaterialAnalysisRepresentative = -1;
    faceMaterialAnalysisDistinctColorCount = 0;
    faceMaterialAnalysisTriangles = 0;
    faceMaterialAnalysisCorners = 0;
  }

  void clearUnifiedFaceMaterialData(void) {
    unifiedMaterialCoordVBO.reset();
    unifiedMaterialNormalVBO.reset();
    unifiedMaterialColorVBO.reset();
    unifiedMaterialIndexVBO.reset();
    unifiedMaterialCoords.clear();
    unifiedMaterialNormals.clear();
    unifiedMaterialColors.clear();
    unifiedMaterialIndices.clear();
    unifiedMaterialKey = FaceMaterialUnifiedKey();
    unifiedMaterialHasNormals = FALSE;
    unifiedMaterialReady = FALSE;
  }

  void clearFaceMaterialIndexers(void) {
    faceMaterialIndexers.clear();
    faceMaterialRepresentatives.clear();
    faceMaterialGroupedKey = FaceMaterialGroupedKey();
  }

public:
  void invalidateFaceMaterialCaches(void) {
    this->clearFaceMaterialAnalysis();
    this->clearFaceMaterialIndexers();
    this->clearUnifiedFaceMaterialData();
  }

private:
  // Validate the face/material mapping and cache the inputs used by the
  // adaptive selector. The result is keyed by source pointers, node ID,
  // lengths, and the logical material-color hash.
  SbBool analyzeFaceMaterials(const int32_t * coordindices,
                              const int numcoordindices,
                              const int32_t * materialindices,
                              const int nummaterialindices,
                              const SbUniqueId shapeNodeId,
                              const std::vector<uint32_t>& materialcolors,
                              const uint64_t materialcolorhash) {
    const FaceMaterialAnalysisKey key = {
      coordindices,
      materialindices,
      numcoordindices,
      nummaterialindices,
      static_cast<int>(materialcolors.size()),
      materialcolorhash,
      shapeNodeId
    };
    if (faceMaterialAnalysisReady && faceMaterialAnalysisKey == key) {
      return faceMaterialAnalysisValid;
    }

    faceMaterialAnalysisKey = key;
    faceMaterialAnalysisReady = TRUE;
    faceMaterialAnalysisValid = FALSE;
    faceMaterialAnalysisUniform = FALSE;
    faceMaterialAnalysisRepresentative = -1;
    faceMaterialAnalysisDistinctColorCount = 0;
    faceMaterialAnalysisTriangles = 0;
    faceMaterialAnalysisCorners = 0;

    if (!coordindices || !materialindices || numcoordindices <= 0 ||
        nummaterialindices <= 0 || materialcolors.empty()) {
      return FALSE;
    }

    std::map<uint32_t, uint64_t> colorTriangles;
    FaceMaterialFaceIterator faces(
      coordindices, numcoordindices, materialindices, nummaterialindices);
    FaceMaterialFace faceData;
    int face = 0;
    while (faces.next(faceData)) {
      if (faceData.count < 3 ||
          faceData.materialIndex < 0 ||
          faceData.materialIndex >= static_cast<int>(materialcolors.size())) {
        return FALSE;
      }

      if (face == 0) {
        faceMaterialAnalysisRepresentative = faceData.materialIndex;
      }

      const uint64_t triangles = static_cast<uint64_t>(faceData.count - 2);
      const uint32_t color = materialcolors[faceData.materialIndex];
      colorTriangles[color] += triangles;
      faceMaterialAnalysisTriangles += triangles;
      faceMaterialAnalysisCorners += static_cast<uint64_t>(faceData.count);
      ++face;
    }

    if (!faces.isValid() || face == 0 || colorTriangles.empty()) {
      return FALSE;
    }

    faceMaterialAnalysisValid = TRUE;
    faceMaterialAnalysisDistinctColorCount = static_cast<int>(colorTriangles.size());
    faceMaterialAnalysisUniform = colorTriangles.size() == 1;
    return TRUE;
  }

  // Choose a fast path only for opaque, valid material data. Unsupported
  // inputs deliberately return FALLBACK so the existing renderer retains
  // ownership of texture, attribute, transparency, and unusual-topology
  // semantics.
  FaceMaterialStrategy chooseFaceMaterialStrategy(const SbBool doTextures,
                                                  const SbBool doattribs,
                                                  const SbBool coordinatesAre3D) const {
    if (!faceMaterialAnalysisValid || !faceMaterialOpaque) {
      return FACE_MATERIAL_FALLBACK;
    }

    const FaceMaterialSettings &settings = faceMaterialSettings();
    const FaceMaterialStrategy overrideStrategy = settings.strategy;
    if (overrideStrategy == FACE_MATERIAL_OVERALL) {
      return faceMaterialAnalysisUniform ? FACE_MATERIAL_OVERALL : FACE_MATERIAL_FALLBACK;
    }
    if (overrideStrategy == FACE_MATERIAL_GROUPED ||
        overrideStrategy == FACE_MATERIAL_FALLBACK) {
      return overrideStrategy;
    }
    if (overrideStrategy == FACE_MATERIAL_UNIFIED) {
      return (!doTextures && !doattribs && coordinatesAre3D)
        ? FACE_MATERIAL_UNIFIED : FACE_MATERIAL_FALLBACK;
    }

    const int distinctColors = faceMaterialAnalysisDistinctColorCount;
    const uint64_t triangles = faceMaterialAnalysisTriangles;
    const uint64_t estimatedUnifiedBytes =
      faceMaterialAnalysisCorners *
        (2ULL * sizeof(SbVec3f) + sizeof(uint32_t)) +
      triangles * 3ULL * sizeof(GLint);
    const uint64_t averageTriangles = distinctColors > 0
      ? triangles / static_cast<uint64_t>(distinctColors) : 0;
    if (distinctColors <= settings.maximumGroups &&
        averageTriangles >= static_cast<uint64_t>(
          settings.minimumTrianglesPerGroup)) {
      return FACE_MATERIAL_GROUPED;
    }
    if (!doTextures && !doattribs && coordinatesAre3D &&
        distinctColors > 1 &&
        triangles >= static_cast<uint64_t>(
          settings.minimumUnifiedTriangles) &&
        estimatedUnifiedBytes <= settings.maximumUnifiedBytes) {
      return FACE_MATERIAL_UNIFIED;
    }
    return FACE_MATERIAL_FALLBACK;
  }

public:
  FaceMaterialRenderState prepare(const FaceMaterialRenderInput &input) {
    FaceMaterialRenderState renderState;
    const FaceMaterialGeometry &geometry = input.geometry;

    this->updateFaceMaterialColors(input.materialElement);
    renderState.opaque = faceMaterialOpaque;

    const SbBool analysisValid = this->analyzeFaceMaterials(
      geometry.coordIndices,
      geometry.numCoordIndices,
      geometry.materialIndices,
      geometry.numMaterialIndices,
      geometry.shapeNodeId,
      faceMaterialColors,
      faceMaterialColorHash);
    if (analysisValid && faceMaterialAnalysisUniform && renderState.opaque) {
      renderState.strategy = FACE_MATERIAL_OVERALL;
    }
    else {
      renderState.strategy = this->chooseFaceMaterialStrategy(
        input.doTextures,
        input.doAttributes,
        input.coordinatesAre3D);
    }

    if (input.prepareVertexArrays) {
      if (renderState.strategy == FACE_MATERIAL_GROUPED) {
        renderState.vertexArraysReady = this->prepareFaceMaterialIndexers(geometry);
      }
      else if (renderState.strategy == FACE_MATERIAL_UNIFIED) {
        renderState.vertexArraysReady = this->prepareUnifiedFaceMaterialData(geometry);
      }

      if ((renderState.strategy == FACE_MATERIAL_GROUPED ||
           renderState.strategy == FACE_MATERIAL_UNIFIED) &&
          !renderState.vertexArraysReady) {
        renderState.strategy = FACE_MATERIAL_FALLBACK;
      }
    }

    renderState.representative = faceMaterialAnalysisRepresentative;
    faceMaterialTestProbe.recordStrategy(renderState.strategy);
    return renderState;
  }

private:
  SbBool updateFaceMaterialColors(const SoLazyElement * materialElement) {
    const SbBool packed = materialElement->isPacked();
    const uint32_t * packedPointer = packed ? materialElement->getPackedPointer() : NULL;
    const SbColor * diffusePointer = packed ? NULL : materialElement->getDiffusePointer();
    const float * transparencyPointer = materialElement->getTransparencyPointer();
    const int numcolors = materialElement->getNumDiffuse();
    const int numtransparencies = materialElement->getNumTransparencies();
    const SbUniqueId diffuseNodeId = materialElement->getDiffuseNodeId();
    const SbUniqueId transparencyNodeId = materialElement->getTransparencyNodeId();
    const SbBool opaque = !materialElement->isTransparent();

    if (packed == faceMaterialPacked &&
        packedPointer == faceMaterialPackedPointer &&
        diffusePointer == faceMaterialDiffusePointer &&
        transparencyPointer == faceMaterialTransparencyPointer &&
        numcolors == faceMaterialNumColors &&
        numtransparencies == faceMaterialNumTransparencies &&
        diffuseNodeId == faceMaterialDiffuseNodeId &&
        transparencyNodeId == faceMaterialTransparencyNodeId &&
        opaque == faceMaterialOpaque) {
      return TRUE;
    }

    faceMaterialPacked = packed;
    faceMaterialPackedPointer = packedPointer;
    faceMaterialDiffusePointer = diffusePointer;
    faceMaterialTransparencyPointer = transparencyPointer;
    faceMaterialNumColors = numcolors;
    faceMaterialNumTransparencies = numtransparencies;
    faceMaterialDiffuseNodeId = diffuseNodeId;
    faceMaterialTransparencyNodeId = transparencyNodeId;
    faceMaterialOpaque = opaque;
    faceMaterialColorHash = 1469598103934665603ULL;
    faceMaterialColors.clear();
    faceMaterialColors.resize(numcolors);

    if (packed) {
      for (int i = 0; i < numcolors; ++i) {
        faceMaterialColors[i] = packedPointer[i];
      }
    }
    else {
      const int transparencyCount = numtransparencies;
      for (int i = 0; i < numcolors; ++i) {
        const float trans = (transparencyPointer && transparencyCount > 0)
          ? transparencyPointer[i < transparencyCount ? i : transparencyCount - 1]
          : 0.0f;
        faceMaterialColors[i] = diffusePointer[i].getPackedValue(trans);
      }
    }

    for (std::vector<uint32_t>::const_iterator it = faceMaterialColors.begin();
         it != faceMaterialColors.end(); ++it) {
      faceMaterialColorHash ^= static_cast<uint64_t>(*it);
      faceMaterialColorHash *= 1099511628211ULL;
    }
    return FALSE;
  }

public:
  SbBool prepareFaceMaterialIndexers(const FaceMaterialGeometry &geometry) {
    const FaceMaterialGroupedKey key = {
      geometry.coordIndices,
      geometry.materialIndices,
      geometry.numCoordIndices,
      static_cast<int>(faceMaterialColors.size()),
      faceMaterialColorHash,
      geometry.shapeNodeId
    };
    if (faceMaterialIndexers.size() > 0 && faceMaterialGroupedKey == key) {
      return faceMaterialIndexers.empty() ? FALSE : TRUE;
    }

    this->clearFaceMaterialIndexers();
    if (!geometry.coordIndices || !geometry.materialIndices ||
        geometry.numCoordIndices <= 0 || geometry.numMaterialIndices <= 0) {
      return FALSE;
    }

    std::map<uint32_t, int> materialGroups;
    FaceMaterialFaceIterator faces(
      geometry.coordIndices,
      geometry.numCoordIndices,
      geometry.materialIndices,
      geometry.numMaterialIndices);
    FaceMaterialFace faceData;
    int face = 0;
    while (faces.next(faceData)) {
      const int faceSize = faceData.count;
      const int material = faceData.materialIndex;
      if (faceSize < 3 || material < 0 ||
          material >= static_cast<int>(faceMaterialColors.size())) {
        this->clearFaceMaterialIndexers();
        return FALSE;
      }

      ++face;
      const uint32_t color = faceMaterialColors[material];
      std::map<uint32_t, int>::iterator group = materialGroups.find(color);
      int groupIndex;
      if (group == materialGroups.end()) {
        groupIndex = static_cast<int>(faceMaterialIndexers.size());
        materialGroups[color] = groupIndex;
        faceMaterialIndexers.push_back(
          std::unique_ptr<SoVertexArrayIndexer>(new SoVertexArrayIndexer));
        faceMaterialRepresentatives.push_back(material);
      }
      else {
        groupIndex = group->second;
      }

      SoVertexArrayIndexer * indexer = faceMaterialIndexers[groupIndex].get();
      if (faceSize == 3) {
        indexer->addTriangle(faceData.coordIndices[0],
                             faceData.coordIndices[1],
                             faceData.coordIndices[2]);
      }
      else if (faceSize == 4) {
        indexer->addQuad(faceData.coordIndices[0],
                         faceData.coordIndices[1],
                         faceData.coordIndices[2],
                         faceData.coordIndices[3]);
      }
      else {
        indexer->beginTarget(GL_POLYGON);
        for (int vertex = 0; vertex < faceSize; ++vertex) {
          indexer->targetVertex(GL_POLYGON, faceData.coordIndices[vertex]);
        }
        indexer->endTarget(GL_POLYGON);
      }
    }

    if (!faces.isValid() || face == 0) {
      this->clearFaceMaterialIndexers();
      return FALSE;
    }

    bool hasIndexers = false;
    for (std::vector<std::unique_ptr<SoVertexArrayIndexer> >::iterator it =
           faceMaterialIndexers.begin();
         it != faceMaterialIndexers.end(); ++it) {
      if (*it) {
        SoVertexArrayIndexer *indexer = it->get();
        indexer->close();
        hasIndexers = hasIndexers || (indexer->getNumVertices() > 0);
      }
    }
    if (!hasIndexers) {
      this->clearFaceMaterialIndexers();
      return FALSE;
    }

    faceMaterialGroupedKey = key;
    return TRUE;
  }

  // Build the common vertex domain needed to render per-face colors in one
  // indexed draw. The map below preserves shared vertices where all indexed
  // attributes match, while duplicating only color/normal seams.
  SbBool prepareUnifiedFaceMaterialData(const FaceMaterialGeometry &geometry) {
    const SoCoordinateElement *coords = geometry.coordinates;
    const SbVec3f *normals = geometry.normals;
    const uint32_t *colorPointer = faceMaterialColors.empty()
      ? NULL : faceMaterialColors.data();
    const FaceMaterialUnifiedKey key = {
      coords ? coords->getArrayPtr3() : NULL,
      normals,
      geometry.coordinateNodeId,
      geometry.normalNodeId,
      geometry.shapeNodeId,
      geometry.coordIndices,
      geometry.normalIndices,
      geometry.materialIndices,
      colorPointer,
      geometry.numCoordIndices,
      coords ? coords->getNum() : 0,
      static_cast<int>(faceMaterialColors.size()),
      geometry.normalCount,
      faceMaterialColorHash,
      geometry.hasNormals
    };
    // Coordinate elements are action-local. The source data pointer and node
    // generation identify the data without tying the cache to one action's
    // element instance.
    if (unifiedMaterialReady && unifiedMaterialKey == key) {
      faceMaterialTestProbe.recordUnifiedCacheHit();
      return TRUE;
    }

    this->clearUnifiedFaceMaterialData();
    if (!coords || !coords->is3D() || !geometry.coordIndices ||
        !geometry.materialIndices || geometry.numCoordIndices <= 0 ||
        geometry.numMaterialIndices <= 0 || faceMaterialColors.empty() ||
        (geometry.hasNormals && (!normals || geometry.normalCount <= 0))) {
      return FALSE;
    }

    std::map<UnifiedVertexKey, GLint> unifiedVertexMap;
    FaceMaterialFaceIterator faces(
      geometry.coordIndices,
      geometry.numCoordIndices,
      geometry.materialIndices,
      geometry.numMaterialIndices);
    FaceMaterialFace faceData;
    int face = 0;
    while (faces.next(faceData)) {
      const int faceSize = faceData.count;
      if (faceSize != 3 && faceSize != 4) {
        this->clearUnifiedFaceMaterialData();
        return FALSE;
      }

      const int material = faceData.materialIndex;
      if (material < 0 ||
          material >= static_cast<int>(faceMaterialColors.size())) {
        this->clearUnifiedFaceMaterialData();
        return FALSE;
      }

      GLint faceVertices[4];
      for (int corner = 0; corner < faceSize; ++corner) {
        const int coordindex = faceData.coordIndices[corner];
        if (coordindex < 0 || coordindex >= coords->getNum()) {
          this->clearUnifiedFaceMaterialData();
          return FALSE;
        }

        int normalindex = -1;
        if (geometry.hasNormals) {
          normalindex = geometry.normalIndices ?
            geometry.normalIndices[faceData.indexOffset + corner] : coordindex;
          if (normalindex < 0 || normalindex >= geometry.normalCount) {
            this->clearUnifiedFaceMaterialData();
            return FALSE;
          }
        }

        const UnifiedVertexKey key = {
          coordindex, normalindex, faceMaterialColors[material]
        };
        std::map<UnifiedVertexKey, GLint>::iterator existing = unifiedVertexMap.find(key);
        if (existing != unifiedVertexMap.end()) {
          faceVertices[corner] = existing->second;
        }
        else {
          faceVertices[corner] = static_cast<GLint>(unifiedMaterialCoords.size());
          unifiedVertexMap[key] = faceVertices[corner];
          unifiedMaterialCoords.push_back(coords->get3(coordindex));
          unifiedMaterialColors.push_back(
            packedColorForVertexArray(faceMaterialColors[material]));
          if (geometry.hasNormals) {
            unifiedMaterialNormals.push_back(normals[normalindex]);
          }
        }
      }

      unifiedMaterialIndices.push_back(faceVertices[0]);
      unifiedMaterialIndices.push_back(faceVertices[1]);
      unifiedMaterialIndices.push_back(faceVertices[2]);
      if (faceSize == 4) {
        unifiedMaterialIndices.push_back(faceVertices[0]);
        unifiedMaterialIndices.push_back(faceVertices[2]);
        unifiedMaterialIndices.push_back(faceVertices[3]);
      }
      ++face;
    }

    if (!faces.isValid() || face == 0 || unifiedMaterialIndices.empty()) {
      this->clearUnifiedFaceMaterialData();
      return FALSE;
    }

    unifiedMaterialCoordVBO.reset(new SoVBO);
    unifiedMaterialCoordVBO->setBufferData(
      unifiedMaterialCoords.data(),
      static_cast<intptr_t>(unifiedMaterialCoords.size() * sizeof(SbVec3f)));
    if (geometry.hasNormals) {
      unifiedMaterialNormalVBO.reset(new SoVBO);
      unifiedMaterialNormalVBO->setBufferData(
        unifiedMaterialNormals.data(),
        static_cast<intptr_t>(unifiedMaterialNormals.size() * sizeof(SbVec3f)));
    }
    unifiedMaterialColorVBO.reset(new SoVBO);
    unifiedMaterialColorVBO->setBufferData(
      unifiedMaterialColors.data(),
      static_cast<intptr_t>(unifiedMaterialColors.size() * sizeof(uint32_t)));
    unifiedMaterialIndexVBO.reset(new SoVBO(GL_ELEMENT_ARRAY_BUFFER));
    unifiedMaterialIndexVBO->setBufferData(
      unifiedMaterialIndices.data(),
      static_cast<intptr_t>(unifiedMaterialIndices.size() * sizeof(GLint)));

    unifiedMaterialKey = key;
    unifiedMaterialHasNormals = geometry.hasNormals;
    unifiedMaterialReady = TRUE;
    faceMaterialTestProbe.recordUnifiedCacheBuild();
    return TRUE;
  }

  SbBool renderUnifiedFaceMaterial(SoGLRenderAction * action,
                                   SoState * state,
                                   const uint32_t contextid) {
    const cc_glglue * glue = sogl_glue_instance(state);
    const int vertexCount = static_cast<int>(unifiedMaterialCoords.size());
    const SbBool useVBO = SoVBO::shouldCreateVBO(state, contextid, vertexCount);

    if (useVBO) {
      unifiedMaterialCoordVBO->bindBuffer(contextid);
      cc_glglue_glVertexPointer(glue, 3, GL_FLOAT, 0, NULL);
      if (unifiedMaterialHasNormals) {
        unifiedMaterialNormalVBO->bindBuffer(contextid);
        cc_glglue_glNormalPointer(glue, GL_FLOAT, 0, NULL);
      }
      unifiedMaterialColorVBO->bindBuffer(contextid);
      cc_glglue_glColorPointer(glue, 4, GL_UNSIGNED_BYTE, 0, NULL);
      unifiedMaterialIndexVBO->bindBuffer(contextid);
    }
    else {
      cc_glglue_glBindBuffer(glue, GL_ARRAY_BUFFER, 0);
      cc_glglue_glVertexPointer(glue, 3, GL_FLOAT, 0,
                                unifiedMaterialCoords.data());
      if (unifiedMaterialHasNormals) {
        cc_glglue_glNormalPointer(glue, GL_FLOAT, 0,
                                  unifiedMaterialNormals.data());
      }
      cc_glglue_glColorPointer(glue, 4, GL_UNSIGNED_BYTE, 0,
                               unifiedMaterialColors.data());
      cc_glglue_glBindBuffer(glue, GL_ELEMENT_ARRAY_BUFFER, 0);
    }

    cc_glglue_glEnableClientState(glue, GL_VERTEX_ARRAY);
    if (unifiedMaterialHasNormals) {
      cc_glglue_glEnableClientState(glue, GL_NORMAL_ARRAY);
    }
    cc_glglue_glEnableClientState(glue, GL_COLOR_ARRAY);
    SoGLVertexAttributeElement::getInstance(state)->enableVBO(action);
    cc_glglue_glDrawElements(glue,
                             GL_TRIANGLES,
                             static_cast<GLsizei>(unifiedMaterialIndices.size()),
                             GL_UNSIGNED_INT,
                             useVBO ? NULL : unifiedMaterialIndices.data());
    SoGLVertexAttributeElement::getInstance(state)->disableVBO(action);
    SoGLLazyElement * lelem = (SoGLLazyElement *) SoLazyElement::getInstance(state);
    lelem->reset(state, SoLazyElement::DIFFUSE_MASK);
    cc_glglue_glDisableClientState(glue, GL_COLOR_ARRAY);
    if (unifiedMaterialHasNormals) {
      cc_glglue_glDisableClientState(glue, GL_NORMAL_ARRAY);
    }
    cc_glglue_glDisableClientState(glue, GL_VERTEX_ARRAY);
    cc_glglue_glBindBuffer(glue, GL_ELEMENT_ARRAY_BUFFER, 0);
    if (useVBO) {
      cc_glglue_glBindBuffer(glue, GL_ARRAY_BUFFER, 0);
    }
    return useVBO;
  }

  void renderGroupedFaceMaterial(SoMaterialBundle &materials,
                                 SoState *state,
                                 const SbBool useVBO,
                                 const uint32_t contextid)
  {
    for (size_t material = 0;
         material < this->groupedIndexerCount(); ++material) {
      SoVertexArrayIndexer *indexer = this->groupedIndexer(material);
      if (indexer) {
        materials.send(this->groupedRepresentative(material), FALSE);
        indexer->render(state, useVBO, contextid);
      }
    }
  }

  size_t groupedIndexerCount(void) const
  {
    return faceMaterialIndexers.size();
  }

  SoVertexArrayIndexer * groupedIndexer(const size_t index)
  {
    return faceMaterialIndexers[index].get();
  }

  int groupedRepresentative(const size_t index) const
  {
    return faceMaterialRepresentatives[index];
  }
};


FaceMaterialRenderer::FaceMaterialRenderer(void)
  : impl(new Impl)
{
}

FaceMaterialRenderer::~FaceMaterialRenderer(void)
{
}

void
FaceMaterialRenderer::invalidateFaceMaterialCaches(void)
{
  impl->invalidateFaceMaterialCaches();
}

FaceMaterialRenderState
FaceMaterialRenderer::prepare(const FaceMaterialRenderInput &input)
{
  return impl->prepare(input);
}

SbBool
FaceMaterialRenderer::renderUnifiedFaceMaterial(SoGLRenderAction *action,
                                                SoState *state,
                                                uint32_t contextid)
{
  return impl->renderUnifiedFaceMaterial(action, state, contextid);
}

void
FaceMaterialRenderer::renderGroupedFaceMaterial(SoMaterialBundle &materials,
                                                SoState *state,
                                                SbBool useVBO,
                                                uint32_t contextid)
{
  impl->renderGroupedFaceMaterial(materials, state, useVBO, contextid);
}
