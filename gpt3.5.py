import openai
from wxauto import *
import time
import threading
import logging
from datetime import datetime

# Constants
openai.api_key = "bc57b5ecaf124dbea5f66cbb883e112a"
openai.api_base = "https://mikaelrealmopenaiuseast.openai.azure.com/"
openai.api_type = 'azure'
# openai.api_version = '2022-12-01'
openai.api_version = '2023-03-15-preview'
deployment_id ='GPT35'
bot_wechat_id = '堃仔'
gpt_temperature = 0.8
gpt_max_token = 1500
max_token_per_session = 20
wechat_one_msg_upper_limit = 1500
num_message_history_to_check = 5


bypass_session_list = ['文件传输助手','腾讯新闻','订阅号','微信团队']
bot_name = "堃仔"
bot_name_in_reply = '[AI]'
# bot_name_in_reply = ''
chat_hint = ["堃仔"]  #, "[AI]"]

# 所有会话的最后num_message_history_to_check条消息
all_session_last_message = {}
# 所有会话的gpt prompt history，session_name为key, [{prompt},..]为value
all_session_prompt_history = {}
# 每个会话一个单独请求队列，先问先答，直到没有消息
session_request_queue = {}

# 存储生成的线程列表
thread_list = {}

# 日志文件
filename = "C:\\Users\\kufang\\PycharmProjects\\gpt3.5\\" + datetime.now().strftime("%d-%m-%Y %H-%M-%S") + ".txt" #Setting the filename from current date and time
logging.basicConfig(filename=filename, filemode='a',
                    format="%(asctime)s, %(msecs)d %(name)s %(levelname)s [ %(filename)s-%(module)s-%(lineno)d ]  : %(message)s",
                    datefmt="%H:%M:%S",
                    level=logging.INFO)


class GPTRequestThread(threading.Thread):
    def __init__(self, session_id):
        threading.Thread.__init__(self)
        self.thread_id = id
        self.idle_time = 0
        self.name = session_id
        self.session = session_id
        if self.session not in session_request_queue.keys():
            session_request_queue[self.session] = []
        if self.session not in all_session_prompt_history.keys():
            all_session_prompt_history[self.session] = []

    def send_request_to_gpt(self, prompt, prompt_history):
        # Send a completion call to generate an answer
        system_prompt = '你是一个世界上最强大的人工智能，你可以帮助任何人找到需要的任何信息，你的名字是' + bot_name
        message_to_send = [{"role": "system",
                            "content": system_prompt}] + prompt_history
        message_to_send.append(prompt)
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

    def my_worker(self):
        logging.info(self.name + ": Thread started.")
        while True:
            # 删掉所有已发送的消息
            session_request_queue[self.session][:] = [x for x in session_request_queue[self.session] if not x[2]]
            # 处理队列中所有消息
            if len(session_request_queue[self.session]) != 0:
                for each_query in session_request_queue[self.session]:
                    # 队列中每个用户消息尚未得到gpt回复时
                    if each_query[1] is None:
                        # 构造发送给gpt的prompt
                        msg_to_gpt = each_query[0].strip()
                        user_prompt = {"role": "user", "content": msg_to_gpt}
                        # 发送给gpt，得到答复
                        try:
                            logging.info("Before sending Query")
                            logging.info("Query is: " + each_query[0])
                            ai_reply = self.send_request_to_gpt(user_prompt, all_session_prompt_history[self.session])

                        # 将回复填入队列中第一个消息的回复里
                            each_query[1] = ai_reply
                            # print("\n会话 " + self.session + " ，问题 " + each_query[0] + " 获取gpt回答成功\n")
                            logging.info("After sending Query")
                            logging.info("Reply stored is: " + each_query[1])
                        except Exception as e:
                            print(e)
                            logging.info("Exception in sending query to gpt.")
                            logging.info("Exception is: " + e)
                    self.idle_time = 0
            else:
                self.idle_time = self.idle_time + 1
            time.sleep(0.1)
            # 如果3分钟左右没有新消息，释放线程
            if self.idle_time >= 1800:
                break
        thread_list.pop(self.session)
        logging.info(self.name + "Thread released due to idle for 3 minutes.")

    def run(self):
        self.my_worker()


def handle_msg(msg):
    """

    :param msg: 微信消息
    :return: True 如果消息需要转发给gpt
    """
    # 系统消息忽略
    if msg[0] == 'sys':
        return False
    # 自己发的消息忽略
    elif msg[0] == bot_wechat_id:
        return False

    msg_content = msg[1]

    # 不以chat_hint开头的忽略
    if msg_content.startswith(tuple(chat_hint)):
        # 重置消息无需发给gpt
        if '重置' in msg_content:
            return False
        else:
            return True

    return False


def process_last_message(last_session, last_message):
    """

    :param last_session:
    :param last_message:
    :return: True if has new message
    """
    if last_message is None:
        return False
    # 如果消息是自己发的，跳过
    if last_message[0] == bot_wechat_id:
        return False
    # 如果聊天窗口是新冒出来的，添加到dict
    if last_session not in all_session_last_message.keys():
        # 添加此聊天最后一条消息到列表
        all_session_last_message[last_session] = [last_message]
        return True
    else:
        # 已经存在的窗口，如果这条消息不存在历史里，加进去
        history_message_match_list = [x for x in all_session_last_message[last_session] if last_message[0] == x[0] and last_message[1] == x[1]]
        if len(history_message_match_list) == 0:
            logging.info("Last message list before update: " + str(all_session_last_message[last_session]))
            all_session_last_message[last_session].append(last_message)
            while len(all_session_last_message[last_session]) > 10:
                all_session_last_message[last_session].pop(0)
            logging.info("Session: " + last_session + " last message updated.")
            logging.info("Last message list after update: " + str(all_session_last_message[last_session]))
            return True
        # 如果存在了说明已经处理过了，不用处理
    return False


def init_all_session_threads(session_list):
    for init_each_session in session_list:
        if init_each_session in bypass_session_list:
            continue
        each_thread = GPTRequestThread(init_each_session)
        thread_list[init_each_session] = each_thread
        each_thread.start()


def send_msg_to_wechat_using_clipboard(bot, msg):
    # 用拷贝粘贴可以有换行和空行，看起来很清晰
    start_index = 0
    # 设置1500字的上线，微信电脑版单条微信上限为2500
    while start_index + wechat_one_msg_upper_limit <= len(msg):
        WxUtils.SetClipboard(bot_name_in_reply + msg[start_index:start_index + wechat_one_msg_upper_limit])
        bot.SendClipboard()
        start_index = start_index + wechat_one_msg_upper_limit
    if start_index < len(msg):
        WxUtils.SetClipboard(bot_name_in_reply + msg[start_index:])
        bot.SendClipboard()


def process_prompt_history(prompt_session, prompt):
    if prompt == {}:
        return None
    if prompt_session not in all_session_prompt_history.keys():
        # 聊天历史为空列表
        all_session_prompt_history[prompt_session] = []
        all_session_prompt_history[prompt_session].append(prompt)
    else:
        all_session_prompt_history[prompt_session].append(prompt)


if __name__ == "__main__":
    kun_zai_bot = WeChat()
    # 初始化所有聊天窗口的线程
    init_all_session_threads(kun_zai_bot.GetSessionList())

    # 停不下来
    while True:
        # 每次
        # 遍历所有聊天窗口
        for each_session in kun_zai_bot.GetSessionList():
            if each_session in bypass_session_list:
                continue
            # 选定当前聊天窗口
            kun_zai_bot.ChatWith(each_session)
            # 获取最后X条消息
            cur_session_X_last_message = kun_zai_bot.GetAllMessage[-num_message_history_to_check-1:]
            for each_last_message in cur_session_X_last_message:
                if process_last_message(each_session, each_last_message):
                    # 消息有变化时，检查是否满足发送给gpt的条件。
                    if handle_msg(each_last_message):
                        # 如果满足，检查线程是否已经释放，如果释放，初始化
                        if each_session not in thread_list.keys():
                            new_thread = GPTRequestThread(each_session)
                            thread_list[each_session] = new_thread
                            new_thread.start()
                        # 添加新消息到处理队列末尾
                        logging.info("Session: " + each_session + " Adding new question to queue")
                        logging.info("Request queue before adding: " + str(session_request_queue[each_session]))
                        session_request_queue[each_session].append([each_last_message[1], None, False])
                        logging.info("Request queue after adding: " + str(session_request_queue[each_session]))
                    else:
                        if '重置' in each_last_message[1]:
                            if each_session not in all_session_prompt_history.keys():
                                # 聊天历史初始化为空列表
                                all_session_prompt_history[each_session] = []
                            else:
                                # 重置列表
                                all_session_prompt_history[each_session].clear()

            if each_session in session_request_queue.keys() and len(session_request_queue[each_session]) != 0:
                for each_query_in_session in [x for x in session_request_queue[each_session] if not x[2]]:
                    # gpt处理过且尚未发送
                    if each_query_in_session[1] is not None:
                        # 遍历这个会话队列所有的gpt消息，如果已经获取到了，检查是否已经发送过给会话，确认是否需要回复给这个聊天窗口
                        reply = each_query_in_session[1]
                        if reply != "":
                            cur_prompt = {"role": "assistant", "content": reply}
                            # 将用户问题添加到prompt history
                            user_input = each_query_in_session[0].replace(bot_name, '').strip()
                            user_input_prompt = {"role": "user", "content": user_input}
                            process_prompt_history(each_session, user_input_prompt)
                            # 添加gpt回复添加到prompt history
                            process_prompt_history(each_session, cur_prompt)

                            logging.info("Sending reply to session: " + each_session + ": " + reply)
                            logging.info("Request queue before sending: " + str(session_request_queue[each_session]))

                            # 回复gpt答复到当前会话
                            kun_zai_bot.ChatWith(each_session)
                            # time.sleep(0.1)
                            send_msg_to_wechat_using_clipboard(kun_zai_bot, reply)

                            logging.info("Reply sent to session: " + each_session + ": " + reply)
                            # print("\n回复给 " + each_session + "\n问题：" + each_query_in_session[0] + "\n回答：" + each_query_in_session[1])
                            # 回复完后标记这个请求为已发送
                            each_query_in_session[2] = True
                            logging.info("Request queue after sending: " + str(session_request_queue[each_session]))
                            # 如果prompt history超过 条，清空history，重置
                            if len(all_session_prompt_history[each_session]) >= max_token_per_session:
                                all_session_prompt_history[each_session].clear()
                                reset_reply = bot_name_in_reply + ' 对话已达到' + str(max_token_per_session) + '句，重置对话'
                                kun_zai_bot.SendMsg(reset_reply)
                        else:
                            # 回复消息无效，标记这个请求为已发送
                            each_query_in_session[2] = True
                            logging.info("Invalid reply not sent to session: " + each_session + ": " + reply)
                            logging.info("Request queue after not sending: " + str(session_request_queue[each_session]))

        # time.sleep(0.1)
