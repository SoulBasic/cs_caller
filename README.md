# cs_caller

一个用于验证 CS 小地图报点流程的原型项目，当前包含：

1. 帧源抽象（Mock 图片帧源 + 原生 NDI 接收 + OpenCV capture）。
2. OpenCV HSV 红点检测。
3. 用户定义区域映射（当前以拖拽矩形生成为多边形）。
4. TTS 播报（`pyttsx3` 优先，失败自动回退到控制台输出）。
5. 可视化区域编辑器（实时预览、拖拽框选、地图配置持久化）。

## 安装

```bash
cd cs_caller
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

NDI 模式额外依赖：

```bash
pip install "cyndilib==0.0.9"
```

## CLI 用法

### 0) 严格 2 步快速开跑（推荐）

1. **OBS 开 NDI 输出**：`工具 -> NDI 输出设置` 勾选主输出（源名建议 `OBS`）。
2. **启动 GUI 后点一次“连接并开始播报”**：

```bash
python -m cs_caller.cli gui --source-mode ndi --map de_dust2
```

说明：
- `ndi` 模式下如果源留空，GUI 会自动填 `ndi://OBS`。
- `ndi` 源输入支持三种写法：`OBS`、`ndi://OBS`、完整源名（如 `OBS Studio (DESKTOP-XXX)`）。
- 连接成功后会自动开启检测与语音播报；如只想看画面可点“仅预览”。

### 1) 启动 GUI 编辑器

```bash
python -m cs_caller.cli gui --source-mode mock --image /absolute/path/to/minimap.png --map de_dust2
```

常用参数：

- `--source-mode`：`mock|ndi|capture`
- `--source`：在 `ndi/capture` 模式下指定源（例：`OBS`、`ndi://OBS`、`OBS Studio (DESKTOP-XXX)`、`0`、`rtsp://...`）
- `--maps-dir`：地图 YAML 目录（默认 `config/maps`）
- `--fps`：预览帧率（默认 `16`）
- `--tts-backend`：`auto|pyttsx3|console`
- `--settings-path`：运行设置文件（默认 `config/app_settings.yaml`）

NDI 示例（原生接收，不走 `cv2.VideoCapture`）：

```bash
python -m cs_caller.cli gui --source-mode ndi --source "OBS"
```

编辑器中可完成：

- 实时预览帧
- 视频源连接面板（模式/源文本/连接或重连）
- 一键动作：“连接并开始播报”“保存并开始播报”“仅预览”
- 可在不关闭编辑器的情况下切换 `mock|ndi|capture` 并重连
- 源连接状态与错误横幅提示（失败不退出 GUI）
- 运行模式提示（未连接 / 仅预览 / 播报模式）
- 鼠标拖拽画矩形区域
- 释放鼠标后输入 callout 文本
- 地图新建/载入/保存（保存到 `config/maps/<map>.yaml`）
- 开启“运行检测并播报”查看映射与语音触发
- 自动记忆上次设置（`config/app_settings.yaml`：地图、源模式、源文本、TTS）
- 自动记忆检测开关（播报模式/仅预览）
- 未传入 `--map/--source-mode/--source/--tts-backend` 时会自动读取上次设置

### 2) 使用配置执行 mock 检测

```bash
python -m cs_caller.cli mock --image /absolute/path/to/minimap.png --map de_dust2
```

可选参数：

- `--map-config`：直接指定 YAML 文件，优先于 `--map`
- `--cooldown`：同一报点冷却秒数（默认 `2.0`）
- `--stable-frames`：连续稳定帧门槛（默认 `3`）
- `--max-frames`：最多处理帧数（默认 `120`）
- `--tts-backend`：`auto|pyttsx3|console`

## Windows 单EXE打包（单进程）

> 按大师要求：保持单进程，不拆前后端。

1. 准备一张默认样图到：`assets/minimap_sample.png`
2. 在 Windows PowerShell/cmd 运行：

```bat
scripts\windows\build_exe.bat
```

3. 产物：`dist\cs_caller\cs_caller.exe`

说明：
- EXE 启动后直接进入 GUI 编辑器。
- 配置保存在 `config/maps/*.yaml`。
- 后续接入 NDI 时仍保持同一进程内运行。

## Windows 使用说明（中文）

### Windows 免编译安装（NDI）

```powershell
cd C:\path\to\cs_caller
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
python -m pip install "cyndilib==0.0.9"
```

然后安装 NDI Runtime（必须）：
- 打开 `https://ndi.video/tools/ndi-core-suite/`
- 下载并安装 NDI Runtime/Core Suite（x64）
- 安装后重启 PowerShell，再运行 GUI

### 环境准备

1. 安装 Python 3.10+（建议 3.11）。
2. 在 PowerShell 中进入项目目录：

```powershell
cd C:\path\to\cs_caller
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .
```

3. 安装原生 NDI 后端（免编译）：

```powershell
python -m pip install --upgrade pip
python -m pip install "cyndilib==0.0.9"
```

4. 安装 NDI Runtime（必须）：
   - 打开 `https://ndi.video/tools/ndi-core-suite/`
   - 下载并安装 NDI Runtime/Core Suite（x64）
   - 安装完成后重启终端，再执行 GUI

### 启动 GUI 编辑器

```powershell
python -m cs_caller.cli gui --image C:\abs\minimap.png --map de_dust2
```

操作流程：

1. 左上角输入或选择地图名，点击“载入”或“新建”。
2. 在画面上按住左键拖拽框选区域。
3. 松开鼠标后输入报点文本（如 `A Site`）。
4. 点击“保存”，配置写入 `config/maps/<地图名>.yaml`。
5. 勾选“运行检测并播报”可直接验证红点映射和语音触发。

### OBS 开启 NDI 后怎么一步跑起来（Windows）

1. OBS 菜单点击 `工具 -> NDI 输出设置`，勾选主输出，源名建议固定为 `OBS`。
2. 在项目目录运行（只需这一条命令）：

```powershell
python -m cs_caller.cli gui --source-mode ndi --map de_dust2
```

GUI 打开后点“连接并开始播报”即可：
- `ndi` 源留空会自动填 `ndi://OBS`；
- 也可直接填 `OBS` 或完整源名，程序会做不区分大小写的精确/包含匹配；
- 状态为“已连接”即成功拉流；
- 若失败，错误横幅会提示原因，并显示“当前发现的 NDI 源数量与名称”；此时可直接把模式切到 `mock` 并填入本地图片路径，再点“重连源”，无需重启程序。

备注：
- 程序为单进程架构；但 NDI 握手（discover/connect probe）会临时启用子进程隔离，避免 `cyndilib` 阻塞 GUI 主进程。
- NDI 握手默认硬超时 3 秒（可用环境变量 `CS_CALLER_NDI_PROBE_TIMEOUT_S` 调整）；超时会主动终止子进程并返回清晰错误横幅。
- 上次成功使用的地图/源模式/源字符串/TTS 会写入 `config/app_settings.yaml`，下次自动带出。

### 超时环境变量（推荐）

- `CS_CALLER_CONNECT_TIMEOUT_MS`：GUI 连接超时（毫秒），默认 `10000`，允许范围 `3000-30000`（超出范围会回退默认值）。
- `CS_CALLER_NDI_PROBE_TIMEOUT_S`：NDI 握手子进程超时（秒），默认 `3`，内部会限制在 `0.5-10.0`。
- 推荐值（OBS + NDI 常用）：`CS_CALLER_CONNECT_TIMEOUT_MS=10000`，`CS_CALLER_NDI_PROBE_TIMEOUT_S=5`。
- 建议保持 GUI 超时大于 NDI probe 超时（至少多 2 秒），避免 probe 未结束前 GUI 先误报超时。

### 常见问题排查（精确对照）

| 现象 | 快速定位 | 精确处理 |
| --- | --- | --- |
| 点击连接后未响应 | 状态长期停留“连接中...”，但窗口可继续操作 | 1) `ndi` 模式握手在短生命周期子进程中执行，主 GUI 不会被阻塞；2) 若超时会在状态/横幅显示当前超时阈值（例如 10.0s）；3) 优先确认 OBS NDI 输出已开启、源名与 GUI 输入一致；4) 若仍不稳定，适当提高 `CS_CALLER_CONNECT_TIMEOUT_MS` 与 `CS_CALLER_NDI_PROBE_TIMEOUT_S`，再重试；5) 仍失败可先切到 `mock` 验证流程。 |
| 打不开流（连接失败） | GUI 顶部“视频源连接”状态为“连接失败”且有红色横幅 | 1) 确认 OBS `工具 -> NDI 输出设置` 已开启主输出；2) `source` 可填 `OBS` / `ndi://OBS` / 完整源名；3) 对照横幅里“发现 N 个源: ...”修正输入；4) 按预检提示安装 `cyndilib` 与 NDI Runtime。 |
| 无画面（连上但黑屏/卡住） | 状态为“已连接”但画布无更新，或出现“读取异常” | 1) OBS 先确认推流画面在动；2) 检查防火墙/局域网连通；3) 点“重连源”；4) 仍失败先切 `mock` 验证检测链路。 |
| 有画面不播报 | 画布有画面，但无“检测到: xxx”覆盖文本或无语音 | 1) 勾选“运行检测并播报”；2) 检查区域是否覆盖红点位置并已保存地图；3) 切换 `--tts-backend console` 验证是否仅 TTS 后端问题。 |

### 使用已保存配置运行

```powershell
python -m cs_caller.cli mock --image C:\abs\minimap.png --map de_dust2 --tts-backend auto
```

## 目录结构

```text
cs_caller/
  config/maps/
  src/cs_caller/
    announcer.py
    callout_mapper.py
    detector.py
    frame_clock.py
    map_config_store.py
    region_editor.py
    pipeline.py
    cli.py
    gui/
      app.py
    sources/
      base.py
      ndi_native.py
      mock_source.py
    tts/
      base.py
      console_tts.py
      pyttsx3_tts.py
  tests/
```
