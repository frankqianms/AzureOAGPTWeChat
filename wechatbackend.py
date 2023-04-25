import random
import sys
import threading
import time
import xml
import openai
from envconfig import *
import ntchat


SELF_WXID = ""
session_request_queue = {}
# 给队列加锁，防止三个线程同时修改队列
session_request_queue_lock = threading.Lock()
all_session_prompt_history = {}

# 存储生成的线程列表
thread_list = {}


def should_reply_message(message):
    msg_data = message["data"]
    # @的人列表
    at_list = msg_data['at_user_list']
    # 消息内容
    msg_content = msg_data['msg']

    if SELF_WXID in at_list:
        return True
    else:
        if msg_content.startswith(bot_wechat_id):
            return True

    return False


def remove_hint_from_message_start(msg_content):
    return msg_content[len(bot_wechat_id):] if msg_content.startswith(bot_wechat_id) else msg_content


class GPTRequestThread(threading.Thread):
    def __init__(self, chat_id):
        threading.Thread.__init__(self)
        self.thread_id = id
        self.idle_time = 0
        self.name = chat_id

    def send_request_to_gpt(self, prompt, prompt_history):
        # Send a completion call to generate an answer
        system_prompt = '你是一个世界上最强大的人工智能，你可以帮助任何人找到需要的任何信息，你的名字是' + bot_name
        message_to_send = [{"role": "system",
                            "content": system_prompt}] + prompt_history
        message_to_send.append(prompt)
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
            console_log("Thread: " + self.name +
                  " has error with Azure OpenAI API call: " + str(ex))
            logging.error(ex)
            if openai.api_key == key1:
                openai.api_key = key2
                openai.api_base = api_base2
            else:
                openai.api_key = key1
                openai.api_base = api_base2
            logging.info("Thread: " + self.name + " Switching to backup key success")
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
            # 处理队列中所有消息
            if len(session_request_queue[self.name]) != 0:
                # 防止监听新消息在线程for loop中扩大队列
                cur_queue_len = len(session_request_queue[self.name])
                for each_request_index in range(cur_queue_len):
                    each_request = session_request_queue[self.name][each_request_index]
                    session_id = each_request['session_id']
                    at_list = each_request['at_list']
                    message = each_request['message']
                    reply = each_request['reply']
                    is_sent = each_request['is_sent']

                    if reply or is_sent:
                        # 处理过的不用管
                        continue

                    # 构造发送给gpt的prompt
                    # 去掉 bot_name开头
                    msg_to_gpt = remove_hint_from_message_start(message)
                    user_prompt = {"role": "user", "content": msg_to_gpt}
                    # 发送给gpt，得到答复
                    try:
                        # logging.info("Before sending Query")
                        logging.info("Thread: " + self.name + ", Query sent to GPT is: " + msg_to_gpt)
                        if self.name not in all_session_prompt_history.keys():
                            all_session_prompt_history[self.name] = []
                        ai_reply = self.send_request_to_gpt(user_prompt, all_session_prompt_history[self.name])

                        # 将回复填入队列中第一个消息的回复里
                        session_request_queue[self.name][each_request_index]['reply'] = ai_reply
                        # console_log("\n会话 " + self.session + " ，问题 " +
                        # each_query[0] + " 获取gpt回答成功\n")
                        logging.info(
                            "Thread: " + self.name + ", After sending Query, Reply stored is: " + ai_reply)
                    except Exception as ex:
                        print(str(datetime.now())[:-4] + str(ex))
                        logging.info("Thread: " + self.name + ", Exception in sending query to gpt.")
                        logging.info("Thread: " + self.name + ", Exception is: " + str(ex))
                    self.idle_time = 0

            self.idle_time = self.idle_time + 1
            time.sleep(0.1)
            # 如果30s左右没有新消息，删掉已发送消息，释放线程
            if self.idle_time >= 300:
                # session_request_queue[self.name] = [d for d in session_request_queue[self.name] if not d['is_sent']]
                break
        thread_list.pop(self.name)
        logging.info(self.name + ", Thread released due to idle for 30 s.")

    def run(self):
        self.my_worker()


def enqueue_request_to_gpt(message):
    msg_data = message["data"]
    # 消息内容
    msg_content = msg_data['msg']
    # 群id（如有）
    room_id = msg_data['room_wxid']
    # 发送人id
    from_wxid = msg_data["from_wxid"]

    with session_request_queue_lock:
        # 群消息流程
        if room_id:
            # 当前群聊第一次进入消息队列
            if room_id not in session_request_queue.keys():
                session_request_queue[room_id] = [{
                    'session_id': room_id,
                    'at_list': [from_wxid],
                    'message': msg_content,
                    'reply': '',
                    'is_sent': False
                }]
            else:
                session_request_queue[room_id].append({
                    'session_id': room_id,
                    'at_list': [from_wxid],
                    'message': msg_content,
                    'reply': '',
                    'is_sent': False
                })
        # 个人消息流程
        else:
            if from_wxid not in session_request_queue.keys():
                session_request_queue[from_wxid] = [{
                    'session_id': from_wxid,
                    'at_list': [],
                    'message': msg_content,
                    'reply': '',
                    'is_sent': False
                }]
            else:
                session_request_queue[from_wxid].append({
                    'session_id': from_wxid,
                    'at_list': [],
                    'message': msg_content,
                    'reply': '',
                    'is_sent': False
                })


def handle_command(wechat_instance: ntchat.WeChat, message):
    msg_data = message["data"]
    # 群id（如有）
    room_id = msg_data['room_wxid']
    from_id = msg_data['from_wxid']
    session_id = room_id if room_id else from_id

    msg = msg_data['msg']
    msg = remove_hint_from_message_start(msg)

    if '重置' in msg:
        clear_history(session_id)
        wechat_instance.send_text(to_wxid=session_id, content="对话已重置")


def handle_message(session_id, message):
    # 添加问题到队列
    enqueue_request_to_gpt(message)
    # 查看线程是否在运行
    if session_id not in thread_list.keys():
        cur_thread = GPTRequestThread(session_id)
        thread_list[session_id] = cur_thread
        cur_thread.start()


def is_command(message):
    msg_data = message["data"]
    msg = msg_data['msg']
    msg = remove_hint_from_message_start(msg)
    if '重置' in msg:
        return True
    return False


def handle_group_chat_message(wechat_instance: ntchat.WeChat, message):
    msg_data = message["data"]
    # 群id（如有）
    room_id = msg_data['room_wxid']

    # 非群消息流程退出
    if not room_id:
        return None

    # 只处理提示词开头或者@我自己的消息
    if should_reply_message(message):
        # 处理特殊命令
        if is_command(message):
            handle_command(wechat_instance, message)
        else:
            handle_message(room_id, message)


def handle_personal_chat_message(wechat_instance: ntchat.WeChat, message):
    msg_data = message["data"]
    # 群id（如有）
    room_id = msg_data['room_wxid']
    # 发送人id
    from_wxid = msg_data["from_wxid"]

    # 非个人消息流程退出
    if room_id:
        return None

    # 只处理提示词开头或者@我自己的消息
    if should_reply_message(message):
        if is_command(message):
            handle_command(wechat_instance, message)
        else:
            handle_message(from_wxid, message)


def is_session_request_queue_empty():
    session_request_queue_copy = session_request_queue.copy()
    for each_key in session_request_queue_copy.keys():
        if session_request_queue_copy[each_key]:
            return False
    return True


def process_prompt_history(prompt_session, prompt):
    if prompt == {}:
        return None
    if prompt_session not in all_session_prompt_history.keys():
        # 聊天历史为空列表
        all_session_prompt_history[prompt_session] = []
        all_session_prompt_history[prompt_session].append(prompt)
    else:
        all_session_prompt_history[prompt_session].append(prompt)


def enqueue_history(each_request):
    session_id = each_request['session_id']
    at_list = each_request['at_list']
    message = each_request['message']
    reply = each_request['reply']

    user_input = remove_hint_from_message_start(message)
    user_input_prompt = {"role": "user", "content": user_input}
    gpt_reply_prompt = {"role": "assistant", "content": reply}
    # 将用户问题添加到prompt history
    process_prompt_history(session_id, user_input_prompt)
    # 添加gpt回复添加到prompt history
    process_prompt_history(session_id, gpt_reply_prompt)
    if len(all_session_prompt_history[session_id]) > max_token_per_session:
        return False
    return True


def clear_history(session_id):
    if session_id not in all_session_prompt_history.keys():
        # 聊天历史为空列表
        all_session_prompt_history[session_id] = []
    else:
        all_session_prompt_history[session_id].clear()


def send_reply_from_processed_queue(wechat_instance: ntchat.WeChat):
    if is_session_request_queue_empty():
        time.sleep(1)
        return None
    # 解决监听消息时会增加dictionary的key的runtime error
    session_request_queue_copy = session_request_queue.copy()
    for each_key in session_request_queue_copy.keys():
        for each_request_index in range(len(session_request_queue_copy[each_key])):
            each_request = session_request_queue[each_key][each_request_index]
            session_id = each_request['session_id']
            at_list = each_request['at_list']
            message = each_request['message']
            reply = each_request['reply']
            is_sent = each_request['is_sent']

            is_group_chat = 'chatroom' in session_id

            if not reply or is_sent:
                # 没有gpt回复或者已经发送的消息不处理
                continue
            else:
                rand_time = random.uniform(1.5, 4.5)
                time.sleep(rand_time)
                if at_list:
                    wechat_instance.send_room_at_msg(to_wxid=session_id, content=reply, at_list=at_list)
                else:
                    wechat_instance.send_text(to_wxid=session_id, content=reply)
                each_request['is_sent'] = True
                if not enqueue_history(each_request):
                    clear_history(session_id)
                    wechat_instance.send_text(to_wxid=session_id, content='对话已达到' + str(max_token_per_session) + '句，重置对话')
        # 如果当前会话线程释放，并且没有更多未处理消息，清理一次队列
        not_sent_requests = [x for x in session_request_queue[each_key] if not x['is_sent']]
        if each_key not in thread_list.keys() and len(not_sent_requests) == 0:
            with session_request_queue_lock:
                session_request_queue[each_key] = [x for x in session_request_queue[each_key] if not x['is_sent']]


def start_gpt_bot_using_we_chat_backend():
    wechat = ntchat.WeChat()

    # 打开pc微信, smart: 是否管理已经登录的微信
    wechat.open(smart=True)

    # 等待登录
    wechat.wait_login()

    # 当前登录的自己的id
    global SELF_WXID
    SELF_WXID = wechat.get_login_info()["wxid"]

    # 注册消息回调
    @wechat.msg_register(ntchat.MT_RECV_FRIEND_MSG)
    def on_recv_text_msg(wechat_instance: ntchat.WeChat, message):
        xml_content = message["data"]["raw_msg"]
        dom = xml.dom.minidom.parseString(xml_content)

        # 从xml取相关参数
        encrypt_username = dom.documentElement.getAttribute("encryptusername")
        ticket = dom.documentElement.getAttribute("ticket")
        scene = dom.documentElement.getAttribute("scene")

        # 自动同意好友申请
        ret = wechat_instance.accept_friend_request(encrypt_username, ticket, int(scene))

        if ret:
            # 通过后向他发条消息
            wechat_instance.send_text(to_wxid=ret["userName"], content="你好!")

    # 注册消息回调
    @wechat.msg_register(ntchat.MT_RECV_TEXT_MSG)
    def on_recv_text_msg(wechat_instance: ntchat.WeChat, message):

        # 消息流
        """
        message: {'data': {'at_user_list': [], 'from_wxid': 'wxid_qsgskpb26kw822', 'is_pc': 0, 'msg': '你好', 'msgid': '5915605810877521354', 'room_wxid': '', 'timestamp': 1682341574, 'to_wxid': 'wxid_rpzz4v3jir2v22', 'wx_type': 1}, 'type': 11046}
        """
        msg_data = message["data"]
        # 群id（如有）
        room_id = msg_data['room_wxid']

        # 群消息流程
        if room_id:
            handle_group_chat_message(wechat_instance, message)
        # 私人消息流程
        else:
            handle_personal_chat_message(wechat_instance, message)

    try:
        while True:
            # 主线程负责发送队列里收到gpt的回复给对应的聊天
            send_reply_from_processed_queue(wechat)

    except KeyboardInterrupt:
        ntchat.exit_()
        sys.exit()
