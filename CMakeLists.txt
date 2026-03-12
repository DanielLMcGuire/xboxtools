cmake_minimum_required(VERSION 3.10)

project(XboxDev C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_executable(amdcpuid cpu.c)
add_executable(xboxkrnlid krnl.c)