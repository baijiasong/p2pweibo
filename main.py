from peers import *
from blockchainPeers import *
from flask import Flask, jsonify, request, render_template

import sys
import hashlib
import json
import requests
import commands

app = Flask(__name__)
peer = None
blockchainPeer = None

@app.route('/appendpeer', methods=['POST'])
def appendPeer():
    global blockchainPeer
    values = request.get_json()
    required = ['nodeid', 'ip', 'rtt']
    if not all(k in values for k in required) : return 'Missing Values', 400
    blockchainPeer.appendPeer(nodeid=values['nodeid'], ip=values['ip'], rtt=values['rtt'])
    response = {'Result' : 'Peer Appended'}
    return jsonify(response), 200

@app.route('/getpeers', methods=['GET'])
def getPeers():
    global blockchainPeer
    response = {
        'peers': blockchainPeer.peers,
        'length': len(blockchainPeer.peers)
    }
    return jsonify(response), 200

@app.route('/addusername', methods=['POST'])
def addUsername():
    global blockchainPeer
    values = request.get_json()
    required = ['username', 'rtt']
    if not all(k in values for k in required) : return 'Missing Values', 400
    blockchainPeer.addUsername(username=values['username'], rtt=int(values['rtt']))
    response = {'Result' : 'Username Appended'}
    return jsonify(response), 200

@app.route('/chain', methods=['GET'])
def getChain():
    global blockchainPeer
    response = {
        'chain': blockchainPeer.chain,
        'length': len(blockchainPeer.chain),
    }
    return jsonify(response), 200

@app.route('/block', methods=['POST'])
def appendBlock():
    global blockchainPeer
    values = request.get_json()
    required = ['block']
    if not all(k in values for k in required) : return 'Missing Values', 400
    blockchainPeer.appendBlock(values['block'])
    response = {'Result' : 'Block Appended'}
    return jsonify(response), 200

# =========================================

@app.route('/hello')
def hello():
    return render_template('hello.html')

@app.route('/', methods=['GET'])
def homepage():
    global peer
    return jsonify(peer.mainpage()), 200

@app.route('/user/<username>', methods=['GET'])
def userpage(username):
    global peer
    return jsonify(peer.userpage(username)), 200

@app.route('/fans', methods=['GET'])
def fans():
    global peer
    response = {
        'data' : peer.getFans()
    }
    return jsonify(response), 200

@app.route('/follows', methods=['GET'])
def follows():
    global peer
    response = {
        'data' : peer.getFollows()
    }
    return jsonify(response), 200

@app.route('/messages', methods=['GET'])
def getMessages():
    global peer
    response = {
        'data' : peer.getPriMessages()
    }
    return jsonify(response), 200

@app.route('/notices', methods=['GET'])
def notice():
    global peer
    response = {
        'data' : peer.getNotices()
    }
    return jsonify(response), 200

@app.route('/follow', methods=['POST'])
def follow():
    global peer
    values = response.get_json()
    required = ['username']
    if not all(k in values for k in required):
        return 'Missing values', 400
    peer.follow(values['username'])
    response = {}
    return response, 200

@app.route('/unfollow', methods=['POST'])
def unfollow():
    global peer
    values = response.get_json()
    required = ['username']
    if not all(k in values for k in required):
        return 'Missing values', 400
    peer.unfollow(values['username'])
    response = {}
    return response, 200

@app.route('/repost', methods=['POST'])
def repost():
    global peer
    values = response.get_json()
    required = ['comment', 'username', 'content']
    if not all(k in values for k in required):
        return 'Missing values', 400
    peer.repost(values['comment'], values['username'], values['content'])
    response = {}
    return jsonify(response), 200

@app.route('/post', methods=['POST'])
def post():
    global peer
    values = request.get_json()
    required = ['content']
    if not all(k in values for k in required):
        return 'Missing values', 400

    peer.post(values['content'])
    response = {
        'test': 'test',
    }
    return jsonify(response), 200

@app.route('/primessage', methods=['POST'])
def priMessage():
    global peer
    values = request.get_json()
    required = ['username', 'content']
    if not all(k in values for k in required) : return 'Missing Values', 400
    peer.sendPriMessage(values['username'], values['content'])
    response = {
        'test' : 'test',
    }
    return jsonify(response), 200


def addTestData():
    global peer
    ### Add user0
    username0 = 'user0'
    userhash0 = hashlib.sha256(username0).hexdigest()
    posthash0 = hashlib.sha256(username0 + 'post').hexdigest()
    fanshash0 = hashlib.sha256(username0 + 'fans').hexdigest()
    followhash0 = hashlib.sha256(username0 + 'follow').hexdigest()
    privhash0 = hashlib.sha256(username0 + 'priv').hexdigest()
    messagehash0 = hashlib.sha256(username0 + 'notice').hexdigest()
    peer.postKademlia(key=userhash0, value='PublicKey')
    peer.postKademlia(key=posthash0, value='{}')
    peer.postKademlia(key=fanshash0, value='{}')
    peer.postKademlia(key=followhash0, value='{}')
    peer.postKademlia(key=privhash0, value='{}')
    peer.postKademlia(key=messagehash0, value='{}')

    ### Add posts for user0
    posts = json.loads('{}')
    posts['0'] = '1513424378User0 Post 0'
    posts['1'] = '1513425378User0 Post 1'
    posts['2'] = '1513426378User0 Post 2'
    posts['3'] = '1513427378User0 Post 3//RefeUser Refe Content@dpatrickx '
    peer.postKademlia(posthash0, json.dumps(posts))

    ### Add User1
    username1 = 'user1'
    userhash1 = hashlib.sha256(username1).hexdigest()
    posthash1 = hashlib.sha256(username1 + 'post').hexdigest()
    fanshash1 = hashlib.sha256(username1 + 'fans').hexdigest()
    followhash1 = hashlib.sha256(username1 + 'follow').hexdigest()
    privhash1 = hashlib.sha256(username1 + 'priv').hexdigest()
    messagehash1 = hashlib.sha256(username1 + 'notice').hexdigest()
    peer.postKademlia(key=userhash1, value='PublicKey')
    peer.postKademlia(key=posthash1, value='{}')
    peer.postKademlia(key=fanshash1, value='{}')
    peer.postKademlia(key=followhash1, value='{}')
    peer.postKademlia(key=privhash1, value='{}')
    peer.postKademlia(key=messagehash1, value='{}')

    ### Add posts for user1
    posts = json.loads('{}')
    posts['0'] = '1513424378User1 Post 0'
    posts['1'] = '1513425378User1 Post 1'
    posts['2'] = '1513426378User1 Post 2'
    posts['3'] = '1513427378User1 Post 3//RefeUser Refe Content @dpatrickx '
    peer.postKademlia(posthash1, json.dumps(posts))

def main(username):
    global peer
    global blockchainPeer
    flaskPort = 5000

    blockchainPeer = BlockChainPeer(port=flaskPort)

    # peer = Peer(username=username, maxpeers=5, serverport=19840)
    # addTestData()

    # peer.follow('user0')
    # peer.follow('user1')
    # peer.post('@dpatrickx Post 0')
    # peer.repost('Repost 0', 'user1', 'Post 0')

    # peer.sendPriMessage('dpatrickx', 'hello world')
    blockchainPeer.mainloop()
    app.run(host='127.0.0.1', port=flaskPort, debug=False)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print "%s username" % sys.argv[0]
        sys.exit(-1)
    main(sys.argv[1])
