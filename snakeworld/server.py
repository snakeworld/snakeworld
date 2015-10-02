import asyncio
import enum
import json
import logging
import os
import random
import uuid
import websockets


logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel('INFO')


class Direction(enum.Enum):
    LEFT = 'l'
    RIGHT = 'r'
    UP = 'u'
    DOWN = 'd'


class Size:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        
    def get_state(self):
        return {'width': self.width, 'height': self.height}
        
    def __str__(self):
        return 'Size(%s, %s)' % (self.width, self.height)
        

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        
    @classmethod
    def get_random(cls, map_size):
        return cls(random.randint(1, map_size.width-1), random.randint(1, map_size.height-1))
        
    def get_state(self):
        return {'x': self.x, 'y': self.y}
        
    def random_move(self, map_size):
        self.x = random.randint(1, map_size.width-1)
        self.y = random.randint(1, map_size.height-1)
        
    def get_neighbour(self, direction):
        if direction == Direction.LEFT:
            return Point(self.x-1, self.y)
        elif direction == Direction.RIGHT:
            return Point(self.x+1, self.y)
        elif direction == Direction.UP:
            return Point(self.x, self.y-1)
        elif direction == Direction.DOWN:
            return Point(self.x, self.y+1)
        else:
            raise ValueError("Invalid direction %r" % direction)
            
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __str__(self):
        return "Point(%s, %s)" % (self.x, self.y)


class GameObject:
    def __init__(self, map_size):
        self.map_size = map_size
        self.position = Point.get_random(self.map_size)
        
    def get_state(self):
        return self.position.get_state()
        
    def collide(self, other):
        return self.position == other.position
        
    def random_move(self):
        self.position.random_move(self.map_size)
    
    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, self.position)


class Snake(GameObject):
    def __init__(self, websocket, map_size):
        super().__init__(map_size)
        self.body = []
        self.direction = None
        self.length = 1
        self.best_length = 1
        self.died = 0
        self.killed = 0
        self.name = str("Anonymous-%s" % uuid.uuid4())
        self.websocket = websocket
        r = lambda: random.randint(0,255)
        self.color = '#%02X%02X%02X' % (r(),r(),r())
        self.active = False
        self.reset()
        
    def activate(self, name):
        self.name = name
        self.active = True
        
    def move(self):
        if not self.body or not self.direction:
            return
        head = self.body[0]
        new_head = head.get_neighbour(self.direction)
        self.body.insert(0, new_head)
        self.position = new_head
        if len(self.body) > self.length:
            self.body.pop()
            
    def inc_length(self):
        self.length += 1
        self.best_length = max(self.length, self.best_length)
    
    def reset(self):
        self.direction = random.choice(list(Direction))
        self.length = 6
        self.best_length = max(self.length, self.best_length)
        head = Point.get_random(self.map_size)
        self.body = [head]
        self.position = head
 
    def get_state(self):
        return {
            'body': [p.get_state() for p in self.body],
            'name': self.name,
            'color': self.color,
            'direction': self.direction.value,
            'best_length': self.best_length,
            'length': self.length,
        }
        
    def change_direction(self, direction):
        if (direction == Direction.UP and self.direction == Direction.DOWN) \
            or (direction == Direction.DOWN and self.direction == Direction.UP) \
            or (direction == Direction.LEFT and self.direction == Direction.RIGHT) \
            or (direction == Direction.RIGHT and self.direction == Direction.LEFT):
                return
        self.direction = direction
        
    def collide(self, other):
        if isinstance(other, Snake):
            other_body = other.body
            if self is other:
                other_body = other_body[1:]
            for p in other_body:
                if self.position == p:
                    return True
            return False
        else:
            return super().collide(other)
            
    def __str__(self):
        return 'Snake(name=%r, direction=%s, position=%s, length=%s, best_length=%s)' % (
            self.name, self.direction.name, self.position, self.length, self.best_length)


class Fruit(GameObject):
    pass


class Wall(GameObject):
    pass


class GameEngine:
    def __init__(self):
        self.snakes = {}
        self.fruits = []
        self.walls = []
        self.step = 0
        self.size = Size(200, 100)
        self.max_fruits = 20
    
    @asyncio.coroutine
    def run(self):
        try:
            logger.info("Create fruits")
            for i in range(self.max_fruits):
                self.create_fruit()
            logger.info("Ready to loop")
            while True:
                #logger.info("Step %s", self.step)
                for snake in self.snakes.values():
                    snake.move()
                self.check_collisions()
                yield from self.update_clients()
                yield from asyncio.sleep(0.1)
                self.step += 1
        except Exception:
            logger.exception("Error on run")
            
    def create_fruit(self):
        fruit = Fruit(self.size)
        self.fruits.append(fruit)
    
    def check_collisions(self):
        for snake in self.snakes.values():
            # Check for collision with fruits
            for fruit in self.fruits:
                if snake.collide(fruit):
                    snake.inc_length()
                    fruit.random_move()
            # Check for collision with map borders
            if not ((0 <= snake.position.x < self.size.width) \
                and (0 <= snake.position.y < self.size.height)):
                    snake.reset()
            # Check for collision with other snakes
            for other_snake in self.snakes.values():
                if snake.collide(other_snake):
                    if snake is not other_snake:
                        # Other snake killed this snake, he becomes bigger !!
                        other_snake.inc_length()
                    snake.reset()
    
    @asyncio.coroutine
    def update_clients(self):
        game_state = self.pack_game_state()
        to_close = []
        for snake in self.snakes.values():
            if snake.websocket.open:
                yield from snake.websocket.send(game_state)
            else:
                to_close.append(snake)
        for snake in to_close:
            self.close_snake(snake)
    
    def pack_game_state(self):
        return json.dumps(self.get_state())
        
    def get_state(self):
        state = {
            'size': self.size.get_state(),
            'snakes': [snake.get_state() for snake in self.snakes.values() if snake.active],
            'fruits': [fruit.get_state() for fruit in self.fruits],
            'walls': [wall.get_state() for wall in self.walls],
        }
        return state
    
    @asyncio.coroutine
    def on_client(self, websocket, path):
        snake = None
        try:
            logger.info("New connection from client %s" % websocket)
            snake = Snake(websocket, self.size)
            self.snakes[snake.name] = snake
            raw_init = yield from websocket.recv()
            json_init = json.loads(raw_init)
            name = json_init['name']
            if name and name not in self.snakes:
                del self.snakes[snake.name]
                snake.activate(name)
                self.snakes[snake.name] = snake
                yield from websocket.send('Success')
                while websocket.open:
                    raw_msg = yield from websocket.recv()
                    if raw_msg is None:
                        break
                    logger.info("Recv %r", raw_msg)
                    try:
                        msg = json.loads(raw_msg)
                        direction = Direction(msg['direction'])
                        snake.change_direction(direction)
                    except Exception as ex:
                        yield from websocket.send(json.dumps({'error': str(ex)}))
                print('Client closed')
            else:
                yield from websocket.send('Error name already in use')
        except Exception as ex:
            logger.exception("Error")
            if snake is not None:
                self.close_snake(snake)
            
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
    engine = GameEngine()
    
    start_server = websockets.serve(engine.on_client, os.getenv('IP', '0.0.0.0'), os.getenv('PORT', 8080))
    
    asyncio.get_event_loop().run_until_complete(start_server)
    logger.info("Listen")
    asyncio.get_event_loop().run_until_complete(engine.run())
    logger.info("Engin started")
    asyncio.get_event_loop().run_forever()