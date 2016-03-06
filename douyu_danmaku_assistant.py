# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup

import socket
import struct
import hashlib
import threading
import urllib
import urllib2
import json
import uuid
import time
import sys
import re

__author__ = 'jingqiwang'

reload(sys)
sys.setdefaultencoding('utf-8')


def welcome():
    def filter_tag(tag):
        return tag.name == 'a' and tag.has_attr('href') and tag.has_attr('title') and tag.get('href').count('/') == 1 and 'directory' not in tag.get('href') and len(tag.get('href')) > 1

    rooms = []
    url = 'http://www.douyutv.com/directory/all'
    request = urllib2.Request(url)
    response = urllib2.urlopen(request)
    page = response.read()
    soup = BeautifulSoup(page, 'html.parser')
    cnt = 1
    for item in soup.find_all(filter_tag):
        roomid = item['href'][1:]
        title = item['title']
        category = item.find_all('span', class_='tag ellipsis')[0].text
        ownername = item.find_all('span', class_='dy-name ellipsis fl')[0].text
        rooms.append({'id': cnt, 'rid': roomid, 'title': title, 'oname': ownername, 'cate': category})
        print '\033[1m%s. 房间号: %s, 房间名: %s, 主播:\033[0m \033[1;31m%s\033[0m, \033[1m分类: %s\033[0m' % (cnt, roomid, title, ownername, category)
        print '-' * 100
        cnt += 1
    return cnt, rooms


def get_room_info(cnt, rooms):
    while True:
        rid = raw_input(u'\033[1m请输入房间号或序号: \033[0m')
        if rid in ('exit', 'quit'):
            sys.exit()
        elif rid.isdigit() and 0 < int(rid) <= cnt - 1:
            rid = rooms[int(rid) - 1]['rid']

        url = 'http://www.douyutv.com/' + rid
        try:
            page = urllib.urlopen(url).read()
            room_info = re.search('var \$ROOM = (.+);', page).group(1)
            auth_servers = re.search('\"server_config\":\"(.+)\",\"', page).group(1)
            auth_servers = urllib.unquote_plus(auth_servers)
            auth_servers = json.loads(auth_servers)
            # auth_host, auth_port = auth_servers[0]['ip'], auth_servers[0]['port']
            room_info = json.loads(room_info)
            rid = room_info['room_id']
            rname = room_info['room_name']
            oname = room_info['owner_name']
            category = room_info['cate_name']
            return auth_servers, rid, rname, oname, category
        except:
            print u'\033[1;31m[错误]请输入正确的房间号\033[0m'


class DouyuDanmakuClient:
    def __init__(self, auth_server, rid, rname, oname, category):
        # self.auth_host = auth_host
        # self.auth_port = auth_port
        self.auth_server = auth_server
        self.danmaku_host = '111.161.35.131'
        self.danmaku_port = 8601
        self.rid = rid
        self.gid = None
        self.rt = None
        self.vk = None
        self.username = None
        self.rname = rname
        self.oname = oname
        self.devid = None
        self.catagory = category
        self.danmaku_auth_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.danmaku_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.danmaku_auth_socket.connect((self.auth_server['ip'], int(self.auth_server['port'])))
        self.danmaku_socket.connect((self.danmaku_host, self.danmaku_port))

    def run(self):
        self.login()
        t_keeplive = threading.Thread(target=self.keeplive)
        t_keeplive.setDaemon(True)
        t_keeplive.start()
        self.get_danmaku()

    def login(self):
        self.send_auth_loginreq_msg()
        response = self.danmaku_auth_socket.recv(65535)
        self.username = re.search('\/username@=(.+)\/nickname', response).group(1)
        response = self.danmaku_auth_socket.recv(65535)
        self.gid = re.search('\/gid@=(\d+)\/', response).group(1)
        self.send_qrl_msg()
        response = self.danmaku_auth_socket.recv(65535)
        self.send_auth_keeplive_msg()
        # response = self.danmaku_auth_socket.recv(65535)

    def get_danmaku(self):
        self.send_loginreq_msg()
        response = self.danmaku_socket.recv(65535)
        self.send_joingroup_msg()
        # response = self.danmaku_socket.recv(65535)
        while True:
            response = self.danmaku_socket.recv(65535)
            try:
                dtype = re.search('type@=(.+?)\/', response).group(1)
            except:
                print '\033[1;31m[错误] 啊哦,出现了未知错误...\033[0m'
                continue
            if dtype == 'error':
                print '\033[1;31m[错误] 啊哦,出现了未知错误...\033[0m'
            elif dtype == 'upgrade':
                nickname = re.search('\/nn@=(.+?)\/', response).group(1)
                level = re.search('\/level@=(.+?)\/', response).group(1)
                print '\033[1;36m[信息]\033[0m \033[1;33m%s\033[0m \033[1m这货悄悄地升到了%s级\033[0m' % (nickname, level)
            elif dtype == 'blackres':
                limittime, administrator, nickname = re.search('\/limittime@=(.+)\/snick@=(.+?)/dnick(.+?)\/', response).groups()
                print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;33m%s\033[0m \033[1m被管理员\033[0m \033[1;31m%s\033[0m \033[1m禁言%s小时\033[0m' % (nickname, administrator, int(limittime) / 3600)
            elif dtype == 'uenter':
                nickname = re.search('\/nn@=(.+?)\/')
                level = re.search('\/level@=(.+?)\/', response).group(1)
                print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m进入房间\033[0m' % (level, nickname)
            elif dtype == 'userenter':
                nickname = re.search('Snick@A=(.+?)@Srg', response).group(1)
                level = re.search('@Slevel@A=(.+?)@', response).group(1)
                print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m进入房间\033[0m' % (level, nickname)
            elif dtype == 'dgb':
                gfid, number, uid, nickname = re.search('\/gfid@=(.+)\/gs@=(.+)\/uid@=(.+)\/nn@=(.+?)\/', response).groups()
                level = re.search('\/level@=(.+?)\/', response).group(1)
                if gfid == '50':
                    try:
                        hit = re.search('\/hits@=(.+)\/', response).group(1)
                        print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m送给主播%s个赞,\033[0m \033[1;31m%s连击\033[0m' % (level, nickname, number, hit)
                    except:
                        print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m送给主播%s个赞\033[0m' % (level, nickname, number)
                else:
                    print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m送给主播%s个鱼丸\033[0m' % (level, nickname, int(number) * 100)
            elif dtype == 'dgn':
                gfid = re.search('\/gfid@=(.+?)\/gs', response).group(1)
                number, hits = re.search('\/gfcnt@=(.+?)\/hits@=(.+?)\/', response).groups()
                nickname = re.search('\/src_ncnm@=(.+?)\/rid', response).group(1)
                level = re.search('\/level@=(.+?)\/', response).group(1)
                if gfid == '50':
                    print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m送给主播%s个鱼丸,\033[0m \033[1;31m%s连击\033[0m' % (level, nickname, int(number) * 100, hits)
                elif gfid == '57':
                    print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m送给主播%s个赞,\033[0m \033[1;31m%s连击\033[0m' % (level, nickname, number, hits)
                elif gfid == '53':
                    print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m送给主播%s个鱼丸,\033[0m \033[1;31m%s连击\033[0m' % (level, nickname, int(number) * 520, hits)
                elif gfid == '52':
                    print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m送给主播%s个666,\033[0m \033[1;31m%s连击\033[0m' % (level, nickname, number, hits)
                else:
                    print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m送给主播%s个不知啥礼物,\033[0m \033[1;31m%s连击\033[0m' % (level, nickname, number, hits)
                    print response
            elif dtype == 'onlinegift':
                nickname = re.search('\/nn@=(.+?)\/ur', response).group(1)
                level = re.search('\/level@=(.+?)\/', response).group(1)
                sil = re.search('\/sil@=(.+?)\/', response).group(1)
                print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m通过在线领鱼丸获得了%s个酬勤专享鱼丸\033[0m' % (level, nickname, sil)
            elif dtype == 'gift_title':
                print response
            elif dtype == 'bc_buy_deserve':
                number, hits = re.search('\/cnt@=(.+?)\/hits@=(.+?)\/', response).groups()
                nickname = re.search('@Snick@A=(.+?)@', response).group(1)
                level = re.search('\/level@=(.+?)\/', response).group(1)
                print '\033[1;36m[信息]\033[0m \033[1m用户\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s\033[0m \033[1m送给主播%s个\033[0m\033[1;31m高级酬勤\033[0m' % (level, nickname, number)
            elif dtype == 'spbc':
                nickname, receiver, giftname, number = re.search('\/sn@=(.+?)\/dn@=(.+)\/gn@=(.+)\/gc@=(.+)\/drid', response).groups()
                print '\033[1;36m[信息]\033[0m \033[1;32m土豪\033[0m %s \033[1m送给主播\033[0m \033[1;33m%s\033[0m \033[1m%s个\033[0m\033[1;31m%s\033[0m' % (nickname, receiver, number, giftname)
            elif dtype == 'ranklist':
                print response
            elif dtype == 'ggbb':
                print response
            elif dtype == 'chatmsg':
                nickname = re.search('\/nn@=(.+?)\/', response).group(1)
                chatmsg = re.search('\/txt@=(.+?)\/', response).group(1)
                level = re.search('\/level@=(.+?)\/', response).group(1)
                print '\033[1;34m[弹幕]\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s:\033[0m \033[1;35m%s\033[0m' % (level, nickname, chatmsg)
            elif dtype == 'chatmessage':
                nickname = re.search('\/snick@=(.+?)\/cd', response).group(1)
                chatmsg = re.search('\/content@=(.+?)\/snick', response).group(1)
                try:
                    level = re.search('\/level@=(.+?)\/', response).group(1)
                    print '\033[1;34m[弹幕]\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s:\033[0m \033[1;35m%s\033[0m' % (level, nickname, chatmsg)
                except:
                    # print response
                    level = re.search('@Slevel@A=(.+?)@', response).group(1)
                    print '\033[1;34m[弹幕]\033[0m \033[1;32m[LV %s]\033[0m \033[1;33m%s:\033[0m \033[1;35m%s\033[0m' % (level, nickname, chatmsg)
            else:
                print '\033[1;31m[错误] 主播有毒,这条消息未能解析\033[0m'
                print response

    def send_joingroup_msg(self):
        data = 'type@=joingroup/rid@=%s/gid@=%s/' % (self.rid, self.gid)
        self.danmaku_socket.sendall(self.pack_data(data))

    def send_loginreq_msg(self):
        data = 'type@=loginreq/username@=/password@=/roomid@=%s/' % self.rid
        self.danmaku_socket.sendall(self.pack_data(data))

    def send_auth_loginreq_msg(self):
        self.devid = str(uuid.uuid4()).replace('-', '')
        self.rt = int(time.time())
        self.vk = hashlib.md5(str(self.rt) + '7oE9nPEG9xXV69phU31FYCLUagKeYtsF' + self.devid).hexdigest()
        data = 'type@=loginreq/username@=/password@=/roomid@=%s/ct@=0/devid@=%s/rt@=%s/vk@=%s/ver@=20150929/' % (self.rid, self.devid, self.rt, self.vk)
        self.danmaku_auth_socket.sendall(self.pack_data(data))

    def send_qrl_msg(self):
        data = 'type@=qrl/rid@=%s/' % self.rid
        self.danmaku_auth_socket.sendall(self.pack_data(data))

    def send_auth_keeplive_msg(self):
        data = 'type@=keepalive/tick@=%s/vbw@=0/k@=19beba41da8ac2b4c7895a66cab81e23/' % int(time.time())
        self.danmaku_auth_socket.sendall(self.pack_data(data))

    def send_keeplive_msg(self):
        data = 'type@=keepalive/tick@=%s/' % int(time.time())
        self.danmaku_socket.sendall(self.pack_data(data))

    def keeplive(self):
        while True:
            self.send_auth_keeplive_msg()
            self.send_keeplive_msg()
            time.sleep(60)

    def pack_data(self, data):
        length = {'len': len(data)}
        return struct.pack('12B{0[len]}sB'.format(length), length['len'] + 9, 0x00, 0x00, 0x00, length['len'] + 9, 0x00, 0x00, 0x00, 0xb1, 0x02, 0x00, 0x00, data, 0x00)


if __name__ == '__main__':
    rnumber, rooms = welcome()
    # room_url = 'http://www.douyutv.com/' + rid
    auth_servers, rid, rname, oname, category = get_room_info(rnumber, rooms)
    client = DouyuDanmakuClient(auth_servers[0], rid, rname, oname, category)
    client.run()