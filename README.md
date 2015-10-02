
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
websocket = new WebSocket('ws://52.19.18.173:8080/');

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