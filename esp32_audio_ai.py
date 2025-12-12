import serial
import time
import requests
import json
import base64
import uuid
# 新增导入
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.common import credential
from tencentcloud.asr.v20190614 import asr_client, models

# ------------------- 【用户配置区】 -------------------
SERIAL_PORT = "COM6"
SERIAL_BAUD = 115200
#这里使用的是腾讯云的语音识别服务，但是如果追求更好的效果可以使用豆包的分角色语音识别，效果应该会更好
TENCENT_SECRET_ID = "your tecent_secret_id"
TENCENT_SECRET_KEY = "your tecent_secret_key"
TENCENT_REGION = "ap-shanghai"

# 豆包配置
DOUBAO_API_URL = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"#看调用文档
#同理将这些换成你自己的内容
DOUBAO_API_KEY = "your Doubao api key"     #API KEY管理
DOUBAO_ENDPOINT = "your project endpoint"  #在线推理-项目id

# ------------------- 【工具函数】 -------------------
def call_doubao_judge(text):
    if not text:
        return "NORMAL"
    headers = {
        "Authorization": f"Bearer {DOUBAO_API_KEY}",
        "Content-Type": "application/json"
    }
    prompt = f"""你是专业反诈分析师，分析对话是否存在针对老年人的保健品诈骗。
特征：
1. 宣称能治疗/根治疾病；
2. 夸大功效（如"神奇效果""延年益寿"）；
3. 诱导购买（如"仅限今天""买多送多"）；
4. 强调"独家配方""特效药"。

规则：
- 符合任意两条 → 回复"ALERT"；
- 无上述特征 → 回复"NORMAL"；
- 仅返回结果，不要额外内容。

对话：
"{text}"
"""
    payload = {
        "model": DOUBAO_ENDPOINT,
        "stream": False,
        "messages": [{"role": "user", "content": prompt}]
    }
    try:
        response = requests.post(DOUBAO_API_URL, headers=headers, data=json.dumps(payload), timeout=15)
        response.raise_for_status()
        result = response.json()["choices"][0]["message"]["content"].strip()
        print(f"✅ 豆包AI判断结果：{result}")
        return result
    except Exception as e:
        print(f"❌ 豆包AI调用失败：{str(e)}")
        if 'response' in locals():
            print(f"📥 豆包错误响应: {response.text}")
        return "NORMAL"

def receive_wav_from_esp32(ser):
    print("\n🔍 等待ESP32发送WAV...")
    buffer = b""
    while b"WAV_START" not in buffer:
        if ser.in_waiting > 0:
            buffer += ser.read(ser.in_waiting)
        time.sleep(0.01)
    print("📥 检测到 WAV_START 标记。")
    # 从缓冲区中提取WAV数据（去掉WAV_START标记）
    wav_data_start_index = buffer.index(b"WAV_START") + len(b"WAV_START")
    buffer = buffer[wav_data_start_index:]

    # 读取4字节的WAV大小
    while len(buffer) < 4:
        if ser.in_waiting > 0:
            buffer += ser.read(4 - len(buffer))
        time.sleep(0.01)
    wav_size_bytes = buffer[:4]
    wav_size = int.from_bytes(wav_size_bytes, byteorder="little")
    print(f"📊 预期接收WAV数据大小: {wav_size} 字节。")
    buffer = buffer[4:]

    # 读取WAV数据主体
    received_data = b""
    # 已在buffer中的数据
    received_data += buffer
    remaining_size = wav_size - len(received_data)
    
    while remaining_size > 0:
        chunk = ser.read(min(remaining_size, 1024))
        if not chunk:
            time.sleep(0.01)
            continue
        received_data += chunk
        remaining_size -= len(chunk)

    print(f"✅ WAV数据接收完成！实际大小: {len(received_data)} 字节。")

    # ==================== 保存接收的音频到本地 ====================
    try:
        with open("received_audio.wav", "wb") as f:
            f.write(received_data)
        print("✅ 已将接收的音频数据保存为 'received_audio.wav'")
    except Exception as e:
        print(f"❌ 保存音频文件失败: {e}")
    # ==================================================================

    return received_data

# ------------------- 【腾讯云ASR识别函数（方案一：快速修复）】 -------------------
def recognize_speech_with_tencent(wav_data):
    """
    使用腾讯云ASR服务识别音频中的文本。
    方案一快速修复：直接处理返回的文本结果，绕过JSON解析。
    """
    print("\n🟡 正在调用腾讯云ASR服务...")
    try:
        cred = credential.Credential(TENCENT_SECRET_ID, TENCENT_SECRET_KEY)
        httpProfile = HttpProfile()
        httpProfile.endpoint = "asr.tencentcloudapi.com"
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        client = asr_client.AsrClient(cred, TENCENT_REGION, clientProfile)

        audio_base64 = base64.b64encode(wav_data).decode("utf-8")
        req = models.CreateRecTaskRequest()
        # 注意：即使我们设置了ResTextFormat=2，返回的依然是文本，所以这里的设置暂时无关紧要
        params = {
            "EngineModelType": "16k_zh",
            "ChannelNum": 1,
            "ResTextFormat": 1, # 索性改为1，明确期望纯文本
            "SourceType": 1,
            "Data": audio_base64,
            # 由于返回的是纯文本，说话人分离信息会丢失，所以这两个参数暂时无效
            # "SpeakerDiarization": 1,
            # "SpeakerNumber": 2
        }
        req.from_json_string(json.dumps(params))
        
        # --- 创建任务请求 ---
        try:
            resp = client.CreateRecTask(req)
            resp_dict = json.loads(resp.to_json_string())
            task_id = resp_dict['Data']['TaskId']
            print(f"✅ 腾讯云ASR任务创建成功，TaskId: {task_id}")
        except Exception as e:
            print(f"❌ 创建ASR任务时发生异常: {e}")
            return ""

        # --- 查询任务状态 ---
        max_retries = 30
        for i in range(max_retries):
            time.sleep(1.5)
            try:
                query_req = models.DescribeTaskStatusRequest()
                query_req.from_json_string(json.dumps({"TaskId": task_id}))
                
                query_resp = client.DescribeTaskStatus(query_req)
                raw_response = query_resp.to_json_string()
                
                if not raw_response:
                    print("⚠️ 腾讯云返回空响应，将重试...")
                    continue

                result_dict = json.loads(raw_response)

            except json.JSONDecodeError as e:
                print(f"❌ 查询响应JSON解析失败: {e}")
                return ""
            except Exception as e:
                print(f"❌ 查询ASR任务状态时发生异常: {e}")
                continue

            if 'Error' in result_dict:
                print(f"❌ 腾讯云API返回错误: {result_dict['Error']['Code']} - {result_dict['Error']['Message']}")
                return ""

            status = result_dict['Data']['StatusStr']
            
            if status == 'success':
                # ==================== 核心修改：直接获取文本结果 ====================
                recognized_text = result_dict['Data'].get('Result', '').strip()
                if not recognized_text:
                    print("⚠️  腾讯云返回的识别结果为空！")
                    return ""
                
                print("✅ 腾讯云ASR识别成功（纯文本格式）：")
                print(recognized_text)
                return recognized_text
                # ==================================================================
                
            elif status == 'failed':
                error_msg = result_dict['Data'].get('ErrorMsg', '未知错误')
                print(f"❌ 腾讯云ASR任务失败: {error_msg}")
                return ""

        print(f"❌ 腾讯云ASR任务查询超时")
        return ""
        
    except Exception as e:
        print(f"❌ 腾讯云ASR调用过程中发生异常: {str(e)}")
        return ""

# ------------------- 【主逻辑】 -------------------
def main():
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        time.sleep(2)
        print(f"✅ 串口已打开：{SERIAL_PORT}（{SERIAL_BAUD}波特率）")
        
        while True:
            wav_data = receive_wav_from_esp32(ser)
            if not wav_data:
                continue
            
            asr_text = recognize_speech_with_tencent(wav_data)
            if not asr_text:
                print("❌ ASR识别失败或结果为空，向ESP32发送'NORMAL'")
                ser.write(b"NORMAL\n")
                continue
            
            ai_result = call_doubao_judge(asr_text)
            ser.write(f"{ai_result}\n".encode("utf-8"))
            print(f"✅ 最终结果已发送给ESP32：{ai_result}\n" + "-"*50)
            
    except KeyboardInterrupt:
        print("\n🔌 用户中断，正在关闭串口...")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("✅ 串口已关闭")

if __name__ == "__main__":
    main()