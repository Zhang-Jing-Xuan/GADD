# Original code: https://github.com/pytorch/vision/blob/master/torchvision/models/resnet.py

import torch.nn.functional as F
import torch.nn as nn
import math


def conv3x3(in_planes, out_planes, stride=1):
    "3x3 convolution with padding"
    return nn.Conv2d(in_planes, out_planes, kernel_size=3, stride=stride, padding=1, bias=False)


def normalization(inplanes, norm_type):
    if norm_type == 'batch':
        bn = nn.BatchNorm2d(inplanes)
    elif norm_type == 'instance':
        bn = nn.GroupNorm(inplanes, inplanes)
    else:
        raise AssertionError(f"Check normalization type! {norm_type}")
    return bn


class IntroBlock(nn.Module):
    def __init__(self, size, planes, norm_type, nch=3):
        super(IntroBlock, self).__init__()
        self.size = size
        if size == 'large':
            self.conv1 = nn.Conv2d(nch, planes, kernel_size=7, stride=2, padding=3, bias=False)
            self.bn1 = normalization(planes, norm_type)
            self.relu = nn.ReLU(inplace=True)
            self.pool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        elif size == 'mid':
            self.conv1 = nn.Conv2d(nch, planes, kernel_size=3, stride=1, padding=1, bias=False)
            self.bn1 = normalization(planes, norm_type)
            self.relu = nn.ReLU(inplace=True)
            self.pool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        elif size == 'small':
            self.conv1 = nn.Conv2d(nch, planes, kernel_size=3, stride=1, padding=1, bias=False)
            self.bn1 = normalization(planes, norm_type)
            self.relu = nn.ReLU(inplace=True)
        else:
            raise AssertionError("Check network size type!")

    def forward(self, x):
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        if self.size != 'small':
            x = self.pool(x)

        return x


class BasicBlock(nn.Module):
    expansion = 1

    def __init__(self, inplanes, planes, norm_type='batch', stride=1, downsample=None):
        super(BasicBlock, self).__init__()
        self.conv1 = conv3x3(inplanes, planes, stride)
        self.bn1 = normalization(planes, norm_type)
        self.conv2 = conv3x3(planes, planes)
        self.bn2 = normalization(planes, norm_type)
        self.relu = nn.ReLU(inplace=True)

        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


class Bottleneck(nn.Module):
    expansion = 4

    def __init__(self, inplanes, planes, norm_type='batch', stride=1, downsample=None):
        super(Bottleneck, self).__init__()

        self.conv1 = nn.Conv2d(inplanes, planes, kernel_size=1, bias=False)
        self.bn1 = normalization(planes, norm_type)
        self.conv2 = nn.Conv2d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = normalization(planes, norm_type)
        self.conv3 = nn.Conv2d(planes, planes * Bottleneck.expansion, kernel_size=1, bias=False)
        self.bn3 = normalization(planes * Bottleneck.expansion, norm_type)
        self.relu = nn.ReLU(inplace=True)

        self.downsample = downsample
        self.stride = stride

    def forward(self, x):
        residual = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)
        out = self.relu(out)

        out = self.conv3(out)
        out = self.bn3(out)

        if self.downsample is not None:
            residual = self.downsample(x)

        out += residual
        out = self.relu(out)

        return out


class ResNet(nn.Module):
    def __init__(self, dataset, depth, num_classes, norm_type='batch', size=-1, nch=3):
        super(ResNet, self).__init__()
        self.dataset = dataset
        self.norm_type = norm_type

        if self.dataset.startswith('cifar') or (0 < size and size <= 64):
            self.net_size = 'small'
        elif (64 < size and size <= 128):
            self.net_size = 'mid'
        else:
            self.net_size = 'large'

        
        if self.dataset.startswith('cifar'):
            self.inplanes = 32
            n = int((depth - 2) / 6)
            block = BasicBlock

            self.layer0 = IntroBlock(self.net_size, self.inplanes, norm_type, nch=nch)
            self.layer1 = self._make_layer(block, 32, n, stride=1)
            self.layer2 = self._make_layer(block, 64, n, stride=2)
            self.layer3 = self._make_layer(block, 128, n, stride=2)
            self.layer4 = self._make_layer(block, 256, n, stride=2)
            self.avgpool = nn.AvgPool2d(4)
            self.fc = nn.Linear(256 * block.expansion, num_classes)

        else:
            blocks = {
                10: BasicBlock,
                18: BasicBlock,
                34: BasicBlock,
                50: Bottleneck,
                101: Bottleneck,
                152: Bottleneck,
                200: Bottleneck
            }
            layers = {
                10: [1, 1, 1, 1],
                18: [2, 2, 2, 2],
                34: [3, 4, 6, 3],
                50: [3, 4, 6, 3],
                101: [3, 4, 23, 3],
                152: [3, 8, 36, 3],
                200: [3, 24, 36, 3]
            }
            assert layers[
                depth], 'invalid detph for ResNet (depth should be one of 18, 34, 50, 101, 152, and 200)'

            self.inplanes = 64

            self.layer0 = IntroBlock(self.net_size, self.inplanes, norm_type, nch=nch)
            self.layer1 = self._make_layer(blocks[depth], 64, layers[depth][0])
            self.layer2 = self._make_layer(blocks[depth], 128, layers[depth][1], stride=2)
            self.layer3 = self._make_layer(blocks[depth], 256, layers[depth][2], stride=2)
            self.layer4 = self._make_layer(blocks[depth], 512, layers[depth][3], stride=2)
            self.avgpool = nn.AvgPool2d(7)
            self.fc = nn.Linear(512 * blocks[depth].expansion, num_classes)

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                n = m.kernel_size[0] * m.kernel_size[1] * m.out_channels
                m.weight.data.normal_(0, math.sqrt(2. / n))
            elif isinstance(m, nn.BatchNorm2d) or isinstance(m, nn.GroupNorm):
                m.weight.data.fill_(1)
                m.bias.data.zero_()

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion:
            downsample = nn.Sequential(
                nn.Conv2d(self.inplanes,
                          planes * block.expansion,
                          kernel_size=1,
                          stride=stride,
                          bias=False),
                normalization(planes * block.expansion, self.norm_type),
            )

        layers = []
        layers.append(
            block(self.inplanes,
                  planes,
                  norm_type=self.norm_type,
                  stride=stride,
                  downsample=downsample))
        self.inplanes = planes * block.expansion
        for i in range(1, blocks):
            layers.append(block(self.inplanes, planes, norm_type=self.norm_type))

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.layer0(x)
        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = F.avg_pool2d(x, x.shape[-1])
        x = x.view(x.size(0), -1)
        x = self.fc(x)

        return x

    def get_feature(self, x, idx_from, idx_to=-1):
        if idx_to == -1:
            idx_to = idx_from

        features = []
        x = self.layer0(x)
        features.append(x)  # starts from 0
        if idx_to < len(features):
            return features[idx_from:idx_to + 1]

        x = self.layer1(x)
        features.append(x)
        if idx_to < len(features):
            return features[idx_from:idx_to + 1]

        x = self.layer2(x)
        features.append(x)
        if idx_to < len(features):
            return features[idx_from:idx_to + 1]

        x = self.layer3(x)
        features.append(x)
        if idx_to < len(features):
            return features[idx_from:idx_to + 1]

        x = self.layer4(x)
        features.append(x)
        if idx_to < len(features):
            return features[idx_from:idx_to + 1]

        x = F.avg_pool2d(x, x.shape[-1])
        x = x.view(x.size(0), -1)
        features.append(x)
        if idx_to < len(features):
            return features[idx_from:idx_to + 1]

        x = self.fc(x)
        features.append(x)  # logit is 6
        return features[idx_from:idx_to + 1]


if __name__ == "__main__":
    import torch

    dataset = 'imagenet'
    depth = 10
    num_classes = 10
    size = 56
    norm_type = 'instance'

    model = ResNet(dataset, depth, num_classes, size=size, norm_type=norm_type).cuda()
    print(model)

    data = torch.ones([128, 3, size, size]).to('cuda')
    output = model(data)
    print(output.shape)