from typing import Tuple, Optional
import torch
import torch.nn as nn
import torch.nn.functional as F


class PlantDiseaseCNN(nn.Module):
    def __init__(self, num_classes: int = 38, embedding_dim: int = 128):
        super(PlantDiseaseCNN, self).__init__()
        self.num_classes = num_classes
        self.embedding_dim = embedding_dim

        self.conv1 = nn.Conv2d(3, 32, kernel_size=3, padding=1)
        self.bn1 = nn.BatchNorm2d(32)
        self.pool1 = nn.MaxPool2d(2, 2)

        self.conv2 = nn.Conv2d(32, 64, kernel_size=3, padding=1)
        self.bn2 = nn.BatchNorm2d(64)
        self.pool2 = nn.MaxPool2d(2, 2)

        self.conv3 = nn.Conv2d(64, 128, kernel_size=3, padding=1)
        self.bn3 = nn.BatchNorm2d(128)
        self.pool3 = nn.MaxPool2d(2, 2)

        self.conv4 = nn.Conv2d(128, 256, kernel_size=3, padding=1)
        self.bn4 = nn.BatchNorm2d(256)
        self.pool4 = nn.MaxPool2d(2, 2)

        self.gap = nn.AdaptiveAvgPool2d((1, 1))

        self.fc_embedding = nn.Linear(256, embedding_dim)
        self.bn_emb = nn.BatchNorm1d(embedding_dim)

        self.classifier = nn.Linear(embedding_dim, num_classes)
        self.dropout = nn.Dropout(0.3)

    def extract_features(self, x: torch.Tensor) -> torch.Tensor:
        x = self.pool1(F.relu(self.bn1(self.conv1(x))))
        x = self.pool2(F.relu(self.bn2(self.conv2(x))))
        x = self.pool3(F.relu(self.bn3(self.conv3(x))))
        x = self.pool4(F.relu(self.bn4(self.conv4(x))))
        x = self.gap(x)
        x = torch.flatten(x, 1)

        emb = F.relu(self.bn_emb(self.fc_embedding(x)))
        emb_norm = F.normalize(emb, p=2, dim=1)
        return emb_norm

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        emb = self.extract_features(x)
        x_drop = self.dropout(emb)
        logits = self.classifier(x_drop)
        return logits, emb


def get_model(num_classes: int = 38, embedding_dim: int = 128) -> PlantDiseaseCNN:
    return PlantDiseaseCNN(num_classes=num_classes, embedding_dim=embedding_dim)
