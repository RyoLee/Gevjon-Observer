# -*- coding: utf-8 -*-

import os
from threading import Thread
import pymem
import keyboard
import time
import json
import win32gui
import win32con
import win32file
import os
import ctypes, sys
import atexit 


PIPE_NAME = r'\\.\pipe\GevjonCore'

#数据文件
cards_db_path = 'cards.json'
#暂停快捷键
pause_hotkey = 'ctrl+p'
#退出快捷键
exit_hotkey = 'ctrl+q'
#切换模式快捷键
switch_hotkey = 'ctrl+s'
#核心路径
core_path = 'core'

cid_temp = 0
cid_temp_duel = 0
cid_temp_deck = 0
cid_temp_oppo = 0
cid_show_gui = 0
pause = False
process_exit = False
baseAddress = None
pm = {}
deck_addr = None
duel_addr = None
oppo_addr = None
sleep_time = 0.1
  
@atexit.register 
def closeUI(): 
    if is_admin():
        os.system("taskkill /f /im Gevjon.exe")

def send_to_pipe(msg: str):
    file_handle = win32file.CreateFile(PIPE_NAME,
                                       win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                                       win32file.FILE_SHARE_WRITE, None,
                                       win32file.OPEN_EXISTING, 0, None)
    try:
        win32file.WriteFile(file_handle, str.encode(msg))
    finally:
        try:
            win32file.CloseHandle(file_handle)
        except:
            pass

# 清理终端
def cls():
    os.system("cls" if os.name == "nt" else "clear")


def read_longlongs(pm, base, offsets):
    value = pm.read_longlong(base)
    for offset in offsets:
        value = pm.read_longlong(value + offset)
    return value


def get_cid(type: int):
    global pm
    global deck_addr
    global duel_addr
    global oppo_addr
    while type == 1:
        try:
            deck_pointer_value = (
                read_longlongs(pm, deck_addr, [0xB8, 0x0, 0xF8, 0x1D8]) + 0x20
            )
            deck_cid = pm.read_int(deck_pointer_value)
            return deck_cid
        except:
            return 0
    while type == 2:
        try:
            duel_pointer_value = read_longlongs(pm, duel_addr, [0xB8, 0x0]) + 0x44
            duel_cid = pm.read_int(duel_pointer_value)
            return duel_cid
        except:
            return 0
    while type == 3:
        try:
            oppo_pointer_value = (
                read_longlongs(pm, oppo_addr, [0xB8, 0x0, 0xF8, 0x140]) + 0x20
            )
            oppo_cid = pm.read_int(oppo_pointer_value)
            return oppo_cid
        except:
            return 0


def valid_cid(cid: int):
    if cid > 4000 and cid < 20000:
        return True
    else:
        return False


def translate():
    global cid_temp_duel
    global cid_temp_deck
    global cid_temp_oppo
    global cid_show_gui
    global baseAddress
    if baseAddress is None:
        try:
            get_baseAddress()
        except:
            print("地址没找到，不执行检测")
            return
        # print("翻译卡组卡片")
    cid_deck = get_cid(1)
    cid_duel = get_cid(2)
    cid_oppo = get_cid(3)
    cid_update = False

    if valid_cid(cid_oppo) and cid_oppo != cid_temp_oppo:
        cid_temp_oppo = cid_oppo
        cid_update = True
        cid_show_gui = cid_oppo
    if valid_cid(cid_deck) and cid_deck != cid_temp_deck:
        cid_temp_deck = cid_deck
        cid_update = True
        cid_show_gui = cid_deck
    if valid_cid(cid_duel) and cid_duel != cid_temp_duel:
        cid_temp_duel = cid_duel
        cid_update = True
        cid_show_gui = cid_duel
    if cid_update:
        cls()
        get_at = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        print(f"检测时间:{get_at}")
        print("-----------------------------------")
        print_card(cid_show_gui)
        print("-----------------------------------")
        print(f"{switch_hotkey}开启检测,{pause_hotkey}暂停检测,{exit_hotkey}退出程序\n")
def print_card(cid: int):
    if valid_cid(cid):
        try:
            card_t = cards_db[str(cid)]
            msg ={}
            msg["id"] = card_t['id']
            msg["name"] = card_t['cn_name']
            msg["desc"] = '【'+card_t['en_name']+'】'+'\n'
            +'【'+card_t['jp_name']+'】'+'\n'
            +'【'+card_t['cn_name']+'】'+'\n\n'
            + card_t['text']['types']+'\n\n'
            if card_t["text"]["pdesc"]:
                msg["desc"]+=card_t['text']['pdesc']+'\n\n'
            msg["desc"]+=card_t['text']['desc']
            msg["mode"] = "issued"
            send_to_pipe(json.dumps(msg,ensure_ascii=False))
        except:
            print(f"数据库中未查到该卡,cid:{cid}，如果是新卡请提交issue。如果是token衍生物请忽略。")
    else:
        return 0


def translate_check_thread():
    global pause
    global process_exit
    global sleep_time
    while not process_exit:
        if pause:
            cls()
            print("暂停检测")
            print(f"{switch_hotkey}开启检测,{pause_hotkey}暂停检测,{exit_hotkey}退出程序\n")
        else:
            translate()
        time.sleep(sleep_time)
    print("程序结束")


def status_change(switch: bool, need_pause: bool, exit: bool):
    global pause
    global process_exit
    process_exit = exit
    pause = need_pause
    if switch:
        print("已开启检测，请点击一张卡片")


def get_baseAddress():
    global pm
    global baseAddress
    global deck_addr
    global duel_addr
    global oppo_addr
    pm = pymem.Pymem("masterduel.exe")
    print("Process id: %s" % pm.process_id)
    baseAddress = pymem.process.module_from_name(
        pm.process_handle, "GameAssembly.dll"
    ).lpBaseOfDll
    print("成功找到模块")
    # deck 组卡界面 duel 决斗界面 oppo 回放
    deck_addr = baseAddress + int("0x01CCD278", base=16)
    duel_addr = baseAddress + int("0x01cb2b90", base=16)
    oppo_addr = baseAddress + int("0x01CCD278", base=16)


# UAC判断
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


# UAC重开
def uac_reload():
    if not is_admin():
        stdout=os.popen('cd '+core_path+ ' && start Gevjon.exe ')
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()


# 加载配置文件
def config_load():
    global cards_db
    # 加载卡片文本
    try:
        with open(cards_db_path, "rb") as f:
            cards_db = json.load(f)
    except:
        print(f"未找到{cards_db_path},请下载后放在同一目录")
def main():
    uac_reload()
    # 加载游戏
    try:
        get_baseAddress()
    except:
        print("未找到地址，可能是游戏未启动 或 没有使用管理员权限运行MDT")
    config_load()
    keyboard.add_hotkey(switch_hotkey, status_change, args=(True, False, False))
    keyboard.add_hotkey(exit_hotkey, status_change, args=(False, False, True))
    keyboard.add_hotkey(pause_hotkey, status_change, args=(False, True, False))
    p = Thread(target=translate_check_thread)
    p.start()
    p.join()
if __name__ == "__main__":
    main()