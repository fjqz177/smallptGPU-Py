# camera.py
import numpy as np
from vec import Vec


class Camera:
    """相机类，定义视角和方向，与 OpenCL 内核兼容"""

    def __init__(self):
        self.orig = Vec()  # 相机原点
        self.target = Vec()  # 目标点
        self.dir = Vec()  # 方向向量
        self.x = Vec()  # 水平向量
        self.y = Vec()  # 垂直向量

    def to_struct(self):
        """转换为 OpenCL 兼容的扁平化 float 数组"""
        return np.array(
            [
                self.orig.x,
                self.orig.y,
                self.orig.z,
                self.target.x,
                self.target.y,
                self.target.z,
                self.dir.x,
                self.dir.y,
                self.dir.z,
                self.x.x,
                self.x.y,
                self.x.z,
                self.y.x,
                self.y.y,
                self.y.z,
            ],
            dtype=np.float32,
        )
