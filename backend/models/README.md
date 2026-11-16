# 姿态模型资产说明

本目录放**姿态估计模型**。注意：**大模型不入库**，需要本地准备。

## 一、已入库的

| 文件 | 大小 | 用途 |
|---|---|---|
| `pose_landmarker_lite.task` | 5.5 MB | MediaPipe BlazePose（旧链路 `vision/pose_estimator.py`，实时模式还在用） |

这个文件已在仓库里，clone 下来就有，**不需要额外操作**。

## 二、不入库的：Lightweight OpenPose

坐姿抽检模块（`vision/pose_lw.py`）用的是 [Lightweight OpenPose](https://github.com/Daniil-Osokin/lightweight-human-pose-estimation.pytorch)，
需要「仓库 + 权重」两样东西，**总量约 90 MB，不进仓库**。

原因：
- 权重 `checkpoint_iter_370000.pth` 共 **88 MB**，逼近 GitHub 单文件 100 MB 硬限制；
- 加上 PyTorch（CPU 版约 200 MB）会让干净机器上的首次部署非常慢；
- 这两样都有稳定的官方来源，用一次命令就能拿到，没必要让每个人 clone 一个 90 MB 的二进制。

### 准备步骤（一次即可）

```powershell
# 1) 装 CPU 版 PyTorch（约 200MB；别装 CUDA 版）
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 2) 把 LW 仓库 clone 到**项目根**（与 backend 同级）
cd G:\中级实训
git clone https://github.com/Daniil-Osokin/lightweight-human-pose-estimation.pytorch.git

# 3) 下载权重（约 88MB）
New-Item -ItemType Directory -Force "G:\中级实训\lightweight-human-pose-estimation.pytorch\checkpoints" | Out-Null
curl.exe -L -o "G:\中级实训\lightweight-human-pose-estimation.pytorch\checkpoints\checkpoint_iter_370000.pth" `
  "https://download.01.org/opencv/openvino_training_extensions/models/human_pose_estimation/checkpoint_iter_370000.pth"
```

> 第 3 步的域名是 Intel 老地址，若 404，改用 OpenVINO Model Zoo 或该仓库 issue 里给出的镜像。

### 配置怎么指

`backend/config.yaml`：

```yaml
sitting:
  lw_repo: ../../lightweight-human-pose-estimation.pytorch   # 相对 backend/
  lw_checkpoint: checkpoints/checkpoint_iter_370000.pth      # 相对 lw_repo
```

### 验证是否准备好

```powershell
cd G:\中级实训\xiaoqi\backend
python -c "from xiaoqi.config import load_config; from xiaoqi.vision.pose_lw import LWPoseEstimator as E; c=load_config(); e=E(c.sitting_lw_repo,c.sitting_lw_checkpoint); print('ok=',e.ok,'| err=',e.last_error)"
```

预期：`ok= True | err= None`

失败时 `last_error` 会明确写出缺哪一步（没装 torch / 仓库路径不对 / 权重缺失）。

## 三、为什么不把权重放进 Git LFS

5.5 MB 的 MediaPipe 模型直接入库是划算的（M4-5「干净机器从零跑」不依赖网络）。
但 88 MB 的 LW 权重即使上了 LFS，clone 时的拉取时长和流量成本也不划算，
而且抽检是可选功能（`sitting.enabled: false` 即可关闭）——所以走"本地准备"。

> 如果后续确实需要一键部署，建议做成 `scripts/setup_pose_lw.ps1` 自动下载 + 校验哈希，
> 而不是把二进制塞进 Git。
