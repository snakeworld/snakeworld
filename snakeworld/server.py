import asyncio
import json
import logging
import math
import time
import os
import websockets

from .common import *


logger = logging.getLogger(__name__)


class GameEngine(GameState):
    def __init__(self):
        super().__init__(Size(200, 100))
        self.max_fruits = 20
        self.actions = {}

    def run(self):
        start_server = websockets.serve(self.on_client, '0.0.0.0', 8080)
        asyncio.get_event_loop().run_until_complete(start_server)
        logger.info("Listen")
        asyncio.get_event_loop().run_until_complete(self.loop())
    
    @asyncio.coroutine
    def loop(self):
        logger.info("Engine started")
        LOOP_TIME = 0.1
        try:
            logger.info("Create fruits")
            for i in range(self.max_fruits):
                self.create_fruit()
            logger.info("Ready to loop")
            while True:
                start = time.monotonic()
                self.apply_actions()
                #logger.info("Step %s", self.step)
                for snake in self.snakes.values():
                    snake.move()
                self.check_collisions()
                yield from self.update_clients()
                self.step += 1
                ellapsed_time = time.monotonic() - start
                if ellapsed_time > LOOP_TIME:
                    logger.warning("Ellapsed time for step %s: %.3fs", self.step, ellapsed_time)
                else:
                    yield from asyncio.sleep(LOOP_TIME - ellapsed_time)
        except Exception:
            logger.exception("Error on run")
            
    def apply_actions(self):
        to_remove = []
        for snakename, direction in self.actions.items():
            if direction is not None and snakename in self.snakes:
                self.snakes[snakename].change_direction(direction)
                self.actions[snakename] = None
            else:
                to_remove.append(snakename)
        for r in to_remove:
            del self.actions[r]
            
    def create_fruit(self):
        fruit = Fruit.create_random(self.size)
        self.fruits.append(fruit)
    
    def check_collisions(self):
        for snake in self.snakes.values():
            # Check for collision with fruits
            for fruit in self.fruits:
                if snake.collide(fruit):
                    snake.inc_length()
                    fruit.random_move(self.size)
            # Check for collision with map borders
            if not ((0 <= snake.position.x < self.size.width) \
                and (0 <= snake.position.y < self.size.height)):
                    self.reset_snake(snake)
            # Check for collision with other snakes
            for other_snake in self.snakes.values():
                if snake.collide(other_snake):
                    if snake is not other_snake:
                        # Other snake killed this snake, he becomes bigger !!
                        other_snake.inc_length(1 + math.floor(0.1*snake.length))
                    self.reset_snake(snake)
                    
    def reset_snake(self, snake):
        for _ in range(20):
            snake.reset(self.size)
            respawn_ok = True
            for other_snake in self.snakes.values():
                if other_snake is not snake and snake.manathan_distance(other_snake) <= 5:
                    respawn_ok = False
                    break
                    
            if respawn_ok:
                break
            else:
                logger.info('Spawn is too close, reset')
    
    @asyncio.coroutine
    def update_clients(self):
        game_state = self.pack_game_state()
        to_close = []
        for snake in self.snakes.values():
            if snake.websocket.open:
                try:
                    yield from snake.websocket.send(game_state)
                except IOError as ex:
                    logger.warning("Error writing to snake %s: %s", snake, ex)
            else:
                to_close.append(snake)
        for snake in to_close:
            self.close_snake(snake)
    
    def pack_game_state(self):
        return json.dumps(self.to_dict())
    
    @asyncio.coroutine
    def on_client(self, websocket, path):
        snake = None
        try:
            logger.info("New connection from client %s" % websocket)
            snake = Snake.create(websocket, self.size)
            self.snakes[snake.name] = snake
            init_data = yield from self.get_snakeinit(snake)
            name = init_data['name']
            if name and name not in self.snakes:
                del self.snakes[snake.name]
                snake.activate(name)
                self.snakes[snake.name] = snake
                yield from websocket.send('Success')
                while websocket.open:
                    raw_msg = yield from websocket.recv()
                    if raw_msg is None:
                        break
                    logger.debug("Recv %r", raw_msg)
                    try:
                        msg = json.loads(raw_msg)
                        if msg:
                            direction = Direction(msg['direction'])
                            self.actions[snake.name] = direction
                    except Exception as ex:
                        yield from websocket.send(json.dumps({'error': str(ex)}))
                print('Client closed')
            else:
                yield from websocket.send('Error name already in use')
        except Exception as ex:
            logger.exception("Error with snake %s", snake)
            if snake is not None:
                self.close_snake(snake)
                
    @asyncio.coroutine
    def get_snakeinit(self, snake):
        while snake.websocket.open:
            raw_init = yield from snake.websocket.recv()
            json_init = json.loads(raw_init)
            if 'name' not in json_init:
                continue
            return json_init
        raise ValueError("Websocket closed")
            
    def close_snake(self, snake):
        name = snake.name
        logger.info('Remove snake %s', name)
        if snake.name in self.snakes:
            logger.info("Snake in snakes")
            del self.snakes[name]
        if snake.websocket.open:
            snake.websocket.close()
        logger.info('Snake %s has been removed', name)
            

if __name__ == '__main__':            
    logger.addHandler(logging.StreamHandler())
    logger.setLevel('INFO')
    
    engine = GameEngine()
    engine.run()