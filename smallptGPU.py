# smallptGPU.py
import sys
from renderconfig import RenderConfig
from displayfunc import DisplayFunc

if __name__ == "__main__":
    if len(sys.argv) == 7:
        use_cpus = int(sys.argv[1]) == 1
        use_gpus = int(sys.argv[2]) == 1
        force_gpu_work_size = int(sys.argv[3])
        width = int(sys.argv[4])
        height = int(sys.argv[5])
        scene_file = sys.argv[6]
    else:
        use_cpus, use_gpus = True, True
        force_gpu_work_size = 0
        width, height = 1024, 768
        scene_file = "scenes/cornell.scn"

    config = RenderConfig(
        scene_file, width, height, use_cpus, use_gpus, force_gpu_work_size
    )
    display = DisplayFunc(config)
    display.run()
