// rendering_kernel.cl
// 光线追踪渲染内核，适用于现代 OpenCL 环境

// 结构定义
typedef struct {
    float x, y, z; // 位置或颜色
} Vec;

typedef struct {
    Vec o, d; // 射线起点和方向
} Ray;

typedef struct {
    float rad; // 半径
    Vec p, e, c; // 位置、发射光、颜色
    int refl; // 反射类型: 0-DIFF（漫反射）, 1-SPEC（镜面反射）, 2-REFR（折射）
} Sphere;

typedef struct {
    Vec orig, target; // 相机原点和目标
    Vec dir, x, y; // 相机方向、水平和垂直向量
} Camera;

// 常量定义
#define EPSILON 0.01f
#define FLOAT_PI 3.14159265358979323846f
#define DIFF 0
#define SPEC 1
#define REFR 2

// 向量操作函数
Vec vadd(Vec a, Vec b)
{
    Vec result;
    result.x = a.x + b.x;
    result.y = a.y + b.y;
    result.z = a.z + b.z;
    return result;
}

Vec vsub(Vec a, Vec b)
{
    Vec result;
    result.x = a.x - b.x;
    result.y = a.y - b.y;
    result.z = a.z - b.z;
    return result;
}

Vec vmul(Vec a, Vec b)
{
    Vec result;
    result.x = a.x * b.x;
    result.y = a.y * b.y;
    result.z = a.z * b.z;
    return result;
}

Vec vsmul(float k, Vec a)
{
    Vec result;
    result.x = k * a.x;
    result.y = k * a.y;
    result.z = k * a.z;
    return result;
}

float vdot(Vec a, Vec b)
{
    return a.x * b.x + a.y * b.y + a.z * b.z;
}

Vec vnorm(Vec v)
{
    float len = sqrt(vdot(v, v));
    return vsmul(1.0f / len, v);
}

Vec vxcross(Vec a, Vec b)
{
    Vec result;
    result.x = a.y * b.z - a.z * b.y;
    result.y = a.z * b.x - a.x * b.z;
    result.z = a.x * b.y - a.y * b.x;
    return result;
}

int viszero(Vec v)
{
    return (v.x == 0.0f) && (v.y == 0.0f) && (v.z == 0.0f);
}

// 随机数生成函数
float get_random(uint* seed0, uint* seed1)
{
    *seed0 = 36969 * (*seed0 & 0xffff) + (*seed0 >> 16);
    *seed1 = 18000 * (*seed1 & 0xffff) + (*seed1 >> 16);
    uint ires = (*seed0 << 16) + *seed1;
    uint ui = (ires & 0x007fffff) | 0x40000000;
    union {
        uint u;
        float f;
    } converter;
    converter.u = ui;
    return (converter.f - 2.0f) / 2.0f;
}

// 球体相交测试（使用 __constant）
float sphere_intersect(const __constant Sphere* s, const Ray* r)
{
    Vec op = vsub(s->p, r->o);
    float b = vdot(op, r->d);
    float det = b * b - vdot(op, op) + s->rad * s->rad;
    if (det < 0.0f)
        return 0.0f;
    det = sqrt(det);
    float t = b - det;
    if (t > EPSILON)
        return t;
    t = b + det;
    if (t > EPSILON)
        return t;
    return 0.0f;
}

// 场景相交测试
int intersect(const __constant Sphere* spheres, uint sphere_count, const Ray* r, float* t, uint* id)
{
    float inf = 1e20f;
    *t = inf;
    int hit = 0;
    for (uint i = 0; i < sphere_count; ++i) {
        float d = sphere_intersect(&spheres[i], r);
        if (d != 0.0f && d < *t) {
            *t = d;
            *id = i;
            hit = 1;
        }
    }
    return hit;
}

// 阴影射线相交测试
int intersect_p(const __constant Sphere* spheres, uint sphere_count, const Ray* r, float maxt)
{
    for (uint i = 0; i < sphere_count; ++i) {
        float d = sphere_intersect(&spheres[i], r);
        if (d != 0.0f && d < maxt)
            return 1;
    }
    return 0;
}

// 采样光源
Vec sample_lights(const __constant Sphere* spheres, uint sphere_count, uint* seed0, uint* seed1, Vec hit_point, Vec normal)
{
    Vec result = { 0.0f, 0.0f, 0.0f };
    for (uint i = 0; i < sphere_count; ++i) {
        const __constant Sphere* light = &spheres[i];
        if (!viszero(light->e)) {
            float u1 = get_random(seed0, seed1);
            float u2 = get_random(seed0, seed1);
            float zz = 1.0f - 2.0f * u1;
            float r = sqrt(max(0.0f, 1.0f - zz * zz));
            float phi = 2.0f * FLOAT_PI * u2;
            Vec unit_sphere_point = { r * cos(phi), r * sin(phi), zz };
            Vec sphere_point = vadd(light->p, vsmul(light->rad, unit_sphere_point));
            Vec shadow_dir = vsub(sphere_point, hit_point);
            float len = sqrt(vdot(shadow_dir, shadow_dir));
            shadow_dir = vsmul(1.0f / len, shadow_dir);
            float wo = vdot(shadow_dir, unit_sphere_point);
            if (wo > 0.0f)
                continue;
            wo = -wo;
            float wi = vdot(shadow_dir, normal);
            if (wi > 0.0f && !intersect_p(spheres, sphere_count, &(Ray) { hit_point, shadow_dir }, len - EPSILON)) {
                Vec c = light->e;
                float s = (4.0f * FLOAT_PI * light->rad * light->rad) * wi * wo / (len * len);
                result = vadd(result, vsmul(s, c));
            }
        }
    }
    return result;
}

// 光线追踪主函数
Vec radiance(const __constant Sphere* spheres, uint sphere_count, const Ray* start_ray, uint* seed0, uint* seed1)
{
    Ray current_ray = *start_ray;
    Vec rad = { 0.0f, 0.0f, 0.0f };
    Vec throughput = { 1.0f, 1.0f, 1.0f };
    int depth = 0;
    int specular_bounce = 1;
    while (depth < 6) {
        float t;
        uint id;
        if (!intersect(spheres, sphere_count, &current_ray, &t, &id)) {
            return rad;
        }
        const __constant Sphere* obj = &spheres[id];
        Vec hit_point = vadd(current_ray.o, vsmul(t, current_ray.d));
        Vec normal = vnorm(vsub(hit_point, obj->p));
        float dp = vdot(normal, current_ray.d);
        Vec nl = dp < 0.0f ? normal : vsmul(-1.0f, normal);
        Vec e_col = obj->e;
        if (!viszero(e_col)) {
            if (specular_bounce) {
                Vec contrib = vsmul(fabs(dp), e_col);
                rad = vadd(rad, vmul(throughput, contrib));
            }
            return rad;
        }
        if (obj->refl == DIFF) {
            specular_bounce = 0;
            throughput = vmul(throughput, obj->c);
            Vec ld = sample_lights(spheres, sphere_count, seed0, seed1, hit_point, nl);
            rad = vadd(rad, vmul(throughput, ld));
            float r1 = 2.0f * FLOAT_PI * get_random(seed0, seed1);
            float r2 = get_random(seed0, seed1);
            float r2s = sqrt(r2);
            Vec w = nl;
            Vec u = vnorm(vxcross(fabs(w.x) > 0.1f ? (Vec) { 0.0f, 1.0f, 0.0f } : (Vec) { 1.0f, 0.0f, 0.0f }, w));
            Vec v = vxcross(w, u);
            Vec new_dir = vnorm(vadd(vadd(vsmul(cos(r1) * r2s, u), vsmul(sin(r1) * r2s, v)), vsmul(sqrt(1.0f - r2), w)));
            current_ray.o = hit_point;
            current_ray.d = new_dir;
        } else if (obj->refl == SPEC) {
            specular_bounce = 1;
            Vec new_dir = vsub(current_ray.d, vsmul(2.0f * vdot(normal, current_ray.d), normal));
            throughput = vmul(throughput, obj->c);
            current_ray.o = hit_point;
            current_ray.d = new_dir;
        } else { // REFR
            specular_bounce = 1;
            Vec refl_dir = vsub(current_ray.d, vsmul(2.0f * vdot(normal, current_ray.d), normal));
            int into = vdot(normal, nl) > 0;
            float nc = 1.0f, nt = 1.5f;
            float nnt = into ? nc / nt : nt / nc;
            float ddn = vdot(current_ray.d, nl);
            float cos2t = 1.0f - nnt * nnt * (1.0f - ddn * ddn);
            if (cos2t < 0.0f) {
                throughput = vmul(throughput, obj->c);
                current_ray.o = hit_point;
                current_ray.d = refl_dir;
            } else {
                float kk = (into ? 1.0f : -1.0f) * (ddn * nnt + sqrt(cos2t));
                Vec nkk = vsmul(kk, normal);
                Vec trans_dir = vnorm(vsub(vsmul(nnt, current_ray.d), nkk));
                float a = nt - nc, b = nt + nc;
                float R0 = a * a / (b * b);
                float c = 1.0f - (into ? -ddn : vdot(trans_dir, normal));
                float Re = R0 + (1.0f - R0) * c * c * c * c * c;
                float Tr = 1.0f - Re;
                float P = 0.25f + 0.5f * Re;
                float RP = Re / P;
                float TP = Tr / (1.0f - P);
                if (get_random(seed0, seed1) < P) {
                    throughput = vsmul(RP, throughput);
                    throughput = vmul(throughput, obj->c);
                    current_ray.o = hit_point;
                    current_ray.d = refl_dir;
                } else {
                    throughput = vsmul(TP, throughput);
                    throughput = vmul(throughput, obj->c);
                    current_ray.o = hit_point;
                    current_ray.d = trans_dir;
                }
            }
        }
        depth++;
    }
    return rad;
}

// 生成相机射线
Ray generate_camera_ray(const __constant Camera* camera, uint* seed0, uint* seed1, int width, int height, int x, int y)
{
    float inv_width = 1.0f / width;
    float inv_height = 1.0f / height;
    float r1 = get_random(seed0, seed1) - 0.5f;
    float r2 = get_random(seed0, seed1) - 0.5f;
    float kcx = (x + r1) * inv_width - 0.5f;
    float kcy = (y + r2) * inv_height - 0.5f;
    Vec rdir = vadd(vadd(vsmul(kcx, camera->x), vsmul(kcy, camera->y)), camera->dir);
    rdir = vnorm(rdir);
    Vec rorig = vadd(camera->orig, vsmul(0.1f, rdir));
    Ray ray = { rorig, rdir };
    return ray;
}

// 内核函数
__kernel void RadianceGPU(
    __global Vec* colors, // 输出颜色缓冲区
    __global uint* seeds, // 随机种子缓冲区
    __constant Sphere* spheres, // 场景中的球体数组
    __constant Camera* camera, // 相机参数
    uint sphere_count, // 球体数量
    uint width, // 图像宽度
    uint height, // 图像高度
    uint current_sample, // 当前采样数
    __global uint* pixels, // 输出像素缓冲区
    uint work_offset, // 工作偏移
    uint work_amount)
{
    // 获取全局工作项 ID
    uint gid = get_global_id(0);
    if (gid >= work_amount)
        return;

    // 计算屏幕坐标
    uint scr_x = (work_offset + gid) % width;
    uint scr_y = (work_offset + gid) / width;

    // 获取随机种子
    uint seed_index = gid * 2;
    uint seed0 = seeds[seed_index];
    uint seed1 = seeds[seed_index + 1];

    // 生成相机射线并计算辐射值
    Ray ray = generate_camera_ray(camera, &seed0, &seed1, width, height, scr_x, scr_y);
    Vec r = radiance(spheres, sphere_count, &ray, &seed0, &seed1);

    // 累积颜色
    if (current_sample == 0) {
        colors[gid] = r;
    } else {
        float k1 = (float)current_sample;
        float k2 = 1.0f / (current_sample + 1.0f);
        colors[gid].x = (colors[gid].x * k1 + r.x) * k2;
        colors[gid].y = (colors[gid].y * k1 + r.y) * k2;
        colors[gid].z = (colors[gid].z * k1 + r.z) * k2;
    }

    // 转换为像素颜色（RGB）
    // 添加伽马校正（gamma = 2.2）
    float gamma = 2.2f;
    int r_int = (int)(clamp(pow(colors[gid].x, 1.0f / gamma), 0.0f, 1.0f) * 255.0f + 0.5f);
    int g_int = (int)(clamp(pow(colors[gid].y, 1.0f / gamma), 0.0f, 1.0f) * 255.0f + 0.5f);
    int b_int = (int)(clamp(pow(colors[gid].z, 1.0f / gamma), 0.0f, 1.0f) * 255.0f + 0.5f);
    pixels[gid] = (r_int << 16) | (g_int << 8) | b_int;

    // 更新随机种子
    seeds[seed_index] = seed0;
    seeds[seed_index + 1] = seed1;
}