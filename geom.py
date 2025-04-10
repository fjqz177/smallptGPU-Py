# geom.py
import numpy as np
from vec import Vec


class Ray:
    """射线类"""

    def __init__(self):
        self.o = Vec()  # 起点
        self.d = Vec()  # 方向


class Refl:
    """反射类型枚举，与 OpenCL 内核一致"""

    DIFF = 0  # 漫反射
    SPEC = 1  # 镜面反射
    REFR = 2  # 折射


class Sphere:
    """球体类，与 OpenCL 内核兼容"""

    def __init__(self):
        """初始化球体"""
        self.rad = 0.0  # 半径
        self.p = Vec()  # 位置
        self.e = Vec()  # 发射光
        self.c = Vec()  # 颜色
        self.refl = Refl.DIFF  # 反射类型

    def to_struct(self):
        """转换为 OpenCL 兼容的结构化数组"""
        return np.array(
            (
                self.rad,
                (self.p.x, self.p.y, self.p.z),
                (self.e.x, self.e.y, self.e.z),
                (self.c.x, self.c.y, self.c.z),
                self.refl,
            ),
            dtype=[
                ("rad", "f4"),
                ("p", "3f4"),
                ("e", "3f4"),
                ("c", "3f4"),
                ("refl", "i4"),
            ],
        )
