#include <Inventor/SoDB.h>
#include <Inventor/SoOffscreenRenderer.h>
#include <Inventor/SbColor.h>
#include <Inventor/SbVec2s.h>
#include <Inventor/SbVec3f.h>
#include <Inventor/nodes/SoCoordinate3.h>
#include <Inventor/nodes/SoDirectionalLight.h>
#include <Inventor/nodes/SoIndexedFaceSet.h>
#include <Inventor/nodes/SoLightModel.h>
#include <Inventor/nodes/SoMaterial.h>
#include <Inventor/nodes/SoMaterialBinding.h>
#include <Inventor/nodes/SoNormal.h>
#include <Inventor/nodes/SoNormalBinding.h>
#include <Inventor/nodes/SoOrthographicCamera.h>
#include <Inventor/nodes/SoSeparator.h>
#include <Inventor/nodes/SoShaderObject.h>
#include <Inventor/nodes/SoShaderProgram.h>
#include <Inventor/nodes/SoVertexShader.h>
#include <Inventor/nodes/SoTexture2.h>
#include <Inventor/nodes/SoTextureCoordinate2.h>
#include <Inventor/nodes/SoVertexAttribute.h>
#include <Inventor/fields/SoMFFloat.h>

#include "SoIndexedFaceSetTestHooks.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace {

const int ImageSize = 128;
bool offscreenContextUnavailable = false;

struct Scene {
  SoSeparator * root;
  SoMaterial * material;
  SoLightModel * lightmodel;
  SoCoordinate3 * coordinates;
  SoNormal * normals;
  SoNormalBinding * normalBinding;
  SoIndexedFaceSet * faces;
};

struct Pixel {
  unsigned char red;
  unsigned char green;
  unsigned char blue;
};

SbColor asymmetricColor(void)
{
  return SbColor(0x12 / 255.0f, 0x48 / 255.0f, 0xa7 / 255.0f);
}

Scene createScene(const std::vector<SbColor> & colors,
                  const std::vector<int32_t> & materialindices)
{
  Scene scene = { new SoSeparator, new SoMaterial, NULL, new SoCoordinate3,
                  NULL, NULL, new SoIndexedFaceSet };
  scene.root->ref();

  SoOrthographicCamera * camera = new SoOrthographicCamera;
  camera->position = SbVec3f(0.0f, 0.0f, 5.0f);
  camera->height = 2.4f;

  SoLightModel * lightmodel = new SoLightModel;
  lightmodel->model = SoLightModel::BASE_COLOR;
  scene.lightmodel = lightmodel;

  SoDirectionalLight * light = new SoDirectionalLight;
  light->direction = SbVec3f(0.0f, 0.0f, -1.0f);

  SoMaterialBinding * binding = new SoMaterialBinding;
  binding->value = SoMaterialBinding::PER_FACE_INDEXED;

  scene.material->diffuseColor.setNum(static_cast<int>(colors.size()));
  for (int i = 0; i < static_cast<int>(colors.size()); ++i) {
    scene.material->diffuseColor.set1Value(i, colors[i]);
  }

  scene.faces->materialIndex.setValues(
    0, static_cast<int>(materialindices.size()), materialindices.data());

  scene.root->addChild(camera);
  scene.root->addChild(lightmodel);
  scene.root->addChild(light);
  scene.root->addChild(scene.material);
  scene.root->addChild(binding);
  scene.root->addChild(scene.coordinates);
  scene.root->addChild(scene.faces);
  return scene;
}

void setTwoFaceGeometry(Scene & scene)
{
  const SbVec3f points[] = {
    SbVec3f(-1.0f, -0.8f, 0.0f), SbVec3f(-0.05f, -0.8f, 0.0f),
    SbVec3f(-0.05f, 0.8f, 0.0f), SbVec3f(-1.0f, 0.8f, 0.0f),
    SbVec3f(0.05f, -0.8f, 0.0f), SbVec3f(1.0f, -0.8f, 0.0f),
    SbVec3f(1.0f, 0.8f, 0.0f), SbVec3f(0.05f, 0.8f, 0.0f)
  };
  scene.coordinates->point.setValues(0, 8, points);
  const int32_t indices[] = { 0, 1, 2, 3, -1, 4, 5, 6, 7, -1 };
  scene.faces->coordIndex.setValues(0, 10, indices);
}

void setGridGeometry(Scene & scene, const int rows, const int columns)
{
  std::vector<SbVec3f> points;
  std::vector<int32_t> indices;
  points.reserve(static_cast<size_t>(rows * columns * 4));
  indices.reserve(static_cast<size_t>(rows * columns * 5));

  for (int row = 0; row < rows; ++row) {
    for (int column = 0; column < columns; ++column) {
      const float x0 = -1.0f + 2.0f * column / columns;
      const float x1 = -1.0f + 2.0f * (column + 1) / columns;
      const float y0 = -1.0f + 2.0f * row / rows;
      const float y1 = -1.0f + 2.0f * (row + 1) / rows;
      const int32_t base = static_cast<int32_t>(points.size());
      points.push_back(SbVec3f(x0, y0, 0.0f));
      points.push_back(SbVec3f(x1, y0, 0.0f));
      points.push_back(SbVec3f(x1, y1, 0.0f));
      points.push_back(SbVec3f(x0, y1, 0.0f));
      indices.push_back(base + 0);
      indices.push_back(base + 1);
      indices.push_back(base + 2);
      indices.push_back(base + 3);
      indices.push_back(-1);
    }
  }

  scene.coordinates->point.setValues(
    0, static_cast<int>(points.size()), points.data());
  scene.faces->coordIndex.setValues(
    0, static_cast<int>(indices.size()), indices.data());
}

bool renderScene(SoOffscreenRenderer & renderer, SoNode * root,
                 std::vector<unsigned char> & pixels)
{
  if (!renderer.render(root) || !renderer.getBuffer()) {
    offscreenContextUnavailable = true;
    return false;
  }
  pixels.assign(renderer.getBuffer(), renderer.getBuffer() + ImageSize * ImageSize * 3);
  return true;
}

Pixel pixelAt(const std::vector<unsigned char> & pixels, const int x, const int y)
{
  const size_t offset = static_cast<size_t>((y * ImageSize + x) * 3);
  return Pixel { pixels[offset], pixels[offset + 1], pixels[offset + 2] };
}

bool closeTo(Pixel actual, SbColor expected)
{
  const int red = static_cast<int>(expected[0] * 255.0f + 0.5f);
  const int green = static_cast<int>(expected[1] * 255.0f + 0.5f);
  const int blue = static_cast<int>(expected[2] * 255.0f + 0.5f);
  return std::abs(static_cast<int>(actual.red) - red) <= 8
      && std::abs(static_cast<int>(actual.green) - green) <= 8
      && std::abs(static_cast<int>(actual.blue) - blue) <= 8;
}

bool expectStrategy(const CoinFaceMaterialTestStrategy expected, const char * label)
{
  const CoinFaceMaterialTestState state = coinGetFaceMaterialTestState();
  if (state.lastStrategy != expected) {
    std::fprintf(stderr, "%s selected strategy %d, expected %d\n",
                 label, static_cast<int>(state.lastStrategy),
                 static_cast<int>(expected));
    return false;
  }
  return true;
}

bool expectUnifiedBuilds(const uint64_t expected, const char * label)
{
  const CoinFaceMaterialTestState state = coinGetFaceMaterialTestState();
  if (state.unifiedCacheBuilds != expected) {
    std::fprintf(stderr, "%s unified cache builds were %llu, expected %llu\n",
                 label,
                 static_cast<unsigned long long>(state.unifiedCacheBuilds),
                 static_cast<unsigned long long>(expected));
    return false;
  }
  return true;
}

bool expectUnifiedHits(const uint64_t expected, const char * label)
{
  const CoinFaceMaterialTestState state = coinGetFaceMaterialTestState();
  if (state.unifiedCacheHits != expected) {
    std::fprintf(stderr, "%s unified cache hits were %llu, expected %llu\n",
                 label,
                 static_cast<unsigned long long>(state.unifiedCacheHits),
                 static_cast<unsigned long long>(expected));
    return false;
  }
  return true;
}

CoinFaceMaterialTestStrategy expectedStrategyForTwoColorScene(void)
{
  const char * value = std::getenv("COIN_FACE_MATERIAL_STRATEGY");
  if (!value || std::strcmp(value, "auto") == 0 || std::strcmp(value, "grouped") == 0) {
    return COIN_FACE_MATERIAL_TEST_GROUPED;
  }
  if (std::strcmp(value, "unified") == 0) {
    return COIN_FACE_MATERIAL_TEST_UNIFIED;
  }
  if (std::strcmp(value, "fallback") == 0) {
    return COIN_FACE_MATERIAL_TEST_FALLBACK;
  }
  return COIN_FACE_MATERIAL_TEST_UNKNOWN;
}

bool checkPixel(const std::vector<unsigned char> & pixels, const int x, const int y,
                const SbColor & expected, const char * label)
{
  const Pixel actual = pixelAt(pixels, x, y);
  if (!closeTo(actual, expected)) {
    std::fprintf(stderr, "%s pixel was (%u, %u, %u)\n", label,
                 actual.red, actual.green, actual.blue);
    return false;
  }
  return true;
}

bool containsPixel(const std::vector<unsigned char> & pixels,
                   const SbColor & expected, const char * label)
{
  for (int y = 0; y < ImageSize; ++y) {
    for (int x = 0; x < ImageSize; ++x) {
      if (closeTo(pixelAt(pixels, x, y), expected)) {
        return true;
      }
    }
  }
  std::fprintf(stderr, "%s color was not present in the framebuffer\n", label);
  return false;
}

bool renderSingleReferencedMaterial(const bool asymmetric)
{
  const SbColor special = asymmetric ? asymmetricColor() : SbColor(0.2f, 0.7f, 0.3f);
  const std::vector<SbColor> colors = {
    SbColor(1.0f, 0.0f, 0.0f), SbColor(0.0f, 1.0f, 0.0f), special
  };
  const std::vector<int32_t> materialindices = { 2 };
  Scene scene = createScene(colors, materialindices);
  const int32_t indices[] = { 0, 1, 2, 3, -1 };
  const SbVec3f points[] = {
    SbVec3f(-1.0f, -0.8f, 0.0f), SbVec3f(1.0f, -0.8f, 0.0f),
    SbVec3f(1.0f, 0.8f, 0.0f), SbVec3f(-1.0f, 0.8f, 0.0f)
  };
  scene.coordinates->point.setValues(0, 4, points);
  scene.faces->coordIndex.setValues(0, 5, indices);

  SoOffscreenRenderer renderer(SbViewportRegion(SbVec2s(ImageSize, ImageSize)));
  renderer.setComponents(SoOffscreenRenderer::RGB);
  renderer.setBackgroundColor(SbColor(0.0f, 0.0f, 0.0f));
  std::vector<unsigned char> pixels;
  const bool rendered = renderScene(renderer, scene.root, pixels);
  const bool correct = rendered
      && checkPixel(pixels, 64, 64, special, "single face")
      && expectStrategy(COIN_FACE_MATERIAL_TEST_OVERALL, "single face");
  scene.root->unref();
  return rendered ? correct : false;
}

bool renderSamePackedColor(void)
{
  const SbColor repeated(0.25f, 0.5f, 0.75f);
  const std::vector<SbColor> colors = {
    SbColor(1.0f, 0.0f, 0.0f), repeated, repeated
  };
  Scene scene = createScene(colors, std::vector<int32_t> { 1, 2 });
  setTwoFaceGeometry(scene);
  SoOffscreenRenderer renderer(SbViewportRegion(SbVec2s(ImageSize, ImageSize)));
  renderer.setComponents(SoOffscreenRenderer::RGB);
  renderer.setBackgroundColor(SbColor(0.0f, 0.0f, 0.0f));
  std::vector<unsigned char> pixels;
  const bool rendered = renderScene(renderer, scene.root, pixels);
  const bool correct = rendered
      && checkPixel(pixels, 32, 64, repeated, "same-color left face")
      && checkPixel(pixels, 96, 64, repeated, "same-color right face")
      && expectStrategy(COIN_FACE_MATERIAL_TEST_OVERALL, "same packed color");
  scene.root->unref();
  return rendered ? correct : false;
}

Scene createStrategyScene(void)
{
  std::vector<int32_t> materialindices;
  for (int i = 0; i < 64; ++i) {
    materialindices.push_back(i % 2);
  }
  Scene scene = createScene(
    std::vector<SbColor> { SbColor(0.9f, 0.1f, 0.1f), SbColor(0.1f, 0.2f, 0.9f) },
    materialindices);
  setGridGeometry(scene, 8, 8);
  scene.lightmodel->model = SoLightModel::PHONG;

  // Keep normals in the active vertex domain so the mutation test verifies
  // that the unified cache also observes normal-node changes.
  scene.normals = new SoNormal;
  std::vector<SbVec3f> normals(256, SbVec3f(0.0f, 0.0f, 1.0f));
  scene.normals->vector.setValues(0, static_cast<int>(normals.size()), normals.data());
  scene.normalBinding = new SoNormalBinding;
  scene.normalBinding->value = SoNormalBinding::PER_VERTEX_INDEXED;
  scene.root->insertChild(scene.normals, 4);
  scene.root->insertChild(scene.normalBinding, 5);
  return scene;
}

bool renderStrategyScene(void)
{
  Scene scene = createStrategyScene();
  SoOffscreenRenderer renderer(SbViewportRegion(SbVec2s(ImageSize, ImageSize)));
  renderer.setComponents(SoOffscreenRenderer::RGB);
  renderer.setBackgroundColor(SbColor(0.0f, 0.0f, 0.0f));
  std::vector<unsigned char> pixels;
  const bool rendered = renderScene(renderer, scene.root, pixels);
  const bool correct = rendered && expectStrategy(
    expectedStrategyForTwoColorScene(), "two-color scene");
  scene.root->unref();
  return correct;
}

bool renderSmallFallback(void)
{
  std::vector<SbColor> colors;
  std::vector<int32_t> materialindices;
  for (int i = 0; i < 16; ++i) {
    colors.push_back(SbColor((i + 1) / 17.0f, (16 - i) / 17.0f, (i % 5 + 1) / 6.0f));
    materialindices.push_back(i);
  }
  Scene scene = createScene(colors, materialindices);
  setGridGeometry(scene, 4, 4);
  SoOffscreenRenderer renderer(SbViewportRegion(SbVec2s(ImageSize, ImageSize)));
  renderer.setComponents(SoOffscreenRenderer::RGB);
  renderer.setBackgroundColor(SbColor(0.0f, 0.0f, 0.0f));
  std::vector<unsigned char> pixels;
  const bool rendered = renderScene(renderer, scene.root, pixels);
  const bool correct = rendered && expectStrategy(
    COIN_FACE_MATERIAL_TEST_FALLBACK, "small fallback");
  scene.root->unref();
  return correct;
}

bool renderMutation(void)
{
  Scene scene = createStrategyScene();
  // Keep the color assertion in the unlit mode, then enable normals before
  // the normal mutation so both state variants exercise the same cache.
  scene.lightmodel->model = SoLightModel::BASE_COLOR;
  SoOffscreenRenderer renderer(SbViewportRegion(SbVec2s(ImageSize, ImageSize)));
  renderer.setComponents(SoOffscreenRenderer::RGB);
  renderer.setBackgroundColor(SbColor(0.0f, 0.0f, 0.0f));
  std::vector<unsigned char> pixels;
  if (!renderScene(renderer, scene.root, pixels)
      || !expectStrategy(COIN_FACE_MATERIAL_TEST_UNIFIED, "mutation warm build")
      || !expectUnifiedBuilds(1, "mutation warm build")
      || !renderScene(renderer, scene.root, pixels)
      || !expectUnifiedHits(1, "mutation warm render")
      || !expectUnifiedBuilds(1, "mutation warm render")) {
    scene.root->unref();
    return false;
  }

  scene.material->diffuseColor.set1Value(0, SbColor(0.2f, 0.9f, 0.2f));
  if (!renderScene(renderer, scene.root, pixels)
      || !containsPixel(pixels, SbColor(0.2f, 0.9f, 0.2f), "mutated color")
      || !expectUnifiedBuilds(2, "material color mutation")) {
    scene.root->unref();
    return false;
  }

  scene.coordinates->point.set1Value(0, SbVec3f(-1.2f, -0.8f, 0.0f));
  if (!renderScene(renderer, scene.root, pixels)
      || !expectUnifiedBuilds(3, "coordinate mutation")) {
    scene.root->unref();
    return false;
  }

  scene.lightmodel->model = SoLightModel::PHONG;
  scene.normals->vector.set1Value(0, SbVec3f(0.0f, 0.0f, -1.0f));
  if (!renderScene(renderer, scene.root, pixels)
      || !expectUnifiedBuilds(4, "normal mutation")) {
    scene.root->unref();
    return false;
  }

  scene.faces->materialIndex.set1Value(0, 1);
  scene.faces->materialIndex.set1Value(1, 0);
  if (!renderScene(renderer, scene.root, pixels)
      || !expectUnifiedBuilds(5, "material index mutation")) {
    scene.root->unref();
    return false;
  }

  // Change topology separately from material indices. The coordinate-index
  // mutation must invalidate the unified index stream independently.
  scene.faces->coordIndex.set1Value(0, 1);
  scene.faces->coordIndex.set1Value(1, 0);
  const bool rendered = renderScene(renderer, scene.root, pixels)
      && expectUnifiedBuilds(6, "coordinate index mutation");
  scene.root->unref();
  return rendered;
}

bool renderWithCustomAttribute(void)
{
  Scene scene = createStrategyScene();
  SoShaderProgram * program = new SoShaderProgram;
  SoVertexShader * shader = new SoVertexShader;
  shader->sourceType = SoShaderObject::GLSL_PROGRAM;
  shader->sourceProgram = "void main() { gl_Position = ftransform(); }";
  program->shaderObject.set1Value(0, shader);
  SoVertexAttribute * attribute = new SoVertexAttribute;
  attribute->name = "coinFaceMaterialTestAttribute";
  attribute->typeName = "SoMFFloat";
  SoMFFloat * values = static_cast<SoMFFloat *>(attribute->getValuesField());
  std::vector<float> attributeValues(256);
  for (int i = 0; i < static_cast<int>(attributeValues.size()); ++i) {
    attributeValues[i] = static_cast<float>(i % 2);
  }
  values->setValues(0, static_cast<int>(attributeValues.size()), attributeValues.data());
  scene.root->insertChild(program, 1);
  scene.root->insertChild(attribute, 2);

  SoOffscreenRenderer renderer(SbViewportRegion(SbVec2s(ImageSize, ImageSize)));
  renderer.setComponents(SoOffscreenRenderer::RGB);
  renderer.setBackgroundColor(SbColor(0.0f, 0.0f, 0.0f));
  std::vector<unsigned char> pixels;
  const bool rendered = renderScene(renderer, scene.root, pixels)
      && expectStrategy(COIN_FACE_MATERIAL_TEST_FALLBACK, "custom attribute");
  scene.root->unref();
  return rendered;
}

bool renderWithTexture(void)
{
  Scene scene = createStrategyScene();
  SoTexture2 * texture = new SoTexture2;
  const unsigned char white[] = { 255, 255, 255 };
  texture->model = SoTexture2::REPLACE;
  texture->image.setValue(SbVec2s(1, 1), 3, white);
  SoTextureCoordinate2 * texturecoordinates = new SoTextureCoordinate2;
  std::vector<SbVec2f> texcoords(256);
  for (int i = 0; i < static_cast<int>(texcoords.size()); ++i) {
    texcoords[i] = SbVec2f((i % 4) / 3.0f, (i / 4) / 63.0f);
  }
  texturecoordinates->point.setValues(0, static_cast<int>(texcoords.size()), texcoords.data());
  scene.root->insertChild(texture, 1);
  scene.root->insertChild(texturecoordinates, 2);

  SoOffscreenRenderer renderer(SbViewportRegion(SbVec2s(ImageSize, ImageSize)));
  renderer.setComponents(SoOffscreenRenderer::RGB);
  renderer.setBackgroundColor(SbColor(0.0f, 0.0f, 0.0f));
  std::vector<unsigned char> pixels;
  const bool rendered = renderScene(renderer, scene.root, pixels)
      && expectStrategy(COIN_FACE_MATERIAL_TEST_FALLBACK, "texture");
  scene.root->unref();
  return rendered;
}

bool renderTransparent(void)
{
  Scene scene = createStrategyScene();
  scene.material->transparency.setNum(2);
  scene.material->transparency.set1Value(0, 0.5f);
  scene.material->transparency.set1Value(1, 0.5f);
  SoOffscreenRenderer renderer(SbViewportRegion(SbVec2s(ImageSize, ImageSize)));
  renderer.setComponents(SoOffscreenRenderer::RGB);
  renderer.setBackgroundColor(SbColor(0.0f, 0.0f, 0.0f));
  std::vector<unsigned char> pixels;
  const bool rendered = renderScene(renderer, scene.root, pixels)
      && expectStrategy(COIN_FACE_MATERIAL_TEST_FALLBACK, "transparent");
  scene.root->unref();
  return rendered;
}

bool renderCase(const char * name)
{
  if (std::strcmp(name, "nonzero-material") == 0) {
    return renderSingleReferencedMaterial(false);
  }
  if (std::strcmp(name, "asymmetric-rgba") == 0) {
    return renderSingleReferencedMaterial(true);
  }
  if (std::strcmp(name, "same-packed-color") == 0) {
    return renderSamePackedColor();
  }
  if (std::strcmp(name, "two-colors") == 0) {
    return renderStrategyScene();
  }
  if (std::strcmp(name, "small-fallback") == 0) {
    return renderSmallFallback();
  }
  if (std::strcmp(name, "mutation") == 0) {
    return renderMutation();
  }
  if (std::strcmp(name, "custom-attribute") == 0) {
    return renderWithCustomAttribute();
  }
  if (std::strcmp(name, "texture") == 0) {
    return renderWithTexture();
  }
  if (std::strcmp(name, "transparent") == 0) {
    return renderTransparent();
  }
  std::fprintf(stderr, "unknown test case: %s\n", name);
  return false;
}

} // namespace

int main(int argc, char ** argv)
{
  if (argc != 2) {
    std::fprintf(stderr, "usage: %s CASE\n", argv[0]);
    return EXIT_FAILURE;
  }

  SoDB::init();
  coinResetFaceMaterialTestState();
  const bool success = renderCase(argv[1]);
  SoDB::finish();
  if (!success) {
    return offscreenContextUnavailable ? 77 : EXIT_FAILURE;
  }
  return EXIT_SUCCESS;
}
