import sys
import ntchat


def start_gpt_bot_using_we_chat_backend():
    wechat = ntchat.WeChat()

    # 打开pc微信, smart: 是否管理已经登录的微信
    wechat.open(smart=True)

    # 等待登录
    wechat.wait_login()
    # 获取联系人列表并输出
    contacts = wechat.get_contacts()

    print("联系人列表: ")
    print(contacts)

    rooms = wechat.get_rooms()
    print("群列表: ")
    print(rooms)


    # 注册消息回调
    @wechat.msg_register(ntchat.MT_RECV_TEXT_MSG)
    def on_recv_text_msg(wechat_instance: ntchat.WeChat, message):
        data = message["data"]
        from_wxid = data["from_wxid"]
        self_wxid = wechat_instance.get_login_info()["wxid"]
        print("message: " + str(message))
        # 判断消息不是自己发的，并回复对方
        if from_wxid != self_wxid:
            wechat_instance.send_text(to_wxid=from_wxid, content=f"你发送的消息是: {data['msg']}")


    try:
        while True:
            pass
    except KeyboardInterrupt:
        ntchat.exit_()
        sys.exit()