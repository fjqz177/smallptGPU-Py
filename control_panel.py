# control_panel.py
import threading
import tkinter as tk
from tkinter import ttk

from geom import Refl


class ControlPanel:
    """渲染控制面板，用于实时修改相机与场景参数"""

    def __init__(self, config, refresh_ms=300):
        self.config = config
        self.refresh_ms = refresh_ms
        self.root = tk.Tk()
        self.root.title("SmallptGPU 控制面板")
        self.root.geometry("520x700")

        self.entry_bindings = {}
        self.current_entry = None
        self._slider_update_lock = False
        self.defaults = self._capture_defaults()

        self._build_ui()
        self._load_from_config()
        self._schedule_refresh()

    def _build_ui(self):
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.camera_frame = ttk.Frame(notebook)
        self.scene_frame = ttk.Frame(notebook)
        notebook.add(self.camera_frame, text="相机")
        notebook.add(self.scene_frame, text="场景")

        self._build_camera_tab()
        self._build_scene_tab()
        self._build_universal_slider()

    def _build_camera_tab(self):
        cam_box = ttk.LabelFrame(self.camera_frame, text="相机参数")
        cam_box.pack(fill=tk.X, padx=8, pady=8)

        self.cam_orig_entries = self._vec_editor(
            cam_box, "orig (x,y,z)", 0, self.apply_camera
        )
        self.cam_target_entries = self._vec_editor(
            cam_box, "target (x,y,z)", 1, self.apply_camera
        )

        gamma_box = ttk.Frame(cam_box)
        gamma_box.grid(row=2, column=0, sticky="ew", padx=4, pady=6)
        gamma_box.columnconfigure(1, weight=1)
        ttk.Label(gamma_box, text="gamma").grid(row=0, column=0, sticky="w")
        self.gamma_var = tk.StringVar()
        gamma_entry = ttk.Entry(gamma_box, textvariable=self.gamma_var, width=12)
        gamma_entry.grid(row=0, column=1, sticky="w")
        gamma_entry.bind("<Return>", lambda _e: self.apply_camera())
        gamma_entry.bind("<FocusOut>", lambda _e: self.apply_camera())
        self.gamma_entry = gamma_entry
        self._register_entry(
            self.gamma_entry,
            "gamma",
            lambda: self.config.gamma,
            self._set_gamma,
            self.apply_camera,
            "gamma",
            lambda: self.defaults["gamma"],
        )

        self._register_vec_entries(
            self.cam_orig_entries,
            self.config.camera.orig,
            lambda: self.defaults["camera.orig"],
            "camera.orig",
            self.apply_camera,
            "pos",
        )
        self._register_vec_entries(
            self.cam_target_entries,
            self.config.camera.target,
            lambda: self.defaults["camera.target"],
            "camera.target",
            self.apply_camera,
            "pos",
        )

        btn_row = ttk.Frame(cam_box)
        btn_row.grid(row=3, column=0, sticky="ew", padx=4, pady=6)
        btn_row.columnconfigure(0, weight=1)
        apply_btn = ttk.Button(btn_row, text="应用相机", command=self.apply_camera)
        apply_btn.pack(side=tk.LEFT)
        reset_btn = ttk.Button(btn_row, text="重置采样", command=self._reset_sampling)
        reset_btn.pack(side=tk.RIGHT)

    def _build_scene_tab(self):
        scene_box = ttk.LabelFrame(self.scene_frame, text="球体列表")
        scene_box.pack(fill=tk.BOTH, expand=False, padx=8, pady=8)

        self.sphere_list = tk.Listbox(scene_box, height=8)
        self.sphere_list.pack(fill=tk.X, padx=6, pady=6)
        self.sphere_list.bind(
            "<<ListboxSelect>>", lambda _e: self._load_sphere_fields()
        )

        detail_box = ttk.LabelFrame(self.scene_frame, text="球体参数")
        detail_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self.sphere_rad_var = tk.StringVar()
        self.sphere_rad_entry = self._entry_row(
            detail_box, "半径", self.sphere_rad_var, 0
        )

        self.sphere_p_entries = self._vec_editor(
            detail_box, "位置 p (x,y,z)", 1, self.apply_sphere
        )
        self.sphere_e_entries = self._vec_editor(
            detail_box, "发光 e (x,y,z)", 2, self.apply_sphere
        )
        self.sphere_c_entries = self._vec_editor(
            detail_box, "颜色 c (x,y,z)", 3, self.apply_sphere
        )

        refl_row = ttk.Frame(detail_box)
        refl_row.grid(row=4, column=0, sticky="ew", padx=4, pady=6)
        refl_row.columnconfigure(1, weight=1)
        ttk.Label(refl_row, text="反射类型").grid(row=0, column=0, sticky="w")
        self.refl_var = tk.StringVar()
        self.refl_combo = ttk.Combobox(
            refl_row,
            textvariable=self.refl_var,
            values=["DIFF", "SPEC", "REFR"],
            state="readonly",
            width=10,
        )
        self.refl_combo.grid(row=0, column=1, sticky="w")
        self.refl_combo.bind("<<ComboboxSelected>>", lambda _e: self.apply_sphere())
        self.refl_combo.bind(
            "<FocusIn>", lambda _e: self._set_combo_target(self.refl_combo)
        )

        self._register_entry(
            self.sphere_rad_entry,
            "sphere.rad",
            lambda: self._get_current_sphere().rad,
            self._set_sphere_rad,
            self.apply_sphere,
            "radius",
            lambda: self._default_sphere_value("rad"),
        )

        self._register_vec_entries(
            self.sphere_p_entries,
            lambda: self._get_current_sphere().p,
            lambda: self._default_sphere_value("p"),
            "sphere.p",
            self.apply_sphere,
            "pos",
        )
        self._register_vec_entries(
            self.sphere_e_entries,
            lambda: self._get_current_sphere().e,
            lambda: self._default_sphere_value("e"),
            "sphere.e",
            self.apply_sphere,
            "emission",
        )
        self._register_vec_entries(
            self.sphere_c_entries,
            lambda: self._get_current_sphere().c,
            lambda: self._default_sphere_value("c"),
            "sphere.c",
            self.apply_sphere,
            "color",
        )

        btn_row = ttk.Frame(detail_box)
        btn_row.grid(row=5, column=0, sticky="ew", padx=4, pady=6)
        btn_row.columnconfigure(0, weight=1)
        apply_btn = ttk.Button(btn_row, text="应用球体", command=self.apply_sphere)
        apply_btn.pack(side=tk.LEFT)

    def _entry_row(self, parent, label, var, row):
        row_frame = ttk.Frame(parent)
        row_frame.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        row_frame.columnconfigure(1, weight=1)
        ttk.Label(row_frame, text=label).grid(row=0, column=0, sticky="w")
        entry = ttk.Entry(row_frame, textvariable=var, width=12)
        entry.grid(row=0, column=1, sticky="w")
        entry.bind("<Return>", lambda _e: self.apply_sphere())
        entry.bind("<FocusOut>", lambda _e: self.apply_sphere())
        return entry

    def _vec_editor(self, parent, label, row, apply_func):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        ttk.Label(frame, text=label).grid(row=0, column=0, sticky="w")
        entries = []
        for i in range(3):
            var = tk.StringVar()
            entry = ttk.Entry(frame, textvariable=var, width=10)
            entry.grid(row=0, column=i + 1, padx=4)
            entry.bind("<Return>", lambda _e: apply_func())
            entry.bind("<FocusOut>", lambda _e: apply_func())
            entries.append((var, entry))
        return entries

    def _build_universal_slider(self):
        slider_box = ttk.LabelFrame(self.root, text="万能滑块")
        slider_box.pack(fill=tk.X, padx=8, pady=6)

        self.slider_label = ttk.Label(slider_box, text="点击任意参数输入框后使用滑块")
        self.slider_label.pack(anchor="w", padx=6, pady=4)

        sens_row = ttk.Frame(slider_box)
        sens_row.pack(fill=tk.X, padx=6, pady=2)
        ttk.Label(sens_row, text="灵敏度").pack(side=tk.LEFT)
        self.sensitivity_var = tk.DoubleVar(value=1.0)
        self.sensitivity_scale = ttk.Scale(
            sens_row,
            orient="horizontal",
            variable=self.sensitivity_var,
            from_=0.01,
            to=15.0,
        )
        self.sensitivity_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8)
        self.sensitivity_value = ttk.Label(sens_row, text="1.0x")
        self.sensitivity_value.pack(side=tk.RIGHT)
        self.sensitivity_scale.bind(
            "<B1-Motion>", lambda _e: self._on_sensitivity_change()
        )
        self.sensitivity_scale.bind(
            "<ButtonRelease-1>", lambda _e: self._on_sensitivity_change()
        )

        self.slider_var = tk.DoubleVar(value=0.0)
        self.slider_scale = ttk.Scale(
            slider_box,
            orient="horizontal",
            variable=self.slider_var,
            from_=0.0,
            to=1.0,
            command=self._on_universal_change,
        )
        self.slider_scale.pack(fill=tk.X, padx=6, pady=6)

        reset_row = ttk.Frame(slider_box)
        reset_row.pack(fill=tk.X, padx=6, pady=4)
        reset_btn = ttk.Button(
            reset_row, text="重置所选参数", command=self._reset_selected_parameter
        )
        reset_btn.pack(side=tk.RIGHT)

    def _register_entry(
        self, entry, name, getter, setter, apply_func, range_kind, default_getter
    ):
        self.entry_bindings[entry] = {
            "name": name,
            "get": getter,
            "set": setter,
            "apply": apply_func,
            "kind": range_kind,
            "default": default_getter,
        }
        entry.bind("<FocusIn>", lambda _e: self._set_slider_target(entry))

    def _register_vec_entries(
        self,
        entries,
        vec_provider,
        default_provider,
        name_prefix,
        apply_func,
        range_kind,
    ):
        axes = ["x", "y", "z"]
        provider = vec_provider if callable(vec_provider) else lambda: vec_provider
        defaulter = (
            default_provider if callable(default_provider) else lambda: default_provider
        )
        for axis, (_var, entry) in zip(axes, entries):
            self._register_entry(
                entry,
                f"{name_prefix}.{axis}",
                lambda a=axis: getattr(provider(), a),
                lambda value, a=axis: setattr(provider(), a, value),
                apply_func,
                range_kind,
                lambda a=axis: self._get_axis_value(defaulter(), a),
            )

    def _set_slider_target(self, entry):
        if entry not in self.entry_bindings:
            return
        self.current_entry = entry
        binding = self.entry_bindings[entry]
        try:
            value = float(binding["get"]())
        except (ValueError, TypeError):
            return
        sensitivity = max(0.01, float(self.sensitivity_var.get()))
        min_val, max_val = self._calc_range(binding["kind"], value, sensitivity)
        self.slider_scale.configure(from_=min_val, to=max_val)
        self._slider_update_lock = True
        self.slider_var.set(value)
        self._slider_update_lock = False
        self._update_slider_label(binding["name"], value, min_val, max_val)

    def _update_slider_label(self, name, value, min_val, max_val):
        self.slider_label.config(
            text=f"{name}: {value:.3f}  (范围 {min_val:.3f} ~ {max_val:.3f})"
        )

    def _set_combo_target(self, combo):
        self.current_entry = combo

    def _on_universal_change(self, value):
        if self._slider_update_lock or self.current_entry is None:
            return
        if self.current_entry not in self.entry_bindings:
            return
        binding = self.entry_bindings[self.current_entry]
        try:
            raw = float(value)
        except ValueError:
            return
        min_val = float(self.slider_scale.cget("from"))
        max_val = float(self.slider_scale.cget("to"))
        val = raw
        val = max(min_val, min(max_val, val))
        self._slider_update_lock = True
        binding["set"](val)
        self._set_entry_text(self.current_entry, val)
        binding["apply"]()
        self._update_slider_label(binding["name"], val, min_val, max_val)
        self._slider_update_lock = False

    def _on_sensitivity_change(self):
        self.sensitivity_value.config(text=f"{self.sensitivity_var.get():.1f}x")
        if self.current_entry in self.entry_bindings:
            binding = self.entry_bindings[self.current_entry]
            try:
                value = float(binding["get"]())
            except (ValueError, TypeError):
                return
            sensitivity = max(0.01, float(self.sensitivity_var.get()))
            min_val, max_val = self._calc_range(binding["kind"], value, sensitivity)
            self.slider_scale.configure(from_=min_val, to=max_val)
            self._center_slider_range(value)
            self._update_slider_label(binding["name"], value, min_val, max_val)

    def _reset_selected_parameter(self):
        self.sensitivity_var.set(1.0)
        self.sensitivity_value.config(text="1.0x")
        if self.current_entry in self.entry_bindings:
            binding = self.entry_bindings[self.current_entry]
            try:
                default_val = float(binding["default"]())
            except (ValueError, TypeError):
                return
            binding["set"](default_val)
            self._set_entry_text(self.current_entry, default_val)
            binding["apply"]()
            sensitivity = max(0.01, float(self.sensitivity_var.get()))
            min_val, max_val = self._calc_range(
                binding["kind"], default_val, sensitivity
            )
            self.slider_scale.configure(from_=min_val, to=max_val)
            self._slider_update_lock = True
            self.slider_var.set(default_val)
            self._slider_update_lock = False
            self._update_slider_label(binding["name"], default_val, min_val, max_val)
        elif self.current_entry == self.refl_combo:
            default_refl = self._default_sphere_value("refl")
            if default_refl is None:
                return
            refl_name = {
                Refl.DIFF: "DIFF",
                Refl.SPEC: "SPEC",
                Refl.REFR: "REFR",
            }.get(default_refl, "DIFF")
            self.refl_var.set(refl_name)
            self.apply_sphere()

    def _center_slider_range(self, value):
        self._slider_update_lock = True
        self.slider_var.set(value)
        self._slider_update_lock = False

    def _set_entry_text(self, entry, value):
        for var, ent in (
            self.cam_orig_entries
            + self.cam_target_entries
            + self.sphere_p_entries
            + self.sphere_e_entries
            + self.sphere_c_entries
        ):
            if ent == entry:
                var.set(f"{value:.3f}")
                return
        if entry == self.gamma_entry:
            self.gamma_var.set(f"{value:.3f}")
        elif entry == self.sphere_rad_entry:
            self.sphere_rad_var.set(f"{value:.3f}")

    def _set_gamma(self, value):
        self.config.gamma = value
        for dev in self.config.render_devices:
            dev.update_gamma(value)

    @staticmethod
    def _get_axis_value(source, axis):
        if hasattr(source, axis):
            return getattr(source, axis)
        if isinstance(source, (list, tuple)):
            axis_index = {"x": 0, "y": 1, "z": 2}
            return float(source[axis_index[axis]])
        return 0.0

    def _capture_defaults(self):
        defaults = {
            "gamma": float(self.config.gamma),
            "camera.orig": (
                float(self.config.camera.orig.x),
                float(self.config.camera.orig.y),
                float(self.config.camera.orig.z),
            ),
            "camera.target": (
                float(self.config.camera.target.x),
                float(self.config.camera.target.y),
                float(self.config.camera.target.z),
            ),
            "spheres": [],
        }
        for s in self.config.spheres:
            defaults["spheres"].append(
                {
                    "rad": float(s.rad),
                    "p": (float(s.p.x), float(s.p.y), float(s.p.z)),
                    "e": (float(s.e.x), float(s.e.y), float(s.e.z)),
                    "c": (float(s.c.x), float(s.c.y), float(s.c.z)),
                    "refl": s.refl,
                }
            )
        return defaults

    def _get_current_sphere(self):
        if not self.config.spheres:
            raise RuntimeError("场景中没有球体")
        idx = getattr(self.config, "current_sphere", 0)
        idx = max(0, min(idx, len(self.config.spheres) - 1))
        return self.config.spheres[idx]

    def _default_sphere_value(self, field):
        if not self.defaults.get("spheres"):
            return None
        idx = getattr(self.config, "current_sphere", 0)
        idx = max(0, min(idx, len(self.defaults["spheres"]) - 1))
        return self.defaults["spheres"][idx].get(field)

    def _set_sphere_rad(self, value):
        self._get_current_sphere().rad = value

    def _calc_range(self, kind, value, sensitivity):
        sensitivity = max(0.01, float(sensitivity))
        if kind == "gamma":
            span = max(1.0, abs(value) * 2.0 + 0.5) * sensitivity
            min_bound, max_bound = 0.05, 10.0
            span = min(span, value - min_bound, max_bound - value)
            span = max(0.0, span)
            return value - span, value + span
        if kind == "radius":
            span = max(5.0, abs(value) * 2.0 + 1.0) * sensitivity
            min_bound = 0.01
            span = min(span, value - min_bound)
            span = max(0.0, span)
            return value - span, value + span
        if kind == "color":
            span = max(2.0, abs(value) * 2.0 + 1.0) * sensitivity
            return value - span, value + span
        if kind == "emission":
            span = max(5.0, abs(value) * 2.0 + 1.0) * sensitivity
            min_bound = 0.0
            span = min(span, value - min_bound) if value >= min_bound else span
            span = max(0.0, span)
            return value - span, value + span
        span = max(10.0, abs(value) * 2.0 + 2.0) * sensitivity
        return value - span, value + span

    def _load_from_config(self):
        self._refresh_camera_fields()
        self._refresh_sphere_list()
        self._load_sphere_fields()

    def _refresh_camera_fields(self):
        cam = self.config.camera
        self._set_vec_vars(self.cam_orig_entries, cam.orig)
        self._set_vec_vars(self.cam_target_entries, cam.target)
        self.gamma_var.set(f"{self.config.gamma:.3f}")

    def _refresh_sphere_list(self):
        self.sphere_list.delete(0, tk.END)
        for i, s in enumerate(self.config.spheres):
            self.sphere_list.insert(
                tk.END,
                f"#{i} r={s.rad:.3f} p=({s.p.x:.1f},{s.p.y:.1f},{s.p.z:.1f})",
            )
        if self.config.spheres:
            current = getattr(self.config, "current_sphere", 0)
            current = max(0, min(current, len(self.config.spheres) - 1))
            self.sphere_list.selection_set(current)

    def _load_sphere_fields(self):
        idx = self._selected_sphere_index()
        if idx is None:
            return
        s = self.config.spheres[idx]
        if not self._should_skip_update(self.sphere_rad_entry):
            self.sphere_rad_var.set(f"{s.rad:.3f}")
        self._set_vec_vars(self.sphere_p_entries, s.p)
        self._set_vec_vars(self.sphere_e_entries, s.e)
        self._set_vec_vars(self.sphere_c_entries, s.c)
        if not self._should_skip_update(self.refl_combo):
            refl_name = {
                Refl.DIFF: "DIFF",
                Refl.SPEC: "SPEC",
                Refl.REFR: "REFR",
            }.get(s.refl, "DIFF")
            self.refl_var.set(refl_name)
        self.config.current_sphere = idx
        if not self.sphere_list.curselection():
            self.sphere_list.selection_clear(0, tk.END)
            self.sphere_list.selection_set(idx)

    def _selected_sphere_index(self):
        sel = self.sphere_list.curselection()
        if sel:
            return int(sel[0])
        if self.config.spheres:
            return getattr(self.config, "current_sphere", 0)
        return None

    def apply_camera(self):
        try:
            self._apply_vec_vars(self.cam_orig_entries, self.config.camera.orig)
            self._apply_vec_vars(self.cam_target_entries, self.config.camera.target)
            gamma = float(self.gamma_var.get())
            if gamma <= 0:
                raise ValueError
            self.config.gamma = gamma
            for dev in self.config.render_devices:
                dev.update_gamma(gamma)
        except ValueError:
            return
        self.config.reinit(False)

    def apply_sphere(self):
        idx = self._selected_sphere_index()
        if idx is None:
            return
        s = self.config.spheres[idx]
        try:
            s.rad = float(self.sphere_rad_var.get())
            self._apply_vec_vars(self.sphere_p_entries, s.p)
            self._apply_vec_vars(self.sphere_e_entries, s.e)
            self._apply_vec_vars(self.sphere_c_entries, s.c)
        except ValueError:
            return
        refl = self.refl_var.get()
        s.refl = {
            "DIFF": Refl.DIFF,
            "SPEC": Refl.SPEC,
            "REFR": Refl.REFR,
        }.get(refl, Refl.DIFF)
        self.config.reinit_scene()
        self._refresh_sphere_list()

    def _reset_sampling(self):
        self.config.reinit(False)

    def _set_vec_vars(self, vars_list, vec):
        self._update_var_if_not_focused(vars_list[0][1], vars_list[0][0], vec.x)
        self._update_var_if_not_focused(vars_list[1][1], vars_list[1][0], vec.y)
        self._update_var_if_not_focused(vars_list[2][1], vars_list[2][0], vec.z)

    def _apply_vec_vars(self, vars_list, vec):
        vec.x = float(vars_list[0][0].get())
        vec.y = float(vars_list[1][0].get())
        vec.z = float(vars_list[2][0].get())

    def _should_skip_update(self, widget):
        try:
            focus = self.root.focus_get()
        except KeyError:
            return False
        return focus == widget

    def _update_var_if_not_focused(self, entry, var, value):
        if not self._should_skip_update(entry):
            var.set(f"{value:.3f}")

    def _is_editing_sphere_fields(self):
        try:
            focus = self.root.focus_get()
        except KeyError:
            return False
        sphere_entries = [
            self.sphere_rad_entry,
            self.refl_combo,
            self.sphere_p_entries[0][1],
            self.sphere_p_entries[1][1],
            self.sphere_p_entries[2][1],
            self.sphere_e_entries[0][1],
            self.sphere_e_entries[1][1],
            self.sphere_e_entries[2][1],
            self.sphere_c_entries[0][1],
            self.sphere_c_entries[1][1],
            self.sphere_c_entries[2][1],
        ]
        return focus in sphere_entries

    def _schedule_refresh(self):
        self.root.after(self.refresh_ms, self._refresh_tick)

    def _refresh_tick(self):
        self._refresh_if_idle()
        self._schedule_refresh()

    def _refresh_if_idle(self):
        if not self._should_skip_update(self.gamma_entry):
            self.gamma_var.set(f"{self.config.gamma:.3f}")
        cam = self.config.camera
        self._set_vec_vars(self.cam_orig_entries, cam.orig)
        self._set_vec_vars(self.cam_target_entries, cam.target)
        if (
            not self._should_skip_update(self.sphere_list)
            and not self._is_editing_sphere_fields()
        ):
            self._refresh_sphere_list()
            self._load_sphere_fields()

    def run(self):
        self.root.mainloop()


def start_control_panel(config):
    """在后台线程启动控制面板"""

    def _run():
        panel = ControlPanel(config)
        panel.run()

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    return thread
