cmake_minimum_required(VERSION 3.15)

project(XboxDev C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded$<$<CONFIG:Debug>:Debug>")

add_executable(amdcpuid amd_cpu_enum.c)
add_executable(xkrnlid nt_krnl_xhook.c)
add_executable(clockspd tsc_enum.c)