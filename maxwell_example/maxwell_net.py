# Maxwell example: simple PyTorch network -> pnnx -> ncnn
# Copyright 2026 Tencent
# SPDX-License-Identifier: BSD-3-Clause

import os
import numpy as np
import torch
import torch.nn as nn
import pnnx


class MaxwellNet(nn.Module):
    """A tiny CNN for demonstration: Conv2d + ReLU + global average pooling + Linear."""

    def __init__(self):
        super(MaxwellNet, self).__init__()
        self.conv = nn.Conv2d(3, 8, kernel_size=1)
        self.relu = nn.ReLU()
        self.fc = nn.Linear(8, 4)

    def forward(self, x):
        x = self.conv(x)
        x = self.relu(x)
        x = x.mean((2, 3))
        return self.fc(x)


def main():
    # reproducible random input
    torch.manual_seed(42)
    model = MaxwellNet().eval()
    x = torch.rand(1, 3, 32, 32)

    with torch.no_grad():
        y = model(x)

    workdir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(workdir)

    # save input and reference PyTorch output as raw float32 binaries
    x.detach().cpu().numpy().astype("float32").tofile("input_data.bin")
    y.detach().cpu().numpy().astype("float32").tofile("pytorch_output.bin")

    # also print them for the report
    print("input shape:", x.shape)
    print("pytorch output:")
    print(y.numpy())

    # export to ncnn via pnnx
    pnnx.export(model, "maxwell_model.pt", (x,))
    print("exported ncnn model:")
    print("  ", os.path.join(workdir, "maxwell_model.ncnn.param"))
    print("  ", os.path.join(workdir, "maxwell_model.ncnn.bin"))


if __name__ == "__main__":
    main()
