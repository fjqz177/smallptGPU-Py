# renderdevice.py
import pyopencl as cl
import numpy as np


class RenderDevice:
    """OpenCL 渲染设备类，与重写的 rendering_kernel.cl 兼容"""

    def __init__(
        self,
        device,
        kernel_file_name,
        force_gpu_work_size,
        camera,
        spheres,
        sphere_count,
    ):
        self.device = device
        self.device_name = device.name.strip()  # 移除可能的空白字符
        self.context = cl.Context([device])
        self.queue = cl.CommandQueue(
            self.context, properties=cl.command_queue_properties.PROFILING_ENABLE
        )
        self.sphere_count = sphere_count
        self.work_offset = 0
        self.work_amount = 0
        self.width = 0
        self.height = 0
        self.current_sample = 0
        self.pixels = None
        self.colors = None
        self.seeds = None
        self.exe_unit_count = 0.0
        self.exe_time = 0.0

        self.gamma = np.array([2.2], dtype=np.float32)  # 默认 gamma 值为 2.2
        self.gamma_buffer = cl.Buffer(
            self.context,
            cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=self.gamma,
        )

        # 加载并编译内核
        with open(kernel_file_name, "r", encoding="utf-8") as f:
            kernel_source = f.read()
        self.program = cl.Program(self.context, kernel_source).build()
        self.kernel = self.program.RadianceGPU
        self.work_group_size = self.kernel.get_work_group_info(
            cl.kernel_work_group_info.WORK_GROUP_SIZE, device
        )
        if force_gpu_work_size > 0 and device.type == cl.device_type.GPU:
            self.work_group_size = force_gpu_work_size
            print(f"[{self.device_name}] 强制工作组大小: {self.work_group_size}")

        # 初始化缓冲区
        self.camera_buffer = cl.Buffer(
            self.context,
            cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=camera.to_struct(),
        )
        sphere_data = np.array([s.to_struct() for s in spheres])
        self.sphere_buffer = cl.Buffer(
            self.context,
            cl.mem_flags.READ_ONLY | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=sphere_data,
        )

    def set_workload(self, offset, amount, screen_width, screen_height, screen_pixels):
        """设置工作负载"""
        self.work_offset = offset
        self.work_amount = amount
        self.width = screen_width
        self.height = screen_height
        self.pixels = screen_pixels
        self.colors = np.zeros(amount, dtype=[("x", "f4"), ("y", "f4"), ("z", "f4")])
        self.seeds = np.random.randint(2, 100000, size=(amount * 2,), dtype=np.uint32)

        self.color_buffer = cl.Buffer(
            self.context,
            cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=self.colors,
        )
        self.pixel_buffer = cl.Buffer(
            self.context, cl.mem_flags.WRITE_ONLY, size=amount * 4
        )
        self.seed_buffer = cl.Buffer(
            self.context,
            cl.mem_flags.READ_WRITE | cl.mem_flags.COPY_HOST_PTR,
            hostbuf=self.seeds,
        )

    def set_args(self, current_sample):
        """设置内核参数，与新内核匹配"""
        self.current_sample = current_sample
        self.kernel.set_args(
            self.color_buffer,
            self.seed_buffer,
            self.sphere_buffer,
            self.camera_buffer,
            np.uint32(self.sphere_count),
            np.uint32(self.width),
            np.uint32(self.height),
            np.uint32(self.current_sample),
            self.pixel_buffer,
            np.uint32(self.work_offset),
            np.uint32(self.work_amount),
            self.gamma_buffer,  # 添加 gamma 缓冲区
        )

    def execute_kernel(self):
        """执行内核"""
        global_size = (
            (self.work_amount + self.work_group_size - 1) // self.work_group_size
        ) * self.work_group_size
        event = cl.enqueue_nd_range_kernel(
            self.queue, self.kernel, (global_size,), (self.work_group_size,)
        )
        # 注意：新内核中像素颜色已直接写入 RGB 格式，无需 gamma 校正
        cl.enqueue_copy(
            self.queue,
            self.pixels[self.work_offset : self.work_offset + self.work_amount],
            self.pixel_buffer,
        )
        self.queue.finish()
        self.exe_unit_count += self.work_amount
        profiling = event.get_profiling_info
        self.exe_time += (
            profiling(cl.profiling_info.END) - profiling(cl.profiling_info.START)
        ) / 1e9

    def update_camera_buffer(self, camera):
        """更新相机缓冲区"""
        cl.enqueue_copy(self.queue, self.camera_buffer, camera.to_struct())

    def update_scene_buffer(self, spheres):
        """更新场景缓冲区"""
        sphere_data = np.array([s.to_struct() for s in spheres])
        cl.enqueue_copy(self.queue, self.sphere_buffer, sphere_data)

    def get_performance(self):
        """获取性能指标"""
        return (
            1.0
            if self.exe_time == 0.0 or self.exe_unit_count == 0.0
            else (self.exe_unit_count / self.exe_time)
        )

    def get_name(self):
        """获取设备名称"""
        return self.device_name

    def get_work_offset(self):
        """获取工作偏移量"""
        return self.work_offset

    def get_work_amount(self):
        """获取工作量"""
        return self.work_amount
    
    def update_gamma(self, new_gamma):
        """更新 gamma 值"""
        self.gamma[0] = new_gamma
        cl.enqueue_copy(self.queue, self.gamma_buffer, self.gamma)
