from __future__ import print_function, division
import os
import torch
import pandas as pd
from skimage import io, transform
import numpy as np
import matplotlib.pyplot as plt
import SimpleITK as sitk
from torch.utils.data import Dataset, DataLoader
from torchvision import transforms, utils
import csv
from constants import *

# Ignore warnings
import warnings
warnings.filterwarnings("ignore")

def load_itk_image(filename):
    itkimage = sitk.ReadImage(filename)
    numpyImage = sitk.GetArrayFromImage(itkimage)

    numpyOrigin = np.array(list(reversed(itkimage.GetOrigin())))
    numpySpacing = np.array(list(reversed(itkimage.GetSpacing())))

    return numpyImage, numpyOrigin, numpySpacing


def readCSV(filename):
    lines = []
    with open(filename, "r") as f:
        csvreader = csv.reader(f)
        for line in csvreader:
            lines.append(line)
    return lines


def worldToVoxelCoord(worldCoord, origin, spacing):
    stretchedVoxelCoord = np.absolute(worldCoord - origin)
    voxelCoord = stretchedVoxelCoord / spacing
    return voxelCoord

def voxelToWorldCoord(voxelCoord, origin, spacing):
    stretchedVoxelCoord = voxelCoord * spacing
    worldCoord = stretchedVoxelCoord + origin
    return worldCoord


def normalizePlanes(npzarray):
    maxHU = 400.
    minHU = -1000.

    # npzarray = (npzarray - minHU) / (maxHU - minHU)
    npzarray = (npzarray + 600) / (300)
    npzarray[npzarray > 1] = 1.
    npzarray[npzarray < 0] = 0.
    return npzarray

def show_center(image, center):
    plt.imshow(image)
    plt.scatter([center[1]],[center[2]], s=10, marker='.', c='r')
    plt.pause(0.001)

def file_exists(record, root_dir, subset):
    for idx in subset:
        path = os.path.join(root_dir,'subset'+str(idx), str(record[0])+'.mhd')
        if os.path.exists(path):
            return True
    return False

def get_subset(record, root_dir, subset):
    for idx in subset:
        path = os.path.join(root_dir,'subset'+str(idx), str(record[0])+'.mhd')
        if os.path.exists(path):
            return idx
    return -1

class Luna16Dataset(Dataset):
    def __init__(self, csv_file, root_dir, subset, phase, transform = None):
        self.center_frame = readCSV(csv_file)
        self.center_frame = self.center_frame[1:]
        self.root_dir = root_dir
        self.subset = subset
        self.center_frame = [record+[str(get_subset(record, self.root_dir, subset))]
                             for record in self.center_frame if file_exists(record, self.root_dir, subset)]
        pos = 0
        tot = 0
        if phase == 'train':
            for i in range(len(self.center_frame)):
                tot += 1
                if self.center_frame[i][4] == '1':
                    pos += 1
                    for _ in range(7):
                        self.center_frame.append(self.center_frame[i])
        print('positive is: '+str(pos))
        print('total is: ' + str(tot))
        self.transform = transform

    def __len__(self):
        return len(self.center_frame)

    def __getitem__(self, idx):
        # print(idx)
        cube_name = os.path.join(self.root_dir, 'subset'+self.center_frame[idx][5],
                                 self.center_frame[idx][0]+'.mhd')
        numpyImage, numpyOrigin, numpySpacing = load_itk_image(cube_name)
        cand = self.center_frame[idx]
        worldCoord = np.asarray([float(cand[3]), float(cand[2]), float(cand[1])])
        voxelCoord = worldToVoxelCoord(worldCoord, numpyOrigin, numpySpacing)
        voxelWidth = 40
        voxelDepth = 24
        numpyImage = np.lib.pad(numpyImage, ((voxelDepth // 2, voxelDepth // 2),
                   (voxelWidth // 2, voxelWidth // 2), (voxelWidth // 2, voxelWidth // 2)), 'wrap')
        coord_start = [0, 0, 0]
        coord_end = [0, 0, 0]
        coord_start[0] = int(voxelCoord[0])#  - voxelDepth / 2.0)
        coord_end[0] = int(voxelCoord[0]) + voxelDepth #  / 2.0)
        coord_start[1] = int(voxelCoord[1])  # - voxelDepth / 2.0)
        coord_end[1] = int(voxelCoord[1]) + voxelWidth  # / 2.0)
        coord_start[2] = int(voxelCoord[2])  # - voxelDepth / 2.0)
        coord_end[2] = int(voxelCoord[2]) + voxelWidth  # / 2.0)
        patch = numpyImage[coord_start[0]:coord_end[0], coord_start[1]:coord_end[1], coord_start[2]:coord_end[2]]
        # if (patch.shape[0] != 24):
#             print('zero shape ' + str(coord_start[0]) + ' ' + str(coord_end[0]))
        # print(patch.shape)
        patch = normalizePlanes(patch)
        label = int(cand[4])
        sample = {'cube':patch, 'label': label}

        if self.transform:
            sample = self.transform(sample)

        return sample

class RandomFlip(object):
    def __init__(self, output_size):
        assert isinstance(output_size, (int, tuple))
        self.output_size = output_size

    def __call__(self, sample):
        cube, label = sample['cube'], sample['label']
        z = np.random.randint(0, 2)
        x = np.random.randint(0, 2)
        y = np.random.randint(0, 2)
        if (z == 1):
            cube = np.flip(cube, 0)
        if (x == 1):
            cube = np.flip(cube, 1)
        if (y == 1):
            cube = np.flip(cube, 2)

        return {'cube':cube, 'label':label}

class RandomCrop(object):
    def __init__(self, output_size):
        assert isinstance(output_size, (int, tuple))
        if isinstance(output_size, int):
            self.output_size = (20,output_size, output_size)
        else:
            assert len(output_size) == 3
            self.output_size = output_size

    def __call__(self, sample):
        z = np.random.randint(0, 5)
        x = np.random.randint(0, 5)
        y = np.random.randint(0, 5)
        cube, label = sample['cube'], sample['label']
        cube = cube[z:z+20, x:x+36, y:y+36]
        return {'cube':cube, 'label':label}

class ToTensor(object):
    def __call__(self, sample):
        cube, label = sample['cube'], sample['label']
        cube = np.expand_dims(cube,0)
        # print('cube\' s size is '+str(cube.shape))
        # print('label\' s type is ' + str(type(label)), file=f)
        return {'cube':torch.from_numpy(cube.copy()).float(), 'label': label}

# flip = RandomFlip((20,36,36))
# crop = RandomCrop((20,36,36))
if __name__ == '__main__':
    plt.ion()  # interactive mode
    root_path = '/Users/hyacinth/Downloads/TUTORIAL/data/'
    cand_path = '/Users/hyacinth/Downloads/TUTORIAL/data/candidates.csv'

    transformed_dataset = Luna16Dataset(csv_file=cand_path, root_dir=root_path, subset=[0],
                                        transform=transforms.Compose(
                                            [RandomFlip((20, 36, 36)), RandomCrop((20, 36, 36)),
                                             ToTensor()]))
    dataloader = DataLoader(transformed_dataset, batch_size=1, shuffle=True, num_workers=4)

    for i_batch, sample_batched in enumerate(dataloader):
        print(i_batch, sample_batched['cube'].size(), sample_batched['label'].size())
        fig = plt.figure()
        img = sample_batched['cube']
        img = img[0][0][10].numpy()
        plt.imshow(img, cmap='gray')
        plt.show()

    print('ends')
