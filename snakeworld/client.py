import asyncio
import json
import websockets
from server import Snake, Size, Direction, Fruit, Point

@asyncio.coroutine
def bot():
    websocket = yield from websockets.connect('ws://localhost:8080/')
    name = input("What's your name? ")
    play = False
    yield from websocket.send(json.dumps({'name': name}))
    print("> {}".format(name))
    while websocket.open:
        greeting = yield from websocket.recv()
        if greeting == "Success":
            play = True
        else:
            print("## START ROUND ##")
            snakes = {}
            fruits = []
            data = json.loads(greeting)
            map_size = Size(data['size']['width'], data['size']['height'])
            for snake in data['snakes']:
                s = Snake(None, map_size)
                s.name = snake['name']
                s.direction = Direction(snake['direction'])
                snakes[s.name] = s
            for fruit in data['fruits']:
                f = Fruit(map_size)
                f.position = Point(fruit['x'], fruit['y'])
                fruits.append(f)
            print("snakes : " + str(len(snakes.keys())))
            print("fruits : " + str(len(fruits)))
            print("map_size : " + str(map_size))
            print()
                
                    
    print("Websocket closed")
    yield from websocket.close()


asyncio.get_event_loop().run_until_complete(bot())