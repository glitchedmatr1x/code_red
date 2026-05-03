# Install script for directory: D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py

# Set the install prefix
if(NOT DEFINED CMAKE_INSTALL_PREFIX)
  set(CMAKE_INSTALL_PREFIX "C:/Program Files/LLVM")
endif()
string(REGEX REPLACE "/$" "" CMAKE_INSTALL_PREFIX "${CMAKE_INSTALL_PREFIX}")

# Set the install configuration name.
if(NOT DEFINED CMAKE_INSTALL_CONFIG_NAME)
  if(BUILD_TYPE)
    string(REGEX REPLACE "^[^A-Za-z0-9_]+" ""
           CMAKE_INSTALL_CONFIG_NAME "${BUILD_TYPE}")
  else()
    set(CMAKE_INSTALL_CONFIG_NAME "Release")
  endif()
  message(STATUS "Install configuration: \"${CMAKE_INSTALL_CONFIG_NAME}\"")
endif()

# Set the component getting installed.
if(NOT CMAKE_INSTALL_COMPONENT)
  if(COMPONENT)
    message(STATUS "Install component: \"${COMPONENT}\"")
    set(CMAKE_INSTALL_COMPONENT "${COMPONENT}")
  else()
    set(CMAKE_INSTALL_COMPONENT)
  endif()
endif()

# Is this installation the result of a crosscompile?
if(NOT DEFINED CMAKE_CROSSCOMPILING)
  set(CMAKE_CROSSCOMPILING "FALSE")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/bin" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/bin/analyze-build")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/bin" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/bin/intercept-build")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/bin" TYPE PROGRAM RENAME "scan-build-py" FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/bin/scan-build")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/libexec" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/libexec/analyze-c++")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/libexec" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/libexec/analyze-cc")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/libexec" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/libexec/intercept-c++")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/libexec" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/libexec/intercept-cc")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/__init__.py")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/analyze.py")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/arguments.py")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/clang.py")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/compilation.py")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/intercept.py")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/report.py")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/shell.py")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild/resources" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/resources/scanview.css")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild/resources" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/resources/selectable.js")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libscanbuild/resources" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libscanbuild/resources/sorttable.js")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libear" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libear/__init__.py")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libear" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libear/config.h.in")
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "scan-build-py" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/libear" TYPE PROGRAM FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/tools/scan-build-py/lib/libear/ear.c")
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
if(CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/sccl_cmake_build/tools/clang/tools/scan-build-py/install_local_manifest.txt"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
