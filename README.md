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
  <img src="https://img.shields.io/badge/Alert-LED%2B Vibrator-FF6B6B?style=flat-square" />
</div>

---

## 📖 项目概述
本项目是一款面向老年人的便携式防诈骗辅助设备，通过「区域监测→音频采集→AI内容判别→声光震动提醒」的全流程，帮助老年人在线下（如保健品推销现场）快速识别虚假宣传话术，降低受骗风险。


## 🚀 工作流程
1. 📍 设备进入被标记的风险区域后自动启动
2. 🎙️ 每4秒自动采集现场对话音频
3. 📤 音频数据通过串口传输至电脑端
4. 🧠 电脑端将音频转文字后，通过AI分析内容风险
5. ⚠️ 若判定为虚假宣传：设备亮红灯+震动；安全场景：亮绿灯


## 🛠️ 硬件组成
- ESP32开发板（核心控制单元）
- I2S麦克风模块（音频采集）
- WS2812/外置LED灯（状态显示）
- 震动马达（触觉提醒）
- 电源模块（便携供电）


## 🧩 软件架构
### 设备端（ESP32）
- 基于Arduino框架开发
- 功能：音频采集、串口通信、灯光/震动控制
- 依赖库：Adafruit_NeoPixel


### 电脑端（Python）
- 功能：音频接收、语音转文字（ASR）、AI风险判别、结果回传
- 依赖工具：串口通信库、云ASR服务、大语言模型API


## 📦 安装与配置
### 1. 硬件接线（按引脚定义）
- I2S_SCK_PIN → 14
- I2S_WS_PIN → 15
- I2S_SD_PIN → 12
- WS2812_PIN → 48
- 外置 LED_PIN → 5
- 震动马达_PIN → 2


### 2. 设备端配置
1. 安装Arduino IDE，添加ESP32开发板支持
2. 安装依赖库：`Adafruit_NeoPixel`
3. 上传`main.cpp`代码至ESP32


### 3. 电脑端配置
1. 安装Python 3.6+
2. 安装依赖包：
```bash
pip install serial requests tencentcloud-sdk-python

3.配置esp32_audio_ai.py中的密钥：
- 串口端口：将ser = serial.Serial('COM3', 115200)中的COM3改为实际端口（Windows 为 COM 开头，Mac/Linux 为/dev/ttyUSB0等）
- 云 ASR 密钥：填写腾讯云 TENCENT_SECRET_ID、TENCENT_SECRET_KEY
- 大语言模型密钥：填写 DOUBAO_API_KEY、DOUBAO_ENDPOINT


## 📌 使用方法
1. 连接 ESP32 与电脑（USB）
2. 启动 ESP32 设备
3. 运行电脑端脚本：
```bash
python esp32_audio_ai.py

4. 设备自动进入监测状态：
- 安全场景：LED 亮绿灯，无震动
- 风险场景：LED 亮红灯，同时震动马达启动（持续 5 秒）

## 🔍 虚假宣传识别特征
AI 将判定包含以下2 项及以上内容的对话为风险话术：
- 宣称「根治疾病 / 替代药物治疗」
- 夸大功效（如「延年益寿 / 包治百病 / 一吃就好」）
- 诱导紧急消费（如「限时折扣 / 今日不买明天涨价 / 买多送多」）
- 强调「独家配方 / 特效秘药 / 内部渠道」

## ⚠️ 注意事项
1. 本设备为辅助提醒工具，最终决策请结合实际情况判断
2. 云 ASR 服务、大语言模型 API 可能产生费用，请参考对应平台的定价规则
3. 若设备无响应，检查串口端口是否正确、硬件接线是否松动
4. 长时间使用时，建议配备便携充电宝为 ESP32 供电
