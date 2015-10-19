import asyncio
import collections
import csv
import json
import logging
import math
import msgpack
import os
import time
from statistics import mean
import websockets

from .common import *
from .client import BaseClient
from .utils import json_dumps


logger = logging.getLogger(__name__)


class GameStateCompressor:

    def compress(self, state):
        return {
            'walls': [self.compress_point(x) for x in state['walls']],
            'fruits': [self.compress_point(x) for x in state['fruits']],
            'size': state['size'],
            'step': state['step'],
            'snakes': [self.compress_snake(snake) for snake in state['snakes']],
        }

    def compress_point(self, node):
        return (node['x'], node['y'])

    def compress_body(self, body):
        if len(body) < 3:
            return body
        compressed_body = []
        for i, node in enumerate(body):
            if i == 0:
                compressed_body.append(self.compress_point(node))
            elif node['x'] != compressed_body[-1][0] and node['y'] != compressed_body[-1][1]:
                compressed_body.append(self.compress_point(body[i-1]))
        last_node = self.compress_point(body[-1])
        if compressed_body[-1] != last_node:
            compressed_body.append(last_node)
        return compressed_body

    def compress_snake(self, snake):
        snake['body'] = self.compress_body(snake['body'])
        return snake


class ReadOnlyProxy:
    PACK_JSON = 'json'
    PACK_MSGPACK = 'msgpack'

    def __init__(self, server_url='ws://52.19.18.173:8080/', compressor=None, pack=PACK_JSON):
        self.server_url = server_url
        self.websocket = None
        self.compressor = compressor
        self.pack = pack
        self.queues = []
        self.compress_ratios = collections.deque(maxlen=100)

    def run_until_complete(self):
        asyncio.get_event_loop().run_until_complete(self.run())

    @asyncio.coroutine
    def run(self):
        logger.info('Connecting to webserver %s...', self.server_url)
        self.websocket = yield from websockets.connect(self.server_url)
        logger.info('Listening connections...')
        yield from websockets.serve(self.on_client, '0.0.0.0', 8081)
        yield from self.loop()
        logger.info('Proxy stop')

    @asyncio.coroutine
    def loop(self):
        logger.info('Proxy started')
        while self.websocket.open:
            # XXX This could be optimized if pack is 'json' and compression is not activated
            gamestate, size = yield from self.recv_game_state()
            if gamestate is None:
                logger.warning('gamestate is None')
                continue
            step = gamestate['step']
            if self.compressor is not None:
                gamestate = self.compressor.compress(gamestate)
            if self.pack == self.PACK_JSON:
                gamestate = json_dumps(gamestate)
            else:
                gamestate = msgpack.packb(gamestate)
            self.compress_ratios.append(size / len(gamestate) - 1)
            if step % self.compress_ratios.maxlen == 0:
                logger.info('Compression ratio: %.2f%%', mean(self.compress_ratios) * 100)
            for q in self.queues:
                try:
                    q.put_nowait(gamestate)
                except asyncio.QueueFull:
                    logger.info('Queue %s is full, skip frame', id(q))

    @asyncio.coroutine
    def recv_game_state(self):
        # XXX Missing frame-skip detection
        logger.debug('Update game state')
        raw_data = yield from self.websocket.recv()
        try:
            return json.loads(raw_data), len(raw_data)
        except:
            logger.error('Cannot parse %r', raw_data)
            return None, 0
        if 'error' in data:
            error = data['error']
            logger.warning('Got an error from server: %s', error)
            return None, 0

    @asyncio.coroutine
    def on_client(self, websocket, path):
        queue = None
        try:
            logger.info("New connection from client %s" % websocket)
            queue = asyncio.Queue(maxsize=10)
            self.queues.append(queue)
            while websocket.open:
                gamestate = yield from queue.get()
                yield from asyncio.wait_for(websocket.send(gamestate), timeout=5)
        except Exception as ex:
            logger.exception('Error')
            if queue in self.queues:
                logger.info('Remove queue %s', id(queue))
                self.queues.remove(queue)


if __name__ == '__main__':
    import sys

    logger.addHandler(logging.StreamHandler())
    logger.setLevel('INFO')

    def compare(data):
        js = json.dumps(data, separators=(',', ':')).encode('utf8')
        m = msgpack.packb(data)
        compressed = compressor.compress(data)
        m2 = msgpack.packb(compressed)
        js2 = json.dumps(compressed, separators=(',', ':')).encode('utf8')
        print('json: %.3f ko' % (len(js) / 1000))
        print('msgpack: %.3f ko' % (len(m) / 1000))
        print('json (compressed): %.3f ko' % (len(js2) / 1000))
        print('msgpack (compressed): %.3f ko' % (len(m2) / 1000))

    compressor = GameStateCompressor()
    kwargs = {
        'compressor': compressor,
        'pack': ReadOnlyProxy.PACK_MSGPACK,
    }
    if len(sys.argv) > 1:
        kwargs['server_url'] = sys.argv[1]
    proxy = ReadOnlyProxy(**kwargs)
    proxy.run_until_complete()
