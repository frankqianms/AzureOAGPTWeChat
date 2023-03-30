import os
import requests
import json
import openai
from wxauto import *
import time
import threading
import schedule


openai.api_key = "bc57b5ecaf124dbea5f66cbb883e112a"
openai.api_base = "https://mikaelrealmopenaiuseast.openai.azure.com/" # your endpoint should look like the following https://YOUR_RESOURCE_NAME.openai.azure.com/
openai.api_type = 'azure'
# openai.api_version = '2022-12-01' # this may change in the future
openai.api_version = '2023-03-15-preview'  # this may change in the future
deployment_id ='GPT35' #This will correspond to the custom name you chose for your deployment when you deployed a model.
bot_wechat_id = 'AimeeG'

all_session_last_message = {}
all_session_prompt_history = {}
bypass_session_list = ['文件传输助手','腾讯新闻','订阅号','微信团队']
chat_hint = "堃仔"

# 每个会话一个单独请求队列，先问先答，直到没有消息
session_request_queue = {}


class GPTRequestThread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)
        self.threadID = id
        self.shut_down_flag = False

    def send_request_to_gpt(prompt, prompt_history):
        # Send a completion call to generate an answer
        system_prompt = '你是一个世界上最强大的人工智能，你可以帮助任何人找到需要的任何信息，你的名字是' + chat_hint
        message_to_send = [{"role": "system",
                            "content": system_prompt}] + prompt_history
        message_to_send.append(prompt)
        response = openai.ChatCompletion.create(
            engine="GPT35",
            messages=message_to_send,
            temperature=0.8,
            max_tokens=800,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None)

        # return response['choices'][0]['message']['content'].replace('\\n', '').replace(' .', '.').strip()
        return response['choices'][0]['message']['content'].strip()

    def handle_msg(msg, session):
        if msg[0] == 'sys':
            return ""
        elif msg[0] == bot_wechat_id:
            return ""  # ignore self sent message

        # 当前session的prompt_history

        # 向某人发送消息（以`文件传输助手`为例）
        cur_reply = ''
        msg_content = msg[1]

        if msg_content.startswith(chat_hint):
            if '重置' in msg_content:
                if session in all_session_prompt_history.keys():
                    all_session_prompt_history[session].clear()
                cur_reply = '[' + chat_hint + '] ' + ' 重置对话'
            else:
                msg_to_gpt = msg_content.replace(chat_hint, '').strip()
                user_input_prompt = {"role": "user", "content": msg_to_gpt}
                # 添加对话到聊天历史，只添加user的问题
                all_session_prompt_history[session].append(user_input_prompt)
                ai_reply = send_request_to_gpt(user_input_prompt, all_session_prompt_history[session])
                cur_reply = '[' + chat_hint + '] ' + ai_reply.replace('[' + chat_hint + ']', '')

        return cur_reply


def send_request_to_gpt(prompt, prompt_history):
    # Send a completion call to generate an answer
    system_prompt = '你是一个世界上最强大的人工智能，你可以帮助任何人找到需要的任何信息，你的名字是' + chat_hint
    message_to_send = [{"role": "system", "content": system_prompt}] + prompt_history
    message_to_send.append(prompt)
    response = openai.ChatCompletion.create(
        engine="GPT35",
        messages=message_to_send,
        temperature=0.8,
        max_tokens=800,
        frequency_penalty=0,
        presence_penalty=0,
        stop=None)

    # return response['choices'][0]['message']['content'].replace('\\n', '').replace(' .', '.').strip()
    return response['choices'][0]['message']['content'].strip()


def handle_msg(msg, session):
    if msg[0] == 'sys':
        return ""
    elif msg[0] == bot_wechat_id:
        return ""  # ignore self sent message

    # 当前session的prompt_history

    # 向某人发送消息（以`文件传输助手`为例）
    cur_reply = ''
    msg_content = msg[1]

    if msg_content.startswith(chat_hint):
        if '重置' in msg_content:
            if session in all_session_prompt_history.keys():
                all_session_prompt_history[session].clear()
            else:
                all_session_prompt_history[session] = []
            cur_reply = '[' + chat_hint + ']' + ' 重置对话'
        else:
            msg_to_gpt = msg_content.replace(chat_hint, '').strip()
            user_input_prompt = {"role": "user", "content": msg_to_gpt}
            # 添加对话到聊天历史，只添加user的问题
            process_prompt_history(session, user_input_prompt)
            ai_reply = send_request_to_gpt(user_input_prompt, all_session_prompt_history[session])
            cur_reply = '[' + chat_hint + '] ' + ai_reply.replace('[' + chat_hint + ']', '')

    return cur_reply


def process_prompt_history(session, prompt):
    if prompt == {}:
        return None
    if session not in all_session_prompt_history.keys():
        # 聊天历史为空列表
        all_session_prompt_history[session] = []
        all_session_prompt_history[session].append(prompt)
    else:
        all_session_prompt_history[session].append(prompt)


def process_gpt_reply(bot, session, last_message):
    # 发送最后一条消息给gpt处理
    gpt_reply = handle_msg(last_message, session)
    # 回复若是有效输出
    if gpt_reply != "":
        # 回复到此聊天窗口
        print(last_message)
        print(gpt_reply)
        # 小于1500字直接发送
        if len(gpt_reply) < 1500:
            WxUtils.SetClipboard(gpt_reply)
            bot.SendClipboard()
        # 大于1500字分批发送，每次1500字
        else:
            start_index = 0
            while start_index + 1500 <= len(gpt_reply):
                WxUtils.SetClipboard(gpt_reply[start_index:start_index + 1500])
                bot.SendClipboard()
                start_index = start_index + 1500
            if start_index < len(gpt_reply):
                WxUtils.SetClipboard(gpt_reply[start_index:])
                bot.SendClipboard()

        # kun_zai_bot.SendMsg(gpt_reply)
        if len(all_session_prompt_history[each_session]) == 20:
            all_session_prompt_history[each_session].clear()
            reset_reply = '[' + chat_hint + '] ' + '对话已达到10句，重置对话'
            kun_zai_bot.SendMsg(reset_reply)
    return gpt_reply


def process_last_message(session, last_message):
    """

    :param session:
    :param last_message:
    :return: True if has new message
    """
    if session not in all_session_last_message.keys():
        # 设置此聊天最后一条消息
        all_session_last_message[each_session] = last_message
        return True
    else:
        if all_session_last_message[session] != last_message:
            all_session_last_message[each_session] = last_message
            return True
    return False


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
            if process_last_message(each_session, cur_session_last_message):
                reply = process_gpt_reply(kun_zai_bot, each_session, cur_session_last_message)
                if reply != "":
                    cur_prompt = {"role": "assistant", "content": reply}
                    process_prompt_history(each_session, cur_prompt)

        time.sleep(0.1)
