import enum
import random
import uuid
import cgi


class Direction(enum.Enum):
    LEFT = 'l'
    RIGHT = 'r'
    UP = 'u'
    DOWN = 'd'


class Size:
    def __init__(self, width, height):
        self.width = width
        self.height = height
        
    def to_dict(self):
        return {'width': self.width, 'height': self.height}
        
    @classmethod
    def from_dict(cls, data):
        return cls(data['width'], data['height'])
        
    def __str__(self):
        return 'Size(%s, %s)' % (self.width, self.height)
        

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        
    @classmethod
    def get_random(cls, map_size):
        return cls(random.randint(10, map_size.width-10), random.randint(10, map_size.height-10))
        
    def to_dict(self):
        return {'x': self.x, 'y': self.y}
        
    @classmethod
    def from_dict(cls, data):
        return cls(data['x'], data['y'])
        
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
            
    def manathan_distance(self, other):
        return abs(self.x - other.x) + abs(self.y - other.y)
        
    def __eq__(self, other):
        return self.x == other.x and self.y == other.y
    
    def __str__(self):
        return "Point(%s, %s)" % (self.x, self.y)


class GameObject:
    def __init__(self, position):
        self.position = position
        
    @classmethod
    def create_random(cls, map_size):
        return cls(Point.get_random(map_size))
        
    def to_dict(self):
        return self.position.to_dict()

    @classmethod
    def from_dict(cls, data):
        return cls(Point.from_dict(data))
        
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
            return self.position == other.position
        
    def random_move(self, map_size):
        self.position.random_move(map_size)
        
    def manathan_distance(self, other):
        return self.position.manathan_distance(other.position)
    
    def __str__(self):
        return '%s(%s)' % (self.__class__.__name__, self.position)


class Snake(GameObject):
    def __init__(self, websocket):
        super().__init__(None)
        self.body = []
        self.direction = Direction.UP
        self.length = 1
        self.best_length = 1
        self.died = 0
        self.killed = 0
        self.name = str("Anonymous-%s" % uuid.uuid4())
        self.websocket = websocket
        r = lambda: random.randint(100,255)
        self.color = '#%02X%02X%02X' % (r(),r(),r())
        self.active = False
        
    @classmethod
    def create(cls, websocket, map_size):
        o = cls(websocket)
        o.reset(map_size)
        return o
        
    def activate(self, name, color):
        self.name = cgi.escape(name)[:20]
        if color:
            self.color = color
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
            
    def inc_length(self, inc=1):
        self.length += inc
        self.best_length = max(self.length, self.best_length)
    
    def reset(self, map_size):
        self.direction = random.choice(list(Direction))
        self.length = 6
        self.best_length = max(self.length, self.best_length)
        head = Point.get_random(map_size)
        self.body = [head]
        self.position = head
 
    def to_dict(self):
        return {
            'body': [p.to_dict() for p in self.body],
            'name': self.name,
            'color': self.color,
            'direction': self.direction.value,
            'best_length': self.best_length,
            'length': self.length,
            'died': self.died,
            'killed': self.killed,
        }
        
    @classmethod
    def from_dict(cls, data):
        o = cls(None)
        o.body = [Point.from_dict(d) for d in data['body']]
        o.position = o.body[0]
        o.name = data['name']
        o.color = data['color']
        o.direction = Direction(data['direction'])
        o.best_length = data['best_length']
        o.length = data['length']
        o.died = data['died']
        o.killed = data['killed']
        return o
        
    def change_direction(self, direction):
        if (direction == Direction.UP and self.direction == Direction.DOWN) \
            or (direction == Direction.DOWN and self.direction == Direction.UP) \
            or (direction == Direction.LEFT and self.direction == Direction.RIGHT) \
            or (direction == Direction.RIGHT and self.direction == Direction.LEFT):
                return
        self.direction = direction

    def __str__(self):
        return 'Snake(name=%r, direction=%s, position=%s, length=%s, best_length=%s)' % (
            self.name, self.direction.name, self.position, self.length, self.best_length)


class Fruit(GameObject):
    pass


class Wall(GameObject):
    pass


class GameState:
    def __init__(self, size, snakes=None, fruits=None, walls=None, step=0):
        self.size = size
        self.snakes = snakes or {}
        self.fruits = fruits or []
        self.walls = walls or []
        self.step = step
        
    def to_dict(self):
        state = {
            'size': self.size.to_dict(),
            'snakes': [snake.to_dict() for snake in self.snakes.values() if snake.active],
            'fruits': [fruit.to_dict() for fruit in self.fruits],
            'walls': [wall.to_dict() for wall in self.walls],
            'step': self.step,
        }
        return state
        
    @classmethod
    def from_dict(cls, data):
        snakes = [Snake.from_dict(d) for d in data['snakes']]
        return cls(
            size=Size.from_dict(data['size']),
            snakes=dict((s.name, s) for s in snakes),
            fruits=[Fruit.from_dict(d) for d in data['fruits']],
            walls=[Wall.from_dict(d) for d in data['walls']],
            step=data['step'],
        )