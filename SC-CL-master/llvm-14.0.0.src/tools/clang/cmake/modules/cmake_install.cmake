# Install script for directory: D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/cmake/modules

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

if(CMAKE_INSTALL_COMPONENT STREQUAL "clang-cmake-exports" OR NOT CMAKE_INSTALL_COMPONENT)
  if(EXISTS "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/cmake/clang/ClangTargets.cmake")
    file(DIFFERENT _cmake_export_file_changed FILES
         "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/cmake/clang/ClangTargets.cmake"
         "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/sccl_cmake_build/tools/clang/cmake/modules/CMakeFiles/Export/c1119db3fad74e49663c818a9c468e27/ClangTargets.cmake")
    if(_cmake_export_file_changed)
      file(GLOB _cmake_old_config_files "$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/cmake/clang/ClangTargets-*.cmake")
      if(_cmake_old_config_files)
        string(REPLACE ";" ", " _cmake_old_config_files_text "${_cmake_old_config_files}")
        message(STATUS "Old export file \"$ENV{DESTDIR}${CMAKE_INSTALL_PREFIX}/lib/cmake/clang/ClangTargets.cmake\" will be replaced.  Removing files [${_cmake_old_config_files_text}].")
        unset(_cmake_old_config_files_text)
        file(REMOVE ${_cmake_old_config_files})
      endif()
      unset(_cmake_old_config_files)
    endif()
    unset(_cmake_export_file_changed)
  endif()
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/cmake/clang" TYPE FILE FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/sccl_cmake_build/tools/clang/cmake/modules/CMakeFiles/Export/c1119db3fad74e49663c818a9c468e27/ClangTargets.cmake")
  if(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Dd][Ee][Bb][Uu][Gg])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/cmake/clang" TYPE FILE FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/sccl_cmake_build/tools/clang/cmake/modules/CMakeFiles/Export/c1119db3fad74e49663c818a9c468e27/ClangTargets-debug.cmake")
  endif()
  if(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Mm][Ii][Nn][Ss][Ii][Zz][Ee][Rr][Ee][Ll])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/cmake/clang" TYPE FILE FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/sccl_cmake_build/tools/clang/cmake/modules/CMakeFiles/Export/c1119db3fad74e49663c818a9c468e27/ClangTargets-minsizerel.cmake")
  endif()
  if(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Rr][Ee][Ll][Ww][Ii][Tt][Hh][Dd][Ee][Bb][Ii][Nn][Ff][Oo])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/cmake/clang" TYPE FILE FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/sccl_cmake_build/tools/clang/cmake/modules/CMakeFiles/Export/c1119db3fad74e49663c818a9c468e27/ClangTargets-relwithdebinfo.cmake")
  endif()
  if(CMAKE_INSTALL_CONFIG_NAME MATCHES "^([Rr][Ee][Ll][Ee][Aa][Ss][Ee])$")
    file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/cmake/clang" TYPE FILE FILES "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/sccl_cmake_build/tools/clang/cmake/modules/CMakeFiles/Export/c1119db3fad74e49663c818a9c468e27/ClangTargets-release.cmake")
  endif()
endif()

if(CMAKE_INSTALL_COMPONENT STREQUAL "clang-cmake-exports" OR NOT CMAKE_INSTALL_COMPONENT)
  file(INSTALL DESTINATION "${CMAKE_INSTALL_PREFIX}/lib/cmake/clang" TYPE FILE FILES
    "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/sccl_cmake_build/tools/clang/cmake/modules/CMakeFiles/ClangConfig.cmake"
    "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/SC-CL-master/llvm-14.0.0.src/tools/clang/cmake/modules/AddClang.cmake"
    )
endif()

string(REPLACE ";" "\n" CMAKE_INSTALL_MANIFEST_CONTENT
       "${CMAKE_INSTALL_MANIFEST_FILES}")
if(CMAKE_INSTALL_LOCAL_ONLY)
  file(WRITE "D:/Games/Red Dead Redemption/Code Red/Code_RED/data/code_red_sccl_attempt_bundle_v1/code_red_sccl_windows_build_kit_v1/output/sccl_cmake_build/tools/clang/cmake/modules/install_local_manifest.txt"
     "${CMAKE_INSTALL_MANIFEST_CONTENT}")
endif()
