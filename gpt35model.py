from wechatfrontend import *
import sys
from stablediffusionmodule import *
from wechatbackend import *


if __name__ == "__main__":
    args = sys.argv
    if len(args) > 1:
        judge_if_server_side = args[1]

        if judge_if_server_side == "Client":
            if len(args) == 3:
                if args[2] == "Backend":
                    start_gpt_bot_using_we_chat_backend()
                elif args[2] == "Frontend":
                    # WeChat client side frontend method
                    start_gpt_bot_using_we_chat_frontend()
                else:
                    exit("Invalid argument")
            else:
                # WeChat client side frontend method, default with no parameter
                start_gpt_bot_using_we_chat_frontend()
        elif judge_if_server_side == "Server":
            # Stable Diffusion Server side
            run_stable_diffusion_queue()
    else:
        # WeChat client side frontend method, default with no parameter
        # start_gpt_bot_using_we_chat_frontend()
        run_stable_diffusion_queue()
