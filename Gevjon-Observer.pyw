# -*- coding: utf-8 -*-

from threading import Thread
from urllib.request import urlopen,Request
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
import webbrowser

### config start ###
AUTO_UPDATE = True
MAX_RETRY = 3
PIPE_NAME = r"\\.\pipe\GevjonCore"
CARDS_DB_FILE = "cards.json"
CORE_PATH = "core"
LOG_LEVEL = logging.INFO
LOG_PATH = "log.txt"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
PRO_URL = "https://github.com/RyoLee/Gevjon-Observer/releases/latest"
VERSION_URL = "https://ghproxy.com/https://raw.githubusercontent.com/RyoLee/Gevjon-Observer/PY-MR/version.txt"
USER_COUNT_URL = "https://hits.dwyl.com/RyoLee/Gevjon.svg"
### config end ###

# init logger & global params
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
oppo_addr = None
sleep_time = 0.1


class Version:
    """
    version format MAJOR.MINOR.PATCH
    """

    def __init__(self, ver_str):
        if isinstance(ver_str, str):
            self.Major, self.Minor, self.Patch = map(int, ver_str.split("."))

    def __repr__(self):
        return "{}.{}.{}".format(self.Major, self.Minor, self.Patch)

    def __eq__(self, other):
        return (
            self.Major == other.Major
            and self.Minor == other.Minor
            and self.Patch == other.Patch
        )

    def __hash__(self):
        hash(str(self))

    def __lt__(self, other):
        if other.Major != self.Major:
            return self.Major < other.Major
        elif other.Minor != self.Minor:
            return self.Minor < other.Minor
        else:
            return self.Patch < other.Patch

    def __gt__(self, other):
        if other.Major != self.Major:
            return self.Major > other.Major
        elif other.Minor != self.Minor:
            return self.Minor > other.Minor
        else:
            return self.Patch > other.Patch


@atexit.register
def close_ui():
    """
    close Gevjon when observer crash
    """
    if is_admin():
        logger.info("quit observer")
        logger.info("closing Gevjson")
        os.popen("taskkill /f /im Gevjon.exe")


def send_to_pipe(msg: str):
    """
    send card data to Gevjon by namedpipe
    """
    file_handle = win32file.CreateFile(
        PIPE_NAME,
        win32file.GENERIC_READ | win32file.GENERIC_WRITE,
        win32file.FILE_SHARE_WRITE,
        None,
        win32file.OPEN_EXISTING,
        0,
        None,
    )
    try:
        win32file.WriteFile(file_handle, str.encode(msg))
    except Exception as ex:
        logger.warning(ex)
    finally:
        try:
            win32file.CloseHandle(file_handle)
        except Exception as e:
            logger.warning(e)


def read_longlongs(pm, base, offsets):
    """
    read memory
    """
    value = pm.read_longlong(base)
    for offset in offsets:
        value = pm.read_longlong(value + offset)
    return value


def get_cid(type: int):
    """
    search card id
    """
    global pm
    global deck_addr
    global duel_addr
    global oppo_addr
    while type == 1:
        try:
            deck_pointer_value = (
                read_longlongs(pm, deck_addr, [0xB8, 0x0, 0xF8, 0x1E0]) + 0x2C
            )
            deck_cid = pm.read_int(deck_pointer_value)
            return deck_cid
        except:
            return 0
    while type == 2:
        try:
            duel_pointer_value = read_longlongs(pm, duel_addr, [0xB8, 0x10]) + 0x4C
            duel_cid = pm.read_int(duel_pointer_value)
            return duel_cid
        except:
            return 0
    while type == 3:
        try:
            oppo_pointer_value = (
                read_longlongs(pm, oppo_addr, [0xB8, 0x0, 0xF8, 0x138]) + 0x2C
            )
            oppo_cid = pm.read_int(oppo_pointer_value)
            return oppo_cid
        except Exception:
            return 0


def valid_cid(cid: int):
    """
    check cid by range
    """
    if cid > 4000 and cid < 20000:
        return True
    else:
        return False


def translate():
    """
    search cid
    """
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


def print_card(cid: int):
    """
    format description
    """
    if valid_cid(cid):
        try:
            card_t = cards_db[str(cid)]
            msg = {}
            msg["mode"] = "issued"
            msg["data"] = json.dumps(card_t, ensure_ascii=False)
            send_to_pipe(json.dumps(msg, ensure_ascii=False))
        except Exception as ex:
            logger.warning(ex)
    else:
        return 0


def translate_check_thread():
    """
    check loop
    """
    global sleep_time
    while True:
        translate()
        if not check_if_process_running("Gevjon.exe"):
            sys.exit()
        time.sleep(sleep_time)


def get_baseAddress():
    """
    find base address
    """
    global pm
    global baseAddress
    global deck_addr
    global duel_addr
    global oppo_addr
    pm = pymem.Pymem("masterduel.exe")
    logger.info("Process id: %s" % pm.process_id)
    baseAddress = pymem.process.module_from_name(
        pm.process_handle, "GameAssembly.dll"
    ).lpBaseOfDll
    logger.info("address found!")
    deck_addr = baseAddress + int("0x01E99C18", base=16)
    duel_addr = baseAddress + int("0x01DBDC88", base=16)
    oppo_addr = baseAddress + int("0x01E99C18", base=16)


def is_admin():
    """
    check privilege
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def uac_reload():
    """
    start Gevjon & restart by admin
    """
    if not is_admin():
        logger.info(
            "current user is not admin,start Gevjon and restart observer as admin user"
        )
        stdout = os.popen("cd " + CORE_PATH + " && start Gevjon.exe ")
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
        sys.exit()


def load_db():
    """
    load data
    """
    global cards_db
    try:
        with open(CORE_PATH + "/" + CARDS_DB_FILE, "r", encoding="UTF-8") as f:
            cards_db = json.load(f)
    except Exception as ex:
        logger.warning(ex)


def check_if_process_running(process_name):
    """
    check if there is any running process that contains the given name process name.(full name)
    """
    # iterate over the all the running process
    for proc in psutil.process_iter():
        try:
            # check if process name is the given name string.
            if process_name.lower() == proc.name().lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False


def check_update():
    """
    check update
    """
    try:
        with open("version.txt", "r", encoding="UTF-8") as f:
            cur_version = f.read()
            retry = 0
            while MAX_RETRY > retry:
                try:
                    headers = {'User-Agent':'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:23.0) Gecko/20100101 Firefox/23.0'}
                    req = Request(url=VERSION_URL, headers=headers)
                    tar_version = urlopen(req).read().decode("utf-8")
                    # fmt: off
                    logger.info("checking version...current[" + cur_version + "]->latest[" + tar_version + "]")
                    # fmt: on
                    if Version(tar_version) > Version(cur_version):
                        if 6 == ctypes.windll.user32.MessageBoxW(
                            0,
                            "New version:\t" + tar_version + "\nUpdate now?",
                            "New version found",
                            0x04 | 0x40,
                        ):
                            webbrowser.open_new_tab(PRO_URL)
                            req = Request(url=USER_COUNT_URL, headers=headers)
                            urlopen(req).read()
                            exit(0)
                        else:
                            return
                    else:
                        return
                except Exception as ex:
                    retry += 1
                    logger.warning(ex)
    except Exception as ex:
        logger.warning(ex)


def main():
    try:
        get_baseAddress()
    except Exception as ex:
        logger.warning(ex)
    load_db()
    p = Thread(target=translate_check_thread)
    p.start()
    p.join()


if __name__ == "__main__":
    if not is_admin() and AUTO_UPDATE:
        check_update()
    uac_reload()
    main()
