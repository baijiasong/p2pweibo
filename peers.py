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
    def __init__(self, username, maxpeers, serverport):
        self.debug = 0
        self.maxpeers = int(maxpeers)
        self.serverport = int(serverport)
        self.peerlock = threading.Lock()
        self.peers = {}
        self.shutdown = False

        self.handlers = {}
        self.router = None
        self.addrouter(self.__router)

        self.username = username
        self.initHash()

        self.allPosts = None
        self.notices = None
        self.fans = None
        self.follows = None
        self.priMessages = None
        self.allUsers = None

        self._getFans()
        self._getFollows()
        self._getAllPosts()
        self._getAllNotices()
        self._getPriMessages()

        r = self.getKademlia(self.userhash)
        if r.text.startswith('\n<html>') == True:
            self.signUp()

    def getKademlia(self, key):
        return requests.get('http://127.0.0.1:1984/' + key)

    def postKademlia(self, key, value):
        return requests.post('http://127.0.0.1:1984/' + key, data=value)

    def initHash(self):
        self.userhash = hashlib.sha256(self.username).hexdigest()
        self.posthash = hashlib.sha256(self.username + 'post').hexdigest()
        self.fanshash = hashlib.sha256(self.username + 'fans').hexdigest()
        self.followhash = hashlib.sha256(self.username + 'follow').hexdigest()
        self.privhash = hashlib.sha256(self.username + 'priv').hexdigest()
        self.noticehash = hashlib.sha256(self.username + 'notice').hexdigest()

    def signUp(self):
        print 'signUp', self.username
        self.postKademlia(key=self.userhash, value='PublicKey')
        self.postKademlia(key=self.posthash, value='{}')
        self.postKademlia(key=self.fanshash, value='{}')
        self.postKademlia(key=self.followhash, value='{}')
        self.postKademlia(key=self.privhash, value='{}')
        self.postKademlia(key=self.noticehash, value='{}')

    ### ATHash entry format: "ATSB||timestamp||username content"
    def _getAllNotices(self):
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
            self.notices.append(item)

    def getNotices(self):
        if self.notices == None : self._getAllNotices()
        return self.notices

    def _at(self, comment, refe):
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
    def _getPriMessages(self):
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
            self.priMessages.append(item)

    def getPriMessages(self):
        if self.priMessages == None : self._getPriMessages()
        return self.priMessages

    def sendPriMessage(self, username, content):
        if self.fans == None : self._getFans()
        if self.follows == None : self._getFollows()
        if not (username in self.fans or username in self.follows) : return
        content = str(int(time.time())) + username + ' ' + content
        key = hashlib.sha256(username + 'priv').hexdigest()
        posts = json.loads(str(self.getKademlia(key).text))
        posts[str(len(posts))] = content
        self.postKademlia(key, json.dumps(posts))

    ### POST format: "timestamp||username body//refeUser refeContent"
    def _post(self, content):
        ps = json.loads(str(self.getKademlia(self.posthash).text))
        ps[str(len(ps))] = content
        self.postKademlia(self.posthash, json.dumps(ps))

    def repost(self, comment, username, content):
        content = str(int(time.time())) + self.username + ' ' + comment \
            + '//' + username + ' ' + content
        self._at(comment, content)
        self._post(content)

    def post(self, content):
        content = str(int(time.time())) + self.username + ' '  + content
        self._at(content, content)
        self._post(content)

    def _getAllPosts(self):
        q = []
        if self.follows == None : self._getFollows()
        tempUsers = self.follows
        tempUsers.append(self.username)
        for f in tempUsers:
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
                heapq.heappush(q, (ts, [ts, username, body, refeUser, refeContent]))
        self.allPosts = []
        while q:
            item = heapq.heappop(q)
            self.allPosts.append(item)

    def getPost(self, number):
        if self.allPosts == None: self._getAllPosts()
        return self.allPosts[ : number]

    ### fans/follows db: { 'data' : [user0, user1, ... , usern] }
    def _getFans(self):
        fs = json.loads(str(self.getKademlia(self.fanshash).text))
        if fs.has_key('data'):
            self.fans = fs['data']
        else:
            self.fans = []

    def getFans(self):
        if self.fans == None : self._getFans()
        return self.fans

    def _getFollows(self):
        fs = json.loads(str(self.getKademlia(self.followhash).text))
        if fs.has_key('data'):
            self.follows = fs['data']
        else:
            self.follows = []

    def getFollows(self):
        if self.follows == None : self._getFollows()
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

    def __debug( self, msg ):
        if self.debug:
            btdebug(msg)

    def __handlepeer( self, clientsock ):
        self.__debug( 'New child ' + str(threading.currentThread().getName()) )
        self.__debug( 'Connected ' + str(clientsock.getpeername()) )

        host, port = clientsock.getpeername()
        peerconn = PeerConnection( None, host, port, clientsock, debug=False )

        try:
            msgtype, msgdata = peerconn.recvdata()
            if msgtype: msgtype = msgtype.upper()
            if msgtype not in self.handlers:
                self.__debug( 'Not handled: %s: %s' % (msgtype, msgdata) )
            else:
                self.__debug( 'Handling peer msg: %s: %s' % (msgtype, msgdata) )
                self.handlers[ msgtype ]( peerconn, msgdata )
        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()

        self.__debug( 'Disconnecting ' + str(clientsock.getpeername()) )
        peerconn.close()

        # end handlepeer method

    def __runstabilizer( self, stabilizer, delay ):
        while not self.shutdown:
            stabilizer()
            time.sleep( delay )

    def startstabilizer( self, stabilizer, delay ):
        """ Registers and starts a stabilizer function with this peer.
        The function will be activated every <delay> seconds.

        """
        t = threading.Thread( target = self.__runstabilizer,
                      args = [ stabilizer, delay ] )
        t.start()

    def addhandler(self, msgtype, handler):
        """ Registers the handler for the given message type with this peer """
        assert len(msgtype) == 4
        self.handlers[ msgtype ] = handler

    def addrouter( self, router ):
        self.router = router

    def addpeer( self, peerid, host, port ):
        """ Adds a peer name and host:port mapping to the known list of peers.

        """
        if peerid not in self.peers and (self.maxpeers == 0 or
                         len(self.peers) < self.maxpeers):
            self.peers[ peerid ] = (host, int(port))
            return True
        else:
            return False

    def getpeer( self, peerid ):
        """ Returns the (host, port) tuple for the given peer name """
        assert peerid in self.peers    # maybe make this just a return NULL?
        return self.peers[ peerid ]

    def removepeer( self, peerid ):
        """ Removes peer information from the known list of peers. """
        if peerid in self.peers:
            del self.peers[ peerid ]

    def addpeerat( self, loc, peerid, host, port ):
        """ Inserts a peer's information at a specific position in the
        list of peers. The functions addpeerat, getpeerat, and removepeerat
        should not be used concurrently with addpeer, getpeer, and/or
        removepeer.

        """
        self.peers[ loc ] = (peerid, host, int(port))

    def getpeerat( self, loc ):
        if loc not in self.peers:
            return None
        return self.peers[ loc ]

    def removepeerat( self, loc ):
        removepeer( self, loc )

    def getpeerids( self ):
        """ Return a list of all known peer id's. """
        return self.peers.keys()

    def numberofpeers( self ):
        """ Return the number of known peer's. """
        return len(self.peers)

    def maxpeersreached( self ):
        """ Returns whether the maximum limit of names has been added to the
        list of known peers. Always returns True if maxpeers is set to
        0.

        """
        assert self.maxpeers == 0 or len(self.peers) <= self.maxpeers
        return self.maxpeers > 0 and len(self.peers) == self.maxpeers

    def sendtopeer( self, peerid, msgtype, msgdata, waitreply=True ):
        if self.router:
            nextpid, host, port = self.router( peerid )
        if not self.router or not nextpid:
            self.__debug( 'Unable to route %s to %s' % (msgtype, peerid) )
            return None
        #host,port = self.peers[nextpid]
        return self.connectandsend( host, port, msgtype, msgdata,
                                pid=nextpid,
                                waitreply=waitreply )

    def connectandsend( self, host, port, msgtype, msgdata,
            pid=None, waitreply=True ):
        """
        connectandsend( host, port, message type, message data, peer id,
        wait for a reply ) -> [ ( reply type, reply data ), ... ]

        Connects and sends a message to the specified host:port. The host's
        reply, if expected, will be returned as a list of tuples.

        """
        msgreply = []
        try:
            peerconn = PeerConnection( pid, host, port, debug=self.debug )
            peerconn.senddata( msgtype, msgdata )
            self.__debug( 'Sent %s: %s' % (pid, msgtype) )

            if waitreply:
                onereply = peerconn.recvdata()
                while (onereply != (None,None)):
                    msgreply.append( onereply )
                    self.__debug( 'Got reply %s: %s'
                          % ( pid, str(msgreply) ) )
                    onereply = peerconn.recvdata()
            peerconn.close()
        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()

        return msgreply

        # end connectsend method

    def checklivepeers( self ):
        """ Attempts to ping all currently known peers in order to ensure that
        they are still active. Removes any from the peer list that do
        not reply. This function can be used as a simple stabilizer.

        """
        todelete = []
        for pid in self.peers:
            isconnected = False
            try:
                self.__debug( 'Check live %s' % pid )
                host,port = self.peers[pid]
                peerconn = PeerConnection( pid, host, port, debug=self.debug )
                peerconn.senddata( 'PING', '' )
                isconnected = True
            except:
                todelete.append( pid )
                if isconnected:
                    peerconn.close()

        self.peerlock.acquire()
        try:
            for pid in todelete:
                if pid in self.peers: del self.peers[pid]
        finally:
            self.peerlock.release()
        # end checklivepeers method

    def makeserversocket(self, port, backlog=5):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('', port))
        s.listen(backlog)
        return s

    def getPeers(self):
        address = ('202.112.237.152', 24325)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(address)

        peerconn = PeerConnection(None, '202.112.237.152', 24325, debug=self.debug )

        while True:
            msgtype, msgdata = peerconn.recvdata()
            if msgtype == None:
                continue
            elif msgtype == PEER:
                print 'Got Reply: ', msgdata
            elif msgtype == END:
                print 'Got End'
                break
            else:
                break

    def mainloop(self):
        self.getPeers()

        s = self.makeserversocket(self.serverport)
        s.settimeout(10)

        print 'Server started at port : %d' % (self.serverport)

        while not self.shutdown:
            try:
                clientsock, clientaddr = s.accept()
                clientsock.settimeout(None)

                t = threading.Thread( target = self.__handlepeer, args = [ clientsock ] )
                t.start()
            except KeyboardInterrupt:
                print 'KeyboardInterrupt'
                self.shutdown = True
                break
            except:
                if self.debug:
                    traceback.print_exc()
                    break
        s.close()

# End of class Peer

class PeerConnection:
    def __init__( self, peerid, host, port, sock=None, debug=False ):
        # any exceptions thrown upwards

        self.id = peerid
        self.debug = debug

        if not sock:
            self.s = socket.socket( socket.AF_INET, socket.SOCK_STREAM )
            self.s.connect( ( host, int(port) ) )
        else:
            self.s = sock

        self.sd = self.s.makefile( 'rw', 0 )


    def __makemsg( self, msgtype, msgdata ):
        msglen = len(msgdata)
        msg = struct.pack( "!4sL%ds" % msglen, msgtype, msglen, msgdata )
        return msg


    def __debug( self, msg ):
        if self.debug:
            btdebug( msg )


    def senddata( self, msgtype, msgdata ):
        try:
            msg = self.__makemsg( msgtype, msgdata )
            self.sd.write( msg )
            self.sd.flush()
        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()
            return False
        return True

    def recvdata( self ):
        try:
            msgtype = self.sd.read(4)
            if not msgtype: return (None, None)

            lenstr = self.sd.read(4)
            msglen = int(struct.unpack( "!L", lenstr )[0])
            msg = ""

            while len(msg) != msglen:
                data = self.sd.read( min(2048, msglen - len(msg)) )
                if not len(data):
                    break
                msg += data

            if len(msg) != msglen:
                return (None, None)

        except KeyboardInterrupt:
            raise
        except:
            if self.debug:
                traceback.print_exc()
            return (None, None)

        return ( msgtype, msg )

    def close( self ):
        self.s.close()
        self.s = None
        self.sd = None

    def __str__( self ):
        return "|%s|" % peerid
