# 姿态模型资产说明

本目录放**姿态估计模型**。Lightweight OpenPose 的仓库与权重**不入库**，需要本地准备一次。

抽检（`vision/pose_lw.py` + `vision/spot_check.py`）是**唯一**姿态源（D-016），没有降级链路：模型未就绪时后端照常起服务，但**等于没有姿态数据**——`GET /api/health` 的 `sitting.model_ready=false`、`pose_source=null`，`last_error` 写明缺哪一步；启动时还会向已连接的 WebSocket 客户端广播 `{"type":"error","code":"POSE_UNAVAILABLE","message":"<原因>"}`，前端据此显示失败原因，不能假装画面里没人。

## 一、不入库的：Lightweight OpenPose

坐姿抽检用的是 [Lightweight OpenPose](https://github.com/Daniil-Osokin/lightweight-human-pose-estimation.pytorch)，
需要「仓库 + 权重」两样东西，**总量约 90 MB，不进仓库**。

原因：
- 权重 `checkpoint_iter_370000.pth` 共 **88 MB**，逼近 GitHub 单文件 100 MB 硬限制；
- 加上 PyTorch（CPU 版约 200 MB）会让干净机器上的首次部署非常慢；
- 这两样都有稳定的官方来源，用一次命令就能拿到，没必要让每个人 clone 一个 90 MB 的二进制。

### 准备步骤（一次即可）

```bash
# 1) 装 CPU 版 PyTorch（约 200MB；别装 CUDA 版）
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 2) 把 LW 仓库 clone 到**仓库根目录的上一级**（与 xiaoqi/ 同级，即 backend 的 ../../）
cd ..                       # 从 xiaoqi/ 进入上一级
git clone https://github.com/Daniil-Osokin/lightweight-human-pose-estimation.pytorch.git

# 3) 下载权重（约 88MB）
LW=lightweight-human-pose-estimation.pytorch
mkdir -p "$LW/checkpoints"
curl -L -o "$LW/checkpoints/checkpoint_iter_370000.pth" \
  "https://download.01.org/opencv/openvino_training_extensions/models/human_pose_estimation/checkpoint_iter_370000.pth"
```

> Windows（组员机）：同样的三步，用 PowerShell —— `python -m pip ...` 不变；`git clone` 不变；
> 第 3 步 `New-Item -ItemType Directory -Force "$LW\checkpoints"` + `curl.exe -L -o "$LW\checkpoints\checkpoint_iter_370000.pth" <url>`。
> 第 3 步的域名是 Intel 老地址，若 404，改用 OpenVINO Model Zoo 或该仓库 issue 里给出的镜像。

### 配置怎么指

`backend/config.yaml`：

```yaml
sitting:
  lw_repo: ../../lightweight-human-pose-estimation.pytorch   # 相对 backend/
  lw_checkpoint: checkpoints/checkpoint_iter_370000.pth      # 相对 lw_repo
```

### 验证是否准备好

```bash
cd backend
python -c "from xiaoqi.config import load_config; from xiaoqi.vision.pose_lw import LWPoseEstimator as E; c=load_config(); e=E(c.sitting_lw_repo,c.sitting_lw_checkpoint); print('ok=',e.ok,'| err=',e.last_error)"
```

预期：`ok= True | err= None`

失败时 `last_error` 会明确写出缺哪一步（没装 torch / 仓库路径不对 / 权重缺失）。

## 二、为什么不把权重放进 Git LFS

LW 权重 88 MB、torch CPU 版约 200 MB，即使上了 LFS，clone 时的拉取时长和流量成本也不划算；
而且这两样有稳定官方来源，走"本地准备"比把二进制塞进仓库更干净。

> 如果后续确实需要一键部署，建议做成 `scripts/setup_pose_lw.ps1` 自动下载 + 校验哈希，
> 而不是把二进制塞进 Git。
