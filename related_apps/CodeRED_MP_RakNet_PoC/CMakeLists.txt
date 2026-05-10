cmake_minimum_required(VERSION 3.16)

project(CodeRED_MP_SLikeNet_PoC LANGUAGES C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CODE_RED_SLIKENET_ROOT "$ENV{CODE_RED_SLIKENET_ROOT}" CACHE PATH "Path to SLikeNet root")
if(NOT CODE_RED_SLIKENET_ROOT)
  set(CODE_RED_SLIKENET_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/third_party/slikenet")
endif()

if(NOT EXISTS "${CODE_RED_SLIKENET_ROOT}/CMakeLists.txt")
  message(FATAL_ERROR "CODE_RED_SLIKENET_ROOT does not point to SLikeNet: ${CODE_RED_SLIKENET_ROOT}")
endif()

set(CODE_RED_PAWN_ROOT "$ENV{CODE_RED_PAWN_ROOT}" CACHE PATH "Path to Pawn root, e.g. open.mp/lib/pawn")
if(NOT CODE_RED_PAWN_ROOT)
  set(CODE_RED_PAWN_ROOT "/home/chairman/Projects/omp-ipv6/open.mp/lib/pawn")
endif()

if(NOT EXISTS "${CODE_RED_PAWN_ROOT}/source/amx/amx.c")
  message(FATAL_ERROR "CODE_RED_PAWN_ROOT does not point to an open.mp/CompuPhase Pawn tree: ${CODE_RED_PAWN_ROOT}")
endif()

file(GLOB CODE_RED_SLIKENET_SOURCES CONFIGURE_DEPENDS
  "${CODE_RED_SLIKENET_ROOT}/Source/src/*.cpp"
)
list(FILTER CODE_RED_SLIKENET_SOURCES EXCLUDE REGEX "/Source/src/crypto/")

add_library(codered_slikenet_core STATIC ${CODE_RED_SLIKENET_SOURCES})
target_compile_features(codered_slikenet_core PUBLIC cxx_std_11)
target_compile_definitions(codered_slikenet_core PUBLIC _RETAIL)
target_include_directories(codered_slikenet_core
  BEFORE PUBLIC
    "${CMAKE_CURRENT_SOURCE_DIR}/include/codered_mp/compat/mingw"
)
target_include_directories(codered_slikenet_core
  PUBLIC
    "${CODE_RED_SLIKENET_ROOT}/Source"
    "${CODE_RED_SLIKENET_ROOT}/Source/include"
)
if(WIN32)
  target_compile_definitions(codered_slikenet_core PUBLIC WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS SHA1_HAS_TCHAR)
  target_link_libraries(codered_slikenet_core PUBLIC ws2_32 iphlpapi)
else()
  target_link_libraries(codered_slikenet_core PUBLIC pthread)
endif()

add_library(codered_pawn_amx STATIC
  "${CODE_RED_PAWN_ROOT}/source/amx/amx.c"
  "${CODE_RED_PAWN_ROOT}/source/amx/amxaux.c"
  "${CODE_RED_PAWN_ROOT}/source/amx/amxcore.c"
  "${CODE_RED_PAWN_ROOT}/source/amx/amxfloat.c"
)
target_compile_definitions(codered_pawn_amx
  PUBLIC
    PAWN_CELL_SIZE=32
    HAVE_STDINT_H
    HAVE_INTTYPES_H
    AMX_NODYNALOAD
)
target_include_directories(codered_pawn_amx
  PUBLIC
    "${CODE_RED_PAWN_ROOT}/source/amx"
    "${CODE_RED_PAWN_ROOT}/source/linux"
)
if(UNIX)
  target_compile_definitions(codered_pawn_amx PUBLIC LINUX HAVE_UNISTD_H HAVE_ALLOCA_H)
endif()
if(WIN32)
  target_compile_definitions(codered_pawn_amx PUBLIC HAVE_ALLOCA_H=0)
endif()

add_library(codered_mp_protocol STATIC
  src/protocol.cpp
)
target_include_directories(codered_mp_protocol
  PUBLIC
    include
    "${CODE_RED_SLIKENET_ROOT}/Source"
    "${CODE_RED_SLIKENET_ROOT}/Source/include"
)
target_link_libraries(codered_mp_protocol PUBLIC codered_slikenet_core)

add_library(codered_mp_client_stack STATIC
  src/client_net_stack.cpp
)
target_include_directories(codered_mp_client_stack
  PUBLIC
    include
)
target_link_libraries(codered_mp_client_stack PUBLIC codered_mp_protocol)

add_library(codered_mp_pawn_host STATIC
  src/pawn_host.cpp
)
target_include_directories(codered_mp_pawn_host
  PUBLIC
    include
)
target_link_libraries(codered_mp_pawn_host PUBLIC codered_mp_protocol codered_pawn_amx)

add_executable(codered-mp-server
  src/server_main.cpp
)
target_link_libraries(codered-mp-server PRIVATE codered_mp_protocol codered_mp_pawn_host)

add_executable(codered-mp-client
  src/client_main.cpp
)
target_link_libraries(codered-mp-client PRIVATE codered_mp_client_stack)

if(MINGW)
  target_link_options(codered-mp-server PRIVATE -static -static-libgcc -static-libstdc++)
  target_link_options(codered-mp-client PRIVATE -static -static-libgcc -static-libstdc++)
endif()

if(WIN32)
  target_compile_definitions(codered_mp_protocol PUBLIC WIN32_LEAN_AND_MEAN _CRT_SECURE_NO_WARNINGS)
endif()
