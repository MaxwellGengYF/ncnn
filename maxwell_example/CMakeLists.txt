# Maxwell example: PyTorch -> pnnx -> ncnn C++ inference
# Copyright 2026 Tencent
# SPDX-License-Identifier: BSD-3-Clause

add_executable(maxwell_example maxwell_example.cpp)

target_include_directories(maxwell_example PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/../src
    ${CMAKE_CURRENT_BINARY_DIR}/../src
)

target_link_libraries(maxwell_example PRIVATE ncnn)

set_property(TARGET maxwell_example PROPERTY FOLDER "maxwell_example")
