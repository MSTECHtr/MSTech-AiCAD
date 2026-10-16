set(COIN_TEST_SKIP_RETURN_CODE 77)

macro(create_testsuite input)
	get_filename_component(FLNAME "${input}" NAME_WE)
	get_filename_component(FLPATH "${input}" PATH)
	string(REGEX REPLACE ".*[/\\]" "" FLSUBFLD "${FLPATH}")
	set(COIN_STR_TEST_CLASS "${FLNAME}")
	file(READ ${PROJECT_SOURCE_DIR}/${input} f0)
	if(f0 MATCHES "#ifdef[ \t]+COIN_TEST_SUITE")
		# message(STATUS "Parse: ${PROJECT_SOURCE_DIR}/${input} - ${FLPATHSUB}${FLNAME}Test.cpp")
		# get first include from file, which we assume is include to tested class
		string(REGEX MATCH "[\n\r]+#include[ \t]<[^\n]+" iclass "${f0}")
		# get block between '#ifdef COIN_TEST_SUITE' and '#endif'
		string(REGEX REPLACE ".*#ifdef[ \t]+COIN_TEST_SUITE" "" f1 "${f0}")
		string(REGEX REPLACE "#endif[ \t/!]+COIN_TEST_SUITE.*" "" f2 "${f1}")
		# get all #include statements within COIN_TEST_SUITE code block
		string(REGEX MATCHALL "#include[ \t]<[^\n]+" i0 "${f2}")
		string(REPLACE ";" "\n" COIN_STR_TEST_INCL "${i0}")
		set(COIN_STR_TEST_INCL "${iclass}\n${COIN_STR_TEST_INCL}")
		# remove #include statements from test code string (moved to ${COIN_STR_TEST_INCL})
		string(REGEX REPLACE "[\n\r ]*#include[ \t]<[^\n]+" "" COIN_STR_TEST_CODE "${f2}")
		# generate new test code file with extracted snippets
		configure_file(TestSuiteTemplate.cmake.in "${FLSUBFLD}${FLNAME}Test.cpp")
	endif()
endmacro()

macro(create_file_test input testfunc filter)
	file(GLOB_RECURSE COIN_IV_FILES RELATIVE ${PROJECT_SOURCE_DIR}
		../${input}/*.iv
		../${input}/*.iv.gz
	)
	if (HAVE_VRML97)
		file(GLOB_RECURSE COIN_WRL_VRML_FILES RELATIVE ${PROJECT_SOURCE_DIR}
			../${input}/*.wrl
			../${input}/*.vrml
			../${input}/*.wrl.gz
			../${input}/*.vrml.gz
		)
		list(APPEND COIN_IV_FILES ${COIN_WRL_VRML_FILES})
	endif()
	string(REGEX REPLACE "[\\./\\-]+" "" TESTSUITENAME "${input}")
	set(COIN_STR_TEST_INCL "")
	set(COIN_STR_TEST_CODE "const char *readError[] = { \"Coin read error:\", 0 };\n")
	set(COIN_STR_TEST_CLASS "${TESTSUITENAME}")
	set(extra_macro_args ${ARGN})
	list(LENGTH extra_macro_args num_extra_args)
	foreach(INPUTFILE ${COIN_IV_FILES})
		if(${num_extra_args} EQUAL 0 OR NOT ("${INPUTFILE}" MATCHES "${extra_macro_args}"))
			string(REGEX REPLACE "[\\./\\-]+" "_" TESTNAME "${INPUTFILE}")
			if (${filter})
				set(COIN_STR_TEST_CODE "${COIN_STR_TEST_CODE}\nBOOST_AUTO_TEST_CASE(${TESTNAME}) { PushMessageSuppressFilters(readError); ResetReadErrorCount(); test_file(\"${PROJECT_SOURCE_DIR}/${INPUTFILE}\", &${testfunc}); PopMessageSuppressFilters(); }")
			else()
				set(COIN_STR_TEST_CODE "${COIN_STR_TEST_CODE}\nBOOST_AUTO_TEST_CASE(${TESTNAME}) { ResetReadErrorCount(); test_file(\"${PROJECT_SOURCE_DIR}/${INPUTFILE}\", &${testfunc}); }")
			endif()
		endif()
	endforeach()
	configure_file(TestSuiteTemplate.cmake.in "${TESTSUITENAME}Test.cpp")
endmacro()

# Parse all source files for embedded '#ifdef COIN_TEST_SUITE' and extract those blocks
# to separate test source files.
file(GLOB_RECURSE COIN_SRC_FILES RELATIVE ${PROJECT_SOURCE_DIR} ${PROJECT_SOURCE_DIR}/src/*.cpp)
foreach(INPUTFILE ${COIN_SRC_FILES})
	create_testsuite(${INPUTFILE})
endforeach()

# Create test cases for all scenes under models folder (this replaces StandardTests.cpp).
# The original StandardTests.cpp also tested additional folders:
# - "killers" with testInCorrectFile
# - "slackers" with testOutOfSpecFile
# However, those folders are not in the repository.
create_file_test("models" "testCorrectFile" false "incorrect")
# bug039.iv and bug055-5.iv contain errors but load anyway: ignore for now
create_file_test("models/io/incorrect" "testIncorrectFile" true "(bug039|bug055-5)")

# Include all extracted '*Tests.cpp' files in the target.
FILE(GLOB COIN_TEST_SOURCES "${CMAKE_CURRENT_BINARY_DIR}/*Test.cpp")

add_executable(CoinTests TestSuiteMain.cpp TestSuiteUtils.cpp TestSuiteMisc.cpp ${COIN_TEST_SOURCES})
set_target_properties(CoinTests PROPERTIES DEBUG_POSTFIX "${CMAKE_DEBUG_POSTFIX}")
target_link_libraries(CoinTests Coin ${COIN_TARGET_LINK_LIBRARIES})
target_include_directories(CoinTests PRIVATE
	${CMAKE_CURRENT_SOURCE_DIR}
	${PROJECT_SOURCE_DIR}/include
	${PROJECT_SOURCE_DIR}/include/Inventor/annex
	${PROJECT_BINARY_DIR}/include
	${COIN_TARGET_INCLUDE_DIRECTORIES}
)
if(NOT WIN32)
	target_sources(CoinTests PRIVATE GLUWrapperTest.cpp)
	target_include_directories(CoinTests PRIVATE
		${PROJECT_SOURCE_DIR}/src
		${PROJECT_BINARY_DIR}/src
	)
endif()
if (USE_PTHREAD)
	target_link_libraries(CoinTests pthread)
endif()
add_test(NAME CoinTests COMMAND CoinTests)

function(coin_add_egl_test)
	cmake_parse_arguments(ARG "" "NAME" "SOURCES;LABELS" ${ARGN})
	if(NOT ARG_NAME OR NOT ARG_SOURCES)
		message(FATAL_ERROR "coin_add_egl_test requires NAME and SOURCES")
	endif()
	add_executable(${ARG_NAME} ${ARG_SOURCES})
	target_link_libraries(${ARG_NAME} PRIVATE Coin OpenGL::EGL)
	target_compile_definitions(${ARG_NAME} PRIVATE
		COIN_INTERNAL
		COIN_TEST_SKIP_RETURN_CODE=${COIN_TEST_SKIP_RETURN_CODE})
	target_include_directories(${ARG_NAME} PRIVATE
		${PROJECT_SOURCE_DIR}/src)
	add_test(NAME ${ARG_NAME} COMMAND ${ARG_NAME})
	set(test_labels "egl")
	if(ARG_LABELS)
		list(APPEND test_labels ${ARG_LABELS})
	endif()
	set_tests_properties(${ARG_NAME} PROPERTIES
		SKIP_RETURN_CODE ${COIN_TEST_SKIP_RETURN_CODE}
		LABELS "${test_labels}")
endfunction()

if(HAVE_EGL AND CMAKE_SYSTEM_NAME STREQUAL "Linux")
	coin_add_egl_test(NAME EGLBindingTest SOURCES EGLBindingTest.cpp
		LABELS requires-egl)
endif()

# These tests inspect private renderer state through test-only symbols in the
# Coin library. Keep them off Windows until that policy is testable without
# exporting private instrumentation from the Coin DLL.
if(NOT WIN32)
	add_executable(CoinFaceMaterialTests CoinFaceMaterialTests.cpp)
	set_target_properties(CoinFaceMaterialTests PROPERTIES DEBUG_POSTFIX "${CMAKE_DEBUG_POSTFIX}")
	target_link_libraries(CoinFaceMaterialTests Coin ${COIN_TARGET_LINK_LIBRARIES})
	target_include_directories(CoinFaceMaterialTests PRIVATE
		${PROJECT_SOURCE_DIR}/include
		${PROJECT_BINARY_DIR}/include
		${PROJECT_SOURCE_DIR}/src/shapenodes
		${COIN_TARGET_INCLUDE_DIRECTORIES}
	)
	target_compile_definitions(CoinFaceMaterialTests PRIVATE COIN_FACE_MATERIAL_TESTING)
	if (USE_PTHREAD)
		target_link_libraries(CoinFaceMaterialTests pthread)
	endif()

	function(add_face_material_test test_name case_name strategy)
		cmake_parse_arguments(FACE "" "MAX_GROUPS;MIN_UNIFIED_TRIANGLES" "" ${ARGN})
		set(test_environment
			COIN_GLX_PIXMAP_DIRECT_RENDERING=1
			COIN_FACE_MATERIAL_STRATEGY=${strategy}
		)
		if(DEFINED FACE_MAX_GROUPS)
			list(APPEND test_environment
				COIN_FACE_MATERIAL_MAX_GROUPS=${FACE_MAX_GROUPS})
		endif()
		if(DEFINED FACE_MIN_UNIFIED_TRIANGLES)
			list(APPEND test_environment
				COIN_FACE_MATERIAL_MIN_UNIFIED_TRIANGLES=${FACE_MIN_UNIFIED_TRIANGLES})
		endif()
		add_test(NAME ${test_name}
			COMMAND ${CMAKE_COMMAND} -E env
				${test_environment}
				$<TARGET_FILE:CoinFaceMaterialTests> ${case_name})
		set_tests_properties(${test_name} PROPERTIES
			SKIP_RETURN_CODE 77)
	endfunction()

	add_face_material_test(CoinFaceMaterial_nonzero_material nonzero-material auto)
	add_face_material_test(CoinFaceMaterial_same_packed_color same-packed-color auto)
	add_face_material_test(CoinFaceMaterial_asymmetric_rgba asymmetric-rgba auto)
	add_face_material_test(CoinFaceMaterial_forced_overall nonzero-material overall)
	add_face_material_test(CoinFaceMaterial_forced_grouped two-colors grouped)
	add_face_material_test(CoinFaceMaterial_forced_unified two-colors unified)
	add_face_material_test(CoinFaceMaterial_forced_fallback two-colors fallback)
	add_face_material_test(CoinFaceMaterial_auto_small_fallback small-fallback auto
		MAX_GROUPS 1 MIN_UNIFIED_TRIANGLES 100000)
	add_face_material_test(CoinFaceMaterial_mutation mutation unified)
	add_face_material_test(CoinFaceMaterial_custom_attribute custom-attribute unified)
	add_face_material_test(CoinFaceMaterial_texture texture unified)
	add_face_material_test(CoinFaceMaterial_transparent transparent unified)
endif()

# Many warnings are generated from test macros on macOS with Xcode.
include(CheckCXXCompilerFlag)
CHECK_CXX_COMPILER_FLAG(-Wtautological-compare DISABLE_WARNING_TAUTOLOGCOMPARE)
if(DISABLE_WARNING_TAUTOLOGCOMPARE)
	target_compile_options(CoinTests PUBLIC -Wno-tautological-compare)
endif()
