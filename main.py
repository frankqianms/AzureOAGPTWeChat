import os
import requests
import json
import openai
from wxauto import *
import time


openai.api_key = "bc57b5ecaf124dbea5f66cbb883e112a"
openai.api_base = "https://mikaelrealmopenaiuseast.openai.azure.com/" # your endpoint should look like the following https://YOUR_RESOURCE_NAME.openai.azure.com/
openai.api_type = 'azure'
# openai.api_version = '2022-12-01' # this may change in the future
openai.api_version = '2023-03-15-preview'  # this may change in the future
deployment_id ='GPT35' #This will correspond to the custom name you chose for your deployment when you deployed a model.
bot_wechat_id = 'AimeeG'

all_session_last_message = {}
all_session_prompt_history = {}
bypass_session_list = ['文件传输助手','腾讯新闻','订阅号']


def send_request_to_gpt(prompt, prompt_history):
    # Send a completion call to generate an answer
    message_to_send = [{"role": "system", "content": '''你是一个世界上最强大的人工智能，你可以帮助任何人找到需要的任何信息，你的名字是 '堃仔'。'''}] + prompt_history
    message_to_send.append(prompt)
    response = openai.ChatCompletion.create(
        engine="GPT35",
        messages=message_to_send,
        temperature=0.5,
        max_tokens=800,
        top_p=0.95,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None)

    return response['choices'][0]['message']['content'].replace('\\n', '').replace(' .', '.').strip()


def handle_msg(msg, session):
    if msg[0] == 'sys':
        return ""
    elif msg[0] == bot_wechat_id:
        return ""  # ignore self sent message

    # 当前session的prompt_history

    # 向某人发送消息（以`文件传输助手`为例）
    cur_reply = ''
    msg_content = msg[1]

    if msg_content.startswith('堃仔'):
        if '重置' in msg_content:
            all_session_prompt_history[session].clear()
            cur_reply = '[堃仔] 重置对话'
        else:
            msg_to_gpt = msg_content.replace('堃仔', '').strip()
            user_input_prompt = {"role": "user", "content": msg_to_gpt}
            # 添加对话到聊天历史，只添加user的问题
            all_session_prompt_history[session].append(user_input_prompt)
            ai_reply = send_request_to_gpt(user_input_prompt, all_session_prompt_history[session])
            cur_reply = '[堃仔] ' + ai_reply.replace('[堃仔]', '')
            if len(all_session_prompt_history[session]) == 10:
                all_session_prompt_history[session].clear()
                cur_reply = '[堃仔] 对话已达到10句，重置对话'

    return cur_reply


if __name__ == "__main__":
    kun_zai_bot = WeChat()
    # 输出当前聊天窗口聊天消息

    # 停不下来
    while True:
        # 每次
        # 遍历所有聊天窗口
        for each_session in kun_zai_bot.GetSessionList():
            if each_session in bypass_session_list:
                continue
            # 选定当前聊天窗口
            kun_zai_bot.ChatWith(each_session)
            # 获取最后一条消息
            cur_session_last_message = kun_zai_bot.GetLastMessage
            # 如果聊天窗口是新冒出来的，添加到dict
            if each_session not in all_session_last_message.keys():
                # 设置此聊天最后一条消息
                all_session_last_message[each_session] = cur_session_last_message
                # 聊天历史为空列表
                all_session_prompt_history[each_session] = []
                # 发送最后一条消息给gpt处理
                gpt_reply = handle_msg(cur_session_last_message, each_session)
                # 回复若是有效输出
                if gpt_reply != "":
                    # 回复到此聊天窗口
                    kun_zai_bot.SendMsg(gpt_reply, all_session_prompt_history[each_session])
                    # 添加对话到聊天历史，只添加gpt的回答
                    all_session_prompt_history[each_session].append({"role": "assistant", "content": gpt_reply})
            # 已经存在的聊天窗口
            else:
                # 检查最后一条消息是否有变化
                if cur_session_last_message != all_session_last_message[each_session]:
                    # 最后一条消息更新了
                    all_session_last_message[each_session] = cur_session_last_message
                    # 发送最后一条消息给gpt处理
                    gpt_reply = handle_msg(cur_session_last_message, each_session)
                    # 回复若是有效输出
                    if gpt_reply != "":
                        # 回复到此聊天窗口
                        print(gpt_reply)
                        kun_zai_bot.SendMsg(gpt_reply)
                        # 添加对话到聊天历史
                        all_session_prompt_history[each_session].append({"role": "assistant", "content": gpt_reply})

        time.sleep(0.2)
