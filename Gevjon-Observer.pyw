# -*- coding: utf-8 -*-

import os
from threading import Thread
import pymem
import time
import json
import win32file
import os
import ctypes
import sys
import atexit
import logging
import psutil

'''
config
'''
PIPE_NAME = r'\\.\pipe\GevjonCore'
CARDS_DB_PATH = 'cards.json'
CORE_PATH = 'core'
LOG_LEVEL = logging.INFO
LOG_PATH = "log.txt"
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


'''
init logger & global params
'''
logger = logging.getLogger(__name__)
logger.setLevel(level=LOG_LEVEL)
handler = logging.FileHandler(LOG_PATH)
handler.setLevel(LOG_LEVEL)
formatter = logging.Formatter(LOG_FORMAT)
handler.setFormatter(formatter)
logger.addHandler(handler)
cid_temp = 0
cid_temp_duel = 0
cid_temp_deck = 0
cid_temp_oppo = 0
cid_show_gui = 0
baseAddress = None
pm = {}
deck_addr = None
duel_addr = None
replay_addr = None
sleep_time = 0.1


'''
close Gevjon when observer crash
'''
@atexit.register
def close_ui():
    if is_admin():
        logger.info("quit observer")
        logger.info("closing Gevjson")
        os.system("taskkill /f /im Gevjon.exe")


'''
send card data to Gevjon by namedpipe
'''
def send_to_pipe(msg: str):
    file_handle = win32file.CreateFile(PIPE_NAME,
                                       win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                                       win32file.FILE_SHARE_WRITE, None,
                                       win32file.OPEN_EXISTING, 0, None)
    try:
        win32file.WriteFile(file_handle, str.encode(msg))
    except Exception as ex:
        logger.warning(ex)
    finally:
        try:
            win32file.CloseHandle(file_handle)
        except Exception as e:
            logger.warning(e)


'''
read memory
'''
def read_longlongs(pm, base, offsets):
    value = pm.read_longlong(base)
    for offset in offsets:
        value = pm.read_longlong(value + offset)
    return value


'''
search card id
'''
def get_cid(type: int):
    global pm
    global deck_addr
    global duel_addr
    global replay_addr
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
            duel_pointer_value = read_longlongs(
                pm, duel_addr, [0xB8, 0x0]) + 0x44
            duel_cid = pm.read_int(duel_pointer_value)
            return duel_cid
        except:
            return 0
    while type == 3:
        try:
            oppo_pointer_value = (
                read_longlongs(pm, replay_addr, [
                               0xB8, 0x0, 0xF8, 0x140]) + 0x20
            )
            oppo_cid = pm.read_int(oppo_pointer_value)
            return oppo_cid
        except:
            return 0


'''
check cid by range
'''
def valid_cid(cid: int):
    if cid > 4000 and cid < 20000:
        return True
    else:
        return False


'''
search cid
'''
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
            return
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
        print_card(cid_show_gui)


'''
format description
'''
def print_card(cid: int):
    if valid_cid(cid):
        try:
            card_t = cards_db[str(cid)]
            msg = {}
            msg["id"] = str(card_t['id'])
            msg["name"] = card_t['cn_name']
            msg["desc"] = '【'+card_t['en_name']+'】\n' + \
                          '【'+card_t['jp_name']+'】\n' + \
                          '【'+card_t['cn_name']+'】\n\n' + \
                          str(card_t['text']['types'])+'\n\n\n'
            if 'pdesc' in card_t["text"] and "" != card_t["text"]["pdesc"]:
                msg["desc"] += '------------------------\n' + \
                    str(card_t['text']['pdesc']) + \
                    '\n------------------------\n\n\n'
            msg["desc"] += card_t['text']['desc']
            msg["mode"] = "issued"
            send_to_pipe(json.dumps(msg, ensure_ascii=False))
        except Exception as ex:
            logger.warning(ex)
    else:
        return 0


'''
check loop
'''
def translate_check_thread():
    global sleep_time
    while True:
        translate()
        if not check_if_process_running('Gevjon.exe'):
            sys.exit()
        time.sleep(sleep_time)


'''
find base address
'''
def get_baseAddress():
    global pm
    global baseAddress
    global deck_addr
    global duel_addr
    global replay_addr
    pm = pymem.Pymem("masterduel.exe")
    logger.info("Process id: %s" % pm.process_id)
    baseAddress = pymem.process.module_from_name(
        pm.process_handle, "GameAssembly.dll"
    ).lpBaseOfDll
    logger.info("address found!")
    # deck/duel/replay
    deck_addr = baseAddress + int("0x01CCD278", base=16)
    duel_addr = baseAddress + int("0x01cb2b90", base=16)
    replay_addr = baseAddress + int("0x01CCD278", base=16)


'''
check privilege
'''
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


'''
start Gevjon & restart by admin
'''
def uac_reload():
    if not is_admin():
        logger.info(
            "current user is not admin,start Gevjon and restart observer as admin user")
        stdout = os.popen('cd '+CORE_PATH + ' && start Gevjon.exe ')
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        sys.exit()


'''
load data
'''
def load_db():
    global cards_db
    try:
        with open(CARDS_DB_PATH, "r", encoding='UTF-8') as f:
            cards_db = json.load(f)
    except Exception as ex:
        logger.warning(ex)


'''
Check if there is any running process that contains the given name process name.(full name)
'''
def check_if_process_running(process_name):
    # iterate over the all the running process
    for proc in psutil.process_iter():
        try:
            # check if process name is the given name string.
            if process_name.lower() == proc.name().lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


'''
main
'''
def main():
    uac_reload()
    try:
        get_baseAddress()
    except Exception as ex:
        logger.warning(ex)
    load_db()
    p = Thread(target=translate_check_thread)
    p.start()
    p.join()


if __name__ == "__main__":
    main()
