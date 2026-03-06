# displayfunc.py
import OpenGL.GL as gl
import OpenGL.GLUT as glut
import numpy as np
from vec import Vec, vnorm, vsmul, vadd, vsub
import time
from PIL import Image
from ctypes import c_ubyte

MOVE_STEP = 10.0  # 每次移动的步长
ROTATE_STEP = 2.0 * np.pi / 180.0  # 每次旋转的步长


class DisplayFunc:
    """显示和交互类"""

    def __init__(self, config):
        """初始化显示和交互类"""
        self.config = config
        self.print_help = True
        self.show_workload = True
        self.total_elapsed_time = 0.0

        glut.glutInit()
        glut.glutInitDisplayMode(glut.GLUT_RGB | glut.GLUT_DOUBLE)
        glut.glutInitWindowSize(config.width, config.height)
        glut.glutCreateWindow(b"SmallptGPU V2.0")
        glut.glutDisplayFunc(self.display)
        glut.glutReshapeFunc(self.reshape)
        glut.glutKeyboardFunc(self.key)
        glut.glutSpecialFunc(self.special)
        glut.glutIdleFunc(self.idle)

    def display(self):
        """显示函数"""
        rgba_pixels = np.zeros(
            (self.config.width * self.config.height, 4), dtype=np.uint8
        )
        rgba_pixels[:, 0] = (self.config.pixels >> 16) & 0xFF  # R
        rgba_pixels[:, 1] = (self.config.pixels >> 8) & 0xFF  # G
        rgba_pixels[:, 2] = self.config.pixels & 0xFF  # B
        rgba_pixels[:, 3] = 255  # A
        gl.glRasterPos2i(0, 0)
        gl.glDrawPixels(
            self.config.width,
            self.config.height,
            gl.GL_RGBA,
            gl.GL_UNSIGNED_BYTE,
            rgba_pixels.tobytes(),
        )
        # 如果需要显示工作负载，则绘制工作负载
        if self.show_workload:
            for i, dev in enumerate(self.config.render_devices):
                start = dev.get_work_offset() // self.config.width
                end = (
                    dev.get_work_offset() + dev.get_work_amount()
                ) // self.config.width
                colors = [(1, 0, 0), (0, 1, 0), (0, 0, 1), (1, 1, 0)]
                gl.glColor3f(*colors[i % 4])
                gl.glRecti(0, start, 10, end)
                gl.glBegin(gl.GL_LINES)
                gl.glVertex2i(0, start)
                gl.glVertex2i(self.config.width, start)
                gl.glVertex2i(0, end)
                gl.glVertex2i(self.config.width, end)
                gl.glEnd()
                gl.glColor3f(1, 1, 1)
                gl.glRasterPos2i(12, (start + end) // 2)
                glut.glutBitmapString(glut.GLUT_BITMAP_8_BY_13, dev.get_name().encode())

        self.print_captions()
        if self.print_help:
            gl.glPushMatrix()
            gl.glLoadIdentity()
            gl.glOrtho(-0.5, 639.5, -0.5, 479.5, -1.0, 1.0)
            self.print_help_and_devices()
            gl.glPopMatrix()

        glut.glutSwapBuffers()

    def reshape(self, new_width, new_height):
        """窗口大小调整"""
        self.config.width = new_width
        self.config.height = new_height
        gl.glViewport(0, 0, new_width, new_height)
        gl.glLoadIdentity()
        gl.glOrtho(0.0, new_width - 1, 0.0, new_height - 1, -1.0, 1.0)
        self.config.reinit(True)

    def key(self, key, x, y):
        """键盘事件"""
        key = key.decode()
        if key == "p":  # 保存图像
            rgba_pixels = np.zeros(
                (self.config.width * self.config.height, 4), dtype=np.uint8
            )
            rgba_pixels[:, 0] = (self.config.pixels >> 16) & 0xFF  # R
            rgba_pixels[:, 1] = (self.config.pixels >> 8) & 0xFF  # G
            rgba_pixels[:, 2] = self.config.pixels & 0xFF  # B
            rgba_pixels[:, 3] = 255  # A
            img = Image.fromarray(
                rgba_pixels.reshape(self.config.height, self.config.width, 4)[
                    ::-1, :, :3
                ]
            )
            img.save("image.png")
        elif key == " ":  # 暂停/继续渲染
            self.config.reinit(False)
        elif key == "h":  # 显示/隐藏帮助信息
            self.print_help = not self.print_help
        elif key == "k":  # 显示/隐藏工作负载
            self.show_workload = not self.show_workload
        elif key == "a":  # 向左移动
            dir = Vec(
                self.config.camera.x.x, self.config.camera.x.y, self.config.camera.x.z
            )
            vnorm(dir)
            vsmul(dir, -MOVE_STEP, dir)
            vadd(self.config.camera.orig, self.config.camera.orig, dir)
            vadd(self.config.camera.target, self.config.camera.target, dir)
            self.config.reinit(False)
        elif key == "d":  # 向右移动
            dir = Vec(
                self.config.camera.x.x, self.config.camera.x.y, self.config.camera.x.z
            )
            vnorm(dir)
            vsmul(dir, MOVE_STEP, dir)
            vadd(self.config.camera.orig, self.config.camera.orig, dir)
            vadd(self.config.camera.target, self.config.camera.target, dir)
            self.config.reinit(False)
        elif key == "w":  # 向前移动
            dir = Vec(
                self.config.camera.dir.x,
                self.config.camera.dir.y,
                self.config.camera.dir.z,
            )
            vnorm(dir)
            vsmul(dir, MOVE_STEP, dir)
            vadd(self.config.camera.orig, self.config.camera.orig, dir)
            vadd(self.config.camera.target, self.config.camera.target, dir)
            self.config.reinit(False)
        elif key == "s":  # 向后移动
            dir = Vec(
                self.config.camera.dir.x,
                self.config.camera.dir.y,
                self.config.camera.dir.z,
            )
            vnorm(dir)
            vsmul(dir, -MOVE_STEP, dir)
            vadd(self.config.camera.orig, self.config.camera.orig, dir)
            vadd(self.config.camera.target, self.config.camera.target, dir)
            self.config.reinit(False)
        elif key == "r":  # 向上移动
            dir = Vec(
                self.config.camera.y.x, self.config.camera.y.y, self.config.camera.y.z
            )
            vnorm(dir)
            vsmul(dir, MOVE_STEP, dir)
            vadd(self.config.camera.orig, self.config.camera.orig, dir)
            vadd(self.config.camera.target, self.config.camera.target, dir)
            self.config.reinit(False)
        elif key == "f":  # 向下移动
            dir = Vec(
                self.config.camera.y.x, self.config.camera.y.y, self.config.camera.y.z
            )
            vnorm(dir)
            vsmul(dir, -MOVE_STEP, dir)
            vadd(self.config.camera.orig, self.config.camera.orig, dir)
            vadd(self.config.camera.target, self.config.camera.target, dir)
            self.config.reinit(False)
        
        elif key == "+":  # 选择下一个球体
            self.config.current_sphere = (self.config.current_sphere + 1) % self.config.sphere_count
            print(
                f"Selected sphere {self.config.current_sphere} "
                f"({self.config.spheres[self.config.current_sphere].p.x}, "
                f"{self.config.spheres[self.config.current_sphere].p.y}, "
                f"{self.config.spheres[self.config.current_sphere].p.z})"
            )
            self.config.reinit_scene()
        elif key == "-":  # 选择上一个球体
            self.config.current_sphere = (self.config.current_sphere + self.config.sphere_count - 1) % self.config.sphere_count
            print(
                f"Selected sphere {self.config.current_sphere} "
                f"({self.config.spheres[self.config.current_sphere].p.x}, "
                f"{self.config.spheres[self.config.current_sphere].p.y}, "
                f"{self.config.spheres[self.config.current_sphere].p.z})"
            )
            self.config.reinit_scene()
        elif key == "4":  # 左移当前球体
            self.config.spheres[self.config.current_sphere].p.x -= 0.5 * MOVE_STEP
            self.config.reinit_scene()
        elif key == "6":  # 右移当前球体
            self.config.spheres[self.config.current_sphere].p.x += 0.5 * MOVE_STEP
            self.config.reinit_scene()
        elif key == "8":  # 向前移动当前球体
            self.config.spheres[self.config.current_sphere].p.z -= 0.5 * MOVE_STEP
            self.config.reinit_scene()
        elif key == "2":  # 向后移动当前球体
            self.config.spheres[self.config.current_sphere].p.z += 0.5 * MOVE_STEP
            self.config.reinit_scene()
        elif key == "9":  # 向上移动当前球体
            self.config.spheres[self.config.current_sphere].p.y += 0.5 * MOVE_STEP
            self.config.reinit_scene()
        elif key == "3":  # 向下移动当前球体
            self.config.spheres[self.config.current_sphere].p.y -= 0.5 * MOVE_STEP
            self.config.reinit_scene()
        # elif key == "l":  # 重置负载均衡
        #     self.config.reinit(False)
        #     self.config.restart_workload_procedure()
        elif key == "n":  # 选择上一个设备
            self.config.selected_device = (self.config.selected_device + len(self.config.render_devices) - 1) % len(self.config.render_devices)
        elif key == "m":  # 选择下一个设备
            self.config.selected_device = (self.config.selected_device + 1) % len(self.config.render_devices)
        # elif key == "v":  # 减少当前设备的性能索引
        #     if self.config.is_profiling():
        #         print("Please, wait for the end of the profiling phase")
        #     else:
        #         self.config.dec_perf_index(self.config.selected_device)
        # elif key == "b":  # 增加当前设备的性能索引
        #     if self.config.is_profiling():
        #         print("Please, wait for the end of the profiling phase")
        #     else:
        #         self.config.inc_perf_index(self.config.selected_device)     
        
        elif key == "t":  # 增加 gamma 值
            new_gamma = self.config.gamma + 0.1
            self.config.gamma = new_gamma
            for dev in self.config.render_devices:
                dev.update_gamma(new_gamma)
            print(f"Gamma increased to {new_gamma:.1f}")
        elif key == "g":  # 减少 gamma 值
            new_gamma = max(0.1, self.config.gamma - 0.1)  # 确保 gamma 不小于 0.1
            self.config.gamma = new_gamma
            for dev in self.config.render_devices:
                dev.update_gamma(new_gamma)
            print(f"Gamma decreased to {new_gamma:.1f}")

    def special(self, key, x, y):
        """特殊按键"""
        if key == glut.GLUT_KEY_UP:  # 向上旋转
            t = Vec()
            vsub(t, self.config.camera.target, self.config.camera.orig)
            t_new = Vec(
                t.x,
                t.y * np.cos(-ROTATE_STEP) + t.z * np.sin(-ROTATE_STEP),
                -t.y * np.sin(-ROTATE_STEP) + t.z * np.cos(-ROTATE_STEP),
            )
            vadd(self.config.camera.target, self.config.camera.orig, t_new)
            self.config.reinit(False)
        elif key == glut.GLUT_KEY_DOWN:  # 向下旋转
            t = Vec()
            vsub(t, self.config.camera.target, self.config.camera.orig)
            t_new = Vec(
                t.x,
                t.y * np.cos(ROTATE_STEP) + t.z * np.sin(ROTATE_STEP),
                -t.y * np.sin(ROTATE_STEP) + t.z * np.cos(ROTATE_STEP),
            )
            vadd(self.config.camera.target, self.config.camera.orig, t_new)
            self.config.reinit(False)
        elif key == glut.GLUT_KEY_LEFT:  # 逆时针旋转
            t = Vec()
            vsub(t, self.config.camera.target, self.config.camera.orig)
            t_new = Vec(
                t.x * np.cos(ROTATE_STEP) + t.z * np.sin(ROTATE_STEP),
                t.y,
                -t.x * np.sin(ROTATE_STEP) + t.z * np.cos(ROTATE_STEP),
            )
            vadd(self.config.camera.target, self.config.camera.orig, t_new)
            self.config.reinit(False)
        elif key == glut.GLUT_KEY_RIGHT:  # 顺时针旋转
            t = Vec()
            vsub(t, self.config.camera.target, self.config.camera.orig)
            t_new = Vec(
                t.x * np.cos(-ROTATE_STEP) + t.z * np.sin(-ROTATE_STEP),
                t.y,
                -t.x * np.sin(-ROTATE_STEP) + t.z * np.cos(-ROTATE_STEP),
            )
            vadd(self.config.camera.target, self.config.camera.orig, t_new)
            self.config.reinit(False)

    def idle(self):
        """空闲时更新渲染"""
        start_sample = self.config.current_sample
        if start_sample == 0:
            self.total_elapsed_time = 0.0
        start_time = time.time()
        self.config.execute()
        elapsed = time.time() - start_time
        self.total_elapsed_time += elapsed
        samples = self.config.current_sample - start_sample
        sample_sec = samples * self.config.width * self.config.height / (elapsed + 1)
        # 修改为纯英文，避免中文
        self.config.caption_buffer = (
            f"[Render Time {elapsed:.3f} s (Sample {self.config.current_sample})]"
            f"[Avg Sample Rate {(self.config.current_sample * self.config.width * self.config.height / (self.total_elapsed_time + 1) / 1000):.1f}K]"
            f"[Current Sample Rate {sample_sec / 1000:.1f}K]"
        )
        glut.glutPostRedisplay()

    def run(self):
        """启动主循环"""
        glut.glutMainLoop()

    def print_captions(self):
        """绘制标题"""
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glColor4f(0, 0, 0, 0.8)
        gl.glRecti(
            0, self.config.height - 15, self.config.width - 1, self.config.height - 1
        )
        gl.glRecti(0, 0, self.config.width - 1, 20)
        gl.glDisable(gl.GL_BLEND)
        gl.glColor3f(1, 1, 1)
        gl.glRasterPos2i(4, 5)
        glut.glutBitmapString(
            glut.GLUT_BITMAP_8_BY_13, self.config.caption_buffer.encode()
        )
        gl.glRasterPos2i(4, self.config.height - 10)
        glut.glutBitmapString(
            glut.GLUT_BITMAP_8_BY_13, b"SmallptGPU V2.0 (Written by David Bucciarelli)"
        )

    @staticmethod
    def PrintString(font, string):
        """在屏幕上绘制字符串"""
        for char in string:
            glut.glutBitmapCharacter(font, ord(char))

    def print_help_and_devices(self):
        """绘制帮助和设备信息"""
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glColor4f(0, 0, 0, 0.5)
        gl.glRecti(10, 80, 630, 440)
        gl.glDisable(gl.GL_BLEND)

        gl.glColor3f(1, 1, 1)
        # 帮助文本和设备信息可补充
        help_text = b"Help & Devices"
        help_text_ctypes = (c_ubyte * len(help_text))(*help_text)
        gl.glRasterPos2i(
            320
            - glut.glutBitmapLength(glut.GLUT_BITMAP_9_BY_15, help_text_ctypes) // 2,
            420,
        )
        self.PrintString(glut.GLUT_BITMAP_9_BY_15, "Help & Devices")

        # Help
        gl.glRasterPos2i(60, 390)
        self.PrintString(glut.GLUT_BITMAP_9_BY_15, "h - toggle Help")
        gl.glRasterPos2i(60, 375)
        self.PrintString(
            glut.GLUT_BITMAP_9_BY_15, "arrow Keys - rotate camera left/right/up/down"
        )
        gl.glRasterPos2i(60, 360)
        self.PrintString(
            glut.GLUT_BITMAP_9_BY_15, "a and d - move camera left and right"
        )
        gl.glRasterPos2i(60, 345)
        self.PrintString(
            glut.GLUT_BITMAP_9_BY_15, "w and s - move camera forward and backward"
        )
        gl.glRasterPos2i(60, 330)
        self.PrintString(glut.GLUT_BITMAP_9_BY_15, "r and f - move camera up and down")
        gl.glRasterPos2i(60, 315)
        self.PrintString(
            glut.GLUT_BITMAP_9_BY_15,
            "PageUp and PageDown - move camera target up and down",
        )
        gl.glRasterPos2i(60, 300)
        self.PrintString(
            glut.GLUT_BITMAP_9_BY_15, "+ and - - to select next/previous object"
        )
        gl.glRasterPos2i(60, 285)
        self.PrintString(
            glut.GLUT_BITMAP_9_BY_15, "2, 3, 4, 5, 6, 8, 9 - to move selected object"
        )
        # gl.glRasterPos2i(60, 270)
        # self.PrintString(glut.GLUT_BITMAP_9_BY_15, "l - reset load balancing procedure")
        gl.glRasterPos2i(60, 255)
        self.PrintString(glut.GLUT_BITMAP_9_BY_15, "k - toggle workload visualization")
        gl.glRasterPos2i(60, 240)
        self.PrintString(
            glut.GLUT_BITMAP_9_BY_15, "n, m - select previous/next OpenCL device"
        )
        # gl.glRasterPos2i(60, 225)
        # self.PrintString(
        #     glut.GLUT_BITMAP_9_BY_15,
        #     "v, b - increase/decrease the worload of the selected OpenCL device",
        # )
