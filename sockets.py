#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2014 Abram Hindle
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request, jsonify
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__)
sockets = Sockets(app)
app.debug = True


class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()

    def add_set_listener(self, listener):
        self.listeners.append(listener)

    def update(self, entity, key, value):
        entry = self.space.get(entity, dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners(entity)

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners(entity)

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            listener(entity, self.get(entity))

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity, dict())

    def world(self):
        return self.space


class Client:
    def __init__(self):
        self.queue = queue.Queue()

    def put(self, v):
        self.queue.put_nowait(v)

    def get(self):
        return self.queue.get()


myWorld = World()
clients = []
def send_all(msg):
    #print("IN SEND ALL", msg)
    if json.dumps(msg) == json.dumps({"X0": {"x": 0}} ):
        print("IN SEND ALL IFFFF", msg)
    for client in clients:
        client.put( msg )

def send_all_json(obj):
    send_all( json.dumps(obj) )
    #print(clients)

def set_listener(entity, data):
    ''' do something with the update ! '''
    # msg = json.dumps({entity: data})
    # for client in clients:
    #     client.put(msg)
    #print("set_listener", entity, data)
    send_all_json({entity:data})


myWorld.add_set_listener(set_listener)


@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return flask.redirect("/static/index.html", code=302)
    return None


def read_ws(ws, client):
    '''A greenlet function that reads from the websocket and updates the world'''
    # XXX: TODO IMPLEMENT ME
    while True:
        msg = ws.receive()
        #print("WS RECV IN READ: %s" % msg)
        if msg is not None:
            if 'type' in json.loads(msg).keys() and json.loads(msg)['type'] == "ack" :
                print(json.loads(msg)['message'])
            else:
                data = json.loads(msg)
                print("DATA", data)
                # for entity, updates in data.items():
                #     print("ENTITY", entity)
                #     print("UPDATES", updates)
                #     for key, value in updates.items():
                #         myWorld.update(entity, key, value)
                send_all_json(data)
                # for other_client in clients:
                #     if other_client != client:
                #         print("PUTTING", other_client, data)
                #         other_client.put(json.dumps(data))
        else:
            break
    return None


@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket '''
    print("REACHED SUBSCRIBE")
    client = Client()
    clients.append(client)
    print("Added client", client)
    print("Clients", clients)
    g = gevent.spawn(read_ws, ws, client)
    try:
        while not ws.closed:
            msg = client.get()
            try:
                ws.send(msg)
            except Exception as e:
                print(f"Error while sending message to client: {str(e)}")
                break
    except Exception as e:
        print(f"Error in subscribe_socket: {str(e)}")
    finally:
        clients.remove(client)
        gevent.kill(g)
        if not ws.closed:
            ws.close()
    return None


# I give this to you, this is how you get the raw body/data portion of a post in flask
# this should come with flask but whatever, it's not my project.
def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data.decode("utf8") != u''):
        return json.loads(request.data.decode("utf8"))
    else:
        return json.loads(request.form.keys()[0])


@app.route("/entity/<entity>", methods=['POST', 'PUT'])
def update(entity):
    '''update the entities via this interface'''
    data = flask_post_json()
    for key, value in data.items():
        myWorld.update(entity, key, value)

    return jsonify(myWorld.get(entity)),200
    return None


@app.route("/world", methods=['POST', 'GET'])
def world():
    '''you should probably return the world here'''

    return jsonify(myWorld.world()),200
    return None


@app.route("/entity/<entity>")
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    return jsonify(myWorld.get(entity)),200
    return None


@app.route("/clear", methods=['POST', 'GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()
    return jsonify(myWorld.world()),200
    return None


if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
