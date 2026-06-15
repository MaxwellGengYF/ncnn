// Maxwell example: ncnn C++ inference for a pnnx-converted PyTorch model
// Copyright 2026 Tencent
// SPDX-License-Identifier: BSD-3-Clause

#include "net.h"

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

static std::vector<float> read_binary_floats(const char* path, size_t expected_count)
{
    std::vector<float> data(expected_count);
    std::ifstream fs(path, std::ios::binary);
    if (!fs.is_open())
    {
        std::cerr << "failed to open " << path << std::endl;
        std::exit(1);
    }
    fs.read(reinterpret_cast<char*>(data.data()), expected_count * sizeof(float));
    if ((size_t)fs.gcount() != expected_count * sizeof(float))
    {
        std::cerr << "failed to read " << expected_count << " floats from " << path << std::endl;
        std::exit(1);
    }
    return data;
}

static void join_path(std::string& out, const char* dir, const char* file)
{
    out = dir;
    if (!out.empty() && out.back() != '/' && out.back() != '\\')
    {
        out += '/';
    }
    out += file;
}

int main(int argc, char** argv)
{
    const char* model_dir = ".";
    if (argc > 1)
    {
        model_dir = argv[1];
    }

    std::string param_path;
    std::string bin_path;
    std::string input_path;
    std::string ref_path;
    join_path(param_path, model_dir, "maxwell_model.ncnn.param");
    join_path(bin_path, model_dir, "maxwell_model.ncnn.bin");
    join_path(input_path, model_dir, "input_data.bin");
    join_path(ref_path, model_dir, "pytorch_output.bin");

    ncnn::Net net;
    net.opt.use_vulkan_compute = true;

    if (net.load_param(param_path.c_str()) != 0)
    {
        std::cerr << "failed to load param " << param_path << std::endl;
        return -1;
    }
    if (net.load_model(bin_path.c_str()) != 0)
    {
        std::cerr << "failed to load model " << bin_path << std::endl;
        return -1;
    }

    const int w = 32;
    const int h = 32;
    const int c = 3;
    std::vector<float> input_data = read_binary_floats(input_path.c_str(), w * h * c);

    // ncnn::Mat(w, h, c, data) shares the same NCHW layout as PyTorch
    ncnn::Mat in(w, h, c, input_data.data());

    ncnn::Extractor ex = net.create_extractor();
    ex.input("in0", in);

    ncnn::Mat out;
    int ret = ex.extract("out0", out);
    if (ret != 0)
    {
        std::cerr << "extract failed, ret=" << ret << std::endl;
        return -1;
    }

    std::vector<float> ref_output = read_binary_floats(ref_path.c_str(), out.w);

    std::cout << "ncnn output:   ";
    float max_diff = 0.f;
    for (int i = 0; i < out.w; i++)
    {
        std::cout << out[i] << " ";
        float diff = std::fabs(out[i] - ref_output[i]);
        if (diff > max_diff)
        {
            max_diff = diff;
        }
    }
    std::cout << std::endl;

    std::cout << "pytorch output:";
    for (float v : ref_output)
    {
        std::cout << " " << v;
    }
    std::cout << std::endl;

    std::cout << "max diff = " << max_diff << std::endl;

    if (max_diff < 1e-3f)
    {
        std::cout << "PASS: outputs match" << std::endl;
        return 0;
    }
    else
    {
        std::cout << "FAIL: outputs differ too much" << std::endl;
        return 1;
    }
}
