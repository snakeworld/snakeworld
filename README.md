
      _____             _     __          __        _     _ 
     / ____|           | |    \ \        / /       | |   | |
    | (___  _ __   __ _| | ____\ \  /\  / /__  _ __| | __| |
     \___ \| '_ \ / _` | |/ / _ \ \/  \/ / _ \| '__| |/ _` |
     ____) | | | | (_| |   <  __/\  /\  / (_) | |  | | (_| |
    |_____/|_| |_|\__,_|_|\_\___| \/  \/ \___/|_|  |_|\__,_|
    --------------------------------------------------------


Hi there! Welcome to SnakeWorld !


## Implementation example : RandomBot

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
```