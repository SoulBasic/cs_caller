# cs_caller

一个用于验证 CS 小地图点位报点流程的原型项目，包含以下能力：

1. 以固定 `16fps` 从帧源抽帧（后续可接 NDI）。
2. 使用 OpenCV HSV 阈值检测小地图红色敌人点。
3. 按地图多边形区域将坐标映射为 callout 名称。
4. 通过 TTS 抽象播报 callout，带冷却与稳定性过滤。

## 安装

```bash
cd cs_caller
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## 快速演示（Mock）

`--image` 指向一张小地图截图，程序会重复读取该图并每秒 16 帧处理：

```bash
python -m cs_caller.cli mock --image /absolute/path/to/minimap.png --map de_dust2
```

可选参数：

- `--map-config`：地图配置文件路径（默认 `config/maps/de_dust2.yaml`）
- `--cooldown`：同一报点冷却秒数（默认 `2.0`）
- `--stable-frames`：连续稳定帧数门槛（默认 `3`）
- `--max-frames`：最多处理帧数，便于调试

## 目录结构

```text
cs_caller/
  config/maps/de_dust2.yaml
  src/cs_caller/
    frame_clock.py
    detector.py
    callout_mapper.py
    announcer.py
    pipeline.py
    cli.py
    sources/
      base.py
      mock_source.py
    tts/
      base.py
      console_tts.py
  tests/
```

## 说明

- 当前 NDI 仅保留接口与 TODO stub，便于后续接入。
- 该原型以清晰模块边界为主，便于后续替换检测策略和语音引擎。
