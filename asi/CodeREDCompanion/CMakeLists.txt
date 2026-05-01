cmake_minimum_required(VERSION 3.21)

project(CodeREDCompanionASI VERSION 0.1.0 LANGUAGES CXX)

add_library(CodeREDCompanion SHARED
    src/CodeREDCompanion.cpp
)

target_compile_features(CodeREDCompanion PRIVATE cxx_std_17)

target_compile_definitions(CodeREDCompanion PRIVATE
    WIN32_LEAN_AND_MEAN
    NOMINMAX
    CODERED_COMPANION_VERSION="0.1.0-loader-proof"
)

if(MSVC)
    target_compile_options(CodeREDCompanion PRIVATE /W4 /permissive-)
else()
    target_compile_options(CodeREDCompanion PRIVATE -Wall -Wextra -Wpedantic)
endif()

set_target_properties(CodeREDCompanion PROPERTIES
    OUTPUT_NAME "CodeREDCompanion"
    PREFIX ""
    SUFFIX ".asi"
)

# Keep the artifact path predictable across Visual Studio multi-config builds.
foreach(config DEBUG RELEASE RELWITHDEBINFO MINSIZEREL)
    set_target_properties(CodeREDCompanion PROPERTIES
        RUNTIME_OUTPUT_DIRECTORY_${config} "${CMAKE_BINARY_DIR}/dist/${config}"
        LIBRARY_OUTPUT_DIRECTORY_${config} "${CMAKE_BINARY_DIR}/dist/${config}"
        ARCHIVE_OUTPUT_DIRECTORY_${config} "${CMAKE_BINARY_DIR}/dist/${config}"
    )
endforeach()
