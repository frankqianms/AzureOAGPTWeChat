# 导入Selenium库
import shutil

from selenium.common import TimeoutException
from selenium.webdriver.support.expected_conditions import visibility_of_element_located
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options
from selenium.webdriver import Edge, ActionChains
from datetime import date
from datetime import datetime
import subprocess
import time
import os
from selenium.webdriver.support.wait import WebDriverWait
import openai
from envconfig import *


negative_prompt = "(NSFW: 2), paintings, sketches, (worst quality:2), (low quality:2), (normal quality:2), " \
                  "low res, normal quality, ((monochrome)), ((grayscale)), skin spots, acnes, skin blemishes, " \
                  "age spot, glans, bad legs, error legs, bad feet, 6 more fingers on one hand, deformity, " \
                  "malformed limbs, extra limbs,"

image_width = 512
image_height = 768
image_process_timeout = 30


def get_formatted_prompt_from_gpt(prompt):
    # Send a completion call to generate an answer
    system_prompt = '你是一个世界上最强大的人工智能，你可以帮助任何人找到需要的任何信息'
    message_to_send = [{"role": "system", "content": system_prompt}]
    user_prompt = {"role": "user", "content": prompt}
    message_to_send.append(user_prompt)
    try:
        response = openai.ChatCompletion.create(
            engine="GPT35",
            messages=message_to_send,
            temperature=gpt_temperature,
            max_tokens=gpt_max_token,
            frequency_penalty=0.2,
            presence_penalty=0,
            stop=None)
    except Exception as ex:
        print(str(datetime.now())[:-4] + " has error with Azure OpenAI API call: " + str(ex))
        if openai.api_key == key1:
            openai.api_key = key2
            openai.api_base = api_base2
        else:
            openai.api_key = key1
            openai.api_base = api_base2
        logging.info("Switching to backup key success")
        response = openai.ChatCompletion.create(
            engine="GPT35",
            messages=message_to_send,
            temperature=gpt_temperature,
            max_tokens=gpt_max_token,
            frequency_penalty=0.2,
            presence_penalty=0,
            stop=None)

    # return response['choices'][0]['message']['content'].replace('\\n', '').replace(' .', '.').strip()
    return response['choices'][0]['message']['content'].strip()


def filter_by_sensitive_keywords(prefilter_prompt):
    filtered_prompt = prefilter_prompt.strip().split(',')
    filtered_prompt = [item for item in filtered_prompt if all(exclude_item not in item for exclude_item in sensitive_prompts)]
    filtered_prompt = ','.join(filtered_prompt)
    return filtered_prompt


def process_sd_request(driver, user_prompt):
    # 从user_prompt获取关键词，发送给gpt生成适合SD的prompt
    # 发送给浏览器sd webui处理图片生成请求
    request_to_gpt = '''StableDiffusion是一款利用深度学习的文生图模型，支持通过使用提示词来产生新的图像，描述要包含或省略的元素。
我在这里引入StableDiffusion算法中的Prompt概念，又被称为提示符。
下面的prompt是用来指导AI绘画模型创作图像的。它们包含了图像的各种细节，如人物的外观、背景、颜色和光线效果，以及图像的主题和风格。这些prompt的格式经常包含括号内的加权数字，用于指定某些细节的重要性或强调。例如，"(masterpiece:1.5)"表示作品质量是非常重要的，多个括号也有类似作用。此外，如果使用中括号，如"{blue hair:white hair:0.3}"，这代表将蓝发和白发加以融合，蓝发占比为0.3。括号内的加权数字单个不应该超过1.5，平均数应该约等于1。
如果prompt包含人体，请必须在prompt中包含给人物描绘完整的服装。如果对象主体不是人物，那么不要给出人物相关的prompt，例如衣物，服装等。
以下是用prompt帮助AI模型生成图像的例子：cold , solo , ( 1girl ) , detailed eyes , shinegoldeneyes, ( longliverhair ), expressionless , ( long sleeves , puffy sleeves ) ,  ( white wings ) , shinehalo , ( heavymetal : 1 . 2 ) , ( metaljewelry ) ,  cross-lacedfootwear ( chain ) ,  ( Whitedoves : 1 . 2 ) 

可以选择的prompt包括：

颜色
light（明）
dark（暗）
pale（薄）
deep（濃）

天气 时间
golden hour lighting  （阳光照明）
strong rim light      （强边缘光照）
intense shadows  （强烈的阴影）
in the rain            （雨）
rainy days              （雨）
sunset                  （日落）
cloudy                   （多云）

建筑物
in the baroque architecture     （巴洛克建筑 文艺复兴时期意大利的一种装修风格，外形自由，追求动感，喜好富丽）
in the romanesque architecture streets        （罗马式街道）
in the palace                                 （宫廷）
at the castle（城的外观为背景）
in the castle（城的内部为背景）
in the street                                   （在街上）
in the cyberpunk city                       （在赛博朋克城市里）
rainy night in a cyberpunk city with glowing neon lights  （在雨天的赛博朋克城市，还有霓虹灯）
at the lighthouse                               （在灯塔周围）
in misty onsen                                 （温泉）
by the moon                                     （月亮边上）
in a bar, in bars                                   （酒吧）
in a tavern                                        （居酒屋）
Japanese arch                                  （鳥居）
in a locker room                                 （在上锁的房间里）

山
on a hill（山上）
the top of the hill（山顶）

海
on the beach       （海滩上）
over the sea           （海边上）
beautiful purple sunset at beach  （海边的美丽日落）
in the ocean           （海中）
on the ocean          （船上）

仿照例子，并不局限于我给你的单词，给出一套详细描述“''' + user_prompt + '''”的prompt，每个prompt以逗号分隔，注意：prompt不能超过80个。直接开始给出英文版的prompt不需要用自然语言描述。'''
    prompt_input = "(extremely detailed CG unity 8k wallpaper), (masterpiece), (best quality), (ultra-detailed), (best illustration), (best shadow), ultra-high res, (realistic, photo-realistic:1.2),"

    translation_prompt = "翻译以下内容为英文：" + user_prompt
    translated_prompt = get_formatted_prompt_from_gpt(translation_prompt)
    # print(translated_prompt)
    translated_prompt = translated_prompt.strip().replace('.', '')

    # 过滤敏感词：
    translated_prompt = filter_by_sensitive_keywords(translated_prompt)
    # print(translated_prompt)
    formatted_user_prompt = get_formatted_prompt_from_gpt(request_to_gpt)

    formatted_user_prompt = filter_by_sensitive_keywords(formatted_user_prompt)

    prompt_input = prompt_input + translated_prompt + ", " + formatted_user_prompt
    # 获取prompt输入框
    prompt_text_area = driver.find_element(By.XPATH, "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]"
                                                     "/div/div[1]/div[1]/div[1]/div/div/div/div[2]/label/textarea")
    # 清除历史内容
    prompt_text_area.clear()
    prompt_text_area.send_keys(prompt_input)

    # 定位生成按钮，并点击
    generate_button = driver.find_element(By.XPATH, "//*[contains(text(), '生成')]")
    print(str(datetime.now())[:-4] + "开始出图")
    generate_button.click()

    # 判断出图是否成功

    """
    失败案例：
    OutOfMemoryError: CUDA out of memory. Tried to allocate 8.82 GiB (GPU 0; 23.99 GiB total capacity; 10.98 GiB already allocated; 10.39 GiB free; 11.03 GiB reserved in total by PyTorch) If reserved memory is >> allocated memory try setting max_split_size_mb to avoid fragmentation. See documentation for Memory Management and PYTORCH_CUDA_ALLOC_CONF
    Time taken: 0.55sTorch active/reserved: 9854/9922 MiB, Sys VRAM: 12552/24564 MiB (51.1%)
    
    判断条件：2秒内结束说明出图失败
    """
    image_process_done = False
    for iterator in range(image_process_timeout):
        button_skip = driver.find_element(By.ID, 'txt2img_skip')
        button_style = button_skip.get_attribute('style')
        if button_style == 'display: none;':
            print(str(datetime.now())[:-4] + "出图结束")
            image_process_done = True
            break
        elif button_style == 'display: block;':
            # 出图中
            pass
        time.sleep(1)

    if image_process_done:
        time_taken_text = driver.find_element(By.XPATH, "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[5]/div[2]/div[2]/div[3]/div[2]/div[2]/div/div/p[1]")
        # print(str(datetime.now())[:-4] + time_taken_text.text)
        time_taken_seconds = time_taken_text.text.split(":")[1][:-1].strip()
        if float(time_taken_seconds) < 2.0:
            print(str(datetime.now())[:-4] + "出图失败")
        else:
            print(str(datetime.now())[:-4] + "出图成功，用时" + time_taken_seconds + "秒")
            # 获取seed ID，防止发错图给聊天
            seed_text = driver.find_element(By.XPATH,
                                                  "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[5]/div[2]/div[2]/div[3]/div[1]/div[2]/div").text
            seed_index_start = seed_text.find("Seed: ") + len("Seed: ")
            seed_index_end = seed_text.find(", Size:")
            seed_value = seed_text[seed_index_start: seed_index_end]
            return seed_value
    else:
        print(str(datetime.now())[:-4] + "出图超时，中止出图")
        # 定位中止按钮，并点击
        stop_button = driver.find_element(By.XPATH, "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[1]/div[2]/div[1]/button[1]")
        stop_button.click()

    return None


def initialize_sd_web_ui(driver):
    # 获取negative prompt输入框
    neg_prompt_text_area = driver.find_element(By.XPATH, "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]"
                                                         "/div/div[1]/div[1]/div[2]/div/div/div/div[2]/label/textarea")
    neg_prompt_text_area.clear()
    # 设置预设的negative prompt
    neg_prompt_text_area.send_keys(negative_prompt)

    # 获取采样方法
    # 点击采样方法下拉框
    dropdown_button = driver.find_element(By.XPATH,
                                          '/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[5]/div[1]/div[1]/div/div[1]/label/div/div[1]')
    dropdown_button.click()

    # 等待下拉框加载
    wait = WebDriverWait(driver, 1)
    dropdown_menu = wait.until(visibility_of_element_located((By.XPATH,
                                                              '/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[5]/div[1]/div[1]/div/div[1]/label/div/ul')))

    # 点击需要的采样方法
    sampler_option = dropdown_menu.find_element(By.XPATH, "//li[@data-value='DPM++ SDE Karras']")
    sampler_option.click()

    # 设置sampling step
    sampler_step = driver.find_element(By.XPATH,
                                       "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[5]/div[1]/div[1]/div/div[2]/div[2]/div/input")
    sampler_step.clear()
    sampler_step.send_keys(28)

    # 设置面部修复
    face_fix_check_box = driver.find_element(By.XPATH, "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[5]/div[1]/div[2]/div[1]/label/input")
    face_fix_check_box.click()

    # 设置提示词相关性
    cfg_scale_num = driver.find_element(By.XPATH, "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[5]/div[1]/div[5]/div[2]/div/input")
    cfg_scale_num.clear()
    cfg_scale_num.send_keys(9)

    # 设置图片宽度
    image_width_box = driver.find_element(By.XPATH,
                                          "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[5]/div[1]/div[4]/div[1]/div/div[2]/div[2]/div/input")
    image_width_box.clear()
    image_width_box.send_keys(image_width)

    # 设置图片高度
    image_height_box = driver.find_element(By.XPATH,
                                           "/html/body/gradio-app/div/div/div/div/div/div[2]/div[2]/div/div[5]/div[1]/div[4]/div[1]/div/div[2]/div[2]/div/input")
    image_height_box.clear()
    image_height_box.send_keys(image_height)


def find_current_sd_output_folder():
    current_date = date.today()
    current_date_string = current_date.strftime('%Y-%m-%d')
    path = os.path.join(sd_webui_output_folder_path, current_date_string)
    if os.path.isdir(path):
        return path
    else:
        return None


def move_image_to_output(cur_folder_path, session, generated_image_seed):
    time.sleep(1)
    png_files = [file for file in os.listdir(cur_folder_path) if file.endswith('.png')]
    last_png_file = png_files[-1]
    file_end = generated_image_seed + ".png"
    if last_png_file.endswith(file_end):
        print("找到目标图片，正在移动中")
        destination_folder_path = os.path.join(image_output_folder_path, session)
        if not os.path.exists(destination_folder_path):
            os.makedirs(destination_folder_path)
        dest_file_name_str = session + " " + generated_image_seed + ".png"
        source_file_path = os.path.join(cur_folder_path, last_png_file)
        shutil.copy2(source_file_path, destination_folder_path + '\\' + dest_file_name_str)
        print("移动完成")
    else:
        print("未找到目标图片")


def update_request_file_name_by_seed(file_path, generated_image_seed):
    old_name = file_path.split('\\')[-1]
    new_name = old_name.replace('.txt', '-' + generated_image_seed + '.txt')
    return new_name


def run_stable_diffusion_queue():
    # # 启动Stable Diffusion webui
    # batch_file = "F:\\stable-diffusion-webui\\webui.bat"
    # # Save the current working directory
    # original_dir = os.getcwd()
    # # Change the current working directory to the same drive as the batch file
    # os.chdir(os.path.splitdrive(batch_file)[0])
    # # Run the batch file using subprocess
    # subprocess.call(batch_file, shell=True)
    # time.sleep(10)
    # # Change the current working directory back to the original directory
    # os.chdir(original_dir)

    # 设置 EdgeOptions 选项
    options = Options()
    options.use_default_content_settings = True
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-popup-blocking")

    # 如果 Edge 浏览器和驱动器文件不在同一目录，则需要设置路径。这里我们将 Edge 浏览器和驱动器文件保存在同一目录中。
    service = Service("F:\\stable-diffusion-webui\\edgedriver_win64\\msedgedriver.exe")  # 驱动器路径
    driver = Edge(service=service, options=options)

    # 打开SD的webui网页
    url = "http://127.0.0.1:7860/"
    driver.get(url)
    # 最小化窗口
    # driver.minimize_window()
    time.sleep(10)
    initialize_sd_web_ui(driver)

    while True:
        # Image Requests 文件夹应该包含以聊天会话名作为文件夹名的，每一个聊天里未处理的图片请求，请求为txt格式的文字
        #  - aimee
        #    - time_stamp1.txt
        #    - time_stamp2.txt
        session_image_request_folders = [f for f in os.listdir(requests_folder_path) if os.path.isdir(os.path.join(requests_folder_path, f))]

        # 遍历所有会话的文件夹
        for folder in session_image_request_folders:
            session = folder
            # 获取所有txt的请求文件
            files = [fs for fs in os.listdir(os.path.join(requests_folder_path, folder)) if fs.endswith('.txt')]
            # 遍历会话的所有请求
            for file in files:
                file_path = os.path.join(requests_folder_path, folder, file)
                # 获取当前请求txt
                with open(file_path, 'r') as f:
                    file_content = f.read()
                # 处理当前请求
                print(str(datetime.now())[:-4] + "画图请求：" + file_path)
                generated_image_seed = process_sd_request(driver, file_content)
                if generated_image_seed:
                    cur_folder_path = find_current_sd_output_folder()
                    if cur_folder_path:
                        print(str(datetime.now())[:-4] + "出图完成：" + file_content)
                        move_image_to_output(cur_folder_path, session, generated_image_seed)
                        # 把请求的文件名添加上seed，方便和图片文件名对应起来
                        new_file_name = update_request_file_name_by_seed(file_path, generated_image_seed)

                    else:
                        print(str(datetime.now())[:-4] + "无法找到SD webui出图文件夹 " + cur_folder_path)
                # 处理完成不管成功失败，都移动request 文件到历史记录
                print(str(datetime.now())[:-4] + "归档请求：" + file_path)
                destination_folder = os.path.join(image_history_folder_path, session)
                if not os.path.exists(destination_folder):
                    os.makedirs(destination_folder)
                shutil.copy2(file_path, destination_folder + '\\' + new_file_name)
                os.remove(file_path)
        time.sleep(1)
