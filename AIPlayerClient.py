from collections import deque
import random
import os
import json
from dotenv import load_dotenv

import paho.mqtt.client as paho
from paho import mqtt
import time

game_running = False
next_move = False
game_state = None
game_map = [["N" for i in range(10)] for j in range(10)]
coins = set()
walls = set()

# setting callbacks for different events to see if it works, print the message etc.
def on_connect(client, userdata, flags, rc, properties=None):
    """
        Prints the result of the connection with a reasoncode to stdout ( used as callback for connect )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param flags: these are response flags sent by the broker
        :param rc: stands for reasonCode, which is a code for the connection result
        :param properties: can be used in MQTTv5, but is optional
    """
    print("CONNACK received with code %s." % rc)


# with this callback you can see if your publish was successful
def on_publish(client, userdata, mid, properties=None):
    """
        Prints mid to stdout to reassure a successful publish ( used as callback for publish )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param properties: can be used in MQTTv5, but is optional
    """
    print("mid: " + str(mid))


# print which topic was subscribed to
def on_subscribe(client, userdata, mid, granted_qos, properties=None):
    """
        Prints a reassurance for successfully subscribing
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param mid: variable returned from the corresponding publish() call, to allow outgoing messages to be tracked
        :param granted_qos: this is the qos that you declare when subscribing, use the same one for publishing
        :param properties: can be used in MQTTv5, but is optional
    """
    print("Subscribed: " + str(mid) + " " + str(granted_qos))


# print message, useful for checking if it was successful
def on_message(client, userdata, msg):
    """
        Prints a mqtt message to stdout ( used as callback for subscribe )
        :param client: the client itself
        :param userdata: userdata is set when initiating the client, here it is userdata=None
        :param msg: the message with topic and payload
    """
    print("message: " + msg.topic + " " + str(msg.qos) + " " + str(msg.payload))
    global game_running
    global next_move
    global game_state
    if 'Error' in msg.payload.decode():
        next_move = True
        game_running = False
    if msg.topic.endswith('/lobby') and msg.payload.decode() == 'Game Over: All coins have been collected':
        game_running = False
    elif msg.topic.endswith('/game_state'):
        next_move = True
        game_state = json.loads(msg.payload.decode())
    elif msg.topic.endswith('/start') and msg.payload.decode() == 'START':
        game_running = True

def lobby_prompt():
    print("Welcome to the Tech Assignment 1 Game as a Player!")
    option = ""
    while not option.isnumeric() or int(option) not in range(1, 2+1):
        print(
            "Select one of the following options:\n",
            "    1. Create a new lobby\n",
            "    2. Join a lobby"
        )
        option = input("Enter the digit corresponding to the option: ")
    lobby_name = input("Enter the name of the lobby: ")
    player_name = input("Enter your player name: ")
    team_name = input("Enter the name of the team you would like to join: ")
    match int(option):
        case 1:
            return (lobby_name, player_name, team_name, True)
        case 2:
            return (lobby_name, player_name, team_name, False)

def print_map():
    for i in range(len(game_map)):
        row = ""
        for j in range(len(game_map[0])):
            row += game_map[i][j] + " "
        print(row)

def construct_map():
    # how far the player can see on the map at any given time
    vision_radius = 2
    # get game position info
    player_pos = game_state["currentPosition"]
    obstacle_pos = game_state["walls"] + game_state["teammatePositions"] + game_state["enemyPositions"]
    coin_pos = game_state["coin1"] + game_state["coin2"] + game_state["coin3"]
    # calculate coordinates near player
    player_x, player_y = player_pos[0], player_pos[1]
    min_x = max(player_x - vision_radius, 0)
    max_x = min(player_x + vision_radius, 10)
    min_y = max(player_y - vision_radius, 0)
    max_y = min(player_y + vision_radius, 10)
    # reset space near player
    for x in range(min_x, max_x):
        for y in range(min_y, max_y):
            game_map[x][y] = "N"
    # place player
    game_map[player_x][player_y] = "P"
    # place obstacles
    for pos in obstacle_pos:
        game_map[pos[0]][pos[1]] = "O"
    # place coins
    for pos in coin_pos:
        game_map[pos[0]][pos[1]] = "C"

def bfs(start: tuple[int, int]):
    frontier = deque()
    explored = set()
    previous = {}
    # search for nearest coin using bfs
    explored.add(start)
    frontier.append(start)
    while len(frontier) != 0:
        current = frontier.popleft()
        for dir in directions:
            x = current[0]+dir[0]
            y = current[1]+dir[1]
            if valid_coord(x, y):
                s = game_map[x][y]
                neighbor = (x, y)
                if neighbor not in explored and s != "O":
                    explored.add(neighbor)
                    previous[neighbor] = current
                    if s == "C":
                        return move_from_path(start, previous, neighbor)
                    frontier.append(neighbor)
    return None

def valid_coord(x, y):
    return (x >= 0 and x < 10) and (y >= 0 and y < 10)

directions = [
    (-1, 0),
    (1, 0),
    (0, -1),
    (0, 1),
]

direction_mapping = {
    directions[0] : "UP",
    directions[1] : "DOWN",
    directions[2] : "LEFT",
    directions[3] : "RIGHT",
}

def move_from_path(start, previous, end):
    # backtrack from the end node to the front and return the next correct move
    current = end
    while previous[current] != start:
        current = previous[current]
    difference = (current[0]-start[0], current[1]-start[1])
    return direction_mapping[difference]

def make_move():
    # update the map with the current game state
    construct_map()
    # get player's current position
    player_pos = game_state["currentPosition"]
    start_node = (player_pos[0], player_pos[1])
    # find path to nearest coin using bfs
    new_move = bfs(start_node)
    # if no coin is found, move in a random direction until agent hits a wall, then switch direction
    if not new_move:
        new_move = gen_random_move(player_pos)
    return new_move

dir = directions[0]
def gen_random_move(pos):
    global dir
    x = pos[0] + dir[0]
    y = pos[1] + dir[1]
    # if neighboring cell in the current direction is not a valid move
    while not valid_coord(x, y) or game_map[x][y] == "O":
        # choose new direction in a counter-clockwise manner
        if direction_mapping[dir] == "UP":
            dir = directions[2]
        elif direction_mapping[dir] == "DOWN":
            dir = directions[3]
        elif direction_mapping[dir] == "LEFT":
            dir = directions[1]
        elif direction_mapping[dir] == "RIGHT":
            dir = directions[0]
        x = pos[0] + dir[0]
        y = pos[1] + dir[1]
    return direction_mapping[dir]

if __name__ == '__main__':
    load_dotenv(dotenv_path='./credentials.env')
    
    broker_address = os.environ.get('BROKER_ADDRESS')
    broker_port = int(os.environ.get('BROKER_PORT'))
    username = os.environ.get('USER_NAME')
    password = os.environ.get('PASSWORD')

    lobby_name, player_name, team_name, creating_lobby = lobby_prompt()

    client = paho.Client(callback_api_version=paho.CallbackAPIVersion.VERSION1, client_id=f"{player_name}", userdata=None, protocol=paho.MQTTv5)

    # enable TLS for secure connection
    client.tls_set(tls_version=mqtt.client.ssl.PROTOCOL_TLS)
    # set username and password
    client.username_pw_set(username, password)
    # connect to HiveMQ Cloud on port 8883 (default for MQTT)
    client.connect(broker_address, broker_port)

    # setting callbacks, use separate functions like above for better visibility
    client.on_subscribe = on_subscribe # Can comment out to not print when subscribing to new topics
    client.on_message = on_message
    client.on_publish = on_publish # Can comment out to not print when publishing to topics

    client.loop_start()

    client.subscribe(f"games/{lobby_name}/lobby", qos=2)
    client.subscribe(f'games/{lobby_name}/{player_name}/game_state', qos=2)
    client.subscribe(f'games/{lobby_name}/scores', qos=2)
    client.subscribe(f'games/{lobby_name}/start', qos=2)

    client.publish("new_game", json.dumps({'lobby_name' : lobby_name,
                                           'team_name' : team_name,
                                           'player_name' : player_name}), qos=2)
    time.sleep(1)

    if creating_lobby:
        print("Waiting for other players to join...")
        input("Press enter to start the game: ")
        client.publish(f"games/{lobby_name}/start", "START", qos=2)
        time.sleep(1)
    else:
        print("Waiting for game to start...")
        
    while not game_running:
        time.sleep(0.5) # Wait for game to start

    while True:
        while not next_move:
            time.sleep(0.5)
        time.sleep(0.5) # Wait for subsequent messages
        if not game_running:
            break
        move = make_move()
        next_move = False
        print("Decided on move:", move)
        client.publish(f"games/{lobby_name}/{player_name}/move", move, qos=2)
        time.sleep(0.5)
        print("Waiting for all players to make a move...")

    if creating_lobby:
        client.publish(f"games/{lobby_name}/start", "STOP", qos=2)
        time.sleep(1)

    print("Game has ended!")

    client.loop_stop()

