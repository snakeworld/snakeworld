
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

class RandomBot(BaseClient):
    def evaluate(self):
        directions = list(Direction)
        directions.append(None)
        direction = random.choice(directions)
        return direction
```