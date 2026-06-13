# pnnx model stat
# model inputshape = [1,3,32,32]f32
# FLOPS = 73.804K
# memory OPS = 35.928K

import os
import numpy as np
import tempfile, zipfile
import torch
import torch.nn as nn
import torch.nn.functional as F
try:
    import torchvision
    import torchaudio
except:
    pass

class Model(nn.Module):
    def __init__(self):
        super(Model, self).__init__()

        self.conv = nn.Conv2d(bias=True, dilation=(1,1), groups=1, in_channels=3, kernel_size=(1,1), out_channels=8, padding=(0,0), padding_mode='zeros', stride=(1,1))
        self.relu = nn.ReLU()
        self.fc = nn.Linear(bias=True, in_features=8, out_features=4)

        archive = zipfile.ZipFile('maxwell_model.pnnx.bin', 'r')
        self.conv.bias = self.load_pnnx_bin_as_parameter(archive, 'conv.bias', (8), 'float32')
        self.conv.weight = self.load_pnnx_bin_as_parameter(archive, 'conv.weight', (8,3,1,1), 'float32')
        self.fc.bias = self.load_pnnx_bin_as_parameter(archive, 'fc.bias', (4), 'float32')
        self.fc.weight = self.load_pnnx_bin_as_parameter(archive, 'fc.weight', (4,8), 'float32')
        archive.close()

    def load_pnnx_bin_as_parameter(self, archive, key, shape, dtype, requires_grad=True):
        return nn.Parameter(self.load_pnnx_bin_as_tensor(archive, key, shape, dtype), requires_grad)

    def load_pnnx_bin_as_tensor(self, archive, key, shape, dtype):
        fd, tmppath = tempfile.mkstemp()
        with os.fdopen(fd, 'wb') as tmpf, archive.open(key) as keyfile:
            tmpf.write(keyfile.read())
        m = np.memmap(tmppath, dtype=dtype, mode='r', shape=shape).copy()
        os.remove(tmppath)
        return torch.from_numpy(m)

    def forward(self, v_0):
        v_1 = self.conv(v_0)
        v_2 = self.relu(v_1)
        v_3 = torch.mean(v_2, dim=(2,3), keepdim=False)
        v_4 = self.fc(v_3)
        return v_4

def export_torchscript():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 3, 32, 32, dtype=torch.float)

    mod = torch.jit.trace(net, v_0)
    mod.save("maxwell_model_pnnx.py.pt")

def export_onnx():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 3, 32, 32, dtype=torch.float)

    torch.onnx.export(net, v_0, "maxwell_model_pnnx.py.onnx", export_params=True, operator_export_type=torch.onnx.OperatorExportTypes.ONNX_ATEN_FALLBACK, opset_version=13, input_names=['in0'], output_names=['out0'])

def export_pnnx():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 3, 32, 32, dtype=torch.float)

    import pnnx
    pnnx.export(net, "maxwell_model_pnnx.py.pt", v_0)

def export_ncnn():
    export_pnnx()

@torch.no_grad()
def test_inference():
    net = Model()
    net.float()
    net.eval()

    torch.manual_seed(0)
    v_0 = torch.rand(1, 3, 32, 32, dtype=torch.float)

    return net(v_0)

if __name__ == "__main__":
    print(test_inference())
