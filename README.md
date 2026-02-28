# cs_caller

一个用于验证 CS 小地图报点流程的原型项目，当前包含：

1. 帧源抽象（Mock 图片帧源 + NDI/OpenCV capture）。
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

## CLI 用法

### 1) 启动 GUI 编辑器

```bash
python -m cs_caller.cli gui --source-mode mock --image /absolute/path/to/minimap.png --map de_dust2
```

常用参数：

- `--source-mode`：`mock|ndi|capture`
- `--source`：在 `ndi/capture` 模式下指定源（例：`ndi://OBS`、`0`、`rtsp://...`）
- `--maps-dir`：地图 YAML 目录（默认 `config/maps`）
- `--fps`：预览帧率（默认 `16`）
- `--tts-backend`：`auto|pyttsx3|console`
- `--settings-path`：运行设置文件（默认 `config/app_settings.yaml`）

NDI 示例：

```bash
python -m cs_caller.cli gui --source-mode ndi --source "ndi://OBS"
```

编辑器中可完成：

- 实时预览帧
- 视频源连接面板（模式/源文本/连接或重连）
- 可在不关闭编辑器的情况下切换 `mock|ndi|capture` 并重连
- 源连接状态与错误横幅提示（失败不退出 GUI）
- 鼠标拖拽画矩形区域
- 释放鼠标后输入 callout 文本
- 地图新建/载入/保存（保存到 `config/maps/<map>.yaml`）
- 开启“运行检测并播报”查看映射与语音触发
- 自动记忆上次设置（`config/app_settings.yaml`：地图、源模式、源文本、TTS）
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

1. 在 OBS 安装并启用 NDI 插件（obs-ndi），重启 OBS。
2. OBS 菜单点击 `工具 -> NDI 输出设置`，勾选主输出，源名建议固定为 `OBS`。
3. 确认 Windows 已安装 NDI Runtime（否则 GUI 会在连接区给出错误横幅）。
4. 在项目目录运行（只需这一条命令）：

```powershell
python -m cs_caller.cli gui --source-mode ndi --source "ndi://OBS" --map de_dust2
```

5. GUI 打开后，顶部“视频源连接”区会显示当前模式与源：
   - 状态为“已连接”即成功拉流；
   - 若失败，错误横幅会提示原因，此时可直接把模式切到 `mock` 并填入本地图片路径，再点“重连源”，无需重启程序。

备注：
- 程序为单进程架构，NDI 失败不会导致 GUI 退出。
- 上次成功使用的地图/源模式/源字符串/TTS 会写入 `config/app_settings.yaml`，下次自动带出。

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
      mock_source.py
    tts/
      base.py
      console_tts.py
      pyttsx3_tts.py
  tests/
```
