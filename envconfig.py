import logging
import os
from datetime import datetime

# Constants


key1 = "bc57b5ecaf124dbea5f66cbb883e112a"
api_base1 = "https://mikaelrealmopenaiuseast.openai.azure.com/"
key2 = "e0fa531d0d4d4c96a70be8434c5f85b4"
api_base2 = "https://mikaelrealmopenaiussouthcentral.openai.azure.com/"
OPENAI_API_TYPE = 'azure'
OPENAI_API_VERSION = '2023-03-15-preview'
# openai.api_version = '2022-12-01'
deployment_id = 'GPT35'
bot_wechat_id = '堃仔'
bot_name = "堃仔"
gpt_temperature = 0.8
gpt_max_token = 1500
# 发送给gpt的消息历史最大数量
max_token_per_session = 20
wechat_one_msg_upper_limit = 600
bot_name_in_reply = ''  # '[AI]'
# bot_name_in_reply = ''
chat_hint = [bot_name, '@' + bot_name + ' ']  # , "[AI]"]
image_hint = bot_name + "生成图片："
image_backend_hint = "生成图片："
sensitive_prompts = ["nude", "pussy", "topless", "breast", "boob", "busty", "naked", "sensual", "sex", "cock", "penis", "masturbate", "masturbating", "nipple", "chest"]


# 日志文件
folder_path = "logs"
if not os.path.exists(folder_path):
    os.makedirs(folder_path)

filename = "logs\\" + datetime.now().strftime(
    "%d-%m-%Y") + ".txt"  # Setting the filename from current date and time
logging.basicConfig(filename=filename, filemode='a',
                    format="%(asctime)s, %(msecs)d %(name)s %(levelname)s "
                           "[ %(filename)s-%(module)s-%(lineno)d ]  : %(message)s",
                    datefmt="%H:%M:%S",
                    level=logging.INFO)


def console_log(log_line):
    print(str(datetime.now())[:-4] + ' ' + log_line)
