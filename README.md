# 🎵 NetEase Cloud Music VIP Decryptor & Universal Converter (网易云音乐 VIP 歌曲解密 & 全能转换工具)

<p align="center">
  <img src="app_icon.png" width="128" height="128" alt="CloudMusicConverter Logo">
</p>

<p align="center">
  <strong>现代化 · 高保真 · 全兼容 · 批量解密 NCM / 无损还原 / 智能转码 MP3 & AAC</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python Version">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=flat-square&logo=windows&logoColor=white" alt="Platform">
  <img src="https://img.shields.io/badge/Encoder-FFmpeg%20%7C%20libmp3lame-007808?style=flat-square" alt="Encoder">
  <a href="https://github.com/studioj2y/163MusicConverter"><img src="https://img.shields.io/badge/GitHub-studioj2y%2F163MusicConverter-181717?style=flat-square&logo=github" alt="GitHub"></a>
  <img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License">
</p>

---

## 📖 项目简介

从网易云音乐客户端下载的 VIP 歌曲通常带有专有加密（`.ncm` 格式），导致无法直接在第三方播放器、车载中控、Hi-Fi 随身听或手机中播放。

本项目是一款专为 Windows 用户打造的现代化桌面音频解密与格式转换工具。基于 **CustomTkinter** 与 **TkinterDnD** 开发，具备现代浅色/深色卡片式 UI、原生拖拽导入、增量历史比对、无损流式解密以及基于开源行业金标编码器 **FFmpeg (`libmp3lame` / `aac`)** 的最优参数转码能力。

---

## ✨ 核心特性

### 1. 🎯 三大目标格式与声学优化
* **源文件（仅解密）**：
  * **原汁原味**：直接解密提取 NCM 内封装的母带音频流（无损 **FLAC** 或 **320kbps MP3**）。
  * **零重编码损耗**：瞬间完成，并自动通过 Mutagen 写入完整的 ID3v2 / FLAC Vorbis 元数据与内嵌高清专辑封面。
  * 自动禁用冗余码率选项，避免设置困扰。
* **MP3 通用音频 (`libmp3lame`)**：
  * 支持指定码率：
    * `320 kbps (CBR 恒定码率 - 最高音质/推荐)`
    * `256 kbps (CBR 恒定码率 - 高品质)`
    * `192 kbps (CBR 恒定码率 - 标准品质)`
    * `128 kbps (CBR 恒定码率 - 紧凑便携)`
    * `VBR V0 (~245 kbps 动态码率 - 极高音质)`
    * `VBR V2 (~190 kbps 动态码率 - 黄金平衡)`
    * `VBR V5 (~130 kbps 动态码率 - 相当于128k便携档)`
  * **车机全兼容规范**：自动采用 **ID3v2.3** 规范并追加 **ID3v1** 尾部标签，内嵌高清封面，完美兼容车载中控、旧款 MP3 播放器与手机。
* **AAC / M4A (`aac` in `.m4a` 容器)**：
  * 支持指定码率：
    * `320 kbps (CBR 恒定码率 - 极限高保真)`
    * `256 kbps (CBR 恒定码率 - Apple iTunes Plus 推荐)`
    * `192 kbps (CBR 恒定码率 - 标准高质量)`
    * `128 kbps (CBR 恒定码率 - 高性价比便携)`
    * `VBR 动态质量 (~190-220 kbps 动态高保真)`
    * `VBR 动态质量 (~120-140 kbps 动态紧凑便携)`
  * **流式秒开规范**：采用通用的 `.m4a` 容器封装，默认高保真 CBR 模式彻底杜绝车机寻轨漂移，并自动启用 **FastStart**（Moov Atom 提前），内嵌封面与元数据，无缝适配 iOS、macOS、Android 及 Hi-Fi 设备。

### 2. 🔍 智能增量比对与筛选（省时省力）
* **一键筛选未转换歌曲**：点击工具栏的 **「🔍 筛选未转换 (剔除已存在)」**，毫秒级快速比对输出目录，自动剔除已经转换过的历史歌曲，**只保留新增未转换的歌曲**。
* **导入时自动排除**：勾选下方「导入时自动排除已转换歌曲」后，每次拖入整个目录或点击一键导入，系统会在载入时**自动跳过历史已转换歌曲，列表仅展示真正需要转换的新歌曲**。

### 3. 🎨 统一规范的现代 UI/UX
* **浅色 / 深色无缝切换**：采用 Slate-50 高质感轻量背景与卡片式容器，右上角支持随时切换深/浅主题。
* **高反差分段按钮**：选中项反白纯白文字，视觉层次清晰。
* **完备的鼠标与右键菜单**：
  * 支持批量将文件或文件夹从 Windows 资源管理器直接拖入。
  * **右键菜单**：支持播放已转换音频、在资源管理器中定位源文件、移除选中、筛选未转换、清空列表。
  * **双击联动**：双击已完成歌曲即可直接调用系统默认播放器试听；未完成歌曲则定位文件所在目录。
* **全局快捷键支持**：
  * `Ctrl+O`：添加文件
  * `Ctrl+D`：添加文件夹
  * `Ctrl+F`：筛选未转换
  * `Ctrl+L`：清空列表
  * `Delete`：移除选中项
  * `Alt+S`：开始 / 停止转换

---

## 📁 目录结构

```text
CloudMusicConverter/
├── app.py                      # 桌面 GUI 主程序 (CustomTkinter + TkinterDnD)
├── task_manager.py             # 多线程转换管道与增量比对引擎
├── ncm_cipher.py               # 流式分块 NCM 解密算法与 Mutagen 标签写入引擎
├── ffmpeg_engine.py            # FFmpeg 自动发现、最优参数配置与转码进度跟踪
├── config.py                   # 本地用户配置持久化管理
├── app_icon.ico                # 多分辨率 Windows 应用图标 (16x16 ~ 256x256)
├── app_icon.png                # 高清品牌图标素材
├── run.bat                     # Windows 便捷静默启动脚本 (无控制台黑框)
├── run_debug.bat               # Windows 带控制台调试启动脚本
├── create_desktop_shortcut.bat # 一键在桌面创建带专属图标的快捷方式
├── requirements.txt            # Python 依赖清单
├── settings.json.example       # 配置模板文件
├── tests/
│   └── test_suite.py           # 自动化单元与集成测试套件
└── README.md                   # 项目使用与技术说明文档
```

---

## 🚀 快速开始

### 1. 获取代码与安装依赖

确保您的系统已安装 **Python 3.8+** 以及 **FFmpeg**：
```bash
git clone https://github.com/studioj2y/163MusicConverter.git
cd 163MusicConverter
pip install -r requirements.txt
```

### 2. 启动应用

#### 方式 A：双击启动脚本（推荐）
直接双击运行目录下的 **`run.bat`** 即可静默启动图形界面。

#### 方式 B：命令行启动
```bash
python app.py
```

#### 方式 C：创建桌面图标
双击执行 **`create_desktop_shortcut.bat`**，即可直接在 Windows 桌面上生成带有专属耳麦图标的快捷方式。

---

## 🧪 自动化测试

运行内置的完整测试套件：
```bash
python tests/test_suite.py
```

---

## 📄 开源许可证

本项目基于 [MIT 许可证](LICENSE) 开源。仅供个人技术研究与已购数字音乐的跨设备播放用途使用，请支持正版音乐。
