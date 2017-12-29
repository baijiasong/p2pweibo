#!/usr/bin/python

import socket
import struct
import threading
import time
import traceback
import requests
import hashlib
import json
import re
import heapq
import time

from twisted.internet import reactor
from kademlia.network import Server

PEER = 'PEER'
END = 'ENDD'
AT = 'ATSB'

class Peer:
    def __init__(self, username):
        self.debug = 0
        self.peers = {}
        self.shutdown = False

        self.handlers = {}
        self.router = None

        self.username = username
        self.__initHash()

        self.allPosts = None
        self.notices = None
        self.fans = None
        self.follows = None
        self.priMessages = None
        self.allUsers = None

        r = self.getKademlia(self.userhash)
        if r.text.startswith('\n<html>') == True:
            self.__signUp()

        self.__fresh()

    def mainpage(self):
        self.__fresh()
        r = {}
        r['username'] = self.username
        r['fans'] = len(self.fans)
        r['follows'] = len(self.follows)
        r['postsnum'] = len(self.allPosts)
        r['posts'] = self.allPosts[ : 10]
        return r

    def userpage(self, username):
        r = {}
        r['username'] = username
        r['fans'] = len(self.fans)
        r['follows'] = len(self.follows)
        r['postsnum'] = len(self.allPosts)
        r['posts'] = self.allPosts[ : 10]
        return r

    def getKademlia(self, key):
        return requests.get('http://127.0.0.1:1984/' + str(key))

    def postKademlia(self, key, value):
        return requests.post(url='http://127.0.0.1:1984/' + str(key), data=value)

    def __fresh(self):
        self.__getFans()
        self.__getFollows()
        self.__getAllPosts()
        self.__getAllNotices()
        self.__getPriMessages()

    def __initHash(self):
        self.userhash = hashlib.sha256(self.username).hexdigest()
        self.posthash = hashlib.sha256(self.username + 'post').hexdigest()
        self.fanshash = hashlib.sha256(self.username + 'fans').hexdigest()
        self.followhash = hashlib.sha256(self.username + 'follow').hexdigest()
        self.privhash = hashlib.sha256(self.username + 'priv').hexdigest()
        self.noticehash = hashlib.sha256(self.username + 'notice').hexdigest()

    def __signUp(self):
        self.postKademlia(key=self.userhash, value='PublicKey')
        self.postKademlia(key=self.posthash, value='{}')
        self.postKademlia(key=self.fanshash, value='{}')
        self.postKademlia(key=self.followhash, value='{}')
        self.postKademlia(key=self.privhash, value='{}')
        self.postKademlia(key=self.noticehash, value='{}')

    ### ATHash entry format: "ATSB||timestamp||username content"
    def __getAllNotices(self):
        notices = json.loads(str(self.getKademlia(self.noticehash).text))
        q = []
        for rank in notices:
            content = notices[rank]
            noticeType = content[ : 4]
            if noticeType == AT:
                ts = int(content[4 : 14])
                username = content[14 : content.find(' ')]
                content = content[content.find(' ')+1 : ]
                heapq.heappush(q, (ts, [ts, username, content]))
        self.notices = []
        while q:
            item = heapq.heappop(q)
            self.notices.insert(0, item[1])

    def getNotices(self):
        self.__getAllNotices()
        return self.notices

    def __at(self, comment, refe):
        users = re.findall('@([^\s]*)\s', comment)
        content = AT + str(int(time.time())) + self.username + ' ' + refe
        for username in users:
            r = self.getKademlia(hashlib.sha256(username).hexdigest())
            if r.text.startswith('\n<html>'):
                continue
            key = hashlib.sha256(username + 'notice').hexdigest()
            posts = self.getKademlia(key)
            ps = json.loads(str(posts.text))
            ps[str(len(ps))] = content
            self.postKademlia(key, json.dumps(ps))

    ### Private Message Format: "timestamp||username content"
    def __getPriMessages(self):
        messages = json.loads(str(self.getKademlia(self.privhash).text))
        q = []
        for rank in messages:
            message = messages[rank]
            ts = int(message[ : 10])
            username = message[10 : message.find(' ')]
            content = message[message.find(' ')+1 : ]
            heapq.heappush(q, (ts, [ts, username, content]))
        self.priMessages = []
        while q:
            item = heapq.heappop(q)
            self.priMessages.insert(0, item[1])

    def getPriMessages(self):
        self.__getPriMessages()
        return self.priMessages

    def sendPriMessage(self, username, content):
        if self.fans == None : self.__getFans()
        if self.follows == None : self.__getFollows()
        if not (username in self.fans or username in self.follows) : return
        content = str(int(time.time())) + username + ' ' + content
        key = hashlib.sha256(username + 'priv').hexdigest()
        posts = json.loads(str(self.getKademlia(key).text))
        posts[str(len(posts))] = content
        self.postKademlia(key, json.dumps(posts))

    ### POST format: "timestamp||username body//refeUser refeContent"
    def __post(self, content):
        ps = json.loads(str(self.getKademlia(self.posthash).text))
        ps[str(len(ps))] = content
        self.postKademlia(self.posthash, json.dumps(ps))

    def repost(self, comment, username, content):
        content = str(int(time.time())) + self.username + ' ' + comment \
            + '//' + username + ' ' + content
        self.__at(comment, content)
        self.__post(content)

    def post(self, content):
        content = str(int(time.time())) + self.username + ' '  + content
        self.__at(content, content)
        self.__post(content)

    def __getAllPosts(self):
        q = []
        self.__getFollows()
        self.follows.append(self.username)
        for f in self.follows:
            key = hashlib.sha256(f + 'post').hexdigest()
            posts = json.loads(self.getKademlia(key).text)
            for post in posts:
                content = posts[post]
                ts = int(content[ : 10])
                username = content[10 : content.find(' ')]
                pos = content.rfind('//')
                body = content[10+len(username)+1 : ] if pos == -1 else \
                    content[10+len(username)+1 : content.rfind('//')]
                refe = '' if pos == -1 else content[pos+2 : ]
                refeUser = refe[ : refe.find(' ')]
                refeContent = refe[refe.find(' ')+1 : ]
                kind = '0' if refeUser == '' else '1'
                ft = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))
                heapq.heappush(q, (ts, [kind, username, ft, body, refeUser, refeContent]))
        self.allPosts = []
        self.follows.remove(self.username)
        while q:
            item = heapq.heappop(q)
            self.allPosts.insert(0, item[1])

    def getPost(self, number):
        self.__getAllPosts()
        return self.allPosts[ : number]

    ### fans/follows db: { 'data' : [user0, user1, ... , usern] }
    def __getFans(self):
        fs = json.loads(str(self.getKademlia(self.fanshash).text))
        if fs.has_key('data'):
            self.fans = fs['data']
        else:
            self.fans = []

    def getFans(self):
        self.__getFans()
        return self.fans

    def __getFollows(self):
        fs = json.loads(str(self.getKademlia(self.followhash).text))
        if fs.has_key('data'):
            self.follows = fs['data']
        else:
            self.follows = []

    def getFollows(self):
        self.__getFollows()
        return self.follows

    def follow(self, username):
        func = lambda x,y:x if y in x else x + [y]
        # write to peer->followhash
        follows = self.getKademlia(self.followhash)
        fs = json.loads(str(follows.text))
        if fs.has_key('data'):
            arr = fs['data']
            arr.append(username)
            fs['data'] = reduce(func, [[], ] + arr)
        else:
            fs['data'] = [username]
        self.postKademlia(self.followhash, json.dumps(fs))
        # write to username->fanshash
        key = hashlib.sha256(username + 'fans').hexdigest()
        fans = self.getKademlia(key)
        fs = json.loads(str(fans.text))
        if fs.has_key('data'):
            arr = fs['data']
            arr.append(self.username)
            fs['data'] = reduce(func, [[], ] + arr)
        else:
            fs['data'] = [self.username]
        self.postKademlia(key, json.dumps(fs))

    def unfollow(self, username):
        # remove self->followhash
        follows = self.getKademlia(self.followhash)
        fs = json.loads(str(follows.text))
        if fs.has_key('data'):
            arr = fs['data']
            if username in arr:
                arr.remove(username)
        self.postKademlia(self.followhash, json.dumps(fs))

        # remove username->fanshash
        key = hashlib.sha256(username + 'fans').hexdigest()
        fans = self.getKademlia(key)
        fs = json.loads(str(fans.text))
        if fs.has_key('data'):
            arr = fs['data']
            if self.username in arr:
                arr.remove(self.username)
        self.postKademlia(key, json.dumps(fs))

    def __router(self, peerid):
        if peerid not in self.getpeerids():
            return (None, None, None)
        else:
            rt = [peerid]
            rt.extend(self.peers[peerid])
            return rt
