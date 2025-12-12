#include <Arduino.h>
#include <WiFi.h>
#include <driver/i2s.h>
#include <Adafruit_NeoPixel.h>

// ------------------- 【用户配置区】 -------------------
// WiFi配置 (当前版本未使用，但保留)
const char* ssid = "WIIISH惟学 Open";
const char* password = "Wiiish@2023";

// 硬件引脚定义
#define I2S_SCK_PIN 14
#define I2S_WS_PIN 15
#define I2S_SD_PIN 12
#define WS2812_PIN 48
#define NUM_WS2812 1
#define EXTERNAL_LED_PIN 5
#define VIBRATOR_PIN 2  // 马达接GPIO2

// 音频配置
#define RECORD_SECONDS 4
#define SAMPLE_RATE 16000
#define BITS_PER_SAMPLE 16
#define BYTES_PER_SAMPLE BITS_PER_SAMPLE / 8
#define SAMPLES_PER_RECORD (SAMPLE_RATE * RECORD_SECONDS)

// I2S优化配置
#define DMA_BUF_COUNT 8
#define DMA_BUF_LEN 1024

// 音频能量检测阈值
#define AUDIO_ENERGY_THRESHOLD 50

// 警报配置
#define ALERT_DURATION 5000  // 警报持续5秒
// 🌟 纯正负极马达无需PWM，注释掉强度配置
// #define VIBRATION_STRENGTH 100  

// 串口配置
#define SERIAL_BAUD 115200
// I2S读取超时（避免卡住，单位：毫秒）
#define I2S_READ_TIMEOUT 5000

// ------------------- 【全局变量】 -------------------
Adafruit_NeoPixel ws2812 = Adafruit_NeoPixel(NUM_WS2812, WS2812_PIN, NEO_GRB + NEO_KHZ800);
const i2s_port_t I2S_PORT = I2S_NUM_0;
int16_t audioBuffer[SAMPLES_PER_RECORD];
unsigned long lastSegmentTime = 0;
unsigned long alertStartTime = 0;
bool isAlertActive = false;

// ------------------- 【工具函数】 -------------------
float calculateAudioEnergy(int16_t* buffer, int samples) {
  float energy = 0.0f;
  for (int i = 0; i < samples; i++) {
    energy += (float)buffer[i] * buffer[i];
  }
  energy /= samples;
  return sqrt(energy);
}

void generateWavHeader(uint8_t* header, size_t audioSize) {
  const uint32_t fileSize = audioSize + 36;
  const uint32_t byteRate = SAMPLE_RATE * (BITS_PER_SAMPLE / 8) * 1;
  header[0] = 'R'; header[1] = 'I'; header[2] = 'F'; header[3] = 'F';
  *(uint32_t*)&header[4] = fileSize;
  header[8] = 'W'; header[9] = 'A'; header[10] = 'V'; header[11] = 'E';
  header[12] = 'f'; header[13] = 'm'; header[14] = 't'; header[15] = ' ';
  *(uint32_t*)&header[16] = 16;
  *(uint16_t*)&header[20] = 1;
  *(uint16_t*)&header[22] = 1;
  *(uint32_t*)&header[24] = SAMPLE_RATE;
  *(uint32_t*)&header[28] = byteRate;
  *(uint16_t*)&header[32] = BITS_PER_SAMPLE / 8;
  *(uint16_t*)&header[34] = BITS_PER_SAMPLE;
  header[36] = 'd'; header[37] = 'a'; header[38] = 't'; header[39] = 'a';
  *(uint32_t*)&header[40] = audioSize;
}

void receiveAiResult() {
  if (Serial.available() > 0) {
    String result = Serial.readStringUntil('\n');
    result.trim();
    if (result == "ALERT") {
      if (!isAlertActive) { // 避免重复触发导致计时重置
        Serial.println("🚨 电脑端AI判定诈骗！触发警报！");
        alertStartTime = millis();
        isAlertActive = true;
        ws2812.setPixelColor(0, 255, 0, 0);
        ws2812.show();
      } else {
        Serial.println("⚠️  已处于警报状态，忽略重复ALERT指令");
      }
    } else if (result == "NORMAL") {
      Serial.println("✅ 电脑端AI判定正常。");
      if (!isAlertActive) {
        ws2812.setPixelColor(0, 0, 255, 0);
        ws2812.show();
      }
    }
  }
}

// 警报控制（纯正负极马达适配：纯通断脉冲震动）
void controlAlert() {
  if (isAlertActive) {
    unsigned long alertElapsed = millis() - alertStartTime;
    if (alertElapsed < ALERT_DURATION) {
      // LED闪烁 + 马达脉冲震动（200ms周期）
      digitalWrite(EXTERNAL_LED_PIN, (millis() % 200) < 100);
      digitalWrite(VIBRATOR_PIN, (millis() % 200) < 100);
    } else {
      // 强制关闭所有输出，重置状态
      digitalWrite(EXTERNAL_LED_PIN, LOW);
      digitalWrite(VIBRATOR_PIN, LOW);
      isAlertActive = false;
      ws2812.setPixelColor(0, 0, 255, 0);
      ws2812.show();
      Serial.println("✅ 警报结束，马达已断电");
    }
  } else {
    // 非警报状态确保输出关闭
    digitalWrite(EXTERNAL_LED_PIN, LOW);
    digitalWrite(VIBRATOR_PIN, LOW);
  }
}

// ------------------- 【硬件初始化】 -------------------
void initWiFi() {
  Serial.printf("\n🔵 连接WiFi: %s...", ssid);
  WiFi.begin(ssid, password);
  int timeout = 0;
  while (WiFi.status() != WL_CONNECTED && timeout < 30) { delay(500); Serial.print("."); timeout++; }
  if (WiFi.status() == WL_CONNECTED) Serial.printf("\n✅ WiFi IP: %s\n", WiFi.localIP().toString().c_str());
  else Serial.println("\n❌ WiFi连接失败（当前版本使用串口，不影响）");
}

void initI2SMicrophone() {
  Serial.println("\n🔵 初始化I2S麦克风...");
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = (i2s_bits_per_sample_t)BITS_PER_SAMPLE,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL3,
    .dma_buf_count = DMA_BUF_COUNT,
    .dma_buf_len = DMA_BUF_LEN,
    .use_apll = true,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK_PIN,
    .ws_io_num = I2S_WS_PIN,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD_PIN
  };
  esp_err_t err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  if (err != ESP_OK) { Serial.printf("❌ I2S驱动安装失败: %s\n", esp_err_to_name(err)); while (1); }
  err = i2s_set_pin(I2S_PORT, &pin_config);
  if (err != ESP_OK) { Serial.printf("❌ I2S引脚配置失败: %s\n", esp_err_to_name(err)); while (1); }
  i2s_start(I2S_PORT);
  Serial.println("✅ I2S麦克风初始化完成！");
}

void initWS2812() {
  ws2812.begin();
  ws2812.setBrightness(50);
  ws2812.setPixelColor(0, 0, 255, 0);
  ws2812.show();
  Serial.println("✅ WS2812 LED 初始化完成，当前为绿灯。");
}

// ------------------- 【核心功能】 -------------------
// 录音并发送WAV（修改I2S读取逻辑，避免卡住）
void recordAndSendWav() {
  Serial.printf("\n🎤 开始录音 %d 秒...\n", RECORD_SECONDS);
  
  // 1. 清空I2S残留数据（解决二次录音卡住）
  size_t flushBytes = 0;
  i2s_read(I2S_PORT, NULL, 0, &flushBytes, 100);
  if (flushBytes > 0) Serial.printf("ℹ️ 清空I2S残留数据：%d 字节\n", flushBytes);

  size_t bytesRead = 0;
  // 2. I2S读取加超时（避免无限阻塞）
  esp_err_t err = i2s_read(I2S_PORT, audioBuffer, sizeof(audioBuffer), &bytesRead, pdMS_TO_TICKS(I2S_READ_TIMEOUT));

  if (err != ESP_OK || bytesRead != sizeof(audioBuffer)) {
    Serial.printf("❌ 录音失败: %s, 实际读取 %d 字节 / 预期 %d 字节\n", esp_err_to_name(err), bytesRead, sizeof(audioBuffer));
    lastSegmentTime = millis();  // 重置时间戳，避免循环卡住
    return;
  }
  
  Serial.println("✅ 录音完成！");

  float energy = calculateAudioEnergy(audioBuffer, SAMPLES_PER_RECORD);
  Serial.printf("🔊 录音能量: %.2f (阈值: %d)\n", energy, AUDIO_ENERGY_THRESHOLD);
  if (energy < AUDIO_ENERGY_THRESHOLD) {
    Serial.println("⚠️  音频能量过低，已丢弃。");
    return;
  }

  const size_t wavHeaderSize = 44;
  const size_t totalWavSize = wavHeaderSize + sizeof(audioBuffer);
  uint8_t* wavData = (uint8_t*)malloc(totalWavSize);
  if (!wavData) {
    Serial.println("❌ 内存分配失败");
    return;
  }
  generateWavHeader(wavData, sizeof(audioBuffer));
  memcpy(wavData + wavHeaderSize, audioBuffer, sizeof(audioBuffer));

  Serial.println("📤 发送WAV数据...");
  Serial.write("WAV_START", 9);
  Serial.write((const uint8_t*)&totalWavSize, sizeof(totalWavSize));
  Serial.write(wavData, totalWavSize);
  Serial.write("WAV_END", 7);
  Serial.flush();
  free(wavData);
  
  Serial.printf("✅ WAV发送完毕！总大小: %d 字节\n", totalWavSize);
}

// ------------------- 【主程序】 -------------------
void setup() {
  Serial.begin(SERIAL_BAUD);
  while (!Serial) { delay(10); }
  Serial.println("==================================================");
  Serial.println("🔵 ESP32 语音采集与警报系统 (修复版)");
  Serial.println("==================================================");

  // 初始化引脚
  pinMode(EXTERNAL_LED_PIN, OUTPUT);
  pinMode(VIBRATOR_PIN, OUTPUT);  // 马达引脚设为输出
  digitalWrite(EXTERNAL_LED_PIN, LOW);
  digitalWrite(VIBRATOR_PIN, LOW);

  // 初始化外设
  initWS2812();
  initWiFi();
  initI2SMicrophone();

  Serial.println("\n🔵 系统就绪！每4秒录音一次");
  lastSegmentTime = millis();
}

void loop() {
  receiveAiResult();
  controlAlert();
  
  if (millis() - lastSegmentTime >= RECORD_SECONDS * 1000) {
    recordAndSendWav();
    lastSegmentTime = millis();
    Serial.printf("\n⏳ 等待 %d 秒后下一次录音...\n", RECORD_SECONDS);
  }
  delay(100);
}