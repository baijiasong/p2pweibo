import socket
import threading
import sys
import traceback
import os
import json
import hashlib
import requests
import time
from  uuid import uuid4

class BlockChainPeer:
    def __init__(self, port):
        self.allusers = []
        self.port = port
        self.ip = self.__getHostIp()
        self.peers = {}
        self.chain = []
        self.previousHash = None
        self.nodeid = str(uuid4()).replace('-', '')
        self.usernames = []
        self.mutex = threading.Lock()
        self.ifMine = None
        self.peers[self.nodeid] = self.__getHostIp()

    @property
    def lastBlock(self):
        return self.chain[-1]

    @staticmethod
    def hash(block):
        return hashlib.sha256(json.dumps(block, sort_keys=True)).hexdigest()

    def __newBlock(self, previousHash, nouce=0):
        if self.mutex.acquire(1):
            block = {
                'index': len(self.chain),
                'timestamp': int(time.time()),
                'usernames': self.usernames,
                'nouce': nouce,
                'previousHash': previousHash,
                'author': self.nodeid
            }
            self.usernames = []
            self.chain.append(block)
            self.mutex.release()
            return block

    def showChain(self):
        for block in self.chain:
            print block['previousHash'][:6] + '->',
        print 'End'

    def mine(self):
        while self.ifMine:
            self.thisRound = True
            self.previousHash = self.hash(self.lastBlock)
            self.usernames = []
            self.showChain()
            self.__pow(self.previousHash)

    def __pow(self, previousHash):
        print '-----------------------------------'
        print 'Mining', previousHash
        nouce = 1
        while self.thisRound:
            guessHash = hashlib.sha256(previousHash + str(nouce) + self.nodeid).hexdigest()
            if guessHash[ : 6] == "000000":
                print '### Mint', nouce, len(self.chain)
                block = self.__newBlock(nouce=nouce, previousHash=self.previousHash)
                self.__broadcastBlock(block)
                return
            nouce += 1

    def __broadcastBlock(self, block):
        data = {
            'block': block
        }
        for nodeid in self.peers:
            if nodeid == self.nodeid : continue
            try:
                requests.post('http://%s:%d/block' % (self.peers[nodeid], self.port), json=data)
            except:
                continue

    def appendBlock(self, block):
        previousHash = block['previousHash']
        if previousHash == self.previousHash:
            self.chain.append(block)
            self.usernames = []
            self.thisRound = False
            print 'Get Mint From', block['nouce']
        else:
            print 'Conflict', len(self.chain), block['index']+1
            if len(self.chain) < block['index'] + 1 : self.__syncBlockchain()

    def __syncBlockchain(self):
        if self.mutex.acquire(1):
            self.ifMine = False
            self.thisRound = False
            for nodeid in self.peers:
                if nodeid == self.nodeid : continue
                response = requests.get('http://%s:%d/chain' % (self.peers[nodeid], self.port))
                if response.status_code == 200:
                    length = response.json()['length']
                    if length > len(self.chain):
                        self.chain = response.json()['chain']
            self.ifMine = True
            t = threading.Thread(target=self.mine, args=[])
            t.setDaemon(True)
            t.start()
        self.mutex.release()
        self.allusers = []
        for block in self.chain:
            self.allusers += block['usernames']
        print 'AllUsers', self.allusers

    def appendPeer(self, nodeid, ip, rtt):
        if nodeid == self.nodeid : return
        if nodeid in self.peers : return
        rtt -= 1
        if rtt > 0:
            data = {
                'nodeid' : nodeid,
                'ip': ip,
                'rtt': rtt
            }
            for node in self.peers:
                if node == self.nodeid : continue
                requests.post('http://%s:%d/appendpeer' % (self.peers[node], self.port), json=data)
        print 'Add Peer', nodeid, ip
        self.peers[nodeid] = ip

    def __addUsername(self, username):
        if self.mutex.acquire(1):
            self.usernames.append(username)
            self.mutex.release()
        print self.usernames

    def addUsername(self, username, rtt):
        print 'addUsername CALL'
        if not username in self.usernames:
            self.__addUsername(username)
        else:
            return
        rtt -= 1
        if rtt <= 0 : return
        data = {
            'username' : username,
            'rtt' : rtt
        }
        for nodeid in self.peers:
            if nodeid == self.nodeid : continue
            print 'report to', self.peers[nodeid]
            requests.post('http://%s:%d/addusername' % (self.peers[nodeid], self.port), json=data)
            print 'report end'

    @staticmethod
    def __getHostIp():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(('8.8.8.8', 80))
            ip = s.getsockname()[0]
        finally:
            s.close()
        return ip

    def __addPeers(self, ip):
        print 'Add peers from ', ip
        response = requests.get('http://%s:%d/getpeers' % (ip, self.port))
        if response.status_code == 200:
            length = response.json()['length']
            peers = response.json()['peers']
            for nodeid in peers:
                if nodeid in self.peers : continue
                print 'Add Peer', nodeid, peers[nodeid]
                self.peers[nodeid] = peers[nodeid]

    def connectPeers(self):
        data = {
            'nodeid': self.nodeid,
            'ip': self.__getHostIp(),
            'rtt': 5
        }
        if not os.path.exists('peers.txt') : return
        peerips = open('peers.txt').read().split('\n')
        for peerip in peerips:
            if len(peerip) == 0 : continue
            if peerip == self.ip : continue
            print 'Add peer to ', peerip
            requests.post('http://%s:%d/appendpeer' % (peerip, self.port), json=data)
            self.__addPeers(peerip)
        print 'Peers:', self.peers
        # initial block
        if len(self.peers) <= 1:
            self.__newBlock(nouce=0, previousHash='1')
        self.__syncBlockchain()

    def mainloop(self):
        print 'Nodeid', self.nodeid
        self.connectPeers()
