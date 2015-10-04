import asyncio
import logging
import json
import websockets
from snakeworld.common import Snake, Size, Direction, Fruit, Point, GameState

logger = logging.getLogger(__name__)


class BaseClient:
    def __init__(self, name, server_url='ws://52.19.18.173:8080/'):
        self.name = name
        self.server_url = server_url
        self.websocket = None
        self.state = None
        self.mysnake = None
    
    def run_until_complete(self):
        asyncio.get_event_loop().run_until_complete(self.run())
        
    @asyncio.coroutine
    def run(self):
        logger.info("Connecting to webserver")
        self.websocket = yield from websockets.connect(self.server_url)
        logger.info("Client connected to webserver")
        yield from self.send_init()
        yield from self.loop()
        logger.info("Client stop")
        
    @asyncio.coroutine
    def loop(self):
        while self.websocket.open:
            yield from self.update_game_state()
            if asyncio.iscoroutine(self.evaluate):
                direction = yield from self.evaluate()
            else:
                direction = self.evaluate()
            if direction is not None:
                yield from self.websocket.send(json.dumps({'direction': direction.value}))

    @asyncio.coroutine
    def send_init(self):
        logger.info("Initialize client")
        yield from self.websocket.send(json.dumps({'name': self.name}))
        logger.info("Client initialized")
        
    @asyncio.coroutine
    def update_game_state(self):
        logger.debug("Update game state")
        raw_data = yield from self.websocket.recv()
        try:
            data = json.loads(raw_data)
        except:
            logger.error("Cannot parse %r", raw_data)
            return
        if 'error' in data:
            self.error = data['error']
            self.state = None
            logger.warning("Got an error from server: %s", self.error)
            return
        if 'size' not in data:
            print(data)
        new_state = GameState.from_dict(data)
        if self.state and new_state.step != self.state.step + 1:
            logger.warning("Frame skip: prev_step=%s, recv_step=%s", self.state.step, new_state.step)
        self.state = new_state
        if self.state and self.name in self.state.snakes:
            self.mysnake = self.state.snakes[self.name]
    
    def evaluate(self):
        """The brain.
        
        Must return a Direction or None.
        
        You may access the game state with self.state and the last error with self.error.
        
        In case of error self.state will be None.
        """
        raise NotImplementedError()