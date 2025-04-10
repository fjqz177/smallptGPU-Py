# vec.py
# 向量操作模块，移植自 vec.h
import numpy as np


class Vec:
    """三维向量类，用于表示位置或颜色"""

    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def __add__(self, other):
        """向量加法"""
        return Vec(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other):
        """向量减法"""
        return Vec(self.x - other.x, self.y - other.y, self.z - other.z)

    def __mul__(self, other):
        """向量逐元素乘法或标量乘法"""
        if isinstance(other, Vec):
            return Vec(self.x * other.x, self.y * other.y, self.z * other.z)
        return Vec(self.x * other, self.y * other, self.z * other)

    def __rmul__(self, other):
        """右标量乘法"""
        return self.__mul__(other)

    def dot(self, other):
        """点积"""
        return self.x * other.x + self.y * other.y + self.z * other.z

    def norm(self):
        """向量归一化"""
        length = np.sqrt(self.dot(self))
        if length > 0:
            self.x /= length
            self.y /= length
            self.z /= length
        return self

    def cross(self, other):
        """叉积"""
        return Vec(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    def to_array(self):
        """转换为 NumPy 数组"""
        return np.array([self.x, self.y, self.z], dtype=np.float32)


# 以下为兼容 C++ 宏的函数
def vinit(v, a, b, c):
    """初始化向量"""
    v.x, v.y, v.z = float(a), float(b), float(c)


def vassign(a, b):
    """向量赋值"""
    a.x, a.y, a.z = b.x, b.y, b.z


def vclr(v):
    """清零向量"""
    v.x, v.y, v.z = 0.0, 0.0, 0.0


def vadd(v, a, b):
    """向量加法"""
    v.x, v.y, v.z = a.x + b.x, a.y + b.y, a.z + b.z


def vsub(v, a, b):
    """向量减法"""
    v.x, v.y, v.z = a.x - b.x, a.y - b.y, a.z - b.z


def vsadd(v, a, b):
    """标量加向量"""
    k = float(a)
    v.x, v.y, v.z = b.x + k, b.y + k, b.z + k


def vssub(v, a, b):
    """向量减标量"""
    k = float(a)
    v.x, v.y, v.z = b.x - k, b.y - k, b.z - k


def vmul(v, a, b):
    """逐元素乘法"""
    v.x, v.y, v.z = a.x * b.x, a.y * b.y, a.z * b.z


def vsmul(v, a, b):
    """标量乘向量"""
    k = float(a)
    v.x, v.y, v.z = k * b.x, k * b.y, k * b.z


def vdot(a, b):
    """点积"""
    return a.x * b.x + a.y * b.y + a.z * b.z


def vnorm(v):
    """归一化"""
    _l = 1.0 / np.sqrt(vdot(v, v))
    vsmul(v, _l, v)


def vxcross(v, a, b):
    """叉积"""
    v.x = a.y * b.z - a.z * b.y
    v.y = a.z * b.x - a.x * b.z
    v.z = a.x * b.y - a.y * b.x


def vfilter(v):
    """返回最大分量"""
    return max(v.x, max(v.y, v.z))


def viszero(v):
    """检查是否为零向量"""
    return v.x == 0.0 and v.y == 0.0 and v.z == 0.0


def toInt(x):
    """转换为 0-255 的整数（gamma 校正）"""
    x = max(0.0, min(1.0, float(x)))
    return int((x ** (1.0 / 2.2)) * 255.0 + 0.5)
