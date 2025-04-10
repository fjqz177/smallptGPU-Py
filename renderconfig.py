# renderconfig.py
import numpy as np
from vec import Vec, vsub, vnorm, vxcross, vsmul
from camera import Camera
from geom import Sphere, Refl
from renderdevice import RenderDevice
import pyopencl as cl
import time


class RenderConfig:
    """渲染配置类，管理场景和设备"""

    def __init__(self, scene_file_name, w, h, use_cpus, use_gpus, force_gpu_work_size):
        """初始化渲染配置"""
        self.width = w
        self.height = h
        self.current_sample = 0
        # 新内核直接输出 RGB，无需额外的 alpha 通道，但仍使用 uint32 表示像素
        self.pixels = np.zeros((w * h), dtype=np.uint32)  # RGB 格式
        self.camera = Camera()
        self.spheres = []
        self.sphere_count = 0
        self.current_sphere = 0
        self.selected_device = 0
        self.caption_buffer = ""
        self.render_devices = []
        self.device_perf_index = []
        self.workload_profiling = False
        self.time_first_workload_update = 0.0

        self.read_scene(scene_file_name)
        self.setup_opencl(use_cpus, use_gpus, force_gpu_work_size)
        self.update_camera()
        self.update_device_workload(True)

    def read_scene(self, file_name):
        """读取场景文件"""
        print(f"读取场景文件: {file_name}")
        with open(file_name, "r") as f:
            lines = f.readlines()
            for line in lines:
                parts = line.strip().split()
                if not parts:
                    continue
                if parts[0] == "camera":
                    self.camera.orig = Vec(
                        float(parts[1]), float(parts[2]), float(parts[3])
                    )
                    self.camera.target = Vec(
                        float(parts[4]), float(parts[5]), float(parts[6])
                    )
                elif parts[0] == "size":
                    self.sphere_count = int(parts[1])
                elif parts[0] == "sphere":
                    s = Sphere()
                    s.rad = float(parts[1])
                    s.p = Vec(float(parts[2]), float(parts[3]), float(parts[4]))
                    s.e = Vec(float(parts[5]), float(parts[6]), float(parts[7]))
                    s.c = Vec(float(parts[8]), float(parts[9]), float(parts[10]))
                    s.refl = [Refl.DIFF, Refl.SPEC, Refl.REFR][int(parts[11])]
                    self.spheres.append(s)
        print(f"场景包含 {self.sphere_count} 个球体")

    def setup_opencl(self, use_cpus, use_gpus, force_gpu_work_size):
        """初始化 OpenCL 设备"""
        platforms = cl.get_platforms()
        if not platforms:
            raise RuntimeError("未找到 OpenCL 平台")
        platform = platforms[0]
        devices = platform.get_devices()
        selected_devices = []
        for i, dev in enumerate(devices):
            dev_type = dev.type
            print(f"设备 {i}: {dev.name}, 类型: {dev_type}")
            if (use_cpus and dev_type & cl.device_type.CPU) or (
                use_gpus and dev_type & cl.device_type.GPU
            ):
                selected_devices.append(dev)

        if not selected_devices:
            raise RuntimeError("未找到合适的 OpenCL 设备")

        for dev in selected_devices:
            rd = RenderDevice(
                dev,
                "rendering_kernel.cl",
                force_gpu_work_size,
                self.camera,
                self.spheres,
                self.sphere_count,
            )
            self.render_devices.append(rd)
            self.device_perf_index.append(1.0)

        self.workload_profiling = len(self.render_devices) > 1
        self.time_first_workload_update = self.wall_clock_time()

    def update_camera(self):
        """更新相机参数"""
        vsub(self.camera.dir, self.camera.target, self.camera.orig)
        vnorm(self.camera.dir)
        up = Vec(0.0, 1.0, 0.0)
        fov = np.pi / 4  # 45 度视角
        vxcross(self.camera.x, self.camera.dir, up)
        vnorm(self.camera.x)
        vsmul(self.camera.x, self.width * fov / self.height, self.camera.x)
        vxcross(self.camera.y, self.camera.x, self.camera.dir)
        vnorm(self.camera.y)
        vsmul(self.camera.y, fov, self.camera.y)
        for dev in self.render_devices:
            dev.update_camera_buffer(self.camera)

    def update_device_workload(self, calculate_new_load):
        """更新设备工作负载"""
        print("更新 OpenCL 设备工作负载")
        if calculate_new_load:
            self.device_perf_index = [
                dev.get_performance() for dev in self.render_devices
            ]

        total_perf = sum(self.device_perf_index)
        total_workload = self.width * self.height
        work_offset = 0
        for i, dev in enumerate(self.render_devices):
            work_left = total_workload - work_offset
            if work_left <= 0:
                work_amount = 1
                work_offset = total_workload
            else:
                work_amount = (
                    work_left
                    if i == len(self.render_devices) - 1
                    else int(work_left * self.device_perf_index[i] / total_perf)
                )
            dev.set_workload(
                work_offset, work_amount, self.width, self.height, self.pixels
            )
            work_offset += work_amount
        self.current_sample = 0

    def execute(self):
        """执行渲染"""
        start_time = self.wall_clock_time()
        if self.current_sample < 20:
            self.execute_kernels()
            self.current_sample += 1
        else:
            k = min(self.current_sample - 20, 100) / 100.0
            threshold = 0.5 * k
            while True:
                self.execute_kernels()
                self.current_sample += 1
                if self.wall_clock_time() - start_time > threshold:
                    break
        elapsed = self.wall_clock_time() - start_time
        samples = self.current_sample
        # sample_sec = samples * self.width * self.height / elapsed
        self.caption_buffer = (
            f"[渲染时间 {elapsed:.3f} 秒 (第 {self.current_sample} 次采样)]"
            f"[平均采样率 {(samples * self.width * self.height / (elapsed + 1) / 1000):.1f}K]"
        )
        self.check_device_workload()

    def execute_kernels(self):
        """运行 OpenCL 内核"""
        for dev in self.render_devices:
            dev.set_args(self.current_sample)
            dev.execute_kernel()

    def check_device_workload(self):
        """检查并调整工作负载"""
        current_time = self.wall_clock_time()
        if self.workload_profiling and (
            current_time - self.time_first_workload_update > 10.0
        ):
            self.update_device_workload(True)
            self.workload_profiling = False

    def reinit(self, realloc_buffers):
        """重新初始化"""
        if realloc_buffers:
            self.pixels = np.zeros((self.width * self.height), dtype=np.uint32)
            self.update_device_workload(False)
        self.update_camera()
        self.current_sample = 0

    def reinit_scene(self):
        """重新初始化场景"""
        self.current_sample = 0
        for dev in self.render_devices:
            dev.update_scene_buffer(self.spheres)

    def get_render_device(self):
        """获取当前渲染设备"""
        return self.render_devices

    def get_perf_index(self, device_index):
        """获取设备性能指标"""
        return self.device_perf_index[device_index]

    @staticmethod
    def wall_clock_time():
        """获取当前时间（秒）"""
        return time.time()
