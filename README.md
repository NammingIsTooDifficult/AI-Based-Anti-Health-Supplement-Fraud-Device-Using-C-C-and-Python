```markdown
<p align="center">
  <img src="https://img.shields.io/badge/Platform-ESP32-blueviolet?style=for-the-badge" />
  <img src="https://img.shields.io/badge/License-MIT-brightgreen?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Framework-Arduino-00979D?style=for-the-badge&logo=arduino" />
  <img src="https://img.shields.io/badge/Language-Python-3776AB?style=for-the-badge&logo=python" />
  <img src="https://img.shields.io/badge/Function-AI%20Detection-F7DF1E?style=for-the-badge" />
</p>

<h1 align="center">老年人保健品虚假宣传识别系统</h1>
<p align="center">
  <b>✨ 便携式AI设备 | 线下场景防诈骗 | 声光震动双提醒</b>
</p>

---

<div align="center">
  <img src="https://img.shields.io/badge/Hardware-ESP32-3578E5?style=flat-square&logo=espressif" />
  <img src="https://img.shields.io/badge/Audio-I2S%20Mic-FF4500?style=flat-square" />
  <img src="https://img.shields.io/badge/AI-LLM%20Analysis-00C853?style=flat-square" />
  <img src="https://img.shields.io/badge/Alert-LED%2B%20Vibrator-FF6B6B?style=flat-square" />
</div>

---

## 📖 项目概述
本项目是一款面向老年人的便携式防诈骗辅助设备，通过「区域监测 → 音频采集 → AI 内容判别 → 声光震动提醒」的全流程，帮助老年人在线下（如保健品推销现场）快速识别虚假宣传话术，降低受骗风险。

---

## 🚀 工作流程
1. 📍 设备进入被标记的风险区域后自动启动  
2. 🎙️ 每 4 秒自动采集现场对话音频  
3. 📤 音频通过串口传输至电脑端  
4. 🧠 电脑端转写语音并用 AI 分析话术风险  
5. ⚠️ 若判定为虚假宣传 → 亮红灯 + 震动  
   安全场景 → 亮绿灯

---

## 🛠️ 硬件组成
- ESP32 开发板（核心控制单元）  
- I2S 麦克风模块（音频采集）  
- WS2812 / 外置 LED 指示灯（状态显示）  
- 振动马达（触觉提醒）  
- 便携电源模块（移动供电）

---

## 🧩 软件架构

### ▶ 设备端（ESP32）
- 框架：Arduino  
- 功能：音频采集、WAV 打包、串口发送、警报控制  
- 外设：LED 显示、振动马达  
- 依赖：`Adafruit_NeoPixel`

### ▶ 电脑端（Python）
- 功能：接收音频 → ASR 识别 → AI 判别 → 回传结果  
- 依赖：
  - 串口通信库  
  - 腾讯云 ASR  
  - 豆包大模型 API  

---

## 📦 安装与配置

### 1. 硬件接线（按引脚定义）
- `I2S_SCK_PIN` → 14  
- `I2S_WS_PIN` → 15  
- `I2S_SD_PIN` → 12  
- `WS2812_PIN` → 48  
- 外置 `LED_PIN` → 5  
- 震动马达 `PIN` → 2  

---

### 2. 设备端配置（ESP32）
1. 安装 Arduino IDE  
2. 添加 ESP32 开发板支持  
3. 安装依赖库：
```

Adafruit_NeoPixel

````
4. 将 `main.cpp` 上传至 ESP32

---

### 3. 电脑端配置（Python）
1. 安装 Python 3.6+  
2. 安装依赖包：

```bash
pip install pyserial requests tencentcloud-sdk-python
````

3. 编辑 `esp32_audio_ai.py`：

   * 修改串口端口
   * 配置腾讯云 ASR：`TENCENT_SECRET_ID`、`TENCENT_SECRET_KEY`
   * 配置豆包 LLM：`DOUBAO_API_KEY`、`DOUBAO_ENDPOINT`

---

## 📌 使用方法

1. 将 ESP32 连接到电脑（USB）
2. 启动设备端（LED 亮绿灯）
3. 运行电脑端脚本：

```bash
python esp32_audio_ai.py
```

4. 设备进入自动监测模式：

   * **安全场景**：LED 亮绿灯
   * **风险场景**：LED 亮红灯 + 马达震动（5 秒）

---

## 🔍 虚假宣传识别特征（AI 判定：满足 ≥2 条）

* 宣称「能治病 / 能替代药物」
* 夸大功效（如"延年益寿"、"神奇效果"）
* 诱导紧急消费（如"仅限今天"、"买多送多"）
* 强调「独家秘方 / 特效药」

---

## ⚠️ 注意事项

1. 本设备用于辅助判断，结果不等同医疗建议
2. ASR 服务与 LLM 可能产生使用费用
3. 若无响应，请检查：

   * 串口号
   * 线材连接
   * 麦克风接触是否松动
4. 长时间使用建议配合移动电源
