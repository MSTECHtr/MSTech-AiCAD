#include <EGL/egl.h>
#include <EGL/eglext.h>

#include "glue/gl_egl.h"

#include <Inventor/C/glue/gl.h>

#include <cstdlib>
#include <iostream>

#ifndef COIN_TEST_SKIP_RETURN_CODE
#error COIN_TEST_SKIP_RETURN_CODE must match the CTest SKIP_RETURN_CODE property
#endif

namespace {

int skip(const char * reason)
{
  std::cout << "SKIP: " << reason << std::endl;
  return COIN_TEST_SKIP_RETURN_CODE;
}

EGLDisplay acquire_surfaceless_display()
{
  PFNEGLGETPLATFORMDISPLAYEXTPROC getPlatformDisplay =
      reinterpret_cast<PFNEGLGETPLATFORMDISPLAYEXTPROC>(
          eglGetProcAddress("eglGetPlatformDisplayEXT"));
  if (!getPlatformDisplay) return EGL_NO_DISPLAY;
  return getPlatformDisplay(EGL_PLATFORM_SURFACELESS_MESA,
                            EGL_DEFAULT_DISPLAY, NULL);
}

struct EGLTestState {
  EGLDisplay display;
  EGLContext foreignContext;
  EGLSurface drawSurface;
  EGLSurface readSurface;
  void * coinContext;
  bool coinMadeCurrent;

  explicit EGLTestState(EGLDisplay displayIn)
    : display(displayIn),
      foreignContext(EGL_NO_CONTEXT),
      drawSurface(EGL_NO_SURFACE),
      readSurface(EGL_NO_SURFACE),
      coinContext(NULL),
      coinMadeCurrent(false)
  {
  }

  void cleanup()
  {
    if (this->coinMadeCurrent) {
      cc_glglue_context_reinstate_previous(this->coinContext);
    }
    if (this->coinContext) {
      cc_glglue_context_destruct(this->coinContext);
    }
    eglMakeCurrent(this->display,
                   EGL_NO_SURFACE,
                   EGL_NO_SURFACE,
                   EGL_NO_CONTEXT);
    if (this->foreignContext != EGL_NO_CONTEXT) {
      eglDestroyContext(this->display, this->foreignContext);
    }
    if (this->drawSurface != EGL_NO_SURFACE) {
      eglDestroySurface(this->display, this->drawSurface);
    }
    if (this->readSurface != EGL_NO_SURFACE) {
      eglDestroySurface(this->display, this->readSurface);
    }
    eglTerminate(this->display);
  }
};

int fail(const char * message)
{
  std::cerr << "FAIL: " << message << std::endl;
  return 1;
}

int run_owned_surfaceless_test()
{
  setenv("EGL_PLATFORM", "surfaceless", 1);
  void * coinContext = cc_glglue_context_create_offscreen(16, 16);
  unsetenv("EGL_PLATFORM");
  if (!coinContext) {
    eglglue_cleanup();
    return skip("Coin could not create an owned surfaceless context");
  }

  if (!cc_glglue_context_make_current(coinContext)) {
    cc_glglue_context_destruct(coinContext);
    eglglue_cleanup();
    return fail("Coin owned surfaceless context could not be made current");
  }

  int result = 0;
  if (eglQueryAPI() != EGL_OPENGL_API ||
      eglGetCurrentDisplay() == EGL_NO_DISPLAY ||
      eglGetCurrentContext() == EGL_NO_CONTEXT) {
    result = fail("Coin did not activate its owned surfaceless context");
  }

  cc_glglue_context_reinstate_previous(coinContext);
  if (eglGetCurrentDisplay() != EGL_NO_DISPLAY ||
      eglGetCurrentContext() != EGL_NO_CONTEXT) {
    result = fail("Coin did not restore the empty caller EGL binding");
  }
  cc_glglue_context_destruct(coinContext);
  eglglue_cleanup();
  return result;
}

int run_borrowed_display_test(EGLTestState & state)
{
  if (eglBindAPI(EGL_OPENGL_ES_API) == EGL_FALSE) {
    return skip("OpenGL ES client API is unavailable");
  }

  EGLint configAttributes[] = {
    EGL_SURFACE_TYPE, EGL_PBUFFER_BIT,
    EGL_RENDERABLE_TYPE, EGL_OPENGL_ES2_BIT,
    EGL_RED_SIZE, 8,
    EGL_GREEN_SIZE, 8,
    EGL_BLUE_SIZE, 8,
    EGL_ALPHA_SIZE, 8,
    EGL_NONE
  };
  EGLConfig config = (EGLConfig) 0;
  EGLint configCount = 0;
  if (eglChooseConfig(state.display,
                      configAttributes,
                      &config,
                      1,
                      &configCount) == EGL_FALSE || configCount == 0) {
    return skip("no OpenGL ES pbuffer configuration");
  }

  EGLint surfaceAttributes[] = {
    EGL_WIDTH, 16,
    EGL_HEIGHT, 16,
    EGL_NONE
  };
  state.drawSurface =
      eglCreatePbufferSurface(state.display, config, surfaceAttributes);
  state.readSurface =
      eglCreatePbufferSurface(state.display, config, surfaceAttributes);
  if (state.drawSurface == EGL_NO_SURFACE ||
      state.readSurface == EGL_NO_SURFACE) {
    return skip("OpenGL ES pbuffers could not be created");
  }

  EGLint contextAttributes[] = {
    EGL_CONTEXT_CLIENT_VERSION, 2,
    EGL_NONE
  };
  state.foreignContext = eglCreateContext(state.display,
                                          config,
                                          EGL_NO_CONTEXT,
                                          contextAttributes);
  if (state.foreignContext == EGL_NO_CONTEXT ||
      eglMakeCurrent(state.display,
                     state.drawSurface,
                     state.readSurface,
                     state.foreignContext) == EGL_FALSE) {
    return skip("OpenGL ES context could not be made current");
  }

  const EGLenum previousApi = eglQueryAPI();
  const EGLDisplay previousDisplay = eglGetCurrentDisplay();
  const EGLContext previousContext = eglGetCurrentContext();
  const EGLSurface previousDrawSurface = eglGetCurrentSurface(EGL_DRAW);
  const EGLSurface previousReadSurface = eglGetCurrentSurface(EGL_READ);

  state.coinContext = cc_glglue_context_create_offscreen(16, 16);
  if (!state.coinContext) return fail("Coin offscreen context creation failed");
  if (eglQueryAPI() != previousApi) {
    return fail("Coin did not restore the caller API after context creation");
  }
  if (!cc_glglue_context_make_current(state.coinContext)) {
    return fail("Coin offscreen context could not be made current");
  }
  state.coinMadeCurrent = true;
  if (eglQueryAPI() != EGL_OPENGL_API) {
    return fail("Coin context did not bind the OpenGL client API");
  }
  if (eglGetCurrentDisplay() != previousDisplay) {
    return fail("Coin context did not use the caller's EGL display");
  }

  cc_glglue_context_reinstate_previous(state.coinContext);
  state.coinMadeCurrent = false;
  if (eglQueryAPI() != previousApi) {
    return fail("Coin did not restore the caller API");
  }
  if (eglGetCurrentDisplay() != previousDisplay ||
      eglGetCurrentContext() != previousContext ||
      eglGetCurrentSurface(EGL_DRAW) != previousDrawSurface ||
      eglGetCurrentSurface(EGL_READ) != previousReadSurface) {
    return fail("Coin did not restore the complete caller EGL binding");
  }

  cc_glglue_context_destruct(state.coinContext);
  state.coinContext = NULL;
  eglglue_cleanup();
  if (eglQueryAPI() != previousApi ||
      eglGetCurrentDisplay() != previousDisplay ||
      eglGetCurrentContext() != previousContext ||
      eglGetCurrentSurface(EGL_DRAW) != previousDrawSurface ||
      eglGetCurrentSurface(EGL_READ) != previousReadSurface) {
    return fail("Coin cleanup did not preserve the borrowed EGL binding");
  }

  return 0;
}

} // namespace

int main()
{
  setenv("COIN_EGL", "1", 1);
  setenv("COIN_EGL_CORE_PROFILE", "1", 1);

  const int ownedResult = run_owned_surfaceless_test();
  if (ownedResult != 0) return ownedResult;

  // Acquire the caller's platform directly. EGL_PLATFORM remains unset so
  // Coin must discover and borrow the already-current display.
  EGLDisplay display = acquire_surfaceless_display();
  if (display == EGL_NO_DISPLAY) return skip("no EGL display");

  EGLint major = 0;
  EGLint minor = 0;
  if (eglInitialize(display, &major, &minor) == EGL_FALSE) {
    return skip("EGL display could not be initialized");
  }

  EGLTestState state(display);
  const int result = run_borrowed_display_test(state);
  state.cleanup();
  return result;
}
