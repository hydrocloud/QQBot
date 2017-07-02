#!/usr/bin/env python3

import sys
import json
import os
import threading
import time
import requests
import json
import pymongo

with open(sys.argv[1]) as f:
    cfg = json.loads(f.read())

db = pymongo.MongoClient("127.0.0.1", 27017).HydroCloud_QQBot

from cqsdk import CQBot, CQAt, CQImage, FriendAdd, RcvdPrivateMessage, RcvdGroupMessage, SendPrivateMessage, SendGroupMessage, GroupBan

qqbot = CQBot(11235)

app_backend_token = "null"

watched_group_messages = []

def get_service_token():
    r = requests.post("https://oneidentity.me/services/api/get_token", data = {
        "serviceId": cfg["service_id"],
        "secretKey": cfg["secret_key"]
    }).json()
    return r["token"]

def app_backend_request(p, data):
    global app_backend_token
    data["token"] = app_backend_token
    r = requests.post("https://app.hydrocloud.net" + p, data = data).json()
    if r["msg"] == "Invalid token":
        r = requests.post("https://app.hydrocloud.net/api/qqbot/get_session", data = {
            "token": get_service_token()
        }).json()
        app_backend_token = r["token"]
        data["token"] = app_backend_token
        r = requests.post("https://app.hydrocloud.net" + p, data = data).json()
    return r

@qqbot.listener((RcvdGroupMessage, RcvdPrivateMessage))
def on_message(message):
    if isinstance(message, RcvdGroupMessage):
        handle_group_message(message)
    elif isinstance(message, RcvdPrivateMessage):
        handle_private_message(message)

def handle_group_message(msg):
    text = msg.text
    qq = msg.qq
    group = msg.group
    current_time = int(time.time() * 1000)

    global watched_group_messages

    parts = text.split(" ")
    if parts[0] == "/subscribe" or parts[0] == "/unsubscribe":
        try:
            subscribe_type = parts[1]
            op = None

            if subscribe_type == "from":
                from_qq = parts[2]
                op = {
                    "qq": qq,
                    "from_group": group,
                    "type": "from",
                    "from_qq": from_qq
                }
            elif subscribe_type == "keyword":
                kw = parts[2]
                op = {
                    "qq": qq,
                    "from_group": group,
                    "type": "keyword",
                    "keyword": kw
                }
            else:
                qqbot.send(SendGroupMessage(group = group, text = "未知的订阅类型。"))
                return

            current = db.group_subscriptions.find_one(op)

            if parts[0] == "/subscribe":
                if current != None:
                    qqbot.send(SendGroupMessage(group = group, text = "消息订阅记录已存在。"))
                else:
                    db.group_subscriptions.insert_one(op)
                    qqbot.send(SendGroupMessage(group = group, text = "订阅成功。"))
            else:
                if current == None:
                    qqbot.send(SendGroupMessage(group = group, text = "消息订阅记录不存在。"))
                else:
                    db.group_subscriptions.delete_many(op)
                    qqbot.send(SendGroupMessage(group = group, text = "取消订阅成功。"))

        except Exception as e:
            print(e)
            qqbot.send(SendGroupMessage(group = group, text = "订阅失败。"))
    else:
        for ss in db.group_subscriptions.find({ "type": "from", "from_group": group, "from_qq": qq }):
            watched_group_messages.append({
                "qq": ss["qq"],
                "from_group": group,
                "from_qq": qq,
                "content": text,
                "create_time": current_time
            })
        for ss in db.group_subscriptions.find({ "type": "keyword", "from_group": group }):
            if ss["keyword"] in text:
                watched_group_messages.append({
                    "qq": ss["qq"],
                    "from_group": group,
                    "from_qq": qq,
                    "content": text,
                    "create_time": current_time
                })

def handle_private_message(msg):
    text = msg.text
    qq = msg.qq
    current_time = int(time.time() * 1000)

    parts = text.split(" ")

    if parts[0] == "/connect":
        username = parts[1]
        req_id = parts[2]
        r = app_backend_request("/api/qqbot/verify_user", data = {
            "username": username,
            "request_id": req_id,
            "qq": qq
        })
        print(r)
        if r["msg"] != "OK":
            qqbot.send(SendPrivateMessage(qq = qq, text = r["msg"]))
        else:
            qqbot.send(SendPrivateMessage(qq = qq, text = "关联成功。"))

def update_watched_group_messages():
    global watched_group_messages
    ms = watched_group_messages
    watched_group_messages = []

    if len(ms) > 0:
        r = app_backend_request("/api/qqbot/add_user_watched_group_messages", {
            "messages": json.dumps(ms)
        })
        print(r)

if __name__ == '__main__':
    try:
        qqbot.start()
        while True:
            try:
                update_watched_group_messages()
            except Exception as e:
                print(e)
            time.sleep(10)
    except KeyboardInterrupt:
        pass
