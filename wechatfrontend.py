import shutil

from wxauto import *
import time
import threading
from datetime import datetime
import openai
from envconfig import *
import keyboard


bypass_session_list = ['文件传输助手', '腾讯新闻', '订阅号', '微信团队', '微信支付']
bot_name = "堃仔"
bot_name_in_reply = ''  # '[AI]'
# bot_name_in_reply = ''
chat_hint = [bot_name]  # , "[AI]"]
image_hint = bot_name + "生成图片："

# 所有会话的最后num_message_history_to_check条消息
all_session_last_message = {}
# 所有会话的gpt prompt history，session_name为key, [{prompt},..]为value
all_session_prompt_history = {}
# 每个会话一个单独请求队列，先问先答，直到没有消息
session_request_queue = {}

# 存储生成的线程列表
thread_list = {}

# 每个会话查看的最近开始的历史消息条数
num_message_history_to_check = 5
# 每个工作循环遍历的消息个数
session_num_to_check = 4
# 机器人存储的消息历史记录的条数
num_of_message_history_to_store = 10

openai.api_key = key1
openai.api_base = api_base1
openai.api_type = 'azure'
openai.api_version = '2023-03-15-preview'


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
            console_log("Thread: " + self.session +
                  " has error with Azure OpenAI API call: " + str(ex))
            logging.error(ex)
            if openai.api_key == key1:
                openai.api_key = key2
                openai.api_base = api_base2
            else:
                openai.api_key = key1
                openai.api_base = api_base2
            logging.info("Thread: " + self.session + " Switching to backup key success")
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
                        # 去掉 bot_name开头
                        msg_to_gpt = each_query[0][len(bot_name):].strip()
                        # print(str(datetime.now())[:-4] + msg_to_gpt)
                        user_prompt = {"role": "user", "content": msg_to_gpt}
                        # 发送给gpt，得到答复
                        try:
                            # logging.info("Before sending Query")
                            logging.info("Thread: " + self.name + ", Query sent to GPT is: " + msg_to_gpt)
                            ai_reply = self.send_request_to_gpt(user_prompt, all_session_prompt_history[self.session])

                            # 将回复填入队列中第一个消息的回复里
                            each_query[1] = ai_reply
                            # console_log("\n会话 " + self.session + " ，问题 " +
                            # each_query[0] + " 获取gpt回答成功\n")
                            logging.info(
                                "Thread: " + self.name + ", After sending Query, Reply stored is: " + each_query[1])
                        except Exception as ex:
                            print(str(datetime.now())[:-4] + str(ex))
                            logging.info("Thread: " + self.name + ", Exception in sending query to gpt.")
                            logging.info("Thread: " + self.name + ", Exception is: " + str(ex))
                    self.idle_time = 0
            else:
                self.idle_time = self.idle_time + 1
            time.sleep(0.1)
            # 如果1分钟左右没有新消息，释放线程
            if self.idle_time >= 600:
                break
        thread_list.pop(self.session)
        logging.info(self.name + ", Thread released due to idle for 3 minutes.")

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
    :return: True if session has new message
    """
    if last_message is None:
        return False
    # 如果消息是自己发的，跳过
    if last_message[0] == bot_wechat_id:
        return False
    # 忽略系统消息
    if last_message[0] == "SYS":
        return False
    # 如果聊天窗口是新冒出来的，添加到dict
    if last_session not in all_session_last_message.keys():
        # 添加此聊天最后一条消息到列表
        all_session_last_message[last_session] = [last_message]
        return True
    else:
        # 已经存在的窗口，如果这条消息不存在历史里，加进去
        history_message_match_list = [x for x in all_session_last_message[last_session] if
                                      (last_message[0] == x[0] and last_message[1] == x[1])]
        if len(history_message_match_list) == 0:
            logging.info("Session: " + last_session + ", Updating last message")
            logging.info("Session: " + last_session + ", Last message list before update: " + str(
                all_session_last_message[last_session]))
            all_session_last_message[last_session].append(last_message)
            while len(all_session_last_message[last_session]) > num_of_message_history_to_store:
                all_session_last_message[last_session].pop(0)
            logging.info("Session: " + last_session + " last message updated.")
            logging.info("Session: " + last_session + ", Last message list after update: " + str(
                all_session_last_message[last_session]))
            return True
        # 如果存在了说明已经处理过了，不用处理
    return False


def init_all_session_threads(session_lists):
    for init_each_session in session_lists:
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


def detect_and_process_last_message_in_top_has_changed(wechat_bot,
                                                       last_top_session_name, last_top_session_last_message_content):
    """

    :param wechat_bot:
    :param last_top_session_name:
    :param last_top_session_last_message_content:
    :return: True(session changed)/False(session not changed),
    True(session last message changed)/False(session last message not changed),
    last_top_session,last_top_session_last_message
    """
    cur_top_session_name = locate_top_valid_session(wechat_bot)
    if cur_top_session_name == -1:
        return False, False, "", ["", "", ""]
    # noinspection PyBroadException
    try:
        cur_top_current_last_message_content = wechat_bot.GetLastMessage
    except Exception:
        cur_top_current_last_message_content = ["", "", ""]
    if last_top_session_name == cur_top_session_name:
        if cur_top_current_last_message_content[0] == last_top_session_last_message_content[0] \
                and cur_top_current_last_message_content[1] == last_top_session_last_message_content[1]:
            return False, False, last_top_session_name, last_top_session_last_message_content
        else:
            # 如果手动点了一个非顶端窗口，这里可以强行点回去顶端窗口修复bug
            wechat_bot.ChatWith(cur_top_session_name)
            try:
                cur_top_current_last_message_content = wechat_bot.GetLastMessage
            except Exception:
                cur_top_current_last_message_content = ["", "", ""]
            if cur_top_current_last_message_content[0] == last_top_session_last_message_content[0] \
                    and cur_top_current_last_message_content[1] == last_top_session_last_message_content[1]:
                return False, False, last_top_session_name, last_top_session_last_message_content
            # 非手动点非顶端窗口的情况，而是正常顶端窗口消息更新了
            else:
                return False, True, last_top_session_name, cur_top_current_last_message_content
    else:
        return True, True, cur_top_session_name, cur_top_current_last_message_content


def get_chat_history_in_session_and_process(we_chat_bot, each_ses):
    into_working_mode = False
    # 获取最后X条消息
    all_messages = we_chat_bot.GetAllMessage
    if len(all_messages) <= num_message_history_to_check:
        cur_session_x_last_message = all_messages
    else:
        cur_session_x_last_message = we_chat_bot.GetAllMessage[-num_message_history_to_check - 1:]
    for each_last_message in cur_session_x_last_message:
        if process_last_message(each_ses, each_last_message):
            # 消息有变化时，检查是否满足发送给gpt的条件。
            if handle_msg(each_last_message):
                if each_last_message[1].startswith(image_hint):
                    # 图片流程
                    user_prompt = each_last_message[1][len(image_hint):]
                    now = datetime.now()
                    # Format date and time as string
                    dt_string = now.strftime("%Y-%m-%d %H:%M:%S")
                    file_name_to_create = dt_string.replace(":", "-")
                    file_name_to_create = file_name_to_create + ' ' + each_ses + ".txt"
                    file_name_to_create = os.path.join(requests_folder_path, file_name_to_create)
                    with open(file_name_to_create, "w") as file:
                        file.write(user_prompt)
                        file.close()
                else:
                    # 文字流程
                    # 如果满足，检查线程是否已经释放，如果释放，初始化
                    if each_ses not in thread_list.keys():
                        new_thread = GPTRequestThread(each_ses)
                        thread_list[each_ses] = new_thread
                        new_thread.start()

                    # 添加新消息到处理队列末尾
                    logging.info("Session: " + each_ses + ", Adding new question to queue")
                    logging.info("Session: " + each_ses + ", Request queue before adding: " + str(
                        session_request_queue[each_ses]))
                    session_request_queue[each_ses].append([each_last_message[1], None, False])
                    logging.info("Session: " + each_ses + ", Request queue after adding: " + str(
                        session_request_queue[each_ses]))
                into_working_mode = True
            else:
                if each_last_message[1].startswith(tuple(chat_hint)):
                    if '重置' in each_last_message[1]:
                        if each_ses not in all_session_prompt_history.keys():
                            # 聊天历史初始化为空列表
                            all_session_prompt_history[each_ses] = []
                        else:
                            # 重置列表
                            all_session_prompt_history[each_ses].clear()
                            logging.info("Session: " + each_ses + ", session prompt history cleared")
                        reset_reply = bot_name_in_reply + ' 对话已重置'
                        we_chat_bot.SendMsg(reset_reply)
    return into_working_mode


def has_queued_message_in_request_queue():
    for each_q in session_request_queue.keys():
        if len(session_request_queue[each_q]) > 0:
            return True
    return False


def has_unsent_processed_images():
    if not os.listdir(image_output_folder_path):
        return False
    else:
        return True


def has_unprocessed_images():
    if not os.listdir(requests_folder_path):
        return False
    else:
        return True


def image_queue_not_empty():
    return has_unprocessed_images() or has_unsent_processed_images()


def send_processed_image_from_gpt_to_wechat(we_chat_bot, each_ses=None):
    png_files = [file for file in os.listdir(image_output_folder_path) if file.endswith('.png')]
    for image in png_files:
        cur_session = image.split(" ")[0]
        if each_ses:
            if each_ses != cur_session:
                continue

        img_path = os.path.join(image_output_folder_path, image)
        img_path_str = img_path.replace('\\', '/')
        file_size = os.path.getsize(img_path_str)
        if file_size > 10000:  # 10kb以上才是和谐图片，10kb以下都是全黑屏蔽图片
            we_chat_bot.ChatWith(cur_session)
            we_chat_bot.SendFiles(img_path_str)
        else:
            we_chat_bot.ChatWith(cur_session)
            we_chat_bot.SendMsg("图片生成失败")
        now = datetime.now()
        # Format date and time as string
        dt_string = now.strftime("%Y-%m-%d %H:%M:%S")
        file_name_to_create = dt_string.replace(":", "-")
        file_name_to_create = file_name_to_create + " " + image
        shutil.copy2(img_path, image_history_folder_path + '\\' + file_name_to_create)
        os.remove(img_path)


def send_processed_message_from_gpt_to_wechat(we_chat_bot, each_ses):
    # 选定当前聊天窗口
    if each_ses not in session_request_queue.keys() or len(session_request_queue[each_ses]) == 0:
        # 没有消息任务
        return False
    if each_ses in session_request_queue.keys() and len(session_request_queue[each_ses]) != 0:
        for each_query_in_session in [x for x in session_request_queue[each_ses] if not x[2]]:
            # gpt处理过且尚未发送
            if each_query_in_session[1] is not None:
                # 遍历这个会话队列所有的gpt消息，如果已经获取到了，检查是否已经发送过给会话，确认是否需要回复给这个聊天窗口
                reply = each_query_in_session[1]
                if reply != "":
                    cur_prompt = {"role": "assistant", "content": reply}
                    # 将用户问题添加到prompt history
                    user_input = each_query_in_session[0][len(bot_name):].strip()
                    user_input_prompt = {"role": "user", "content": user_input}
                    process_prompt_history(each_ses, user_input_prompt)
                    # 添加gpt回复添加到prompt history
                    process_prompt_history(each_ses, cur_prompt)

                    logging.info("Session: " + each_ses + ", Sending reply to session: " + reply)
                    logging.info("Session: " + each_ses + ", Request queue before sending: " + str(
                        session_request_queue[each_ses]))

                    # 回复gpt答复到当前会话
                    we_chat_bot.ChatWith(each_ses)
                    # time.sleep(0.1)
                    send_msg_to_wechat_using_clipboard(we_chat_bot, reply)

                    logging.info("Session: " + each_ses + ", Reply sent: " + reply)
                    # console_log("\n回复给 " + each_ses + "\n问题：" +
                    # each_query_in_session[0] + "\n回答：" + each_query_in_session[1])
                    # 回复完后标记这个请求为已发送
                    each_query_in_session[2] = True
                    logging.info("Session: " + each_ses + ", Request queue after sending: " + str(
                        session_request_queue[each_ses]))
                    # 如果prompt history超过 max_token_per_session 条，清空history，重置
                    if len(all_session_prompt_history[each_ses]) >= max_token_per_session:
                        all_session_prompt_history[each_ses].clear()
                        reset_reply = bot_name_in_reply + ' 对话已达到' + str(max_token_per_session) + '句，重置对话'
                        we_chat_bot.SendMsg(reset_reply)
                else:
                    # 回复消息无效，标记这个请求为已发送
                    each_query_in_session[2] = True
                    logging.info("Session: " + each_ses + ", Invalid reply not sent to session: " + reply)
                    logging.info("Session: " + each_ses + "Request queue after not sending: " + str(
                        session_request_queue[each_ses]))
    return True


def locate_top_valid_session(we_chat_bot):
    ses_list = we_chat_bot.GetSessionList()
    filtered_session_list = [ss for ss in ses_list if ss not in bypass_session_list]
    if len(filtered_session_list) > 0:
        return filtered_session_list[0]
    else:
        return -1


def start_gpt_bot_using_we_chat_frontend():
    kun_zai_bot = WeChat()
    # 初始化所有聊天窗口的线程
    init_all_session_threads(kun_zai_bot.GetSessionList())
    # 0: working, 1: idle
    state_machine = 1
    console_log("当前进入状态：idle")
    logging.info("初始化完成，当前进入状态：idle")
    # 初始化，待机状态，选中第一个非忽略聊天窗口
    top_session = locate_top_valid_session(kun_zai_bot)

    # 一个真正的聊天窗口都没有
    if top_session == -1:
        last_top_session = ""
        last_top_session_message = ["", "", ""]
    else:
        kun_zai_bot.ChatWith(top_session)
        # 上一个最上面的窗口
        last_top_session = top_session
        # 上一个最上面的窗口的最后消息
        try:
            last_top_session_message = kun_zai_bot.GetLastMessage
        except Exception:
            last_top_session_message = ["", "", ""]

    # 停不下来
    loop_iter = 1
    while loop_iter > 0:
        if loop_iter >= 10000:
            # 防止整数翻转
            loop_iter = 1

        top_has_changed, top_message_has_changed, last_top_session, last_top_session_message = \
            detect_and_process_last_message_in_top_has_changed(kun_zai_bot, last_top_session, last_top_session_message)

        # 每次
        # 遍历所有聊天窗口
        session_list = kun_zai_bot.GetSessionList()
        # 去掉无效聊天
        session_list = [ss for ss in session_list if ss not in bypass_session_list]
        # 工作期流程
        if state_machine == 0:
            # 反向遍历
            # 目标：
            # 1.处理所有消息队列，发送给对应聊天窗口
            # 2.遍历所有消息窗口，有需要加入消息队列
            # 3.处理到顶端窗口，消息未变化，并且消息队列为空，进入idle状态
            # 4.如果消息队列不在遍历的聊天窗口，单独搜索这个窗口发送
            for session_index in range(min(len(session_list), session_num_to_check + 1) - 1, -1, -1):
                each_session = session_list[session_index]
                kun_zai_bot.ChatWith(each_session)
                # 遍历到最上面窗口了
                if session_index == 0:
                    # 最上面窗口未变化
                    if not top_has_changed:
                        # 最上面窗口未变化，最后消息未变化
                        if not top_message_has_changed:
                            pass
                        # 最上面窗口未变，最后消息变化
                        else:
                            # 按情况添加消息到消息队列
                            get_chat_history_in_session_and_process(kun_zai_bot, each_session)
                    # 顶端窗口变化了
                    else:
                        # 按情况添加消息到消息队列
                        get_chat_history_in_session_and_process(kun_zai_bot, each_session)
                # 非顶端窗口
                else:
                    # 按情况添加消息到消息队列
                    get_chat_history_in_session_and_process(kun_zai_bot, each_session)

                # 统一处理发送当前会话GPT回答过，仍未发送的消息
                send_processed_message_from_gpt_to_wechat(kun_zai_bot, each_session)
                # 统一处理发送当前会话图片已生成，未发送的图片
                send_processed_image_from_gpt_to_wechat(kun_zai_bot, each_session)

            pending_processing_sessions = [es for es in session_request_queue.keys() if
                                           len(session_request_queue[es]) != 0]
            str_pending_processing_sessions = [[key, str(sum([1 for item in val_list if not item[2]])) + " 条消息处理中"]
                                               for key, val_list in session_request_queue.items() if len(val_list) > 0]
            if len(str_pending_processing_sessions) > 0:
                console_log("当前状态：working, 处理消息队列中，当前等待消息的聊天有：" + str(
                    str_pending_processing_sessions))
                logging.info("当前状态：working, 处理消息队列中，当前等待消息的聊天有：" + str(
                    str_pending_processing_sessions))

            if has_unsent_processed_images():
                if loop_iter % 2 == 0:
                    console_log("当前状态：working, 发送已处理的图片中")
                    logging.info("当前状态：working, 发送已处理的图片中")

            # 检测是否存在消息队列的会话不在循环遍历的会话中，已经被刷到靠很后面了
            delayed_sessions = [es[0] for es in pending_processing_sessions if es
                                not in session_list[:min(len(session_list), session_num_to_check + 1)]]
            for each_delayed_session in delayed_sessions:
                kun_zai_bot.ChatWith(each_delayed_session)
                get_chat_history_in_session_and_process(kun_zai_bot, each_delayed_session)
                send_processed_message_from_gpt_to_wechat(kun_zai_bot, each_delayed_session)

            if has_unsent_processed_images():
                send_processed_image_from_gpt_to_wechat(kun_zai_bot)

            # 消息队列为空时
            request_queue_empty = not has_queued_message_in_request_queue()
            # 消息和图片队列已经空了，可以直接进入idle了
            if request_queue_empty:
                console_log("当前进入状态：idle")
                state_machine = 1

        # 闲置期，只检查第一个窗口
        elif state_machine == 1:
            if loop_iter % 60 == 0:
                # 30 秒按一次键盘，防止关屏或者休眠
                keyboard.press_and_release('alt + ctrl')
            if top_has_changed:
                kun_zai_bot.ChatWith(last_top_session)
                if top_message_has_changed:
                    # 进入工作状态，添加消息到队列
                    if get_chat_history_in_session_and_process(kun_zai_bot, last_top_session):
                        state_machine = 0
                        console_log("当前进入状态：working，处理消息")
                else:
                    # 应该没有这种情况
                    console_log("错误情况发生")
                    pass
            else:
                if top_message_has_changed:
                    if get_chat_history_in_session_and_process(kun_zai_bot, last_top_session):
                        state_machine = 0
                        console_log("当前进入状态：working，处理消息")
                else:
                    # 如果收到了新的生成的图片，进入working状态
                    if has_unsent_processed_images():
                        state_machine = 0
                        console_log("当前进入状态：working，处理图片")
                        # send_processed_image_from_gpt_to_wechat(kun_zai_bot)
                    else:
                        time.sleep(0.5)

        loop_iter = loop_iter + 1
