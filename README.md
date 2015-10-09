
      _____             _     __          __        _     _ 
     / ____|           | |    \ \        / /       | |   | |
    | (___  _ __   __ _| | ____\ \  /\  / /__  _ __| | __| |
     \___ \| '_ \ / _` | |/ / _ \ \/  \/ / _ \| '__| |/ _` |
     ____) | | | | (_| |   <  __/\  /\  / (_) | |  | | (_| |
    |_____/|_| |_|\__,_|_|\_\___| \/  \/ \___/|_|  |_|\__,_|
    --------------------------------------------------------


Hi there! Welcome to SnakeWorld !


## Implementation example (Python): RandomBot

```python

# randombot.py

from snakeworld.common import Direction
from snakeworld.client import BaseClient


class RandomBot(BaseClient):
    def evaluate(self):
        # Get a list of available directions
        directions = list(Direction)
        # Add None in the possible moves, sending None means keeping the current direction
        directions.append(None)
        # Choose a random direction
        direction = random.choice(directions)
        return direction
        

bot = RandomBot("MyAmazingBotName")
bot.run_until_complete()
```


## Implementation example (JavaScript): RandomBot


```js

// Connect to the server
websocket = new WebSocket('ws://5.39.83.97:8080/');

// Send bot name
websocket.send('{"name": "MyAmazingBotName"}');

// Define choices
choices = ['l', 'r', 'u', 'd', null];

// Implement a response to the server
websocket.onmessage = function (event) {
  // Choose a random move and send it back to the server
  websocket.send('{"direction": "' + choices[Math.floor(Math.random() * choices.length)] + '"}');
};
```


## Protocole


### Identification

On his conneciton the client must send an identification message containing his
name.

```json

{"name": "mybotname"}
```


### Game update

Every 100ms, the game engine do 1 step and send to all clients the new game state
using the following format:

```json
{
    "size": {
        "width": 200,
        "height": 100,
    },
    "snakes": [
        {
            "body": [
                {"x": 20, "y": 37},
                ..
            ],
            "name": "bot1",
            "color": "#128020",
            "direction": "u",
            "best_length": 27,
            "length": 17
        },
        ..
    ],
    "fruits": [
        {"x": 37, "y":43},
        ..
    ],
    "walls": [
        {"x": 37, "y":43},
        ..
    ],
    "step": 11367
}
```


### Action


The client can send at any moment an action to the server. The server make a step
every 100ms, in case the client send more than one action in less than 100ms the
server will only execute the last one.


```json

{"direction": "u"}
```

The possible actions are:

* "l" for left
* "r" for right
* "u" for up
* "d" for down
* null to keep the current direction
