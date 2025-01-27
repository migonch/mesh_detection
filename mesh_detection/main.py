import sys
from pathlib import Path
import numpy as np
from functools import partial

import torch
import torch.nn as nn
from torch.optim import Adam

from mesh_detection.dataset import FaceDataset
from mesh_detection.batch_iter import batch_iterator
from mesh_detection.utils import add_channel_dim, randomly_shift
from mesh_detection.split import stratified_train_val_test_split
from mesh_detection.model import BitNet
from mesh_detection.train import validator, train, criterion
from mesh_detection.metric import l2

from dpipe.layers import ResBlock2d


device = 'cuda' if torch.cuda.is_available() else 'cpu'

if __name__ == '__main__':
    experiment_path = Path(sys.argv[1])
    experiment_path.mkdir(exist_ok=True)

    data_path = Path('~/kaggle_face/training.csv')
    dataset = FaceDataset(data_path)
    contain_nans = [np.any(np.isnan(dataset.load_key_points(i))) for i in dataset.ids]
    train_ids, val_ids, test_ids = stratified_train_val_test_split(dataset.ids, labels=contain_nans, random_state=42)[0]

    iterate_batches = batch_iterator(dataset.load_image, dataset.load_key_points, train_ids, 50, randomly_shift, add_channel_dim)

    stucture = [
        [[1, 16, 16],                       [16]],
            [[16, 32, 32],                  [32]],
                [[32, 64, 64],              [64]],
                    [[64, 128, 128],        [128]],
                        [[128, 256, 256],   [256]],
                            [256, 512, 512]
    ]

    n_points = 15
    conv_block = partial(ResBlock2d, kernel_size=3, padding=1)
    pooling = partial(nn.MaxPool2d, kernel_size=2)

    model = BitNet(stucture, n_points, conv_block, pooling).to(device)

    # hyper-parameters
    lr = 1e-3
    n_epochs = 50

    optimizer = Adam(model.parameters(), lr=lr)
    validate = validator(val_ids, dataset.load_image, dataset.load_key_points, {'l2': l2})
    model, losses, val_metrics = train(model, iterate_batches, optimizer, criterion, n_epochs, validate)

    torch.save(model.state_dict(), experiment_path / 'model.pth')
    np.save(experiment_path / 'losses.npy', losses)
    np.save(experiment_path / 'val_metrics.npy', val_metrics)

