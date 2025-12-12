import requests
import json
import base64
import os
import time
from PIL import Image
import io
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ====================== 1. 全局配置（仅优化模型版本，其他不变） ======================
DOUBAO_API_URL = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
#if you use DOUBAO, you can check their official documentation to know how to get your api key and endpoint
DOUBAO_API_KEY = "your DOUBAO api key" #Put your own key, if you want to run this program.
DOUBAO_ENDPOINT = "your endpoint" #Ditto.
DOUBAO_SIZE = "2K"
DOUBAO_OPTIMIZE_DIR = "./doubao_optimized_images"
# I use TripoAI to gennerate mutiview photo and 3D model from the sketch. To get those parameters, please check their official doc too.
TRIPO_API_KEY = "your TripoAI api key"
TRIPO_API_BASE_URL = "https://api.tripo3d.ai/v2/openapi"
TRIPO_UPLOAD_URL = f"{TRIPO_API_BASE_URL}/upload/sts"
TRIPO_GENERATE_URL = f"{TRIPO_API_BASE_URL}/task"
INPUT_PHOTO_DIR = "./input_photos"
TRIPO_OUTPUT_DIR = "./tripo_three_views"
TIMEOUT = 180  # 延长单次请求超时（应对网络波动）
RETRY_TIMES = 1

# 超时配置（保持你的20次×20秒=400秒，足够覆盖生成）
MAX_POLL_TIMES = 20
POLL_INTERVAL = 20


# ====================== 2. 基础工具函数（完全保留） ======================
def check_and_create_dir(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)
        print(f"Directory created: {dir_path}")
    else:
        print(f"Directory already exists: {dir_path}")

def create_retry_session():
    session = requests.Session()
    retry = Retry(
        total=RETRY_TIMES,
        backoff_factor=2,
        allowed_methods=["POST", "GET"],
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.proxies = {"http": None, "https": None}
    return session

def normalize_path(path):
    return path.replace("\\", "/")


# ====================== 3. 选择已有豆包图（完全保留） ======================
def select_existing_doubao_image():
    check_and_create_dir(DOUBAO_OPTIMIZE_DIR)
    supported_formats = ('.jpg', '.jpeg', '.png', '.webp')
    existing_images = [f for f in os.listdir(DOUBAO_OPTIMIZE_DIR) if f.lower().endswith(supported_formats)]
    
    if not existing_images:
        print(f"ℹ️ No existing Doubao optimized images in {DOUBAO_OPTIMIZE_DIR}")
        return None
    
    print(f"\n===== Found {len(existing_images)} Existing Doubao Optimized Images =====")
    for idx, file in enumerate(existing_images):
        file_path = os.path.join(DOUBAO_OPTIMIZE_DIR, file)
        file_path = normalize_path(file_path)
        file_size = round(os.path.getsize(file_path) / 1024 / 1024, 2)
        print(f"{idx+1}. {file} (Size: {file_size}MB)")
    
    while True:
        try:
            choice = input(f"\nPlease choose:\n1. Use existing image (no Doubao cost)\n2. Regenerate Doubao image (cost 1 generation)\nEnter number (1/2): ")
            if choice == "1":
                img_choice = int(input(f"\nEnter the number of the image to use (1-{len(existing_images)}): ")) - 1
                if 0 <= img_choice < len(existing_images):
                    selected_path = os.path.join(DOUBAO_OPTIMIZE_DIR, existing_images[img_choice])
                    selected_path = normalize_path(selected_path)
                    print(f"✅ Selected existing Doubao image: {selected_path}")
                    return selected_path
                else:
                    print(f"❌ Invalid number (enter 1-{len(existing_images)})")
            elif choice == "2":
                print("ℹ️ Selected to regenerate Doubao image (will cost 1 generation)")
                return "regenerate"
            else:
                print("❌ Please enter 1 or 2")
        except ValueError:
            print("❌ Please enter a valid number")

def select_user_edited_image():
    check_and_create_dir(INPUT_PHOTO_DIR)
    supported_formats = ('.jpg', '.jpeg', '.png', '.webp')
    image_files = [f for f in os.listdir(INPUT_PHOTO_DIR) if f.lower().endswith(supported_formats)]
    
    if not image_files:
        print(f"⚠️ No valid images found in {INPUT_PHOTO_DIR} (supported formats: {supported_formats})")
        return None
    
    print(f"\n===== Available Hand-Edited Furniture Images =====")
    for idx, file in enumerate(image_files):
        print(f"{idx+1}. {file}")
    
    while True:
        try:
            choice = int(input("\nEnter image number: ")) - 1
            if 0 <= choice < len(image_files):
                selected_path = os.path.join(INPUT_PHOTO_DIR, image_files[choice])
                selected_path = normalize_path(selected_path)  # 归一化路径
                print(f"✅ Selected hand-edited image: {selected_path}")
                return selected_path
            else:
                print(f"❌ Invalid number (enter 1-{len(image_files)})")
        except ValueError:
            print("❌ Please enter a valid number")

# ====================== 4. 豆包生成优化图（完全保留） ======================
def optimize_image_by_doubao(user_edited_img_path):
    check_and_create_dir(DOUBAO_OPTIMIZE_DIR)
    user_edited_img_path = normalize_path(user_edited_img_path)
    
    try:
        with Image.open(user_edited_img_path) as img:
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail((6000, 6000))
            img_format = img.format.lower() if img.format else "jpeg"
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format=img_format, quality=85)
            img_base64 = f"data:image/{img_format};base64,{base64.b64encode(img_byte_arr.getvalue()).decode('utf-8')}"
    except Exception as e:
        print(f"❌ Doubao optimization: Failed to convert image to Base64: {str(e)}")
        return None

    prompt = f"""
    Optimize the user's hand-edited furniture image for 3D modeling reference:
    1. Keep the positional relationship between the original furniture and hand-drawn parts (e.g., handles, brackets);
    2. Refine hand-drawn lines/color blocks into clear, continuous solid outlines (no blur or breaks);
    3. Unify image tone, remove noise, and use solid background (e.g., white);
    4. Resolution {DOUBAO_SIZE}, no watermark, clear details (easy for TripoAI to generate three views);
    5. Do not change the core shape of the furniture, only optimize clarity and lines.
    """
    prompt = prompt.strip()[:300]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DOUBAO_API_KEY}"
    }
    data = {
        "model": DOUBAO_ENDPOINT,
        "prompt": prompt,
        "image": img_base64,
        "size": DOUBAO_SIZE,
        "watermark": False,
        "num_images": 1,
        "response_format": "url"
    }

    session = create_retry_session()
    try:
        print("\n⏳ Doubao is optimizing the hand-edited image (cost 1 generation)...")
        response = session.post(DOUBAO_API_URL, headers=headers, data=json.dumps(data), timeout=TIMEOUT)
        response.raise_for_status()
        response_data = response.json()

        if "data" in response_data and len(response_data["data"]) == 1:
            optimize_img_url = response_data["data"][0]["url"]
            timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            original_filename = os.path.splitext(os.path.basename(user_edited_img_path))[0]
            optimize_img_filename = f"optimized_furniture_{original_filename}_{timestamp}.jpg"
            optimize_img_path = os.path.join(DOUBAO_OPTIMIZE_DIR, optimize_img_filename)
            optimize_img_path = normalize_path(optimize_img_path)
            
            img_response = session.get(optimize_img_url, timeout=30)
            img_response.raise_for_status()
            with open(optimize_img_path, "wb") as f:
                f.write(img_response.content)
            print(f"✅ Doubao optimized image saved (cost 1 generation): {optimize_img_path}")
            return optimize_img_path
        else:
            print(f"❌ Doubao optimization failed: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
            return None
    except Exception as e:
        print(f"❌ Doubao optimization request failed: {str(e)}")
        return None


# ====================== 5. TripoAI上传函数（完全保留） ======================
def upload_to_tripo(optimize_img_path):
    headers = {
        "Authorization": f"Bearer {TRIPO_API_KEY}"
    }

    optimize_img_path = normalize_path(optimize_img_path)
    pure_filename = os.path.basename(optimize_img_path)
    
    if pure_filename.lower().endswith(('.jpg', '.jpeg')):
        mime_type = "image/jpeg"
    elif pure_filename.lower().endswith('.png'):
        mime_type = "image/png"
    elif pure_filename.lower().endswith('.webp'):
        mime_type = "image/webp"
    else:
        mime_type = "image/jpeg"

    try:
        with open(optimize_img_path, "rb") as f:
            files = {
                "file": (
                    pure_filename.encode('utf-8').decode('latin-1'),
                    f,
                    mime_type
                )
            }

            session = create_retry_session()
            print(f"\n⏳ Uploading Doubao optimized image to TripoAI (Filename: {pure_filename})...")
            response = session.post(TRIPO_UPLOAD_URL, headers=headers, files=files, timeout=TIMEOUT)
            response.raise_for_status()
            response_data = response.json()

        if response_data["code"] == 0 and "image_token" in response_data["data"]:
            image_token = response_data["data"]["image_token"]
            print(f"✅ TripoAI upload success, image_token: {image_token}")
            return image_token
        else:
            print(f"❌ TripoAI upload failed: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
            return None
    except Exception as e:
        print(f"❌ TripoAI upload error: {str(e)}")
        if "codec can't encode characters" in str(e):
            print("💡 Windows系统专属解决方案：")
            print("1. 确保文件夹路径无中文（当前路径：{DOUBAO_OPTIMIZE_DIR}）")
            print("2. 右键点击图片→属性→详细信息→删除所有中文元数据")
        return None

# 识别4张视图并上传（适配Multiview to Model）
def upload_4_views_for_multiview():
    """
    手动选择前/左/后/右视图文件并上传，按[前→左→后→右]构造Multiview接口files列表
    前/左视图为必填，后/右视图可选
    :return: files列表（符合接口要求）/ None（失败）
    """
    # 定义视图配置：(视图角色, 中文名称, 是否必填)
    view_configs = [
        ("front", "前视图", True),   # 接口第1位：必填
        ("left", "左视图", True),    # 接口第2位：必填
        ("back", "后视图", False),   # 接口第3位：可选
        ("right", "右视图", False)   # 接口第4位：可选
    ]
    files_list = []  # 最终返回的files列表

    # 逐个手动选择并上传视图
    for view_role, view_cn, is_required in view_configs:
        while True:
            # 提示用户输入文件路径
            file_path = input(f"\n请输入{view_cn}的文件路径（支持jpg/png，必填：{is_required}）：").strip()
            
            # 处理可选视图的空输入
            if not file_path and not is_required:
                print(f"⚠️ 未选择{view_cn}，将留空")
                files_list.append({})
                break
            
            # 验证必填视图输入
            if not file_path and is_required:
                print(f"❌ {view_cn}为必填项，不能为空！")
                continue
            
            # 验证文件存在且格式合法
            if not os.path.exists(file_path):
                print(f"❌ 文件不存在：{file_path}，请重新输入")
                continue
            if not file_path.lower().endswith(('.jpg', '.png', '.jpeg')):
                print(f"❌ 仅支持jpg/png格式，当前文件：{file_path}，请重新输入")
                continue
            
            # 上传文件到TripoAI，获取file_token
            print(f"⏳ 正在上传{view_cn}...")
            file_token = upload_to_tripo(file_path)
            if not file_token:
                print(f"❌ {view_cn}上传失败，请重新选择文件")
                continue
            
            # 构造接口要求的格式并添加到列表
            files_list.append({"type": "jpg", "file_token": file_token})
            print(f"✅ {view_cn}上传成功，token：{file_token[:10]}...")
            break

    # 验证必填项是否上传成功
    if not files_list[0].get("file_token"):  # 前视图必填
        print("\n❌ 前视图上传失败，无法继续生成3D模型")
        return None
    if not files_list[1].get("file_token"):  # 左视图必填（至少2张有效图）
        print("\n❌ 左视图上传失败，Multiview接口至少需要前+左2张视图")
        return None

    print(f"\n✅ 已构造Multiview接口files列表（顺序：前→左→后→右）")
    return files_list

# ====================== 6. 核心函数：分视角生成拟真图（替换原有3图生成函数） ======================
def generate_single_view_by_tripo(image_token, view_type, user_text):
    """
    单次生成1个视角的拟真图（新增Back/Right视角，适配4视图需求）
    视角定义：Front=0°（正面）、Back=180°（背面）、Left=90°（左侧）、Right=270°（右侧）
    """
    check_and_create_dir(TRIPO_OUTPUT_DIR)
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TRIPO_API_KEY}"
    }

    # 【核心修改：新增Back/Right视角Prompt，明确透视和内容】
    view_prompts = {
        "Front": f"""
Generate a photorealistic front-view rendering of the furniture (reference: Doubao-optimized hand-drawn image):
- Perspective: Direct horizontal front projection (0° angle), show full front shape + hand-drawn parts (e.g., handles);
- Style: Photorealistic (NOT line art), {user_text}, soft shadow on white background;
- Resolution: 2K (2048x2048), no watermark, consistent shape with reference.
        """,
        "Back": f"""
Generate a photorealistic back-view rendering of the furniture (reference: Doubao-optimized hand-drawn image):
- Perspective: Direct horizontal back projection (180° angle), show full back shape + hand-drawn parts' back side;
- Style: Photorealistic (NOT line art), {user_text}, soft shadow on white background;
- Resolution: 2K (2048x2048), no watermark, shape matches front view (symmetry if applicable).
        """,
        "Left": f"""
Generate a photorealistic left-view rendering of the furniture (reference: Doubao-optimized hand-drawn image):
- Perspective: Direct horizontal left projection (90° angle), show side thickness + hand-drawn parts' side connection;
- Style: Photorealistic (NOT line art), {user_text}, soft shadow on white background;
- Resolution: 2K (2048x2048), no watermark, width/height matches front view.
        """,
        "Right": f"""
Generate a photorealistic right-view rendering of the furniture (reference: Doubao-optimized hand-drawn image):
- Perspective: Direct horizontal right projection (270° angle), show side structure + hand-drawn parts' right side;
- Style: Photorealistic (NOT line art), {user_text}, soft shadow on white background;
- Resolution: 2K (2048x2048), no watermark, shape matches left view (symmetry if applicable).
        """
    }

    # 【原有代码保留】请求数据构造、任务提交、轮询逻辑完全不变
    data = {
        "type": "generate_image",
        "model_version": "flux.1_kontext_pro",
        "prompt": view_prompts[view_type].strip().replace("\n", " ")[:1024],
        "file": {"file_token": image_token},
        "num_images": 1,  # 单次仅生成1个视角
        "response_format": "url"
    }

    session = create_retry_session()
    try:
        print(f"\n⏳ Generating {view_type} View (photorealistic, not line art)...")
        response = session.post(TRIPO_GENERATE_URL, headers=headers, data=json.dumps(data), timeout=TIMEOUT)

        # 捕获HTTP错误（400/500等）
        if response.status_code >= 400:
            error_data = response.json() if response.text else {}
            print(f"❌ Error: {error_data.get('message', 'Unknown error')}")
            return None

        response_data = response.json()
        if response_data["code"] == 0 and "task_id" in response_data["data"]:
            task_id = response_data["data"]["task_id"]
            status_url = f"{TRIPO_API_BASE_URL}/task/{task_id}"
            print(f"✅ {view_type} View Task submitted: TaskID={task_id}")

            # 轮询等待生成（确保前一个视角完成）
            for _ in range(MAX_POLL_TIMES):
                remaining = MAX_POLL_TIMES - _
                print(f"⏳ Waiting for {view_type} View (remaining {remaining} retries)...")
                
                status_res = session.get(status_url, headers=headers, timeout=TIMEOUT)
                if status_res.status_code >= 400:
                    time.sleep(POLL_INTERVAL)
                    continue

                status_data = status_res.json()
                if status_data["code"] != 0:
                    time.sleep(POLL_INTERVAL)
                    continue

                # 兼容大小写状态（success/SUCCESS）
                task_status = status_data["data"]["status"].upper()
                if task_status == "SUCCESS":
                    output = status_data["data"]["output"]
                    # 提取图片URL（支持两种返回格式）
                    if "generated_image" in output:
                        return output["generated_image"]
                    elif "images" in output and len(output["images"]) > 0:
                        return output["images"][0]["url"]
                elif task_status in ["FAILED", "REJECTED"]:
                    print(f"❌ {view_type} View Task failed: {status_data['data'].get('error_msg')}")
                    return None

                time.sleep(POLL_INTERVAL)

            print(f"❌ {view_type} View Task timed out")
            return None
        else:
            print(f"❌ {view_type} View Task submit failed")
            return None
    except Exception as e:
        print(f"❌ {view_type} View Generation error: {str(e)}")
        return None
    
# 多图生成3D模型（Multiview to Model） ======================
# ====================== 辅助函数：GLB转STL（基于文档Conversion接口） ======================
# ====================== 辅助函数：GLB转STL（适配实际回传格式） ======================
def convert_glb_to_stl(original_task_id):
    """
    修复：处理带查询参数的STL URL，优先提取output.model（用户确认有效）
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TRIPO_API_KEY}"
    }
    convert_data = {
        "type": "convert_model",
        "format": "STL",
        "original_model_task_id": original_task_id,
        "quad": False,
        "bake": True,
        "face_limit": 10000
    }

    session = create_retry_session()
    try:
        print(f"\n===== 调用convert_model接口（GLB→STL） =====")
        response = session.post(TRIPO_GENERATE_URL, headers=headers, data=json.dumps(convert_data), timeout=TIMEOUT)

        if response.status_code >= 400:
            error_data = response.json() if response.text else {}
            print(f"❌ 转换接口错误：{error_data.get('message')}")
            return None

        response_data = response.json()
        if response_data["code"] != 0 or "task_id" not in response_data["data"]:
            print(f"❌ 转换任务提交失败：{json.dumps(response_data, indent=2)}")
            return None

        convert_task_id = response_data["data"]["task_id"]
        status_url = f"{TRIPO_API_BASE_URL}/task/{convert_task_id}"
        print(f"✅ 转换任务提交成功：Task ID={convert_task_id}")

        # 轮询任务状态
        for _ in range(MAX_POLL_TIMES):
            remaining = MAX_POLL_TIMES - _
            print(f"⏳ 等待转换（剩余{remaining}次重试）...")
            
            status_res = session.get(status_url, headers=headers, timeout=TIMEOUT)
            if status_res.status_code >= 400:
                time.sleep(POLL_INTERVAL)
                continue

            status_data = status_res.json()
            if status_data["code"] != 0:
                print(f"⚠️ 轮询响应错误：{status_data.get('message')}")
                time.sleep(POLL_INTERVAL)
                continue

            task_status = status_data["data"]["status"].upper()
            if task_status == "SUCCESS":
                task_data = status_data["data"]
                stl_url = None

                # ---------------------- 核心修复：处理output.model（带查询参数的URL） ----------------------
                if "output" in task_data and "model" in task_data["output"]:
                    output_model_url = task_data["output"]["model"]
                    # 1. 先去掉URL后的查询参数（?及后面的内容）
                    url_without_query = output_model_url.split("?")[0]  # 关键：分割查询参数
                    # 2. 验证：是字符串 + 以https开头 + 分割后的路径以.stl结尾
                    if (isinstance(output_model_url, str)
                        and output_model_url.startswith("https://")
                        and url_without_query.lower().endswith(".stl")):  # 用分割后的URL判断后缀
                        stl_url = output_model_url  # 保留完整URL（含查询参数，服务器需要）
                        print(f"✅ 从output.model提取到有效STL URL（已处理查询参数）")
                        print(f"   分割后的文件路径：{url_without_query}")
                        return stl_url  # 提取到直接返回，不执行后续逻辑

                # ---------------------- 备选：处理result.model.url ----------------------
                print(f"⚠️ output.model未提取到有效URL（或已跳过），尝试备选result.model.url")
                if "result" in task_data and "model" in task_data["result"]:
                    result_model = task_data["result"]["model"]
                    if (isinstance(result_model, dict)
                        and "url" in result_model
                        and result_model["url"].startswith("https://")):
                        # 同样处理查询参数
                        result_url_without_query = result_model["url"].split("?")[0]
                        if result_url_without_query.lower().endswith(".stl"):
                            stl_url = result_model["url"]
                            print(f"✅ 从result.model.url提取到有效STL URL")
                            return stl_url

                # ---------------------- 提取失败提示 ----------------------
                print(f"❌ 未提取到有效STL URL，实际回传：")
                print(f"output.model URL：{task_data.get('output', {}).get('model', '空')[:80]}...")
                return None

            elif task_status in ["FAILED", "REJECTED"]:
                error_msg = task_data.get("error_msg", "未知错误")
                print(f"❌ 转换任务失败：{error_msg}")
                return None

            time.sleep(POLL_INTERVAL)

        print(f"❌ 转换任务超时")
        return None
    except Exception as e:
        print(f"❌ GLB→STL转换异常：{str(e)}")
        return None


# ====================== 核心函数：multiview生成+自动转STL（完整代码） ======================
def generate_3d_by_multiview(files_list, user_text):
    """
    调用Multiview to Model接口生成3D模型，自动将GLB转为STL，最终仅返回STL格式URL
    :param files_list: 按[前→左→后→右]顺序的files列表（含file_token）
    :param user_text: 用户对模型的补充要求（如材质、精度）
    :return: 仅含STL格式的URL字典（key="STL"）/ None（失败）
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TRIPO_API_KEY}"
    }
    
    # 按文档限制prompt长度≤1024字符
    prompt = f"3D model of furniture based on multiviews, {user_text}"
    prompt = prompt[:1024]
    
    # 按文档构造Multiview请求参数
    data = {
        "type": "multiview_to_model",
        "model_version": "v2.5-20250123",
        "files": files_list,
        "prompt": prompt,
        "texture": True,
        "pbr": True,
        "texture_quality": "detailed",
        "face_limit": 10000,
        "auto_size": False
    }

    session = create_retry_session()
    try:
        print(f"\n===== 调用Multiview to Model生成3D模型 =====")
        response = session.post(TRIPO_GENERATE_URL, headers=headers, data=json.dumps(data), timeout=TIMEOUT)

        if response.status_code >= 400:
            error_data = response.json() if response.text else {}
            print(f"❌ 接口错误：{error_data.get('message', '未知错误')}")
            print(f"   错误码：{error_data.get('code', '未知')}")
            print(f"   官方建议：{error_data.get('suggestion', '无')}")
            return None

        response_data = response.json()
        if response_data["code"] == 0 and "task_id" in response_data["data"]:
            task_id = response_data["data"]["task_id"]  # multiview任务ID（转STL需用）
            trace_id = response.headers.get("X-Tripo-Trace-ID", "未知")
            print(f"✅ 任务提交成功：")
            print(f"   Task ID：{task_id}")
            print(f"   Trace ID：{trace_id}")
            status_url = f"{TRIPO_API_BASE_URL}/task/{task_id}"

            # 轮询任务状态
            for _ in range(MAX_POLL_TIMES):
                remaining = MAX_POLL_TIMES - _
                print(f"⏳ 等待模型生成（剩余{remaining}次重试，间隔{POLL_INTERVAL}秒）...")
                
                status_res = session.get(status_url, headers=headers, timeout=TIMEOUT)
                if status_res.status_code >= 400:
                    time.sleep(POLL_INTERVAL)
                    continue

                status_data = status_res.json()
                if status_data["code"] != 0:
                    print(f"⚠️ 状态查询异常：{status_data.get('message')}")
                    time.sleep(POLL_INTERVAL)
                    continue

                task_status = status_data["data"]["status"].upper()
                if task_status == "SUCCESS":
                    task_output = status_data["data"]
                    model_urls = {}

                    # 提取GLB URL（适配你的回传格式：result.pbr_model或output.pbr_model）
                    if "result" in task_output and "pbr_model" in task_output["result"]:
                        pbr_model = task_output["result"]["pbr_model"]
                        if isinstance(pbr_model, dict) and "url" in pbr_model:
                            model_urls["GLB"] = pbr_model["url"]
                            print(f"✅ 从result提取到GLB格式URL")
                    elif "output" in task_output and "pbr_model" in task_output["output"]:
                        pbr_url = task_output["output"]["pbr_model"]
                        if isinstance(pbr_url, str) and pbr_url.startswith("https://"):
                            model_urls["GLB"] = pbr_url
                            print(f"✅ 从output提取到GLB格式URL")

                    # 自动转STL（核心流程）
                    if "GLB" in model_urls:
                        print(f"\n⚠️ 检测到仅GLB格式，自动触发GLB→STL转换")
                        stl_url = convert_glb_to_stl(original_task_id=task_id)
                        if stl_url:
                            model_urls.clear()
                            model_urls["STL"] = stl_url  # 仅保留STL格式
                        else:
                            print(f"❌ 流程中断：GLB→STL转换失败")
                            return None
                    else:
                        print(f"❌ 未提取到GLB格式URL，无法转STL")
                        return None

                    # 返回仅含STL的URL字典
                    if "STL" in model_urls:
                        print(f"✅ 3D模型最终可用格式：{list(model_urls.keys())}（仅STL）")
                        return model_urls
                    else:
                        print(f"❌ 转换后仍无STL格式")
                        return None

                elif task_status in ["FAILED", "REJECTED"]:
                    error_msg = status_data["data"].get("error_msg", "未知错误")
                    print(f"❌ 任务失败：{error_msg}")
                    return None

                time.sleep(POLL_INTERVAL)

            print(f"❌ 任务超时（已等待{MAX_POLL_TIMES * POLL_INTERVAL}秒）")
            return None
        else:
            print(f"❌ 任务提交失败：{json.dumps(response_data, indent=2, ensure_ascii=False)}")
            return None
    except Exception as e:
        print(f"❌ 3D模型生成异常：{str(e)}")
        return None
    
# ====================== 7. 下载相关函数（优化后） ======================
# 1. 单视图下载函数（替换原有版本，自动生成“x视图+时间”文件名）
def download_single_tripo_image(img_url, view_type):
    """
    下载单张视图，命名格式：{view_type}视图_时间戳.jpg（如“前视图_20250506_143025.jpg”）
    :param img_url: 图片URL
    :param view_type: 视图类型（前/后/左/右）
    :return: 保存路径（成功）/ None（失败）
    """
    check_and_create_dir(TRIPO_OUTPUT_DIR)
    # 生成时间戳（格式：YYYYMMDD_HHMMSS）
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    # 规范文件名：视图类型+时间戳
    save_filename = f"{view_type}视图_{timestamp}.jpg"
    save_path = os.path.join(TRIPO_OUTPUT_DIR, save_filename)
    save_path = normalize_path(save_path)
    session = create_retry_session()

    try:
        print(f"\n⏳ 正在下载 {view_type}视图...")
        response = session.get(img_url, timeout=60)  # 延长超时应对2K图
        response.raise_for_status()
        with open(save_path, "wb") as f:
            f.write(response.content)
        print(f"✅ {view_type}视图已保存至：{save_path}")
        return save_path
    except Exception as e:
        print(f"❌ {view_type}视图下载失败：{str(e)}")
        # 重试：简化URL（去除参数，部分场景有效）
        if "?" in img_url:
            simplified_url = img_url.split("?")[0]
            print(f"⚠️ 尝试简化URL重试...")
            try:
                response = session.get(simplified_url, timeout=60)
                response.raise_for_status()
                with open(save_path, "wb") as f:
                    f.write(response.content)
                print(f"✅ {view_type}视图（简化URL）已保存至：{save_path}")
                return save_path
            except Exception as retry_e:
                print(f"❌ {view_type}视图重试失败：{str(retry_e)}")
    return None

# 下载3D模型（强制STL格式）
def download_3d_model(model_urls, save_dir="./tripo_3d_models"):
    """
    下载Multiview生成的3D模型，仅保留STL格式（适配3D打印）
    :param model_urls: 模型URL字典（key=格式，value=URL）
    :param save_dir: 保存目录
    """
    # 筛选STL格式模型
    stl_url = None
    for model_format, url in model_urls.items():
        if model_format.upper() == "STL":
            stl_url = url
            break
    
    if not stl_url:
        print(f"\n❌ 未找到STL格式模型，当前支持的格式：{list(model_urls.keys())}")
        print("⚠️ 建议联系TripoAI官方开启STL格式输出，或转换其他格式为STL")
        return

    # 创建保存目录
    check_and_create_dir(save_dir)
    session = create_retry_session()

    # 生成STL格式文件名（强制stl后缀）
    timestamp = time.strftime("%Y%m%d_%H%M%S", time.localtime())
    save_filename = f"家具模型_{timestamp}.stl"
    save_path = os.path.join(save_dir, save_filename)
    save_path = normalize_path(save_path)

    try:
        print(f"\n⏳ 正在下载STL格式3D模型...")
        # STL模型可能较大，延长超时至180秒
        response = session.get(stl_url, timeout=180)
        response.raise_for_status()
        
        # 强制以二进制写入STL文件
        with open(save_path, "wb") as f:
            f.write(response.content)
        
        print(f"✅ STL模型已保存至：{save_path}")
        print(f"ℹ️ 模型格式：STL（适配3D打印/建模软件）")
    except Exception as e:
        print(f"❌ STL模型下载失败：{str(e)}")
        # 重试简化URL（应对参数过长问题）
        if "?" in stl_url:
            simplified_url = stl_url.split("?")[0]
            print(f"⚠️ 尝试简化URL重试下载STL模型...")
            try:
                response = session.get(simplified_url, timeout=180)
                response.raise_for_status()
                with open(save_path, "wb") as f:
                    f.write(response.content)
                print(f"✅ STL模型（简化URL）已保存至：{save_path}")
            except Exception as retry_e:
                print(f"❌ STL模型重试下载失败：{str(retry_e)}")

# ====================== 8. 主流程（整合3个核心流程入口） ======================
if __name__ == "__main__":
    # ====================== 新增：总流程选择（用户期望的3个选项） ======================
    print("===== 家具3D模型生成总流程选择 =====")
    print("1. 完整流程：用户草图 → 豆包优化图 → 多视图 → 3D模型")
    print("2. 复用豆包图：现有豆包优化图 → 多视图 → 3D模型")
    print("3. 复用多视图：现有多视图 → 直接生成3D模型")
    while True:
        main_flow_choice = input("请选择总流程（1/2/3）：").strip()
        if main_flow_choice not in ["1", "2", "3"]:
            print("❌ 输入错误，请选择1/2/3！")
            continue
        break

    # 变量初始化（各流程共用）
    optimize_img_path = None
    tripo_image_token = None

    # ====================== 流程1：完整流程（草图→豆包→多视图→3D） ======================
    if main_flow_choice == "1":
        print("\n===== 步骤1：选择用户手绘草图 =====")
        user_edited_img_path = select_user_edited_image()
        if not user_edited_img_path:
            exit(1)
        
        print("\n===== 步骤2：生成豆包优化图 =====")
        optimize_img_path = optimize_image_by_doubao(user_edited_img_path)
        if not optimize_img_path or not os.path.exists(optimize_img_path):
            print("❌ Process interrupted: Doubao optimized image is invalid or missing")
            exit(1)

    # ====================== 流程2：复用豆包图（豆包→多视图→3D） ======================
    elif main_flow_choice == "2":
        print("\n===== 步骤1：选择现有豆包优化图 =====")
        # 【完全保留你原有豆包图选择逻辑】
        existing_img_path = select_existing_doubao_image()
        if existing_img_path == "regenerate":
            user_edited_img_path = select_user_edited_image()
            if not user_edited_img_path:
                exit(1)
            optimize_img_path = optimize_image_by_doubao(user_edited_img_path)
        elif existing_img_path:
            optimize_img_path = existing_img_path
        else:
            print(f"ℹ️ Automatically enter Doubao image regeneration process...")
            user_edited_img_path = select_user_edited_image()
            if not user_edited_img_path:
                exit(1)
            optimize_img_path = optimize_image_by_doubao(user_edited_img_path)
        
        if not optimize_img_path or not os.path.exists(optimize_img_path):
            print("❌ Process interrupted: Doubao optimized image is invalid or missing")
            exit(1)

    # ====================== 流程3：复用多视图（直接3D） ======================
    elif main_flow_choice == "3":
        print("\n===== 已选择「复用多视图直接生成3D模型」 =====")
        print(f"   提示：需准备前视图_*.jpg/左视图_*.jpg等格式文件（保存在 {TRIPO_OUTPUT_DIR}）")
        input("确认已准备好旧图路径后，按Enter键继续...")

    # ====================== 流程1/2 共用：生成多视图（流程3跳过） ======================
    if main_flow_choice in ["1", "2"]:
        # 【完全保留你原有“生成新图/用旧图”分支逻辑】
        while True:
            print("\n===== 视角图选择 =====")
            print("1. 生成新的前/左/后/右4张视角图（基于豆包优化图）")
            print("2. 使用已生成的旧视角图直接生成3D模型（跳过新图生成）")
            choice = input("请输入选择（1/2）：").strip()
            
            if choice not in ["1", "2"]:
                print("❌ 输入错误，请选择1或2！")
                continue
            
            # 分支1：生成新图（保留你原有逻辑）
            if choice == "1":
                # 【你原有代码：合并用户输入】
                user_text = input("\nEnter furniture modification + material/style (e.g., add handle, wood texture): ")
                if not user_text.strip():
                    user_text = "realistic texture, soft shadow, high detail"  # 默认拟真参数
                    print(f"⚠️ Using default requirement: {user_text}")

                # 【你原有代码：上传豆包优化图获取token】
                tripo_image_token = upload_to_tripo(optimize_img_path)
                if not tripo_image_token:
                    print("❌ Process interrupted: TripoAI upload failed")
                    exit(1)

                # 【你原有代码：分4次生成前/左/后/右视图】
                views_to_generate = [
                    ("Front", "前"),   # 接口第1位：前视图（必填）
                    ("Left", "左"),    # 接口第2位：左视图（必填，至少2张图）
                    ("Back", "后"),    # 接口第3位：后视图（可选）
                    ("Right", "右")    # 接口第4位：右视图（可选）
                ]

                # 【你原有代码：依次生成每个视角】
                for api_view_type, chinese_view_type in views_to_generate:
                    print(f"\n===== Generating {chinese_view_type}视图 =====")
                    view_url = generate_single_view_by_tripo(tripo_image_token, api_view_type, user_text)
                    if not view_url:
                        print(f"❌ Process interrupted: {chinese_view_type}视图生成失败")
                        exit(1)
                    download_single_tripo_image(view_url, chinese_view_type)

                # 【你原有代码：生成完成提示】
                print(f"\n✅ All 4 views generated! Saved to {TRIPO_OUTPUT_DIR}")
                print(f"   File format example: 前视图_20250506_143025.jpg / 左视图_20250506_143025.jpg")
                print(f"   Order for 3D model: 前→左→后→右（已匹配Multiview接口要求）")
                break
            
            # 分支2：用旧图（跳过新图生成）
            elif choice == "2":
                print("\nℹ️ 已选择使用旧视角图，即将进入3D模型生成流程！")
                print(f"   提示：旧图需符合格式（前视图_*.jpg/左视图_*.jpg等），且保存在 {TRIPO_OUTPUT_DIR}")
                input("确认已准备好旧图路径后，按Enter键继续...")
                break

    # ====================== 所有流程共用：3D模型生成流程（完全保留你的原有逻辑） ======================
    print(f"\n===== 开始通过4张视图生成3D模型 =====")
    multiview_files = upload_4_views_for_multiview()
    if not multiview_files:
        print("❌ 流程中断：无法构造Multiview接口所需的视图列表")
        exit(1)

    model_user_text = input("\n请输入3D模型要求（如“木质纹理、低多边形”）：").strip()
    if not model_user_text:
        model_user_text = "realistic texture, high detail, suitable for 3D printing"  # 默认要求

    model_urls = generate_3d_by_multiview(multiview_files, model_user_text)
    if not model_urls:
        print("❌ 流程中断：3D模型生成失败")
        exit(1)

    download_3d_model(model_urls)
    print(f"\n🎉 全流程完成！3D模型保存至：tripo_3d_models 文件夹")