import asyncio
import collections
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
        self.is_updating = collections.defaultdict(lambda: False)

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
            start = None
            while True:
                #if start:
                #    logger.info("time before last start : %.3fs", time.monotonic() - start)
                start = time.monotonic()
                self.apply_actions()
                t_apply_actions = time.monotonic() - start
                for snake in self.snakes.values():
                    if snake.active:
                        snake.move()
                t_move = time.monotonic() - start - t_apply_actions
                self.check_collisions()
                t_check_collisions = time.monotonic() - start - t_move
                self.update_clients(self.step)
                t_update_clients = time.monotonic() - start - t_check_collisions
                self.gc_snakes()
                t_gc_snakes = time.monotonic() - start - t_update_clients
                self.step += 1
                ellapsed_time = time.monotonic() - start
                if ellapsed_time > LOOP_TIME:
                    logger.warning("Ellapsed time for step %s: %.3fs", self.step, ellapsed_time)
                    logger.warning("t_apply_actions=%.3f, t_move=%.3f, t_check_collisions=%.3f, t_update_clients=%.3f, t_gc_snakes=%.3f" % (
                        t_apply_actions, t_move, t_check_collisions, t_update_clients, t_gc_snakes))
                else:
                    # yield from asyncio.sleep(LOOP_TIME - ellapsed_time)
                    # for bots, it's better to always give the same time to compute strategy
                    yield from asyncio.sleep(LOOP_TIME)
                if self.step % 100 == 0:
                    self.print_stats()
        except Exception:
            logger.exception("Error on run")
            
    def print_stats(self):
        print("step=%s, snakes=%s, active_snakes=%s" % (
            self.step, len(self.snakes), sum(1 for s in self.snakes.values() if s.active)))
            
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
            if not snake.active:
                continue
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
                if other_snake.active and snake.collide(other_snake):
                    if snake is not other_snake:
                        # Other snake killed this snake, he becomes bigger !!
                        other_snake.inc_length(1 + math.floor(0.1*snake.length))
                        other_snake.killed += 1
                    self.reset_snake(snake)
                    
    def reset_snake(self, snake):
        snake.died += 1
        snake.active = False
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
        snake.active = True
    
    def update_clients(self, step):
        game_state = self.pack_game_state()
        for snake in self.snakes.values():
            if snake.websocket.open:
                if self.is_updating[snake.name]:
                    logger.warning("Snake %s is still updating, skipping frame %s", snake.name, step)
                else:
                    asyncio.async(self.update_client(snake, game_state))
            
    @asyncio.coroutine
    def update_client(self, snake, game_state):
        self.is_updating[snake.name] = True
        try:
            if snake.websocket.open:
                yield from snake.websocket.send(game_state)
        except Exception as ex:
            logger.exception("Error during update_client for snake %s: %r", snake.name, ex)
        finally:
            self.is_updating[snake.name] = False
            
    def gc_snakes(self):
        to_close = []
        for snake in self.snakes.values():
            if not snake.websocket.open:
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
        if name in self.snakes:
            logger.info("Remove from snakes")
            del self.snakes[name]
        if name in self.actions:
            logger.info("Remove from actions")
            del self.actions[name]
        if name in self.is_updating:
            logger.info("Remove from is_updating")
            del self.is_updating[name]
        if snake.websocket.open:
            logger.warning("Websocket was not closed")
            asyncio.async(snake.websocket.close())
        logger.info('Snake %s has been removed', name)
            

if __name__ == '__main__':            
    logger.addHandler(logging.StreamHandler())
    logger.setLevel('INFO')
    
    engine = GameEngine()
    engine.run()